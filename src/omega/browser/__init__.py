"""Safe optional browser automation for Omega."""

from omega.browser.bookmarks import BookmarkStore
from omega.browser.configuration import BrowserConfiguration
from omega.browser.exceptions import (
    BrowserConfigurationError,
    BrowserError,
    BrowserInitializationError,
    BrowserNavigationError,
    BrowserSessionError,
    BrowserTabError,
    BrowserTimeoutError,
    BrowserUnavailableError,
    UnsafeUrlError,
)
from omega.browser.manager import BrowserManager
from omega.browser.models import (
    Bookmark,
    BrowserSessionState,
    NavigationRequest,
    PageSummary,
    SearchRequest,
    TabSummary,
)
from omega.browser.playwright_backend import PlaywrightBrowserBackend
from omega.browser.protocols import BrowserBackend
from omega.browser.search import build_search_url
from omega.browser.validation import UrlValidator, ValidatedUrl, redact_url

__all__ = [
    "Bookmark",
    "BookmarkStore",
    "BrowserBackend",
    "BrowserConfiguration",
    "BrowserConfigurationError",
    "BrowserError",
    "BrowserInitializationError",
    "BrowserManager",
    "BrowserNavigationError",
    "BrowserSessionError",
    "BrowserSessionState",
    "BrowserTabError",
    "BrowserTimeoutError",
    "BrowserUnavailableError",
    "NavigationRequest",
    "PageSummary",
    "PlaywrightBrowserBackend",
    "SearchRequest",
    "TabSummary",
    "UnsafeUrlError",
    "UrlValidator",
    "ValidatedUrl",
    "build_search_url",
    "redact_url",
]
