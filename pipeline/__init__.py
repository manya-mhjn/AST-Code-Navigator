"""
pipeline — AST-based Code Knowledge Graph ingestion pipeline.

Architecture:
    FileParser (single I/O boundary)
        → ASTNodeExtractor (pure logic)
        → ASTEdgeExtractor (pure logic)
        → ASTVectorChunker (pure logic)
        → Neo4j Sink / Weaviate Sink

Usage:
    from pipeline.orchestrator import ingest_codebase
    ingest_codebase("path/to/repo")
"""

import importlib

__all__ = [
    "FileParser",
    "ParsedFile",
    "stream_repo_files",
    "ASTNodeExtractor",
    "ASTEdgeExtractor",
    "ASTVectorChunker",
    "Neo4jCodeGraphIngestor",
    "WeaviateCloudCodeDB",
    "ingest_codebase",
    "CallGraphTraversal",
    "traverse_call_graph",
]

_EXPORTS = {
    "FileParser": ("pipeline.parser", "FileParser"),
    "ParsedFile": ("pipeline.parser", "ParsedFile"),
    "stream_repo_files": ("pipeline.parser", "stream_repo_files"),
    "ASTNodeExtractor": ("pipeline.node_extractor", "ASTNodeExtractor"),
    "ASTEdgeExtractor": ("pipeline.edge_extractor", "ASTEdgeExtractor"),
    "ASTVectorChunker": ("pipeline.vector_chunker", "ASTVectorChunker"),
    "Neo4jCodeGraphIngestor": ("pipeline.neo4j_sink", "Neo4jCodeGraphIngestor"),
    "WeaviateCloudCodeDB": ("pipeline.weaviate_sink", "WeaviateCloudCodeDB"),
    "ingest_codebase": ("pipeline.orchestrator", "ingest_codebase"),
    "CallGraphTraversal": ("pipeline.graph_traversal", "CallGraphTraversal"),
    "traverse_call_graph": ("pipeline.graph_traversal", "traverse_call_graph")
}


def __getattr__(name: str):
    if name in _EXPORTS:
        module_name, attr_name = _EXPORTS[name]
        module = importlib.import_module(module_name)
        return getattr(module, attr_name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
