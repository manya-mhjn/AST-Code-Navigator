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
            try:
                from pipeline.tools import _get_neo4j_session
                pooled = _get_neo4j_session()
                if pooled:
                    self.neo4j_db = pooled
                    self._owns_db = False
                else:
                    self.neo4j_db = Neo4jCodeGraphIngestor(
                        uri=_require_env("NEO4J_URI"),
                        auth=(_require_env("NEO4J_USER"), _require_env("NEO4J_PASSWORD")),
                    )
                    self._owns_db = True
            except Exception:
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
            "dead_parameters": [],
            "total_dead_entities": 0,
        }

        with self.neo4j_db.driver.session() as session:
            # 1. STEP 1: Find Application Root Entrypoints
            entrypoint_records = session.run("""
                MATCH (entry)
                WHERE (entry:Function OR entry:File)
                  AND (entry.name IN ['main', 'app', 'cli', 'run', 'start', 'serve'] 
                       OR entry.name STARTS WITH 'main_' 
                       OR entry.name STARTS WITH 'cli_' 
                       OR entry.name STARTS WITH 'run_' 
                       OR entry.file_path ENDS WITH 'main.py' 
                       OR entry.file_path ENDS WITH 'app.py' 
                       OR entry.file_path ENDS WITH 'setup.py' 
                       OR entry.file_path ENDS WITH 'manage.py')
                RETURN DISTINCT elementId(entry) AS entry_id, coalesce(entry.name, entry.id) AS name
            """)
            entrypoint_rows = [dict(r) for r in entrypoint_records]
            entrypoint_syms = [r["name"] for r in entrypoint_rows]
            entrypoint_ids = [r["entry_id"] for r in entrypoint_rows]

            # 2. STEP 2: Compute Reachable Set (R) from Entrypoints
            reachable_elem_ids: Set[Any] = set(entrypoint_ids)
            reachable_names: Set[str] = set(entrypoint_syms)

            if entrypoint_syms and use_dp_reachability:
                reach_res = self.traverse_graph_dp(
                    symbols=entrypoint_syms,
                    direction="outgoing",
                    edge_types=["RESOLVED_CALLS", "CALLS", "IMPORTS", "INSTANTIATES", "HAS_METHOD", "RESOLVED_INHERITS", "USES_ENV", "CONTAINS_VARIABLE"],
                    max_depth=30,
                    limit=1000,
                )
                for n in reach_res.get("detailed_nodes", []):
                    if n.get("int_id"):
                        reachable_elem_ids.add(n.get("int_id"))
                    if n.get("id"):
                        reachable_elem_ids.add(n.get("id"))
                    if n.get("name"):
                        reachable_names.add(n.get("name"))

            # 3. STEP 3: Fetch Universe Set (U) of all defined entities
            universe_records = session.run("""
                MATCH (n)
                WHERE (n:Function OR n:Class OR n:File OR n:EnvVar OR n:Variable)
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
                LIMIT 500
            """, scope=scope_path)

            # 4. STEP 4: Single-Pass Set Difference in Python RAM (U \ R)
            for r in universe_records:
                elem_id = r["elem_id"]
                node_id = r["id"]
                name = r["name"]
                node_type = r["type"]
                file_path = r["file_path"] or "unknown"
                line = r["line"]

                # If entity is not in reachable set, it belongs to the dead set
                if (elem_id not in reachable_elem_ids) and (node_id not in reachable_elem_ids) and (name not in reachable_names):
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
        exclude_boilerplate: bool,
        limit: int,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        discovered_paths: List[Dict[str, Any]] = []
        discovered_raw: List[Dict[str, Any]] = []
        visited_nodes: Dict[str, Dict[str, Any]] = {}
        global_visited_int_ids: Set[Any] = set()

        queue: deque[Tuple[Dict[str, Any], List[Dict[str, Any]], int]] = deque()

        for anchor in anchors:
            anchor_int_id = anchor.get("int_id")
            anchor_id = anchor["id"]
            if anchor_int_id is not None:
                global_visited_int_ids.add(anchor_int_id)
            visited_nodes[anchor_id] = {**anchor, "distance": 0}
            queue.append((anchor, [anchor], 0))

        # Early Depth Pruning: terminate frontier expansion if limit is reached
        while queue and len(discovered_paths) < limit and len(visited_nodes) < limit * 2:
            curr_node, chain, depth = queue.popleft()

            if depth >= max_depth:
                continue

            curr_id = curr_node.get("int_id") if curr_node.get("int_id") is not None else curr_node["id"]
            edge_key = "-".join(sorted(edge_types))
            label_key = "-".join(sorted(target_labels)) if target_labels else "all"
            memo_key = f"{curr_id}:{direction}:{edge_key}:{label_key}:{exclude_boilerplate}"

            if memo_key in self._dp_memo:
                neighbors = self._dp_memo[memo_key]
            else:
                neighbors = self._fetch_1hop_neighbors(
                    session=session,
                    node=curr_node,
                    direction=direction,
                    edge_types=edge_types,
                    target_labels=target_labels,
                    exclude_boilerplate=exclude_boilerplate,
                )
                self._dp_memo[memo_key] = neighbors

            for nbr in neighbors:
                edge_type = nbr.get("edge_type", "RESOLVED_CALLS")
                nbr_type = nbr.get("type", "Node")
                nbr_id = nbr["id"]
                nbr_name = nbr.get("name", nbr_id)
                nbr_int_id = nbr.get("int_id")

                if nbr_type in ("Target", "RawVariable", "RawInstanceAttribute"):
                    if include_raw:
                        discovered_raw.append({
                            "type": f"raw_{'caller' if direction == 'incoming' else 'callee'}",
                            "source_id": curr_id,
                            "source_name": curr_node.get("name", str(curr_id)),
                            "caller_id": nbr_id if direction == "incoming" else curr_id,
                            "caller_name": nbr_name if direction == "incoming" else curr_node.get("name", str(curr_id)),
                            "line": nbr.get("line"),
                            "target_name": curr_node.get("name", str(curr_id)) if direction == "incoming" else nbr_name,
                            "file_path": nbr.get("file_path", ""),
                            "distance": depth + 1,
                        })
                    continue

                if include_raw and edge_type == "CALLS":
                    discovered_raw.append({
                        "type": f"raw_{'caller' if direction == 'incoming' else 'callee'}",
                        "source_id": curr_id,
                        "source_name": curr_node.get("name", str(curr_id)),
                        "caller_id": nbr_id if direction == "incoming" else curr_id,
                        "caller_name": nbr_name if direction == "incoming" else curr_node.get("name", str(curr_id)),
                        "line": nbr.get("line"),
                        "target_name": curr_node.get("name", str(curr_id)) if direction == "incoming" else nbr_name,
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
                    queue.append((nbr, new_chain, depth + 1))

        return discovered_paths, discovered_raw, visited_nodes

    def _fetch_1hop_neighbors(
        self,
        session,
        node: Dict[str, Any],
        direction: str,
        edge_types: List[str],
        target_labels: Optional[List[str]],
        exclude_boilerplate: bool = True,
    ) -> List[Dict[str, Any]]:
        node_id = node.get("id")
        node_name = node.get("name") or str(node_id).split("::")[-1].split(".")[-1]
        int_id = node.get("int_id")
        rel_pattern = "|".join(edge_types)

        boilerplate_clause = ""
        if exclude_boilerplate:
            boilerplate_clause = """
              AND NOT (neighbor.name STARTS WITH '__' AND neighbor.name ENDS WITH '__')
              AND NOT neighbor.name IN ['print', 'len', 'range', 'isinstance', 'str', 'int', 'dict', 'list', 'set', 'repr', 'super', 'type', 'getattr', 'setattr', 'hasattr']
            """

        match_curr = "(($int_id IS NOT NULL AND elementId(curr) = $int_id) OR curr.id = $node_id OR curr.name = $node_name OR curr.id ENDS WITH ('.' + $node_name) OR curr.id ENDS WITH ('::' + $node_name))"

        if direction == "incoming":
            cypher = f"""
                MATCH (neighbor)-[r:{rel_pattern}]->(curr)
                WHERE {match_curr}
                  AND ($target_labels IS NULL OR labels(neighbor)[0] IN $target_labels)
                  {boilerplate_clause}
                RETURN DISTINCT
                    elementId(neighbor) AS int_id,
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
                WHERE {match_curr}
                  AND ($target_labels IS NULL OR labels(neighbor)[0] IN $target_labels)
                  {boilerplate_clause}
                RETURN DISTINCT
                    elementId(neighbor) AS int_id,
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
            int_id=int_id,
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
