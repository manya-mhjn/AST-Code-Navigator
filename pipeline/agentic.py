"""
agentic.py — LangGraph-based Multi-Tier Agent Orchestrator for CodeNavigator.

Constructs a LangGraph StateGraph that:
  1. Classifies developer queries via the LangChain Intent Tool.
  2. Conditionally routes execution across 3 Tiers:
     - DETERMINISTIC_1_SHOT (1-Turn Atomic / Composite execution)
     - GUIDED_RECIPE (Branching 2-3 Turn recipe execution)
     - REACT_FALLBACK (Open-ended exploratory ReAct loop)
  3. Synthesizes and outputs structured results.
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

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import SystemMessage, HumanMessage

from pipeline.graph_traversal import CallGraphTraversal, print_traversal_result
from pipeline.neo4j_sink import Neo4jCodeGraphIngestor
from pipeline.tools import classify_intent, tool_classify_intent, tool_traverse_call_graph
from pipeline.tools_utils import ExecutionStrategy, ExecutionType
from pipeline.weaviate_sink import WeaviateCloudCodeDB
from pipeline.utils import get_llm


def _require_env(name: str) -> str:
    """Fail fast with a clear message if a required env var is missing."""
    value = os.environ.get(name)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{name}' is not set. "
            f"Set it via: export {name}=<value>"
        )
    return value


# -----------------------------------------------------------------------------
# LangGraph Agent State Definition
# -----------------------------------------------------------------------------

class CodeNavigatorAgentState(TypedDict):
    query: str
    intent: Optional[Dict[str, Any]]
    strategy: Optional[str]
    execution_type: Optional[str]
    task_id: Optional[int]
    task_name: Optional[str]
    target_symbols: List[str]
    recommended_tools: List[str]
    allowed_tools: List[str]
    workflow_recipe: Optional[str]
    tool_output: Optional[Dict[str, Any]]
    final_summary: Optional[str]

# 1. Full Tool Catalog for ReAct Fallback
FULL_TOOL_CATALOG = [
    tool_traverse_call_graph,
    tool_classify_intent,
    # Add your other tools here:
    # calculate_blast_radius,
    # search_codebase_semantic,
    # get_symbol_code_snippet,
    # query_api_endpoints,
    # detect_orphan_and_dead_code,
]
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
    exec_type = intent.get("execution_type")
    turns = intent.get("expected_turns")
    symbols = intent.get("target_symbols", [])

    print(f"\n[Intent Routing Decision]")
    print(f"  * Task: #{task_id} ({task_name})")
    print(f"  * Strategy: {strategy} (Type: {exec_type}, Expected Turns: {turns})")
    print(f"  * Extracted Symbols: {symbols}")
    print(f"  * Recommended Tools: {intent['recommended_tools']}")

    return {
        "intent": intent,
        "strategy": strategy,
        "execution_type": exec_type,
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

    # Task #1 & #2: Call Graph Traversals
    if task_id in (1, 2) and symbols:
        target = symbols[0]
        direction = "incoming" if task_id == 1 else "outgoing"
        print(f"   Invoking Graph Traversal on '{target}' (Direction: {direction})...")
        try:
            engine = CallGraphTraversal()
            try:
                res = engine.traverse_call_graph(target_symbol=target, direction=direction, max_depth=3)
                print_traversal_result(res)
                return {"tool_output": res}
            finally:
                engine.close()
        except Exception as e:
            print(f"   [Warning] Graph Traversal failed (Database unreachable): {e}")
            return {"tool_output": {"error": f"Database unreachable: {e}", "target": target}}

    # Task #13: Dead Code & Orphan Detection
    elif task_id == 13:
        print("   Invoking Dead Code & Orphan Node Detection...")
        try:
            db = Neo4jCodeGraphIngestor(
                uri=_require_env("NEO4J_URI"),
                auth=(_require_env("NEO4J_USER"), _require_env("NEO4J_PASSWORD")),
            )
            with db.driver.session() as session:
                records = session.run("""
                    MATCH (fn:Function)
                    WHERE NOT ( ()-[:RESOLVED_CALLS|CALLS]->(fn) )
                      AND NOT fn.name STARTS WITH '__'
                      AND NOT fn.name STARTS WITH 'test_'
                    RETURN fn.name AS name, fn.file_path AS file_path, fn.line_start AS line
                    LIMIT 20
                """)
                orphans = [{"name": r["name"], "file_path": r["file_path"], "line": r["line"]} for r in records]
                db.close()
                print(f"   Found {len(orphans)} uncalled orphan function(s).")
                return {"tool_output": {"orphan_functions": orphans, "total_found": len(orphans)}}
        except Exception as e:
            return {"tool_output": {"error": str(e)}}

    # General 1-Shot Tool fallback
    else:
        print(f"   Ready to execute 1-shot tool: '{primary_tool}' with symbols: {symbols}")
        return {
            "tool_output": {
                "tool": primary_tool,
                "symbols": symbols,
                "status": "Ready for 1-turn synthesis",
            }
        }




# In pipeline/agentic.py

def guided_llm_node(state: CodeNavigatorAgentState):
    """Invokes LLM with the injected recipe and restricted toolset."""
    recipe = state.get("workflow_recipe")
    query = state["query"]
    allowed_tool_names = state.get("allowed_tools", [])

    # 1. Filter tools to only those allowed for this recipe
    active_tools = [t for t in FULL_TOOL_CATALOG if t.name in allowed_tool_names]
    
    # Safety check: if no specific tools matched, fall back to FULL_TOOL_CATALOG
    tools_to_bind = active_tools if active_tools else FULL_TOOL_CATALOG

    # 2. Initialize LLM and bind the filtered tools
    llm = get_llm()
    llm_with_tools = llm.bind_tools(tools_to_bind)

    # 3. Construct messages with recipe guidance
    messages = [
        SystemMessage(content=f"Follow this workflow recipe carefully:\n{recipe}"),
        HumanMessage(content=query)
    ] + state.get("messages", [])

    # 4. Invoke LLM
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


# Subgraph Construction
guided_workflow = StateGraph(CodeNavigatorAgentState)

guided_workflow.add_node("guided_llm", guided_llm_node)
guided_workflow.add_node("guided_tools", ToolNode(FULL_TOOL_CATALOG))

guided_workflow.add_edge(START, "guided_llm")

# Conditional Edge: If LLM requested a tool, go to tool node; else end
guided_workflow.add_conditional_edges(
    "guided_llm",
    tools_condition,  # Built-in LangGraph check for response.tool_calls
    {
        "tools": "guided_tools",
        "__end__": END
    }
)

# Loop back from Tool execution to LLM for next decision
guided_workflow.add_edge("guided_tools", "guided_llm")



# 2. The ReAct LLM Node
def react_llm_node(state: CodeNavigatorAgentState):
    """
    Autonomous ReAct agent node with full tool access for open-ended queries.
    """
    query = state["query"]
    
    # Bind ALL tools (unconstrained)
    llm_with_all_tools = get_llm().bind_tools(FULL_TOOL_CATALOG)
    
    # Autonomous Exploration Prompt
    system_prompt = SystemMessage(
        content=(
            "You are CodeNavigator, an autonomous AI software architecture assistant.\n"
            "The user asked an open-ended or exploratory codebase question.\n"
            "Follow the ReAct framework:\n"
            "1. Thought: Analyze what information is needed.\n"
            "2. Action: Use graph or vector search tools to gather evidence.\n"
            "3. Observation: Review tool outputs.\n"
            "4. Final Answer: Synthesize a clear, accurate architectural response with file/line references.\n"
            "Do not stop until you have gathered sufficient evidence to answer completely."
        )
    )
    
    messages = [system_prompt, HumanMessage(content=query)] + state.get("messages", [])
    response = llm_with_all_tools.invoke(messages)
    
    return {"messages": [response]}


def synthesizer_node(state: CodeNavigatorAgentState) -> Dict[str, Any]:
    """Node 3: Formats and synthesizes the final agent response."""
    strategy = state.get("strategy")
    task_name = state.get("task_name")
    tool_output = state.get("tool_output")

    summary = (
        f"Query processed via Strategy: {strategy} | Task: {task_name}\n"
        f"Status: {tool_output.get('status', 'SUCCESS') if tool_output else 'COMPLETED'}"
    )
    print(f"\n[LangGraph Node: Synthesizer] Execution complete.")
    print("=" * 80 + "\n")
    return {"final_summary": summary}


# -----------------------------------------------------------------------------
# Conditional Router
# -----------------------------------------------------------------------------

def route_by_strategy(state: CodeNavigatorAgentState) -> str:
    """Conditional edge function routing based on the classified strategy."""
    strategy = state.get("strategy")
    if strategy == ExecutionStrategy.DETERMINISTIC_1_SHOT.value:
        return "deterministic_1_shot"
    elif strategy == ExecutionStrategy.GUIDED_RECIPE.value:
        return "guided_recipe"
    else:
        return "react_fallback"


# -----------------------------------------------------------------------------
# Build LangGraph Agent StateGraph
# -----------------------------------------------------------------------------

def build_agentic_graph():
    workflow = StateGraph(CodeNavigatorAgentState)

    # Add Nodes
    workflow.add_node("classifier", classifier_node)
    workflow.add_node("deterministic_1_shot", deterministic_1_shot_node)
    
    # Tier 2: Guided Recipe Loop
    workflow.add_node("guided_llm", guided_llm_node)
    workflow.add_node("guided_tools", ToolNode(FULL_TOOL_CATALOG))
    
    # Tier 3: ReAct Fallback Loop
    workflow.add_node("react_llm", react_llm_node)
    workflow.add_node("react_tools", ToolNode(FULL_TOOL_CATALOG))
    
    workflow.add_node("synthesizer", synthesizer_node)

    # 1. Start at Classifier
    workflow.add_edge(START, "classifier")

    # 2. Classifier conditionally routes across the 3 Tiers
    workflow.add_conditional_edges(
        "classifier",
        route_by_strategy,
        {
            "deterministic_1_shot": "deterministic_1_shot",
            "guided_recipe": "guided_llm",
            "react_fallback": "react_llm",      # <--- Routes to ReAct Fallback
        }
    )

    # 3. Tier 2 Loop (Guided Recipe)
    workflow.add_conditional_edges(
        "guided_llm",
        tools_condition,
        {"tools": "guided_tools", "__end__": "synthesizer"}
    )
    workflow.add_edge("guided_tools", "guided_llm")

    # 4. Tier 3 Loop (ReAct Fallback)
    workflow.add_conditional_edges(
        "react_llm",
        tools_condition,
        {"tools": "react_tools", "__end__": "synthesizer"}
    )
    workflow.add_edge("react_tools", "react_llm")

    # 5. Terminal Edges to Synthesizer -> END
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
            "intent": None,
            "strategy": None,
            "execution_type": None,
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
        nargs="?",
        default="What is the blast radius if I modify Order.status?",
        help="User query to process.",
    )
    args = parser.parse_args()

    agent = CodeNavigatorAgent()
    agent.handle_user_query(args.query)
