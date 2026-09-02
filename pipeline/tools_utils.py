"""
tools_utils.py — Data structures, enums, and task definitions for CodeNavigator tools.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class ExecutionStrategy(str, Enum):
    DETERMINISTIC_1_SHOT = "DETERMINISTIC_1_SHOT"  # 1 Turn (Atomic or Chained Composite)
    GUIDED_RECIPE = "GUIDED_RECIPE"                # 2-3 Turns (Branching / Conditional)
    REACT_FALLBACK = "REACT_FALLBACK"              # N Turns (Open-ended exploration)


class ExecutionType(str, Enum):
    ATOMIC = "atomic"        # Single direct DB query (e.g. Dead code, Module coupling)
    COMPOSITE = "composite"  # Backend-orchestrated multi-step pipeline (e.g. Param lineage)
    BRANCHING = "branching"  # Conditional decision-tree (e.g. Blast radius)
    OPEN_ENDED = "open_ended"# Unconstrained ReAct loop


@dataclass
class IntentClassificationResult:
    query: str
    task_id: Optional[int]
    task_name: str
    strategy: ExecutionStrategy
    execution_type: ExecutionType
    expected_turns: int                  # 1, 2-3, or -1 (variable)
    recommended_tools: List[str]         # Primary tool(s) to call
    allowed_tools: List[str]             # Filtered tool subset for token efficiency
    target_symbols: List[str]            # Extracted functions/classes/env vars
    workflow_recipe: Optional[str]       # Injected into prompt for Tier 2 branching
    confidence: float
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["strategy"] = self.strategy.value
        data["execution_type"] = self.execution_type.value
        return data


# Canonical mapping for all 20 Code Intelligence Tasks
TASK_DEFINITIONS: Dict[int, Dict[str, Any]] = {
    # =========================================================================
    # TIER 1: DETERMINISTIC 1-SHOT — ATOMIC (1 Turn, 1 Direct DB Query)
    # =========================================================================
    1: {
        "name": "Upstream Call Tracing (Caller Analysis)",
        "strategy": ExecutionStrategy.DETERMINISTIC_1_SHOT,
        "execution_type": ExecutionType.ATOMIC,
        "expected_turns": 1,
        "recommended_tools": ["traverse_call_graph"],
        "patterns": [
            r"who calls\b", r"callers? of\b", r"where is .* called",
            r"call chain leading into", r"endpoints? .* invoke", r"incoming calls?"
        ],
        "recipe": None,
    },
    2: {
        "name": "Downstream Call Tracing (Callee / Dependency Analysis)",
        "strategy": ExecutionStrategy.DETERMINISTIC_1_SHOT,
        "execution_type": ExecutionType.ATOMIC,
        "expected_turns": 1,
        "recommended_tools": ["traverse_call_graph"],
        "patterns": [
            r"what does .* call", r"callees? of\b", r"functions? does .* invoke",
            r"internal functions does .* execute", r"downstream dependencies of", r"outgoing calls?"
        ],
        "recipe": None,
    },
    5: {
        "name": "Class Instance Attribute Mutability (self.)",
        "strategy": ExecutionStrategy.DETERMINISTIC_1_SHOT,
        "execution_type": ExecutionType.ATOMIC,
        "expected_turns": 1,
        "recommended_tools": ["query_variable_and_state_references"],
        "patterns": [
            r"self\.\w+", r"instance attribute", r"which methods .* mutate self\.",
            r"is self\..* initialized in __init__", r"where is self\..* modified"
        ],
        "recipe": None,
    },
    6: {
        "name": "Inherited Class Attribute Resolution (super())",
        "strategy": ExecutionStrategy.DETERMINISTIC_1_SHOT,
        "execution_type": ExecutionType.ATOMIC,
        "expected_turns": 1,
        "recommended_tools": ["inspect_type_and_inheritance_hierarchy"],
        "patterns": [
            r"inherited (from|attribute|method)", r"parent class of", r"super\(\)",
            r"does .* override any instance attributes", r"where is .* defined in parent"
        ],
        "recipe": None,
    },
    7: {
        "name": "Global & Module-Level Variable Audit",
        "strategy": ExecutionStrategy.DETERMINISTIC_1_SHOT,
        "execution_type": ExecutionType.ATOMIC,
        "expected_turns": 1,
        "recommended_tools": ["query_variable_and_state_references"],
        "patterns": [
            r"global (variable|state|constant)", r"module(-|\s)level (variable|constant)",
            r"write(s)? to .* global", r"where is .* constant defined and used"
        ],
        "recipe": None,
    },
    8: {
        "name": "Local Variable Initialization & Constant Default Audits",
        "strategy": ExecutionStrategy.DETERMINISTIC_1_SHOT,
        "execution_type": ExecutionType.ATOMIC,
        "expected_turns": 1,
        "recommended_tools": ["get_symbol_code_snippet"],
        "patterns": [
            r"hardcoded default", r"default (initial )?value of", r"initial value does .* get assigned",
            r"default timeout", r"default parameter value"
        ],
        "recipe": None,
    },
    9: {
        "name": "Environment & Configuration Audit",
        "strategy": ExecutionStrategy.DETERMINISTIC_1_SHOT,
        "execution_type": ExecutionType.ATOMIC,
        "expected_turns": 1,
        "recommended_tools": ["query_variable_and_state_references"],
        "patterns": [
            r"env(ironment)? variable", r"config(uration)? parameter", r"secret usage",
            r"is .* read with a default fallback", r"list all env.* variables",
            r"\b[A-Z0-9_]{3,}_(KEY|SECRET|TOKEN|URL|PORT|HOST|ENV|CONFIG|PWD|PASSWORD)\b",
            r"where (in .*)?is [A-Z0-9_]+ read"
        ],
        "recipe": None,
    },
    12: {
        "name": "Module & Architecture Coupling",
        "strategy": ExecutionStrategy.DETERMINISTIC_1_SHOT,
        "execution_type": ExecutionType.ATOMIC,
        "expected_turns": 1,
        "recommended_tools": ["analyze_architecture_coupling"],
        "patterns": [
            r"circular (imports?|dependencies)", r"module coupling", r"does .* module depend on",
            r"architectural boundaries", r"third(-|\s)party libraries .* versus internal"
        ],
        "recipe": None,
    },
    13: {
        "name": "Dead Code & Orphan Identification",
        "strategy": ExecutionStrategy.DETERMINISTIC_1_SHOT,
        "execution_type": ExecutionType.ATOMIC,
        "expected_turns": 1,
        "recommended_tools": ["detect_orphan_and_dead_code"],
        "patterns": [
            r"dead code", r"orphan(ed)? (functions?|classes?|code)", r"unused (functions?|imports?|code)",
            r"zero incoming callers", r"uncalled functions"
        ],
        "recipe": None,
    },
    17: {
        "name": "Type & Class Hierarchy Inspection",
        "strategy": ExecutionStrategy.DETERMINISTIC_1_SHOT,
        "execution_type": ExecutionType.ATOMIC,
        "expected_turns": 1,
        "recommended_tools": ["inspect_type_and_inheritance_hierarchy"],
        "patterns": [
            r"which classes inherit from", r"class hierarchy", r"what fields are defined on .* (struct|class|dataclass)",
            r"where is .* enum referenced", r"subclasses of"
        ],
        "recipe": None,
    },
    20: {
        "name": "API Contract & Interface Surface",
        "strategy": ExecutionStrategy.DETERMINISTIC_1_SHOT,
        "execution_type": ExecutionType.ATOMIC,
        "expected_turns": 1,
        "recommended_tools": ["query_api_endpoints"],
        "patterns": [
            r"what rest endpoints", r"what request body .* expects?", r"api surface",
            r"deprecated api endpoints", r"http methods? do they use"
        ],
        "recipe": None,
    },

    # =========================================================================
    # TIER 1: DETERMINISTIC 1-SHOT — COMPOSITE (1 Turn, Chained in Backend)
    # =========================================================================
    4: {
        "name": "Function Parameter & Argument Lineage",
        "strategy": ExecutionStrategy.DETERMINISTIC_1_SHOT,
        "execution_type": ExecutionType.COMPOSITE,
        "expected_turns": 1,
        "recommended_tools": ["trace_parameter_lineage"],  # Runs: Neo4j (Callers) -> Weaviate (Caller Snippets)
        "patterns": [
            r"parameter (lineage|mapping|flow)", r"how does .* parameter .* get mapped",
            r"which callers? pass (none|missing|null|invalid) arguments?", r"argument lineage"
        ],
        "recipe": None,
    },
    16: {
        "name": "Business Logic & Concept Explanation",
        "strategy": ExecutionStrategy.DETERMINISTIC_1_SHOT,
        "execution_type": ExecutionType.COMPOSITE,
        "expected_turns": 1,
        "recommended_tools": ["search_codebase_semantic_with_context"],  # Runs: Weaviate Search -> Neo4j 1-hop context
        "patterns": [
            r"how does (this|the) .* feature work", r"step(-|\s)by(-|\s)step workflow for",
            r"where is the logic for .* implemented", r"explain (the )?business logic",
            r"how is .* calculated for"
        ],
        "recipe": None,
    },
    19: {
        "name": "Test Coverage & Traceability",
        "strategy": ExecutionStrategy.DETERMINISTIC_1_SHOT,
        "execution_type": ExecutionType.COMPOSITE,
        "expected_turns": 1,
        "recommended_tools": ["query_test_traceability_composite"],  # Runs: Neo4j (Test callers) -> Weaviate (Assertions)
        "patterns": [
            r"which test files? (actually )?invoke", r"tests? (do I need to|to) re(-|\s)?run",
            r"are there any .* lack(ing)? .* test", r"test coverage for"
        ],
        "recipe": None,
    },

    # =========================================================================
    # TIER 2: GUIDED RECIPE — BRANCHING / CONDITIONAL (2-3 Turns)
    # =========================================================================
    3: {
        "name": "Blast Radius & Impact Analysis",
        "strategy": ExecutionStrategy.GUIDED_RECIPE,
        "execution_type": ExecutionType.BRANCHING,
        "expected_turns": 2,
        "recommended_tools": ["calculate_blast_radius", "query_api_endpoints", "query_test_traceability"],
        "patterns": [
            r"blast radius", r"impact analysis", r"what (will|might) break if I (change|modify|delete|rename)",
            r"if I change .* what other files break", r"which endpoints will be impacted"
        ],
        "recipe": (
            "1. Run `calculate_blast_radius(changed_symbols)` to identify all transitive dependents.\n"
            "2. If affected nodes include API endpoints, run `query_api_endpoints()` to check if public contracts break.\n"
            "3. If core services are affected, run `query_test_traceability()` to output test suites needing re-execution."
        ),
    },
    10: {
        "name": "Data Flow & Variable Expression Lineage",
        "strategy": ExecutionStrategy.GUIDED_RECIPE,
        "execution_type": ExecutionType.BRANCHING,
        "expected_turns": 2,
        "recommended_tools": ["get_symbol_code_snippet", "traverse_call_graph"],
        "patterns": [
            r"what (inputs|formulas) determine .* value", r"how is .* calculated",
            r"if .* changes which downstream variables .* are affected", r"expression lineage"
        ],
        "recipe": (
            "1. Fetch target function snippet via `get_symbol_code_snippet()` to extract the local formula.\n"
            "2. If input variables are parameters passed from external callers, branch to `traverse_call_graph(direction='incoming')`.\n"
            "3. Synthesize the complete end-to-end derivation formula."
        ),
    },
    11: {
        "name": "State Mutation & Reassignment Tracing",
        "strategy": ExecutionStrategy.GUIDED_RECIPE,
        "execution_type": ExecutionType.BRANCHING,
        "expected_turns": 2,
        "recommended_tools": ["get_symbol_code_snippet", "query_variable_and_state_references"],
        "patterns": [
            r"where .* does .* get reassigned", r"mutate(s)? .* in(-|\s)place",
            r"\.append\(|\.pop\(|\.update\(|\.extend\(", r"how many times .* variable .* change"
        ],
        "recipe": (
            "1. Query methods referencing the target attribute using `query_variable_and_state_references()`.\n"
            "2. Fetch snippets for all modifying methods.\n"
            "3. Sequence in-place mutations (`.append`, `.pop`) and reassignments in execution order."
        ),
    },
    14: {
        "name": "Security & Vulnerability Path Tracking (Taint Analysis)",
        "strategy": ExecutionStrategy.GUIDED_RECIPE,
        "execution_type": ExecutionType.BRANCHING,
        "expected_turns": 3,
        "recommended_tools": ["trace_taint_and_security_paths", "get_symbol_code_snippet", "traverse_call_graph"],
        "patterns": [
            r"taint (analysis|path)", r"sql injection|raw sql", r"unsanitized (user )?input",
            r"unauthenticated (access|endpoints?)", r"hardcoded (api key|secret|password)"
        ],
        "recipe": (
            "1. Run `trace_taint_and_security_paths(source, sink)` to identify untrusted input paths.\n"
            "2. Fetch intermediate call site snippets to check for sanitizers/validators.\n"
            "3. If no sanitizer is present along the path, flag the vulnerability with exact file/line proof."
        ),
    },
    15: {
        "name": "Error Handling & Exception Propagation",
        "strategy": ExecutionStrategy.GUIDED_RECIPE,
        "execution_type": ExecutionType.BRANCHING,
        "expected_turns": 2,
        "recommended_tools": ["get_symbol_code_snippet", "traverse_call_graph"],
        "patterns": [
            r"swallow(ed)? (error|exception)", r"bare except", r"try(-|\s)catch",
            r"if .* throws an exception .* what fallback", r"which functions catch"
        ],
        "recipe": (
            "1. Fetch the target function snippet to locate `try/except` blocks.\n"
            "2. If exception propagates unhandled, trace downstream/upstream callers via `traverse_call_graph()`.\n"
            "3. Check whether upstream handlers catch or re-raise the exception."
        ),
    },
    18: {
        "name": "Performance & Bottleneck Spotting",
        "strategy": ExecutionStrategy.GUIDED_RECIPE,
        "execution_type": ExecutionType.BRANCHING,
        "expected_turns": 2,
        "recommended_tools": ["get_symbol_code_snippet", "traverse_call_graph"],
        "patterns": [
            r"n\+1 (query|problem)", r"(database |db )?queries (executed |run )?inside (a )?(for |while )?loops?",
            r"inside (a )?(for |while )?loops?", r"synchronous (http|network) calls",
            r"performance (bottleneck|issue)", r"blocking i/o"
        ],
        "recipe": (
            "1. Fetch the function snippet via `get_symbol_code_snippet()`.\n"
            "2. Inspect for loops (`for`, `while`) wrapping I/O calls.\n"
            "3. If loops call helper methods, use `traverse_call_graph(direction='outgoing')` to check if helpers perform DB/network operations."
        ),
    },
}
