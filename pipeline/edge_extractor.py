"""
Edge extraction module for Python ASTs.
"""

from pipeline.parser import ParsedFile
from pipeline.utils import detect_env_var

class ASTEdgeExtractor:
    """
    A dedicated, production-ready Edge Extractor for Python ASTs.
    Extracts all structural relationship edges for Neo4j knowledge graph ingestion:
    - (File)-[:IMPORTS]->(Import)
    - (File)-[:CONTAINS_CLASS]->(Class)
    - (Class)-[:INHERITS_FROM]->(BaseClass)
    - (Class)-[:HAS_CLASS_ATTRIBUTE]->(ClassAttribute)
    - (Class)-[:HAS_INSTANCE_ATTRIBUTE]->(InstanceAttribute)
    - (Class)-[:HAS_METHOD]->(Function)
    - (File)-[:CONTAINS_FUNCTION]->(Function)
    - (Function)-[:HAS_PARAMETER]->(Parameter)
    - (File)-[:CONTAINS_VARIABLE]->(Variable)
    - (File / Class / Function)-[:USES_ENV]->(EnvVar)
    - (File / Class / Function)-[:CALLS]->(Target)
    """

    def extract_edges(self, parsed_file: ParsedFile, nodes: dict = None) -> list:
        file_path = parsed_file.file_path
        root_node = parsed_file.root_node

        edges = []

        # STRUCTURAL EDGES DERIVED FROM EXTRACTED NODES
        if nodes:
            for imp in nodes.get("Import", []):
                edges.append({"src": file_path, "edge": "IMPORTS", "target": imp["id"]})

            for cls in nodes.get("Class", []):
                edges.append({"src": file_path, "edge": "CONTAINS_CLASS", "target": cls["id"]})
                for base in cls.get("bases", []):
                    edges.append({"src": cls["id"], "edge": "INHERITS_FROM", "target": base})

            for fn in nodes.get("Function", []):
                if not fn.get("is_method"):
                    edges.append({"src": file_path, "edge": "CONTAINS_FUNCTION", "target": fn["id"]})
                else:
                    class_id = f"{file_path}::{fn['class_name']}"
                    edges.append({"src": class_id, "edge": "HAS_METHOD", "target": fn["id"]})

            for var in nodes.get("Variable", []):
                edges.append({"src": file_path, "edge": "CONTAINS_VARIABLE", "target": var["id"]})

            for param in nodes.get("Parameter", []):
                edges.append({"src": param["function_id"], "edge": "HAS_PARAMETER", "target": param["id"]})

            for cattr in nodes.get("ClassAttribute", []):
                edges.append({"src": cattr["class_id"], "edge": "HAS_CLASS_ATTRIBUTE", "target": cattr["id"]})

            for iattr in nodes.get("InstanceAttribute", []):
                edges.append({"src": iattr["class_id"], "edge": "HAS_INSTANCE_ATTRIBUTE", "target": iattr["id"]})

        # ALL CALLS & USES_ENV EDGES ACROSS ALL SCOPES
        self._extract_all_calls_and_envs(root_node, file_path, edges)

        return edges

    def _extract_all_calls_and_envs(self, root_node, file_path: str, edges: list):
        def visit(node, current_scope_id=file_path, current_class_name=None):
            if node.type == "class_definition":
                name_n = node.child_by_field_name("name")
                c_name = name_n.text.decode("utf8") if name_n else None
                class_id = f"{file_path}::{c_name}" if c_name else file_path

                body = node.child_by_field_name("body")
                if body:
                    for child in body.children:
                        visit(child, current_scope_id=class_id, current_class_name=c_name)
                return

            elif node.type == "function_definition":
                name_n = node.child_by_field_name("name")
                if name_n:
                    fn_name = name_n.text.decode("utf8")
                    if current_class_name:
                        func_id = f"{file_path}::{current_class_name}.{fn_name}"
                    else:
                        func_id = f"{file_path}::{fn_name}"

                    body = node.child_by_field_name("body")
                    if body:
                        for child in body.children:
                            visit(child, current_scope_id=func_id, current_class_name=None)
                    return

            if node.type == "call":
                func_n = node.child_by_field_name("function")
                if func_n:
                    target_name = None
                    if func_n.type == "identifier":
                        target_name = func_n.text.decode("utf8")
                    elif func_n.type == "attribute":
                        obj_n = func_n.child_by_field_name("object")
                        attr_n = func_n.child_by_field_name("attribute")
                        if obj_n and attr_n:
                            target_name = f"{obj_n.text.decode('utf8')}.{attr_n.text.decode('utf8')}"

                    if target_name:
                        edges.append({
                            "src": current_scope_id,
                            "edge": "CALLS",
                            "target": target_name,
                            "line": node.start_point[0] + 1
                        })

            env_name = detect_env_var(node)
            if env_name:
                edges.append({
                    "src": current_scope_id,
                    "edge": "USES_ENV",
                    "target": f"ENV::{env_name}"
                })

            for child in node.children:
                visit(child, current_scope_id=current_scope_id, current_class_name=current_class_name)

        visit(root_node)
