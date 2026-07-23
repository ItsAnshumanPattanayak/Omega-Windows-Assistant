"""Optional, lazily imported Playwright adapter for one isolated browser context."""

from __future__ import annotations

from importlib import import_module
from typing import Any
from uuid import UUID, uuid4

from omega.browser.exceptions import (
    BrowserInitializationError,
    BrowserNavigationError,
    BrowserSessionError,
    BrowserTabError,
    BrowserTimeoutError,
    BrowserUnavailableError,
)
from omega.browser.models import PageSummary, TabSummary
from omega.browser.validation import UrlValidator


class PlaywrightBrowserBackend:
    """Control only the browser and non-persistent context launched by Omega."""

    def __init__(self, validator: UrlValidator | None = None) -> None:
        self._validator = validator
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._pages: dict[UUID, Any] = {}
        self._current: UUID | None = None

    def start(self, browser_name: str, timeout_ms: int) -> None:
        del timeout_ms
        if self._browser is not None:
            return
        try:
            sync_api = import_module("playwright.sync_api")
        except ImportError as error:
            raise BrowserUnavailableError(
                "Optional Playwright support is not installed."
            ) from error
        try:
            self._playwright = sync_api.sync_playwright().start()
            browser_type = (
                self._playwright.firefox
                if browser_name == "firefox"
                else self._playwright.chromium
            )
            channel = {"edge": "msedge", "chrome": "chrome"}.get(browser_name)
            launch_options: dict[str, Any] = {"headless": False}
            if channel is not None:
                launch_options["channel"] = channel
            self._browser = browser_type.launch(**launch_options)
            self._context = self._browser.new_context(
                accept_downloads=False,
                service_workers="block",
            )
            if self._validator is not None:
                self._context.route("**/*", self._route_request)
        except Exception as error:
            self._cleanup()
            raise BrowserInitializationError(
                "Omega could not start its controlled browser session."
            ) from error

    def stop(self, timeout_ms: int) -> None:
        del timeout_ms
        self._cleanup()

    def navigate(
        self, url: str, timeout_ms: int, *, new_tab: bool = False
    ) -> PageSummary:
        self._active()
        try:
            if new_tab or self._current is None:
                page = self._context.new_page()
                tab_id = uuid4()
                self._pages[tab_id] = page
                self._current = tab_id
            else:
                tab_id = self._current
                page = self._pages[tab_id]
            page.goto(
                url,
                timeout=timeout_ms,
                wait_until="domcontentloaded",
            )
            return self._page_summary(tab_id, page)
        except BrowserSessionError:
            raise
        except Exception as error:
            if error.__class__.__name__ == "TimeoutError":
                raise BrowserTimeoutError(
                    "Browser navigation exceeded its safe timeout."
                ) from error
            raise BrowserNavigationError(
                "The controlled browser could not complete navigation."
            ) from error

    def close_tab(self, tab_id: UUID, timeout_ms: int) -> TabSummary:
        del timeout_ms
        page = self._page(tab_id)
        summary = self._tab_summary(tab_id, page)
        try:
            page.close()
        except Exception as error:
            raise BrowserTabError("Omega could not close that browser tab.") from error
        self._pages.pop(tab_id, None)
        if self._current == tab_id:
            self._current = next(reversed(self._pages), None)
        return summary

    def switch_tab(self, tab_id: UUID, timeout_ms: int) -> TabSummary:
        del timeout_ms
        page = self._page(tab_id)
        try:
            page.bring_to_front()
        except Exception as error:
            raise BrowserTabError("Omega could not switch to that tab.") from error
        self._current = tab_id
        return self._tab_summary(tab_id, page, current=True)

    def list_tabs(self) -> tuple[TabSummary, ...]:
        self._active()
        self._drop_closed_pages()
        return tuple(
            self._tab_summary(tab_id, page, current=tab_id == self._current)
            for tab_id, page in self._pages.items()
        )

    def refresh(self, timeout_ms: int) -> PageSummary:
        tab_id, page = self._current_page()
        try:
            page.reload(timeout=timeout_ms, wait_until="domcontentloaded")
            return self._page_summary(tab_id, page)
        except Exception as error:
            if error.__class__.__name__ == "TimeoutError":
                raise BrowserTimeoutError(
                    "Page refresh exceeded its safe timeout."
                ) from error
            raise BrowserNavigationError("Omega could not refresh the page.") from error

    def go_back(self, timeout_ms: int) -> PageSummary:
        tab_id, page = self._current_page()
        try:
            page.go_back(timeout=timeout_ms, wait_until="domcontentloaded")
            return self._page_summary(tab_id, page)
        except Exception as error:
            if error.__class__.__name__ == "TimeoutError":
                raise BrowserTimeoutError(
                    "Backward navigation exceeded its safe timeout."
                ) from error
            raise BrowserNavigationError("Omega could not go back.") from error

    def go_forward(self, timeout_ms: int) -> PageSummary:
        tab_id, page = self._current_page()
        try:
            page.go_forward(timeout=timeout_ms, wait_until="domcontentloaded")
            return self._page_summary(tab_id, page)
        except Exception as error:
            if error.__class__.__name__ == "TimeoutError":
                raise BrowserTimeoutError(
                    "Forward navigation exceeded its safe timeout."
                ) from error
            raise BrowserNavigationError("Omega could not go forward.") from error

    def page_information(self, timeout_ms: int) -> PageSummary:
        del timeout_ms
        tab_id, page = self._current_page()
        return self._page_summary(tab_id, page)

    def find_text(self, text: str, timeout_ms: int) -> PageSummary:
        del timeout_ms
        tab_id, page = self._current_page()
        summary = self._page_summary(tab_id, page)
        return PageSummary(
            summary.tab_id,
            summary.title,
            summary.url,
            summary.visible_text,
            summary.load_state,
            summary.visible_text.casefold().count(text.casefold()),
        )

    def _page_summary(self, tab_id: UUID, page: Any) -> PageSummary:
        try:
            visible = page.locator("body").inner_text(timeout=2_000)
        except Exception:
            visible = ""
        try:
            title = page.title()
            url = page.url
        except Exception as error:
            raise BrowserTabError("The browser page is no longer available.") from error
        return PageSummary(tab_id, title, url, visible, "domcontentloaded")

    def _route_request(self, route: Any, request: Any) -> None:
        """Abort unsafe top-level and subresource network targets."""

        if self._validator is None:
            route.abort()
            return
        try:
            self._validator.validate(request.url)
        except Exception:
            route.abort()
            return
        route.continue_()

    def _tab_summary(
        self, tab_id: UUID, page: Any, *, current: bool = False
    ) -> TabSummary:
        summary = self._page_summary(tab_id, page)
        return TabSummary(tab_id, summary.title, summary.url, current)

    def _page(self, tab_id: UUID) -> Any:
        self._active()
        page = self._pages.get(tab_id)
        if page is None or page.is_closed():
            self._pages.pop(tab_id, None)
            raise BrowserTabError("That Omega browser tab is unavailable.")
        return page

    def _current_page(self) -> tuple[UUID, Any]:
        self._active()
        if self._current is None:
            raise BrowserTabError("No Omega browser tab is open.")
        return self._current, self._page(self._current)

    def _drop_closed_pages(self) -> None:
        for tab_id, page in tuple(self._pages.items()):
            if page.is_closed():
                self._pages.pop(tab_id, None)
        if self._current not in self._pages:
            self._current = next(reversed(self._pages), None)

    def _active(self) -> None:
        if (
            self._browser is None
            or self._context is None
            or not self._browser.is_connected()
        ):
            raise BrowserSessionError("The Omega browser session is not active.")

    def _cleanup(self) -> None:
        context, browser, playwright = (
            self._context,
            self._browser,
            self._playwright,
        )
        self._context = self._browser = self._playwright = None
        self._pages.clear()
        self._current = None
        for resource in (context, browser, playwright):
            if resource is None:
                continue
            try:
                if resource is playwright:
                    resource.stop()
                else:
                    resource.close()
            except Exception:
                continue
