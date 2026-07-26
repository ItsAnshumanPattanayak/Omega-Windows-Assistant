"""Fingerprint-bound plugin permission checks."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from omega.plugins.exceptions import PluginPermissionError
from omega.plugins.models import PluginManifest, PluginPermission


class PluginPermissionRepository(Protocol):
    def grant_permission(
        self,
        plugin_id: str,
        version: str,
        fingerprint: str,
        permission: PluginPermission,
    ) -> None: ...

    def revoke_permission(
        self, plugin_id: str, permission: PluginPermission
    ) -> None: ...

    def list_permissions(
        self, plugin_id: str, version: str, fingerprint: str
    ) -> tuple[PluginPermission, ...]: ...


class PluginPermissionService:
    def __init__(self, repository: PluginPermissionRepository) -> None:
        self.repository = repository

    def grant(
        self, manifest: PluginManifest, fingerprint: str, permission: PluginPermission
    ) -> None:
        if permission not in manifest.requested_permissions:
            raise PluginPermissionError("Plugin did not declare that permission.")
        self.repository.grant_permission(
            manifest.plugin_id, str(manifest.version), fingerprint, permission
        )

    def revoke(self, plugin_id: str, permission: PluginPermission) -> None:
        self.repository.revoke_permission(plugin_id, permission)

    def approved(
        self, plugin_id: str, version: str, fingerprint: str
    ) -> frozenset[PluginPermission]:
        return frozenset(
            self.repository.list_permissions(plugin_id, version, fingerprint)
        )

    def require(
        self,
        plugin_id: str,
        version: str,
        fingerprint: str,
        permission: PluginPermission,
    ) -> None:
        if permission not in self.approved(plugin_id, version, fingerprint):
            raise PluginPermissionError("Plugin permission is not approved.")

    def require_all(
        self,
        plugin_id: str,
        version: str,
        fingerprint: str,
        permissions: Iterable[PluginPermission],
    ) -> None:
        approved = self.approved(plugin_id, version, fingerprint)
        if not set(permissions).issubset(approved):
            raise PluginPermissionError("Plugin permissions are pending review.")
