"""
neo4j_sink.py — Neo4j batch ingestor for the Code Knowledge Graph.

Handles high-performance batch insertion of Nodes and Edges
using Cypher UNWIND transactions.
"""

from neo4j import GraphDatabase


class Neo4jCodeGraphIngestor:
    """
    Production-ready Neo4j Batch Ingestor for Code Knowledge Graphs.
    Handles high-performance batch insertion of Nodes and Edges using Cypher UNWIND transactions.
    """

    def __init__(self, uri: str, auth: tuple[str, str]):
        self.driver = GraphDatabase.driver(uri, auth=auth)

    def close(self):
        self.driver.close()

    def setup_database_indexes(self):
        """Creates uniqueness constraints and indexes for high-speed node resolution."""
        queries = [
            "CREATE CONSTRAINT file_id_unique IF NOT EXISTS FOR (f:File) REQUIRE f.id IS UNIQUE",
            "CREATE CONSTRAINT class_id_unique IF NOT EXISTS FOR (c:Class) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT func_id_unique IF NOT EXISTS FOR (fn:Function) REQUIRE fn.id IS UNIQUE",
            "CREATE CONSTRAINT var_id_unique IF NOT EXISTS FOR (v:Variable) REQUIRE v.id IS UNIQUE",
            "CREATE CONSTRAINT env_id_unique IF NOT EXISTS FOR (e:EnvVar) REQUIRE e.id IS UNIQUE",
            "CREATE CONSTRAINT import_id_unique IF NOT EXISTS FOR (i:Import) REQUIRE i.id IS UNIQUE",
            "CREATE CONSTRAINT param_id_unique IF NOT EXISTS FOR (p:Parameter) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT class_attr_id_unique IF NOT EXISTS FOR (ca:ClassAttribute) REQUIRE ca.id IS UNIQUE",
            "CREATE CONSTRAINT inst_attr_id_unique IF NOT EXISTS FOR (ia:InstanceAttribute) REQUIRE ia.id IS UNIQUE",
            "CREATE INDEX target_name_idx IF NOT EXISTS FOR (t:Target) ON (t.name)"
        ]
        with self.driver.session() as session:
            for q in queries:
                session.run(q)
        print("Neo4j Indexes and Constraints Configured.")

    def ingest_nodes(self, nodes_dict: dict):
        """Ingests all extracted Node categories in UNWIND batches."""
        with self.driver.session() as session:
            # 1. File Nodes
            if nodes_dict.get("File"):
                session.run("""
                    UNWIND $batch AS row
                    MERGE (f:File {id: row.id})
                    SET f.name = row.name, f.file_path = row.file_path
                """, batch=nodes_dict["File"])

            # 2. Class Nodes
            if nodes_dict.get("Class"):
                session.run("""
                    UNWIND $batch AS row
                    MERGE (c:Class {id: row.id})
                    SET c += row
                """, batch=nodes_dict["Class"])

            # 3. Function Nodes
            if nodes_dict.get("Function"):
                session.run("""
                    UNWIND $batch AS row
                    MERGE (fn:Function {id: row.id})
                    SET fn += row
                """, batch=nodes_dict["Function"])

            # 4. Variable Nodes
            if nodes_dict.get("Variable"):
                session.run("""
                    UNWIND $batch AS row
                    MERGE (v:Variable {id: row.id})
                    SET v += row
                """, batch=nodes_dict["Variable"])

            # 5. EnvVar Nodes
            if nodes_dict.get("EnvVar"):
                session.run("""
                    UNWIND $batch AS row
                    MERGE (e:EnvVar {id: row.id})
                    SET e += row
                """, batch=nodes_dict["EnvVar"])

            # 6. Import Nodes
            if nodes_dict.get("Import"):
                session.run("""
                    UNWIND $batch AS row
                    MERGE (i:Import {id: row.id})
                    SET i += row
                """, batch=nodes_dict["Import"])

            # 7. Parameter Nodes
            if nodes_dict.get("Parameter"):
                session.run("""
                    UNWIND $batch AS row
                    MERGE (p:Parameter {id: row.id})
                    SET p += row
                """, batch=nodes_dict["Parameter"])

            # 8. ClassAttribute Nodes
            if nodes_dict.get("ClassAttribute"):
                session.run("""
                    UNWIND $batch AS row
                    MERGE (ca:ClassAttribute {id: row.id})
                    SET ca += row
                """, batch=nodes_dict["ClassAttribute"])

            # 9. InstanceAttribute Nodes
            if nodes_dict.get("InstanceAttribute"):
                session.run("""
                    UNWIND $batch AS row
                    MERGE (ia:InstanceAttribute {id: row.id})
                    SET ia += row
                """, batch=nodes_dict["InstanceAttribute"])

            
    

    def ingest_edges(self, edges_list: list):
        """Groups edges by relationship type and ingests them into Neo4j."""
        grouped_edges = {}
        for edge in edges_list:
            edge_type = edge["edge"]
            grouped_edges.setdefault(edge_type, []).append(edge)

        with self.driver.session() as session:
            # 1. IMPORTS
            if "IMPORTS" in grouped_edges:
                session.run("""
                    UNWIND $batch AS row
                    MATCH (f:File {id: row.src})
                    MATCH (i:Import {id: row.target})
                    MERGE (f)-[:IMPORTS]->(i)
                """, batch=grouped_edges["IMPORTS"])

            # 2. CONTAINS_CLASS
            if "CONTAINS_CLASS" in grouped_edges:
                session.run("""
                    UNWIND $batch AS row
                    MATCH (f:File {id: row.src})
                    MATCH (c:Class {id: row.target})
                    MERGE (f)-[:CONTAINS_CLASS]->(c)
                """, batch=grouped_edges["CONTAINS_CLASS"])

            # 3. CONTAINS_FUNCTION
            if "CONTAINS_FUNCTION" in grouped_edges:
                session.run("""
                    UNWIND $batch AS row
                    MATCH (f:File {id: row.src})
                    MATCH (fn:Function {id: row.target})
                    MERGE (f)-[:CONTAINS_FUNCTION]->(fn)
                """, batch=grouped_edges["CONTAINS_FUNCTION"])

            # 4. CONTAINS_VARIABLE
            if "CONTAINS_VARIABLE" in grouped_edges:
                session.run("""
                    UNWIND $batch AS row
                    MATCH (f:File {id: row.src})
                    MATCH (v:Variable {id: row.target})
                    MERGE (f)-[:CONTAINS_VARIABLE]->(v)
                """, batch=grouped_edges["CONTAINS_VARIABLE"])

            # 5. USES_ENV
            if "USES_ENV" in grouped_edges:
                session.run("""
                    UNWIND $batch AS row
                    MATCH (src) WHERE src.id = row.src
                    MATCH (e:EnvVar {id: row.target})
                    MERGE (src)-[:USES_ENV]->(e)
                """, batch=grouped_edges["USES_ENV"])

            # 6. CALLS
            if "CALLS" in grouped_edges:
                session.run("""
                    UNWIND $batch AS row
                    MATCH (src) WHERE src.id = row.src
                    MERGE (target:Target {name: row.target})
                    MERGE (src)-[r:CALLS {line: row.line}]->(target)
                """, batch=grouped_edges["CALLS"])

            # 7. HAS_METHOD
            if "HAS_METHOD" in grouped_edges:
                session.run("""
                    UNWIND $batch AS row
                    MATCH (c:Class {id: row.src})
                    MATCH (fn:Function {id: row.target})
                    MERGE (c)-[:HAS_METHOD]->(fn)
                """, batch=grouped_edges["HAS_METHOD"])

            # 8. INHERITS_FROM
            if "INHERITS_FROM" in grouped_edges:
                session.run("""
                    UNWIND $batch AS row
                    MATCH (c:Class {id: row.src})
                    MERGE (base:Class {name: row.target})
                    MERGE (c)-[:INHERITS_FROM]->(base)
                """, batch=grouped_edges["INHERITS_FROM"])

            # 9. HAS_PARAMETER
            if "HAS_PARAMETER" in grouped_edges:
                session.run("""
                    UNWIND $batch AS row
                    MATCH (fn:Function {id: row.src})
                    MATCH (p:Parameter {id: row.target})
                    MERGE (fn)-[:HAS_PARAMETER]->(p)
                """, batch=grouped_edges["HAS_PARAMETER"])

            # 10. HAS_CLASS_ATTRIBUTE
            if "HAS_CLASS_ATTRIBUTE" in grouped_edges:
                session.run("""
                    UNWIND $batch AS row
                    MATCH (c:Class {id: row.src})
                    MATCH (ca:ClassAttribute {id: row.target})
                    MERGE (c)-[:HAS_CLASS_ATTRIBUTE]->(ca)
                """, batch=grouped_edges["HAS_CLASS_ATTRIBUTE"])

            # 11. HAS_INSTANCE_ATTRIBUTE
            if "HAS_INSTANCE_ATTRIBUTE" in grouped_edges:
                session.run("""
                    UNWIND $batch AS row
                    MATCH (c:Class {id: row.src})
                    MATCH (ia:InstanceAttribute {id: row.target})
                    MERGE (c)-[:HAS_INSTANCE_ATTRIBUTE]->(ia)
                """, batch=grouped_edges["HAS_INSTANCE_ATTRIBUTE"])

            # 12. USES_VARIABLE (Raw)
            if "USES_VARIABLE" in grouped_edges:
                session.run("""
                    UNWIND $batch AS row
                    MATCH (src) WHERE src.id = row.src
                    MERGE (target:RawVariable {name: row.target})
                    MERGE (src)-[:USES_VARIABLE]->(target)
                """, batch=grouped_edges["USES_VARIABLE"])

            # 13. USES_INSTANCE_ATTRIBUTE (Raw)
            if "USES_INSTANCE_ATTRIBUTE" in grouped_edges:
                session.run("""
                    UNWIND $batch AS row
                    MATCH (src) WHERE src.id = row.src
                    MERGE (target:RawInstanceAttribute {name: row.target})
                    MERGE (src)-[:USES_INSTANCE_ATTRIBUTE]->(target)
                """, batch=grouped_edges["USES_INSTANCE_ATTRIBUTE"])
