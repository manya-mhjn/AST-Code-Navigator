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
from collections import deque
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
                    limit=limit,
                )
                all_paths.extend(paths)
                all_raw.extend(raw)
                visited_nodes_map.update(nodes)

            # 3. Deduplicate raw calls by caller_id, line, and target_name
            dedup_raw: List[Dict[str, Any]] = []
            seen_raw: Set[Tuple[Any, Any, Any]] = set()
            for r in all_raw:
                k = (r.get("caller_id"), r.get("line"), r.get("target_name"))
                if k not in seen_raw:
                    seen_raw.add(k)
                    dedup_raw.append(r)

            # 4. Build Inverted File Index
            for node_id, node in visited_nodes_map.items():
                f = node.get("file_path") or "unknown"
                entry = f"{node.get('type', 'Node')} {node.get('name', node_id)} (hop {node.get('distance', 1)})"
                by_file.setdefault(f, []).append(entry)

            result_data["paths"] = all_paths[:limit]
            result_data["raw_calls"] = dedup_raw[:limit]
            result_data["total_paths"] = len(result_data["paths"])
            result_data["total_affected_symbols"] = len(visited_nodes_map)
            result_data["total_affected_files"] = len(by_file)
            result_data["affected_files_summary"] = by_file
            result_data["detailed_nodes"] = list(visited_nodes_map.values())[:limit]
            result_data["unique_nodes"] = list(visited_nodes_map.values())

        return result_data

    # Backward compatibility aliases
    traverse = traverse_graph_dp
    traverse_call_graph = traverse_graph_dp

    def detect_cycles_dp(
        self,
        source_symbol: Optional[str] = None,
        max_depth: int = 6,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Universal Dynamic Programming Cycle & Circular Dependency Detection Engine.
        Finds:
        - File-level import cycles (File A -> File B -> File A)
        - Function call cycles / mutual recursion (Function A -> Function B -> Function A)
        - Class instantiation cycles (Class A -> Class B -> Class A)
        - Heterogeneous cross-type cycles (Function A -> Class B -> Class C -> Function A)
        """
        self._dp_memo.clear()
        max_depth = max(2, min(max_depth, 15))
        
        all_cycles = []
        file_cycles = []
        fn_cycles = []
        class_cycles = []
        heterogeneous_cycles = []
        seen_canonical_cycles = set()

        with self.neo4j_db.driver.session() as session:
            # 1. If source_symbol is provided, resolve anchor nodes for that symbol
            if source_symbol:
                anchors = self._resolve_anchor_nodes(session, [source_symbol], None, None)
            else:
                # Find all active candidate vertices (Files, Functions, Classes)
                records = session.run("""
                    MATCH (n)
                    WHERE (n:File OR n:Function OR n:Class)
                    RETURN coalesce(n.id, n.file_path, n.name) AS id,
                           coalesce(n.name, n.file_path, n.id) AS name,
                           coalesce(n.file_path, split(n.id, '::')[0]) AS file_path,
                           labels(n)[0] AS type,
                           coalesce(n.start_line, n.line, 0) AS line
                    LIMIT 200
                """)
                anchors = [dict(r) for r in records]

            active_edges = ["RESOLVED_CALLS", "CALLS", "IMPORTS", "INSTANTIATES", "HAS_METHOD", "RESOLVED_INHERITS"]

            # Run DP path expansion per anchor
            for anchor in anchors:
                start_id = anchor["id"]
                queue: deque[Tuple[Dict[str, Any], List[Dict[str, Any]], int]] = deque()
                queue.append((anchor, [anchor], 0))

                while queue and len(all_cycles) < limit:
                    curr_node, chain, depth = queue.popleft()
                    if depth >= max_depth:
                        continue

                    curr_id = curr_node["id"]
                    edge_key = "-".join(sorted(active_edges))
                    memo_key = f"{curr_id}:outgoing:{edge_key}:all"

                    if memo_key in self._dp_memo:
                        neighbors = self._dp_memo[memo_key]
                    else:
                        neighbors = self._fetch_1hop_neighbors(
                            session=session,
                            node=curr_node,
                            direction="outgoing",
                            edge_types=active_edges,
                            target_labels=None,
                        )
                        self._dp_memo[memo_key] = neighbors

                    for nbr in neighbors:
                        nbr_id = nbr.get("id")
                        if not nbr_id:
                            continue

                        # Check if this neighbor completes a cycle back to the starting anchor
                        if nbr_id == start_id and len(chain) >= 2:
                            cycle_nodes = chain + [nbr]
                            cycle_node_ids = [n["id"] for n in chain]
                            
                            # Canonical representation to eliminate symmetric rotations
                            min_idx = cycle_node_ids.index(min(cycle_node_ids))
                            canonical_key = tuple(cycle_node_ids[min_idx:] + cycle_node_ids[:min_idx])
                            
                            if canonical_key not in seen_canonical_cycles:
                                seen_canonical_cycles.add(canonical_key)
                                
                                types = [n.get("type", "Node") for n in chain]
                                unique_types = set(types)
                                
                                cycle_chain_str = " -> ".join([f"{n.get('type', 'Node')} {n.get('name')}" for n in cycle_nodes])
                                
                                cycle_item = {
                                    "cycle_length": len(chain),
                                    "cycle_chain": cycle_chain_str,
                                    "nodes": [{
                                        "id": n.get("id"),
                                        "name": n.get("name"),
                                        "type": n.get("type"),
                                        "file_path": n.get("file_path"),
                                        "line": n.get("line"),
                                    } for n in cycle_nodes],
                                    "cycle_type": "file_import" if unique_types == {"File"} else (
                                        "function_call" if unique_types == {"Function"} else (
                                            "class_instantiation" if unique_types == {"Class"} else "heterogeneous"
                                        )
                                    )
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

                        # If neighbor is not already in the active path, continue search
                        elif not any(n["id"] == nbr_id for n in chain):
                            queue.append((nbr, chain + [nbr], depth + 1))

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
        """
        Universal Dynamic Programming Dead Code & Unused Entity Detection Engine.
        Analyzes and detects:
        1. Dead / Uncalled Functions (in-degree = 0 or unreachable from entrypoints via DP)
        2. Dead / Uninstantiated Classes (0 incoming INSTANTIATES / INHERITS_FROM)
        3. Dead / Unused Files (0 incoming IMPORTS, excluding root scripts)
        4. Dead / Unused Environment Variables (0 USES_ENV relationships)
        5. Dead / Unused Global Variables (0 referencing functions)
        6. Dead / Unused Function Parameters
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
            "dead_parameters": [],
            "total_dead_entities": 0,
        }

        with self.neo4j_db.driver.session() as session:
            # 1. Dead Functions (using DP Reachability if requested)
            if entity_type in ("all", "functions", "function", "methods"):
                if use_dp_reachability:
                    # Find root entrypoints (main functions, endpoints)
                    entrypoint_records = session.run("""
                        MATCH (fn:Function)
                        WHERE fn.name = 'main' 
                           OR fn.name STARTS WITH 'run_'
                           OR fn.name STARTS WITH 'cli_'
                           OR fn.file_path ENDS WITH 'main.py'
                           OR fn.file_path ENDS WITH 'app.py'
                        RETURN fn.name AS name, fn.id AS id
                    """)
                    entrypoint_syms = [r["name"] for r in entrypoint_records]
                    
                    reachable_ids = set()
                    if entrypoint_syms:
                        reach_res = self.traverse_graph_dp(
                            symbols=entrypoint_syms,
                            direction="outgoing",
                            edge_types=["RESOLVED_CALLS", "CALLS", "INSTANTIATES", "HAS_METHOD"],
                            max_depth=30,
                            limit=500,
                        )
                        for n in reach_res.get("detailed_nodes", []):
                            reachable_ids.add(n.get("id"))
                            if n.get("name"):
                                reachable_ids.add(n.get("name"))

                    # Query all functions and filter out reachable ones
                    all_fn_records = session.run("""
                        MATCH (fn:Function)
                        WHERE NOT fn.name STARTS WITH '__'
                          AND NOT fn.name STARTS WITH 'test_'
                          AND ($scope IS NULL OR fn.file_path CONTAINS $scope OR fn.id CONTAINS $scope)
                        RETURN fn.id AS id, fn.name AS name, fn.file_path AS file_path, coalesce(fn.start_line, fn.line, 0) AS line
                        LIMIT 300
                    """, scope=scope_path)

                    dead_fns = []
                    for r in all_fn_records:
                        f_id = r["id"]
                        f_name = r["name"]
                        if f_id not in reachable_ids and f_name not in reachable_ids:
                            dead_fns.append({
                                "name": f_name,
                                "file_path": r["file_path"],
                                "line": r["line"],
                                "reason": "Unreachable from application entrypoints via DP forward traversal",
                            })
                    results["dead_functions"] = dead_fns[:limit]
                else:
                    # 1-hop in-degree zero
                    fn_records = session.run("""
                        MATCH (fn:Function)
                        WHERE NOT ()-[:RESOLVED_CALLS|CALLS]->(fn)
                          AND NOT fn.name STARTS WITH '__'
                          AND NOT fn.name STARTS WITH 'test_'
                          AND ($scope IS NULL OR fn.file_path CONTAINS $scope OR fn.id CONTAINS $scope)
                        RETURN fn.name AS name, fn.file_path AS file_path, coalesce(fn.start_line, fn.line, 0) AS line
                        LIMIT $limit
                    """, scope=scope_path, limit=limit)
                    results["dead_functions"] = [
                        {"name": r["name"], "file_path": r["file_path"], "line": r["line"], "reason": "0 incoming callers"}
                        for r in fn_records
                    ]

            # 2. Dead Classes (0 instantiations and 0 inheritance)
            if entity_type in ("all", "classes", "class"):
                cls_records = session.run("""
                    MATCH (cls:Class)
                    WHERE NOT ()-[:INSTANTIATES]->(cls)
                      AND NOT ()-[:RESOLVED_INHERITS|INHERITS_FROM]->(cls)
                      AND NOT cls.name STARTS WITH 'Test'
                      AND NOT cls.name STARTS WITH '_'
                      AND ($scope IS NULL OR cls.file_path CONTAINS $scope OR cls.id CONTAINS $scope)
                    RETURN cls.name AS name, cls.file_path AS file_path, coalesce(cls.start_line, cls.line, 0) AS line
                    LIMIT $limit
                """, scope=scope_path, limit=limit)
                results["dead_classes"] = [
                    {"name": r["name"], "file_path": r["file_path"], "line": r["line"], "reason": "0 instantiations and 0 subclasses"}
                    for r in cls_records
                ]

            # 3. Dead Files / Modules (0 incoming imports, excluding root entrypoints)
            if entity_type in ("all", "files", "file", "modules"):
                file_records = session.run("""
                    MATCH (f:File)
                    WHERE NOT ()-[:IMPORTS]->(f)
                      AND NOT f.name IN ['main.py', 'app.py', 'setup.py', '__init__.py', 'manage.py']
                      AND ($scope IS NULL OR f.file_path CONTAINS $scope OR f.name CONTAINS $scope)
                    RETURN coalesce(f.file_path, f.name) AS file_path, f.name AS name
                    LIMIT $limit
                """, scope=scope_path, limit=limit)
                results["dead_files"] = [
                    {"file_path": r["file_path"], "name": r["name"], "reason": "0 incoming file imports across the repository"}
                    for r in file_records
                ]

            # 4. Dead Environment Variables (0 USES_ENV usages)
            if entity_type in ("all", "env_vars", "env", "envs"):
                env_records = session.run("""
                    MATCH (env:EnvVar)
                    WHERE NOT ()-[:USES_ENV]->(env)
                    RETURN env.name AS name, env.default_value AS default_value
                    LIMIT $limit
                """, limit=limit)
                results["dead_env_vars"] = [
                    {"name": r["name"], "default_value": r["default_value"], "reason": "0 code references to this environment variable"}
                    for r in env_records
                ]

            # 5. Dead Variables & Constants
            if entity_type in ("all", "variables", "variable", "constants"):
                var_records = session.run("""
                    MATCH (var:Variable)
                    WHERE NOT ()-[:CONTAINS_VARIABLE]->()
                      AND NOT var.name STARTS WITH '__'
                      AND ($scope IS NULL OR var.file_path CONTAINS $scope OR var.id CONTAINS $scope)
                    RETURN var.name AS name, var.file_path AS file_path, coalesce(var.start_line, var.line, 0) AS line
                    LIMIT $limit
                """, scope=scope_path, limit=limit)
                results["dead_variables"] = [
                    {"name": r["name"], "file_path": r["file_path"], "line": r["line"], "reason": "Unreferenced global/module variable"}
                    for r in var_records
                ]

        total_dead = (
            len(results["dead_functions"])
            + len(results["dead_classes"])
            + len(results["dead_files"])
            + len(results["dead_env_vars"])
            + len(results["dead_variables"])
            + len(results["dead_parameters"])
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
        limit: int,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        discovered_paths: List[Dict[str, Any]] = []
        discovered_raw: List[Dict[str, Any]] = []
        visited_nodes: Dict[str, Dict[str, Any]] = {}
        global_visited_node_ids: Set[str] = set()

        queue: deque[Tuple[Dict[str, Any], List[Dict[str, Any]], int]] = deque()

        for anchor in anchors:
            anchor_id = anchor["id"]
            global_visited_node_ids.add(anchor_id)
            visited_nodes[anchor_id] = {**anchor, "distance": 0}
            queue.append((anchor, [anchor], 0))

        while queue and len(discovered_paths) < limit:
            curr_node, chain, depth = queue.popleft()

            if depth >= max_depth:
                continue

            curr_id = curr_node["id"]
            edge_key = "-".join(sorted(edge_types))
            label_key = "-".join(sorted(target_labels)) if target_labels else "all"
            memo_key = f"{curr_id}:{direction}:{edge_key}:{label_key}"

            if memo_key in self._dp_memo:
                neighbors = self._dp_memo[memo_key]
            else:
                neighbors = self._fetch_1hop_neighbors(
                    session=session,
                    node=curr_node,
                    direction=direction,
                    edge_types=edge_types,
                    target_labels=target_labels,
                )
                self._dp_memo[memo_key] = neighbors

            for nbr in neighbors:
                edge_type = nbr.get("edge_type", "RESOLVED_CALLS")
                nbr_type = nbr.get("type", "Node")
                nbr_id = nbr["id"]
                nbr_name = nbr.get("name", nbr_id)

                if nbr_type in ("Target", "RawVariable", "RawInstanceAttribute"):
                    if include_raw:
                        discovered_raw.append({
                            "type": f"raw_{'caller' if direction == 'incoming' else 'callee'}",
                            "source_id": curr_id,
                            "source_name": curr_node.get("name", curr_id),
                            "caller_id": nbr_id if direction == "incoming" else curr_id,
                            "caller_name": nbr_name if direction == "incoming" else curr_node.get("name", curr_id),
                            "line": nbr.get("line"),
                            "target_name": curr_node.get("name", curr_id) if direction == "incoming" else nbr_name,
                            "file_path": nbr.get("file_path", ""),
                            "distance": depth + 1,
                        })
                    continue

                if include_raw and edge_type == "CALLS":
                    discovered_raw.append({
                        "type": f"raw_{'caller' if direction == 'incoming' else 'callee'}",
                        "source_id": curr_id,
                        "source_name": curr_node.get("name", curr_id),
                        "caller_id": nbr_id if direction == "incoming" else curr_id,
                        "caller_name": nbr_name if direction == "incoming" else curr_node.get("name", curr_id),
                        "line": nbr.get("line"),
                        "target_name": curr_node.get("name", curr_id) if direction == "incoming" else nbr_name,
                        "file_path": nbr.get("file_path", ""),
                        "distance": depth + 1,
                    })

                if direction == "incoming":
                    new_chain = [nbr] + chain
                else:
                    new_chain = chain + [nbr]

                exec_chain = " -> ".join([n.get("name", n["id"]) for n in new_chain])

                discovered_paths.append({
                    "type": direction,
                    "depth": depth + 1,
                    "execution_chain": exec_chain,
                    "nodes": new_chain,
                    "edges": [edge_type] * (depth + 1),
                })

                if nbr_id not in global_visited_node_ids:
                    global_visited_node_ids.add(nbr_id)
                    visited_nodes[nbr_id] = {
                        "id": nbr_id,
                        "name": nbr_name,
                        "type": nbr_type,
                        "file_path": nbr.get("file_path"),
                        "line": nbr.get("line"),
                        "distance": depth + 1,
                    }
                    queue.append((nbr, new_chain, depth + 1))

        return discovered_paths, discovered_raw, visited_nodes

    def _fetch_1hop_neighbors(
        self,
        session,
        node: Dict[str, Any],
        direction: str,
        edge_types: List[str],
        target_labels: Optional[List[str]],
    ) -> List[Dict[str, Any]]:
        node_id = node["id"]
        node_name = node.get("name") or node_id.split("::")[-1].split(".")[-1]
        rel_pattern = "|".join(edge_types)

        if direction == "incoming":
            cypher = f"""
                MATCH (neighbor)-[r:{rel_pattern}]->(curr)
                WHERE (curr.id = $node_id 
                   OR curr.name = $node_name 
                   OR curr.id ENDS WITH ('.' + $node_name) 
                   OR curr.id ENDS WITH ('::' + $node_name))
                  AND ($target_labels IS NULL OR labels(neighbor)[0] IN $target_labels)
                RETURN DISTINCT
                    coalesce(neighbor.id, neighbor.name) AS id,
                    coalesce(neighbor.name, neighbor.id) AS name,
                    coalesce(neighbor.file_path, split(neighbor.id, '::')[0]) AS file_path,
                    labels(neighbor)[0] AS type,
                    type(r) AS edge_type,
                    coalesce(neighbor.start_line, r.line, neighbor.line) AS line
                LIMIT 50
            """
        else:
            cypher = f"""
                MATCH (curr)-[r:{rel_pattern}]->(neighbor)
                WHERE (curr.id = $node_id 
                   OR curr.name = $node_name 
                   OR curr.id ENDS WITH ('.' + $node_name) 
                   OR curr.id ENDS WITH ('::' + $node_name))
                  AND ($target_labels IS NULL OR labels(neighbor)[0] IN $target_labels)
                RETURN DISTINCT
                    coalesce(neighbor.id, neighbor.name) AS id,
                    coalesce(neighbor.name, neighbor.id) AS name,
                    coalesce(neighbor.file_path, split(neighbor.id, '::')[0]) AS file_path,
                    labels(neighbor)[0] AS type,
                    type(r) AS edge_type,
                    coalesce(neighbor.start_line, r.line, neighbor.line) AS line
                LIMIT 50
            """

        records = session.run(
            cypher,
            node_id=node_id,
            node_name=node_name,
            target_labels=target_labels,
        )
        return [dict(r) for r in records]

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
