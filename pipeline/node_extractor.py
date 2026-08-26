"""
Node Extractor module.
Extracts structural nodes from a Python AST for code graph ingestion.
"""

import os
from tree_sitter import Language, Query, QueryCursor
import tree_sitter_python as tspython
from pipeline.utils import _detect_env_var

from pipeline.parser import ParsedFile
from pipeline.utils import is_internal, _extract_all_env_vars

class ASTNodeExtractor:
    """
    A dedicated fetcher using Tree-sitter Queries (S-expressions) to extract 
    structural nodes from a Python AST for code graph (Neo4j) ingestion.
    """

    def __init__(self):
        # Compatible with modern tree-sitter v0.22+ Python bindings
        self.language = Language(tspython.language())

        # Define flat & composite S-expression Queries
        self.queries = {
            "classes": Query(self.language, """
                (class_definition) @class.def
            """),
            "functions": Query(self.language, """
                (function_definition) @function.def
            """),
            "global_vars": Query(self.language, """
                (module
                    [
                        ;; 1. Standard & Multi-Target Top-Level Assignments (e.g., x = 1 or x = y = 1)
                        (expression_statement
                        (assignment
                            left: [
                            (identifier) @var.name
                            (_ (identifier) @var.name)
                            ]
                        )
                        )

                        ;; 2. Tuple / List / Destructuring Unpacking (e.g., HOST, PORT = \"localhost\", 8080)
                        (expression_statement
                        (assignment
                            left: [
                            (pattern_list (identifier) @var.name)
                            (tuple_pattern (identifier) @var.name)
                            (list_pattern (identifier) @var.name)
                            ]
                        )
                        )

                        ;; 4. Augmented Assignments (e.g., TOTAL_COUNT += 1)
                        (expression_statement
                        (augmented_assignment
                            left: (identifier) @var.name
                        )
                        )

                        ;; 5. Python 3.12+ Type Aliases (e.g., type UserID = int)
                        (type_alias_statement
                        (type (identifier) @var.name)
                        )

                        ;; 6. Global Variables inside Top-Level 'if' blocks
                        (if_statement
                        consequence: (block
                            (expression_statement
                            [
                                (assignment left: [(identifier) @var.name (_ (identifier) @var.name)])
            
                            ]
                            )
                        )
                        alternative: (block
                            (expression_statement
                            [
                                (assignment left: [(identifier) @var.name (_ (identifier) @var.name)])
                    
                            ]
                            )
                        )?
                        )

                        ;; 7. Global Variables declared inside functions via 'global' keyword
                        (_
                        (global_statement
                            (identifier) @var.name
                        )
                        )
                    ]
                    )
            """),
            "class_attributes": Query(self.language, """
                (class_definition
                    body: (block
                        [
                        (expression_statement
                            (assignment
                            left: [
                                (identifier) @class_attr.name
                                (_ (identifier) @class_attr.name)
                            ]
                            )
                        )
                        (expression_statement
                            (assignment
                            left: [
                                (pattern_list (identifier) @class_attr.name)
                                (tuple_pattern (identifier) @class_attr.name)
                                (list_pattern (identifier) @class_attr.name)
                            ]
                            )
                        )

                        (expression_statement
                            (augmented_assignment
                            left: (identifier) @class_attr.name
                            )
                        )
                        (type_alias_statement
                            (type (identifier) @class_attr.name)
                        )
                        (if_statement
                            consequence: (block
                            (expression_statement
                                [
                                (assignment left: [(identifier) @class_attr.name (_ (identifier) @class_attr.name)])
                                (augmented_assignment left: (identifier) @class_attr.name)
                                ]
                            )
                            )
                            alternative: (block
                            (expression_statement
                                [
                                (assignment left: [(identifier) @class_attr.name (_ (identifier) @class_attr.name)])
                                (augmented_assignment left: (identifier) @class_attr.name)
                                ]
                            )
                            )?
                        )
                        ]
                    )
                    ) @class.node
            """),
            "instance_attributes": Query(self.language, """
                [
                (assignment
                    left: (attribute
                        object: (identifier) @obj (#eq? @obj \"self\")
                        attribute: (identifier) @inst_attr.name))

                (augmented_assignment
                    left: (attribute
                        object: (identifier) @obj (#eq? @obj \"self\")
                        attribute: (identifier) @inst_attr.name))

                (assignment
                    left: [
                        (pattern_list (attribute object: (identifier) @obj (#eq? @obj \"self\") attribute: (identifier) @inst_attr.name))
                        (tuple (attribute object: (identifier) @obj (#eq? @obj \"self\") attribute: (identifier) @inst_attr.name))
                        (expression_list (attribute object: (identifier) @obj (#eq? @obj \"self\") attribute: (identifier) @inst_attr.name))
                    ])

                (for_statement
                    left: [
                        (pattern_list (attribute object: (identifier) @obj (#eq? @obj \"self\") attribute: (identifier) @inst_attr.name))
                        (tuple (attribute object: (identifier) @obj (#eq? @obj \"self\") attribute: (identifier) @inst_attr.name))
                        (identifier) @inst_attr.name ; For single variable loops if applicable
                    ])
                ]
            """),
            "env_calls": Query(self.language, """
                (call
                function: [
                    (attribute
                    object: (identifier) @obj (#eq? @obj \"os\")
                    attribute: (identifier) @method (#match? @method \"^(getenv)$\"))
                    (attribute
                    object: (attribute
                        object: (identifier) @obj (#eq? @obj \"os\")
                        attribute: (identifier) @attr (#eq? @attr \"environ\"))
                    attribute: (identifier) @method (#match? @method \"^(get|setdefault)$\"))
                    (identifier) @method (#eq? @method \"getenv\")
                ]
                arguments: (argument_list) @args
                )
            """),
            "env_subscripts": Query(self.language, """
                (subscript
                value: [
                    (attribute
                    object: (identifier) @obj (#eq? @obj \"os\")
                    attribute: (identifier) @attr (#eq? @attr \"environ\"))
                    (identifier) @attr (#eq? @attr \"environ\")
                ]
                subscript: (string (string_content) @env.name)
                )
            """)
        }

    def _safe_captures(self, query: Query, node) -> dict:
        """
        Normalizes query.captures(node) across different tree-sitter python versions
        (whether returning a dict or a list of tuples).
        """
        cursor = QueryCursor(query)
        raw = cursor.captures(node)
        if isinstance(raw, dict):
            return raw
        result = {}
        for item in raw:
            if isinstance(item, tuple) and len(item) == 2:
                n, name = item
                result.setdefault(name, []).append(n)
        return result

    def _extract_env_vars(self, node, seen_env, extracted_nodes):
        env_name, default_val = _detect_env_var(node)
        if env_name:
            # Every reference with line number (for edge scope resolution)
            extracted_nodes["EnvVarUsage"].append({
                "id": f"ENV::{env_name}",
                "env_name": env_name,
                "line": node.start_point[0] + 1
            })
            if env_name not in seen_env:
                seen_env.add(env_name)
                extracted_nodes["EnvVar"].append({
                    "id": f"ENV::{env_name}",
                    "name": env_name,
                    "default_value": default_val
                })
        for child in node.children:
            self._extract_env_vars(child, seen_env, extracted_nodes)

    def fetch_nodes(self, parsed_file: ParsedFile, project_root: str) -> dict:
        file_path = parsed_file.file_path
        root_node = parsed_file.root_node

        extracted_nodes = {
            "File": [{"id": file_path, "name": os.path.basename(file_path), "file_path": file_path}],
            "Import": [],
            "Class": [],
            "ClassAttribute": [],
            "InstanceAttribute": [],
            "Function": [],
            "Parameter": [],
            "Variable": [],
            "EnvVar": [],
            "EnvVarUsage": []
        }

        # 1. Global Variables via Query
        global_captures = self._safe_captures(self.queries["global_vars"], root_node)
        for var_node in global_captures.get("var.name", []):
            var_name = var_node.text.decode("utf8")
            extracted_nodes["Variable"].append({
                "id": f"{file_path}::{var_name}",
                "name": var_name,
                "file_path": file_path,
                "start_line": var_node.start_point[0] + 1
            })

        # 2. Classes and Class Attributes via Query
        class_captures = self._safe_captures(self.queries["classes"], root_node)
        for node in class_captures.get("class.def", []):
            name_node = node.child_by_field_name("name")
            if not name_node:
                continue
            class_name = name_node.text.decode("utf8")
            class_id = f"{file_path}::{class_name}"

            superclasses_node = node.child_by_field_name("superclasses")
            signature = superclasses_node.text.decode("utf8") if superclasses_node else "()"
            
            base_classes = []
            if superclasses_node:
                for child in superclasses_node.children:
                    if child.type in ["identifier", "attribute"]:
                        base_classes.append(child.text.decode("utf8"))

            # Scoped Class Attributes extraction using Query
            class_attr_captures = self._safe_captures(self.queries["class_attributes"], node)
            attributes = set()
            for attr_node in class_attr_captures.get("class_attr.name", []):
                # Verify assignment statement's parent block is directly this class's body block
                stmt_node = attr_node.parent
                while stmt_node and stmt_node.type != "expression_statement":
                    stmt_node = stmt_node.parent
                if stmt_node and stmt_node.parent and stmt_node.parent.parent == node:
                    attr_name = attr_node.text.decode("utf8")
                    attributes.add(attr_name)
                    extracted_nodes["ClassAttribute"].append({
                        "id": f"{class_id}::class_attr::{attr_name}",
                        "name": attr_name,
                        "class_id": class_id,
                        "class_name": class_name,
                        "file_path": file_path,
                        "start_line": attr_node.start_point[0] + 1
                    })

            extracted_nodes["Class"].append({
                "id": class_id,
                "name": class_name,
                "signature": signature,
                "bases": base_classes,
                "attributes": list(attributes),
                "file_path": file_path,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1
            })

        # 3. Functions, Parameters, and Instance Attributes via Query
        func_captures = self._safe_captures(self.queries["functions"], root_node)
        for node in func_captures.get("function.def", []):
            name_node = node.child_by_field_name("name")
            if not name_node:
                continue
            func_name = name_node.text.decode("utf8")

            parent = node.parent
            parent_class_name = None
            while parent:
                if parent.type == "class_definition":
                    class_name_node = parent.child_by_field_name("name")
                    if class_name_node:
                        parent_class_name = class_name_node.text.decode("utf8")
                    break
                parent = parent.parent

            is_method = bool(parent_class_name)
            fqn = f"{file_path}::{parent_class_name}.{func_name}" if is_method else f"{file_path}::{func_name}"
            func_id = fqn

            # Parameters
            params_node = node.child_by_field_name("parameters")
            signature = params_node.text.decode("utf8") if params_node else "()"
            param_names = []
            if params_node:
                for child in params_node.children:
                    p_name = None
                    if child.type == "identifier":
                        p_name = child.text.decode("utf8")
                    elif child.type in ["typed_parameter", "default_parameter", "typed_default_parameter"]:
                        sub = child.child_by_field_name("name") or child.children[0]
                        if sub and sub.type == "identifier":
                            p_name = sub.text.decode("utf8")
                    elif child.type in ["list_splat_pattern", "dictionary_splat_pattern"]:
                        for sub in child.children:
                            if sub.type == "identifier":
                                p_name = ("*" if child.type == "list_splat_pattern" else "**") + sub.text.decode("utf8")
                                break
                    if p_name:
                        param_names.append(p_name)
                        extracted_nodes["Parameter"].append({
                            "id": f"{func_id}::param::{p_name}",
                            "name": p_name,
                            "function_id": func_id
                        })

            # Instance attributes using Query (for class methods)
            if is_method:
                inst_captures = self._safe_captures(self.queries["instance_attributes"], node)
                for inst_node in inst_captures.get("inst_attr.name", []):
                    attr_name = inst_node.text.decode("utf8")
                    extracted_nodes["InstanceAttribute"].append({
                        "id": f"{file_path}::{parent_class_name}::inst_attr::{attr_name}",
                        "name": attr_name,
                        "class_id": f"{file_path}::{parent_class_name}",
                        "class_name": parent_class_name,
                        "file_path": file_path,
                        "start_line": inst_node.start_point[0] + 1
                    })

            extracted_nodes["Function"].append({
                "id": func_id,
                "name": func_name,
                "signature": signature,
                "parameters": param_names,
                "file_path": file_path,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "is_method": is_method,
                "class_name": parent_class_name
            })

        # 4. Environment Variables
        all_env_usages = _extract_all_env_vars(root_node, file_path)
        extracted_nodes["EnvVarUsage"] = all_env_usages
        seen_env = set()
        for usage in all_env_usages:
            if usage["env_name"] not in seen_env:
                seen_env.add(usage["env_name"])
                extracted_nodes["EnvVar"].append({
                    "id": f"ENV::{usage['env_name']}",
                    "name": usage["env_name"],
                    "default_value": usage["default_value"]
                })
        
        # 5. Imports
        for node in root_node.children:
            # 1a. import os, import requests as req
            if node.type == "import_statement":
                for child in node.children:
                    if child.type == "dotted_name":
                        mod_name = child.text.decode("utf8")
                        extracted_nodes["Import"].append({
                            "id": f"{file_path}::import::{mod_name}",
                            "file_path": file_path,
                            "module": mod_name,
                            "imported_symbol": None,
                            "alias": None,
                            "is_from_import": False,
                            "is_internal": is_internal(mod_name, file_path, project_root)
                        })
                    elif child.type == "aliased_import":
                        name_n = child.child_by_field_name("name")
                        alias_n = child.child_by_field_name("alias")
                        if name_n and alias_n:
                            mod_name = name_n.text.decode("utf8")
                            extracted_nodes["Import"].append({
                                "id": f"{file_path}::import::{mod_name}",
                                "file_path": file_path,
                                "module": mod_name,
                                "imported_symbol": None,
                                "alias": alias_n.text.decode("utf8"),
                                "is_from_import": False,
                                "is_internal": is_internal(mod_name, file_path, project_root)
                            })
            # 1b. from langchain_chroma import Chroma
            elif node.type == "import_from_statement":
                mod_node = node.child_by_field_name("module_name") or node.child_by_field_name("relative_import")
                mod_name = mod_node.text.decode("utf8") if mod_node else ""
                
                for child in node.children:
                    if child.type in ["dotted_name", "identifier"] and child != mod_node:
                        symbol = child.text.decode("utf8")
                        extracted_nodes["Import"].append({
                            "id": f"{file_path}::import::{mod_name}::{symbol}",
                            "file_path": file_path,
                            "module": mod_name,
                            "imported_symbol": symbol,
                            "alias": None,
                            "is_from_import": True,
                            "is_internal": is_internal(mod_name, file_path, project_root)
                        })
                    elif child.type == "aliased_import":
                        name_n = child.child_by_field_name("name")
                        alias_n = child.child_by_field_name("alias")
                        if name_n and alias_n:
                            symbol = name_n.text.decode("utf8")
                            extracted_nodes["Import"].append({
                                "id": f"{file_path}::import::{mod_name}::{symbol}",
                                "file_path": file_path,
                                "module": mod_name,
                                "imported_symbol": symbol,
                                "alias": alias_n.text.decode("utf8"),
                                "is_from_import": True,
                                "is_internal": is_internal(mod_name, file_path, project_root)
                            })
        return extracted_nodes
