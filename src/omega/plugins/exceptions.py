"""Bounded plugin-domain failures."""

from omega.core.exceptions import OmegaError


class PluginError(OmegaError):
    """Base class for safe plugin errors."""


class PluginConfigurationError(PluginError):
    """Raised when plugin policy is invalid."""


class PluginValidationError(PluginError):
    """Raised when a manifest or package is invalid."""


class PluginCompatibilityError(PluginError):
    """Raised when a plugin cannot run with this Omega API."""


class PluginPermissionError(PluginError):
    """Raised when a plugin requests an unavailable capability."""


class PluginLoadError(PluginError):
    """Raised when approved plugin code cannot be loaded safely."""


class PluginStorageError(PluginError):
    """Raised for bounded plugin-local storage violations."""
