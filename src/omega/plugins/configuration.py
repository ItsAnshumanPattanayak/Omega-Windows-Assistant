"""Conservative configuration for reviewed local plugins."""

from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from omega.plugins.exceptions import PluginConfigurationError


@dataclass(frozen=True)
class PluginConfiguration:
    enabled: bool = True
    load_builtin_plugins: bool = True
    load_user_plugins: bool = False
    user_plugin_directory: Path | None = None
    development_plugin_directory: Path | None = None
    allow_development_plugins: bool = False
    maximum_plugins: int = 50
    maximum_manifest_bytes: int = 65_536
    maximum_package_bytes: int = 52_428_800
    maximum_package_files: int = 1_000
    maximum_plugin_storage_bytes: int = 10_485_760
    maximum_plugin_configuration_bytes: int = 262_144
    plugin_call_timeout_seconds: int = 30
    plugin_shutdown_timeout_seconds: int = 10
    require_confirmation_for_install: bool = True
    require_confirmation_for_enable: bool = True
    require_confirmation_for_permission_grant: bool = True
    require_confirmation_for_remove: bool = True
    newly_installed_plugins_enabled: bool = False
    automatically_update_plugins: bool = False
    allow_remote_plugin_downloads: bool = False
    allow_shell_permissions: bool = False
    allow_arbitrary_network_permissions: bool = False
    allow_credential_permissions: bool = False
    allow_safety_bypass_permissions: bool = False

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "PluginConfiguration":
        known = {item.name for item in fields(cls)}
        unknown = set(values) - known
        if unknown:
            raise PluginConfigurationError(
                "Unknown plugin setting(s): " + ", ".join(sorted(unknown))
            )
        data = dict(values)
        for name in ("user_plugin_directory", "development_plugin_directory"):
            value = data.get(name)
            if value is not None:
                if not isinstance(value, (str, Path)):
                    raise PluginConfigurationError(f"plugins.{name} is invalid.")
                data[name] = Path(value)
        result = cls(**data)
        result.validate()
        return result

    def validate(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            if item.name.startswith(("maximum_", "plugin_")) and item.name not in {
                "plugin_call_timeout_seconds",
                "plugin_shutdown_timeout_seconds",
            }:
                if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                    raise PluginConfigurationError(
                        f"plugins.{item.name} must be positive."
                    )
        for name in ("plugin_call_timeout_seconds", "plugin_shutdown_timeout_seconds"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 1 <= value <= 300
            ):
                raise PluginConfigurationError(
                    f"plugins.{name} is outside its safe range."
                )
        booleans = (
            "enabled",
            "load_builtin_plugins",
            "load_user_plugins",
            "allow_development_plugins",
            "require_confirmation_for_install",
            "require_confirmation_for_enable",
            "require_confirmation_for_permission_grant",
            "require_confirmation_for_remove",
            "newly_installed_plugins_enabled",
            "automatically_update_plugins",
            "allow_remote_plugin_downloads",
            "allow_shell_permissions",
            "allow_arbitrary_network_permissions",
            "allow_credential_permissions",
            "allow_safety_bypass_permissions",
        )
        if any(not isinstance(getattr(self, name), bool) for name in booleans):
            raise PluginConfigurationError("Plugin switches must be boolean.")
        forbidden = (
            self.automatically_update_plugins,
            self.allow_remote_plugin_downloads,
            self.allow_shell_permissions,
            self.allow_arbitrary_network_permissions,
            self.allow_credential_permissions,
            self.allow_safety_bypass_permissions,
            self.newly_installed_plugins_enabled,
        )
        if any(forbidden):
            raise PluginConfigurationError(
                "Security-critical plugin settings must remain disabled."
            )
