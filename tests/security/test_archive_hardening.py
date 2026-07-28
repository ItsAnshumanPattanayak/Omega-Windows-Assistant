import json
import zipfile
from pathlib import Path

import pytest

from omega.plugins import PluginConfiguration, PluginPackageInstaller, PluginValidator
from omega.plugins.exceptions import PluginValidationError


def _installer(tmp_path: Path, ratio: float = 200.0) -> PluginPackageInstaller:
    configuration = PluginConfiguration.from_mapping({})
    return PluginPackageInstaller(
        configuration,
        PluginValidator(configuration),
        tmp_path / "installed",
        maximum_compression_ratio=ratio,
    )


def _manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "plugin_id": "example.readonly",
        "display_name": "Example",
        "version": "1.0.0",
        "minimum_api_version": "1.0.0",
        "maximum_api_version": "1.0.0",
        "category": "command",
        "entry_point": "plugin:create_plugin",
        "description": "Example",
        "publisher": "Tests",
        "capabilities": ["command_provider"],
        "requested_permissions": ["register_read_only_command"],
        "supported_operating_systems": ["windows"],
        "minimum_python_version": "3.11.0",
        "extension_points": ["command_provider"],
        "restart_required": False,
    }


def test_case_collisions_and_nested_archives_are_rejected(tmp_path: Path) -> None:
    target = tmp_path / "plugin.zip"
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr("plugin.json", json.dumps(_manifest()))
        archive.writestr("PLUGIN.JSON", "{}")
    with pytest.raises(PluginValidationError, match="case-colliding"):
        _installer(tmp_path).validate(target)

    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr("plugin.json", json.dumps(_manifest()))
        archive.writestr("payload.zip", b"nested")
    with pytest.raises(PluginValidationError, match="executable or install-hook"):
        _installer(tmp_path).validate(target)


def test_excessive_compression_ratio_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "plugin.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("plugin.json", json.dumps(_manifest()))
        archive.writestr("payload.txt", b"0" * 20_000)
    with pytest.raises(PluginValidationError, match="compression ratio"):
        _installer(tmp_path, ratio=2.0).validate(target)
