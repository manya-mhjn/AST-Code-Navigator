"""
graph_traversal.py — Call Graph Traversal Engine on Neo4j.

Provides N-hop upstream (caller analysis) and downstream (callee / dependency analysis)
traversals across the Code Knowledge Graph in Neo4j.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv(override=True)

import os
from pipeline.neo4j_sink import Neo4jCodeGraphIngestor


def _require_env(name: str) -> str:
    """Fail fast with a clear message if a required env var is missing."""
    value = os.environ.get(name)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{name}' is not set. "
            f"Set it via: export {name}=<value>"
        )
    return value


class CallGraphTraversal:
    """
    High-performance Call Graph Traversal engine for Neo4j Code Knowledge Graphs.
    Supports N-hop upstream caller tracing, downstream callee tracing, and bidirectional traversal.
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

    def close(self):
        """Closes the underlying Neo4j driver connection if owned by this instance."""
        if self._owns_db and self.neo4j_db:
            self.neo4j_db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def traverse_call_graph(
        self,
        target_symbol: str,
        direction: str = "incoming",
        max_depth: int = 3,
        file_path: Optional[str] = None,
        include_raw: bool = True,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Traverses the call graph up to `max_depth` hops.

        Args:
            target_symbol: Name of the function/method (e.g., 'process_refund') or fully qualified ID.
            direction: 'incoming' (upstream callers), 'outgoing' (downstream callees), or 'both'.
            max_depth: Maximum hops to traverse (default 3, range 1..10).
            file_path: Optional file path to disambiguate target symbol if multiple exist.
            include_raw: Whether to include unresolved :CALLS edges to raw Target nodes.
            limit: Maximum paths to return.

        Returns:
            Structured dictionary with paths, depth levels, unique callers/callees, and node details.
        """
        direction = direction.lower()
        if direction not in ("incoming", "outgoing", "both"):
            raise ValueError(f"Invalid direction '{direction}'. Must be 'incoming', 'outgoing', or 'both'.")

        max_depth = max(1, min(max_depth, 10))

        result_data: Dict[str, Any] = {
            "target": target_symbol,
            "direction": direction,
            "max_depth": max_depth,
            "file_path_filter": file_path,
            "total_paths": 0,
            "paths": [],
            "unique_nodes": [],
            "raw_calls": [],
        }

        with self.neo4j_db.driver.session() as session:
            # 1. Incoming Callers (Upstream Traversal)
            if direction in ("incoming", "both"):
                incoming_res = self._query_incoming_calls(
                    session=session,
                    target_symbol=target_symbol,
                    max_depth=max_depth,
                    file_path=file_path,
                    limit=limit,
                )
                result_data["paths"].extend(incoming_res["paths"])
                if include_raw:
                    raw_callers = self._query_raw_callers(session, target_symbol, file_path)
                    result_data["raw_calls"].extend(raw_callers)

            # 2. Outgoing Callees (Downstream Traversal)
            if direction in ("outgoing", "both"):
                outgoing_res = self._query_outgoing_calls(
                    session=session,
                    target_symbol=target_symbol,
                    max_depth=max_depth,
                    file_path=file_path,
                    limit=limit,
                )
                result_data["paths"].extend(outgoing_res["paths"])
                if include_raw:
                    raw_callees = self._query_raw_callees(session, target_symbol, file_path)
                    result_data["raw_calls"].extend(raw_callees)

            # Deduplicate nodes across all discovered paths
            all_nodes_map = {}
            for path in result_data["paths"]:
                for node in path["nodes"]:
                    if node["id"] not in all_nodes_map:
                        all_nodes_map[node["id"]] = node

            result_data["unique_nodes"] = list(all_nodes_map.values())
            result_data["total_paths"] = len(result_data["paths"])

        return result_data

    def _query_incoming_calls(
        self,
        session,
        target_symbol: str,
        max_depth: int,
        file_path: Optional[str],
        limit: int,
    ) -> Dict[str, Any]:
        """Queries N-hop incoming callers (Upstream)."""
        cypher = f"""
            MATCH path = (caller)-[:RESOLVED_CALLS*1..{max_depth}]->(target)
            WHERE (target.name = $fn_name 
                   OR target.id = $fn_name 
                   OR target.id ENDS WITH ('.' + $fn_name) 
                   OR target.id ENDS WITH ('::' + $fn_name))
              AND ($file_path IS NULL OR target.file_path = $file_path OR target.id STARTS WITH $file_path)
            RETURN 
                [node IN nodes(path) | {{
                    id: coalesce(node.id, node.name),
                    name: coalesce(node.name, node.id),
                    file_path: coalesce(node.file_path, split(node.id, '::')[0]),
                    type: labels(node)[0],
                    line: coalesce(node.line_start, node.line)
                }}] AS nodes_chain,
                [rel IN relationships(path) | type(rel)] AS edge_types,
                length(path) AS depth
            ORDER BY depth ASC
            LIMIT $limit
        """
        records = session.run(cypher, fn_name=target_symbol, file_path=file_path, limit=limit)
        paths = []
        for r in records:
            nodes = r["nodes_chain"]
            # Visual chain: root caller -> ... -> target
            chain_labels = [n["name"] for n in nodes]
            paths.append({
                "type": "incoming",
                "depth": r["depth"],
                "execution_chain": " -> ".join(chain_labels),
                "nodes": nodes,
                "edges": r["edge_types"],
            })
        return {"paths": paths}

    def _query_outgoing_calls(
        self,
        session,
        target_symbol: str,
        max_depth: int,
        file_path: Optional[str],
        limit: int,
    ) -> Dict[str, Any]:
        """Queries N-hop outgoing callees (Downstream)."""
        cypher = f"""
            MATCH path = (source)-[:RESOLVED_CALLS*1..{max_depth}]->(callee)
            WHERE (source.name = $fn_name 
                   OR source.id = $fn_name 
                   OR source.id ENDS WITH ('.' + $fn_name) 
                   OR source.id ENDS WITH ('::' + $fn_name))
              AND ($file_path IS NULL OR source.file_path = $file_path OR source.id STARTS WITH $file_path)
            RETURN 
                [node IN nodes(path) | {{
                    id: coalesce(node.id, node.name),
                    name: coalesce(node.name, node.id),
                    file_path: coalesce(node.file_path, split(node.id, '::')[0]),
                    type: labels(node)[0],
                    line: coalesce(node.line_start, node.line)
                }}] AS nodes_chain,
                [rel IN relationships(path) | type(rel)] AS edge_types,
                length(path) AS depth
            ORDER BY depth ASC
            LIMIT $limit
        """
        records = session.run(cypher, fn_name=target_symbol, file_path=file_path, limit=limit)
        paths = []
        for r in records:
            nodes = r["nodes_chain"]
            chain_labels = [n["name"] for n in nodes]
            paths.append({
                "type": "outgoing",
                "depth": r["depth"],
                "execution_chain": " -> ".join(chain_labels),
                "nodes": nodes,
                "edges": r["edge_types"],
            })
        return {"paths": paths}

    def _query_raw_callers(self, session, target_symbol: str, file_path: Optional[str]) -> List[Dict[str, Any]]:
        """Queries direct 1-hop unresolved CALLS edges where target name matches."""
        cypher = """
            MATCH (caller)-[r:CALLS]->(t:Target)
            WHERE t.name = $fn_name OR t.name ENDS WITH ('.' + $fn_name)
            RETURN caller.id AS caller_id, caller.name AS caller_name, r.line AS line, t.name AS target_name
            LIMIT 20
        """
        records = session.run(cypher, fn_name=target_symbol)
        raw_list = []
        for r in records:
            raw_list.append({
                "type": "raw_caller",
                "caller_id": r["caller_id"],
                "caller_name": r["caller_name"] or r["caller_id"],
                "line": r["line"],
                "target_name": r["target_name"],
            })
        return raw_list

    def _query_raw_callees(self, session, target_symbol: str, file_path: Optional[str]) -> List[Dict[str, Any]]:
        """Queries direct 1-hop unresolved CALLS edges outgoing from the target symbol."""
        cypher = """
            MATCH (source)-[r:CALLS]->(t:Target)
            WHERE (source.name = $fn_name 
                   OR source.id = $fn_name 
                   OR source.id ENDS WITH ('.' + $fn_name) 
                   OR source.id ENDS WITH ('::' + $fn_name))
              AND ($file_path IS NULL OR source.file_path = $file_path OR source.id STARTS WITH $file_path)
            RETURN source.id AS source_id, source.name AS source_name, r.line AS line, t.name AS target_name
            LIMIT 20
        """
        records = session.run(cypher, fn_name=target_symbol, file_path=file_path)
        raw_list = []
        for r in records:
            raw_list.append({
                "type": "raw_callee",
                "source_id": r["source_id"],
                "source_name": r["source_name"] or r["source_id"],
                "line": r["line"],
                "target_name": r["target_name"],
            })
        return raw_list


def traverse_call_graph(
    target_symbol: str,
    direction: str = "incoming",
    max_depth: int = 3,
    file_path: Optional[str] = None,
    include_raw: bool = True,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    Convenience tool function to execute call graph traversal.

    Args:
        target_symbol: Function or method name to trace.
        direction: 'incoming' (callers), 'outgoing' (callees), or 'both'.
        max_depth: Max traversal hop depth (default: 3).
        file_path: Optional file path filter.
        include_raw: Include raw/unresolved calls (default: True).
        limit: Limit maximum results returned.

    Returns:
        Structured call graph result dictionary.
    """
    traversal_engine = CallGraphTraversal()
    try:
        return traversal_engine.traverse_call_graph(
            target_symbol=target_symbol,
            direction=direction,
            max_depth=max_depth,
            file_path=file_path,
            include_raw=include_raw,
            limit=limit,
        )
    finally:
        traversal_engine.close()


def print_traversal_result(result: Dict[str, Any]):
    """Pretty prints traversal results to the console."""
    target = result.get("target")
    direction = result.get("direction", "").upper()
    depth = result.get("max_depth")
    paths = result.get("paths", [])
    raw_calls = result.get("raw_calls", [])

    print("\n" + "=" * 75)
    print(f" CALL GRAPH TRAVERSAL: '{target}' | Direction: {direction} | Max Depth: {depth}")
    print("=" * 75)

    if not paths and not raw_calls:
        print(f"  No call paths found for symbol '{target}'.")
        return

    if paths:
        print(f"\nDiscovered {len(paths)} Resolved Call Path(s):")
        for i, path in enumerate(paths, 1):
            ptype = path.get("type", "").capitalize()
            pdepth = path.get("depth", 1)
            chain = path.get("execution_chain", "")
            print(f"  [{i}] ({ptype} - Hop {pdepth}): {chain}")
            # Print file details for nodes in path
            for n in path.get("nodes", []):
                file_loc = f" (in {n['file_path']}:{n['line']})" if n.get("file_path") and n.get("line") else ""
                print(f"       -> {n['name']} [{n['type']}]{file_loc}")

    if raw_calls:
        print(f"\nDiscovered {len(raw_calls)} Direct Raw / Unresolved Call(s):")
        for raw in raw_calls:
            if raw["type"] == "raw_caller":
                print(f"  * Caller: {raw['caller_name']} (line {raw['line']}) -[:CALLS]-> {raw['target_name']}")
            else:
                print(f"  * Source: {raw['source_name']} (line {raw['line']}) -[:CALLS]-> {raw['target_name']}")

    unique_nodes = result.get("unique_nodes", [])
    if unique_nodes:
        print(f"\nSummary: {len(unique_nodes)} unique function/code nodes involved.")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Traverse Call Graphs in Neo4j (Upstream / Downstream).")
    parser.add_argument("target_symbol", help="Target function or method name (e.g. process_refund, load_adventure)")
    parser.add_argument(
        "-d", "--direction",
        choices=["incoming", "outgoing", "both"],
        default="incoming",
        help="Traversal direction: 'incoming' (callers), 'outgoing' (callees), or 'both' (default: incoming)",
    )
    parser.add_argument("--depth", type=int, default=3, help="Max hop depth (default: 3)")
    parser.add_argument("--file", type=str, default=None, help="Optional file path filter for disambiguation")
    parser.add_argument("--no-raw", action="store_true", help="Exclude raw/unresolved CALLS edges")

    args = parser.parse_args()

    engine = CallGraphTraversal()
    try:
        res = engine.traverse_call_graph(
            target_symbol=args.target_symbol,
            direction=args.direction,
            max_depth=args.depth,
            file_path=args.file,
            include_raw=not args.no_raw,
        )
        print_traversal_result(res)
    finally:
        engine.close()
