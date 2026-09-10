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
    "CodeIntentClassifier",
    "classify_intent",
    "tool_classify_intent",
    "tool_traverse_call_graph",
    "tool_calculate_blast_radius",
    "tool_trace_parameter_lineage",
    "tool_query_variable_and_state_references",
    "tool_inspect_type_and_inheritance_hierarchy",
    "tool_get_symbol_code_snippet",
    "tool_analyze_architecture_coupling",
    "tool_detect_orphan_and_dead_code",
    "tool_trace_taint_and_security_paths",
    "tool_search_codebase_semantic",
    "tool_query_test_traceability",
    "tool_query_api_endpoints",
    "ALL_TOOLS",
    "ExecutionStrategy",
    "TASK_DEFINITIONS",
    "CodeNavigatorAgent",
    "route_query",
    "build_agentic_graph",
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
    "traverse_call_graph": ("pipeline.graph_traversal", "traverse_call_graph"),
    "CodeIntentClassifier": ("pipeline.tools", "CodeIntentClassifier"),
    "classify_intent": ("pipeline.tools", "classify_intent"),
    "tool_classify_intent": ("pipeline.tools", "tool_classify_intent"),
    "tool_traverse_call_graph": ("pipeline.tools", "tool_traverse_call_graph"),
    "tool_calculate_blast_radius": ("pipeline.tools", "tool_calculate_blast_radius"),
    "tool_trace_parameter_lineage": ("pipeline.tools", "tool_trace_parameter_lineage"),
    "tool_query_variable_and_state_references": ("pipeline.tools", "tool_query_variable_and_state_references"),
    "tool_inspect_type_and_inheritance_hierarchy": ("pipeline.tools", "tool_inspect_type_and_inheritance_hierarchy"),
    "tool_get_symbol_code_snippet": ("pipeline.tools", "tool_get_symbol_code_snippet"),
    "tool_analyze_architecture_coupling": ("pipeline.tools", "tool_analyze_architecture_coupling"),
    "tool_detect_orphan_and_dead_code": ("pipeline.tools", "tool_detect_orphan_and_dead_code"),
    "tool_trace_taint_and_security_paths": ("pipeline.tools", "tool_trace_taint_and_security_paths"),
    "tool_search_codebase_semantic": ("pipeline.tools", "tool_search_codebase_semantic"),
    "tool_query_test_traceability": ("pipeline.tools", "tool_query_test_traceability"),
    "tool_query_api_endpoints": ("pipeline.tools", "tool_query_api_endpoints"),
    "ALL_TOOLS": ("pipeline.tools", "ALL_TOOLS"),
    "ExecutionStrategy": ("pipeline.tools_utils", "ExecutionStrategy"),
    "TASK_DEFINITIONS": ("pipeline.tools_utils", "TASK_DEFINITIONS"),
    "CodeNavigatorAgent": ("pipeline.agentic", "CodeNavigatorAgent"),
    "route_query": ("pipeline.agentic", "route_query"),
    "build_agentic_graph": ("pipeline.agentic", "build_agentic_graph"),
}


def __getattr__(name: str):
    if name in _EXPORTS:
        module_name, attr_name = _EXPORTS[name]
        module = importlib.import_module(module_name)
        return getattr(module, attr_name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
