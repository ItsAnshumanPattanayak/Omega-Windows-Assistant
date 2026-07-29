from datetime import datetime
from uuid import UUID

from omega.applications import ApplicationDefinition, ApplicationRegistry
from omega.execution import ApplicationActionDispatcher
from omega.models import ActionResult, CommandSource, ErrorCategory, OmegaErrorDetails
from omega.session import OmegaSession, SessionState


class SessionManagerStub:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.cleared = 0

    @staticmethod
    def _success(action_id: UUID, message: str) -> ActionResult:
        return ActionResult.success_result(action_id, message, message)

    def open_application(
        self, _application_id: str, action_id: UUID, _command_id: UUID | None = None
    ) -> ActionResult:
        self.calls.append("open")
        return self._success(action_id, "Opening Google Chrome.")

    def check_application_status(
        self, _application_id: str, action_id: UUID, _command_id: UUID | None = None
    ) -> ActionResult:
        self.calls.append("status")
        return self._success(action_id, "Google Chrome is running.")

    def request_close_application(
        self, _application_id: str, action_id: UUID, _command_id: UUID | None = None
    ) -> ActionResult:
        self.calls.append("close")
        return self._success(
            action_id,
            "Closing Google Chrome may discard unsaved work. "
            'Type "confirm close Chrome" to continue.',
        )

    def close_application(
        self, _application_id: str, action_id: UUID, _command_id: UUID | None = None
    ) -> ActionResult:
        self.calls.append("confirm")
        return self._success(action_id, "Google Chrome has been closed.")

    def confirm_close_application(
        self, _application_id: str, action_id: UUID, _command_id: UUID | None = None
    ) -> ActionResult:
        self.calls.append("confirm")
        return self._success(action_id, "Google Chrome has been closed.")

    def cancel_close_application(
        self, _application_id: str, action_id: UUID, _command_id: UUID | None = None
    ) -> ActionResult:
        self.calls.append("cancel")
        return self._success(action_id, "The request was cancelled.")

    def request_force_close_application(
        self, _application_id: str, action_id: UUID, _command_id: UUID | None = None
    ) -> ActionResult:
        return self._success(action_id, "Force close is disabled.")

    def confirm_force_close_application(
        self, _application_id: str, action_id: UUID, _command_id: UUID | None = None
    ) -> ActionResult:
        return self._success(action_id, "Force close is disabled.")

    def cancel_force_close_application(
        self, _application_id: str, action_id: UUID, _command_id: UUID | None = None
    ) -> ActionResult:
        return self._success(action_id, "No force close is pending.")

    def clear_pending_confirmations(self) -> None:
        self.cleared += 1


def _session(manager: SessionManagerStub, *, clock=lambda: 0.0) -> OmegaSession:
    registry = ApplicationRegistry(
        [
            ApplicationDefinition(
                "chrome",
                "Google Chrome",
                ("chrome", "google chrome"),
                executable_names=("chrome.exe",),
                process_names=("chrome.exe",),
                supports_graceful_close=True,
                requires_close_confirmation=True,
            )
        ]
    )
    dispatcher = ApplicationActionDispatcher(
        manager, registry  # type: ignore[arg-type]
    )
    return OmegaSession(
        {"display_name": "Anshuman"},
        {
            "activation_phrase": "Hello Omega",
            "shutdown_phrase": "Shut down Omega",
            "active_session_timeout_seconds": 5,
        },
        monotonic_clock=clock,
        now_provider=lambda: datetime(2026, 1, 1, 9),
        application_dispatcher=dispatcher,
    )


def test_inactive_session_never_dispatches_and_active_workflow_uses_results() -> None:
    manager = SessionManagerStub()
    session = _session(manager)

    assert "inactive" in session.handle_input("Open Chrome")
    assert manager.calls == []
    session.handle_input("Hello Omega")
    assert session.handle_input("Open Chrome") == "Opening Google Chrome."
    assert session.handle_input("Is Chrome running?") == "Google Chrome is running."
    assert "confirm close Chrome" in session.handle_input("Close Chrome")
    assert (
        session.handle_input("confirm close Chrome") == "Google Chrome has been closed."
    )
    assert manager.calls == ["open", "status", "confirm"]
    assert [command.original_text for command in session.history] == [
        "Open Chrome",
        "Is Chrome running?",
        "Close Chrome",
        "confirm close Chrome",
    ]


def test_shutdown_has_priority_and_clears_confirmation_state() -> None:
    manager = SessionManagerStub()
    session = _session(manager)
    session.activate()
    session.handle_input("Close Chrome")

    response = session.handle_input("Shut down Omega")

    assert response.startswith("Shutting down")
    assert session.state is SessionState.TERMINATED
    assert manager.calls == []
    assert manager.cleared == 1


def test_timeout_clears_confirmation_and_keeps_history() -> None:
    clock = [0.0]
    manager = SessionManagerStub()
    session = _session(manager, clock=lambda: clock[0])
    session.activate()
    session.handle_input("Close Chrome")
    clock[0] = 5.1

    assert "timed out" in session.check_timeout()
    assert manager.cleared == 1
    assert session.history[0].original_text == "Close Chrome"


def test_failed_application_result_does_not_crash_session() -> None:
    manager = SessionManagerStub()

    def failed(
        _application_id: str, action_id: UUID, command_id: UUID | None = None
    ) -> ActionResult:
        error = OmegaErrorDetails(
            "APPLICATION_NOT_FOUND",
            ErrorCategory.NOT_FOUND,
            "Missing registered target.",
            "I could not find Google Chrome on this computer.",
            True,
            action_id=action_id,
            command_id=command_id,
        )
        return ActionResult.failure_result(
            action_id,
            "Missing registered target.",
            "I could not find Google Chrome on this computer.",
            error,
        )

    manager.open_application = failed  # type: ignore[method-assign]
    session = _session(manager)
    session.activate()

    assert "could not find" in session.handle_input("Open Chrome")
    assert session.state is SessionState.ACTIVE


def test_application_name_requires_context_bound_approval() -> None:
    manager = SessionManagerStub()
    session = _session(manager)
    session.activate()

    assert session.handle_input("  ChRoMe ") == "Do you want to open Google Chrome?"
    pending = session.pending_application_clarification
    assert pending is not None
    assert pending.application_id == "chrome"
    assert manager.calls == []

    assert session.handle_input("yes please") == "Opening Google Chrome."
    assert manager.calls == ["open"]
    assert session.pending_application_clarification is None
    assert session.history[-1].metadata == {
        "clarified_application_name": "Google Chrome"
    }


def test_application_clarification_can_cancel_and_cannot_replay() -> None:
    manager = SessionManagerStub()
    session = _session(manager)
    session.activate()

    session.handle_input("chrome")
    assert session.handle_input("never mind") == (
        "Okay, I will not open Google Chrome."
    )
    assert "no pending confirmation" in session.handle_input("yes")
    assert manager.calls == []


def test_application_clarification_expires_without_real_sleep() -> None:
    clock = [0.0]
    manager = SessionManagerStub()
    session = _session(manager, clock=lambda: clock[0])
    session.activate()
    session.handle_input("chrome")
    clock[0] = 30.0

    assert session.pending_application_clarification is None
    assert "application, file, or folder" in session.handle_input("open it")
    assert manager.calls == []


def test_application_clarification_is_cleared_on_shutdown() -> None:
    manager = SessionManagerStub()
    session = _session(manager)
    session.activate()
    session.handle_input("chrome")

    session.shutdown()

    assert session.pending_application_clarification is None
    assert manager.calls == []


def test_non_answer_does_not_replace_current_application_clarification() -> None:
    manager = SessionManagerStub()
    session = _session(manager)
    session.activate()
    session.handle_input("chrome")

    assert session.handle_input("maybe") == (
        "Please answer yes or no: do you want to open Google Chrome?"
    )
    assert session.pending_application_clarification is not None
    assert manager.calls == []


def test_voice_uses_the_same_application_clarification_lifecycle() -> None:
    manager = SessionManagerStub()
    session = _session(manager)
    session.activate()

    session.handle_input("chrome", source=CommandSource.VOICE)
    assert session.handle_input("open it", source=CommandSource.VOICE) == (
        "Opening Google Chrome."
    )

    assert session.history[-1].source is CommandSource.VOICE
    assert manager.calls == ["open"]


def test_sensitive_confirmation_coexists_without_application_approval() -> None:
    manager = SessionManagerStub()
    session = _session(manager)
    session.activate()
    session.handle_input("Close Chrome")
    session.handle_input("chrome")

    response = session.handle_input("yes")

    assert "don't understand" in response
    assert manager.calls == []
    assert session.pending_application_clarification is not None
