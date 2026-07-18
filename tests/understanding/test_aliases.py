from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from omega.core.exceptions import ConfigurationError
from omega.understanding import ApplicationAliasRegistry


def test_all_configured_aliases_resolve_case_insensitively() -> None:
    registry = ApplicationAliasRegistry.from_file()
    for expected in (
        "chrome",
        "edge",
        "notepad",
        "calculator",
        "file_explorer",
        "paint",
        "settings",
        "task_manager",
        "command_prompt",
        "powershell",
    ):
        assert expected in registry.canonical_names
    assert registry.resolve("Open GOOGLE CHROME") == ("chrome", "google chrome")
    assert registry.resolve("chromebook") is None


def test_duplicate_conflicting_and_invalid_aliases_fail() -> None:
    with pytest.raises(ConfigurationError):
        ApplicationAliasRegistry({"one": ["same"], "two": ["same"]})
    with TemporaryDirectory(dir=Path.cwd() / "data") as directory:
        path = Path(directory) / "aliases.json"
        path.write_text("not json", encoding="utf-8")
        with pytest.raises(ConfigurationError):
            ApplicationAliasRegistry.from_file(path)
