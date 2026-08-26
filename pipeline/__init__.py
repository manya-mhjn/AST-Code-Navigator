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

from pipeline.parser import FileParser, ParsedFile, stream_repo_files
from pipeline.node_extractor import ASTNodeExtractor
from pipeline.edge_extractor import ASTEdgeExtractor
from pipeline.vector_chunker import ASTVectorChunker
from pipeline.neo4j_sink import Neo4jCodeGraphIngestor
from pipeline.weaviate_sink import WeaviateCloudCodeDB
from pipeline.orchestrator import ingest_codebase

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
]
