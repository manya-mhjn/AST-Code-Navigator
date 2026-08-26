"""
utils.py — Shared pure-logic helpers for the pipeline.

Consolidates logic that was duplicated across ASTNodeFetcher and ASTEdgeFetcher:
  - extract_string(): tree-sitter string node → Python string
  - detect_env_var(): detects os.getenv / os.environ[] / os.environ.get() patterns
  - detect_env_var_with_default(): same as above but also extracts the default value
  - is_internal(): classifies imports as internal vs external
"""

import os
import sys


def extract_string(node) -> str:
    """
    Extracts the text content from a tree-sitter string node.
    Handles both quoted strings (by finding string_content child) and bare nodes.
    """
    if node.type == "string":
        for c in node.children:
            if c.type == "string_content":
                return c.text.decode("utf-8")
        return ""
    return node.text.decode("utf-8")


def detect_env_var(node) -> str | None:
    """
    Detects environment variable access patterns in an AST node.
    Recognized patterns:
      - os.getenv("VAR")
      - os.environ["VAR"]
      - os.environ.get("VAR")
      - os.environ.setdefault("VAR", ...)

    Returns the env var name if found, None otherwise.
    """
    if node.type == "call":
        func = node.child_by_field_name("function")
        args = node.child_by_field_name("arguments")
        if func and args and _is_env_call(func):
            pos_args = [c for c in args.children if c.type not in ("(", ")", ",")]
            if pos_args and pos_args[0].type == "string":
                return extract_string(pos_args[0])

    elif node.type == "subscript":
        val = node.child_by_field_name("value")
        sub = node.child_by_field_name("subscript") or node.child_by_field_name("index")
        if val and sub and _is_os_environ(val) and sub.type == "string":
            return extract_string(sub)

    return None


def _detect_env_var(node) -> tuple[str | None, str | None]:
    """Detects if a single AST node is an env var access. Returns (env_name, default_value)."""
    if node.type == "call":
        func = node.child_by_field_name("function")
        args = node.child_by_field_name("arguments")
        if func and args and _is_env_call(func):
            pos_args = [c for c in args.children if c.type not in ("(", ")", ",")]
            if pos_args and pos_args[0].type == "string":
                env_name = extract_string(pos_args[0])
                default_val = None
                if len(pos_args) > 1:
                    default_val = extract_string(pos_args[1])
                else:
                    for child in args.children:
                        if child.type == "keyword_argument":
                            k_name = child.child_by_field_name("name")
                            k_val = child.child_by_field_name("value")
                            if k_name and k_val and k_name.text.decode("utf-8") == "default":
                                default_val = extract_string(k_val)
                return env_name, default_val
    elif node.type == "subscript":
        val = node.child_by_field_name("value")
        sub = node.child_by_field_name("subscript") or node.child_by_field_name("index")
        if val and sub and _is_os_environ(val) and sub.type == "string":
            return extract_string(sub), None
    return None, None

def _resolve_scope(node, file_path: str) -> str:
    """Walks up the AST parent chain to find the enclosing scope ID."""
    func_name = None
    class_name = None
    parent = node.parent
    while parent:
        if parent.type == "function_definition" and func_name is None:
            name_n = parent.child_by_field_name("name")
            if name_n:
                func_name = name_n.text.decode("utf-8")
        elif parent.type == "class_definition" and class_name is None:
            name_n = parent.child_by_field_name("name")
            if name_n:
                class_name = name_n.text.decode("utf-8")
        parent = parent.parent
    if func_name and class_name:
        return f"{file_path}::{class_name}.{func_name}"
    elif func_name:
        return f"{file_path}::{func_name}"
    elif class_name:
        return f"{file_path}::{class_name}"
    return file_path


def _extract_all_env_vars(root_node, file_path: str) -> list[dict]:
    """
    Walks the entire AST once and extracts every environment variable reference.
    Returns a list of dicts, one per usage:
        {"env_name": str, "default_value": str|None, "scope_id": str, "line": int}
    Recognized patterns:
      - os.getenv("VAR", default)
      - os.environ["VAR"]
      - os.environ.get("VAR", default)
      - os.environ.setdefault("VAR", default)
    """
    results = []
    def _visit(node):
        env_name, default_val = _detect_env_var(node)
        if env_name:
            scope_id = _resolve_scope(node, file_path)
            results.append({
                "env_name": env_name,
                "default_value": default_val,
                "scope_id": scope_id,
                "line": node.start_point[0] + 1
            })
        for child in node.children:
            _visit(child)
    _visit(root_node)
    return results



def is_internal(mod_name: str, file_path: str, project_root: str = None) -> bool:
    """
    Determines if a module import is internal (part of the project) or external.

    Fixed: This was originally a nested function inside fetch_nodes_from_file()
    with a phantom `self` parameter that caused a silent argument shift bug.

    Args:
        mod_name: The module name from the import statement (e.g. "os", "myapp.utils").
        file_path: Path to the file containing the import.
        project_root: Root directory of the project being analyzed.
    """
    if not mod_name:
        return False

    # Relative imports are always internal (.helper, ..utils)
    if mod_name.startswith("."):
        return True

    # Python Standard Library modules are external
    root_pkg = mod_name.split(".")[0]
    if hasattr(sys, "stdlib_module_names") and root_pkg in sys.stdlib_module_names:
        return False

    # Normalize module path for filesystem check
    rel_path = os.path.normpath(mod_name.replace(".", os.sep))

    # Build candidate directories to check
    candidate_dirs = []
    if project_root:
        candidate_dirs.append(os.path.abspath(project_root))

    candidate_dirs.append(os.getcwd())

    if file_path:
        file_dir = os.path.dirname(os.path.abspath(file_path))
        candidate_dirs.append(file_dir)
        curr = file_dir
        while curr:
            candidate_dirs.append(curr)
            # Stop at project root markers
            if any(os.path.exists(os.path.join(curr, marker))
                   for marker in (".git", "pyproject.toml", "setup.py", ".env")):
                break
            parent = os.path.dirname(curr)
            if parent == curr:  # Reached filesystem root
                break
            curr = parent

    # Check if module file or folder exists in any candidate root
    for base_dir in candidate_dirs:
        if base_dir and os.path.exists(base_dir):
            py_file = os.path.join(base_dir, f"{rel_path}.py")
            pkg_dir = os.path.join(base_dir, rel_path, "__init__.py")
            mod_dir = os.path.join(base_dir, rel_path)

            if os.path.exists(py_file) or os.path.exists(pkg_dir) or os.path.isdir(mod_dir):
                return True

    return False


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _is_env_call(func_node) -> bool:
    """Checks if a call's function node is an os.getenv / os.environ.get pattern."""
    if func_node.type == "attribute":
        obj = func_node.child_by_field_name("object")
        attr = func_node.child_by_field_name("attribute")
        if obj and attr:
            obj_text = obj.text.decode("utf-8")
            attr_text = attr.text.decode("utf-8")
            # os.getenv(...)
            if obj_text == "os" and attr_text == "getenv":
                return True
            # os.environ.get(...) / os.environ.setdefault(...)
            if obj.type == "attribute":
                iobj = obj.child_by_field_name("object")
                iattr = obj.child_by_field_name("attribute")
                if (iobj and iattr
                        and iobj.text.decode("utf-8") == "os"
                        and iattr.text.decode("utf-8") == "environ"
                        and attr_text in ("get", "setdefault")):
                    return True
    return False


def _is_os_environ(val_node) -> bool:
    """Checks if a node represents `os.environ`."""
    if val_node.type == "attribute":
        obj = val_node.child_by_field_name("object")
        attr = val_node.child_by_field_name("attribute")
        if (obj and attr
                and obj.text.decode("utf-8") == "os"
                and attr.text.decode("utf-8") == "environ"):
            return True
    return False


def _get_class_info(self, node, file_path):
        name_n = node.child_by_field_name("name")
        c_name = name_n.text.decode("utf8") if name_n else None
        class_id = f"{file_path}::{c_name}" if c_name else file_path
        return c_name, class_id

def _get_func_id(self, node, file_path, current_class_name):
    name_n = node.child_by_field_name("name")
    if not name_n:
        return None
    fn_name = name_n.text.decode("utf8")
    if current_class_name:
        return f"{file_path}::{current_class_name}.{fn_name}"
    return f"{file_path}::{fn_name}"

def _collect_scope_vars(self, func_node):
    """Scans a function definition to find local variables and explicit globals to prevent shadowing."""
    explicit_globals = set()
    local_vars = set()
    
    # 1. Add function parameters to local variables
    params_node = func_node.child_by_field_name("parameters")
    if params_node:
        for child in params_node.children:
            if child.type == "identifier":
                local_vars.add(child.text.decode("utf8"))
    # 2. Shallow walk of the body to find assignments and global declarations
    def shallow_walk(n):
        if n.type in ("function_definition", "class_definition"):
            return  # Do not enter nested scopes
            
        if n.type == "global_statement":
            for child in n.children:
                if child.type == "identifier":
                    explicit_globals.add(child.text.decode("utf8"))
                    
        elif n.type in ("assignment", "annotated_assignment", "augmented_assignment"):
            # Check left hand side of assignment
            left = n.child_by_field_name("left") or n.child_by_field_name("name")
            if left and left.type == "identifier":
                name = left.text.decode("utf8")
                if name not in explicit_globals:  # Ensure we don't accidentally mark a global as local
                    local_vars.add(name)
        for child in n.children:
            shallow_walk(child)
            
    body = func_node.child_by_field_name("body")
    if body:
        shallow_walk(body)
        
    return explicit_globals, local_vars

def _extract_call_edge(self, node, current_scope_id, edges):
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

def _extract_env_edge(self, node, current_scope_id, edges):
    # Assumes detect_env_var is defined elsewhere in the file
    env_name = detect_env_var(node)
    if env_name:
        edges.append({
            "src": current_scope_id,
            "edge": "USES_ENV",
            "target": f"ENV::{env_name}"
        })

def _extract_variable_usage(self, node, current_scope_id, local_vars, edges):
    if node.type == "identifier":
        name = node.text.decode("utf8")
        if name not in local_vars and name != "self":
            edges.append({
                "src": current_scope_id,
                "edge": "USES_VARIABLE",
                "target": name
            })

def _extract_instance_attribute_usage(self, node, current_scope_id, edges):
    if node.type == "attribute":
        obj_n = node.child_by_field_name("object")
        if obj_n and obj_n.type == "identifier" and obj_n.text.decode("utf8") == "self":
            attr_n = node.child_by_field_name("attribute")
            if attr_n:
                edges.append({
                    "src": current_scope_id,
                    "edge": "USES_INSTANCE_ATTRIBUTE",
                    "target": attr_n.text.decode("utf8")
                })