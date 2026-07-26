from dataclasses import replace
from pathlib import Path

import pytest

from omega.plugins import (
    PLUGIN_API_VERSION,
    PluginConfiguration,
    PluginContext,
    PluginLifecycle,
    PluginLoader,
    PluginMetadata,
    PluginPermission,
    PluginRegistry,
    PluginStatus,
    PluginValidator,
)
from omega.plugins.exceptions import (
    PluginLoadError,
    PluginPermissionError,
    PluginValidationError,
)


def enabled_metadata(plugin_directory: Path) -> PluginMetadata:
    validator = PluginValidator(PluginConfiguration())
    root = plugin_directory / "example.readonly"
    return PluginMetadata(
        validator.parse_file(root / "plugin.json"),
        str(root),
        validator.fingerprint(root),
        PluginStatus.ENABLED,
    )


def test_disabled_and_changed_plugins_are_not_imported(plugin_directory: Path) -> None:
    config = PluginConfiguration()
    loader = PluginLoader(config, PluginValidator(config))
    item = enabled_metadata(plugin_directory)
    context = PluginContext(item.manifest.plugin_id, PLUGIN_API_VERSION, frozenset())
    with pytest.raises(PluginLoadError):
        loader.load(replace(item, status=PluginStatus.DISABLED), context)
    (plugin_directory / "example.readonly" / "plugin.py").write_text(
        "changed = True", encoding="utf-8"
    )
    with pytest.raises(PluginLoadError):
        loader.load(item, context)


def test_load_activate_duplicate_and_shutdown(plugin_directory: Path) -> None:
    config = PluginConfiguration()
    validator = PluginValidator(config)
    lifecycle = PluginLifecycle(config, PluginLoader(config, validator))
    item = enabled_metadata(plugin_directory)
    context = PluginContext(item.manifest.plugin_id, PLUGIN_API_VERSION, frozenset())
    assert lifecycle.activate(item, context).status is PluginStatus.ACTIVE
    with pytest.raises(PluginLoadError):
        lifecycle.activate(item, context)
    lifecycle.deactivate(item.manifest.plugin_id)


def test_import_and_activation_failures_are_contained(plugin_directory: Path) -> None:
    source = plugin_directory / "example.readonly" / "plugin.py"
    source.write_text("raise RuntimeError('private detail')", encoding="utf-8")
    item = enabled_metadata(plugin_directory)
    config = PluginConfiguration()
    context = PluginContext(item.manifest.plugin_id, PLUGIN_API_VERSION, frozenset())
    with pytest.raises(PluginLoadError, match="bounded initialization") as error:
        PluginLoader(config, PluginValidator(config)).load(item, context)
    assert "private detail" not in str(error.value)


def test_registry_requires_permission_and_namespaces_commands() -> None:
    registry = PluginRegistry()
    with pytest.raises(PluginPermissionError):
        registry.register_command("example", "hello", lambda _: "hi", frozenset())
    identifier = registry.register_command(
        "example",
        "hello",
        lambda value: {"value": value},
        frozenset({PluginPermission.REGISTER_READ_ONLY_COMMAND}),
    )
    assert identifier == "plugin.example.hello"
    assert registry.invoke_command(identifier, "Omega") == {"value": "Omega"}


@pytest.mark.parametrize("name", ["help", "status", "confirm", "shutdown", "not-valid"])
def test_registry_rejects_protected_or_invalid_commands(name: str) -> None:
    with pytest.raises(PluginValidationError):
        PluginRegistry().register_command(
            "example",
            name,
            lambda _: None,
            frozenset({PluginPermission.REGISTER_READ_ONLY_COMMAND}),
        )


@pytest.mark.parametrize(
    "name", ["shell", "exec_payload", "email_send", "calendar_create"]
)
def test_registry_rejects_unsafe_workflow_steps(name: str) -> None:
    with pytest.raises(PluginValidationError):
        PluginRegistry().register_workflow_step(
            "example",
            name,
            lambda _: None,
            frozenset({PluginPermission.REGISTER_WORKFLOW_STEP}),
        )
