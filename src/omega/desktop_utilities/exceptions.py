"""Safe desktop-utility domain failures."""

from omega.core.exceptions import OmegaError


class DesktopUtilityError(OmegaError):
    """Base desktop-utility failure."""


class DesktopUtilityConfigurationError(DesktopUtilityError):
    """Desktop-utility configuration is invalid."""


class DesktopUtilityUnavailableError(DesktopUtilityError):
    """A requested desktop capability is unavailable."""


class ClipboardError(DesktopUtilityError):
    """Clipboard access failed safely."""


class UnsupportedClipboardFormatError(ClipboardError):
    """Clipboard content is not supported plain text."""


class ScreenshotError(DesktopUtilityError):
    """Screenshot capture or metadata handling failed safely."""


class DisplayUnavailableError(DesktopUtilityError):
    """Display metadata is unavailable."""


class WindowMetadataError(DesktopUtilityError):
    """Window metadata or selection is unavailable."""
