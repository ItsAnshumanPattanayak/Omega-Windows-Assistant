"""Privacy-preserving email domain exceptions."""

from omega.core.exceptions import OmegaError


class EmailError(OmegaError):
    """Base exception for provider-independent email operations."""


class EmailConfigurationError(EmailError):
    """Raised when email configuration violates a safe boundary."""


class EmailValidationError(EmailError):
    """Raised when bounded email data is malformed or excessive."""


class EmailUnavailableError(EmailError):
    """Raised when email is disabled or has no configured provider."""


class EmailNotFoundError(EmailError):
    """Raised when a selected message or draft no longer exists."""


class EmailProviderError(EmailError):
    """A redacted provider failure safe to expose to higher layers."""


class EmailProviderTimeout(EmailProviderError):
    """Raised when a provider outcome may be ambiguous after a timeout."""


class DuplicateEmailOperationError(EmailError):
    """Raised when an external mailbox mutation was already attempted."""
