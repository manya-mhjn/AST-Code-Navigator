"""
orchestrator.py — Pipeline orchestration for codebase ingestion.

Wires together the pipeline stages:
  FileParser → NodeExtractor → EdgeExtractor → VectorChunker → Sinks

This is the single entry point for running the full ingestion pipeline.
"""

import os

from pipeline.parser import FileParser, stream_repo_files
from pipeline.node_extractor import ASTNodeExtractor
from pipeline.edge_extractor import ASTEdgeExtractor
from pipeline.vector_chunker import ASTVectorChunker
from pipeline.neo4j_sink import Neo4jCodeGraphIngestor
from pipeline.weaviate_sink import WeaviateCloudCodeDB
from pipeline.symbol_resolver import SymbolResolver
from dotenv import load_dotenv


load_dotenv(override=True)  


def _require_env(name: str) -> str:
    """Fail fast with a clear message if a required env var is missing."""
    value = os.environ.get(name)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{name}' is not set. "
            f"Set it via: export {name}=<value>"
        )
    return value


def ingest_codebase(repo_path: str):
    """
    Main pipeline orchestrator.

    Flow:
        1. FileParser reads + parses each .py file ONCE → ParsedFile
        2. ASTNodeExtractor extracts nodes from the parsed tree (pure logic)
        3. ASTEdgeExtractor extracts edges from the parsed tree + nodes (pure logic)
        4. ASTVectorChunker creates vector documents from parsed tree + nodes (pure logic)
        5. Neo4j sink ingests nodes and edges
        6. Weaviate sink ingests vector documents
    """
    print("Initializing Pipeline...")

    # --- Foundation: single parser instance ---
    file_parser = FileParser()

    # --- Extractors: pure logic, no I/O ---
    node_extractor = ASTNodeExtractor()
    edge_extractor = ASTEdgeExtractor()
    vector_chunker = ASTVectorChunker()

    # --- Sinks: database connections ---
    neo4j_db = Neo4jCodeGraphIngestor(
        uri=_require_env("NEO4J_URI"),
        auth=(_require_env("NEO4J_USER"), _require_env("NEO4J_PASSWORD"))
    )

    weaviate_db = WeaviateCloudCodeDB(
        cluster_url=_require_env("WEAVIATE_CLUSTER_URL"),
        api_key=_require_env("WEAVIATE_API_KEY")
    )

    try:
        # Setup database schemas
        neo4j_db.setup_database_indexes()
        weaviate_db.setup_schema()

        print(f"\nIngesting codebase: {repo_path}")
        files_processed = 0
        files_failed = 0

        for file_path in stream_repo_files(repo_path):
            try:
                print(f"Processing: {file_path}")

                # 1. Parse file ONCE (the single I/O boundary)
                parsed_file = file_parser.parse_file(file_path)

                # 2. Extract nodes (pure logic — no file I/O)
                nodes = node_extractor.fetch_nodes(parsed_file, project_root=repo_path)

                # 3. Extract edges (pure logic — no file I/O)
                edges = edge_extractor.extract_edges(parsed_file, nodes=nodes)

                # 4. Create vector documents (pure logic — no file I/O)
                vector_docs = vector_chunker.create_vector_documents(parsed_file, nodes)

                # 5. Ingest into Neo4j
                neo4j_db.ingest_nodes(nodes)
                neo4j_db.ingest_edges(edges)

                # 6. Ingest into Weaviate
                if vector_docs:
                    weaviate_db.insert_code_chunks(vector_docs)

                files_processed += 1

            except Exception as e:
                files_failed += 1
                print(f"ERROR processing {file_path}: {e}")
                continue
        
        print("Triggering Phase 2 (Post-Ingestion Symbol Resolution)...")
        resolver = SymbolResolver(neo4j_db.driver)
        resolver.resolve_and_ingest()
        
        print(f"\n🎉 Codebase Ingestion Complete!")
        print(f"   Files processed: {files_processed}")
        print(f"   Files failed: {files_failed}")

    finally:
        neo4j_db.close()
        weaviate_db.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m pipeline.orchestrator <repo_path>")
        sys.exit(1)
    ingest_codebase(sys.argv[1])
