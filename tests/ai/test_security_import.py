from __future__ import annotations

import ast
import importlib
from pathlib import Path

from omega.ai import AiConfiguration, PluginAiAccess
from omega.plugins import PluginPermission


def test_ai_import_has_no_network_model_or_thread_side_effect(monkeypatch) -> None:
    calls: list[object] = []
    monkeypatch.setattr(
        "omega.ai.providers.urlopen", lambda *args, **kwargs: calls.append(args)
    )
    import omega.ai

    importlib.reload(omega.ai)
    assert calls == []


def test_ai_source_contains_no_shell_code_pickle_or_package_installation() -> None:
    for path in Path("src/omega/ai").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        lowered = source.casefold()
        assert "pip install" not in lowered
        assert "def download_model" not in lowered
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [item.name for item in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                assert not any(
                    name.split(".")[0] in {"subprocess", "pickle"} for name in names
                )
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"eval", "exec", "compile"}


def test_plugin_ai_permissions_are_explicit_and_separate() -> None:
    assert PluginPermission.USE_LOCAL_AI_GENERATION.value == "use_local_ai_generation"
    assert PluginPermission.USE_LOCAL_AI_EMBEDDINGS.value == "use_local_ai_embeddings"
    assert PluginAiAccess is not None


def test_default_ai_configuration_requires_no_cloud_or_credentials() -> None:
    configuration = AiConfiguration()
    assert configuration.provider is None
    assert configuration.endpoint is None
    assert not configuration.enabled
    assert not configuration.allow_remote_endpoints
