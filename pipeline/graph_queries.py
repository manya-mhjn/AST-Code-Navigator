"""
graph_queries.py — Graph-only structural intelligence queries on Neo4j.

Executes architectural queries that ONLY a Knowledge Graph can perform:
1. Impact Analysis / Blast Radius (Multi-hop callers)
2. Execution Path Tracing (UI entrypoint -> API call)
3. Dead Code Detection (Uncalled functions)
4. Class Instantiation & Method Mapping
"""

from dotenv import load_dotenv
load_dotenv(override=True)

import sys
from pipeline.orchestrator import _require_env
from pipeline.neo4j_sink import Neo4jCodeGraphIngestor


class CodeGraphIntelligence:
    def __init__(self):
        self.neo4j_db = Neo4jCodeGraphIngestor(
            uri=_require_env("NEO4J_URI"),
            auth=(_require_env("NEO4J_USER"), _require_env("NEO4J_PASSWORD"))
        )

    def close(self):
        self.neo4j_db.close()

    def impact_analysis(self, function_name: str = "load_adventure"):
        """
        Query 1: Impact Analysis (Blast Radius).
        Finds all functions across all files that depend on a given function (up to 3 hops deep).
        Vector DB CANNOT do multi-hop dependency tracing!
        """
        print("\n" + "=" * 70)
        print(f" IMPACT ANALYSIS (Blast Radius) FOR: '{function_name}'")
        print("=" * 70)

        with self.neo4j_db.driver.session() as session:
            result = session.run("""
                MATCH path = (dependent)-[:RESOLVED_CALLS|CALLS*1..3]->(target)
                WHERE target.name = $fn_name OR target.id ENDS WITH ('.' + $fn_name)
                RETURN 
                    [node IN nodes(path) | coalesce(node.name, node.id)] AS ExecutionChain,
                    length(path) AS Depth
                ORDER BY Depth ASC
                LIMIT 15
            """, fn_name=function_name)

            found = False
            for rec in result:
                found = True
                chain = " -> ".join(reversed(rec["ExecutionChain"]))
                print(f"  [Hop Depth {rec['Depth']}] {chain}")

            if not found:
                # Fallback check for any calls
                result_any = session.run("""
                    MATCH (caller)-[r:CALLS|RESOLVED_CALLS]->(t)
                    WHERE t.name = $fn_name OR t.id ENDS WITH ('.' + $fn_name)
                    RETURN caller.id AS Caller, type(r) AS Edge, t.id AS Target
                """, fn_name=function_name)
                for rec in result_any:
                    found = True
                    print(f"  Direct Dependency: ({rec['Caller']}) -[:{rec['Edge']}]-> ({rec['Target']})")

            if not found:
                print(f"  No direct or indirect dependencies found calling '{function_name}'.")

    def trace_execution_paths(self):
        """
        Query 2: Execution Path Tracing.
        Traces how control flows from File entrypoints down through functions into API calls.
        """
        print("\n" + "=" * 70)
        print(" EXECUTION PATH TRACING (File -> Function -> Function/API)")
        print("=" * 70)

        with self.neo4j_db.driver.session() as session:
            result = session.run("""
                MATCH (f:File)-[:CONTAINS_FUNCTION]->(fn:Function)-[r:CALLS|RESOLVED_CALLS]->(target)
                RETURN f.name AS File, fn.name AS Function, type(r) AS Relationship, target.name AS Target
                LIMIT 10
            """)
            for rec in result:
                print(f"  File [{rec['File']}] :: {rec['Function']}() -[:{rec['Relationship']}]-> {rec['Target']}()")

    def class_hierarchy_and_instantiation(self):
        """
        Query 3: Class Instantiations & Method Structure.
        Shows which classes are instantiated by which files and what methods they contain.
        """
        print("\n" + "=" * 70)
        print(" CLASS INSTANTIATIONS & METHOD HIERARCHY")
        print("=" * 70)

        with self.neo4j_db.driver.session() as session:
            result = session.run("""
                MATCH (f:File)-[r:INSTANTIATES]->(c:Class)
                OPTIONAL MATCH (c)-[:HAS_METHOD]->(m:Function)
                RETURN f.name AS InstantiatorFile, c.name AS ClassName, collect(m.name) AS Methods
                LIMIT 10
            """)
            found = False
            for rec in result:
                found = True
                methods_str = ", ".join(rec["Methods"]) if rec["Methods"] else "None"
                print(f"  File [{rec['InstantiatorFile']}] instantiates Class [{rec['ClassName']}] (Methods: {methods_str})")

            if not found:
                # Direct class definition query
                result_classes = session.run("""
                    MATCH (c:Class)-[:HAS_METHOD]->(m:Function)
                    RETURN c.name AS ClassName, collect(m.name) AS Methods
                    LIMIT 10
                """)
                for rec in result_classes:
                    print(f"  Class [{rec['ClassName']}] contains Methods: {', '.join(rec['Methods'])}")

    def detect_unused_functions(self):
        """
        Query 4: Dead Code Detection.
        Finds functions that are never called anywhere in the codebase.
        """
        print("\n" + "=" * 70)
        print(" DEAD CODE / UNCALLED FUNCTIONS DETECTION")
        print("=" * 70)

        with self.neo4j_db.driver.session() as session:
            result = session.run("""
                MATCH (fn:Function)
                WHERE NOT ( ()-[:RESOLVED_CALLS|CALLS]->(fn) )
                AND NOT fn.name STARTS WITH '__'
                RETURN fn.name AS UnusedFunction, fn.file_path AS File
                LIMIT 10
            """)
            for rec in result:
                print(f"  * Unused Function: {rec['UnusedFunction']}() in {rec['File']}")


if __name__ == "__main__":
    intelligence = CodeGraphIntelligence()
    target_fn = sys.argv[1] if len(sys.argv) > 1 else "load_adventure"

    intelligence.impact_analysis(target_fn)
    intelligence.trace_execution_paths()
    intelligence.class_hierarchy_and_instantiation()
    intelligence.detect_unused_functions()

    intelligence.close()
