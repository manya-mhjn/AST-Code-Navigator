"""
tools_utils.py — Universal Dynamic Programming Graph Traversal Engine for CodeNavigator.

Provides a unified, O(V + E) linear-time, cycle-immune BFS engine supporting:
- Multi-symbol anchor resolution
- Node label filtering (Source and Target)
- Dynamic relationship / edge filtering (Call graphs, Blast radius, Inheritance, Variables)
- In-memory DP memoization (_dp_memo) and Global Visited-Set tracking.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from dotenv import load_dotenv

from pipeline.neo4j_sink import Neo4jCodeGraphIngestor

load_dotenv(override=True)

ALL_GRAPH_EDGES = [
    "RESOLVED_CALLS",
    "CALLS",
    "IMPORTS",
    "RESOLVED_INHERITS",
    "INHERITS_FROM",
    "INSTANTIATES",
    "USES_ENV",
    "HAS_INSTANCE_ATTRIBUTE",
    "CONTAINS_VARIABLE",
]


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{name}' is not set. "
            f"Set it in .env or via: export {name}=<value>"
        )
    return value


class CallGraphTraversal:
    """
    Universal O(V + E) Dynamic Programming Graph Traversal Engine.
    Handles Call Graphs, Blast Radius, Type Hierarchies, and Variable Lineage.
    """

    def __init__(self, neo4j_sink: Optional[Neo4jCodeGraphIngestor] = None):
        if neo4j_sink:
            self.neo4j_db = neo4j_sink
            self._owns_db = False
        else:
            pooled = None
            try:
                from pipeline.tools import _get_neo4j_session
                pooled = _get_neo4j_session()
            except Exception:
                pass

            if pooled:
                self.neo4j_db = pooled
                self._owns_db = False
            else:
                self.neo4j_db = Neo4jCodeGraphIngestor(
                    uri=_require_env("NEO4J_URI"),
                    auth=(_require_env("NEO4J_USER"), _require_env("NEO4J_PASSWORD")),
                )
                self._owns_db = True

        self._dp_memo: Dict[str, List[Dict[str, Any]]] = {}

    def close(self):
        if self._owns_db and self.neo4j_db:
            self.neo4j_db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def traverse_graph_dp(
        self,
        symbols: Optional[Union[str, List[str]]] = None,
        target_symbol: Optional[str] = None,
        direction: str = "incoming",
        edge_types: Optional[List[str]] = None,
        source_labels: Optional[List[str]] = None,
        target_labels: Optional[List[str]] = None,
        max_depth: int = 4,
        file_path: Optional[str] = None,
        include_raw: bool = True,
        exclude_boilerplate: bool = True,
        limit: int = 50,
    ) -> Dict[str, Any]:
        direction = direction.lower()
        if direction not in ("incoming", "outgoing", "both"):
            raise ValueError(f"Invalid direction '{direction}'. Must be 'incoming', 'outgoing', or 'both'.")

        self._dp_memo.clear()
        max_depth = max(1, min(max_depth, 30))
        raw_syms = symbols or target_symbol or ["unknown"]
        symbols_list = self._normalize_symbols(raw_syms)
        active_edges = edge_types if edge_types is not None else ALL_GRAPH_EDGES

        result_data: Dict[str, Any] = {
            "symbols": symbols_list,
            "direction": direction,
            "edge_types": active_edges,
            "source_labels": source_labels,
            "target_labels": target_labels,
            "max_depth": max_depth,
            "exclude_boilerplate": exclude_boilerplate,
            "total_affected_symbols": 0,
            "total_affected_files": 0,
            "affected_files_summary": {},
            "paths": [],
            "raw_calls": [],
            "detailed_nodes": [],
            "unique_nodes": [],
        }

        with self.neo4j_db.driver.session() as session:
            anchors = self._resolve_anchor_nodes(session, symbols_list, source_labels, file_path)
            if not anchors:
                return result_data

            all_paths: List[Dict[str, Any]] = []
            all_raw: List[Dict[str, Any]] = []
            visited_nodes_map: Dict[str, Dict[str, Any]] = {}
            by_file: Dict[str, List[str]] = {}
            seen_raw: Set[Tuple[Any, Any, Any]] = set()

            directions_to_run = ["incoming", "outgoing"] if direction == "both" else [direction]

            for d in directions_to_run:
                paths, raw, nodes = self._run_bfs_dp_core(
                    session=session,
                    anchors=anchors,
                    direction=d,
                    edge_types=active_edges,
                    target_labels=target_labels,
                    max_depth=max_depth,
                    include_raw=include_raw,
                    exclude_boilerplate=exclude_boilerplate,
                    limit=limit,
                    seen_raw=seen_raw,
                )
                all_paths.extend(paths)
                all_raw.extend(raw)
                visited_nodes_map.update(nodes)

            # Build Inverted File Index
            for node_id, node in visited_nodes_map.items():
                f = node.get("file_path") or "unknown"
                entry = f"{node.get('type', 'Node')} {node.get('name', node_id)} (hop {node.get('distance', 1)})"
                by_file.setdefault(f, []).append(entry)

            result_data["paths"] = all_paths[:limit]
            result_data["raw_calls"] = all_raw[:limit]
            result_data["total_paths"] = len(result_data["paths"])
            result_data["total_affected_symbols"] = len(visited_nodes_map)
            result_data["total_affected_files"] = len(by_file)
            result_data["affected_files_summary"] = by_file
            result_data["detailed_nodes"] = list(visited_nodes_map.values())[:limit]
            result_data["unique_nodes"] = list(visited_nodes_map.values())

        return result_data

    # Backward compatibility alias
    traverse = traverse_graph_dp

    def detect_cycles_dp(
        self,
        source_symbol: Optional[str] = None,
        max_depth: int = 6,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Universal O(V + E) Tarjan's Strongly Connected Components & Transitive Cycle Detection Engine.
        Finds:
        - File-level import cycles (File A -> File B -> File A)
        - Function call cycles / mutual recursion (Function A -> Function B -> Function A)
        - Class instantiation cycles (Class A -> Class B -> Class A)
        - Heterogeneous cross-type cycles (Function A -> Class B -> Class C -> Function A)
        - Arbitrary deep transitive cycles (A -> B -> C -> D -> ... -> A)
        """
        max_depth = max(2, min(max_depth, 25))

        all_cycles = []
        file_cycles = []
        fn_cycles = []
        class_cycles = []
        heterogeneous_cycles = []
        seen_canonical_cycles = set()

        # 1. Fetch active code dependency graph adjacency list
        query = """
            MATCH (src)-[r:RESOLVED_CALLS|IMPORTS|INSTANTIATES|HAS_METHOD|RESOLVED_INHERITS]->(tgt)
            WHERE (src:File OR src:Function OR src:Class)
              AND (tgt:File OR tgt:Function OR tgt:Class)
              AND NOT (src.name STARTS WITH '__' AND src.name ENDS WITH '__')
              AND NOT (tgt.name STARTS WITH '__' AND tgt.name ENDS WITH '__')
            RETURN
                elementId(src) AS src_int_id,
                coalesce(src.id, src.name) AS src_id,
                coalesce(src.name, src.id) AS src_name,
                labels(src)[0] AS src_type,
                coalesce(src.file_path, split(src.id, '::')[0]) AS src_file,
                coalesce(src.start_line, src.line, 0) AS src_line,
                elementId(tgt) AS tgt_int_id,
                coalesce(tgt.id, tgt.name) AS tgt_id,
                coalesce(tgt.name, tgt.id) AS tgt_name,
                labels(tgt)[0] AS tgt_type,
                coalesce(tgt.file_path, split(tgt.id, '::')[0]) AS tgt_file,
                coalesce(tgt.start_line, tgt.line, 0) AS tgt_line,
                type(r) AS rel_type
            LIMIT 25000
        """

        with self.neo4j_db.driver.session() as session:
            records = session.run(query)
            rows = [dict(r) for r in records]

        # 2. Build Adjacency Graph and Node Registry
        nodes: Dict[str, Dict[str, Any]] = {}
        adj: Dict[str, List[str]] = {}

        for r in rows:
            s_id = r["src_id"]
            t_id = r["tgt_id"]

            if s_id not in nodes:
                nodes[s_id] = {
                    "id": s_id,
                    "int_id": r["src_int_id"],
                    "name": r["src_name"],
                    "type": r["src_type"],
                    "file_path": r["src_file"],
                    "line": r["src_line"],
                }
            if t_id not in nodes:
                nodes[t_id] = {
                    "id": t_id,
                    "int_id": r["tgt_int_id"],
                    "name": r["tgt_name"],
                    "type": r["tgt_type"],
                    "file_path": r["tgt_file"],
                    "line": r["tgt_line"],
                }

            adj.setdefault(s_id, []).append(t_id)
            if t_id not in adj:
                adj[t_id] = []

        if not nodes:
            return {
                "source_symbol": source_symbol or "global_audit",
                "total_cycles_detected": 0,
                "file_import_cycles": [],
                "function_call_cycles": [],
                "class_instantiation_cycles": [],
                "heterogeneous_cycles": [],
                "all_cycles": [],
                "summary": "No active dependencies found in code graph.",
            }

        # 3. Tarjan's Strongly Connected Components (SCC) in O(V + E)
        index = 0
        stack: List[str] = []
        indices: Dict[str, int] = {}
        lowlink: Dict[str, int] = {}
        on_stack: Set[str] = set()
        sccs: List[List[str]] = []

        def strongconnect(v: str):
            nonlocal index
            indices[v] = index
            lowlink[v] = index
            index += 1
            stack.append(v)
            on_stack.add(v)

            for w in adj.get(v, []):
                if w not in indices:
                    strongconnect(w)
                    lowlink[v] = min(lowlink[v], lowlink[w])
                elif w in on_stack:
                    lowlink[v] = min(lowlink[v], indices[w])

            if lowlink[v] == indices[v]:
                scc = []
                while True:
                    w = stack.pop()
                    on_stack.remove(w)
                    scc.append(w)
                    if w == v:
                        break
                sccs.append(scc)

        for node_id in nodes:
            if node_id not in indices:
                strongconnect(node_id)

        # 4. Filter Cyclic SCCs (clusters with > 1 node or self-loops)
        cyclic_sccs = [scc for scc in sccs if len(scc) > 1 or (len(scc) == 1 and scc[0] in adj.get(scc[0], []))]

        # TARGETED SCC PRUNING:
        # If source_symbol is provided, filter SCCs before running DFS
        sym_lower = source_symbol.lower() if source_symbol else None
        matching_node_ids: Set[str] = set()
        if sym_lower:
            matching_node_ids = {
                nid for nid, nd in nodes.items()
                if sym_lower in (nd.get("name") or "").lower() or sym_lower in nid.lower()
            }
            if not matching_node_ids:
                return {
                    "source_symbol": source_symbol,
                    "total_cycles_detected": 0,
                    "file_import_cycles": [],
                    "function_call_cycles": [],
                    "class_instantiation_cycles": [],
                    "heterogeneous_cycles": [],
                    "all_cycles": [],
                    "summary": f"Symbol '{source_symbol}' was not found in active cyclic dependencies.",
                }
            target_sccs = [scc for scc in cyclic_sccs if any(nid in matching_node_ids for nid in scc)]
        else:
            target_sccs = cyclic_sccs

        # 5. Extract elementary transitive cycles with Johnson-style symmetry breaking & dead-end pruning
        def search_scc_cycles(scc: List[str], start_nodes: List[str]):
            scc_set = set(scc)
            scc_adj = {u: [v for v in adj.get(u, []) if v in scc_set] for u in scc}
            # Node ordering for symmetry breaking to avoid permutation explosion
            node_order = {nid: idx for idx, nid in enumerate(scc)}

            for start_node in start_nodes:
                if len(all_cycles) >= limit:
                    break

                start_rank = node_order[start_node]
                blocked: Set[str] = set()

                def dfs(curr: str, path: List[str]) -> bool:
                    if len(all_cycles) >= limit:
                        return True
                    found_cycle = False
                    for nxt in scc_adj.get(curr, []):
                        # Cycle completed back to start_node
                        if nxt == start_node and len(path) >= 2:
                            cycle_ids = path + [nxt]
                            min_idx = path.index(min(path))
                            canonical_key = tuple(path[min_idx:] + path[:min_idx])
                            if canonical_key not in seen_canonical_cycles:
                                seen_canonical_cycles.add(canonical_key)
                                cycle_nodes = [nodes[nid] for nid in cycle_ids]
                                types = [n["type"] for n in cycle_nodes[:-1]]
                                unique_types = set(types)
                                cycle_chain_str = " -> ".join([f"{n['type']} {n['name']}" for n in cycle_nodes])

                                cycle_item = {
                                    "cycle_length": len(path),
                                    "cycle_chain": cycle_chain_str,
                                    "nodes": [{
                                        "id": n.get("id"),
                                        "int_id": n.get("int_id"),
                                        "name": n.get("name"),
                                        "type": n.get("type"),
                                        "file_path": n.get("file_path"),
                                        "line": n.get("line"),
                                    } for n in cycle_nodes],
                                    "cycle_type": "file_import" if unique_types == {"File"} else (
                                        "function_call" if unique_types == {"Function"} else (
                                            "class_instantiation" if unique_types == {"Class"} else "heterogeneous"
                                        )
                                    ),
                                }

                                all_cycles.append(cycle_item)
                                if cycle_item["cycle_type"] == "file_import":
                                    file_cycles.append(cycle_item)
                                elif cycle_item["cycle_type"] == "function_call":
                                    fn_cycles.append(cycle_item)
                                elif cycle_item["cycle_type"] == "class_instantiation":
                                    class_cycles.append(cycle_item)
                                else:
                                    heterogeneous_cycles.append(cycle_item)
                            found_cycle = True

                        elif (
                            nxt not in path
                            and nxt not in blocked
                            and node_order.get(nxt, -1) >= start_rank
                            and len(path) < max_depth
                        ):
                            if dfs(nxt, path + [nxt]):
                                found_cycle = True

                    if not found_cycle:
                        blocked.add(curr)
                    return found_cycle

                dfs(start_node, [start_node])

        # Run cycle search across targeted SCCs
        for scc in target_sccs:
            if len(all_cycles) >= limit:
                break
            if matching_node_ids:
                scc_starts = [nid for nid in scc if nid in matching_node_ids]
            else:
                scc_starts = scc
            search_scc_cycles(scc, scc_starts)

        return {
            "source_symbol": source_symbol or "global_audit",
            "total_cycles_detected": len(all_cycles),
            "file_import_cycles": file_cycles,
            "function_call_cycles": fn_cycles,
            "class_instantiation_cycles": class_cycles,
            "heterogeneous_cycles": heterogeneous_cycles,
            "all_cycles": all_cycles[:limit],
            "summary": f"Detected {len(all_cycles)} circular cycle(s) ({len(file_cycles)} file import, {len(fn_cycles)} function recursion, {len(class_cycles)} class instantiation, {len(heterogeneous_cycles)} heterogeneous cross-type loops) up to {max_depth} hops.",
        }

    def detect_dead_entities_dp(
        self,
        entity_type: str = "all",
        scope_path: Optional[str] = None,
        use_dp_reachability: bool = True,
        limit: int = 50,
    ) -> Dict[str, Any]:
        r"""
        Universal Mark-and-Sweep Single-Pass Set Difference Dead Code Engine.
        Computes: Dead Entities = Universe(All Nodes) \ Reachable(From Application Entrypoints).
        Catches isolated dead islands, uninstantiated class clusters, and unused files in O(V + E) linear time.
        """
        entity_type = entity_type.lower()
        results: Dict[str, Any] = {
            "entity_type": entity_type,
            "scope": scope_path or "global",
            "dead_functions": [],
            "dead_classes": [],
            "dead_files": [],
            "dead_env_vars": [],
            "dead_variables": [],
            "total_dead_entities": 0,
        }

        # Dynamic label filter based on entity_type to leverage node label indexes
        if entity_type in ("functions", "function", "methods"):
            label_filter = "n:Function"
        elif entity_type in ("classes", "class"):
            label_filter = "n:Class"
        elif entity_type in ("files", "file", "modules"):
            label_filter = "n:File"
        elif entity_type in ("env_vars", "env", "envs"):
            label_filter = "n:EnvVar"
        elif entity_type in ("variables", "variable", "constants"):
            label_filter = "n:Variable"
        else:
            label_filter = "n:Function OR n:Class OR n:File OR n:EnvVar OR n:Variable"

        query_limit = max(limit * 5, 200)

        with self.neo4j_db.driver.session() as session:
            if use_dp_reachability:
                # Single-pass Mark-and-Sweep Dead Code Query executed entirely in Neo4j
                # Traverses live reachability in 1 database step and computes set difference (U \ R)
                cypher = f"""
                    OPTIONAL MATCH (entry)
                    WHERE (entry:Function OR entry:File)
                      AND (entry.name IN ['main', 'app', 'cli', 'run', 'start', 'serve'] 
                           OR entry.name STARTS WITH 'main_' 
                           OR entry.name STARTS WITH 'cli_' 
                           OR entry.name STARTS WITH 'run_' 
                           OR entry.file_path ENDS WITH 'main.py' 
                           OR entry.file_path ENDS WITH 'app.py' 
                           OR entry.file_path ENDS WITH 'setup.py' 
                           OR entry.file_path ENDS WITH 'manage.py')
                    WITH [e IN collect(entry) WHERE e IS NOT NULL] AS entrypoints
                    CALL {{
                        WITH entrypoints
                        OPTIONAL MATCH (e)
                        WHERE e IN entrypoints
                        OPTIONAL MATCH (e)-[:RESOLVED_CALLS|IMPORTS|INSTANTIATES|HAS_METHOD|RESOLVED_INHERITS|USES_ENV|CONTAINS_VARIABLE*0..15]->(live)
                        RETURN [id IN collect(DISTINCT elementId(live)) WHERE id IS NOT NULL] AS live_ids
                    }}
                    MATCH (n)
                    WHERE ({label_filter})
                      AND NOT elementId(n) IN live_ids
                      AND NOT (n.name STARTS WITH '__' AND n.name ENDS WITH '__')
                      AND NOT n.name STARTS WITH 'test_'
                      AND NOT (n.file_path IS NOT NULL AND n.file_path CONTAINS 'test')
                      AND NOT n.name IN ['main', 'app', 'setup.py', '__init__.py', 'manage.py']
                      AND ($scope IS NULL OR n.file_path CONTAINS $scope OR n.id CONTAINS $scope)
                    RETURN DISTINCT
                        elementId(n) AS elem_id,
                        coalesce(n.id, n.file_path, n.name) AS id,
                        coalesce(n.name, n.file_path, n.id) AS name,
                        coalesce(n.file_path, split(n.id, '::')[0]) AS file_path,
                        labels(n)[0] AS type,
                        coalesce(n.start_line, n.line, 0) AS line,
                        n.default_value AS default_value
                    LIMIT $query_limit
                """
            else:
                # Direct in-degree orphan query (0 incoming dependency edges)
                cypher = f"""
                    MATCH (n)
                    WHERE ({label_filter})
                      AND NOT ()-[:RESOLVED_CALLS|CALLS|IMPORTS|INSTANTIATES|RESOLVED_INHERITS|INHERITS_FROM]->(n)
                      AND NOT (n.name STARTS WITH '__' AND n.name ENDS WITH '__')
                      AND NOT n.name STARTS WITH 'test_'
                      AND NOT (n.file_path IS NOT NULL AND n.file_path CONTAINS 'test')
                      AND NOT n.name IN ['main', 'app', 'setup.py', '__init__.py', 'manage.py']
                      AND ($scope IS NULL OR n.file_path CONTAINS $scope OR n.id CONTAINS $scope)
                    RETURN DISTINCT
                        elementId(n) AS elem_id,
                        coalesce(n.id, n.file_path, n.name) AS id,
                        coalesce(n.name, n.file_path, n.id) AS name,
                        coalesce(n.file_path, split(n.id, '::')[0]) AS file_path,
                        labels(n)[0] AS type,
                        coalesce(n.start_line, n.line, 0) AS line,
                        n.default_value AS default_value
                    LIMIT $query_limit
                """

            records = session.run(cypher, scope=scope_path, query_limit=query_limit)

            for r in records:
                name = r["name"]
                node_type = r["type"]
                file_path = r["file_path"] or "unknown"
                line = r["line"]

                if node_type == "Function" and entity_type in ("all", "functions", "function", "methods"):
                    results["dead_functions"].append({
                        "name": name,
                        "file_path": file_path,
                        "line": line,
                        "reason": "Unreachable from application entrypoints (Dead Code / Island)",
                    })
                elif node_type == "Class" and entity_type in ("all", "classes", "class"):
                    results["dead_classes"].append({
                        "name": name,
                        "file_path": file_path,
                        "line": line,
                        "reason": "0 active instantiations or inheritance links from live code",
                    })
                elif node_type == "File" and entity_type in ("all", "files", "file", "modules"):
                    results["dead_files"].append({
                        "name": name,
                        "file_path": file_path,
                        "reason": "0 incoming imports from application entrypoints (Orphan File)",
                    })
                elif node_type == "EnvVar" and entity_type in ("all", "env_vars", "env", "envs"):
                    results["dead_env_vars"].append({
                        "name": name,
                        "default_value": r["default_value"],
                        "reason": "Unreferenced environment variable in live execution paths",
                    })
                elif node_type == "Variable" and entity_type in ("all", "variables", "variable", "constants"):
                    results["dead_variables"].append({
                        "name": name,
                        "file_path": file_path,
                        "line": line,
                        "reason": "Unreferenced module-level variable / constant",
                    })

            # Trim to limit per category
            results["dead_functions"] = results["dead_functions"][:limit]
            results["dead_classes"] = results["dead_classes"][:limit]
            results["dead_files"] = results["dead_files"][:limit]
            results["dead_env_vars"] = results["dead_env_vars"][:limit]
            results["dead_variables"] = results["dead_variables"][:limit]

        total_dead = (
            len(results["dead_functions"])
            + len(results["dead_classes"])
            + len(results["dead_files"])
            + len(results["dead_env_vars"])
            + len(results["dead_variables"])
        )
        results["total_dead_entities"] = total_dead
        results["summary"] = (
            f"Detected {total_dead} dead/unused entity(ies) across scope '{results['scope']}': "
            f"{len(results['dead_functions'])} functions, {len(results['dead_classes'])} classes, "
            f"{len(results['dead_files'])} files, {len(results['dead_env_vars'])} env vars, "
            f"{len(results['dead_variables'])} variables."
        )
        return results

    def _run_bfs_dp_core(
        self,
        session,
        anchors: List[Dict[str, Any]],
        direction: str,
        edge_types: List[str],
        target_labels: Optional[List[str]],
        max_depth: int,
        include_raw: bool,
        exclude_boilerplate: bool,
        limit: int,
        seen_raw: Optional[Set[Tuple[Any, Any, Any]]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        discovered_paths: List[Dict[str, Any]] = []
        discovered_raw: List[Dict[str, Any]] = []
        visited_nodes: Dict[str, Dict[str, Any]] = {}
        global_visited_int_ids: Set[Any] = set()
        if seen_raw is None:
            seen_raw = set()

        for anchor in anchors:
            anchor_int_id = anchor.get("int_id")
            anchor_id = anchor["id"]
            if anchor_int_id is not None:
                global_visited_int_ids.add(anchor_int_id)
            visited_nodes[anchor_id] = {**anchor, "distance": 0}

        # Level-by-level batched frontier queue
        current_frontier: List[Tuple[Dict[str, Any], List[Dict[str, Any]], int]] = [
            (anchor, [anchor], 0) for anchor in anchors
        ]

        # Early Depth Pruning: terminate frontier expansion if limit is reached
        while current_frontier and len(discovered_paths) < limit and len(visited_nodes) < limit * 2:
            next_frontier: List[Tuple[Dict[str, Any], List[Dict[str, Any]], int]] = []
            unmemoized_nodes: List[Dict[str, Any]] = []
            edge_key = "-".join(sorted(edge_types))
            label_key = "-".join(sorted(target_labels)) if target_labels else "all"

            # 1. Identify which nodes in the current frontier need database fetching
            for curr_node, _, depth in current_frontier:
                if depth >= max_depth:
                    continue
                curr_id = curr_node["id"]
                memo_key = f"{curr_id}:{direction}:{edge_key}:{label_key}:{exclude_boilerplate}"
                if memo_key not in self._dp_memo:
                    unmemoized_nodes.append(curr_node)

            # 2. Fetch all unmemoized 1-hop neighbors in a SINGLE batched UNWIND Cypher query
            if unmemoized_nodes:
                batched_results = self._fetch_batched_1hop_neighbors(
                    session=session,
                    nodes=unmemoized_nodes,
                    direction=direction,
                    edge_types=edge_types,
                    target_labels=target_labels,
                    exclude_boilerplate=exclude_boilerplate,
                )
                for un_node in unmemoized_nodes:
                    u_id = un_node["id"]
                    memo_key = f"{u_id}:{direction}:{edge_key}:{label_key}:{exclude_boilerplate}"
                    self._dp_memo[memo_key] = batched_results.get(u_id, [])

            # 3. Expand the frontier using cached neighbors
            for curr_node, chain, depth in current_frontier:
                if depth >= max_depth:
                    continue
                if len(discovered_paths) >= limit:
                    break

                curr_id = curr_node["id"]
                memo_key = f"{curr_id}:{direction}:{edge_key}:{label_key}:{exclude_boilerplate}"
                neighbors = self._dp_memo.get(memo_key, [])

                for nbr in neighbors:
                    edge_type = nbr.get("edge_type", "RESOLVED_CALLS")
                    nbr_type = nbr.get("type", "Node")
                    nbr_id = nbr["id"]
                    nbr_name = nbr.get("name", nbr_id)
                    nbr_int_id = nbr.get("int_id")

                    if nbr_type in ("Target", "RawVariable", "RawInstanceAttribute"):
                        if include_raw:
                            caller_id = nbr_id if direction == "incoming" else curr_id
                            line = nbr.get("line")
                            target_name = curr_node.get("name", str(curr_id)) if direction == "incoming" else nbr_name
                            raw_key = (caller_id, line, target_name)
                            if raw_key not in seen_raw:
                                seen_raw.add(raw_key)
                                discovered_raw.append({
                                    "type": f"raw_{'caller' if direction == 'incoming' else 'callee'}",
                                    "source_id": curr_id,
                                    "source_name": curr_node.get("name", str(curr_id)),
                                    "caller_id": caller_id,
                                    "caller_name": nbr_name if direction == "incoming" else curr_node.get("name", str(curr_id)),
                                    "line": line,
                                    "target_name": target_name,
                                    "file_path": nbr.get("file_path", ""),
                                    "distance": depth + 1,
                                })
                        continue

                    if include_raw and edge_type == "CALLS":
                        caller_id = nbr_id if direction == "incoming" else curr_id
                        line = nbr.get("line")
                        target_name = curr_node.get("name", str(curr_id)) if direction == "incoming" else nbr_name
                        raw_key = (caller_id, line, target_name)
                        if raw_key not in seen_raw:
                            seen_raw.add(raw_key)
                            discovered_raw.append({
                                "type": f"raw_{'caller' if direction == 'incoming' else 'callee'}",
                                "source_id": curr_id,
                                "source_name": curr_node.get("name", str(curr_id)),
                                "caller_id": caller_id,
                                "caller_name": nbr_name if direction == "incoming" else curr_node.get("name", str(curr_id)),
                                "line": line,
                                "target_name": target_name,
                                "file_path": nbr.get("file_path", ""),
                                "distance": depth + 1,
                            })

                    if direction == "incoming":
                        new_chain = [nbr] + chain
                    else:
                        new_chain = chain + [nbr]

                    exec_chain = " -> ".join([n.get("name", str(n.get("id", ""))) for n in new_chain])

                    discovered_paths.append({
                        "type": direction,
                        "depth": depth + 1,
                        "execution_chain": exec_chain,
                        "nodes": new_chain,
                        "edges": [edge_type] * (depth + 1),
                    })

                    # Fast integer-based membership test in O(1)
                    is_visited = (nbr_int_id in global_visited_int_ids) if nbr_int_id is not None else (nbr_id in visited_nodes)
                    if not is_visited:
                        if nbr_int_id is not None:
                            global_visited_int_ids.add(nbr_int_id)
                        visited_nodes[nbr_id] = {
                            "id": nbr_id,
                            "int_id": nbr_int_id,
                            "name": nbr_name,
                            "type": nbr_type,
                            "file_path": nbr.get("file_path"),
                            "line": nbr.get("line"),
                            "distance": depth + 1,
                        }
                        next_frontier.append((nbr, new_chain, depth + 1))

            current_frontier = next_frontier

        return discovered_paths, discovered_raw, visited_nodes

    def _fetch_batched_1hop_neighbors(
        self,
        session,
        nodes: List[Dict[str, Any]],
        direction: str,
        edge_types: List[str],
        target_labels: Optional[List[str]],
        exclude_boilerplate: bool = True,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Batched 1-hop neighbor retrieval for an entire frontier of nodes in 1 single Cypher query.
        Returns a mapping: {frontier_node_id: [neighbor_1, neighbor_2, ...]}
        """
        if not nodes:
            return {}

        rel_pattern = "|".join(sorted(edge_types))
        boilerplate_clause = ""
        if exclude_boilerplate:
            boilerplate_clause = """
              AND NOT (neighbor.name STARTS WITH '__' AND neighbor.name ENDS WITH '__')
              AND NOT neighbor.name IN ['print', 'len', 'range', 'isinstance', 'str', 'int', 'dict', 'list', 'set', 'repr', 'super', 'type', 'getattr', 'setattr', 'hasattr']
            """

        frontier_items = []
        for n in nodes:
            frontier_items.append({
                "int_id": n.get("int_id"),
                "id": n.get("id"),
                "name": n.get("name") or str(n.get("id", "")).split("::")[-1].split(".")[-1],
            })

        # When internal element IDs are known (O(1) direct pointer lookup in Neo4j), avoid any OR branch.
        # Fall back to exact indexed ID equality only if int_id is absent. Never perform unindexed suffix scans during traversal.
        if all(item.get("int_id") is not None for item in frontier_items):
            curr_match = "elementId(curr) = item.int_id"
        else:
            curr_match = "((item.int_id IS NOT NULL AND elementId(curr) = item.int_id) OR (item.int_id IS NULL AND curr.id = item.id))"

        # Cypher UNWIND query matching all frontier nodes in a single database roundtrip
        if direction == "incoming":
            cypher = f"""
                UNWIND $frontier_items AS item
                MATCH (neighbor)-[r:{rel_pattern}]->(curr)
                WHERE ({curr_match})
                  AND ($target_labels IS NULL OR labels(neighbor)[0] IN $target_labels)
                  {boilerplate_clause}
                RETURN
                    item.id AS frontier_id,
                    elementId(neighbor) AS int_id,
                    coalesce(neighbor.id, neighbor.name) AS id,
                    coalesce(neighbor.name, neighbor.id) AS name,
                    coalesce(neighbor.file_path, split(neighbor.id, '::')[0]) AS file_path,
                    labels(neighbor)[0] AS type,
                    type(r) AS edge_type,
                    coalesce(neighbor.start_line, r.line, neighbor.line) AS line
            """
        else:
            cypher = f"""
                UNWIND $frontier_items AS item
                MATCH (curr)-[r:{rel_pattern}]->(neighbor)
                WHERE ({curr_match})
                  AND ($target_labels IS NULL OR labels(neighbor)[0] IN $target_labels)
                  {boilerplate_clause}
                RETURN
                    item.id AS frontier_id,
                    elementId(neighbor) AS int_id,
                    coalesce(neighbor.id, neighbor.name) AS id,
                    coalesce(neighbor.name, neighbor.id) AS name,
                    coalesce(neighbor.file_path, split(neighbor.id, '::')[0]) AS file_path,
                    labels(neighbor)[0] AS type,
                    type(r) AS edge_type,
                    coalesce(neighbor.start_line, r.line, neighbor.line) AS line
            """

        records = session.run(
            cypher,
            frontier_items=frontier_items,
            target_labels=target_labels,
        )

        grouped: Dict[str, List[Dict[str, Any]]] = {n["id"]: [] for n in nodes}
        for r in records:
            f_id = r["frontier_id"]
            nbr_data = {
                "int_id": r["int_id"],
                "id": r["id"],
                "name": r["name"],
                "file_path": r["file_path"],
                "type": r["type"],
                "edge_type": r["edge_type"],
                "line": r["line"],
            }
            if f_id in grouped:
                grouped[f_id].append(nbr_data)
            else:
                grouped.setdefault(str(f_id), []).append(nbr_data)

        return grouped

    def _resolve_anchor_nodes(
        self,
        session,
        symbols: List[str],
        source_labels: Optional[List[str]],
        file_path: Optional[str],
    ) -> List[Dict[str, Any]]:
        cypher = """
            UNWIND $symbols AS sym
            MATCH (n)
            WHERE (n.name = sym 
               OR n.id = sym 
               OR n.id ENDS WITH ('.' + sym) 
               OR n.id ENDS WITH ('::' + sym)
               OR n.id ENDS WITH ('::inst_attr::' + sym))
              AND ($source_labels IS NULL OR labels(n)[0] IN $source_labels)
              AND ($file_path IS NULL OR n.file_path = $file_path OR n.id STARTS WITH $file_path)
            RETURN DISTINCT
                elementId(n) AS int_id,
                coalesce(n.id, n.name) AS id,
                coalesce(n.name, n.id) AS name,
                coalesce(n.file_path, split(n.id, '::')[0]) AS file_path,
                labels(n)[0] AS type,
                coalesce(n.start_line, n.line) AS line
            LIMIT 20
        """
        records = session.run(
            cypher,
            symbols=symbols,
            source_labels=source_labels,
            file_path=file_path,
        )
        return [dict(r) for r in records]

    @staticmethod
    def _normalize_symbols(symbols: Union[str, List[str]]) -> List[str]:
        result: List[str] = []
        if isinstance(symbols, list):
            for s in symbols:
                if isinstance(s, str) and s.strip():
                    result.append(s.strip(" ,'\""))
        elif isinstance(symbols, str) and symbols.strip():
            result.extend([s.strip(" ,'\"") for s in symbols.replace(",", " ").split() if s.strip()])
        return list(dict.fromkeys(result)) if result else ["unknown"]
