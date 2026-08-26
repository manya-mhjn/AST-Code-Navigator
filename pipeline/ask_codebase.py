"""
ask_codebase.py — GraphRAG Code Navigator Engine.

Combines Vector Search (Weaviate) with Knowledge Graph Context (Neo4j)
to answer natural language questions about your codebase.
"""

from dotenv import load_dotenv
load_dotenv(override=True)

import sys
from pipeline.orchestrator import _require_env
from pipeline.neo4j_sink import Neo4jCodeGraphIngestor
from pipeline.weaviate_sink import WeaviateCloudCodeDB


class CodeNavigatorQueryEngine:
    def __init__(self):
        self.neo4j_db = Neo4jCodeGraphIngestor(
            uri=_require_env("NEO4J_URI"),
            auth=(_require_env("NEO4J_USER"), _require_env("NEO4J_PASSWORD"))
        )
        self.weaviate_db = WeaviateCloudCodeDB(
            cluster_url=_require_env("WEAVIATE_CLUSTER_URL"),
            api_key=_require_env("WEAVIATE_API_KEY")
        )

    def close(self):
        self.neo4j_db.close()
        self.weaviate_db.close()

    def ask(self, question: str, top_k: int = 3):
        print("\n" + "=" * 70)
        print(f"  QUESTION: \"{question}\"")
        print("=" * 70)

        # Step 1: Semantic Vector Search in Weaviate
        print("\n--- [Step 1] Vector Search (Weaviate Cloud) ---")
        vector_results = self.weaviate_db.search_code(query_text=question, limit=top_k)

        if not vector_results:
            print("No vector matches found. Make sure your codebase is ingested!")
            return

        for idx, match in enumerate(vector_results, 1):
            fn_name = match.get("name")
            file_path = match.get("file_path")
            distance = match.get("distance", 0.0)
            node_id = match.get("node_id")

            print(f"\n Match #{idx}: Function/Node '{fn_name}' (Distance: {distance:.4f})")
            print(f"   Location: {file_path}")

            # Step 2: Knowledge Graph Traversal in Neo4j
            print("   --- [Step 2] Graph Context (Neo4j) ---")
            self._fetch_graph_context(node_id, fn_name, file_path)

            print("   --- Code Snippet ---")
            snippet = match.get("content", "").strip()
            first_lines = "\n   ".join(snippet.splitlines()[:10])
            print(f"   {first_lines}")
            if len(snippet.splitlines()) > 10:
                print("   ...")

    def _fetch_graph_context(self, node_id: str, fn_name: str, file_path: str):
        with self.neo4j_db.driver.session() as session:
            # A. Who calls this function? (Callers)
            callers_res = session.run("""
                MATCH (caller)-[:RESOLVED_CALLS|CALLS]->(fn)
                WHERE fn.id = $id OR fn.name = $name
                RETURN caller.id AS Caller, caller.name AS CallerName
                LIMIT 5
            """, id=node_id, name=fn_name)
            callers = [r["CallerName"] or r["Caller"] for r in callers_res]

            # B. What functions does this function call? (Callees)
            callees_res = session.run("""
                MATCH (fn)-[:RESOLVED_CALLS|CALLS]->(callee)
                WHERE fn.id = $id OR fn.name = $name
                RETURN callee.name AS CalleeName, callee.id AS CalleeId
                LIMIT 5
            """, id=node_id, name=fn_name)
            callees = [r["CalleeName"] or r["CalleeId"] for r in callees_res]

            # C. Environment Variables Used
            env_res = session.run("""
                MATCH (fn)-[:USES_ENV]->(e:EnvVar)
                WHERE fn.id = $id OR fn.name = $name
                RETURN e.id AS EnvVar
            """, id=node_id, name=fn_name)
            env_vars = [r["EnvVar"] for r in env_res]

            # Print Graph Synthesis
            if callers:
                print(f"   • Called By: {', '.join(callers)}")
            else:
                print("   • Called By: (No direct internal callers detected)")

            if callees:
                print(f"   • Calls Out To: {', '.join(callees)}")
            else:
                print("   • Calls Out To: (No external function calls)")

            if env_vars:
                print(f"   • Uses Env Vars: {', '.join(env_vars)}")


if __name__ == "__main__":
    query_engine = CodeNavigatorQueryEngine()
    question = sys.argv[1] if len(sys.argv) > 1 else "How to load adventure workflow in game?"
    query_engine.ask(question)
    query_engine.close()
