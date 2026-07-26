"""Public privacy-first desktop utility API."""

from omega.desktop_utilities.adapters import (
    PillowScreenshotBackend,
    TkClipboardBackend,
    TkScreenInformationProvider,
    WindowsPathOpener,
    WindowsWindowInformationProvider,
)
from omega.desktop_utilities.configuration import DesktopUtilitiesConfiguration
from omega.desktop_utilities.exceptions import (
    ClipboardError,
    DesktopUtilityConfigurationError,
    DesktopUtilityError,
    DesktopUtilityUnavailableError,
    DisplayUnavailableError,
    ScreenshotError,
    UnsupportedClipboardFormatError,
    WindowMetadataError,
)
from omega.desktop_utilities.fake import (
    FakeClipboardBackend,
    FakeScreenInformationProvider,
    FakeScreenshotBackend,
    FakeWindowInformationProvider,
)
from omega.desktop_utilities.models import (
    DisplayInformation,
    ScreenshotRecord,
    ScreenshotRegion,
    ScreenshotRequest,
    ScreenshotTarget,
    WindowInformation,
)
from omega.desktop_utilities.services import (
    ClipboardService,
    DesktopInformationService,
    ScreenshotService,
)

__all__ = [
    "ClipboardError",
    "ClipboardService",
    "DesktopInformationService",
    "DesktopUtilitiesConfiguration",
    "DesktopUtilityConfigurationError",
    "DesktopUtilityError",
    "DesktopUtilityUnavailableError",
    "DisplayInformation",
    "DisplayUnavailableError",
    "FakeClipboardBackend",
    "FakeScreenInformationProvider",
    "FakeScreenshotBackend",
    "FakeWindowInformationProvider",
    "PillowScreenshotBackend",
    "ScreenshotError",
    "ScreenshotRecord",
    "ScreenshotRegion",
    "ScreenshotRequest",
    "ScreenshotService",
    "ScreenshotTarget",
    "TkClipboardBackend",
    "TkScreenInformationProvider",
    "UnsupportedClipboardFormatError",
    "WindowInformation",
    "WindowMetadataError",
    "WindowsPathOpener",
    "WindowsWindowInformationProvider",
]
