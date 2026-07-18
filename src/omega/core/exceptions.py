"""Project-specific exception hierarchy."""


class OmegaError(Exception):
    """Base class for all Omega-specific errors."""


class ConfigurationError(OmegaError):
    """Raised when Omega configuration is missing or invalid."""


class InitializationError(OmegaError):
    """Raised when the application cannot initialize safely."""


class UnsupportedPlatformError(OmegaError):
    """Raised when the current runtime does not meet Omega requirements."""
