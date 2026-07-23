"""Bounded browser-session orchestration without parser or presentation logic."""

from __future__ import annotations

import re
from collections.abc import Callable
from threading import RLock
from uuid import UUID

from omega.browser.bookmarks import BookmarkStore
from omega.browser.configuration import BrowserConfiguration
from omega.browser.exceptions import (
    BrowserError,
    BrowserSessionError,
    BrowserTimeoutError,
    UnsafeUrlError,
)
from omega.browser.models import BrowserSessionState, PageSummary, TabSummary
from omega.browser.protocols import BrowserBackend
from omega.browser.search import build_search_url
from omega.browser.validation import UrlValidator
from omega.models import (
    ActionResult,
    ErrorCategory,
    OmegaErrorDetails,
)
from omega.models._serialization import JsonValue

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class BrowserManager:
    """Serialize one explicitly requested, bounded Omega browser session."""

    def __init__(
        self,
        configuration: BrowserConfiguration,
        backend: BrowserBackend,
        *,
        validator: UrlValidator | None = None,
        bookmarks: BookmarkStore | None = None,
    ) -> None:
        self.configuration = configuration
        self.backend = backend
        self.validator = validator or UrlValidator(configuration)
        self.bookmarks = bookmarks or BookmarkStore(configuration, self.validator)
        self.state = BrowserSessionState.STOPPED
        self._lock = RLock()

    def open_browser(self, action_id: UUID, command_id: UUID) -> ActionResult:
        return self._run(
            action_id,
            command_id,
            self._start,
            "Browser session started.",
            "Omega's controlled browser is ready.",
        )

    def close_browser(self, action_id: UUID, command_id: UUID) -> ActionResult:
        def operation() -> dict[str, JsonValue]:
            if self.state is BrowserSessionState.STOPPED:
                return {"closed": False}
            self.state = BrowserSessionState.STOPPING
            try:
                self.backend.stop(self.configuration.operation_timeout_seconds * 1000)
            finally:
                self.state = BrowserSessionState.STOPPED
            return {"closed": True}

        return self._run(
            action_id,
            command_id,
            operation,
            "Browser session stopped.",
            "Omega's controlled browser session was closed.",
        )

    def navigate(
        self,
        action_id: UUID,
        command_id: UUID,
        url: str,
        *,
        new_tab: bool = False,
    ) -> ActionResult:
        def operation() -> dict[str, JsonValue]:
            validated = self.validator.validate(url)
            self._start()
            if (
                new_tab
                and len(self.backend.list_tabs())
                >= self.configuration.maximum_open_tabs
            ):
                raise BrowserSessionError("The maximum number of browser tabs is open.")
            page = self.backend.navigate(
                validated.url,
                self.configuration.navigation_timeout_seconds * 1000,
                new_tab=new_tab,
            )
            safe_page = self._safe_page(page)
            return {"page": safe_page.to_dict(), "host": validated.host}

        return self._run(
            action_id,
            command_id,
            operation,
            "Browser navigation completed.",
            "The validated page is open in Omega's controlled browser.",
        )

    def search(
        self,
        action_id: UUID,
        command_id: UUID,
        query: str,
        engine: str | None = None,
    ) -> ActionResult:
        selected = engine or self.configuration.default_search_engine

        def operation() -> dict[str, JsonValue]:
            search_url = build_search_url(
                query, selected, self.configuration, self.validator
            )
            self._start()
            if len(self.backend.list_tabs()) >= self.configuration.maximum_open_tabs:
                raise BrowserSessionError("The maximum number of browser tabs is open.")
            page = self.backend.navigate(
                search_url.url,
                self.configuration.navigation_timeout_seconds * 1000,
                new_tab=True,
            )
            return {
                "page": self._navigation_data(self._safe_page(page)),
                "engine": selected,
            }

        return self._run(
            action_id,
            command_id,
            operation,
            "Web search opened.",
            f"The search is open using {selected.title()}.",
        )

    def open_new_tab(self, action_id: UUID, command_id: UUID) -> ActionResult:
        home = "https://duckduckgo.com/"
        return self.navigate(action_id, command_id, home, new_tab=True)

    def close_tab(
        self, action_id: UUID, command_id: UUID, tab_id: UUID
    ) -> ActionResult:
        return self._tab_operation(
            action_id,
            command_id,
            lambda: self.backend.close_tab(
                tab_id, self.configuration.operation_timeout_seconds * 1000
            ),
            "Browser tab closed.",
            "The selected Omega browser tab was closed.",
        )

    def switch_tab(
        self, action_id: UUID, command_id: UUID, tab_id: UUID
    ) -> ActionResult:
        return self._tab_operation(
            action_id,
            command_id,
            lambda: self.backend.switch_tab(
                tab_id, self.configuration.operation_timeout_seconds * 1000
            ),
            "Browser tab selected.",
            "Omega switched to the selected browser tab.",
        )

    def list_tabs(self, action_id: UUID, command_id: UUID) -> ActionResult:
        def operation() -> dict[str, JsonValue]:
            self._require_active()
            tabs = tuple(self._safe_tab(tab) for tab in self.backend.list_tabs())
            return {"tabs": [tab.to_dict() for tab in tabs]}

        return self._run(
            action_id,
            command_id,
            operation,
            "Browser tabs listed.",
            "Open tabs are listed in the action result.",
        )

    def refresh(self, action_id: UUID, command_id: UUID) -> ActionResult:
        return self._page_operation(
            action_id,
            command_id,
            lambda: self.backend.refresh(
                self.configuration.navigation_timeout_seconds * 1000
            ),
            "Page refreshed.",
            "The current page was refreshed.",
        )

    def go_back(self, action_id: UUID, command_id: UUID) -> ActionResult:
        return self._page_operation(
            action_id,
            command_id,
            lambda: self.backend.go_back(
                self.configuration.navigation_timeout_seconds * 1000
            ),
            "Browser moved backward.",
            "Omega went back in the current tab.",
        )

    def go_forward(self, action_id: UUID, command_id: UUID) -> ActionResult:
        return self._page_operation(
            action_id,
            command_id,
            lambda: self.backend.go_forward(
                self.configuration.navigation_timeout_seconds * 1000
            ),
            "Browser moved forward.",
            "Omega went forward in the current tab.",
        )

    def page_information(self, action_id: UUID, command_id: UUID) -> ActionResult:
        return self._page_operation(
            action_id,
            command_id,
            lambda: self.backend.page_information(
                self.configuration.operation_timeout_seconds * 1000
            ),
            "Safe page information retrieved.",
            "Safe page information is available in the action result.",
        )

    def find_text(self, action_id: UUID, command_id: UUID, text: str) -> ActionResult:
        cleaned = " ".join(text.split())
        if not cleaned or len(cleaned) > 500:
            return self._failure(
                action_id,
                command_id,
                "INVALID_FIND_TEXT",
                "Find text must contain between 1 and 500 characters.",
                ErrorCategory.VALIDATION,
            )
        return self._page_operation(
            action_id,
            command_id,
            lambda: self.backend.find_text(
                cleaned, self.configuration.operation_timeout_seconds * 1000
            ),
            "Page text search completed.",
            "Omega searched the visible page text.",
        )

    def save_bookmark(
        self, action_id: UUID, command_id: UUID, name: str, url: str
    ) -> ActionResult:
        return self._run(
            action_id,
            command_id,
            lambda: {"bookmark": self.bookmarks.save(name, url).to_dict()},
            "Bookmark saved.",
            "The bookmark was saved in Omega's current process.",
        )

    def save_current_bookmark(
        self, action_id: UUID, command_id: UUID, name: str
    ) -> ActionResult:
        def operation() -> dict[str, JsonValue]:
            self._require_active()
            page = self._safe_page(
                self.backend.page_information(
                    self.configuration.operation_timeout_seconds * 1000
                )
            )
            bookmark = self.bookmarks.save(name, page.url)
            return {"bookmark": bookmark.to_dict()}

        return self._run(
            action_id,
            command_id,
            operation,
            "Bookmark saved.",
            "The current page was saved in Omega's current-process bookmarks.",
        )

    def open_bookmark(
        self, action_id: UUID, command_id: UUID, name: str
    ) -> ActionResult:
        bookmark = self.bookmarks.get(name)
        if bookmark is None:
            return self._failure(
                action_id,
                command_id,
                "BOOKMARK_NOT_FOUND",
                "Omega could not find that bookmark.",
                ErrorCategory.NOT_FOUND,
            )
        return self.navigate(action_id, command_id, bookmark.url, new_tab=True)

    def shutdown(self) -> None:
        """Best-effort cleanup called only from explicit application shutdown."""

        with self._lock:
            if self.state is BrowserSessionState.STOPPED:
                return
            try:
                self.backend.stop(self.configuration.operation_timeout_seconds * 1000)
            finally:
                self.state = BrowserSessionState.STOPPED

    def resolve_tab_id(self, reference: str) -> UUID:
        """Resolve a one-based tab number or exact stable UUID."""

        with self._lock:
            self._require_active()
            tabs = self.backend.list_tabs()
            normalized = reference.strip()
            if normalized.isdigit():
                index = int(normalized)
                if 1 <= index <= len(tabs):
                    return tabs[index - 1].tab_id
                raise BrowserSessionError("That tab number is not open.")
            try:
                candidate = UUID(normalized)
            except ValueError as error:
                raise BrowserSessionError("The tab reference is invalid.") from error
            if any(tab.tab_id == candidate for tab in tabs):
                return candidate
            raise BrowserSessionError("That Omega browser tab is unavailable.")

    def _start(self) -> dict[str, JsonValue]:
        if not self.configuration.enabled or not self.configuration.automation_enabled:
            raise BrowserSessionError("Browser automation is disabled.")
        if self.state is BrowserSessionState.ACTIVE:
            return {"already_active": True}
        self.state = BrowserSessionState.STARTING
        try:
            self.backend.start(
                self.configuration.preferred_browser,
                self.configuration.operation_timeout_seconds * 1000,
            )
        except Exception:
            self.state = BrowserSessionState.FAILED
            raise
        self.state = BrowserSessionState.ACTIVE
        return {"already_active": False}

    def _require_active(self) -> None:
        if self.state is not BrowserSessionState.ACTIVE:
            raise BrowserSessionError("The Omega browser session is not active.")

    def _tab_operation(
        self,
        action_id: UUID,
        command_id: UUID,
        operation: Callable[[], TabSummary],
        message: str,
        user_message: str,
    ) -> ActionResult:
        def wrapped() -> dict[str, JsonValue]:
            self._require_active()
            return {"tab": self._safe_tab(operation()).to_dict()}

        return self._run(action_id, command_id, wrapped, message, user_message)

    def _page_operation(
        self,
        action_id: UUID,
        command_id: UUID,
        operation: Callable[[], PageSummary],
        message: str,
        user_message: str,
    ) -> ActionResult:
        def wrapped() -> dict[str, JsonValue]:
            self._require_active()
            return {"page": self._safe_page(operation()).to_dict()}

        return self._run(action_id, command_id, wrapped, message, user_message)

    def _run(
        self,
        action_id: UUID,
        command_id: UUID,
        operation: Callable[[], dict[str, JsonValue]],
        message: str,
        user_message: str,
    ) -> ActionResult:
        with self._lock:
            try:
                data = operation()
                return ActionResult.success_result(
                    action_id,
                    message,
                    user_message,
                    data=data,
                    metadata={"browser_state": self.state.value},
                )
            except UnsafeUrlError as error:
                return self._failure(
                    action_id,
                    command_id,
                    "UNSAFE_URL",
                    str(error),
                    ErrorCategory.SAFETY,
                )
            except BrowserTimeoutError as error:
                return self._failure(
                    action_id,
                    command_id,
                    "BROWSER_TIMEOUT",
                    str(error),
                    ErrorCategory.TIMEOUT,
                )
            except BrowserError as error:
                return self._failure(
                    action_id,
                    command_id,
                    "BROWSER_OPERATION_FAILED",
                    str(error),
                    ErrorCategory.EXECUTION,
                )
            except Exception:
                return self._failure(
                    action_id,
                    command_id,
                    "BROWSER_INTERNAL_ERROR",
                    "The browser backend failed safely.",
                    ErrorCategory.INTERNAL,
                )

    def _safe_page(self, page: PageSummary) -> PageSummary:
        validated = self.validator.validate(page.url)
        title = self._clean(
            page.title, self.configuration.maximum_page_title_characters
        )
        visible = self._clean(
            page.visible_text, self.configuration.maximum_page_text_characters
        )
        return PageSummary(
            page.tab_id,
            title,
            validated.redacted_url,
            visible,
            self._clean(page.load_state, 100),
            page.text_match_count,
        )

    def _safe_tab(self, tab: TabSummary) -> TabSummary:
        validated = self.validator.validate(tab.url)
        return TabSummary(
            tab.tab_id,
            self._clean(tab.title, self.configuration.maximum_page_title_characters),
            validated.redacted_url,
            tab.current,
        )

    @staticmethod
    def _clean(value: str, limit: int) -> str:
        return _CONTROL.sub("", value)[:limit]

    @staticmethod
    def _navigation_data(page: PageSummary) -> dict[str, JsonValue]:
        """Exclude page title/text that may repeat a private search query."""

        return {
            "tab_id": str(page.tab_id),
            "url": page.url,
            "load_state": page.load_state,
        }

    @staticmethod
    def _failure(
        action_id: UUID,
        command_id: UUID,
        code: str,
        user_message: str,
        category: ErrorCategory,
    ) -> ActionResult:
        details = OmegaErrorDetails(
            code=code,
            category=category,
            message=user_message,
            user_message=user_message,
            recoverable=category
            in {
                ErrorCategory.EXECUTION,
                ErrorCategory.NOT_FOUND,
                ErrorCategory.TIMEOUT,
            },
            action_id=action_id,
            command_id=command_id,
        )
        return ActionResult.failure_result(
            action_id, user_message, user_message, details
        )
