"""Gateway-only browser dispatch and at-most-once tests."""

from uuid import UUID

from omega.browser import BrowserConfiguration, BrowserManager, UrlValidator
from omega.browser.fake import FakeBrowserBackend
from omega.execution import BrowserActionDispatcher
from omega.models import ActionStatus, PermissionDecision, RiskLevel
from omega.safety import SafeExecutionGateway
from omega.understanding import CommandParser


def _dispatcher() -> tuple[
    BrowserActionDispatcher,
    BrowserManager,
    FakeBrowserBackend,
    SafeExecutionGateway,
]:
    config = BrowserConfiguration()
    backend = FakeBrowserBackend()
    manager = BrowserManager(config, backend)
    gateway = SafeExecutionGateway()
    return (
        BrowserActionDispatcher(manager, gateway, UrlValidator(config)),
        manager,
        backend,
        gateway,
    )


def test_open_website_uses_gateway_and_executes_once() -> None:
    dispatcher, _, backend, _ = _dispatcher()
    result = dispatcher.dispatch(CommandParser().parse("Open example.com"))
    assert result is not None
    assert result.result.success
    assert result.action.risk_level is RiskLevel.MEDIUM
    assert result.action.permission_decision is PermissionDecision.ALLOW
    assert result.action.status is ActionStatus.SUCCEEDED
    assert backend.navigation_count == 1


def test_unsafe_url_never_reaches_backend() -> None:
    dispatcher, _, backend, _ = _dispatcher()
    parsed = CommandParser().parse("Open https://127.0.0.1/")
    result = dispatcher.dispatch(parsed)
    assert result is not None
    assert not result.result.success
    assert backend.navigation_count == 0


def test_close_browser_requires_scoped_confirmation_and_runs_once() -> None:
    dispatcher, manager, backend, gateway = _dispatcher()
    opened = dispatcher.dispatch(CommandParser().parse("Open browser"))
    assert opened is not None and opened.result.success
    parsed = CommandParser().parse("Close browser")
    pending = dispatcher.dispatch(parsed)
    assert pending is not None
    assert pending.action.status is ActionStatus.AWAITING_CONFIRMATION
    assert backend.stop_count == 0
    confirmed = gateway.handle_confirmation("confirm close browser", UUID(int=0))
    assert confirmed is not None
    assert confirmed.result.success
    assert backend.stop_count == 1
    assert manager.state.value == "stopped"
    repeated = gateway.handle_confirmation("confirm close browser", UUID(int=0))
    assert repeated is not None and not repeated.result.success
    assert backend.stop_count == 1


def test_save_bookmark_confirmation_is_bound_to_name() -> None:
    dispatcher, _, _, gateway = _dispatcher()
    opened = dispatcher.dispatch(CommandParser().parse("Open example.com"))
    assert opened is not None and opened.result.success
    parsed = CommandParser().parse("Save this page as Docs")
    pending = dispatcher.dispatch(parsed)
    assert pending is not None
    wrong = gateway.handle_confirmation("confirm save bookmark Other", UUID(int=0))
    assert wrong is not None and not wrong.result.success
    confirmed = gateway.handle_confirmation("confirm save bookmark Docs", UUID(int=0))
    assert confirmed is not None and confirmed.result.success


def test_search_action_stores_length_not_query_in_parameters() -> None:
    dispatcher, _, _, _ = _dispatcher()
    result = dispatcher.dispatch(
        CommandParser().parse("Search the web for private medical query")
    )
    assert result is not None
    assert result.action.parameters == {
        "search_engine": "duckduckgo",
        "query_length": 21,
    }
    assert "private medical query" not in str(result.action.to_dict())
