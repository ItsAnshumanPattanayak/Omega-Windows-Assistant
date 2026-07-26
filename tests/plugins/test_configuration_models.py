import pytest

from omega.plugins import (
    PluginCapability,
    PluginCategory,
    PluginConfiguration,
    PluginPermission,
    PluginVersion,
)
from omega.plugins.exceptions import PluginConfigurationError, PluginValidationError


def test_configuration_defaults_are_conservative() -> None:
    value = PluginConfiguration()
    assert value.enabled and value.load_builtin_plugins
    assert not value.load_user_plugins
    assert not value.newly_installed_plugins_enabled
    assert not value.automatically_update_plugins
    assert not value.allow_remote_plugin_downloads


@pytest.mark.parametrize(
    "field",
    [
        "automatically_update_plugins",
        "allow_remote_plugin_downloads",
        "allow_shell_permissions",
        "allow_arbitrary_network_permissions",
        "allow_credential_permissions",
        "allow_safety_bypass_permissions",
        "newly_installed_plugins_enabled",
    ],
)
def test_security_switches_cannot_be_enabled(field: str) -> None:
    with pytest.raises(PluginConfigurationError):
        PluginConfiguration.from_mapping({field: True})


@pytest.mark.parametrize(
    "field",
    [
        "maximum_plugins",
        "maximum_manifest_bytes",
        "maximum_package_bytes",
        "maximum_package_files",
        "maximum_plugin_storage_bytes",
        "maximum_plugin_configuration_bytes",
    ],
)
def test_positive_limits_reject_zero(field: str) -> None:
    with pytest.raises(PluginConfigurationError):
        PluginConfiguration.from_mapping({field: 0})


def test_unknown_configuration_rejected() -> None:
    with pytest.raises(PluginConfigurationError):
        PluginConfiguration.from_mapping({"download_marketplace": True})


@pytest.mark.parametrize("value", ["1", "1.0", "01.0.0", "v1.0.0", "1.0.0-beta"])
def test_semantic_version_rejects_unsupported_forms(value: str) -> None:
    with pytest.raises(PluginValidationError):
        PluginVersion.parse(value)


def test_known_enums_round_trip() -> None:
    assert PluginCategory("command") is PluginCategory.COMMAND
    assert PluginPermission("create_note") is PluginPermission.CREATE_NOTE
    assert PluginCapability("formatter") is PluginCapability.FORMATTER
