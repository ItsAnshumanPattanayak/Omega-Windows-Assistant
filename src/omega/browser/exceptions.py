"""Browser-specific failures with safe project-level ancestry."""

from omega.core.exceptions import ConfigurationError, OmegaError


class BrowserError(OmegaError):
    """Base class for controlled browser failures."""


class BrowserConfigurationError(ConfigurationError, BrowserError):
    """Raised when browser policy configuration is malformed."""


class BrowserUnavailableError(BrowserError):
    """Raised when the optional browser backend is unavailable."""


class BrowserInitializationError(BrowserError):
    """Raised when an explicitly requested browser session cannot start."""


class BrowserSessionError(BrowserError):
    """Raised when an operation requires a different session state."""


class BrowserNavigationError(BrowserError):
    """Raised when controlled navigation fails."""


class UnsafeUrlError(BrowserNavigationError):
    """Raised before an unsafe URL can reach a browser backend."""


class BrowserTimeoutError(BrowserError):
    """Raised when a bounded browser operation times out."""


class BrowserTabError(BrowserError):
    """Raised for invalid or unavailable Omega-controlled tabs."""
