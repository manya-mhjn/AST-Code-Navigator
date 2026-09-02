"""
Edge extraction module for Python ASTs.
"""

from pipeline.utils import _extract_instance_attribute_usage, _get_func_id, _get_class_info, \
    _extract_variable_usage, _extract_env_edge, _extract_call_edge, _collect_scope_vars
from pipeline.parser import ParsedFile

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

            # EnvVarUsage — now identical pattern:
            for usage in nodes.get("EnvVarUsage", []):
                edges.append({"src": usage["scope_id"], "edge": "USES_ENV", "target": f"ENV::{usage['env_name']}"})

        # ALL CALLS & USES_ENV EDGES ACROSS ALL SCOPES
        self._extract_all_calls_and_envs(root_node, file_path, edges)

        return edges

    def _extract_all_calls_and_envs(self, root_node, file_path: str, edges: list):
        def visit(node, current_scope_id=file_path, current_class_name=None, local_vars=None, explicit_globals=None):
            if local_vars is None:
                local_vars = set()
            if explicit_globals is None:
                explicit_globals = set()
            if node.type == "class_definition":
                c_name, class_id = _get_class_info(node, file_path)
                body = node.child_by_field_name("body")
                if body:
                    for child in body.children:
                        visit(child, current_scope_id=class_id, current_class_name=c_name, local_vars=local_vars, explicit_globals=explicit_globals)
                return
            elif node.type == "function_definition":
                func_id = _get_func_id(node, file_path, current_class_name)
                body = node.child_by_field_name("body")
                if body:
                    # Collect locals and explicit globals for THIS function block specifically
                    new_explicit_globals, new_local_vars = _collect_scope_vars(node)
                    
                    for child in body.children:
                        # Enter new scope, passing the new scope's variables down
                        visit(child, current_scope_id=func_id, current_class_name=None, local_vars=new_local_vars, explicit_globals=new_explicit_globals)
                return
            # Unified usage checks for the current node
            _extract_call_edge(node, current_scope_id, edges)
            _extract_env_edge(node, current_scope_id, edges)
            _extract_variable_usage(node, current_scope_id, local_vars, edges)
            _extract_instance_attribute_usage(node, current_scope_id, edges)
            # Continue traversing children
            for child in node.children:
                visit(child, current_scope_id=current_scope_id, current_class_name=current_class_name, local_vars=local_vars, explicit_globals=explicit_globals)
        visit(root_node)
