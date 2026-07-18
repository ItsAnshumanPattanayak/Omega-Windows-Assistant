"""Core Omega abstractions."""

from omega.core.exceptions import (
    ConfigurationError,
    InitializationError,
    ModelValidationError,
    OmegaError,
    UnsupportedPlatformError,
)

__all__ = [
    "ConfigurationError",
    "InitializationError",
    "ModelValidationError",
    "OmegaError",
    "UnsupportedPlatformError",
]
