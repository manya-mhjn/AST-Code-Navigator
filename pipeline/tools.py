"""
tools.py — Agent Tool Interfaces and Intent Classifier for CodeNavigator.

Exposes structured tools, intent classification, and composite workflows.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from pipeline.graph_traversal import traverse_call_graph
from pipeline.tools_utils import (
    ExecutionStrategy,
    ExecutionType,
    IntentClassificationResult,
    TASK_DEFINITIONS,
)


class CodeIntentClassifier:
    """
    Classifies developer questions into execution tiers (DETERMINISTIC_1_SHOT, GUIDED_RECIPE, REACT_FALLBACK).
    """

    def __init__(self):
        self.task_defs = TASK_DEFINITIONS

    def classify(self, query: str) -> IntentClassificationResult:
        normalized = query.strip().lower()

        # 1. Deterministic & Branching Pattern Match
        for task_id, task_info in self.task_defs.items():
            for pattern in task_info["patterns"]:
                if re.search(pattern, normalized, re.IGNORECASE):
                    symbols = self._extract_symbols(query)
                    return IntentClassificationResult(
                        query=query,
                        task_id=task_id,
                        task_name=task_info["name"],
                        strategy=task_info["strategy"],
                        execution_type=task_info["execution_type"],
                        expected_turns=task_info["expected_turns"],
                        recommended_tools=task_info["recommended_tools"],
                        allowed_tools=self._filter_allowed_tools(task_info),
                        target_symbols=symbols,
                        workflow_recipe=task_info.get("recipe"),
                        confidence=0.95,
                        explanation=f"Matched Task #{task_id} ({task_info['name']}) under {task_info['strategy'].value}.",
                    )

        # 2. TIER 3: ReAct Fallback (Open-Ended / Exploratory)
        symbols = self._extract_symbols(query)
        all_tools = [
            "traverse_call_graph", "calculate_blast_radius", "inspect_type_and_inheritance_hierarchy",
            "query_variable_and_state_references", "analyze_architecture_coupling",
            "detect_orphan_and_dead_code", "trace_taint_and_security_paths",
            "query_test_traceability", "query_api_endpoints", "search_codebase_semantic",
            "get_symbol_code_snippet"
        ]
        return IntentClassificationResult(
            query=query,
            task_id=None,
            task_name="Open-Ended / Exploratory Query",
            strategy=ExecutionStrategy.REACT_FALLBACK,
            execution_type=ExecutionType.OPEN_ENDED,
            expected_turns=-1,
            recommended_tools=["search_codebase_semantic", "traverse_call_graph"],
            allowed_tools=all_tools,
            target_symbols=symbols,
            workflow_recipe=None,
            confidence=0.50,
            explanation="No deterministic task pattern matched. Dispatched to unconstrained ReAct loop.",
        )

    def _filter_allowed_tools(self, task_info: Dict[str, Any]) -> List[str]:
        tools = list(task_info["recommended_tools"])
        if "get_symbol_code_snippet" not in tools:
            tools.append("get_symbol_code_snippet")
        return tools

    def _extract_symbols(self, query: str) -> List[str]:
        extracted = []
        # 1. Match code tokens, dot attributes (e.g. Order.status, User.get_permissions), function calls, paths
        matches = re.findall(r"(?:`([^`]+)`|([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)|([\w\.\/\-]+(?:\.py)?::[\w_]+)|([\w\.\/\-]+\(\)))", query)
        for m in matches:
            for item in m:
                if item:
                    token = item.replace("()", "").strip()
                    if token and token not in extracted:
                        extracted.append(token)

        # 2. Match ALL_CAPS constants or env variables (e.g. PAYMENT_SECRET_KEY, MAX_RETRY_COUNT)
        caps = re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", query)
        for c in caps:
            if c not in extracted and "_" in c:
                extracted.append(c)

        # 3. Match lowercase identifiers (e.g. process_refund, user_id, get_user_feed)
        words = re.findall(r"\b[a-z_][a-z0-9_]{3,}\b", query)
        stop_words = {"what", "which", "where", "does", "will", "from", "into", "that", "this", "have", "with", "call", "calls", "read", "modify", "change", "inside", "queries", "database", "loops"}
        for w in words:
            if w not in stop_words and "_" in w and w not in extracted:
                extracted.append(w)

        return extracted


def classify_intent(query: str) -> Dict[str, Any]:
    """Classifies a user developer query into execution tiers and recommended tools."""
    classifier = CodeIntentClassifier()
    return classifier.classify(query).to_dict()


def tool_classify_intent(query: str) -> Dict[str, Any]:
    """
    Agent tool to classify developer queries into execution tiers (DETERMINISTIC_1_SHOT, GUIDED_RECIPE, REACT_FALLBACK).
    """
    return classify_intent(query)


def tool_traverse_call_graph(
    target_symbol: str,
    direction: str = "incoming",
    max_depth: int = 3,
    file_path: Optional[str] = None,
    include_raw: bool = True,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    Agent tool to perform upstream (caller) or downstream (callee) call graph traversals.
    """
    return traverse_call_graph(
        target_symbol=target_symbol,
        direction=direction,
        max_depth=max_depth,
        file_path=file_path,
        include_raw=include_raw,
        limit=limit,
    )
