"""Bounded AST checks for high-impact execution primitives."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class StaticSecurityFinding:
    path: str
    line: int
    code: str
    message: str


class StaticSecurityScanner:
    """Inspect Python source without importing or executing it."""

    def __init__(self, *, maximum_files: int = 1_000) -> None:
        if not 1 <= maximum_files <= 10_000:
            raise ValueError("maximum_files must be between 1 and 10000")
        self.maximum_files = maximum_files

    def scan(self, source_root: Path) -> tuple[StaticSecurityFinding, ...]:
        root = source_root.resolve(strict=False)
        findings: list[StaticSecurityFinding] = []
        files = sorted(root.rglob("*.py"))
        if len(files) > self.maximum_files:
            return (
                StaticSecurityFinding(
                    str(root), 0, "SOURCE_LIMIT", "Source file limit was exceeded."
                ),
            )
        for path in files:
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, UnicodeError, SyntaxError):
                findings.append(
                    StaticSecurityFinding(
                        str(path.relative_to(root)),
                        0,
                        "SOURCE_UNREADABLE",
                        "Source could not be inspected safely.",
                    )
                )
                continue
            findings.extend(self._scan_tree(tree, path.relative_to(root)))
        return tuple(findings)

    @staticmethod
    def _scan_tree(tree: ast.AST, relative_path: Path) -> list[StaticSecurityFinding]:
        findings: list[StaticSecurityFinding] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node.func)
            code = ""
            message = ""
            if name in {"eval", "exec", "os.system"}:
                code = "DYNAMIC_EXECUTION"
                message = f"Prohibited execution primitive: {name}."
            elif name.endswith(".extractall"):
                code = "UNSAFE_ARCHIVE_EXTRACTION"
                message = "Bulk archive extraction bypasses per-member validation."
            elif name in {
                "subprocess.run",
                "subprocess.Popen",
                "subprocess.call",
                "subprocess.check_call",
                "subprocess.check_output",
            } and any(
                keyword.arg == "shell"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
                for keyword in node.keywords
            ):
                code = "SHELL_EXECUTION"
                message = "Subprocess shell execution is prohibited."
            if code:
                findings.append(
                    StaticSecurityFinding(
                        str(relative_path),
                        getattr(node, "lineno", 0),
                        code,
                        message,
                    )
                )
        return findings


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""
