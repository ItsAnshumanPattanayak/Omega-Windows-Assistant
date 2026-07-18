from datetime import datetime

import pytest

from omega.core.exceptions import ModelValidationError
from omega.models import CommandSource, IntentType
from omega.session import OmegaSession, SessionState


def _session(clock=lambda: 0.0) -> OmegaSession:
    return OmegaSession(
        {"display_name": "Anshuman"},
        {
            "activation_phrase": "Hello Omega",
            "shutdown_phrase": "Shut down Omega",
            "active_session_timeout_seconds": 5,
        },
        monotonic_clock=clock,
        now_provider=lambda: datetime(2026, 1, 1, 9),
    )


def test_activation_command_history_and_shutdown() -> None:
    session = _session()
    assert "inactive" in session.handle_input("Open Chrome")
    assert session.handle_input("  HELLO OMEGA ").startswith("Good morning, Anshuman")
    assert session.state is SessionState.ACTIVE
    assert "already active" in session.handle_input("hello omega")
    assert "understood" in session.handle_input("Open Chrome")
    command = session.history[0]
    assert command.original_text == "Open Chrome"
    assert command.source is CommandSource.TEXT
    assert command.intent is IntentType.OPEN_APPLICATION
    assert "Open Chrome" in session.handle_input("show history")
    assert session.handle_input("shut down omega").startswith("Shutting down")
    assert session.state is SessionState.TERMINATED


def test_timeout_and_invalid_timeout() -> None:
    clock = [0.0]
    session = _session(lambda: clock[0])
    session.activate()
    clock[0] = 5.0
    assert session.check_timeout() is None
    clock[0] = 5.1
    assert "timed out" in session.check_timeout()
    assert session.state is SessionState.INACTIVE
    with pytest.raises(ModelValidationError):
        OmegaSession(
            {"display_name": "A"},
            {
                "activation_phrase": "Hello",
                "shutdown_phrase": "Bye",
                "active_session_timeout_seconds": 0,
            },
        )
