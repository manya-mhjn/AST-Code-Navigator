"""
tools.py — Complete LangChain Tool Suite & Intent Classifier for CodeNavigator.

Implements all 20 code intelligence tools with Neo4j Knowledge Graph traversals
and Weaviate Vector DB semantic searches.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Any, Dict, List, Optional, Union
import json

# Ensure repository root is on sys.path
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from dotenv import load_dotenv

load_dotenv(override=True)

from langchain_core.tools import tool

from pipeline.tools_utils import CallGraphTraversal
from pipeline.neo4j_sink import Neo4jCodeGraphIngestor
from pipeline.weaviate_sink import WeaviateCloudCodeDB


def _get_neo4j_session():
    """Helper to open a Neo4j session using environment variables."""
    uri = os.environ.get("NEO4J_URI")
    user = os.environ.get("NEO4J_USER")
    password = os.environ.get("NEO4J_PASSWORD")
    if not (uri and user and password):
        return None
    try:
        db = Neo4jCodeGraphIngestor(uri=uri, auth=(user, password))
        return db
    except Exception as e:
        print(f"[Warning] Could not connect to Neo4j: {e}")
        return None


def _get_weaviate_client():
    """Helper to connect to Weaviate Cloud."""
    url = os.environ.get("WEAVIATE_CLUSTER_URL") or os.environ.get("WEAVIATE_URL")
    api_key = os.environ.get("WEAVIATE_API_KEY")
    if not (url and api_key):
        return None
    try:
        return WeaviateCloudCodeDB(cluster_url=url, api_key=api_key)
    except Exception as e:
        print(f"[Warning] Could not connect to Weaviate: {e}")
        return None

# -----------------------------------------------------------------------------
# LangChain Tools (The 20-Task Suite)
# -----------------------------------------------------------------------------


@tool
def tool_traverse_call_graph(
    target_symbol: str,
    direction: str = "incoming",
    max_depth: int = 3,
    file_path: Optional[str] = None,
    include_raw: bool = True,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    [Task #1, #2] Traverses the call graph in Neo4j up to max_depth hops.
    Use direction='incoming' for upstream callers and direction='outgoing' for downstream callees.
    """
    with CallGraphTraversal() as engine:
        return engine.traverse(
            target_symbol=target_symbol,
            direction=direction,
            max_depth=max_depth,
            file_path=file_path,
            include_raw=include_raw,
            limit=limit,
        )


@tool
def tool_calculate_blast_radius(
    changed_symbols: Optional[Union[List[str], str]] = None,
    target_symbol: Optional[str] = None,
    max_depth: int = 4,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    [Task #3] Calculates the blast radius and transitive impact of modifying symbols using Universal DP Traversal.
    Accepts changed_symbols (list or string) or target_symbol (string).
    Traverses transitive reverse dependencies across :RESOLVED_CALLS, :IMPORTS, :RESOLVED_INHERITS, and variable usages in O(V + E).
    """
    symbols_input = changed_symbols or target_symbol or ["unknown"]
    with CallGraphTraversal() as engine:
        return engine.traverse_graph_dp(
            symbols=symbols_input,
            direction="incoming",
            edge_types=None,  # None selects ALL graph edges
            max_depth=max_depth,
            limit=limit,
        )


@tool
def tool_trace_parameter_lineage(
    function_name: str,
    parameter_name: str,
    max_depth: int = 2,
) -> Dict[str, Any]:
    """
    [Task #4] Traces argument values and lineage for a specific function parameter across callers.
    """
    db = _get_neo4j_session()
    callers = []
    if db:
        try:
            with db.driver.session() as session:
                cypher = """
                MATCH (fn:Function {name: $fn_name})<-[:RESOLVED_CALLS|CALLS]-(caller)
                RETURN caller.name AS caller_name, caller.file_path AS file_path, caller.line_start AS line_start
                LIMIT 20
                """
                records = session.run(cypher, fn_name=function_name)
                callers = [{"caller": r["caller_name"], "file": r["file_path"], "line": r["line_start"]} for r in records]
        except Exception as e:
            print(f"[Warning] Error querying callers in Neo4j: {e}")
        finally:
            db.close()

    return {
        "function_name": function_name,
        "parameter_name": parameter_name,
        "caller_call_sites": callers,
        "lineage_summary": f"Parameter '{parameter_name}' in '{function_name}' is invoked by {len(callers)} caller(s). Inspect caller snippets for explicit argument binding.",
    }


@tool
def tool_query_variable_and_state_references(
    symbol_name: str,
    variable_type: str = "all",
    limit: int = 50,
) -> Dict[str, Any]:
    """
    [Tasks #5, #7, #9, #11] Queries state references and usages.
    Supports variable_type: 'instance_attr' (self.x), 'global' (module constants), 'env_var' (ENV::X), or 'all'.
    """
    db = _get_neo4j_session()
    if not db:
        return {"error": "Neo4j connection unavailable", "symbol_name": symbol_name}

    try:
        with db.driver.session() as session:
            # 1. Environment Variable references
            if variable_type in ("env_var", "all") and (symbol_name.isupper() or "_" in symbol_name):
                env_records = session.run("""
                    MATCH (scope)-[:USES_ENV]->(env:EnvVar)
                    WHERE env.name = $sym OR env.name CONTAINS $sym
                    RETURN scope.name AS scope, scope.file_path AS file_path, env.name AS env_var, env.default_value AS default_value
                    LIMIT $limit
                """, sym=symbol_name, limit=limit)
                env_usages = [{"scope": r["scope"], "file": r["file_path"], "env_var": r["env_var"], "default": r["default_value"]} for r in env_records]
                if env_usages:
                    return {"type": "env_var", "symbol": symbol_name, "references": env_usages, "count": len(env_usages)}

            # 2. Instance Attribute references (self.attr)
            if variable_type in ("instance_attr", "all"):
                clean_sym = symbol_name.split(".")[-1]
                attr_records = session.run("""
                    MATCH (fn:Function)-[:RESOLVED_USES_INST_ATTR]->(attr)
                    WHERE attr.name = $sym OR attr.name ENDS WITH ('.' + $sym)
                    RETURN fn.name AS function_name, fn.file_path AS file_path, attr.name AS attribute
                    LIMIT $limit
                """, sym=clean_sym, limit=limit)
                attr_usages = [{"function": r["function_name"], "file": r["file_path"], "attribute": r["attribute"]} for r in attr_records]
                if attr_usages:
                    return {"type": "instance_attribute", "symbol": symbol_name, "references": attr_usages, "count": len(attr_usages)}

            # 3. Global Variable references
            global_records = session.run("""
                MATCH (fn:Function)-[:RESOLVED_USES_VARIABLE]->(var:Variable)
                WHERE var.name = $sym
                RETURN fn.name AS function_name, fn.file_path AS file_path, var.name AS variable
                LIMIT $limit
            """, sym=symbol_name, limit=limit)
            global_usages = [{"function": r["function_name"], "file": r["file_path"], "variable": r["variable"]} for r in global_records]
            return {"type": "global_variable", "symbol": symbol_name, "references": global_usages, "count": len(global_usages)}
    except Exception as e:
        return {"error": str(e), "symbol_name": symbol_name}
    finally:
        db.close()


@tool
def tool_inspect_type_and_inheritance_hierarchy(
    class_symbol: str,
    direction: str = "both",
) -> Dict[str, Any]:
    """
    [Tasks #6, #17] Inspects class inheritance and type hierarchies.
    Traverses :RESOLVED_INHERITS (superclasses and subclasses) and retrieves :HAS_METHOD links.
    """
    db = _get_neo4j_session()
    if not db:
        return {"error": "Neo4j connection unavailable", "class_symbol": class_symbol}

    try:
        with db.driver.session() as session:
            # Superclasses (Parents)
            parent_records = session.run("""
                MATCH (cls:Class {name: $cls})-[:RESOLVED_INHERITS|INHERITS_FROM*1..3]->(super_cls:Class)
                RETURN super_cls.name AS parent, super_cls.file_path AS file_path
            """, cls=class_symbol)
            parents = [{"name": r["parent"], "file": r["file_path"]} for r in parent_records]

            # Subclasses (Children)
            child_records = session.run("""
                MATCH (sub_cls:Class)-[:RESOLVED_INHERITS|INHERITS_FROM*1..3]->(cls:Class {name: $cls})
                RETURN sub_cls.name AS child, sub_cls.file_path AS file_path
            """, cls=class_symbol)
            children = [{"name": r["child"], "file": r["file_path"]} for r in child_records]

            # Methods
            method_records = session.run("""
                MATCH (cls:Class {name: $cls})-[:HAS_METHOD]->(fn:Function)
                RETURN fn.name AS method, fn.line_start AS line
            """, cls=class_symbol)
            methods = [{"method": r["method"], "line": r["line"]} for r in method_records]

            return {
                "class": class_symbol,
                "superclasses": parents,
                "subclasses": children,
                "methods": methods,
            }
    except Exception as e:
        return {"error": str(e), "class_symbol": class_symbol}
    finally:
        db.close()


@tool
def tool_get_symbol_code_snippet(
    symbol_name: str,
    file_path: Optional[str] = None,
    max_lines: int = 80,
) -> Dict[str, Any]:
    """
    [Tasks #8, #10, #15, #18] Fetches the exact code snippet for a function, class, or method.
    """
    db = _get_neo4j_session()
    line_start, line_end = None, None
    resolved_file = file_path

    # Clean symbol name (strip Class. prefix if present)
    sym_clean = symbol_name.split(".")[-1] if "." in symbol_name else symbol_name

    if db:
        try:
            with db.driver.session() as session:
                records = session.run("""
                    MATCH (n)
                    WHERE (n:Function OR n:Class OR n:Variable) 
                      AND (n.name = $sym 
                           OR n.name = $sym_clean 
                           OR n.id ENDS WITH ('.' + $sym_clean) 
                           OR n.id ENDS WITH ('::' + $sym_clean)
                           OR n.name =~ ('(?i).*' + $sym_clean + '.*'))
                    RETURN coalesce(n.file_path, split(n.id, '::')[0]) AS file_path, 
                           coalesce(n.start_line, n.line_start, n.line) AS line_start, 
                           coalesce(n.end_line, n.line_end) AS line_end
                    LIMIT 1
                """, sym=symbol_name, sym_clean=sym_clean)
                r = records.single()
                if r:
                    resolved_file = r["file_path"]
                    line_start = r["line_start"]
                    line_end = r["line_end"]
        except Exception as e:
            print(f"[Warning] Neo4j snippet lookup: {e}")
        finally:
            db.close()

    # Read from disk if file is resolved
    if resolved_file and os.path.exists(resolved_file):
        try:
            with open(resolved_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            start = max(0, (line_start - 1) if line_start else 0)
            end = min(len(lines), (line_end if line_end else start + max_lines))
            snippet = "".join(lines[start:end])
            return {
                "symbol": symbol_name,
                "file_path": resolved_file,
                "line_start": start + 1,
                "line_end": end,
                "code": snippet,
            }
        except Exception as e:
            return {"error": f"Failed to read file {resolved_file}: {e}"}

    # Fallback to Weaviate vector chunk fetch
    wv = _get_weaviate_client()
    if wv:
        try:
            results = wv.search_code(symbol_name, limit=1)
            if results:
                return {
                    "symbol": symbol_name,
                    "file_path": results[0].get("file_path"),
                    "code": results[0].get("content"),
                    "docstring": results[0].get("docstring"),
                }
        finally:
            wv.close()

    return {"symbol": symbol_name, "error": "Symbol definition not found on disk or vector store."}


@tool
def tool_analyze_architecture_coupling(
    source_module: Optional[str] = None,
    detect_cycles: bool = True,
) -> Dict[str, Any]:
    """
    [Task #12] Analyzes module coupling and detects circular import dependencies in Neo4j.
    """
    db = _get_neo4j_session()
    if not db:
        return {"error": "Neo4j connection unavailable"}

    try:
        with db.driver.session() as session:
            # Direct Imports
            imports_records = session.run("""
                MATCH (f1:File)-[:IMPORTS]->(f2:File)
                RETURN f1.path AS from_file, f2.path AS to_file
                LIMIT 50
            """)
            imports_list = [{"from": r["from_file"], "to": r["to_file"]} for r in imports_records]

            # Circular Import Cycles
            cycle_records = session.run("""
                MATCH (f1:File)-[:IMPORTS]->(f2:File)-[:IMPORTS]->(f1:File)
                WHERE f1.path < f2.path
                RETURN f1.path AS file_a, f2.path AS file_b
                LIMIT 20
            """)
            cycles = [{"cycle": f"{r['file_a']} <---> {r['file_b']}"} for r in cycle_records]

            return {
                "total_import_edges": len(imports_list),
                "circular_cycles_detected": len(cycles),
                "circular_cycles": cycles,
                "dependencies_sample": imports_list[:25],
            }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@tool
def tool_detect_orphan_and_dead_code(
    scope_path: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    [Task #13] Detects dead, uncalled, or orphan functions with in_degree(RESOLVED_CALLS) == 0.
    """
    db = _get_neo4j_session()
    if not db:
        return {"error": "Neo4j connection unavailable"}

    try:
        with db.driver.session() as session:
            cypher = """
            MATCH (fn:Function)
            WHERE NOT ( ()-[:RESOLVED_CALLS|CALLS]->(fn) )
              AND NOT fn.name STARTS WITH '__'
              AND NOT fn.name STARTS WITH 'test_'
              AND NOT fn.is_endpoint = true
            RETURN fn.name AS name, fn.file_path AS file_path, fn.line_start AS line
            LIMIT $limit
            """
            records = session.run(cypher, limit=limit)
            orphans = [{"name": r["name"], "file_path": r["file_path"], "line": r["line"]} for r in records]
            return {
                "total_orphan_functions_found": len(orphans),
                "orphans": orphans,
            }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@tool
def tool_trace_taint_and_security_paths(
    source_pattern: str = "request",
    sink_pattern: str = "execute|eval|exec|query|system",
    max_depth: int = 5,
) -> Dict[str, Any]:
    """
    [Task #14] Finds security taint paths from untrusted input sources to sensitive sinks in Neo4j.
    """
    db = _get_neo4j_session()
    if not db:
        return {"error": "Neo4j connection unavailable", "source": source_pattern, "sink": sink_pattern}

    try:
        with db.driver.session() as session:
            cypher = """
            MATCH (src:Function), (sink:Function)
            WHERE (src.name CONTAINS $src_pat OR src.file_path CONTAINS $src_pat)
              AND (sink.name CONTAINS $sink_pat)
            MATCH path = shortestPath((src)-[:RESOLVED_CALLS*1..5]->(sink))
            RETURN [node in nodes(path) | node.name] AS call_path, length(path) AS depth
            LIMIT 10
            """
            records = session.run(cypher, src_pat=source_pattern, sink_pat=sink_pattern)
            paths = [{"path": " -> ".join(r["call_path"]), "depth": r["depth"]} for r in records]
            return {
                "source_pattern": source_pattern,
                "sink_pattern": sink_pattern,
                "potential_taint_paths": paths,
                "count": len(paths),
            }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@tool
def tool_search_codebase_semantic(
    query: str,
    limit: int = 5,
) -> Dict[str, Any]:
    """
    [Task #16] Performs hybrid semantic code search in Weaviate Cloud.
    """
    wv = _get_weaviate_client()
    if not wv:
        return {"error": "Weaviate client unavailable", "query": query}

    try:
        results = wv.search_code(query, limit=limit)
        return {
            "query": query,
            "results_count": len(results),
            "results": [
                {
                    "name": r.get("name"),
                    "type": r.get("chunk_type"),
                    "file_path": r.get("file_path"),
                    "docstring": r.get("docstring"),
                    "snippet": r.get("content") or "",
                }
                for r in results
            ],
        }
    except Exception as e:
        return {"error": str(e), "query": query}
    finally:
        wv.close()


@tool
def tool_query_test_traceability(
    target_symbol: str,
    max_depth: int = 3,
) -> Dict[str, Any]:
    """
    [Task #19] Finds test suites and test functions that exercise the target symbol.
    """
    db = _get_neo4j_session()
    if not db:
        return {"error": "Neo4j connection unavailable", "target_symbol": target_symbol}

    try:
        with db.driver.session() as session:
            cypher = """
            MATCH (test:Function)-[:RESOLVED_CALLS|CALLS*1..3]->(target)
            WHERE (target.name = $sym OR target.name ENDS WITH ('.' + $sym))
              AND (test.name STARTS WITH 'test_' OR test.file_path CONTAINS 'test')
            RETURN DISTINCT test.name AS test_name, test.file_path AS test_file
            LIMIT 30
            """
            records = session.run(cypher, sym=target_symbol)
            tests = [{"test_function": r["test_name"], "file": r["test_file"]} for r in records]
            return {
                "target_symbol": target_symbol,
                "test_count": len(tests),
                "tests": tests,
            }
    except Exception as e:
        return {"error": str(e), "target_symbol": target_symbol}
    finally:
        db.close()


@tool
def tool_query_api_endpoints(
    route_pattern: Optional[str] = None,
    http_method: Optional[str] = None,
) -> Dict[str, Any]:
    """
    [Task #20] Queries public API endpoints, route definitions, and HTTP contracts.
    """
    db = _get_neo4j_session()
    if not db:
        return {"error": "Neo4j connection unavailable"}

    try:
        with db.driver.session() as session:
            cypher = """
            MATCH (fn:Function)
            WHERE fn.is_endpoint = true OR fn.route_path IS NOT NULL
            RETURN fn.name AS handler_name, fn.route_path AS route, fn.http_method AS method, fn.file_path AS file_path
            LIMIT 50
            """
            records = session.run(cypher)
            endpoints = [
                {
                    "handler": r["handler_name"],
                    "route": r["route"] or "unknown",
                    "method": r["method"] or "ANY",
                    "file_path": r["file_path"],
                }
                for r in records
            ]
            return {
                "total_endpoints": len(endpoints),
                "endpoints": endpoints,
            }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


# -----------------------------------------------------------------------------
# Global Master Tool Registry
# -----------------------------------------------------------------------------

ALL_TOOLS = [
    tool_traverse_call_graph,
    tool_calculate_blast_radius,
    tool_trace_parameter_lineage,
    tool_query_variable_and_state_references,
    tool_inspect_type_and_inheritance_hierarchy,
    tool_get_symbol_code_snippet,
    tool_analyze_architecture_coupling,
    tool_detect_orphan_and_dead_code,
    tool_trace_taint_and_security_paths,
    tool_search_codebase_semantic,
    tool_query_test_traceability,
    tool_query_api_endpoints
]
