"""Bounded personalization-domain errors."""

from omega.core.exceptions import OmegaError


class PersonalizationError(OmegaError):
    """Base class for safe user-facing personalization failures."""


class PersonalizationDisabledError(PersonalizationError):
    """Raised when explicit personalization is unavailable by policy."""


class ProfileError(PersonalizationError):
    """Raised for bounded profile lifecycle failures."""


class PreferenceValidationError(PersonalizationError):
    """Raised when an explicit preference is unknown, invalid, or unsafe."""


class ProfileTransferError(PersonalizationError):
    """Raised for safe export, preview, or import failures."""


class PreferencePermissionError(PersonalizationError):
    """Raised when a plugin or workflow requests unavailable profile data."""
