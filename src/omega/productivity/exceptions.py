"""Narrow failures for Omega's local productivity workspace."""

from omega.core.exceptions import OmegaError


class ProductivityError(OmegaError):
    """Base class for safe productivity failures."""


class ProductivityConfigurationError(ProductivityError):
    """Raised when productivity policy is malformed."""


class ProductivityNotFoundError(ProductivityError):
    """Raised when a requested note, task list, task, or reminder is absent."""


class ProductivityConflictError(ProductivityError):
    """Raised for duplicate names or invalid lifecycle conflicts."""


class StaleProductivityRevisionError(ProductivityConflictError):
    """Raised when an optimistic update targets an old revision."""


class ProductivityImportError(ProductivityError):
    """Raised when a local JSON import is unsafe or malformed."""


class ProductivityExportError(ProductivityError):
    """Raised when a bounded local export cannot be completed safely."""


class InvalidTagError(ProductivityError):
    """Raised when a tag is empty, oversized, or contains control characters."""


class ReminderLinkError(ProductivityError):
    """Raised when a task/reminder association is invalid."""
