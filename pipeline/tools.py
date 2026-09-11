"""
tools.py — Complete LangChain Tool Suite & Intent Classifier for CodeNavigator.

Implements all 20 code intelligence tools with Neo4j Knowledge Graph traversals
and Weaviate Vector DB semantic searches.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Any, Dict, List, Optional

# Ensure repository root is on sys.path
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from dotenv import load_dotenv

load_dotenv(override=True)

from langchain_core.tools import tool

from pipeline.graph_traversal import CallGraphTraversal, traverse_call_graph
from pipeline.neo4j_sink import Neo4jCodeGraphIngestor
from pipeline.tools_utils import (
    ExecutionStrategy,
    TASK_DEFINITIONS,
)
from pipeline.weaviate_sink import WeaviateCloudCodeDB


def _get_neo4j_session():
    """Helper to open a Neo4j session using environment variables."""
    uri = os.environ.get("NEO4J_URI")
    user = os.environ.get("NEO4J_USER")
    password = os.environ.get("NEO4J_PASSWORD")
    if not (uri and user and password):
        return None
    try:
        db = Neo4jCodeGraphIngestor(uri=uri, auth=(user, password))
        return db
    except Exception as e:
        print(f"[Warning] Could not connect to Neo4j: {e}")
        return None


def _get_weaviate_client():
    """Helper to connect to Weaviate Cloud."""
    url = os.environ.get("WEAVIATE_CLUSTER_URL") or os.environ.get("WEAVIATE_URL")
    api_key = os.environ.get("WEAVIATE_API_KEY")
    if not (url and api_key):
        return None
    try:
        return WeaviateCloudCodeDB(cluster_url=url, api_key=api_key)
    except Exception as e:
        print(f"[Warning] Could not connect to Weaviate: {e}")
        return None


# -----------------------------------------------------------------------------
# Intent Classifier
# -----------------------------------------------------------------------------

from pydantic import BaseModel, Field
from pipeline.utils import get_llm


class IntentClassificationSchema(BaseModel):
    """Structured output schema for LLM Intent Classification."""
    task_id: Optional[int] = Field(
        None,
        description="The integer task ID (1-20) matching the task catalog, or null if the query is open-ended or exploratory."
    )
    target_symbols: List[str] = Field(
        default_factory=list,
        description="Extracted code identifiers, function names, class names, dot-attributes, or configuration constants."
    )
    confidence: float = Field(
        0.95,
        description="Confidence score between 0.0 and 1.0."
    )
    reasoning: str = Field(
        ...,
        description="Brief 1-sentence reasoning explaining why this task and strategy were selected."
    )


class CodeIntentClassifier:
    """
    LLM-powered Classifier that presents all 20 Task Definitions to the model
    and extracts structured routing decisions and target code symbols.
    """

    def __init__(self):
        self.task_defs = TASK_DEFINITIONS
        self._prompt_catalog = self._build_task_catalog_prompt()

    def _build_task_catalog_prompt(self) -> str:
        lines = []
        for task_id, task in sorted(self.task_defs.items()):
            lines.append(f"- Task #{task_id:02d}: {task['name']}")
        return "\n".join(lines)

    def classify(self, query: str) -> Dict[str, Any]:
        """
        Presents all 20 Task Definitions to the LLM to classify the user's intent.
        """
        system_instruction = (
            "You are CodeNavigator's Intent Router. Your job is to analyze a developer's codebase query, "
            "classify it into exactly one of the 20 predefined Code Intelligence Tasks, and extract all relevant target code symbols.\n\n"
            "Task Classification Taxonomy & Disambiguation Rules:\n"
            "1. Task #01 (Upstream Call Tracing): Finding which callers or functions invoke/call a given function or method.\n"
            "2. Task #02 (Downstream Call Tracing): Finding what downstream functions or dependencies a given function invoke/call.\n"
            "3. Task #03 (Blast Radius & Impact Analysis): Finding what breaks, impact analysis, or affected downstream modules when modifying a symbol.\n"
            "4. Task #04 (Function Parameter & Argument Lineage): Tracing how specific arguments or parameters are passed into a function across call sites.\n"
            "5. Task #05 (Class Instance Attribute Mutability): Finding where class instance attributes (`self.`) are initialized, read, or modified.\n"
            "6. Task #06 (Inherited Class Attribute Resolution): Resolving attributes, methods, or `super()` calls inherited from parent classes.\n"
            "7. Task #07 (Global & Module-Level Variable Audit): Finding where module-level globals or module constants are declared, read, or modified.\n"
            "8. Task #08 (Local Variable Initialization & Defaults): Inspecting local variable defaults, fallback initial values, and timeouts in a function.\n"
            "9. Task #09 (Environment Variables & Configuration Audit): Auditing where environment variables, secrets, API keys, tokens, or config parameters are accessed.\n"
            "10. Task #10 (Data Flow & Variable Expression Lineage): Tracing mathematical formulas, expression derivations, and intermediate variable dependencies.\n"
            "11. Task #11 (State Mutation & Reassignment Tracing): Tracking where mutable objects (lists, dicts, instances) are mutated in-place or reassigned.\n"
            "12. Task #12 (Module & Architecture Coupling): Finding circular imports, cross-module dependencies, and architectural layer boundaries.\n"
            "13. Task #13 (Dead Code & Orphan Identification): Locating uncalled functions, unused imports, and zero-in-degree dead code.\n"
            "14. Task #14 (Security & Vulnerability Path Tracking): Taint analysis from untrusted user inputs to sensitive sinks (e.g. SQL injection, command execution).\n"
            "15. Task #15 (Error Handling & Exception Propagation): Tracing try/except blocks, unhandled exceptions, and error propagation paths.\n"
            "16. Task #16 (Business Logic & Concept Explanation): Explaining high-level domain workflows, features, and business logic mechanisms.\n"
            "17. Task #17 (Type & Class Hierarchy Inspection): Inspecting class inheritance trees, subclasses, dataclasses, structs, and enum usages.\n"
            "18. Task #18 (Performance & Bottleneck Spotting): Spotting nested loops, redundant iterations, and expensive queries inside loops.\n"
            "19. Task #19 (Test Coverage & Traceability): Identifying unit tests or test files that cover or invoke a given function or class.\n"
            "20. Task #20 (API Contract & Interface Surface): Auditing REST API endpoints, HTTP routes, methods (GET/POST), and request schemas.\n\n"
            "Routing Instructions:\n"
            "- Select the exact integer `task_id` (1 to 20) corresponding to the rule above.\n"
            "- If the query is an open-ended refactoring or design question without a task match, set `task_id` to null.\n"
            "- Extract all target symbols (function names, class names, dot-attributes, or configuration identifiers) into `target_symbols`.\n"
            "- Provide a clear 1-sentence `reasoning` explaining your classification decision."
        )

        try:
            llm = get_llm(temperature=0.0)
            task_id = None
            symbols = []
            confidence = 0.95
            reasoning = "LLM Classification"

            # Attempt native structured output (Gemini, OpenAI, Anthropic, Ollama)
            try:
                structured_llm = llm.with_structured_output(IntentClassificationSchema)
                parsed: IntentClassificationSchema = structured_llm.invoke([
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": f"Classify this developer query:\n\"{query}\""}
                ])
                task_id = parsed.task_id
                symbols = parsed.target_symbols
                confidence = parsed.confidence
                reasoning = parsed.reasoning
            except Exception:
                # Resilient JSON parsing & Pydantic validation for Local HuggingFace models
                from langchain_core.output_parsers import PydanticOutputParser
                parser = PydanticOutputParser(pydantic_object=IntentClassificationSchema)

                prompt = (
                    f"{system_instruction}\n\n"
                    f"{parser.get_format_instructions()}\n\n"
                    f'Developer Query: "{query}"\n'
                )
                response = llm.invoke(prompt)
                raw_text = response.content if hasattr(response, "content") else str(response)
                
                # 1. Extract and parse JSON block from output
                data = {}
                match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", raw_text, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(0))
                    except Exception:
                        pass

                if not data:
                    # Fallback regex extraction if JSON decoding failed
                    tid_m = re.search(r'"task_id"\s*:\s*(\d+|null|"[^"]+")', raw_text)
                    raw_tid_val = tid_m.group(1).replace('"', '') if tid_m else None
                    digit_m = re.search(r"\d+", str(raw_tid_val)) if raw_tid_val else None
                    
                    data = {
                        "task_id": int(digit_m.group(0)) if digit_m else None,
                        "target_symbols": [],
                        "confidence": 0.95,
                        "reasoning": raw_text[:200]
                    }

                # 2. Coerce task_id if represented as "09", "Task 9", or float
                raw_tid = data.get("task_id")
                if raw_tid is not None:
                    digit_match = re.search(r"\d+", str(raw_tid))
                    data["task_id"] = int(digit_match.group(0)) if digit_match else None
                
                # 3. Fallback extraction for target_symbols if empty
                if not data.get("target_symbols"):
                    stop_words = {"who", "what", "where", "which", "how", "calls", "called", "call", "invokes", "invoked", "invoke", "is", "are", "read", "from", "in", "the", "a", "an", "does", "if", "modify", "change", "set", "get", "to", "of", "and", "or", "with", "does", "do", "it"}
                    word_candidates = re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_\.]*)\b", query)
                    data["target_symbols"] = [w for w in word_candidates if w.lower() not in stop_words]

                # 4. Validate with Pydantic Schema
                parsed = IntentClassificationSchema(**data)
                task_id = parsed.task_id
                symbols = parsed.target_symbols
                confidence = parsed.confidence
                reasoning = parsed.reasoning

            # Semantic alignment: Ensure task_id matches the LLM's own reasoning for all 20 tasks
            r_lower = reasoning.lower() + " " + query.lower()
            if any(k in r_lower for k in ["secret", "environment variable", "env var", "config token", "api key", "os.getenv"]) and task_id != 9:
                task_id = 9
            elif any(k in r_lower for k in ["who calls", "caller", "incoming call", "invoked by"]) and task_id != 1:
                task_id = 1
            elif any(k in r_lower for k in ["what does .* call", "callee", "outgoing call", "dependencies called"]) and task_id != 2:
                task_id = 2
            elif any(k in r_lower for k in ["blast radius", "impact analysis", "what breaks", "affect downstream"]) and task_id != 3:
                task_id = 3
            elif any(k in r_lower for k in ["parameter lineage", "argument passed", "parameter passed"]) and task_id != 4:
                task_id = 4
            elif any(k in r_lower for k in ["self.", "instance attribute", "attribute mutability"]) and task_id != 5:
                task_id = 5
            elif any(k in r_lower for k in ["super()", "inherited attribute", "parent class attribute"]) and task_id != 6:
                task_id = 6
            elif any(k in r_lower for k in ["global variable", "module variable", "global constant"]) and task_id != 7:
                task_id = 7
            elif any(k in r_lower for k in ["default value", "initial value", "default timeout", "hardcoded default"]) and task_id != 8:
                task_id = 8
            elif any(k in r_lower for k in ["data flow", "formula", "expression derivation", "variable derivation"]) and task_id != 10:
                task_id = 10
            elif any(k in r_lower for k in ["state mutation", "mutated in-place", "reassignment tracing"]) and task_id != 11:
                task_id = 11
            elif any(k in r_lower for k in ["circular import", "module coupling", "architectural boundary"]) and task_id != 12:
                task_id = 12
            elif any(k in r_lower for k in ["dead code", "orphan function", "uncalled function", "unused code"]) and task_id != 13:
                task_id = 13
            elif any(k in r_lower for k in ["taint", "vulnerability", "sql injection", "security path"]) and task_id != 14:
                task_id = 14
            elif any(k in r_lower for k in ["try/except", "exception propagation", "error handling", "unhandled exception"]) and task_id != 15:
                task_id = 15
            elif any(k in r_lower for k in ["business logic", "explain workflow", "how does .* work", "concept explanation"]) and task_id != 16:
                task_id = 16
            elif any(k in r_lower for k in ["class hierarchy", "subclasses of", "inheritance tree", "dataclass"]) and task_id != 17:
                task_id = 17
            elif any(k in r_lower for k in ["performance bottleneck", "nested loop", "loop bottleneck"]) and task_id != 18:
                task_id = 18
            elif any(k in r_lower for k in ["test coverage", "unit test", "tests invoke", "test file"]) and task_id != 19:
                task_id = 19
            elif any(k in r_lower for k in ["rest endpoint", "api route", "http method", "api contract"]) and task_id != 20:
                task_id = 20

            if task_id and task_id in self.task_defs:
                task_info = self.task_defs[task_id]
                return {
                    "query": query,
                    "task_id": task_id,
                    "task_name": task_info["name"],
                    "strategy": task_info["strategy"].value if hasattr(task_info["strategy"], "value") else str(task_info["strategy"]),
                    "expected_turns": task_info["expected_turns"],
                    "recommended_tools": task_info["recommended_tools"],
                    "allowed_tools": self._filter_allowed_tools(task_info),
                    "target_symbols": symbols,
                    "workflow_recipe": task_info.get("recipe"),
                    "confidence": confidence,
                    "explanation": f"LLM Classification: {reasoning}",
                }
            else:
                return self._react_fallback(query, symbols, reasoning=reasoning)

        except Exception as e:
            return self._react_fallback(query, [], reasoning=f"LLM classification exception ({e}). Defaulted to ReAct loop.")

    def _react_fallback(self, query: str, symbols: List[str], reasoning: str = "Open-ended exploration") -> Dict[str, Any]:
        all_tool_names = [
            "tool_traverse_call_graph", "tool_calculate_blast_radius",
            "tool_inspect_type_and_inheritance_hierarchy", "tool_query_variable_and_state_references",
            "tool_analyze_architecture_coupling", "tool_detect_orphan_and_dead_code",
            "tool_trace_taint_and_security_paths", "tool_query_test_traceability",
            "tool_query_api_endpoints", "tool_search_codebase_semantic",
            "tool_get_symbol_code_snippet", "tool_trace_parameter_lineage"
        ]
        return {
            "query": query,
            "task_id": None,
            "task_name": "Open-Ended / Exploratory Query",
            "strategy": ExecutionStrategy.REACT_FALLBACK.value,
            "expected_turns": -1,
            "recommended_tools": ["tool_search_codebase_semantic", "tool_traverse_call_graph"],
            "allowed_tools": all_tool_names,
            "target_symbols": symbols,
            "workflow_recipe": None,
            "confidence": 0.60,
            "explanation": f"Routed to ReAct loop: {reasoning}",
        }

    def _filter_allowed_tools(self, task_info: Dict[str, Any]) -> List[str]:
        tools = list(task_info["recommended_tools"])
        if "tool_get_symbol_code_snippet" not in tools and "get_symbol_code_snippet" not in tools:
            tools.append("tool_get_symbol_code_snippet")
        normalized_tools = []
        for t in tools:
            if not t.startswith("tool_"):
                normalized_tools.append(f"tool_{t}")
            else:
                normalized_tools.append(t)
        return normalized_tools


def classify_intent(query: str) -> Dict[str, Any]:
    """Classifies a user developer query into execution tiers and recommended tools."""
    classifier = CodeIntentClassifier()
    return classifier.classify(query)


# -----------------------------------------------------------------------------
# LangChain Tools (The 20-Task Suite)
# -----------------------------------------------------------------------------

@tool
def tool_classify_intent(query: str) -> Dict[str, Any]:
    """
    Classifies a developer question into execution tiers (DETERMINISTIC_1_SHOT, GUIDED_RECIPE, REACT_FALLBACK).
    Returns task name, execution strategy, recommended tools, and workflow recipes.
    """
    return classify_intent(query)


@tool
def tool_traverse_call_graph(
    target_symbol: str,
    direction: str = "incoming",
    max_depth: int = 3,
    file_path: Optional[str] = None,
    include_raw: bool = True,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    [Task #1, #2] Traverses the call graph in Neo4j up to max_depth hops.
    Use direction='incoming' for upstream callers and direction='outgoing' for downstream callees.
    """
    return traverse_call_graph(
        target_symbol=target_symbol,
        direction=direction,
        max_depth=max_depth,
        file_path=file_path,
        include_raw=include_raw,
        limit=limit,
    )


@tool
def tool_calculate_blast_radius(
    changed_symbols: List[str],
    max_depth: int = 4,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    [Task #3] Calculates the blast radius and transitive impact of modifying symbols.
    Traverses transitive reverse dependencies across :RESOLVED_CALLS, :IMPORTS, and :RESOLVED_INHERITS.
    """
    db = _get_neo4j_session()
    if not db:
        return {"error": "Neo4j database connection unavailable", "changed_symbols": changed_symbols}

    try:
        with db.driver.session() as session:
            cypher = """
            UNWIND $symbols AS sym
            MATCH path = (dependent)-[:RESOLVED_CALLS|CALLS|IMPORTS|RESOLVED_INHERITS*1..4]->(target)
            WHERE target.name = sym 
               OR target.file_path CONTAINS sym
               OR target.name ENDS WITH ('.' + sym)
            RETURN DISTINCT 
                dependent.name AS name, 
                labels(dependent)[0] AS type, 
                dependent.file_path AS file_path, 
                dependent.line_start AS line_start,
                length(path) AS distance
            ORDER BY distance ASC
            LIMIT $limit
            """
            records = session.run(cypher, symbols=changed_symbols, limit=limit)
            affected = [
                {
                    "name": r["name"],
                    "type": r["type"],
                    "file_path": r["file_path"],
                    "line": r["line_start"],
                    "distance": r["distance"],
                }
                for r in records
            ]
            
            # Group by file path
            by_file: Dict[str, List[str]] = {}
            for item in affected:
                f = item["file_path"] or "unknown"
                by_file.setdefault(f, []).append(f"{item['type']} {item['name']} (hop {item['distance']})")

            return {
                "changed_symbols": changed_symbols,
                "total_affected_symbols": len(affected),
                "total_affected_files": len(by_file),
                "affected_files_summary": by_file,
                "detailed_nodes": affected,
            }
    except Exception as e:
        return {"error": str(e), "changed_symbols": changed_symbols}
    finally:
        db.close()


@tool
def tool_trace_parameter_lineage(
    function_name: str,
    parameter_name: str,
    max_depth: int = 2,
) -> Dict[str, Any]:
    """
    [Task #4] Traces argument values and lineage for a specific function parameter across callers.
    """
    db = _get_neo4j_session()
    callers = []
    if db:
        try:
            with db.driver.session() as session:
                cypher = """
                MATCH (fn:Function {name: $fn_name})<-[:RESOLVED_CALLS|CALLS]-(caller)
                RETURN caller.name AS caller_name, caller.file_path AS file_path, caller.line_start AS line_start
                LIMIT 20
                """
                records = session.run(cypher, fn_name=function_name)
                callers = [{"caller": r["caller_name"], "file": r["file_path"], "line": r["line_start"]} for r in records]
        except Exception as e:
            print(f"[Warning] Error querying callers in Neo4j: {e}")
        finally:
            db.close()

    return {
        "function_name": function_name,
        "parameter_name": parameter_name,
        "caller_call_sites": callers,
        "lineage_summary": f"Parameter '{parameter_name}' in '{function_name}' is invoked by {len(callers)} caller(s). Inspect caller snippets for explicit argument binding.",
    }


@tool
def tool_query_variable_and_state_references(
    symbol_name: str,
    variable_type: str = "all",
    limit: int = 50,
) -> Dict[str, Any]:
    """
    [Tasks #5, #7, #9, #11] Queries state references and usages.
    Supports variable_type: 'instance_attr' (self.x), 'global' (module constants), 'env_var' (ENV::X), or 'all'.
    """
    db = _get_neo4j_session()
    if not db:
        return {"error": "Neo4j connection unavailable", "symbol_name": symbol_name}

    try:
        with db.driver.session() as session:
            # 1. Environment Variable references
            if variable_type in ("env_var", "all") and (symbol_name.isupper() or "_" in symbol_name):
                env_records = session.run("""
                    MATCH (scope)-[:USES_ENV]->(env:EnvVar)
                    WHERE env.name = $sym OR env.name CONTAINS $sym
                    RETURN scope.name AS scope, scope.file_path AS file_path, env.name AS env_var, env.default_value AS default_value
                    LIMIT $limit
                """, sym=symbol_name, limit=limit)
                env_usages = [{"scope": r["scope"], "file": r["file_path"], "env_var": r["env_var"], "default": r["default_value"]} for r in env_records]
                if env_usages:
                    return {"type": "env_var", "symbol": symbol_name, "references": env_usages, "count": len(env_usages)}

            # 2. Instance Attribute references (self.attr)
            if variable_type in ("instance_attr", "all"):
                clean_sym = symbol_name.split(".")[-1]
                attr_records = session.run("""
                    MATCH (fn:Function)-[:RESOLVED_USES_INST_ATTR]->(attr)
                    WHERE attr.name = $sym OR attr.name ENDS WITH ('.' + $sym)
                    RETURN fn.name AS function_name, fn.file_path AS file_path, attr.name AS attribute
                    LIMIT $limit
                """, sym=clean_sym, limit=limit)
                attr_usages = [{"function": r["function_name"], "file": r["file_path"], "attribute": r["attribute"]} for r in attr_records]
                if attr_usages:
                    return {"type": "instance_attribute", "symbol": symbol_name, "references": attr_usages, "count": len(attr_usages)}

            # 3. Global Variable references
            global_records = session.run("""
                MATCH (fn:Function)-[:RESOLVED_USES_VARIABLE]->(var:Variable)
                WHERE var.name = $sym
                RETURN fn.name AS function_name, fn.file_path AS file_path, var.name AS variable
                LIMIT $limit
            """, sym=symbol_name, limit=limit)
            global_usages = [{"function": r["function_name"], "file": r["file_path"], "variable": r["variable"]} for r in global_records]
            return {"type": "global_variable", "symbol": symbol_name, "references": global_usages, "count": len(global_usages)}
    except Exception as e:
        return {"error": str(e), "symbol_name": symbol_name}
    finally:
        db.close()


@tool
def tool_inspect_type_and_inheritance_hierarchy(
    class_symbol: str,
    direction: str = "both",
) -> Dict[str, Any]:
    """
    [Tasks #6, #17] Inspects class inheritance and type hierarchies.
    Traverses :RESOLVED_INHERITS (superclasses and subclasses) and retrieves :HAS_METHOD links.
    """
    db = _get_neo4j_session()
    if not db:
        return {"error": "Neo4j connection unavailable", "class_symbol": class_symbol}

    try:
        with db.driver.session() as session:
            # Superclasses (Parents)
            parent_records = session.run("""
                MATCH (cls:Class {name: $cls})-[:RESOLVED_INHERITS|INHERITS_FROM*1..3]->(super_cls:Class)
                RETURN super_cls.name AS parent, super_cls.file_path AS file_path
            """, cls=class_symbol)
            parents = [{"name": r["parent"], "file": r["file_path"]} for r in parent_records]

            # Subclasses (Children)
            child_records = session.run("""
                MATCH (sub_cls:Class)-[:RESOLVED_INHERITS|INHERITS_FROM*1..3]->(cls:Class {name: $cls})
                RETURN sub_cls.name AS child, sub_cls.file_path AS file_path
            """, cls=class_symbol)
            children = [{"name": r["child"], "file": r["file_path"]} for r in child_records]

            # Methods
            method_records = session.run("""
                MATCH (cls:Class {name: $cls})-[:HAS_METHOD]->(fn:Function)
                RETURN fn.name AS method, fn.line_start AS line
            """, cls=class_symbol)
            methods = [{"method": r["method"], "line": r["line"]} for r in method_records]

            return {
                "class": class_symbol,
                "superclasses": parents,
                "subclasses": children,
                "methods": methods,
            }
    except Exception as e:
        return {"error": str(e), "class_symbol": class_symbol}
    finally:
        db.close()


@tool
def tool_get_symbol_code_snippet(
    symbol_name: str,
    file_path: Optional[str] = None,
    max_lines: int = 80,
) -> Dict[str, Any]:
    """
    [Tasks #8, #10, #15, #18] Fetches the exact code snippet for a function, class, or method.
    """
    db = _get_neo4j_session()
    line_start, line_end = None, None
    resolved_file = file_path

    if db:
        try:
            with db.driver.session() as session:
                records = session.run("""
                    MATCH (n)
                    WHERE (n:Function OR n:Class) AND n.name = $sym
                    RETURN n.file_path AS file_path, n.line_start AS line_start, n.line_end AS line_end
                    LIMIT 1
                """, sym=symbol_name)
                r = records.single()
                if r:
                    resolved_file = r["file_path"]
                    line_start = r["line_start"]
                    line_end = r["line_end"]
        except Exception as e:
            print(f"[Warning] Neo4j snippet lookup: {e}")
        finally:
            db.close()

    # Read from disk if file is resolved
    if resolved_file and os.path.exists(resolved_file):
        try:
            with open(resolved_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            start = max(0, (line_start - 1) if line_start else 0)
            end = min(len(lines), (line_end if line_end else start + max_lines))
            snippet = "".join(lines[start:end])
            return {
                "symbol": symbol_name,
                "file_path": resolved_file,
                "line_start": start + 1,
                "line_end": end,
                "code": snippet,
            }
        except Exception as e:
            return {"error": f"Failed to read file {resolved_file}: {e}"}

    # Fallback to Weaviate vector chunk fetch
    wv = _get_weaviate_client()
    if wv:
        try:
            results = wv.hybrid_search(symbol_name, limit=1)
            if results:
                return {
                    "symbol": symbol_name,
                    "file_path": results[0].get("file_path"),
                    "code": results[0].get("code"),
                    "docstring": results[0].get("docstring"),
                }
        finally:
            wv.close()

    return {"symbol": symbol_name, "error": "Symbol definition not found on disk or vector store."}


@tool
def tool_analyze_architecture_coupling(
    source_module: Optional[str] = None,
    detect_cycles: bool = True,
) -> Dict[str, Any]:
    """
    [Task #12] Analyzes module coupling and detects circular import dependencies in Neo4j.
    """
    db = _get_neo4j_session()
    if not db:
        return {"error": "Neo4j connection unavailable"}

    try:
        with db.driver.session() as session:
            # Direct Imports
            imports_records = session.run("""
                MATCH (f1:File)-[:IMPORTS]->(f2:File)
                RETURN f1.path AS from_file, f2.path AS to_file
                LIMIT 50
            """)
            imports_list = [{"from": r["from_file"], "to": r["to_file"]} for r in imports_records]

            # Circular Import Cycles
            cycle_records = session.run("""
                MATCH (f1:File)-[:IMPORTS]->(f2:File)-[:IMPORTS]->(f1:File)
                WHERE f1.path < f2.path
                RETURN f1.path AS file_a, f2.path AS file_b
                LIMIT 20
            """)
            cycles = [{"cycle": f"{r['file_a']} <---> {r['file_b']}"} for r in cycle_records]

            return {
                "total_import_edges": len(imports_list),
                "circular_cycles_detected": len(cycles),
                "circular_cycles": cycles,
                "dependencies_sample": imports_list[:25],
            }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@tool
def tool_detect_orphan_and_dead_code(
    scope_path: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    [Task #13] Detects dead, uncalled, or orphan functions with in_degree(RESOLVED_CALLS) == 0.
    """
    db = _get_neo4j_session()
    if not db:
        return {"error": "Neo4j connection unavailable"}

    try:
        with db.driver.session() as session:
            cypher = """
            MATCH (fn:Function)
            WHERE NOT ( ()-[:RESOLVED_CALLS|CALLS]->(fn) )
              AND NOT fn.name STARTS WITH '__'
              AND NOT fn.name STARTS WITH 'test_'
              AND NOT fn.is_endpoint = true
            RETURN fn.name AS name, fn.file_path AS file_path, fn.line_start AS line
            LIMIT $limit
            """
            records = session.run(cypher, limit=limit)
            orphans = [{"name": r["name"], "file_path": r["file_path"], "line": r["line"]} for r in records]
            return {
                "total_orphan_functions_found": len(orphans),
                "orphans": orphans,
            }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@tool
def tool_trace_taint_and_security_paths(
    source_pattern: str = "request",
    sink_pattern: str = "execute|eval|exec|query|system",
    max_depth: int = 5,
) -> Dict[str, Any]:
    """
    [Task #14] Finds security taint paths from untrusted input sources to sensitive sinks in Neo4j.
    """
    db = _get_neo4j_session()
    if not db:
        return {"error": "Neo4j connection unavailable", "source": source_pattern, "sink": sink_pattern}

    try:
        with db.driver.session() as session:
            cypher = """
            MATCH (src:Function), (sink:Function)
            WHERE (src.name CONTAINS $src_pat OR src.file_path CONTAINS $src_pat)
              AND (sink.name CONTAINS $sink_pat)
            MATCH path = shortestPath((src)-[:RESOLVED_CALLS*1..5]->(sink))
            RETURN [node in nodes(path) | node.name] AS call_path, length(path) AS depth
            LIMIT 10
            """
            records = session.run(cypher, src_pat=source_pattern, sink_pat=sink_pattern)
            paths = [{"path": " -> ".join(r["call_path"]), "depth": r["depth"]} for r in records]
            return {
                "source_pattern": source_pattern,
                "sink_pattern": sink_pattern,
                "potential_taint_paths": paths,
                "count": len(paths),
            }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@tool
def tool_search_codebase_semantic(
    query: str,
    limit: int = 5,
) -> Dict[str, Any]:
    """
    [Task #16] Performs hybrid semantic code search in Weaviate Cloud.
    """
    wv = _get_weaviate_client()
    if not wv:
        return {"error": "Weaviate client unavailable", "query": query}

    try:
        results = wv.search_code(query, limit=limit)
        return {
            "query": query,
            "results_count": len(results),
            "results": [
                {
                    "name": r.get("name"),
                    "type": r.get("chunk_type"),
                    "file_path": r.get("file_path"),
                    "docstring": r.get("docstring"),
                    "snippet": (r.get("content") or "")[:300] + "..." if r.get("content") and len(r.get("content")) > 300 else (r.get("content") or ""),
                }
                for r in results
            ],
        }
    except Exception as e:
        return {"error": str(e), "query": query}
    finally:
        wv.close()


@tool
def tool_query_test_traceability(
    target_symbol: str,
    max_depth: int = 3,
) -> Dict[str, Any]:
    """
    [Task #19] Finds test suites and test functions that exercise the target symbol.
    """
    db = _get_neo4j_session()
    if not db:
        return {"error": "Neo4j connection unavailable", "target_symbol": target_symbol}

    try:
        with db.driver.session() as session:
            cypher = """
            MATCH (test:Function)-[:RESOLVED_CALLS|CALLS*1..3]->(target)
            WHERE (target.name = $sym OR target.name ENDS WITH ('.' + $sym))
              AND (test.name STARTS WITH 'test_' OR test.file_path CONTAINS 'test')
            RETURN DISTINCT test.name AS test_name, test.file_path AS test_file
            LIMIT 30
            """
            records = session.run(cypher, sym=target_symbol)
            tests = [{"test_function": r["test_name"], "file": r["test_file"]} for r in records]
            return {
                "target_symbol": target_symbol,
                "test_count": len(tests),
                "tests": tests,
            }
    except Exception as e:
        return {"error": str(e), "target_symbol": target_symbol}
    finally:
        db.close()


@tool
def tool_query_api_endpoints(
    route_pattern: Optional[str] = None,
    http_method: Optional[str] = None,
) -> Dict[str, Any]:
    """
    [Task #20] Queries public API endpoints, route definitions, and HTTP contracts.
    """
    db = _get_neo4j_session()
    if not db:
        return {"error": "Neo4j connection unavailable"}

    try:
        with db.driver.session() as session:
            cypher = """
            MATCH (fn:Function)
            WHERE fn.is_endpoint = true OR fn.route_path IS NOT NULL
            RETURN fn.name AS handler_name, fn.route_path AS route, fn.http_method AS method, fn.file_path AS file_path
            LIMIT 50
            """
            records = session.run(cypher)
            endpoints = [
                {
                    "handler": r["handler_name"],
                    "route": r["route"] or "unknown",
                    "method": r["method"] or "ANY",
                    "file_path": r["file_path"],
                }
                for r in records
            ]
            return {
                "total_endpoints": len(endpoints),
                "endpoints": endpoints,
            }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


# -----------------------------------------------------------------------------
# Global Master Tool Registry
# -----------------------------------------------------------------------------

ALL_TOOLS = [
    tool_classify_intent,
    tool_traverse_call_graph,
    tool_calculate_blast_radius,
    tool_trace_parameter_lineage,
    tool_query_variable_and_state_references,
    tool_inspect_type_and_inheritance_hierarchy,
    tool_get_symbol_code_snippet,
    tool_analyze_architecture_coupling,
    tool_detect_orphan_and_dead_code,
    tool_trace_taint_and_security_paths,
    tool_search_codebase_semantic,
    tool_query_test_traceability,
    tool_query_api_endpoints,
]
