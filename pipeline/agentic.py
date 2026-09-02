"""
agentic.py — Agent Routing & Orchestration Engine for CodeNavigator.

Dispatches developer queries across the 3 execution tiers:
  1. DETERMINISTIC_1_SHOT (Atomic direct queries & Composite backend macros)
  2. GUIDED_RECIPE (Branching / Conditional workflows with step-by-step guidance)
  3. REACT_FALLBACK (Open-ended / Exploratory multi-turn tool loops)
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv(override=True)

import os
import sys

# Ensure repository root is on sys.path
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from pipeline.graph_traversal import CallGraphTraversal, print_traversal_result
from pipeline.neo4j_sink import Neo4jCodeGraphIngestor
from pipeline.tools import classify_intent
from pipeline.tools_utils import ExecutionStrategy, ExecutionType, IntentClassificationResult
from pipeline.weaviate_sink import WeaviateCloudCodeDB


def _require_env(name: str) -> str:
    """Fail fast with a clear message if a required env var is missing."""
    value = os.environ.get(name)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{name}' is not set. "
            f"Set it via: export {name}=<value>"
        )
    return value


class CodeNavigatorAgent:
    """
    Main Agent Router and Orchestrator for CodeNavigator.
    Evaluates intent and executes deterministic, guided, or exploratory workflows.
    """

    def __init__(
        self,
        neo4j_sink: Optional[Neo4jCodeGraphIngestor] = None,
        weaviate_sink: Optional[WeaviateCloudCodeDB] = None,
    ):
        self._neo4j_db = neo4j_sink
        self._weaviate_db = weaviate_sink
        self._owns_neo4j = False
        self._owns_weaviate = False
        self._traversal_engine = None

    @property
    def neo4j_db(self) -> Neo4jCodeGraphIngestor:
        if self._neo4j_db is None:
            self._neo4j_db = Neo4jCodeGraphIngestor(
                uri=_require_env("NEO4J_URI"),
                auth=(_require_env("NEO4J_USER"), _require_env("NEO4J_PASSWORD")),
            )
            self._owns_neo4j = True
        return self._neo4j_db

    @property
    def weaviate_db(self) -> Optional[WeaviateCloudCodeDB]:
        if self._weaviate_db is None:
            try:
                self._weaviate_db = WeaviateCloudCodeDB(
                    cluster_url=_require_env("WEAVIATE_CLUSTER_URL"),
                    api_key=_require_env("WEAVIATE_API_KEY"),
                )
                self._owns_weaviate = True
            except Exception as e:
                print(f"[Warning] Weaviate connection not initialized: {e}")
                self._weaviate_db = None
        return self._weaviate_db

    @property
    def traversal_engine(self) -> CallGraphTraversal:
        if self._traversal_engine is None:
            self._traversal_engine = CallGraphTraversal(neo4j_sink=self.neo4j_db)
        return self._traversal_engine

    def close(self):
        """Closes database connections owned by this agent."""
        if self._owns_neo4j and self._neo4j_db:
            self._neo4j_db.close()
        if self._owns_weaviate and self._weaviate_db:
            self._weaviate_db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def handle_user_query(self, user_query: str) -> Dict[str, Any]:
        """
        Main entrypoint: Classifies intent and routes across execution tiers.

        Args:
            user_query: The developer's natural language question.

        Returns:
            Dictionary containing intent, execution plan, tool outputs, and formatted summary.
        """
        print("\n" + "=" * 80)
        print(f"  AGENT ROUTER: \"{user_query}\"")
        print("=" * 80)

        # Step 1: Classify intent
        intent = classify_intent(user_query)
        strategy = intent["strategy"]
        task_id = intent.get("task_id")
        task_name = intent.get("task_name")
        exec_type = intent.get("execution_type")
        turns = intent.get("expected_turns")
        symbols = intent.get("target_symbols", [])
        recipe = intent.get("workflow_recipe")

        print(f"\n[Classification]")
        print(f"  * Task: #{task_id} ({task_name})")
        print(f"  * Strategy: {strategy} (Type: {exec_type}, Expected Turns: {turns})")
        print(f"  * Target Symbols: {symbols}")
        print(f"  * Recommended Tools: {intent['recommended_tools']}")

        response_payload: Dict[str, Any] = {
            "query": user_query,
            "intent": intent,
            "strategy": strategy,
            "task_id": task_id,
            "task_name": task_name,
            "execution_status": "COMPLETED",
            "result_data": None,
        }

        # Step 2: Route according to Tier
        if strategy == ExecutionStrategy.DETERMINISTIC_1_SHOT.value:
            print(f"\n>> [Tier 1: DETERMINISTIC 1-SHOT Execution (1 Turn)]")
            result = self._execute_tier_1(intent, symbols)
            response_payload["result_data"] = result

        elif strategy == ExecutionStrategy.GUIDED_RECIPE.value:
            print(f"\n>> [Tier 2: GUIDED RECIPE (Branching 2-3 Turns)]")
            print(f"   Allowed Tools: {intent['allowed_tools']}")
            print(f"\n   --- WORKFLOW RECIPE ---\n{recipe}\n   -----------------------")
            response_payload["result_data"] = {
                "status": "RECIPE_PREPARED",
                "recipe": recipe,
                "allowed_tools": intent["allowed_tools"],
                "target_symbols": symbols,
            }

        elif strategy == ExecutionStrategy.REACT_FALLBACK.value:
            print(f"\n>> [Tier 3: REACT FALLBACK (Open-Ended Exploration)]")
            print(f"   Full tool catalog exposed ({len(intent['allowed_tools'])} tools).")
            response_payload["result_data"] = {
                "status": "DISPATCHED_TO_REACT_LOOP",
                "allowed_tools": intent["allowed_tools"],
                "target_symbols": symbols,
            }

        print("=" * 80 + "\n")
        return response_payload

    def _execute_tier_1(self, intent: Dict[str, Any], symbols: List[str]) -> Dict[str, Any]:
        """Executes 1-shot deterministic tools (Atomic and Composite)."""
        task_id = intent.get("task_id")
        primary_tool = intent["recommended_tools"][0] if intent["recommended_tools"] else None

        # Task #1 & #2: Call Graph Traversals
        if task_id in (1, 2) and symbols:
            target = symbols[0]
            direction = "incoming" if task_id == 1 else "outgoing"
            print(f"   Executing Call Graph Traversal on '{target}' (Direction: {direction})...")
            traversal_res = self.traversal_engine.traverse_call_graph(
                target_symbol=target, direction=direction, max_depth=3
            )
            print_traversal_result(traversal_res)
            return traversal_res

        # Task #13: Dead Code & Orphan Detection
        elif task_id == 13:
            print("   Executing Dead Code & Orphan Node Detection...")
            return self._detect_dead_code()

        # Task #20: API Surface Query
        elif task_id == 20:
            print("   Executing API Endpoints Surface Query...")
            return self._query_api_surface()

        # Fallback / General 1-Shot Tool Execution
        else:
            print(f"   Ready to execute 1-shot tool: '{primary_tool}' with symbols: {symbols}")
            return {
                "tool": primary_tool,
                "symbols": symbols,
                "status": "Ready for 1-turn synthesis",
            }

    def _detect_dead_code(self) -> Dict[str, Any]:
        """Queries Neo4j for functions with in_degree(RESOLVED_CALLS|CALLS) == 0."""
        with self.neo4j_db.driver.session() as session:
            records = session.run("""
                MATCH (fn:Function)
                WHERE NOT ( ()-[:RESOLVED_CALLS|CALLS]->(fn) )
                  AND NOT fn.name STARTS WITH '__'
                  AND NOT fn.name STARTS WITH 'test_'
                RETURN fn.name AS name, fn.file_path AS file_path, fn.line_start AS line
                LIMIT 25
            """)
            orphans = [
                {"name": r["name"], "file_path": r["file_path"], "line": r["line"]}
                for r in records
            ]
            print(f"\nDiscovered {len(orphans)} Uncalled / Orphan Function(s):")
            for o in orphans[:10]:
                print(f"  * {o['name']}() in {o['file_path']} (line {o['line']})")
            if len(orphans) > 10:
                print(f"  ... and {len(orphans) - 10} more.")
            return {"orphan_functions": orphans, "total_found": len(orphans)}

    def _query_api_surface(self) -> Dict[str, Any]:
        """Queries Neo4j for exposed API endpoints."""
        with self.neo4j_db.driver.session() as session:
            records = session.run("""
                MATCH (fn:Function)
                WHERE fn.is_endpoint = true OR fn.route_path IS NOT NULL
                RETURN fn.name AS name, fn.route_path AS route, fn.http_method AS method, fn.file_path AS file_path
                LIMIT 25
            """)
            endpoints = [
                {"name": r["name"], "route": r["route"], "method": r["method"], "file_path": r["file_path"]}
                for r in records
            ]
            if endpoints:
                print(f"\nDiscovered {len(endpoints)} API Endpoint(s):")
                for ep in endpoints:
                    print(f"  * [{ep['method'] or 'ANY'}] {ep['route'] or ep['name']} -> {ep['file_path']}")
            else:
                print("\nNo explicitly decorated API endpoint nodes found in current graph.")
            return {"endpoints": endpoints, "total_found": len(endpoints)}


def route_query(user_query: str) -> Dict[str, Any]:
    """Convenience helper to route a user query through the agent."""
    with CodeNavigatorAgent() as agent:
        return agent.handle_user_query(user_query)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CodeNavigator Agentic Router & Query Engine.")
    parser.add_argument("query", nargs="?", default="What is the blast radius if I modify Order.status?", help="User query to process.")
    args = parser.parse_args()

    agent = CodeNavigatorAgent()
    try:
        agent.handle_user_query(args.query)
    finally:
        agent.close()
