"""Project-specific exception hierarchy."""


class OmegaError(Exception):
    """Base class for all Omega-specific errors."""


class ConfigurationError(OmegaError):
    """Raised when Omega configuration is missing or invalid."""


class InitializationError(OmegaError):
    """Raised when the application cannot initialize safely."""


class UnsupportedPlatformError(OmegaError):
    """Raised when the current runtime does not meet Omega requirements."""


class ModelValidationError(OmegaError):
    """Raised when a typed Omega model contains an invalid state or value."""


class SessionError(OmegaError):
    """Base exception for invalid Omega text-session behavior."""


class InvalidSessionTransitionError(SessionError):
    """Raised when a session state transition is not permitted."""


class ApplicationError(OmegaError):
    """Base exception for invalid controlled-application behavior."""


class ApplicationRegistryError(ApplicationError):
    """Raised when the allowlisted application registry is invalid."""
