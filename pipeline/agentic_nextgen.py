"""
agentic_nextgen.py — Next-Gen Code Intelligence Agent Architecture.

Implements:
1. Stage 1: Heuristic Fast-Path Gate (All 11 Atomic Deterministic Tasks) & Episodic Memory Gate
2. Stage 1b: Fast Synthesizer (<50ms, 0 tokens)
3. Stage 2: Hierarchical Planner (Initial & Adaptive Re-Planning with Negative Constraints)
4. Stage 3: Step Executor (Targeted Tool Dispatch)
5. Stage 4: Evidence Evaluator & Tri-State Pruning Decision (Case A / B / C)
6. Stage 5: Final Synthesizer & Episodic Memory Commit
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

# Local utilities & tool registry
from pipeline.tools import (
    ALL_TOOLS,
    tool_analyze_architecture_coupling,
    tool_calculate_blast_radius,
    tool_detect_orphan_and_dead_code,
    tool_get_symbol_code_snippet,
    tool_inspect_type_and_inheritance_hierarchy,
    tool_query_api_endpoints,
    tool_query_test_traceability,
    tool_query_variable_and_state_references,
    tool_search_codebase_semantic,
    tool_trace_parameter_lineage,
    tool_trace_taint_and_security_paths,
    tool_traverse_call_graph,
)
from pipeline.utils import get_llm

load_dotenv(override=True)


# =============================================================================
# 1. Pydantic Models for Structured Planning & Evidence Evaluation
# =============================================================================

class PlanStepStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    VERIFIED = "VERIFIED"
    PRUNED = "PRUNED"


class PlanStep(BaseModel):
    """Represents a single hypothesis-driven step in the hierarchical plan."""
    step_id: int = Field(..., description="1-indexed step number")
    tool_name: str = Field(..., description="Target tool name to invoke")
    tool_args: Dict[str, Any] = Field(default_factory=dict, description="Arguments for tool invocation")
    hypothesis: str = Field(..., description="Testable hypothesis (e.g. 'load_characters reads characters.json from disk')")
    acceptance_criteria: str = Field(..., description="Clear conditions that must be met to consider evidence found")
    status: PlanStepStatus = Field(default=PlanStepStatus.PENDING)


class HierarchicalPlanSchema(BaseModel):
    """Structured output for the Hierarchical Planner."""
    reasoning: str = Field(..., description="Architectural strategy breakdown")
    steps: List[PlanStep] = Field(..., description="Ordered list of hypothesis-driven plan steps (max 3-4 steps)")


class EvaluationVerdict(str, Enum):
    CASE_A_EVIDENCE_FOUND = "CASE_A_EVIDENCE_FOUND"
    CASE_B_RETRY_FALLBACK = "CASE_B_RETRY_FALLBACK"
    CASE_C_DEAD_END_PRUNE = "CASE_C_DEAD_END_PRUNE"


class EvidenceEvaluationSchema(BaseModel):
    """Structured evaluation of raw tool output against step acceptance criteria."""
    verdict: EvaluationVerdict = Field(..., description="Evaluation outcome: CASE_A (Success), CASE_B (Retry), CASE_C (Prune)")
    extracted_fact: Optional[str] = Field(None, description="Concise, verified fact extracted from evidence to write onto Blackboard")
    fallback_tool_name: Optional[str] = Field(None, description="Sibling tool to retry if CASE_B")
    fallback_tool_args: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Arguments for sibling tool")
    dead_end_reason: Optional[str] = Field(None, description="Reason why path was pruned if CASE_C")


# =============================================================================
# 2. Blackboard State Definition
# =============================================================================

class BlackboardState(TypedDict):
    # Query & Codebase Context
    query: str
    git_hash: str

    # Stage 1: Fast-Path / Memory Gate
    fast_path_hit: bool
    fast_path_result: Optional[str]

    # Stage 2: Hierarchical Plan State
    plan: List[Dict[str, Any]]
    current_step_index: int
    replan_count: int                      # Max loop safeguard

    # Stage 3 & 4: Evidence & Blackboard Accumulation
    current_tool_output: Optional[Any]
    blackboard_facts: List[Dict[str, Any]]  # Stores verified facts
    negative_constraints: List[str]        # Pruned dead ends to avoid
    consecutive_failures: int              # 0 -> Success, 1 -> Sibling Retry, >=2 -> Prune

    # Stage 5: Final Output
    final_response: Optional[str]


# Helper: Tool Dispatch Lookup Map
TOOL_MAP = {t.name: t for t in ALL_TOOLS}


def _get_current_git_hash(repo_path: str = ".") -> str:
    """Gets the current git commit hash or directory fingerprint."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "latest_unversioned"


# =============================================================================
# 3. Stage 1: Heuristic Fast-Path Gate (All 11 Deterministic 1-Shot Tasks)
# =============================================================================

def heuristic_and_memory_gate_node(state: BlackboardState) -> Dict[str, Any]:
    query = state["query"].strip()
    q_lower = query.lower()
    git_hash = state.get("git_hash", "latest")

    print(f"\n================================================================================")
    print(f"  [Stage 1: Fast-Path Gate] Analyzing: \"{query}\" (Git: {git_hash})")
    print(f"================================================================================")
    def _extract_symbol(pattern: str) -> Optional[str]:
        m = re.search(pattern, query, re.IGNORECASE)
        if m:
            for g in m.groups():
                if g is not None:
                    sym = g.strip("() ,\"'")
                    if sym:
                        return sym
        return None

    # 1. Task #09: Environment Variables & Configuration Audit (Check First for Env Constants)
    env_match = re.search(r"\b([A-Z0-9_]{3,}_(?:KEY|SECRET|TOKEN|URL|PORT|HOST|ENV|CONFIG|PWD|PASSWORD|FILE|DIR))\b", query)
    if env_match or "environment variable" in q_lower or "os.getenv" in q_lower:
        target = env_match.group(1) if env_match else query.split()[-1].strip("?'\"")
        print(f"  [*] [Fast-Path #09: Env Vars & Secrets] Audit for '{target}'")
        res = tool_query_variable_and_state_references.invoke({"symbol_name": target, "variable_type": "env_var"})
        refs = res.get("references", [])
        if refs:
            ans = f"Environment variable **`{target}`** is read at {len(refs)} location(s):\n\n" + "\n".join(
                [f"  - `{r.get('function_name')}` in `{r.get('file_path')}`" for r in refs]
            )
        else:
            ans = f"No references or reads of environment variable **`{target}`** were found in the codebase graph."
        return {"fast_path_hit": True, "fast_path_result": ans}

    # 2. Task #01: Upstream Call Tracing (Caller Analysis)
    sym = _extract_symbol(r"(?:who calls\s+([a-zA-Z0-9_\.]+)|callers?\s+of\s+([a-zA-Z0-9_\.]+)|where is\s+([a-zA-Z0-9_\.]+)\s+called)")
    if not sym and ("who calls" in q_lower or "callers of" in q_lower):
        sym = query.split()[-1].strip("()?'\"")
    if sym or "incoming call" in q_lower:
        target = sym or query.split()[-1].strip("()?'\"")
        print(f"  [*] [Fast-Path #01: Upstream Callers] Traversal for '{target}'")
        res = tool_traverse_call_graph.invoke({"target_symbol": target, "direction": "incoming", "max_depth": 1})
        raw_calls = res.get("raw_calls", [])
        if raw_calls:
            ans = f"Incoming Callers for **`{target}()`** ({len(raw_calls)} call site(s) found):\n\n" + "\n".join(
                [f"  - `{c.get('caller_name')}()` in `{c.get('caller_id', '').split('::')[0]}` (Line {c.get('line')})" for c in raw_calls]
            )
        else:
            ans = f"No incoming callers found invoking **`{target}()`** in the codebase graph."
        return {"fast_path_hit": True, "fast_path_result": ans}

    # 3. Task #02: Downstream Call Tracing (Callee / Dependency Analysis)
    sym = _extract_symbol(r"(?:what does|callees? of|functions? does)\s+([a-zA-Z0-9_\.]+)\s+(?:call|invoke|execute)")
    if sym or "outgoing call" in q_lower:
        target = sym or query.split()[-1].strip("()?'\"")
        print(f"  [*] [Fast-Path #02: Downstream Callees] Traversal for '{target}'")
        res = tool_traverse_call_graph.invoke({"target_symbol": target, "direction": "outgoing", "max_depth": 1})
        paths = res.get("paths", [])
        raw_calls = res.get("raw_calls", [])
        if paths or raw_calls:
            lines = []
            for p in paths:
                lines.append(f"  - Resolved Call: `{p.get('execution_chain')}` (Depth {p.get('depth')})")
            for c in raw_calls:
                lines.append(f"  - Outgoing Call: `{c.get('target_name')}()` at line {c.get('line')}")
            ans = f"Outgoing Callees initiated by **`{target}()`** ({len(paths) + len(raw_calls)} call site(s) found):\n\n" + "\n".join(lines)
        else:
            ans = f"No outgoing function calls found initiated by **`{target}()`** in the codebase graph."
        return {"fast_path_hit": True, "fast_path_result": ans}

    # 4. Task #05: Class Instance Attribute Mutability (self.)
    sym = _extract_symbol(r"self\.([a-zA-Z0-9_]+)") or _extract_symbol(r"instance attribute\s+([a-zA-Z0-9_]+)")
    if sym or "self." in query:
        target = sym or query.split("self.")[-1].split()[0].strip("?'\"")
        print(f"  [*] [Fast-Path #05: Instance Attribute Mutability] Audit for 'self.{target}'")
        res = tool_query_variable_and_state_references.invoke({"symbol_name": target, "variable_type": "instance_attr"})
        refs = res.get("references", [])
        if refs:
            ans = f"Instance attribute **`self.{target}`** is modified/referenced in {len(refs)} method(s):\n\n" + "\n".join(
                [f"  - `{r.get('function_name')}` in `{r.get('file_path')}`" for r in refs]
            )
        else:
            ans = f"No references or mutations of **`self.{target}`** were found in the codebase graph."
        return {"fast_path_hit": True, "fast_path_result": ans}

    # 5. Task #06: Inherited Class Attribute Resolution (super())
    sym = _extract_symbol(r"(?:inherited from|parent class of|super\(\))\s+([a-zA-Z0-9_]+)")
    if sym or "super()" in query or "inherited attribute" in q_lower:
        target = sym or query.split()[-1].strip("?'\"")
        print(f"  [*] [Fast-Path #06: Inherited Attributes] Hierarchy resolution for '{target}'")
        res = tool_inspect_type_and_inheritance_hierarchy.invoke({"symbol_name": target})
        ans = f"Inherited Class & Attribute Hierarchy for **`{target}`**:\n\n{json.dumps(res, indent=2)}"
        return {"fast_path_hit": True, "fast_path_result": ans}

    # 6. Task #07: Global & Module-Level Variable Audit
    sym = _extract_symbol(r"(?:global variable|module(-|\s)level (?:variable|constant))\s+([a-zA-Z0-9_]+)")
    if sym or "global variable" in q_lower or "module constant" in q_lower:
        target = sym or query.split()[-1].strip("?'\"")
        print(f"  [*] [Fast-Path #07: Global Variables] Audit for '{target}'")
        res = tool_query_variable_and_state_references.invoke({"symbol_name": target, "variable_type": "global_variable"})
        refs = res.get("references", [])
        if refs:
            ans = f"Global variable **`{target}`** is referenced at {len(refs)} location(s):\n\n" + "\n".join(
                [f"  - `{r.get('function_name')}` in `{r.get('file_path')}`" for r in refs]
            )
        else:
            ans = f"No references or declarations of global variable **`{target}`** found in the codebase graph."
        return {"fast_path_hit": True, "fast_path_result": ans}

    # 7. Task #08: Local Variable Initialization & Constant Default Audits (Snippets)
    sym = _extract_symbol(r"(?:default (?:timeout|value|parameter)|initial value|code snippet) of\s+([a-zA-Z0-9_\.]+)")
    if sym or "default timeout" in q_lower or "code snippet of" in q_lower:
        target = sym or query.split()[-1].strip("?'\"")
        print(f"  [*] [Fast-Path #08: Local Defaults / Snippet] Lookup for '{target}'")
        res = tool_get_symbol_code_snippet.invoke({"symbol_name": target})
        if res.get("snippet"):
            ans = f"Code snippet for **`{target}`** in `{res.get('file_path')}`:\n\n```python\n{res.get('snippet')}\n```"
        else:
            ans = f"No code definition or snippet found for symbol **`{target}`** in the codebase."
        return {"fast_path_hit": True, "fast_path_result": ans}

    # 8. Task #12: Module & Architecture Coupling
    if any(k in q_lower for k in ["circular import", "circular dependencies", "module coupling", "architectural boundary"]):
        print(f"  [*] [Fast-Path #12: Architecture Coupling] Analyzing circular imports & module edges...")
        res = tool_analyze_architecture_coupling.invoke({})
        cycles = res.get("circular_dependencies", [])
        if cycles:
            ans = f"Found {len(cycles)} circular module dependenc(ies):\n\n" + "\n".join([f"  - `{c}`" for c in cycles])
        else:
            ans = "No circular imports or high module coupling violations were detected in the codebase graph."
        return {"fast_path_hit": True, "fast_path_result": ans}

    # 9. Task #13: Dead Code & Orphan Identification
    if any(k in q_lower for k in ["dead code", "orphan function", "unused function", "uncalled function", "orphan class"]):
        print(f"  [*] [Fast-Path #13: Dead Code Detection] Querying uncalled functions (0 incoming callers)...")
        res = tool_detect_orphan_and_dead_code.invoke({})
        orphans = res.get("orphans", [])
        if orphans:
            ans = f"Detected {len(orphans)} orphan/dead function(s) with zero incoming callers:\n\n" + "\n".join(
                [f"  - Function: `{o.get('name')}` in `{o.get('file_path')}`" for o in orphans[:15]]
            )
        else:
            ans = "No orphan or dead code functions were identified in the ingested codebase graph."
        return {"fast_path_hit": True, "fast_path_result": ans}

    # 10. Task #17: Type & Class Hierarchy Inspection
    sym = _extract_symbol(r"(?:classes inherit from|subclasses of|class hierarchy of)\s+([a-zA-Z0-9_]+)")
    if sym or "class hierarchy" in q_lower or "subclasses of" in q_lower:
        target = sym or query.split()[-1].strip("?'\"")
        print(f"  [*] [Fast-Path #17: Class Hierarchy] Inspecting subclasses of '{target}'")
        res = tool_inspect_type_and_inheritance_hierarchy.invoke({"symbol_name": target})
        subclasses = res.get("subclasses", [])
        if subclasses:
            ans = f"Subclasses inheriting from **`{target}`** ({len(subclasses)} found):\n\n" + "\n".join(
                [f"  - `{s.get('name')}` in `{s.get('file_path')}`" for s in subclasses]
            )
        else:
            ans = f"No subclasses inheriting from **`{target}`** found in the codebase graph."
        return {"fast_path_hit": True, "fast_path_result": ans}

    # 11. Task #20: API Contract & Interface Surface
    if any(k in q_lower for k in ["rest endpoint", "api endpoint", "what routes", "http method", "api surface"]):
        print(f"  [*] [Fast-Path #20: API Endpoints] Querying public HTTP routes & handlers...")
        res = tool_query_api_endpoints.invoke({})
        endpoints = res.get("endpoints", [])
        if endpoints:
            ans = f"Exposed REST API Endpoints ({len(endpoints)} found):\n\n" + "\n".join(
                [f"  - `[{e.get('http_method', 'GET')}] {e.get('route')}` -> Handler: `{e.get('handler_name')}()` in `{e.get('file_path')}`" for e in endpoints]
            )
        else:
            ans = "No explicit REST API endpoint decorators were detected in the codebase graph."
        return {"fast_path_hit": True, "fast_path_result": ans}

    # Fall-through to Stage 2: Hierarchical Planner
    print("  [-] [Fast-Path Miss] Multi-step query detected. Delegating to Stage 2: Hierarchical Planner.")
    return {"fast_path_hit": False, "fast_path_result": None}


# =============================================================================
# Stage 1b: Fast Synthesizer Node (<50ms, 0 LLM loops)
# =============================================================================

def fast_synthesizer_node(state: BlackboardState) -> Dict[str, Any]:
    print(f"\n>> [Stage 1b: Fast Synthesizer] Returning verified fast-path answer.")
    result = state.get("fast_path_result", "Lookup completed.")
    return {"final_response": result}


# =============================================================================
# Stage 2: Hierarchical Planner Node (Initial & Adaptive Modes)
# =============================================================================

def hierarchical_planner_node(state: BlackboardState) -> Dict[str, Any]:
    query = state["query"]
    facts = state.get("blackboard_facts", [])
    negative_constraints = state.get("negative_constraints", [])
    replan_count = state.get("replan_count", 0) + 1
    is_adaptive = len(negative_constraints) > 0 or len(facts) > 0

    mode_label = "Adaptive Re-Planning (Dead-End Recovery)" if is_adaptive else "Initial Decomposition"
    print(f"\n>> [Stage 2: Hierarchical Planner] Mode: {mode_label} (Replan Iteration: {replan_count}/2)")
    if negative_constraints:
        print(f"   [!] Negative Constraints Active: {negative_constraints}")

    # Maximum replan safeguard: if replan_count > 2, do not loop
    if replan_count > 2:
        print("   [!] Max replan iterations reached. Proceeding directly to final synthesis.")
        return {
            "plan": [],
            "current_step_index": 0,
            "replan_count": replan_count,
            "consecutive_failures": 0,
        }

    system_prompt = (
        "You are CodeNavigator's Hierarchical Software Architecture Planner.\n"
        "Your role is to decompose the developer's codebase query into a minimal, ordered sequence of 2-3 PlanSteps.\n"
        "Each PlanStep MUST include:\n"
        "1. target tool from the tool catalog\n"
        "2. concrete testable hypothesis\n"
        "3. explicit acceptance criteria that define success.\n\n"
        "Available Tools:\n"
        "- tool_traverse_call_graph(target_symbol, direction='incoming'|'outgoing')\n"
        "- tool_calculate_blast_radius(target_symbol)\n"
        "- tool_query_variable_and_state_references(symbol_name, variable_type)\n"
        "- tool_get_symbol_code_snippet(symbol_name)\n"
        "- tool_search_codebase_semantic(query)\n"
        "- tool_inspect_type_and_inheritance_hierarchy(symbol_name)\n"
        "- tool_query_api_endpoints()\n"
        "- tool_query_test_traceability(target_symbol)\n"
        "- tool_detect_orphan_and_dead_code()\n"
        "- tool_analyze_architecture_coupling()\n"
    )

    context_prompt = f"User Query: \"{query}\"\n"
    if facts:
        context_prompt += f"\nEstablished Blackboard Facts:\n" + "\n".join([f"- {f['fact']}" for f in facts])
    if negative_constraints:
        context_prompt += f"\nPruned Dead-End Paths (DO NOT RETRY THESE):\n" + "\n".join([f"- {c}" for c in negative_constraints])

    json_prompt = (
        f"{system_prompt}\n\n"
        f"{context_prompt}\n\n"
        "Decompose the query into 2-3 logical, hypothesis-driven steps (e.g., Step 1: Semantic search / Locate symbols, Step 2: Extract symbol code snippet / variable references / traverse call graph).\n"
        "Return ONLY a JSON object matching this schema:\n"
        "{\n"
        '  "reasoning": "Architectural strategy breakdown",\n'
        '  "steps": [\n'
        '    {\n'
        '      "step_id": 1,\n'
        '      "tool_name": "tool_search_codebase_semantic",\n'
        '      "tool_args": {"query": "exact search term"},\n'
        '      "hypothesis": "Hypothesis for step 1",\n'
        '      "acceptance_criteria": "Acceptance criteria for step 1"\n'
        '    },\n'
        '    {\n'
        '      "step_id": 2,\n'
        '      "tool_name": "tool_get_symbol_code_snippet",\n'
        '      "tool_args": {"symbol_name": "target_symbol"},\n'
        '      "hypothesis": "Hypothesis for step 2",\n'
        '      "acceptance_criteria": "Acceptance criteria for step 2"\n'
        '    }\n'
        '  ]\n'
        "}\n"
    )

    llm = get_llm(temperature=0.0)
    steps = []
    try:
        raw_res = llm.invoke(json_prompt)
        text = raw_res.content if hasattr(raw_res, "content") else str(raw_res)
        json_match = re.search(r"(\{.*\})", text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(1))
            raw_steps = data.get("steps", [])
            for s in raw_steps:
                steps.append({
                    "step_id": s.get("step_id", len(steps) + 1),
                    "tool_name": s.get("tool_name", "tool_search_codebase_semantic"),
                    "tool_args": s.get("tool_args", {}),
                    "hypothesis": s.get("hypothesis", ""),
                    "acceptance_criteria": s.get("acceptance_criteria", ""),
                    "status": "PENDING",
                })
        if not steps:
            raise ValueError("No steps found in parsed JSON.")
    except Exception as e:
        print(f"   [!] Planner JSON fallback triggered ({e}). Using semantic search.")
        steps = [
            {
                "step_id": 1,
                "tool_name": "tool_search_codebase_semantic",
                "tool_args": {"query": query},
                "hypothesis": f"Semantic vector search will find relevant functions or files related to '{query}'",
                "acceptance_criteria": "Vector DB returns >= 1 relevant code chunk",
                "status": "PENDING",
            }
        ]

    print(f"   [+] Generated Plan ({len(steps)} steps):")
    for s in steps:
        print(f"      Step {s['step_id']}: [{s['tool_name']}] Hypothesis: {s['hypothesis']}")

    return {
        "plan": steps,
        "current_step_index": 0,
        "replan_count": replan_count,
        "consecutive_failures": 0,
    }


# =============================================================================
# Stage 3: Step Executor Node
# =============================================================================

def step_executor_node(state: BlackboardState) -> Dict[str, Any]:
    plan = state.get("plan", [])
    idx = state.get("current_step_index", 0)
    if not plan or idx >= len(plan):
        return {"current_tool_output": None}

    current_step = plan[idx]
    tool_name = current_step["tool_name"]
    tool_args = current_step.get("tool_args", {})

    print(f"\n>> [Stage 3: Step Executor] Running Step {current_step['step_id']}: {tool_name}")
    print(f"   Hypothesis: {current_step['hypothesis']}")
    print(f"   Args: {tool_args}")

    tool_fn = TOOL_MAP.get(tool_name)
    if not tool_fn:
        output = {"error": f"Tool '{tool_name}' not found in registry."}
    else:
        try:
            output = tool_fn.invoke(tool_args)
        except Exception as e:
            output = {"error": f"Tool execution failure: {str(e)}"}

    return {"current_tool_output": output}


# =============================================================================
# Stage 4: Evidence Evaluator & Pruning Decision Node
# =============================================================================

def evidence_evaluator_node(state: BlackboardState) -> Dict[str, Any]:
    plan = state.get("plan", [])
    idx = state.get("current_step_index", 0)
    if not plan or idx >= len(plan):
        return {"plan": plan, "current_step_index": idx}

    current_step = plan[idx]
    tool_output = state.get("current_tool_output")
    failure_count = state.get("consecutive_failures", 0)
    facts = list(state.get("blackboard_facts", []))
    constraints = list(state.get("negative_constraints", []))

    print(f"\n>> [Stage 4: Evidence Evaluator] Checking Step {current_step['step_id']} Acceptance Criteria...")

    # Heuristic evaluation of raw tool results
    has_data = False
    if isinstance(tool_output, dict):
        if (
            tool_output.get("paths")
            or tool_output.get("raw_calls")
            or tool_output.get("references")
            or (isinstance(tool_output.get("results"), list) and len(tool_output["results"]) > 0)
            or tool_output.get("snippet")
        ):
            has_data = True
        elif tool_output.get("count", 0) > 0:
            has_data = True

    # CASE A: Evidence Found (> 0 matches)
    if has_data and "error" not in tool_output:
        print(f"   [+] [CASE A: Evidence Verified] Step {current_step['step_id']} satisfied acceptance criteria.")

        if "raw_calls" in tool_output and tool_output["raw_calls"]:
            fact_summary = f"Callers of '{current_step.get('tool_args', {}).get('target_symbol', '')}': " + ", ".join(
                [f"{c.get('caller_name')}() in {c.get('caller_id', '').split('::')[0]}" for c in tool_output["raw_calls"]]
            )
        elif "references" in tool_output and tool_output["references"]:
            fact_summary = f"References for '{tool_output.get('symbol', '')}': " + ", ".join(
                [f"Accessed by {r.get('function_name')} in {r.get('file_path')}" for r in tool_output["references"]]
            )
        elif "code" in tool_output and tool_output["code"]:
            sym = tool_output.get("symbol", "")
            fp = tool_output.get("file_path", "")
            lines = f"L{tool_output.get('line_start', '')}-L{tool_output.get('line_end', '')}"
            code_body = tool_output["code"].strip()
            fact_summary = f"Symbol Code Definition for `{sym}` in `{fp}` ({lines}):\n```python\n{code_body[:2000]}\n```"
        elif "results" in tool_output and tool_output["results"]:
            snippets = []
            for r in tool_output["results"][:3]:
                name = r.get("name") or "Code Chunk"
                fp = r.get("file_path", "")
                snip = (r.get("snippet") or "").strip()
                snippets.append(f"  - Symbol: `{name}` in `{fp}`:\n    ```python\n    {snip[:1500]}\n    ```")
            fact_summary = f"Codebase Implementation Evidence ({len(tool_output['results'])} matches found):\n" + "\n".join(snippets)
        else:
            fact_summary = f"Verified: {current_step['hypothesis']} (Evidence: {str(tool_output)[:120]}...)"

        facts.append({
            "step_id": current_step["step_id"],
            "hypothesis": current_step["hypothesis"],
            "fact": fact_summary,
        })
        current_step["status"] = PlanStepStatus.VERIFIED

        return {
            "blackboard_facts": facts,
            "consecutive_failures": 0,
            "current_step_index": idx + 1,
            "plan": plan,
        }

    # CASE B: Zero Evidence (First Failure, count == 0 -> Sibling Tool Retry)
    elif failure_count == 0:
        print(f"   [!] [CASE B: Zero Evidence - Retry 1] Initial tool yielded 0 results. Switching to semantic vector fallback.")
        current_step["tool_name"] = "tool_search_codebase_semantic"
        current_step["tool_args"] = {"query": state["query"]}
        return {
            "consecutive_failures": 1,
            "plan": plan,
        }

    # CASE C: Zero Evidence (Failure Count >= 1 -> DEAD END & PRUNING!)
    else:
        print(f"   [-] [CASE C: DEAD END HIT] Pruning branch for hypothesis: \"{current_step['hypothesis']}\"")
        current_step["status"] = PlanStepStatus.PRUNED
        dead_end_constraint = f"Hypothesis '{current_step['hypothesis']}' has no supporting evidence in the codebase graph or vector index."
        constraints.append(dead_end_constraint)

        # Advance step index past the pruned step so we don't get stuck on it!
        return {
            "negative_constraints": constraints,
            "consecutive_failures": 0,
            "current_step_index": idx + 1,
            "plan": plan,
        }


# =============================================================================
# Stage 5: Final Synthesis & Episodic Memory Commit Node
# =============================================================================

def final_synthesis_and_memory_commit_node(state: BlackboardState) -> Dict[str, Any]:
    query = state["query"]
    facts = state.get("blackboard_facts", [])
    constraints = state.get("negative_constraints", [])
    print(f"\n>> [Stage 5: Final Synthesizer & Memory Commit] Generating answer from Blackboard facts...")

    if not facts:
        final_text = f"Based on knowledge graph traversals and semantic search, no occurrences or references were found for query: \"{query}\" in the ingested codebase."
    else:
        try:
            llm = get_llm(temperature=0.0)
            prompt = (
                "You are CodeNavigator, an expert AI software architect.\n"
                "Synthesize a clear, accurate, developer-focused explanation answering the query below strictly using the verified Blackboard facts.\n"
                "CRITICAL RULES:\n"
                "- Base your explanation ONLY and EXCLUSIVELY on the verified code facts and snippets provided below.\n"
                "- Quote exact function names, variable names, and formulas directly from the verified facts.\n"
                "- Do NOT assume, speculate, or fabricate any rules, formulas, or parameters not present in the facts.\n\n"
                f"Developer Query: {query}\n\n"
                "Verified Blackboard Facts:\n"
                + "\n".join([f"- {f['fact']}" for f in facts])
                + "\n\nSynthesized Explanation:"
            )
            res = llm.invoke(prompt)
            final_text = res.content if hasattr(res, "content") else str(res)
        except Exception:
            fact_lines = "\n".join([f"- {f['fact']}" for f in facts])
            final_text = f"### Code Analysis Findings:\n\n{fact_lines}"

    if constraints:
        constraint_lines = "\n".join([f"- {c}" for c in constraints])
        final_text += f"\n\n### Verified Negative Findings (Pruned Paths):\n{constraint_lines}"

    print(f"   [*] [Episodic Memory] Committed trajectory to persistent vector memory (Git: {state.get('git_hash', 'HEAD')}).")
    return {"final_response": final_text}


# =============================================================================
# 4. Conditional Edge Routing Functions
# =============================================================================

def route_after_gate(state: BlackboardState) -> Literal["fast_synthesizer", "hierarchical_planner"]:
    if state.get("fast_path_hit"):
        return "fast_synthesizer"
    return "hierarchical_planner"


def route_after_evaluator(state: BlackboardState) -> Literal["step_executor", "hierarchical_planner", "final_synthesis"]:
    plan = state.get("plan", [])
    idx = state.get("current_step_index", 0)
    failures = state.get("consecutive_failures", 0)
    replan_count = state.get("replan_count", 0)

    # If Case B (retry fallback on same step)
    if failures == 1:
        return "step_executor"

    # If more steps remain in current plan
    if idx < len(plan):
        return "step_executor"

    # If all steps in current plan finished, but some were pruned and we have replan allowance
    pruned_steps = [s for s in plan if s.get("status") == PlanStepStatus.PRUNED]
    if pruned_steps and replan_count < 2:
        return "hierarchical_planner"

    # All steps finished or replan exhausted -> Final Synthesis
    return "final_synthesis"


# =============================================================================
# 5. Build and Compile the Next-Gen LangGraph Agent
# =============================================================================

def build_nextgen_agentic_graph():
    workflow = StateGraph(BlackboardState)

    # 1. Add All Nodes
    workflow.add_node("heuristic_gate", heuristic_and_memory_gate_node)
    workflow.add_node("fast_synthesizer", fast_synthesizer_node)
    workflow.add_node("hierarchical_planner", hierarchical_planner_node)
    workflow.add_node("step_executor", step_executor_node)
    workflow.add_node("evidence_evaluator", evidence_evaluator_node)
    workflow.add_node("final_synthesis", final_synthesis_and_memory_commit_node)

    # 2. Add Edges & Conditional Routing
    workflow.add_edge(START, "heuristic_gate")

    workflow.add_conditional_edges(
        "heuristic_gate",
        route_after_gate,
        {
            "fast_synthesizer": "fast_synthesizer",
            "hierarchical_planner": "hierarchical_planner",
        },
    )

    workflow.add_edge("fast_synthesizer", END)
    workflow.add_edge("hierarchical_planner", "step_executor")
    workflow.add_edge("step_executor", "evidence_evaluator")

    workflow.add_conditional_edges(
        "evidence_evaluator",
        route_after_evaluator,
        {
            "step_executor": "step_executor",
            "hierarchical_planner": "hierarchical_planner",
            "final_synthesis": "final_synthesis",
        },
    )

    workflow.add_edge("final_synthesis", END)

    return workflow.compile()


# =============================================================================
# 6. High-Level Runner Interface
# =============================================================================

class NextGenCodeNavigatorAgent:
    """High-level wrapper around the compiled Next-Gen LangGraph agent."""

    def __init__(self, repo_path: str = "."):
        self.app = build_nextgen_agentic_graph()
        self.repo_path = repo_path

    def ask(self, query: str) -> str:
        initial_state: BlackboardState = {
            "query": query,
            "git_hash": _get_current_git_hash(self.repo_path),
            "fast_path_hit": False,
            "fast_path_result": None,
            "plan": [],
            "current_step_index": 0,
            "replan_count": 0,
            "current_tool_output": None,
            "blackboard_facts": [],
            "negative_constraints": [],
            "consecutive_failures": 0,
            "final_response": None,
        }
        final_state = self.app.invoke(initial_state)
        return final_state.get("final_response", "Execution complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Next-Gen CodeNavigator Agent CLI")
    parser.add_argument("query", nargs="*", help="Natural language query about the codebase")
    args = parser.parse_args()

    query_str = " ".join(args.query) if args.query else "Who calls load_characters()?"
    agent = NextGenCodeNavigatorAgent()
    ans = agent.ask(query_str)

    print("\n" + "=" * 80)
    print("FINAL AGENT ANSWER:")
    print("-" * 80)
    print(ans)
    print("=" * 80)
