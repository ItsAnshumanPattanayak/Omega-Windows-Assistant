"""Optional-backend and import-side-effect tests."""

import importlib

import pytest

from omega.browser import (
    BrowserConfiguration,
    BrowserUnavailableError,
    PlaywrightBrowserBackend,
    UrlValidator,
)


def test_browser_import_does_not_initialize_playwright_or_resources() -> None:
    module = importlib.import_module("omega.browser")
    backend = module.PlaywrightBrowserBackend()
    assert backend._playwright is None
    assert backend._browser is None
    assert backend._context is None


def test_missing_playwright_is_a_safe_optional_failure(monkeypatch) -> None:
    backend = PlaywrightBrowserBackend()

    def unavailable(name: str):
        raise ImportError(name)

    monkeypatch.setattr(
        "omega.browser.playwright_backend.import_module",
        unavailable,
    )
    with pytest.raises(BrowserUnavailableError, match="not installed"):
        backend.start("edge", 1000)


def test_real_adapter_route_blocks_unsafe_targets_and_continues_safe_ones() -> None:
    class Route:
        def __init__(self) -> None:
            self.aborted = False
            self.continued = False

        def abort(self) -> None:
            self.aborted = True

        def continue_(self) -> None:
            self.continued = True

    class Request:
        def __init__(self, url: str) -> None:
            self.url = url

    config = BrowserConfiguration()
    backend = PlaywrightBrowserBackend(UrlValidator(config))
    unsafe = Route()
    backend._route_request(unsafe, Request("https://127.0.0.1/"))
    assert unsafe.aborted and not unsafe.continued
    safe = Route()
    backend._route_request(safe, Request("https://example.com/"))
    assert safe.continued and not safe.aborted
