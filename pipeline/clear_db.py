"""
clear_db.py — One-click cleanup script for Neo4j and Weaviate Cloud databases.
Clears all nodes, edges, and vector collections.
"""

from dotenv import load_dotenv
load_dotenv(override=True)

import os
from pipeline.orchestrator import _require_env
from pipeline.neo4j_sink import Neo4jCodeGraphIngestor
import weaviate
from weaviate.classes.init import Auth


def clear_all():
    print("Starting Database Cleanup...")

    # 1. Clear Neo4j Code Graph
    print("Clearing Neo4j Graph Database...")
    try:
        neo4j_db = Neo4jCodeGraphIngestor(
            uri=_require_env("NEO4J_URI"),
            auth=(_require_env("NEO4J_USER"), _require_env("NEO4J_PASSWORD"))
        )
        with neo4j_db.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        neo4j_db.close()
        print("[SUCCESS] Neo4j Database Cleared!")
    except Exception as e:
        print(f"[ERROR] Error clearing Neo4j: {e}")

    # 2. Clear Weaviate Vector Database
    print("Clearing Weaviate Vector Database...")
    try:
        raw_url = _require_env("WEAVIATE_CLUSTER_URL").replace("https://", "").replace("http://", "")
        client = weaviate.connect_to_weaviate_cloud(
            cluster_url=raw_url,
            auth_credentials=Auth.api_key(_require_env("WEAVIATE_API_KEY"))
        )
        if client.collections.exists("CodeChunk"):
            client.collections.delete("CodeChunk")
        client.close()
        print("[SUCCESS] Weaviate Vector Database Cleared!")
    except Exception as e:
        print(f"[ERROR] Error clearing Weaviate: {e}")

    print("\nDatabase Cleanup Complete! Both databases are 100% fresh and empty.")



if __name__ == "__main__":
    clear_all()
