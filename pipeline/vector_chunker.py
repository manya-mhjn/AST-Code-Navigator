"""
Module for generating AST-aware semantic chunks for Vector DB indexing.
Extracts code, docstrings, and inline comments for File (Module), Functions, and Classes.
"""

from pipeline.parser import ParsedFile
from langchain_core.documents import Document

class ASTVectorChunker:
    """
    Generates AST-aware semantic chunks for Vector DB indexing (ChromaDB / Pinecone).
    Extracts code, docstrings, and inline comments for File (Module), Functions, and Classes,
    attaching the Neo4j node_id in metadata for GraphRAG integration.
    """

    def __init__(self):
        pass

    def create_vector_documents(self, parsed_file: ParsedFile, nodes: dict) -> list[Document]:
        """
        Reads file, parses docstrings and comments, and returns Vector DB Documents.
        """
        root_node = parsed_file.root_node
        code_lines = parsed_file.code_lines
        file_path = parsed_file.file_path

        documents = []

        # 1. FILE / MODULE LEVEL CHUNK
        module_docstring = self._extract_module_docstring(root_node)
        top_level_comments = self._extract_top_level_comments(root_node)

        file_content_sections = [
            f"# File: {file_path}",
            f"# Module Docstring: {module_docstring}" if module_docstring else "",
            f"# Top-Level Comments: {', '.join(top_level_comments)}" if top_level_comments else "",
            "\n# Code Preview (First 50 lines):",
            "\n".join(code_lines[:50])
        ]
        file_page_content = "\n".join([s for s in file_content_sections if s])

        file_doc = Document(
            page_content=file_page_content,
            metadata={
                "node_id": file_path,
                "file_path": file_path,
                "name": parsed_file.basename,
                "chunk_type": "file",
                "docstring": module_docstring or "",
                "inline_comments": top_level_comments,
                "start_line": 1,
                "end_line": parsed_file.line_count
            }
        )
        documents.append(file_doc)

        # 2. FUNCTION & METHOD CHUNKS
        for fn in nodes.get("Function", []):
            fn_node = self._find_node_by_line(root_node, "function_definition", fn["start_line"])
            
            docstring = self._extract_docstring(fn_node)
            inline_comments = self._extract_comments(fn_node) if fn_node else []

            start_line = fn["start_line"] - 1
            end_line = fn["end_line"]
            full_code = "\n".join(code_lines[start_line:end_line])

            content_sections = [
                f"# File: {file_path}",
                f"# Function: {fn['name']}",
                f"# Signature: {fn['name']}{fn['signature']}",
                f"# Docstring: {docstring}" if docstring else "",
                f"# Comments: {', '.join(inline_comments)}" if inline_comments else "",
                "\n# Code:",
                full_code
            ]
            page_content = "\n".join([s for s in content_sections if s])

            doc = Document(
                page_content=page_content,
                metadata={
                    "node_id": fn["id"],
                    "file_path": file_path,
                    "name": fn["name"],
                    "chunk_type": "function",
                    "docstring": docstring or "",
                    "inline_comments": inline_comments,
                    "is_method": fn["is_method"],
                    "class_name": fn["class_name"] or "",
                    "start_line": fn["start_line"],
                    "end_line": fn["end_line"]
                }
            )
            documents.append(doc)

        # 3. CLASS CHUNKS
        for cls in nodes.get("Class", []):
            cls_node = self._find_node_by_line(root_node, "class_definition", cls["start_line"])
            
            docstring = self._extract_docstring(cls_node)
            inline_comments = self._extract_comments(cls_node) if cls_node else []

            start_line = cls["start_line"] - 1
            end_line = cls["end_line"]
            full_code = "\n".join(code_lines[start_line:end_line])

            content_sections = [
                f"# File: {file_path}",
                f"# Class: {cls['name']}",
                f"# Bases: {', '.join(cls['bases'])}",
                f"# Docstring: {docstring}" if docstring else "",
                f"# Comments: {', '.join(inline_comments)}" if inline_comments else "",
                "\n# Code:",
                full_code
            ]
            page_content = "\n".join([s for s in content_sections if s])

            doc = Document(
                page_content=page_content,
                metadata={
                    "node_id": cls["id"],
                    "file_path": file_path,
                    "name": cls["name"],
                    "chunk_type": "class",
                    "docstring": docstring or "",
                    "inline_comments": inline_comments,
                    "start_line": cls["start_line"],
                    "end_line": cls["end_line"]
                }
            )
            documents.append(doc)

        return documents

    def _extract_module_docstring(self, root_node) -> str | None:
        if not root_node or root_node.type != "module":
            return None
        for child in root_node.children:
            if child.type == "expression_statement":
                for sub in child.children:
                    if sub.type == "string":
                        for content in sub.children:
                            if content.type == "string_content":
                                return content.text.decode("utf8").strip()
                        return sub.text.decode("utf8").strip()
            elif child.type not in ["comment"]:
                break
        return None

    def _extract_top_level_comments(self, root_node) -> list[str]:
        comments = []
        if not root_node:
            return comments
        for child in root_node.children:
            if child.type == "comment":
                text = child.text.decode("utf8").strip().lstrip("#").strip()
                if text:
                    comments.append(text)
        return comments

    def _extract_docstring(self, node) -> str | None:
        if not node:
            return None
        body = node.child_by_field_name("body")
        if not body:
            return None
        for child in body.children:
            if child.type == "expression_statement":
                for sub in child.children:
                    if sub.type == "string":
                        for content in sub.children:
                            if content.type == "string_content":
                                return content.text.decode("utf8").strip()
                        return sub.text.decode("utf8").strip()
            elif child.type not in ["comment"]:
                break
        return None

    def _extract_comments(self, node) -> list[str]:
        comments = []
        if not node:
            return comments
        def walk(n):
            if n.type == "comment":
                text = n.text.decode("utf8").strip().lstrip("#").strip()
                if text:
                    comments.append(text)
            for c in n.children:
                walk(c)
        walk(node)
        return comments

    def _find_node_by_line(self, root_node, target_type, target_line):
        matched = [None]
        def visit(n):
            if n.type == target_type and (n.start_point[0] + 1) == target_line:
                matched[0] = n
                return
            for c in n.children:
                visit(c)
        visit(root_node)
        return matched[0]
