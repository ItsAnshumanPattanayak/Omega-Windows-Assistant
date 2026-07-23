"""Typed browser record and process-local bookmark tests."""

from datetime import UTC
from uuid import uuid4

import pytest

from omega.browser import (
    BookmarkStore,
    BrowserConfiguration,
    BrowserError,
    BrowserSessionState,
    PageSummary,
    TabSummary,
    UrlValidator,
)


def test_browser_state_values_are_stable() -> None:
    assert [state.value for state in BrowserSessionState] == [
        "stopped",
        "starting",
        "active",
        "stopping",
        "failed",
    ]


def test_tab_and_page_serialization_contains_no_backend_objects() -> None:
    tab_id = uuid4()
    tab = TabSummary(tab_id, "Example", "https://example.com/", True)
    page = PageSummary(tab_id, "Example", "https://example.com/", "text", "complete")
    assert tab.to_dict()["tab_id"] == str(tab_id)
    assert page.to_dict()["visible_text"] == "text"
    assert "cookies" not in page.to_dict()
    assert "html" not in page.to_dict()


def test_bookmark_round_trip_and_deterministic_listing() -> None:
    config = BrowserConfiguration()
    store = BookmarkStore(config, UrlValidator(config))
    second = store.save("Zulu", "https://z.example/")
    first = store.save("Alpha", "https://a.example/")
    assert store.get(" alpha ") == first
    assert store.list() == (first, second)
    assert first.created_at.tzinfo is UTC
    assert "metadata" in first.to_dict()


def test_duplicate_and_invalid_bookmarks_are_rejected() -> None:
    config = BrowserConfiguration()
    store = BookmarkStore(config, UrlValidator(config))
    store.save("Docs", "https://example.com/")
    with pytest.raises(BrowserError, match="already exists"):
        store.save("docs", "https://example.org/")
    with pytest.raises(BrowserError):
        store.save("", "https://example.com/")
    with pytest.raises(BrowserError):
        store.save("Unsafe", "http://example.com/")


def test_bookmark_metadata_defaults_are_independent() -> None:
    config = BrowserConfiguration()
    store = BookmarkStore(config, UrlValidator(config))
    first = store.save("One", "https://one.example/")
    second = store.save("Two", "https://two.example/")
    assert first.metadata is not second.metadata
