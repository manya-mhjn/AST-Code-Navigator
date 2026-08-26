"""
parser.py — The single I/O boundary for the entire pipeline.

This module is the ONLY place that reads files from disk and parses them.
Every downstream stage receives a ParsedFile dataclass instead of a file path.
"""

import os
from dataclasses import dataclass

import tree_sitter_python as tspython
from tree_sitter import Language, Parser


@dataclass
class ParsedFile:
    """
    The single typed data object flowing through the pipeline.
    Created once by FileParser, consumed by all downstream stages.
    """
    file_path: str
    file_bytes: bytes
    tree: object          # tree_sitter.Tree
    root_node: object     # tree_sitter.Node
    code_lines: list[str]

    @property
    def basename(self) -> str:
        return os.path.basename(self.file_path)

    @property
    def line_count(self) -> int:
        return len(self.code_lines)


class FileParser:
    """
    Single I/O boundary — the only place in the pipeline that reads and parses files.
    Owns the one Language + Parser instance shared across the entire pipeline.
    """

    def __init__(self):
        self.language = Language(tspython.language())
        self.parser = Parser(self.language)

    def parse_file(self, file_path: str) -> ParsedFile:
        """Reads a file, parses it into a tree-sitter AST, and returns a ParsedFile."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Cannot find file: {file_path}")

        with open(file_path, "rb") as f:
            file_bytes = f.read()

        tree = self.parser.parse(file_bytes)
        code_lines = file_bytes.decode("utf-8", errors="replace").splitlines()

        return ParsedFile(
            file_path=file_path,
            file_bytes=file_bytes,
            tree=tree,
            root_node=tree.root_node,
            code_lines=code_lines,
        )


def stream_repo_files(repo_path: str, target_extension: str = ".py"):
    """
    A generator that lazily walks the directory tree.
    Yields one file path at a time instead of building a massive list.

    Args:
        repo_path: Root directory to walk.
        target_extension: File extension to filter for (default: ".py").
    """
    abs_path = os.path.abspath(repo_path)

    if not os.path.exists(abs_path):
        print(f"ERROR: Path does not exist: {abs_path}")
        return

    if not os.path.isdir(abs_path):
        print(f"ERROR: Path is a file, not a directory: {abs_path}")
        return

    IGNORE_DIRS = {".venv", "venv", "env", ".git", "__pycache__", "site-packages", "build", "dist", ".tox", ".pytest_cache", ".idea", ".vscode"}

    for root, dirs, files in os.walk(abs_path):
        # Prune ignored directories in-place so os.walk does not recurse into them
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for file in files:
            if file.endswith(target_extension):
                yield os.path.join(root, file)

