"""Application-facing plugin management with explicit review boundaries."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from omega.plugins.configuration import PluginConfiguration
from omega.plugins.discovery import PluginDiscovery
from omega.plugins.exceptions import PluginError, PluginValidationError
from omega.plugins.lifecycle import PluginLifecycle
from omega.plugins.models import (
    PluginContext,
    PluginLoadResult,
    PluginMetadata,
    PluginPermission,
    PluginStatus,
)
from omega.plugins.package import PluginPackageInstaller
from omega.plugins.permissions import PluginPermissionService
from omega.plugins.registry import PluginRegistry
from omega.plugins.repository import PluginRepository
from omega.plugins.validation import PLUGIN_API_VERSION, PluginValidator


class PluginManager:
    def __init__(
        self,
        configuration: PluginConfiguration,
        discovery: PluginDiscovery,
        installer: PluginPackageInstaller,
        validator: PluginValidator,
        repository: PluginRepository,
        permissions: PluginPermissionService,
        lifecycle: PluginLifecycle,
        registry: PluginRegistry | None = None,
    ) -> None:
        self.configuration = configuration
        self.discovery = discovery
        self.installer = installer
        self.validator = validator
        self.repository = repository
        self.permissions = permissions
        self.lifecycle = lifecycle
        self.registry = registry or PluginRegistry()
        self._plugins: dict[str, PluginMetadata] = {}
        self._selection: str | None = None

    def discover(self) -> tuple[PluginMetadata, ...]:
        items = self.discovery.discover()
        self._plugins = {item.manifest.plugin_id: item for item in items}
        self._selection = None
        return items

    def install(self, package: Path) -> PluginMetadata:
        if not self.configuration.enabled:
            raise PluginError("Plugin support is disabled.")
        manifest, destination = self.installer.install(package)
        metadata = PluginMetadata(
            manifest,
            str(destination),
            self.validator.fingerprint(destination),
            PluginStatus.DISABLED,
        )
        self.repository.save(metadata)
        self._plugins[manifest.plugin_id] = metadata
        self._selection = manifest.plugin_id
        return metadata

    def select(self, plugin_id: str) -> PluginMetadata:
        metadata = self._plugins.get(plugin_id)
        if metadata is None:
            raise PluginValidationError("Plugin is not selected or installed.")
        self._selection = plugin_id
        return metadata

    def selected(self) -> PluginMetadata:
        if self._selection is None:
            raise PluginValidationError("Select a plugin first.")
        return self.select(self._selection)

    def grant(self, permission: PluginPermission) -> None:
        metadata = self.selected()
        self.permissions.grant(metadata.manifest, metadata.fingerprint, permission)

    def revoke(self, permission: PluginPermission) -> None:
        metadata = self.selected()
        self.permissions.revoke(metadata.manifest.plugin_id, permission)

    def enable(self) -> PluginMetadata:
        metadata = self.selected()
        root = Path(metadata.source_path)
        if self.validator.fingerprint(root) != metadata.fingerprint:
            changed = replace(metadata, status=PluginStatus.UPDATE_REVIEW_REQUIRED)
            self._plugins[metadata.manifest.plugin_id] = changed
            self.repository.save(changed)
            raise PluginValidationError("Plugin changed and requires a new review.")
        enabled = replace(metadata, status=PluginStatus.ENABLED)
        self._plugins[metadata.manifest.plugin_id] = enabled
        self.repository.save(enabled)
        return enabled

    def activate(self) -> PluginLoadResult:
        metadata = self.selected()
        approved = self.permissions.approved(
            metadata.manifest.plugin_id,
            str(metadata.manifest.version),
            metadata.fingerprint,
        )
        context = PluginContext(
            metadata.manifest.plugin_id, PLUGIN_API_VERSION, approved
        )
        try:
            result = self.lifecycle.activate(metadata, context)
            instance = self.lifecycle.instance(metadata.manifest.plugin_id)
            commands = getattr(instance, "commands", None)
            if callable(commands):
                for name, handler in commands().items():
                    self.registry.register_command(
                        metadata.manifest.plugin_id, name, handler, approved
                    )
            workflow_steps = getattr(instance, "workflow_steps", None)
            if callable(workflow_steps):
                for name, handler in workflow_steps().items():
                    self.registry.register_workflow_step(
                        metadata.manifest.plugin_id, name, handler, approved
                    )
        except PluginError:
            try:
                self.lifecycle.deactivate(metadata.manifest.plugin_id)
            finally:
                self.registry.unregister(metadata.manifest.plugin_id)
            self.repository.set_status(metadata.manifest.plugin_id, PluginStatus.FAILED)
            self.repository.record_failure(
                metadata.manifest.plugin_id, "activation_failure"
            )
            raise
        active = replace(metadata, status=PluginStatus.ACTIVE)
        self._plugins[metadata.manifest.plugin_id] = active
        self.repository.save(active)
        return result

    def disable(self) -> None:
        metadata = self.selected()
        self.lifecycle.deactivate(metadata.manifest.plugin_id)
        self.registry.unregister(metadata.manifest.plugin_id)
        disabled = replace(metadata, status=PluginStatus.DISABLED)
        self._plugins[metadata.manifest.plugin_id] = disabled
        self.repository.save(disabled)

    def remove(self) -> None:
        metadata = self.selected()
        self.lifecycle.deactivate(metadata.manifest.plugin_id)
        self.registry.unregister(metadata.manifest.plugin_id)
        target = Path(metadata.source_path).resolve(strict=True)
        install_root = self.installer.install_root
        if target.parent != install_root or target.is_symlink():
            raise PluginValidationError("Installed plugin path is unsafe to remove.")
        removed_root = install_root / "removed"
        removed_root.mkdir(parents=True, exist_ok=True)
        quarantine = removed_root / f"{metadata.manifest.plugin_id}-{uuid4().hex}"
        os.replace(target, quarantine)
        removed = replace(metadata, status=PluginStatus.REMOVED)
        self.repository.save(removed)
        self._plugins.pop(metadata.manifest.plugin_id, None)
        self._selection = None

    def clear_session(self) -> None:
        self._selection = None

    def shutdown(self) -> None:
        self.lifecycle.shutdown()
