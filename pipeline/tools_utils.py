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
