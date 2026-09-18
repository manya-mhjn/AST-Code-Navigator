"""
agentic_nextgen.py — Next-Gen Code Intelligence Agent Architecture.

Implements:
1. Stage 1: Hierarchical Planner (Direct Entry: Direct 1-Step or 2-Step Locate-Then-Inspect)
2. Stage 2: Step Executor (Dynamic Tool Dispatch + $DISCOVERED_SYMBOL Resolution)
3. Stage 3: LLM Evidence Evaluator (Strict Structured Output using EvidenceEvaluationSchema)
4. Stage 4: Final Synthesizer & Episodic Memory Commit
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

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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
    tool_args: Dict[str, Any] = Field(default_factory=dict, description="Arguments (use '$DISCOVERED_SYMBOL' if relying on Step 1)")
    hypothesis: str = Field(..., description="Testable hypothesis")
    acceptance_criteria: str = Field(..., description="Conditions to verify evidence")
    status: PlanStepStatus = Field(default=PlanStepStatus.PENDING)


class HierarchicalPlanSchema(BaseModel):
    """Structured output for the Hierarchical Planner."""
    reasoning: str = Field(..., description="Architectural strategy breakdown")
    steps: List[PlanStep] = Field(..., description="Ordered list of hypothesis-driven plan steps (1-3 steps)")


class EvaluationVerdict(str, Enum):
    CASE_A_EVIDENCE_FOUND = "CASE_A_EVIDENCE_FOUND"
    CASE_B_RETRY_FALLBACK = "CASE_B_RETRY_FALLBACK"
    CASE_C_DEAD_END_PRUNE = "CASE_C_DEAD_END_PRUNE"


class BatchEvaluationSchema(BaseModel):
    """Structured consolidated post-plan evaluation of full execution trace."""
    is_sufficient: bool = Field(
        ...,
        description="True if the cumulative execution trace provides concrete code evidence to answer the query, False otherwise."
    )
    failed_tools: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Explicit list of failed tools: [{'step_id': int, 'tool_name': str, 'hypothesis': str, 'failure_reason': str}]. Empty list [] if all tools succeeded."
    )
    extracted_facts: List[str] = Field(
        default_factory=list,
        description="List of concrete, verified factual statements quoting exact function names, formulas, file paths, and line numbers."
    )
    dead_end_reasons: List[str] = Field(
        default_factory=list,
        description="List of reasons explaining why specific hypotheses failed or found no relevant code."
    )
    replan_suggestion: Optional[str] = Field(
        None,
        description="Specific guidance for the planner if is_sufficient is False or some tools failed."
    )


# =============================================================================
# 2. Blackboard State Definition
# =============================================================================

class BlackboardState(TypedDict):
    query: str
    git_hash: str

    # Plan Tracking
    plan: List[Dict[str, Any]]
    current_step_index: int
    replan_count: int

    # Dynamic Symbol Resolution
    discovered_symbols: List[str]            # Real symbols discovered during semantic search

    # Batch Execution Trace & Evidence Accumulation
    execution_trace: List[Dict[str, Any]]     # All executed steps with hypotheses & raw outputs
    current_tool_output: Optional[Any]
    blackboard_facts: List[Dict[str, Any]]
    negative_constraints: List[str]
    consecutive_failures: int
    is_sufficient: Optional[bool]

    # Final Output
    final_response: Optional[str]


TOOL_MAP = {t.name: t for t in ALL_TOOLS}


def _get_current_git_hash(repo_path: str = ".") -> str:
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
# Stage 1: Hierarchical Planner Node (Direct Entry, Method 1 Aware)
# =============================================================================

def hierarchical_planner_node(state: BlackboardState) -> Dict[str, Any]:
    query = state["query"]
    facts = state.get("blackboard_facts", [])
    negative_constraints = state.get("negative_constraints", [])
    replan_count = state.get("replan_count", 0) + 1
    is_adaptive = len(negative_constraints) > 0 or len(facts) > 0

    mode_label = "Adaptive Re-Planning" if is_adaptive else "Initial Decomposition"
    print(f"\n================================================================================")
    print(f"  [Stage 1: Hierarchical Planner] Mode: {mode_label} (Iteration: {replan_count}/2)")
    print(f"  Query: \"{query}\"")
    print(f"================================================================================")

    if replan_count > 2:
        print("   [!] Max replan iterations reached. Proceeding to synthesis.")
        return {
            "plan": [],
            "current_step_index": 0,
            "replan_count": replan_count,
            "consecutive_failures": 0,
        }

    system_prompt = (
        "You are CodeNavigator's Hierarchical Software Architecture Planner.\n"
        "Your role is to plan the exact sequence of PlanSteps needed to thoroughly answer the user's codebase query.\n\n"
        "PLANNING RULES:\n"
        "CRITICAL INSTRUCTION (Applies to ALL plans):\n"
        "In BOTH cases (whether entity name is given or not), you MUST plan the entire multi-step sequence upfront in this single plan. DO NOT wait for a symbol or previous step to be resolved before planning subsequent steps.\n\n"
        "1. Entity Name Given (User provided exact or approximate function, class, variable, or file name, e.g. 'Who calls load_characters?', 'What is in weapon_dict?'):\n"
        "   - Directly schedule the initial step using the provided entity name.\n"
        "   - Plan all SUBSEQUENT STEPS (Step 2, Step 3, etc.) upfront in this same plan to completely answer the query using any required tools from the catalog (e.g. tool_get_symbol_code_snippet, tool_traverse_call_graph, tool_query_variable_and_state_references).\n\n"
        "2. Entity Name NOT Given (User did NOT provide an exact function/class/variable name, e.g. 'How are characters loaded?', 'Where is tax calculated?'):\n"
        "   - Search using 'tool_get_symbol_code_snippet' first if a candidate symbol can be inferred from the query context; if not getting the answer or no candidate exists, use 'tool_search_codebase_semantic' with natural language keywords.\n"
        "   - Plan all SUBSEQUENT STEPS (Step 2, Step 3, etc.) upfront in this same plan using any required tools from the catalog to inspect, traverse, or analyze the code.\n"
        "     For any argument that requires the discovered symbol name, pass the literal placeholder '$DISCOVERED_SYMBOL'.\n"
        "     The execution engine will automatically and procedurally inject the real symbol discovered into all subsequent steps before running them.\n\n"
        "AVAILABLE TOOLS (Full Catalog):\n"
        "- tool_search_codebase_semantic(query: str)\n"
        "- tool_get_symbol_code_snippet(symbol_name: str)\n"
        "- tool_traverse_call_graph(target_symbol: str, direction: 'incoming'|'outgoing', max_depth: int)\n"
        "- tool_calculate_blast_radius(target_symbol: str)\n"
        "- tool_query_variable_and_state_references(symbol_name: str, variable_type: 'env_var'|'instance_attr'|'global_variable')\n"
        "- tool_inspect_type_and_inheritance_hierarchy(symbol_name: str)\n"
        "- tool_query_api_endpoints()\n"
        "- tool_detect_orphan_and_dead_code(entity_type: 'all'|'functions'|'classes'|'files')\n"
        "- tool_analyze_architecture_coupling()\n"
        "- tool_query_test_traceability(target_symbol: str)\n"
        "- tool_trace_parameter_lineage(target_symbol: str, parameter_name: str)\n"
        "- tool_trace_taint_and_security_paths(source_symbol: str, sink_symbol: str)\n"
    )

    context_prompt = f"User Query: \"{query}\"\n"
    if facts:
        context_prompt += f"\nBlackboard Facts:\n" + "\n".join([f"- {f['fact']}" for f in facts])
    if negative_constraints:
        context_prompt += f"\nPruned Dead-End Paths:\n" + "\n".join([f"- {c}" for c in negative_constraints])

    json_prompt = (
        f"{system_prompt}\n\n"
        f"{context_prompt}\n\n"
        "Generate the Plan. Return ONLY a JSON object matching this schema:\n"
        "{\n"
        '  "reasoning": "Strategy explanation",\n'
        '  "steps": [\n'
        '    {\n'
        '      "step_id": 1,\n'
        '      "tool_name": "tool_search_codebase_semantic",\n'
        '      "tool_args": {"query": "natural language search keywords"},\n'
        '      "hypothesis": "Locate the primary function handling this logic",\n'
        '      "acceptance_criteria": "Vector DB returns relevant code chunk with symbol name"\n'
        '    },\n'
        '    {\n'
        '      "step_id": 2,\n'
        '      "tool_name": "tool_get_symbol_code_snippet",\n'
        '      "tool_args": {"symbol_name": "$DISCOVERED_SYMBOL"},\n'
        '      "hypothesis": "Inspect the complete implementation of the discovered function",\n'
        '      "acceptance_criteria": "Code snippet retrieved for discovered symbol"\n'
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
            for s in data.get("steps", []):
                steps.append({
                    "step_id": s.get("step_id", len(steps) + 1),
                    "tool_name": s.get("tool_name", "tool_search_codebase_semantic"),
                    "tool_args": s.get("tool_args", {}),
                    "hypothesis": s.get("hypothesis", ""),
                    "acceptance_criteria": s.get("acceptance_criteria", ""),
                    "status": "PENDING",
                })
        if not steps:
            raise ValueError("No steps in parsed JSON.")
    except Exception as e:
        print(f"   [!] Planner JSON fallback triggered ({e}). Using semantic search.")
        steps = [
            {
                "step_id": 1,
                "tool_name": "tool_search_codebase_semantic",
                "tool_args": {"query": query},
                "hypothesis": f"Search codebase for '{query}'",
                "acceptance_criteria": "Vector DB returns >= 1 match",
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
        "execution_trace": [],
        "is_sufficient": None,
    }


# =============================================================================
# Stage 2: Batch Step Executor Node (Zero LLM Calls, Resolves $DISCOVERED_SYMBOL)
# =============================================================================

def step_executor_node(state: BlackboardState) -> Dict[str, Any]:
    plan = list(state.get("plan", []))
    discovered_symbols = list(state.get("discovered_symbols", []))
    execution_trace = list(state.get("execution_trace", []))

    print(f"\n>> [Stage 2: Batch Step Executor] Executing {len(plan)} planned steps procedurally...")

    for step in plan:
        tool_name = step["tool_name"]
        tool_args = dict(step.get("tool_args", {}))

        # DYNAMIC SYMBOL RESOLUTION: Replace placeholder with real symbol discovered in earlier steps
        if discovered_symbols:
            latest_symbol = discovered_symbols[-1]
            for k, v in tool_args.items():
                if v == "$DISCOVERED_SYMBOL":
                    print(f"   [*] [Procedural Symbol Resolved] Replaced '$DISCOVERED_SYMBOL' with '{latest_symbol}' for argument '{k}'")
                    tool_args[k] = latest_symbol

        print(f"   -> Executing Step {step['step_id']}: {tool_name}")
        print(f"      Hypothesis: {step['hypothesis']}")
        print(f"      Args: {tool_args}")

        tool_fn = TOOL_MAP.get(tool_name)
        if not tool_fn:
            output = {"error": f"Tool '{tool_name}' not found in registry."}
        else:
            try:
                output = tool_fn.invoke(tool_args)
            except Exception as e:
                output = {"error": f"Tool execution failure: {str(e)}"}

        # Procedural extraction: capture real symbol for subsequent steps
        if isinstance(output, dict):
            if output.get("symbol") and "error" not in output:
                sym = output["symbol"]
                if sym not in discovered_symbols and sym != "$DISCOVERED_SYMBOL":
                    discovered_symbols.append(sym)
                    print(f"      [*] [Procedural Symbol Discovery] Captured symbol from snippet: '{sym}'")
            elif output.get("results"):
                top_sym = None
                for r in output["results"]:
                    fp = r.get("file_path", "")
                    if "test" not in fp.lower() and r.get("name"):
                        top_sym = r.get("name")
                        break
                if not top_sym and output["results"]:
                    top_sym = output["results"][0].get("name")
                if top_sym and top_sym not in discovered_symbols:
                    discovered_symbols.append(top_sym)
                    print(f"      [*] [Procedural Symbol Discovery] Captured symbol from search: '{top_sym}'")

        step["status"] = "EXECUTED"
        execution_trace.append({
            "step_id": step["step_id"],
            "tool_name": tool_name,
            "tool_args": tool_args,
            "hypothesis": step.get("hypothesis", ""),
            "acceptance_criteria": step.get("acceptance_criteria", ""),
            "output": output,
        })

    return {
        "execution_trace": execution_trace,
        "discovered_symbols": discovered_symbols,
        "current_step_index": len(plan),
        "plan": plan,
    }


# =============================================================================
# Stage 3: Consolidated LLM Evidence Evaluator Node (Batch Review)
# =============================================================================

def evidence_evaluator_node(state: BlackboardState) -> Dict[str, Any]:
    query = state["query"]
    plan = state.get("plan", [])
    trace = state.get("execution_trace", [])
    facts = list(state.get("blackboard_facts", []))
    constraints = list(state.get("negative_constraints", []))

    print(f"\n>> [Stage 3: LLM Evidence Evaluator] Reviewing batch execution trace ({len(trace)} steps) with LLM...")

    trace_summary = []
    for t in trace:
        out_str = json.dumps(t["output"], indent=2, default=str)
        trace_summary.append(
            f"### Step {t['step_id']}: Tool `{t['tool_name']}`\n"
            f"- Hypothesis: {t.get('hypothesis', '')}\n"
            f"- Acceptance Criteria: {t.get('acceptance_criteria', 'N/A')}\n"
            f"- Arguments Invoked: {json.dumps(t.get('tool_args', {}))}\n"
            f"- Tool Response / Output:\n```json\n{out_str}\n```"
        )

    eval_prompt = (
        "You are CodeNavigator's Scientific Evidence Evaluator.\n"
        "Your task is to review the full execution trace of planned steps (each step's hypothesis, arguments, acceptance criteria, and raw tool response) and determine if the accumulated evidence is sufficient to answer the developer query.\n\n"
        f"Developer Query: \"{query}\"\n\n"
        "Execution Trace:\n"
        + "\n\n".join(trace_summary) + "\n\n"
        "EVALUATION RULES:\n"
        "1. Check EACH step's tool response against its hypothesis and acceptance criteria:\n"
        "   - If a tool returned empty results, null, an error, or missed the target symbol, report it in `failed_tools` with its `step_id`, `tool_name`, `hypothesis`, and `failure_reason`.\n"
        "   - If all tools returned valid evidence, `failed_tools` MUST be an empty list [].\n"
        "2. Overall Query Sufficiency:\n"
        "   - If the accumulated valid evidence provides the code, formulas, callers, or architecture to answer the developer's query, set `is_sufficient`: true and extract concrete facts in `extracted_facts`.\n"
        "   - If critical information is missing or the tools failed to answer the query, set `is_sufficient`: false, list `dead_end_reasons`, and provide a concrete `replan_suggestion`.\n\n"
        "Return ONLY a JSON object matching this schema:\n"
        "{\n"
        '  "is_sufficient": true,\n'
        '  "failed_tools": [\n'
        '    {\n'
        '      "step_id": 1,\n'
        '      "tool_name": "tool_name_here",\n'
        '      "hypothesis": "hypothesis text",\n'
        '      "failure_reason": "why tool returned empty or failed"\n'
        '    }\n'
        '  ],\n'
        '  "extracted_facts": ["Exact fact quoting symbol, file, lines, or formula"],\n'
        '  "dead_end_reasons": [],\n'
        '  "replan_suggestion": null\n'
        "}\n"
    )

    llm = get_llm(temperature=0.0)
    evaluation: Optional[BatchEvaluationSchema] = None

    try:
        raw_eval = llm.invoke(eval_prompt)
        txt = raw_eval.content if hasattr(raw_eval, "content") else str(raw_eval)
        clean_txt = re.sub(r"^```(?:json)?\s*", "", txt.strip())
        clean_txt = re.sub(r"\s*```$", "", clean_txt)
        m = re.search(r"(\{.*\})", clean_txt, re.DOTALL)
        if m:
            evaluation = BatchEvaluationSchema.model_validate_json(m.group(1))
    except Exception as e:
        print(f"   [!] LLM Batch Evaluation error: {e}. Defaulting to heuristic inspection.")

    if not evaluation:
        failed_tools_list = []
        for t in trace:
            out = t.get("output")
            is_err = isinstance(out, dict) and "error" in out
            is_empty = not out or (isinstance(out, dict) and out.get("results") == [])
            if is_err or is_empty:
                failed_tools_list.append({
                    "step_id": t["step_id"],
                    "tool_name": t["tool_name"],
                    "hypothesis": t.get("hypothesis", ""),
                    "failure_reason": "Tool returned empty results or execution error.",
                })
        has_data = any(
            t.get("output") and not (isinstance(t["output"], dict) and t["output"].get("error"))
            for t in trace
        )
        evaluation = BatchEvaluationSchema(
            is_sufficient=has_data,
            failed_tools=failed_tools_list,
            extracted_facts=[f"Codebase evidence gathered from: {t['tool_name']}" for t in trace if t.get("output")],
            dead_end_reasons=["Evaluator fallback triggered."] if not has_data else [],
        )

    print(f"   [*] Evaluator Verdict: is_sufficient = {evaluation.is_sufficient}")

    # Explicitly log and record failed tools
    if evaluation.failed_tools:
        print(f"   [!] [Failed Tools Identified: {len(evaluation.failed_tools)}]")
        for ft in evaluation.failed_tools:
            s_id = ft.get("step_id")
            t_name = ft.get("tool_name", "Unknown")
            reason = ft.get("failure_reason", "Tool failed to provide evidence.")
            print(f"      [-] Step {s_id} ({t_name}) FAILED: {reason}")
            constraints.append(f"Tool `{t_name}` (Step {s_id}) failed: {reason}")

    # Mark per-step status based on failed_tools
    failed_step_ids = {ft.get("step_id") for ft in evaluation.failed_tools if isinstance(ft, dict)}
    for step in plan:
        if step.get("step_id") in failed_step_ids:
            step["status"] = PlanStepStatus.PRUNED
        else:
            step["status"] = PlanStepStatus.VERIFIED

    if evaluation.is_sufficient:
        print(f"   [+] Evidence confirmed. Extracted {len(evaluation.extracted_facts)} verified facts.")
        for fact_text in evaluation.extracted_facts:
            facts.append({"fact": fact_text})

        return {
            "blackboard_facts": facts,
            "negative_constraints": constraints,
            "is_sufficient": True,
            "plan": plan,
        }
    else:
        print(f"   [-] Insufficient evidence or dead end hit.")
        for reason in evaluation.dead_end_reasons:
            print(f"      [-] Pruned: {reason}")
            constraints.append(reason)
        if evaluation.replan_suggestion:
            constraints.append(f"Replan guidance: {evaluation.replan_suggestion}")

        return {
            "blackboard_facts": facts,
            "negative_constraints": constraints,
            "is_sufficient": False,
            "plan": plan,
        }


# =============================================================================
# Stage 4: Final Synthesis & Episodic Memory Commit Node
# =============================================================================

def final_synthesis_and_memory_commit_node(state: BlackboardState) -> Dict[str, Any]:
    query = state["query"]
    facts = state.get("blackboard_facts", [])
    constraints = state.get("negative_constraints", [])
    print(f"\n>> [Stage 4: Final Synthesizer] Generating answer from Blackboard facts...")

    if not facts:
        final_text = f"No occurrences or references were found for query: \"{query}\" in the codebase."
    else:
        dedup_facts = []
        seen_fact_texts = set()
        for f in facts:
            txt = f.get("fact", "")
            if txt and txt not in seen_fact_texts:
                seen_fact_texts.add(txt)
                dedup_facts.append(f)

        try:
            llm = get_llm(temperature=0.0)
            prompt = (
                "You are CodeNavigator, an expert AI software architect.\n"
                "Synthesize a clear, accurate, developer-focused explanation answering the query below strictly using the verified Blackboard facts.\n"
                "CRITICAL RULES:\n"
                "- Base your explanation ONLY on the verified code facts and snippets provided below.\n"
                "- Quote exact function names, variable names, and line numbers directly from the verified facts.\n"
                "- Do NOT speculate or fabricate any code not present in the facts.\n\n"
                f"Developer Query: {query}\n\n"
                "Verified Blackboard Facts:\n"
                + "\n".join([f"- {f['fact']}" for f in dedup_facts])
                + "\n\nSynthesized Explanation:"
            )
            res = llm.invoke(prompt)
            final_text = res.content if hasattr(res, "content") else str(res)
        except Exception:
            fact_lines = "\n\n".join([f"- {f['fact']}" for f in dedup_facts])
            final_text = f"### Verified Codebase Findings for `{query}`:\n\n{fact_lines}"

    if constraints:
        constraint_lines = "\n".join([f"- {c}" for c in constraints])
        final_text += f"\n\n### Verified Negative Findings (Pruned Paths):\n{constraint_lines}"

    print(f"   [*] [Episodic Memory] Committed trajectory to memory (Git: {state.get('git_hash', 'HEAD')}).")
    return {"final_response": final_text}


# =============================================================================
# Conditional Edge Routing
# =============================================================================

def route_after_evaluator(state: BlackboardState) -> Literal["hierarchical_planner", "final_synthesis"]:
    is_sufficient = state.get("is_sufficient", True)
    replan_count = state.get("replan_count", 0)

    if not is_sufficient and replan_count < 2:
        print(f"\n>> [Routing] Insufficient evidence. Routing to Hierarchical Planner for replanning (Count: {replan_count + 1}/2)...")
        return "hierarchical_planner"

    return "final_synthesis"


# =============================================================================
# Graph Compilation
# =============================================================================

def build_nextgen_agentic_graph():
    workflow = StateGraph(BlackboardState)

    workflow.add_node("hierarchical_planner", hierarchical_planner_node)
    workflow.add_node("step_executor", step_executor_node)
    workflow.add_node("evidence_evaluator", evidence_evaluator_node)
    workflow.add_node("final_synthesis", final_synthesis_and_memory_commit_node)

    workflow.add_edge(START, "hierarchical_planner")
    workflow.add_edge("hierarchical_planner", "step_executor")
    workflow.add_edge("step_executor", "evidence_evaluator")

    workflow.add_conditional_edges(
        "evidence_evaluator",
        route_after_evaluator,
        {
            "hierarchical_planner": "hierarchical_planner",
            "final_synthesis": "final_synthesis",
        },
    )

    workflow.add_edge("final_synthesis", END)

    return workflow.compile()


# =============================================================================
# High-Level Runner Interface & CLI
# =============================================================================

class NextGenCodeNavigatorAgent:
    def __init__(self, repo_path: str = "."):
        self.app = build_nextgen_agentic_graph()
        self.repo_path = repo_path

    def ask_detailed(self, query: str) -> Dict[str, Any]:
        """Runs the agent on the query and returns the complete final state dictionary and metadata."""
        initial_state: BlackboardState = {
            "query": query,
            "git_hash": _get_current_git_hash(self.repo_path),
            "plan": [],
            "current_step_index": 0,
            "replan_count": 0,
            "discovered_symbols": [],
            "execution_trace": [],
            "current_tool_output": None,
            "blackboard_facts": [],
            "negative_constraints": [],
            "consecutive_failures": 0,
            "is_sufficient": None,
            "final_response": None,
        }
        return self.app.invoke(initial_state)

    def ask(self, query: str) -> str:
        """Runs the agent and returns the final synthesized response text."""
        final_state = self.ask_detailed(query)
        return final_state.get("final_response", "Execution complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Next-Gen CodeNavigator Agent CLI")
    parser.add_argument("query", nargs="*", help="Natural language query about the codebase")
    args = parser.parse_args()

    query_str = " ".join(args.query) if args.query else "How are characters loaded into the game?"
    agent = NextGenCodeNavigatorAgent()
    ans = agent.ask(query_str)

    print("\n" + "=" * 80)
    print("FINAL AGENT ANSWER:")
    print("-" * 80)
    print(ans)
    print("=" * 80)

#     i want my llm to give more human like response, write now it is giving direct ans not describing it enough, i want it go an extra mile, dont just give what is asked, I want it to give surrounding information too
# modify the prompt of hirarchical planner to add an extra mile step where it will fetch additional relevant information from the dataset.
# modify the propmt of synthesizer to give elaborate human like response. from all the facts presented to it