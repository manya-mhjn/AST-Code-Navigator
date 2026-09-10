"""
agentic.py — LangGraph-based Multi-Tier Agent Orchestrator for CodeNavigator.

Dispatches developer queries across 3 execution tiers:
  - DETERMINISTIC_1_SHOT (1-Turn Atomic/Composite execution)
  - GUIDED_RECIPE (Branching 2-3 Turn recipe execution)
  - REACT_FALLBACK (Open-ended exploratory ReAct loop)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Annotated, Any, Dict, List, Optional, TypedDict

# Ensure repository root is on sys.path
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from dotenv import load_dotenv

load_dotenv(override=True)

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from pipeline.tools import (
    ALL_TOOLS,
    classify_intent,
    tool_analyze_architecture_coupling,
    tool_calculate_blast_radius,
    tool_classify_intent,
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
from pipeline.tools_utils import ExecutionStrategy
from pipeline.utils import get_llm


# -----------------------------------------------------------------------------
# LangGraph Agent State Definition
# -----------------------------------------------------------------------------

class CodeNavigatorAgentState(TypedDict):
    query: str
    messages: Annotated[List[BaseMessage], add_messages]
    intent: Optional[Dict[str, Any]]
    strategy: Optional[str]
    task_id: Optional[int]
    task_name: Optional[str]
    target_symbols: List[str]
    recommended_tools: List[str]
    allowed_tools: List[str]
    workflow_recipe: Optional[str]
    tool_output: Optional[Dict[str, Any]]
    final_summary: Optional[str]


# -----------------------------------------------------------------------------
# LangGraph Nodes
# -----------------------------------------------------------------------------

def classifier_node(state: CodeNavigatorAgentState) -> Dict[str, Any]:
    """Node 1: Evaluates user query intent using the Intent Classifier Tool."""
    query = state["query"]
    print("\n" + "=" * 80)
    print(f"  [LangGraph Node: Classifier] Analyzing: \"{query}\"")
    print("=" * 80)

    intent = classify_intent(query)
    strategy = intent["strategy"]
    task_id = intent.get("task_id")
    task_name = intent.get("task_name")
    turns = intent.get("expected_turns")
    symbols = intent.get("target_symbols", [])

    print(f"\n[Intent Routing Decision]")
    print(f"  * Task: #{task_id} ({task_name})")
    print(f"  * Strategy: {strategy} (Expected Turns: {turns})")
    print(f"  * Extracted Symbols: {symbols}")
    print(f"  * Recommended Tools: {intent['recommended_tools']}")

    return {
        "intent": intent,
        "strategy": strategy,
        "task_id": task_id,
        "task_name": task_name,
        "target_symbols": symbols,
        "recommended_tools": intent["recommended_tools"],
        "allowed_tools": intent["allowed_tools"],
        "workflow_recipe": intent.get("workflow_recipe"),
    }


def deterministic_1_shot_node(state: CodeNavigatorAgentState) -> Dict[str, Any]:
    """Node 2A: Executes 1-shot deterministic tools (Atomic and Composite)."""
    task_id = state.get("task_id")
    symbols = state.get("target_symbols", [])
    primary_tool = state["recommended_tools"][0] if state.get("recommended_tools") else None

    print(f"\n>> [LangGraph Node: Deterministic 1-Shot Execution]")

    try:
        # Task #1 & #2: Call Graph Traversals
        if task_id in (1, 2) and symbols:
            direction = "incoming" if task_id == 1 else "outgoing"
            print(f"   Executing Call Graph Traversal on '{symbols[0]}' ({direction})...")
            res = tool_traverse_call_graph.invoke({
                "target_symbol": symbols[0],
                "direction": direction,
                "max_depth": 3,
            })
            return {"tool_output": res}

        # Task #3: Blast Radius
        elif task_id == 3 and symbols:
            print(f"   Executing Blast Radius calculation on {symbols}...")
            res = tool_calculate_blast_radius.invoke({"changed_symbols": symbols})
            return {"tool_output": res}

        # Task #4: Parameter Lineage
        elif task_id == 4 and len(symbols) >= 2:
            print(f"   Executing Parameter Lineage on function '{symbols[0]}', param '{symbols[1]}'...")
            res = tool_trace_parameter_lineage.invoke({
                "function_name": symbols[0],
                "parameter_name": symbols[1],
            })
            return {"tool_output": res}

        # Task #5, #7, #9, #11: State & Variable References
        elif task_id in (5, 7, 9, 11) and symbols:
            vtype = "env_var" if task_id == 9 else ("instance_attr" if task_id == 5 else "global")
            print(f"   Executing Variable References Query on '{symbols[0]}' (type: {vtype})...")
            res = tool_query_variable_and_state_references.invoke({
                "symbol_name": symbols[0],
                "variable_type": vtype,
            })
            return {"tool_output": res}

        # Task #6, #17: Class Hierarchy
        elif task_id in (6, 17) and symbols:
            print(f"   Executing Inheritance Hierarchy on class '{symbols[0]}'...")
            res = tool_inspect_type_and_inheritance_hierarchy.invoke({
                "class_symbol": symbols[0],
                "direction": "both",
            })
            return {"tool_output": res}

        # Task #8, #10, #15, #18: Symbol Code Snippets
        elif task_id in (8, 10, 15, 18) and symbols:
            print(f"   Executing Code Snippet Retrieval for '{symbols[0]}'...")
            res = tool_get_symbol_code_snippet.invoke({"symbol_name": symbols[0]})
            return {"tool_output": res}

        # Task #12: Architecture Coupling
        elif task_id == 12:
            print("   Executing Module Coupling & Circular Dependency Detection...")
            res = tool_analyze_architecture_coupling.invoke({})
            return {"tool_output": res}

        # Task #13: Dead Code & Orphan Detection
        elif task_id == 13:
            print("   Executing Dead Code & Orphan Node Detection...")
            res = tool_detect_orphan_and_dead_code.invoke({})
            return {"tool_output": res}

        # Task #14: Security Taint Paths
        elif task_id == 14:
            src = symbols[0] if symbols else "request"
            print(f"   Executing Security Taint Path Tracking for source '{src}'...")
            res = tool_trace_taint_and_security_paths.invoke({"source_pattern": src})
            return {"tool_output": res}

        # Task #16: Semantic Code Search
        elif task_id == 16 and symbols:
            print(f"   Executing Semantic Code Search for '{symbols[0]}'...")
            res = tool_search_codebase_semantic.invoke({"query": state["query"]})
            return {"tool_output": res}

        # Task #19: Test Traceability
        elif task_id == 19 and symbols:
            print(f"   Executing Test Traceability Query for '{symbols[0]}'...")
            res = tool_query_test_traceability.invoke({"target_symbol": symbols[0]})
            return {"tool_output": res}

        # Task #20: API Surface Query
        elif task_id == 20:
            print("   Executing API Endpoints Surface Query...")
            res = tool_query_api_endpoints.invoke({})
            return {"tool_output": res}

        # Fallback 1-shot
        else:
            print(f"   Ready to execute 1-shot tool: '{primary_tool}' with symbols: {symbols}")
            return {
                "tool_output": {
                    "tool": primary_tool,
                    "symbols": symbols,
                    "status": "Ready for 1-turn synthesis",
                }
            }
    except Exception as e:
        print(f"   [Warning] 1-Shot Tool Execution failed: {e}")
        return {"tool_output": {"error": str(e), "symbols": symbols}}


def guided_llm_node(state: CodeNavigatorAgentState) -> Dict[str, Any]:
    """Node 2B: Injects workflow recipes and binds restricted tools for branching execution."""
    recipe = state.get("workflow_recipe")
    query = state["query"]
    allowed_names = state.get("allowed_tools", [])

    # Filter tools down to only those allowed for this recipe
    active_tools = [t for t in ALL_TOOLS if t.name in allowed_names or t.name.replace("tool_", "") in allowed_names]
    tools_to_bind = active_tools if active_tools else ALL_TOOLS

    print(f"\n>> [LangGraph Node: Guided Recipe Orchestrator (Branching 2-3 Turns)]")
    print(f"   Active Bound Tools: {[t.name for t in tools_to_bind]}")
    print(f"\n   --- WORKFLOW RECIPE ---\n{recipe}\n   -----------------------")

    try:
        llm = get_llm()
        try:
            llm_with_tools = llm.bind_tools(tools_to_bind)
            messages = [
                SystemMessage(content=f"You are CodeNavigator executing a guided code intelligence task.\nFollow this recipe step-by-step:\n{recipe}"),
                HumanMessage(content=query),
            ] + state.get("messages", [])
            response = llm_with_tools.invoke(messages)
            return {"messages": [response], "tool_output": {"recipe": recipe, "status": "RECIPE_STEP_EVALUATED"}}
        except Exception:
            # Grounded Fallback: Query codebase vector & graph context before synthesizing
            print("   [Grounding] Querying codebase database for factual context...")
            db_context = tool_search_codebase_semantic.invoke({"query": query})
            
            direct_prompt = (
                "You are CodeNavigator, a strict and factual software architecture assistant.\n"
                "Answer the developer query based ONLY on the provided codebase search results below.\n"
                "CRITICAL: If the search results show no matching symbols, files, or references, state clearly: "
                "'No occurrences found in the codebase graph.' Do NOT hallucinate or assume files exist.\n\n"
                f"--- Codebase Context from Database ---\n{json.dumps(db_context, indent=2, default=str)}\n\n"
                f"Recipe to apply:\n{recipe}\n\n"
                f"Developer Query: {query}\n\n"
                "Factual Answer:"
            )
            response = llm.invoke(direct_prompt)
            content = response.content if hasattr(response, "content") else str(response)
            return {"messages": [HumanMessage(content=content)], "tool_output": db_context}
    except Exception as e:
        print(f"   [Warning] Guided LLM execution error: {e}")
        return {
            "tool_output": {
                "status": "RECIPE_PREPARED",
                "recipe": recipe,
                "allowed_tools": [t.name for t in tools_to_bind],
                "target_symbols": state.get("target_symbols", []),
            }
        }


def react_llm_node(state: CodeNavigatorAgentState) -> Dict[str, Any]:
    """Node 2C: Unconstrained autonomous ReAct exploration loop."""
    query = state["query"]
    print(f"\n>> [LangGraph Node: ReAct Fallback (Open-Ended Exploration)]")
    print(f"   Full tool catalog exposed ({len(ALL_TOOLS)} tools).")

    try:
        llm = get_llm()
        try:
            llm_with_tools = llm.bind_tools(ALL_TOOLS)
            system_prompt = SystemMessage(
                content=(
                    "You are CodeNavigator, an autonomous AI software architecture assistant.\n"
                    "The user asked an open-ended codebase question.\n"
                    "Follow the ReAct framework: Thought -> Action -> Observation -> Final Answer.\n"
                    "Synthesize a clear, factual architectural answer with file and line references."
                )
            )
            messages = [system_prompt, HumanMessage(content=query)] + state.get("messages", [])
            response = llm_with_tools.invoke(messages)
            return {"messages": [response], "tool_output": {"status": "REACT_STEP_EVALUATED"}}
        except Exception:
            # Grounded Fallback: Query codebase vector & graph context before answering
            print("   [Grounding] Querying codebase database for factual context...")
            db_context = tool_search_codebase_semantic.invoke({"query": query})

            direct_prompt = (
                "You are CodeNavigator, a strict and factual software architecture assistant.\n"
                "Answer the developer query based ONLY on the provided codebase search results below.\n"
                "CRITICAL: If the search results show no matching symbols, files, or references, state clearly: "
                "'No occurrences found in the codebase graph.' Do NOT hallucinate files (like config.json) if not in the context.\n\n"
                f"--- Codebase Context from Database ---\n{json.dumps(db_context, indent=2, default=str)}\n\n"
                f"Developer Query: {query}\n\n"
                "Factual Answer:"
            )
            response = llm.invoke(direct_prompt)
            content = response.content if hasattr(response, "content") else str(response)
            return {"messages": [HumanMessage(content=content)], "tool_output": db_context}
    except Exception as e:
        print(f"   [Warning] ReAct LLM execution error: {e}")
        return {
            "tool_output": {
                "status": "DISPATCHED_TO_REACT_LOOP",
                "allowed_tools": [t.name for t in ALL_TOOLS],
                "target_symbols": state.get("target_symbols", []),
            }
        }


def _format_descriptive_fallback(query: str, tool_output: Dict[str, Any]) -> str:
    """Formats structured tool output into readable, 100% factual prose without LLM hallucinations."""
    if not tool_output or not isinstance(tool_output, dict):
        return "No data was returned from the codebase knowledge graph."

    # 1. Call Graph Paths & Raw Call Sites (Tasks #1, #2)
    if "raw_calls" in tool_output and tool_output["raw_calls"]:
        calls = tool_output["raw_calls"]
        sym = tool_output.get("target") or tool_output.get("target_symbol") or "symbol"
        dir_label = "Incoming Callers" if tool_output.get("direction") == "incoming" else "Outgoing Callees"
        lines = [f"Call Graph Analysis for **`{sym}`** ({dir_label} — {len(calls)} call sites found):\n"]
        for i, c in enumerate(calls, 1):
            caller_id = c.get("caller_id", "")
            caller_name = c.get("caller_name", "")
            line = c.get("line")
            file_path = caller_id.split("::")[0] if "::" in caller_id else caller_id
            line_str = f" (Line {line})" if line else ""
            lines.append(f"{i}. Function: `{caller_name}()` | File: `{file_path}`{line_str}")
        return "\n".join(lines)

    if "paths" in tool_output:
        paths = tool_output.get("paths", [])
        sym = tool_output.get("target") or tool_output.get("target_symbol") or "symbol"
        dir_label = "Incoming Callers (Upstream)" if tool_output.get("direction") == "incoming" else "Outgoing Callees (Downstream)"
        if not paths:
            return f"No {dir_label.lower()} found calling '{sym}' in the ingested codebase graph."

        lines = [f"Call Graph Analysis for **`{sym}`** ({dir_label}):\n"]
        for i, p in enumerate(paths, 1):
            nodes = p.get("nodes", [])
            chain = p.get("execution_chain", "")
            depth = p.get("depth", 1)
            lines.append(f"{i}. **Call Chain** (Depth {depth}): `{chain}`")
            for n in nodes:
                fp = n.get("file_path", "")
                line = n.get("line")
                line_str = f" (Line {line})" if line else ""
                lines.append(f"   - Function: `{n.get('name')}` | File: `{fp}`{line_str}")
        return "\n".join(lines)

    # 2. Variable / State / Env References (Tasks #5, #7, #9)
    if "references" in tool_output:
        sym = tool_output.get("symbol") or "symbol"
        refs = tool_output.get("references", [])
        if not refs:
            return f"No references or reads of '{sym}' were found in the ingested codebase graph."
        lines = [f"Variable Reference Audit for **`{sym}`** ({len(refs)} occurrences found):\n"]
        for i, r in enumerate(refs, 1):
            fn = r.get("function_name", "Module Scope")
            fp = r.get("file_path", "")
            lines.append(f"{i}. Accessed by `{fn}` in `{fp}`")
        return "\n".join(lines)

    # 3. Code Snippets (Task #8)
    if "snippet" in tool_output:
        sym = tool_output.get("symbol") or "symbol"
        fp = tool_output.get("file_path", "")
        return f"Code Snippet for **`{sym}`** in `{fp}`:\n\n```python\n{tool_output.get('snippet')}\n```"

    # 4. Dead Code / Orphans (Task #13)
    if "orphans" in tool_output or "dead_code" in tool_output:
        items = tool_output.get("orphans") or tool_output.get("dead_code") or []
        if not items:
            return "No dead code or orphan functions were found in the codebase graph."
        lines = [f"Dead Code & Orphan Identifiers ({len(items)} found):\n"]
        for item in items:
            lines.append(f"- `{item.get('name')}` in `{item.get('file_path')}` (Zero incoming callers)")
        return "\n".join(lines)

    # 5. Semantic Search Results (Task #16)
    if "results" in tool_output and tool_output["results"]:
        lines = ["Codebase Search Results:\n"]
        for res in tool_output["results"][:5]:
            lines.append(f"- `{res.get('name') or res.get('file_path')}`:\n  {res.get('snippet', '')[:120]}...\n")
        return "\n".join(lines)

    return f"Query completed.\n{json.dumps(tool_output, indent=2, default=str)}"


def synthesizer_node(state: CodeNavigatorAgentState) -> Dict[str, Any]:
    """Node 3: Formats and synthesizes the final agent response into descriptive text."""
    query = state.get("query", "")
    strategy = state.get("strategy")
    task_name = state.get("task_name")
    tool_output = state.get("tool_output") or {}
    messages = state.get("messages", [])

    ai_text = None
    if messages:
        last_msg = messages[-1]
        ai_text = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

    # Format 1-shot deterministic directly from database results (100% factual)
    if not ai_text and tool_output:
        ai_text = _format_descriptive_fallback(query, tool_output)

    if not ai_text:
        ai_text = _format_descriptive_fallback(query, tool_output)

    print(f"\n[LangGraph Node: Synthesizer] Execution complete.")
    print("=" * 80)
    print(f"Task: {task_name} | Strategy: {strategy}")
    print("-" * 80)
    print(f"\n{ai_text.strip()}\n")
    print("=" * 80 + "\n")
    return {"final_summary": ai_text}

    print(f"\n[LangGraph Node: Synthesizer] Execution complete.")
    print("=" * 80)
    print(f"Task: {task_name} | Strategy: {strategy}")
    print("-" * 80)
    print(f"\n{ai_text.strip()}\n")
    print("=" * 80 + "\n")
    return {"final_summary": ai_text}


# -----------------------------------------------------------------------------
# Conditional Router
# -----------------------------------------------------------------------------

def route_by_strategy(state: CodeNavigatorAgentState) -> str:
    """Conditional edge function routing based on the classified strategy."""
    strategy = state.get("strategy")
    if strategy == ExecutionStrategy.DETERMINISTIC_1_SHOT.value:
        return "deterministic_1_shot"
    elif strategy == ExecutionStrategy.GUIDED_RECIPE.value:
        return "guided_llm"
    else:
        return "react_llm"


def should_continue(state: CodeNavigatorAgentState) -> str:
    """Checks if the LLM output contains tool calls or final text."""
    messages = state.get("messages", [])
    if messages and hasattr(messages[-1], "tool_calls") and messages[-1].tool_calls:
        return "tools"
    return "synthesizer"


# -----------------------------------------------------------------------------
# Build LangGraph Agent StateGraph
# -----------------------------------------------------------------------------

def build_agentic_graph():
    """Builds and compiles the CodeNavigator LangGraph StateGraph."""
    workflow = StateGraph(CodeNavigatorAgentState)

    # 1. Add Nodes
    workflow.add_node("classifier", classifier_node)
    workflow.add_node("deterministic_1_shot", deterministic_1_shot_node)
    workflow.add_node("guided_llm", guided_llm_node)
    workflow.add_node("guided_tools", ToolNode(ALL_TOOLS))
    workflow.add_node("react_llm", react_llm_node)
    workflow.add_node("react_tools", ToolNode(ALL_TOOLS))
    workflow.add_node("synthesizer", synthesizer_node)

    # 2. Add Edges
    workflow.add_edge(START, "classifier")

    # 3. Classifier conditional branching
    workflow.add_conditional_edges(
        "classifier",
        route_by_strategy,
        {
            "deterministic_1_shot": "deterministic_1_shot",
            "guided_llm": "guided_llm",
            "react_llm": "react_llm",
        },
    )

    # 4. Guided Recipe Loop
    workflow.add_conditional_edges(
        "guided_llm",
        should_continue,
        {
            "tools": "guided_tools",
            "synthesizer": "synthesizer",
        },
    )
    workflow.add_edge("guided_tools", "guided_llm")

    # 5. ReAct Fallback Loop
    workflow.add_conditional_edges(
        "react_llm",
        should_continue,
        {
            "tools": "react_tools",
            "synthesizer": "synthesizer",
        },
    )
    workflow.add_edge("react_tools", "react_llm")

    # 6. Terminal Edges
    workflow.add_edge("deterministic_1_shot", "synthesizer")
    workflow.add_edge("synthesizer", END)

    return workflow.compile()


# -----------------------------------------------------------------------------
# High-Level Agent Class & CLI Entrypoint
# -----------------------------------------------------------------------------

class CodeNavigatorAgent:
    """High-level wrapper around the compiled LangGraph agent graph."""

    def __init__(self):
        self.app = build_agentic_graph()

    def handle_user_query(self, user_query: str) -> Dict[str, Any]:
        """Runs the LangGraph agent state machine for a user query."""
        initial_state: CodeNavigatorAgentState = {
            "query": user_query,
            "messages": [],
            "intent": None,
            "strategy": None,
            "task_id": None,
            "task_name": None,
            "target_symbols": [],
            "recommended_tools": [],
            "allowed_tools": [],
            "workflow_recipe": None,
            "tool_output": None,
            "final_summary": None,
        }
        return self.app.invoke(initial_state)

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def route_query(user_query: str) -> Dict[str, Any]:
    """Convenience helper to route a query through the LangGraph agent."""
    agent = CodeNavigatorAgent()
    return agent.handle_user_query(user_query)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CodeNavigator LangGraph Agentic Router.")
    parser.add_argument(
        "query",
        nargs="*",
        default=["What is the blast radius if I modify Order.status?"],
        help="User query to process.",
    )
    args = parser.parse_args()

    # Join words in case user ran command without quotes
    user_query = " ".join(args.query) if isinstance(args.query, list) else str(args.query)

    agent = CodeNavigatorAgent()
    agent.handle_user_query(user_query)
