import json
from pathlib import Path

import pytest

from omega.plugins import (
    PluginConfiguration,
    PluginDiscovery,
    PluginStatus,
    PluginValidator,
)
from omega.plugins.exceptions import PluginValidationError


def validator(**settings: object) -> PluginValidator:
    return PluginValidator(PluginConfiguration.from_mapping(settings))


def test_valid_manifest_and_compatibility(manifest_data: dict[str, object]) -> None:
    value = validator().parse(json.dumps(manifest_data).encode())
    assert value.plugin_id == "example.readonly"
    assert validator().validate_compatibility(value).valid


def test_oversized_manifest_rejected(manifest_data: dict[str, object]) -> None:
    with pytest.raises(PluginValidationError):
        validator(maximum_manifest_bytes=10).parse(json.dumps(manifest_data).encode())


@pytest.mark.parametrize("plugin_id", ["Bad", "../bad", "bad name", "", "a" * 101])
def test_invalid_identifier_rejected(
    manifest_data: dict[str, object], plugin_id: str
) -> None:
    manifest_data["plugin_id"] = plugin_id
    with pytest.raises(PluginValidationError):
        validator().parse(json.dumps(manifest_data).encode())


@pytest.mark.parametrize(
    "entry",
    ["../plugin:create", "C:/x:create", "x.y:create", "os.system", "x:\u0000bad"],
)
def test_invalid_entry_point_rejected(
    manifest_data: dict[str, object], entry: str
) -> None:
    manifest_data["entry_point"] = entry
    with pytest.raises(PluginValidationError):
        validator().parse(json.dumps(manifest_data).encode())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("category", "shell"),
        ("capabilities", ["arbitrary_code"]),
        ("requested_permissions", ["shell_execution"]),
    ],
)
def test_unknown_manifest_enums_rejected(
    manifest_data: dict[str, object], field: str, value: object
) -> None:
    manifest_data[field] = value
    with pytest.raises(PluginValidationError):
        validator().parse(json.dumps(manifest_data).encode())


@pytest.mark.parametrize("field", ["capabilities", "requested_permissions"])
def test_duplicate_declarations_rejected(
    manifest_data: dict[str, object], field: str
) -> None:
    value = manifest_data[field]
    assert isinstance(value, list)
    manifest_data[field] = value * 2
    with pytest.raises(PluginValidationError):
        validator().parse(json.dumps(manifest_data).encode())


def test_discovery_reads_manifest_without_importing(plugin_directory: Path) -> None:
    marker = plugin_directory / "imported.txt"
    source = plugin_directory / "example.readonly" / "plugin.py"
    source.write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('bad')\n",
        encoding="utf-8",
    )
    items = PluginDiscovery(
        PluginConfiguration(), validator(), (plugin_directory,)
    ).discover()
    assert len(items) == 1 and items[0].status is PluginStatus.DISCOVERED
    assert not marker.exists()


def test_discovery_is_bounded(
    plugin_directory: Path, manifest_data: dict[str, object]
) -> None:
    second = plugin_directory / "second"
    second.mkdir()
    manifest_data["plugin_id"] = "example.second"
    (second / "plugin.json").write_text(json.dumps(manifest_data), encoding="utf-8")
    items = PluginDiscovery(
        PluginConfiguration(maximum_plugins=1), validator(), (plugin_directory,)
    ).discover()
    assert len(items) == 1


def test_duplicate_identifier_rejected(plugin_directory: Path) -> None:
    duplicate = plugin_directory / "duplicate"
    duplicate.mkdir()
    source = plugin_directory / "example.readonly" / "plugin.json"
    (duplicate / "plugin.json").write_bytes(source.read_bytes())
    with pytest.raises(PluginValidationError):
        PluginDiscovery(
            PluginConfiguration(), validator(), (plugin_directory,)
        ).discover()
