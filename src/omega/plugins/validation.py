"""Bounded JSON manifest parsing and compatibility validation."""

from __future__ import annotations

import hashlib
import platform
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from omega.core.exceptions import SecurityValidationError
from omega.plugins.configuration import PluginConfiguration
from omega.plugins.exceptions import PluginCompatibilityError, PluginValidationError
from omega.plugins.models import (
    PluginApiVersion,
    PluginCapability,
    PluginCategory,
    PluginManifest,
    PluginPermission,
    PluginValidationResult,
    PluginVersion,
)
from omega.security import JsonSecurityLimits, load_bounded_json

PLUGIN_API_VERSION = PluginApiVersion(1, 0, 0)
_FIELDS = {
    "schema_version",
    "plugin_id",
    "display_name",
    "version",
    "minimum_api_version",
    "maximum_api_version",
    "category",
    "entry_point",
    "description",
    "publisher",
    "capabilities",
    "requested_permissions",
    "supported_operating_systems",
    "minimum_python_version",
    "extension_points",
    "restart_required",
}


class PluginValidator:
    def __init__(self, configuration: PluginConfiguration) -> None:
        self.configuration = configuration

    def parse_file(self, path: Path) -> PluginManifest:
        if path.is_symlink() or not path.is_file():
            raise PluginValidationError("Plugin manifest must be a regular local file.")
        payload = path.read_bytes()
        return self.parse(payload)

    def parse(self, payload: bytes) -> PluginManifest:
        if len(payload) > self.configuration.maximum_manifest_bytes:
            raise PluginValidationError("Plugin manifest exceeds the size limit.")
        try:
            raw = load_bounded_json(
                payload,
                JsonSecurityLimits(
                    self.configuration.maximum_manifest_bytes,
                    maximum_depth=10,
                    maximum_items=2_000,
                ),
            )
        except SecurityValidationError as error:
            raise PluginValidationError("Plugin manifest is not valid JSON.") from error
        if not isinstance(raw, dict) or set(raw) - _FIELDS:
            raise PluginValidationError("Plugin manifest contains unknown fields.")
        return self._manifest(raw)

    def validate_compatibility(
        self, manifest: PluginManifest
    ) -> PluginValidationResult:
        errors: list[str] = []
        if (
            not manifest.minimum_api_version
            <= PLUGIN_API_VERSION
            <= manifest.maximum_api_version
        ):
            errors.append("Plugin API version is incompatible.")
        running = PluginVersion(
            sys.version_info.major, sys.version_info.minor, sys.version_info.micro
        )
        if running < manifest.minimum_python_version:
            errors.append("Python version is incompatible.")
        host = (
            "windows"
            if platform.system().casefold() == "windows"
            else platform.system().casefold()
        )
        if host not in {
            item.casefold() for item in manifest.supported_operating_systems
        }:
            errors.append("Operating system is incompatible.")
        return PluginValidationResult(not errors, tuple(errors))

    def require_compatible(self, manifest: PluginManifest) -> None:
        result = self.validate_compatibility(manifest)
        if not result.valid:
            raise PluginCompatibilityError("; ".join(result.errors))

    @staticmethod
    def fingerprint(path: Path) -> str:
        digest = hashlib.sha256()
        for item in sorted(path.rglob("*"), key=lambda value: value.as_posix()):
            if item.is_file() and not item.is_symlink():
                digest.update(item.relative_to(path).as_posix().encode())
                digest.update(item.read_bytes())
        return digest.hexdigest()

    @staticmethod
    def _strings(raw: Mapping[str, Any], name: str) -> list[str]:
        value = raw.get(name, [])
        if not isinstance(value, list) or any(
            not isinstance(item, str) for item in value
        ):
            raise PluginValidationError(f"Plugin {name} must be a string list.")
        return value

    def _manifest(self, raw: Mapping[str, Any]) -> PluginManifest:
        try:
            if not isinstance(raw.get("schema_version"), int) or isinstance(
                raw.get("schema_version"), bool
            ):
                raise PluginValidationError("Manifest schema version is invalid.")
            if not isinstance(raw.get("restart_required", False), bool):
                raise PluginValidationError("Manifest restart flag is invalid.")
            capabilities_raw = self._strings(raw, "capabilities")
            permissions_raw = self._strings(raw, "requested_permissions")
            if len(set(capabilities_raw)) != len(capabilities_raw) or len(
                set(permissions_raw)
            ) != len(permissions_raw):
                raise PluginValidationError(
                    "Duplicate manifest declarations are invalid."
                )
            return PluginManifest(
                schema_version=int(raw["schema_version"]),
                plugin_id=str(raw["plugin_id"]),
                display_name=str(raw["display_name"]),
                version=PluginVersion.parse(str(raw["version"])),
                minimum_api_version=PluginVersion.parse(
                    str(raw["minimum_api_version"])
                ),
                maximum_api_version=PluginVersion.parse(
                    str(raw["maximum_api_version"])
                ),
                category=PluginCategory(str(raw["category"])),
                entry_point=str(raw["entry_point"]),
                description=str(raw.get("description", "")),
                publisher=str(raw.get("publisher", "")),
                capabilities=tuple(PluginCapability(item) for item in capabilities_raw),
                requested_permissions=tuple(
                    PluginPermission(item) for item in permissions_raw
                ),
                supported_operating_systems=tuple(
                    self._strings(raw, "supported_operating_systems") or ["windows"]
                ),
                minimum_python_version=PluginVersion.parse(
                    str(raw.get("minimum_python_version", "3.11.0"))
                ),
                extension_points=tuple(self._strings(raw, "extension_points")),
                restart_required=raw.get("restart_required", False),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise PluginValidationError(
                "Plugin manifest fields are invalid."
            ) from error
