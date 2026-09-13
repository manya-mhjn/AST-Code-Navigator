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

import atexit
import threading
from dotenv import load_dotenv

load_dotenv(override=True)

from langchain_core.tools import tool

from pipeline.tools_utils import CallGraphTraversal
from pipeline.neo4j_sink import Neo4jCodeGraphIngestor
from pipeline.weaviate_sink import WeaviateCloudCodeDB

# -----------------------------------------------------------------------------
# Thread-Safe Persistent Connection Pooling (Singleton Pattern)
# -----------------------------------------------------------------------------
_NEO4J_LOCK = threading.Lock()
_WEAVIATE_LOCK = threading.Lock()
_NEO4J_SINGLETON: Optional[Neo4jCodeGraphIngestor] = None
_WEAVIATE_SINGLETON: Optional[WeaviateCloudCodeDB] = None


class _PooledNeo4jClient:
    """Wrapper around singleton Neo4j driver that prevents per-tool closing of the underlying connection pool."""

    def __init__(self, ingestor: Neo4jCodeGraphIngestor):
        self._ingestor = ingestor

    @property
    def driver(self):
        return self._ingestor.driver

    def close(self):
        # No-op: keep the underlying driver alive across tool calls during the session
        pass

    def __getattr__(self, name: str) -> Any:
        return getattr(self._ingestor, name)


class _PooledWeaviateClient:
    """Wrapper around singleton Weaviate client that prevents per-tool closing of the vector client."""

    def __init__(self, client: WeaviateCloudCodeDB):
        self._client = client

    def close(self):
        # No-op: keep the underlying Weaviate client alive across tool calls during the session
        pass

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def _get_neo4j_session() -> Optional[_PooledNeo4jClient]:
    """Returns a thread-safe singleton Neo4j driver wrapped for connection pool reuse."""
    global _NEO4J_SINGLETON
    if _NEO4J_SINGLETON is not None:
        return _PooledNeo4jClient(_NEO4J_SINGLETON)

    with _NEO4J_LOCK:
        if _NEO4J_SINGLETON is not None:
            return _PooledNeo4jClient(_NEO4J_SINGLETON)
        uri = os.environ.get("NEO4J_URI")
        user = os.environ.get("NEO4J_USER")
        password = os.environ.get("NEO4J_PASSWORD")
        if not (uri and user and password):
            return None
        try:
            _NEO4J_SINGLETON = Neo4jCodeGraphIngestor(uri=uri, auth=(user, password))
            return _PooledNeo4jClient(_NEO4J_SINGLETON)
        except Exception as e:
            print(f"[Warning] Could not connect to Neo4j: {e}")
            return None


def _get_weaviate_client() -> Optional[_PooledWeaviateClient]:
    """Returns a thread-safe singleton Weaviate client wrapped for connection pool reuse."""
    global _WEAVIATE_SINGLETON
    if _WEAVIATE_SINGLETON is not None:
        return _PooledWeaviateClient(_WEAVIATE_SINGLETON)

    with _WEAVIATE_LOCK:
        if _WEAVIATE_SINGLETON is not None:
            return _PooledWeaviateClient(_WEAVIATE_SINGLETON)
        url = os.environ.get("WEAVIATE_CLUSTER_URL") or os.environ.get("WEAVIATE_URL")
        api_key = os.environ.get("WEAVIATE_API_KEY")
        if not (url and api_key):
            return None
        try:
            _WEAVIATE_SINGLETON = WeaviateCloudCodeDB(cluster_url=url, api_key=api_key)
            return _PooledWeaviateClient(_WEAVIATE_SINGLETON)
        except Exception as e:
            print(f"[Warning] Could not connect to Weaviate: {e}")
            return None


def _cleanup_singletons():
    """Closes underlying drivers when process exits."""
    global _NEO4J_SINGLETON, _WEAVIATE_SINGLETON
    if _NEO4J_SINGLETON:
        try:
            _NEO4J_SINGLETON.close()
        except Exception:
            pass
        _NEO4J_SINGLETON = None
    if _WEAVIATE_SINGLETON:
        try:
            _WEAVIATE_SINGLETON.close()
        except Exception:
            pass
        _WEAVIATE_SINGLETON = None


atexit.register(_cleanup_singletons)

# -----------------------------------------------------------------------------
# LangChain Tools (The 20-Task Suite)
# -----------------------------------------------------------------------------


@tool
def tool_traverse_call_graph(
    target_symbol: str,
    direction: str = "incoming",
    max_depth: int = 30,
    file_path: Optional[str] = None,
    include_raw: bool = True,
    exclude_boilerplate: bool = True,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    [Task #1, #2] Traverses the call graph in Neo4j up to max_depth hops.
    Use direction='incoming' for upstream callers and direction='outgoing' for downstream callees.
    Pre-filters boilerplate dunder methods and standard library calls in Cypher when exclude_boilerplate=True.
    """
    with CallGraphTraversal() as engine:
        return engine.traverse(
            target_symbol=target_symbol,
            direction=direction,
            max_depth=max_depth,
            file_path=file_path,
            include_raw=include_raw,
            exclude_boilerplate=exclude_boilerplate,
            limit=limit,
        )


@tool
def tool_calculate_blast_radius(
    changed_symbols: Optional[Union[List[str], str]] = None,
    target_symbol: Optional[str] = None,
    max_depth: int = 30,
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
    max_depth: int = 30,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    [Task #4] Traces argument values and lineage for a specific function parameter across callers up to max_depth hops using DP.
    Performs database-level filtered edge expansion for parameter bindings and incoming call chains.
    """
    func_clean = function_name.split(".")[-1] if "." in function_name else function_name
    param_found = False
    direct_bindings = []

    # 1. Database-level Parameter verification and binding extraction
    db = _get_neo4j_session()
    if db:
        try:
            with db.driver.session() as session:
                # A. Verify parameter definition on function
                param_check = session.run("""
                    MATCH (fn:Function)-[:HAS_PARAMETER]->(p:Parameter)
                    WHERE (fn.name = $func OR fn.name = $func_clean OR fn.id ENDS WITH ('.' + $func_clean) OR fn.id ENDS WITH ('::' + $func_clean))
                      AND (p.name = $param OR p.name = $param_clean)
                    RETURN fn.name AS fn_name, p.name AS param_name, p.default_value AS default_val
                    LIMIT 1
                """, func=function_name, func_clean=func_clean, param=parameter_name, param_clean=parameter_name.strip("$"))
                r = param_check.single()
                if r:
                    param_found = True

                # B. Query callers with parameter-filtered edge expansion directly in Cypher
                caller_records = session.run("""
                    MATCH (caller:Function)-[r:RESOLVED_CALLS|CALLS]->(fn:Function)
                    WHERE (fn.name = $func OR fn.name = $func_clean OR fn.id ENDS WITH ('.' + $func_clean) OR fn.id ENDS WITH ('::' + $func_clean))
                      AND ($param IS NULL OR r.arg_name = $param OR r.arguments CONTAINS $param OR r.arg_name IS NULL)
                    RETURN DISTINCT
                        elementId(caller) AS caller_id,
                        coalesce(caller.name, caller.id) AS caller_name,
                        caller.file_path AS file_path,
                        coalesce(r.line, caller.start_line, 0) AS line,
                        r.arg_name AS bound_arg,
                        r.arg_value AS arg_value
                    ORDER BY line ASC
                    LIMIT $limit
                """, func=function_name, func_clean=func_clean, param=parameter_name, limit=limit)
                for rec in caller_records:
                    direct_bindings.append({
                        "caller": rec["caller_name"],
                        "file": rec["file_path"],
                        "line": rec["line"],
                        "bound_argument": rec["bound_arg"] or "positional/inferred",
                        "argument_value": rec["arg_value"],
                    })
        except Exception as e:
            print(f"[Warning] Parameter lineage Cypher check: {e}")

    # 2. Multi-hop Transitive Lineage Call Tree via DP
    with CallGraphTraversal() as engine:
        res = engine.traverse_graph_dp(
            symbols=function_name,
            direction="incoming",
            edge_types=["RESOLVED_CALLS", "CALLS"],
            source_labels=["Function"],
            max_depth=max_depth,
            limit=limit,
        )

    return {
        "function_name": function_name,
        "parameter_name": parameter_name,
        "parameter_exists_in_ast": param_found,
        "max_depth": max_depth,
        "direct_bound_callers": direct_bindings,
        "total_direct_callers": len(direct_bindings),
        "execution_paths": res.get("paths", [])[:limit],
        "lineage_summary": (
            f"Parameter '{parameter_name}' on function '{function_name}' has {len(direct_bindings)} direct caller binding(s) "
            f"and {len(res.get('paths', []))} multi-hop execution chain(s) up to depth {max_depth}."
        ),
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
    symbol_name: Optional[str] = None,
    class_symbol: Optional[str] = None,
    direction: str = "both",
    max_depth: int = 30,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    [Tasks #6, #17] Inspects class inheritance and type hierarchies across any depth using DP traversal.
    Traverses :RESOLVED_INHERITS and :INHERITS_FROM (superclasses and subclasses) and retrieves :HAS_METHOD links.
    """
    target_sym = class_symbol or symbol_name
    if not target_sym:
        return {"error": "Missing required argument 'symbol_name' or 'class_symbol'"}

    # Strip module prefixes if necessary
    target_clean = target_sym.split(".")[-1]

    try:
        with CallGraphTraversal() as engine:
            parents = []
            children = []
            inheritance_paths = []

            # 1. Superclasses (Ancestors / Outgoing inheritance edges)
            if direction in ("both", "superclasses", "parents", "outgoing", "ancestors"):
                res_parents = engine.traverse_graph_dp(
                    symbols=target_clean,
                    direction="outgoing",
                    edge_types=["RESOLVED_INHERITS", "INHERITS_FROM"],
                    source_labels=["Class"],
                    target_labels=["Class"],
                    max_depth=max_depth,
                    limit=limit,
                )
                seen_parents = set()
                for n in res_parents.get("detailed_nodes", []):
                    if n.get("name") != target_clean and n.get("distance", 0) > 0:
                        p_key = (n.get("name"), n.get("file_path"))
                        if p_key not in seen_parents:
                            seen_parents.add(p_key)
                            parents.append({
                                "name": n.get("name"),
                                "file": n.get("file_path"),
                                "distance": n.get("distance", 1),
                                "line": n.get("line"),
                            })
                inheritance_paths.extend(res_parents.get("paths", []))

            # 2. Subclasses (Descendants / Incoming inheritance edges)
            if direction in ("both", "subclasses", "children", "incoming", "descendants"):
                res_children = engine.traverse_graph_dp(
                    symbols=target_clean,
                    direction="incoming",
                    edge_types=["RESOLVED_INHERITS", "INHERITS_FROM"],
                    source_labels=["Class"],
                    target_labels=["Class"],
                    max_depth=max_depth,
                    limit=limit,
                )
                seen_children = set()
                for n in res_children.get("detailed_nodes", []):
                    if n.get("name") != target_clean and n.get("distance", 0) > 0:
                        c_key = (n.get("name"), n.get("file_path"))
                        if c_key not in seen_children:
                            seen_children.add(c_key)
                            children.append({
                                "name": n.get("name"),
                                "file": n.get("file_path"),
                                "distance": n.get("distance", 1),
                                "line": n.get("line"),
                            })
                inheritance_paths.extend(res_children.get("paths", []))

            # 3. Direct Methods (:HAS_METHOD)
            methods = []
            with engine.neo4j_db.driver.session() as session:
                method_records = session.run("""
                    MATCH (cls:Class)-[:HAS_METHOD]->(fn:Function)
                    WHERE cls.name = $cls OR cls.name = $sym_clean 
                       OR cls.id ENDS WITH ('.' + $sym_clean) 
                       OR cls.id ENDS WITH ('::' + $sym_clean)
                    RETURN fn.name AS method, fn.file_path AS file_path, coalesce(fn.start_line, fn.line, 0) AS line
                    ORDER BY line ASC
                """, cls=target_sym, sym_clean=target_clean)
                for r in method_records:
                    methods.append({
                        "method": r["method"],
                        "file": r["file_path"],
                        "line": r["line"],
                    })

            # Deduplicate paths
            dedup_paths = []
            seen_chains = set()
            for p in inheritance_paths:
                chain = p.get("execution_chain")
                if chain and chain not in seen_chains:
                    seen_chains.add(chain)
                    dedup_paths.append(p)

            return {
                "class": target_sym,
                "direction": direction,
                "max_depth": max_depth,
                "superclasses": parents,
                "subclasses": children,
                "methods": methods,
                "inheritance_paths": dedup_paths[:limit],
                "total_ancestors": len(parents),
                "total_descendants": len(children),
                "total_methods": len(methods),
                "summary": f"Class '{target_sym}' has {len(parents)} superclass(es), {len(children)} subclass(es), and {len(methods)} direct method(s) resolved across full transitive inheritance depth.",
            }
    except Exception as e:
        return {"error": str(e), "class_symbol": target_sym}


@tool
def tool_get_symbol_code_snippet(
    symbol_name: str,
    file_path: Optional[str] = None,
    max_lines: int = 80,
) -> Dict[str, Any]:
    """
    [Tasks #8, #10, #15, #18] Fetches code snippet and metadata for a function, class, or method.
    Checks Neo4j Knowledge Graph first for AST coordinates/metadata, then retrieves code chunk directly from Weaviate Vector DB.
    """
    sym_clean = symbol_name.split(".")[-1] if "." in symbol_name else symbol_name
    node_metadata = None

    # 1. FIRST: Check Neo4j Knowledge Graph for symbol definition & metadata
    db = _get_neo4j_session()
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
                    AND ($file_path IS NULL OR n.file_path = $file_path OR n.id STARTS WITH $file_path)
                    RETURN n.id AS node_id,
                        coalesce(n.name, $sym_clean) AS name,
                        coalesce(n.file_path, split(n.id, '::')[0]) AS file_path, 
                        labels(n)[0] AS type,
                        n.signature AS signature,
                        coalesce(n.start_line, n.line) AS line_start, 
                        n.end_line AS line_end
                    ORDER BY 
                        CASE 
                            WHEN n.name = $sym THEN 1                        
                            WHEN n.name = $sym_clean THEN 2                   
                            WHEN n.id ENDS WITH ('::' + $sym_clean) THEN 3    
                            ELSE 4                                           
                        END ASC
                    LIMIT 1
                """, sym=symbol_name, sym_clean=sym_clean)
                r = records.single()
                if r:
                    node_metadata = dict(r)
        except Exception as e:
            print(f"[Warning] Neo4j snippet metadata lookup: {e}")
        finally:
            db.close()

    # 2. THEN: Fetch Code Chunk from Weaviate Vector DB
    wv = _get_weaviate_client()
    if wv:
        try:
            # Query Weaviate using node_id or exact symbol name
            search_query = node_metadata["node_id"] if (node_metadata and node_metadata.get("node_id")) else symbol_name
            results = wv.search_code(search_query, limit=3)
            if not results and node_metadata and node_metadata.get("name"):
                results = wv.search_code(node_metadata["name"], limit=3)
            if not results:
                results = wv.search_code(sym_clean, limit=3)

            best_chunk = None
            if results:
                for r in results:
                    if r.get("name") in (symbol_name, sym_clean) or (node_metadata and r.get("node_id") == node_metadata.get("node_id")):
                        best_chunk = r
                        break
                if not best_chunk:
                    best_chunk = results[0]

            if best_chunk and best_chunk.get("content"):
                return {
                    "symbol": symbol_name,
                    "file_path": best_chunk.get("file_path") or (node_metadata.get("file_path") if node_metadata else None),
                    "line_start": node_metadata.get("line_start") if node_metadata else None,
                    "line_end": node_metadata.get("line_end") if node_metadata else None,
                    "signature": node_metadata.get("signature") if node_metadata else None,
                    "type": node_metadata.get("type") if node_metadata else best_chunk.get("chunk_type"),
                    "code": best_chunk.get("content"),
                    "docstring": best_chunk.get("docstring") or (node_metadata.get("docstring") if node_metadata else None),
                    "source": "neo4j_and_weaviate",
                }
        except Exception as e:
            print(f"[Warning] Weaviate code lookup error: {e}")
        finally:
            wv.close()

    # 3. If chunk not in Weaviate, return Neo4j structured metadata definition
    if node_metadata:
        return {
            "symbol": symbol_name,
            "file_path": node_metadata.get("file_path"),
            "line_start": node_metadata.get("line_start"),
            "line_end": node_metadata.get("line_end"),
            "signature": node_metadata.get("signature"),
            "type": node_metadata.get("type"),
            "docstring": node_metadata.get("docstring"),
            "code": f"# Definition in Neo4j Graph:\n# Symbol: {node_metadata.get('name')}\n# Signature: {node_metadata.get('signature', 'N/A')}\n# File: {node_metadata.get('file_path')}\n# Lines: L{node_metadata.get('line_start')}-L{node_metadata.get('line_end')}",
            "source": "neo4j_graph",
        }

    return {"symbol": symbol_name, "error": "Symbol definition not found in Neo4j Knowledge Graph or Weaviate Vector Store."}


@tool
def tool_analyze_architecture_coupling(
    symbol_name: Optional[str] = None,
    source_module: Optional[str] = None,
    max_depth: int = 6,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    [Task #12] Analyzes module coupling and detects all forms of circular dependencies using Dynamic Programming (DP).
    Detects:
    1. File import cycles (File A <-> File B)
    2. Function call cycles (Function A -> Function B -> Function A)
    3. Class instantiation cycles (Class A -> Class B -> Class A)
    4. Heterogeneous cross-type cycles (Function A -> Class B -> Class C -> Function A)
    """
    target = source_module or symbol_name

    try:
        with CallGraphTraversal() as engine:
            res = engine.detect_cycles_dp(
                source_symbol=target,
                max_depth=max_depth,
                limit=limit,
            )

            # Also sample direct file-to-file import edges for architecture metrics
            with engine.neo4j_db.driver.session() as session:
                imports_records = session.run("""
                    MATCH (f1:File)-[:IMPORTS]->(f2:File)
                    RETURN coalesce(f1.file_path, f1.name) AS from_file, coalesce(f2.file_path, f2.name) AS to_file
                    LIMIT 50
                """)
                imports_list = [{"from": r["from_file"], "to": r["to_file"]} for r in imports_records]

            res["total_import_edges"] = len(imports_list)
            res["dependencies_sample"] = imports_list[:25]
            res["circular_dependencies"] = [c["cycle_chain"] for c in res.get("all_cycles", [])]
            return res
    except Exception as e:
        return {"error": str(e), "source_symbol": target}


@tool
def tool_detect_orphan_and_dead_code(
    entity_type: str = "all",
    scope_path: Optional[str] = None,
    use_dp_reachability: bool = True,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    [Task #13] Detects dead code and unreferenced entities across the entire codebase using DP forward reachability and graph in-degree analysis.
    Supports entity_type: 'all', 'functions', 'classes', 'files', 'env_vars', 'variables'.
    """
    try:
        with CallGraphTraversal() as engine:
            res = engine.detect_dead_entities_dp(
                entity_type=entity_type,
                scope_path=scope_path,
                use_dp_reachability=use_dp_reachability,
                limit=limit,
            )
            # Add backwards compatible aliases
            res["orphans"] = res.get("dead_functions", [])
            res["total_orphan_functions_found"] = len(res.get("dead_functions", []))
            return res
    except Exception as e:
        return {"error": str(e), "scope": scope_path}


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
