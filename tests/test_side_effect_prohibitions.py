import ast
from pathlib import Path


def test_production_execution_contains_no_unrestricted_or_delete_paths() -> None:
    source_root = Path("src/omega")
    prohibited_text = (
        "taskkill",
        "wmic",
        "powershell -command",
    )
    for path in source_root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        lowered = source.casefold()
        assert not any(value in lowered for value in prohibited_text), path
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    assert node.func.id not in {"eval", "exec"}, path
                if isinstance(node.func, ast.Attribute):
                    assert not (
                        isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "os"
                        and node.func.attr == "system"
                    ), path
                    assert not (
                        isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "os"
                        and node.func.attr in {"remove", "unlink"}
                    ), path
                    assert not (
                        isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "os"
                        and node.func.attr in {"rmdir", "removedirs"}
                    ), path
                    assert not (
                        isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "shutil"
                        and node.func.attr == "rmtree"
                    ), path
                    assert node.func.attr != "unlink", path
                    assert node.func.attr != "rmdir", path
                for keyword in node.keywords:
                    assert not (
                        keyword.arg == "shell"
                        and isinstance(keyword.value, ast.Constant)
                        and keyword.value.value is True
                    ), path
