"""Bounded errors for the optional local-AI subsystem."""

from omega.core.exceptions import ConfigurationError, OmegaError


class AiError(OmegaError):
    """Base class for failures at Omega's controlled AI boundary."""


class AiConfigurationError(ConfigurationError, AiError):
    """Raised when local-AI settings violate a conservative boundary."""


class AiDisabledError(AiError):
    """Raised when an optional AI operation is requested while disabled."""


class AiProviderError(AiError):
    """Raised when a configured provider fails safely."""


class AiModelError(AiError):
    """Raised for missing, invalid, or unsupported model descriptors."""


class AiResourceError(AiError):
    """Raised when a bounded queue, timeout, or resource rule is exceeded."""


class AiRequestCancelledError(AiResourceError):
    """Raised when generation is explicitly cancelled."""


class AiValidationError(AiError):
    """Raised when a prompt or provider response fails validation."""


class AiPermissionError(AiError):
    """Raised when a caller lacks explicit local-AI permission."""
