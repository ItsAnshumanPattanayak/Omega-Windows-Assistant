"""No-network browser manager tests using the deterministic fake backend."""

from uuid import uuid4

from omega.browser import (
    BrowserConfiguration,
    BrowserManager,
    BrowserSessionState,
    BrowserTimeoutError,
)
from omega.browser.fake import FakeBrowserBackend
from omega.models import ErrorCategory


def _manager(
    *, maximum_open_tabs: int = 10
) -> tuple[BrowserManager, FakeBrowserBackend]:
    backend = FakeBrowserBackend()
    manager = BrowserManager(
        BrowserConfiguration(maximum_open_tabs=maximum_open_tabs), backend
    )
    return manager, backend


def _ids() -> tuple[object, object]:
    return uuid4(), uuid4()


def test_explicit_start_is_idempotent_and_shutdown_is_owned() -> None:
    manager, backend = _manager()
    action_id, command_id = uuid4(), uuid4()
    assert manager.open_browser(action_id, command_id).success
    assert manager.open_browser(uuid4(), uuid4()).success
    assert backend.start_count == 1
    assert manager.state is BrowserSessionState.ACTIVE
    manager.shutdown()
    assert backend.stop_count == 1
    assert manager.state is BrowserSessionState.STOPPED


def test_navigation_validates_before_backend_and_redacts_result() -> None:
    manager, backend = _manager()
    result = manager.navigate(
        uuid4(), uuid4(), "https://example.com/path?token=secret#fragment", new_tab=True
    )
    assert result.success
    assert backend.navigation_count == 1
    assert result.data["page"]["url"] == "https://example.com/path"  # type: ignore[index]
    blocked = manager.navigate(uuid4(), uuid4(), "http://example.com/")
    assert not blocked.success
    assert blocked.error is not None
    assert blocked.error.category is ErrorCategory.SAFETY
    assert backend.navigation_count == 1


def test_unsafe_redirect_fails_closed_after_backend_reports_it() -> None:
    manager, backend = _manager()
    backend.redirect_url = "http://127.0.0.1/private"
    result = manager.navigate(uuid4(), uuid4(), "https://example.com/", new_tab=True)
    assert not result.success
    assert result.error is not None
    assert result.error.code == "UNSAFE_URL"


def test_tab_limit_switch_close_and_external_close() -> None:
    manager, backend = _manager(maximum_open_tabs=2)
    manager.navigate(uuid4(), uuid4(), "https://one.example/", new_tab=True)
    manager.navigate(uuid4(), uuid4(), "https://two.example/", new_tab=True)
    assert not manager.open_new_tab(uuid4(), uuid4()).success
    tabs_result = manager.list_tabs(uuid4(), uuid4())
    assert len(tabs_result.data["tabs"]) == 2  # type: ignore[index]
    first_id = manager.resolve_tab_id("1")
    assert manager.switch_tab(uuid4(), uuid4(), first_id).success
    assert manager.close_tab(uuid4(), uuid4(), first_id).success
    assert len(backend.list_tabs()) == 1


def test_page_operations_are_typed_and_bounded() -> None:
    config = BrowserConfiguration(
        maximum_page_title_characters=10,
        maximum_page_text_characters=12,
    )
    backend = FakeBrowserBackend()
    manager = BrowserManager(config, backend)
    manager.navigate(uuid4(), uuid4(), "https://example.com/", new_tab=True)
    info = manager.page_information(uuid4(), uuid4())
    assert info.success
    page = info.data["page"]  # type: ignore[index]
    assert len(page["title"]) <= 10
    assert len(page["visible_text"]) <= 12
    assert manager.refresh(uuid4(), uuid4()).success
    assert manager.go_back(uuid4(), uuid4()).success
    assert manager.go_forward(uuid4(), uuid4()).success
    found = manager.find_text(uuid4(), uuid4(), "visible")
    assert found.success


def test_search_query_is_not_persisted_in_result_data() -> None:
    manager, _ = _manager()
    result = manager.search(uuid4(), uuid4(), "private medical query")
    assert result.success
    assert "private medical query" not in str(result.to_dict())
    assert result.data["engine"] == "duckduckgo"  # type: ignore[index]


def test_process_local_bookmark_save_open_and_duplicate() -> None:
    manager, backend = _manager()
    manager.navigate(uuid4(), uuid4(), "https://example.com/docs", new_tab=True)
    saved = manager.save_current_bookmark(uuid4(), uuid4(), "Docs")
    assert saved.success
    opened = manager.open_bookmark(uuid4(), uuid4(), "docs")
    assert opened.success
    assert backend.navigation_count == 2
    duplicate = manager.save_current_bookmark(uuid4(), uuid4(), "Docs")
    assert not duplicate.success


def test_backend_failure_returns_safe_structured_failure_without_retry() -> None:
    manager, backend = _manager()
    backend.fail_next = RuntimeError("secret backend detail")
    result = manager.open_browser(uuid4(), uuid4())
    assert not result.success
    assert result.error is not None
    assert result.error.code == "BROWSER_INTERNAL_ERROR"
    assert "secret backend detail" not in result.user_message
    assert backend.start_count == 0


def test_timeout_returns_typed_timeout_without_retry() -> None:
    manager, backend = _manager()
    backend.fail_next = BrowserTimeoutError("The operation timed out.")
    result = manager.open_browser(uuid4(), uuid4())
    assert not result.success
    assert result.error is not None
    assert result.error.category is ErrorCategory.TIMEOUT
    assert backend.start_count == 0
