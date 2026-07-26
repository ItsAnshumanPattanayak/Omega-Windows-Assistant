"""Public secure plugin architecture API."""

from omega.plugins.configuration import PluginConfiguration
from omega.plugins.discovery import PluginDiscovery
from omega.plugins.fake import FakeReadOnlyPlugin
from omega.plugins.lifecycle import PluginLifecycle, PluginLoader
from omega.plugins.models import (
    PluginApiVersion,
    PluginCapability,
    PluginCategory,
    PluginContext,
    PluginIdentifier,
    PluginLoadResult,
    PluginManifest,
    PluginMetadata,
    PluginPermission,
    PluginRegistration,
    PluginStatus,
    PluginValidationResult,
    PluginVersion,
)
from omega.plugins.package import PluginPackageInstaller
from omega.plugins.permissions import PluginPermissionService
from omega.plugins.registry import PluginRegistry
from omega.plugins.repository import PluginRepository
from omega.plugins.service import PluginManager
from omega.plugins.storage import PluginLocalStorage
from omega.plugins.validation import PLUGIN_API_VERSION, PluginValidator

__all__ = [
    "PLUGIN_API_VERSION",
    "FakeReadOnlyPlugin",
    "PluginApiVersion",
    "PluginCapability",
    "PluginCategory",
    "PluginConfiguration",
    "PluginContext",
    "PluginDiscovery",
    "PluginIdentifier",
    "PluginLifecycle",
    "PluginLoadResult",
    "PluginLoader",
    "PluginLocalStorage",
    "PluginManager",
    "PluginManifest",
    "PluginMetadata",
    "PluginPackageInstaller",
    "PluginPermission",
    "PluginPermissionService",
    "PluginRegistration",
    "PluginRegistry",
    "PluginRepository",
    "PluginStatus",
    "PluginValidationResult",
    "PluginValidator",
    "PluginVersion",
]
