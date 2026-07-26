import json
from pathlib import Path

import pytest


@pytest.fixture
def manifest_data() -> dict[str, object]:
    return {
        "schema_version": 1,
        "plugin_id": "example.readonly",
        "display_name": "Example Read Only",
        "version": "1.0.0",
        "minimum_api_version": "1.0.0",
        "maximum_api_version": "1.0.0",
        "category": "command",
        "entry_point": "plugin:create_plugin",
        "description": "A deterministic example.",
        "publisher": "Omega tests",
        "capabilities": ["command_provider"],
        "requested_permissions": ["register_read_only_command"],
        "supported_operating_systems": ["windows"],
        "minimum_python_version": "3.11.0",
        "extension_points": ["command_provider"],
        "restart_required": False,
    }


@pytest.fixture
def plugin_directory(tmp_path: Path, manifest_data: dict[str, object]) -> Path:
    root = tmp_path / "approved"
    plugin = root / "example.readonly"
    plugin.mkdir(parents=True)
    (plugin / "plugin.json").write_text(json.dumps(manifest_data), encoding="utf-8")
    (plugin / "plugin.py").write_text(
        "class Plugin:\n"
        "    def __init__(self, context): self.context = context\n"
        "    def commands(self):\n"
        "        return {'hello': lambda value: {'message': value}}\n"
        "    def shutdown(self): return None\n"
        "def create_plugin(context): return Plugin(context)\n",
        encoding="utf-8",
    )
    return root
