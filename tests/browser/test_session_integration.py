"""Terminal, GUI-controller path, and voice-source browser integration."""

from omega.browser import BrowserConfiguration, BrowserManager, UrlValidator
from omega.browser.fake import FakeBrowserBackend
from omega.execution import BrowserActionDispatcher
from omega.models import CommandSource, IntentType
from omega.safety import SafeExecutionGateway
from omega.session import OmegaSession


def _session() -> tuple[OmegaSession, FakeBrowserBackend]:
    config = BrowserConfiguration()
    backend = FakeBrowserBackend()
    gateway = SafeExecutionGateway()
    dispatcher = BrowserActionDispatcher(
        BrowserManager(config, backend), gateway, UrlValidator(config)
    )
    session = OmegaSession(
        {"display_name": "Anshuman"},
        {
            "activation_phrase": "Hello Omega",
            "shutdown_phrase": "Shut down Omega",
            "active_session_timeout_seconds": 300,
        },
        browser_dispatcher=dispatcher,
        safety_gateway=gateway,
    )
    session.handle_input("Hello Omega")
    return session, backend


def test_text_command_uses_normal_session_lifecycle() -> None:
    session, backend = _session()
    response = session.handle_input("Open example.com")
    assert "validated page" in response
    assert backend.navigation_count == 1
    assert session.history[-1].intent is IntentType.OPEN_WEBSITE
    assert session.history[-1].source is CommandSource.TEXT


def test_voice_source_is_preserved_without_voice_specific_parser() -> None:
    session, backend = _session()
    response = session.handle_input(
        "Search the web for Python decorators", source=CommandSource.VOICE
    )
    assert "search is open" in response
    assert backend.navigation_count == 1
    assert session.history[-1].source is CommandSource.VOICE


def test_shutdown_closes_only_omega_backend() -> None:
    session, backend = _session()
    session.handle_input("Open browser")
    assert backend.started
    response = session.handle_input("Shut down Omega")
    assert response.startswith("Shutting down")
    assert backend.stop_count == 1


def test_browser_command_is_processed_once() -> None:
    session, backend = _session()
    session.handle_input("Open example.com")
    assert backend.navigation_count == 1
    assert len(session.history) == 1
