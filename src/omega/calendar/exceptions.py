"""Calendar-specific failures with safe user-facing messages."""

from omega.core.exceptions import OmegaError


class CalendarError(OmegaError):
    """Base class for calendar failures."""


class CalendarConfigurationError(CalendarError):
    """Calendar policy configuration is invalid."""


class CalendarValidationError(CalendarError):
    """Calendar input or state is invalid."""


class CalendarNotFoundError(CalendarError):
    """A selected calendar event no longer exists."""


class CalendarProviderError(CalendarError):
    """A provider failed without exposing provider details."""


class CalendarProviderTimeout(CalendarProviderError):
    """A provider mutation timed out with an ambiguous outcome."""


class CalendarUnavailableError(CalendarError):
    """Calendar assistance is disabled or lacks a provider."""
