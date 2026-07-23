"""Deterministic in-memory browser backend for tests and offline smoke checks."""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID, uuid4

from omega.browser.exceptions import BrowserSessionError, BrowserTabError
from omega.browser.models import PageSummary, TabSummary


class FakeBrowserBackend:
    """A no-network backend implementing the production protocol."""

    def __init__(self) -> None:
        self.started = False
        self.start_count = 0
        self.stop_count = 0
        self.navigation_count = 0
        self._tabs: dict[UUID, PageSummary] = {}
        self._current: UUID | None = None
        self._history: dict[UUID, list[str]] = {}
        self._history_index: dict[UUID, int] = {}
        self.redirect_url: str | None = None
        self.fail_next: Exception | None = None

    def start(self, browser_name: str, timeout_ms: int) -> None:
        del browser_name, timeout_ms
        self._raise_if_requested()
        if self.started:
            return
        self.started = True
        self.start_count += 1

    def stop(self, timeout_ms: int) -> None:
        del timeout_ms
        self._raise_if_requested()
        if not self.started:
            return
        self.started = False
        self.stop_count += 1
        self._tabs.clear()
        self._current = None

    def navigate(
        self, url: str, timeout_ms: int, *, new_tab: bool = False
    ) -> PageSummary:
        del timeout_ms
        self._active()
        self._raise_if_requested()
        self.navigation_count += 1
        target = self.redirect_url or url
        self.redirect_url = None
        if new_tab or self._current is None:
            tab_id = uuid4()
            self._current = tab_id
            self._history[tab_id] = [target]
            self._history_index[tab_id] = 0
        else:
            tab_id = self._current
            history = self._history[tab_id]
            index = self._history_index[tab_id]
            del history[index + 1 :]
            history.append(target)
            self._history_index[tab_id] = len(history) - 1
        page = PageSummary(
            tab_id,
            f"Page at {target}",
            target,
            f"Visible text for {target}",
            "complete",
        )
        self._tabs[tab_id] = page
        return page

    def close_tab(self, tab_id: UUID, timeout_ms: int) -> TabSummary:
        del timeout_ms
        self._active()
        self._raise_if_requested()
        page = self._tabs.pop(tab_id, None)
        if page is None:
            raise BrowserTabError("That Omega browser tab is unavailable.")
        self._history.pop(tab_id, None)
        self._history_index.pop(tab_id, None)
        if self._current == tab_id:
            self._current = next(iter(self._tabs), None)
        return TabSummary(tab_id, page.title, page.url, False)

    def switch_tab(self, tab_id: UUID, timeout_ms: int) -> TabSummary:
        del timeout_ms
        self._active()
        self._raise_if_requested()
        page = self._tabs.get(tab_id)
        if page is None:
            raise BrowserTabError("That Omega browser tab is unavailable.")
        self._current = tab_id
        return TabSummary(tab_id, page.title, page.url, True)

    def list_tabs(self) -> tuple[TabSummary, ...]:
        self._active()
        return tuple(
            TabSummary(tab_id, page.title, page.url, tab_id == self._current)
            for tab_id, page in self._tabs.items()
        )

    def refresh(self, timeout_ms: int) -> PageSummary:
        del timeout_ms
        return self._current_page()

    def go_back(self, timeout_ms: int) -> PageSummary:
        del timeout_ms
        page = self._current_page()
        index = max(0, self._history_index[page.tab_id] - 1)
        self._history_index[page.tab_id] = index
        return self._set_history_page(page.tab_id)

    def go_forward(self, timeout_ms: int) -> PageSummary:
        del timeout_ms
        page = self._current_page()
        history = self._history[page.tab_id]
        index = min(len(history) - 1, self._history_index[page.tab_id] + 1)
        self._history_index[page.tab_id] = index
        return self._set_history_page(page.tab_id)

    def page_information(self, timeout_ms: int) -> PageSummary:
        del timeout_ms
        return self._current_page()

    def find_text(self, text: str, timeout_ms: int) -> PageSummary:
        del timeout_ms
        page = self._current_page()
        count = page.visible_text.casefold().count(text.casefold())
        return replace(page, text_match_count=count)

    def _set_history_page(self, tab_id: UUID) -> PageSummary:
        url = self._history[tab_id][self._history_index[tab_id]]
        page = PageSummary(
            tab_id,
            f"Page at {url}",
            url,
            f"Visible text for {url}",
            "complete",
        )
        self._tabs[tab_id] = page
        return page

    def _current_page(self) -> PageSummary:
        self._active()
        self._raise_if_requested()
        if self._current is None or self._current not in self._tabs:
            raise BrowserTabError("No Omega browser tab is open.")
        return self._tabs[self._current]

    def _active(self) -> None:
        if not self.started:
            raise BrowserSessionError("The Omega browser session is not active.")

    def _raise_if_requested(self) -> None:
        if self.fail_next is not None:
            error = self.fail_next
            self.fail_next = None
            raise error
