"""
query_graph_and_vector.py — Query script for CodeNavigator.

Queries Neo4j Graph Database for node & edge counts and cross-file relationships,
and queries Weaviate Vector Database for semantic code chunk search.
"""

from dotenv import load_dotenv
load_dotenv(override=True)

import os
from pipeline.orchestrator import _require_env
from pipeline.neo4j_sink import Neo4jCodeGraphIngestor
from pipeline.weaviate_sink import WeaviateCloudCodeDB


def inspect_neo4j_graph():
    print("=" * 60)
    print(" NEO4J CODE GRAPH ANALYSIS")
    print("=" * 60)

    neo4j_db = Neo4jCodeGraphIngestor(
        uri=_require_env("NEO4J_URI"),
        auth=(_require_env("NEO4J_USER"), _require_env("NEO4J_PASSWORD"))
    )

    with neo4j_db.driver.session() as session:
        # 1. Total Nodes by Label
        print("\n--- 1. Node Counts by Label ---")
        node_result = session.run("""
            MATCH (n)
            RETURN labels(n)[0] AS Label, count(n) AS Count
            ORDER BY Count DESC
        """)
        nodes_found = False
        for record in node_result:
            nodes_found = True
            print(f"  * {record['Label']}: {record['Count']} nodes")
        if not nodes_found:
            print("  (No nodes currently in Neo4j database)")

        # 2. Total Edges by Relationship Type
        print("\n--- 2. Relationship Counts by Type ---")
        edge_result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) AS RelationshipType, count(r) AS Count
            ORDER BY Count DESC
        """)
        edges_found = False
        for record in edge_result:
            edges_found = True
            print(f"  * {record['RelationshipType']}: {record['Count']} edges")
        if not edges_found:
            print("  (No relationships currently in Neo4j database)")

        # 3. Detailed Resolved Relationships Breakdown
        print("\n--- 3. Cross-File & Resolved Edges Sample ---")
        rel_sample = session.run("""
            MATCH (src)-[r]->(tgt)
            WHERE type(r) IN ['RESOLVED_CALLS', 'INSTANTIATES', 'RESOLVED_INHERITS', 'RESOLVED_USES_VARIABLE', 'RESOLVED_USES_INST_ATTR', 'IMPORTS', 'USES_ENV']
            RETURN src.id AS Source, type(r) AS Edge, tgt.id AS Target
            LIMIT 10
        """)
        sample_found = False
        for record in rel_sample:
            sample_found = True
            print(f"  ({record['Source']}) -[:{record['Edge']}]-> ({record['Target']})")
        if not sample_found:
            print("  (No resolved cross-file edges found yet. Run orchestrator to populate!)")

    neo4j_db.close()


def query_weaviate_vector_db(query_text: str = "database connection and queries"):
    print("\n" + "=" * 60)
    print(f" WEAVIATE VECTOR SEARCH: '{query_text}'")
    print("=" * 60)

    try:
        weaviate_db = WeaviateCloudCodeDB(
            cluster_url=_require_env("WEAVIATE_CLUSTER_URL"),
            api_key=_require_env("WEAVIATE_API_KEY")
        )

        results = weaviate_db.search_code(query_text=query_text, limit=3)

        if not results:
            print("  (No vector matches found in Weaviate. Run orchestrator to populate!)")
        else:
            for i, res in enumerate(results, 1):
                print(f"\n--- Match #{i} (Distance: {res.get('distance'):.4f}) ---")
                print(f"File: {res.get('file_path')}")
                print(f"Node / Function: {res.get('name')}")
                print(f"Type: {res.get('chunk_type')}")
                print(f"Content Snippet:\n{res.get('content')[:200]}...")

        weaviate_db.close()
    except Exception as e:
        print(f"Error querying Weaviate: {e}")


if __name__ == "__main__":
    inspect_neo4j_graph()
    query_weaviate_vector_db("database connection and queries")
