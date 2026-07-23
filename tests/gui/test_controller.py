from __future__ import annotations

from concurrent.futures import Future
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from omega.gui.controller import MAX_COMMAND_CHARACTERS, GuiController
from omega.gui.models import (
    ConfirmationRequest,
    GuiPreferences,
    GuiStatus,
    MessageKind,
)
from omega.history import HistoryActivity
from omega.safety import SafeExecutionGateway
from omega.session import OmegaSession, SessionState


class ImmediateRunner:
    def submit(self, operation, on_success, on_error):
        future = Future()
        try:
            result = operation()
        except BaseException as error:
            future.set_exception(error)
            on_error(error)
        else:
            future.set_result(result)
            on_success(result)
        return future

    def shutdown(self, *, wait=False):
        self.closed = True


class DeferredRunner:
    def submit(self, operation, on_success, on_error):
        self.operation = operation
        self.on_success = on_success
        self.on_error = on_error
        return Future()

    def shutdown(self, *, wait=False):
        return None


class FakeView:
    def __init__(self):
        self.messages = []
        self.statuses = []
        self.busy = []
        self.activity = []
        self.confirmations = []
        self.notifications = []
        self.preferences = []
        self.states = []
        self.dismissals = 0

    def add_message(self, message):
        self.messages.append(message)

    def set_status(self, status, detail):
        self.statuses.append((status, detail))

    def set_busy(self, busy):
        self.busy.append(busy)

    def show_activity(self, items):
        self.activity.append(tuple(items))

    def set_undo_availability(self, availability):
        self.undo = availability

    def show_confirmation(self, request):
        self.confirmations.append(request)

    def dismiss_confirmation(self):
        self.dismissals += 1

    def notify(self, notification):
        self.notifications.append(notification)

    def apply_preferences(self, preferences):
        self.preferences.append(preferences)

    def update_session_state(self, state):
        self.states.append(state)


class FakeHistory:
    def __init__(self):
        self.limits = []
        self.failure = None
        self.records = ()

    def latest_activity(self, limit):
        self.limits.append(limit)
        if self.failure is not None:
            raise self.failure
        return (
            HistoryActivity(
                "command",
                uuid4(),
                datetime.now(UTC),
                "Open Chrome",
            ),
        )

    def active_undo_records(self):
        return self.records


class FakePreferences:
    def load(self):
        return GuiPreferences(theme="dark", history_limit=5)

    def save(self, preferences):
        return preferences


class FakeConfirmations:
    def __init__(self):
        self.pending = None

    def get(self, session_id):
        return self.pending


class FakeGateway:
    def __init__(self):
        self.confirmations = FakeConfirmations()


class FakeSession:
    activation_phrase = "Hello Omega"
    shutdown_phrase = "Shut down Omega"

    def __init__(self, gateway):
        self.gateway = gateway
        self.state = SimpleNamespace(value="active")
        self.session_id = uuid4()
        self.calls = []

    def handle_input(self, text):
        self.calls.append(text)
        if text == "confirm clear history" or text == "cancel clear history":
            self.gateway.confirmations.pending = None
        return f"handled: {text}"

    def interrupt(self):
        self.state = SimpleNamespace(value="terminated")
        return "interrupted"


def _controller(runner=None):
    gateway = FakeGateway()
    session = FakeSession(gateway)
    history = FakeHistory()
    view = FakeView()
    controller = GuiController(
        session,
        history,
        FakePreferences(),
        gateway,
        runner or ImmediateRunner(),
        view,
    )
    return controller, session, history, gateway, view


def test_valid_command_is_submitted_and_displayed_once():
    controller, session, history, _, view = _controller()

    assert controller.submit_command("Open Chrome")

    assert session.calls == ["Open Chrome"]
    assert [message.text for message in view.messages] == [
        "Open Chrome",
        "handled: Open Chrome",
    ]
    assert view.messages[0].kind is MessageKind.USER
    assert len(view.activity[-1]) == 1
    assert history.limits == [20]
    assert view.busy == [True, False]


def test_whitespace_and_overlong_commands_are_rejected():
    controller, session, _, _, view = _controller()

    assert not controller.submit_command("   ")
    assert not controller.submit_command("x" * (MAX_COMMAND_CHARACTERS + 1))

    assert session.calls == []
    assert len(view.notifications) == 2


def test_busy_state_prevents_duplicate_submission():
    controller, session, _, _, _ = _controller(DeferredRunner())

    assert controller.submit_command("Open Chrome")
    assert not controller.submit_command("Open Chrome")
    assert session.calls == []


def test_confirmation_and_cancellation_use_exact_session_phrases():
    controller, session, _, gateway, view = _controller()
    gateway.confirmations.pending = SimpleNamespace(
        prompt="Clear local history?",
        display_target="local Omega history",
        expected_confirmation="confirm clear history",
        expected_cancellation="cancel clear history",
    )

    controller.submit_command("clear history")

    request = view.confirmations[-1]
    assert isinstance(request, ConfirmationRequest)
    assert view.statuses[-1][0] is GuiStatus.AWAITING_CONFIRMATION
    assert controller.cancel_pending()
    assert session.calls == ["clear history", "cancel clear history"]
    assert gateway.confirmations.pending is None


def test_toolbar_commands_route_through_session():
    controller, session, _, _, _ = _controller()

    controller.activate()
    controller.show_history()
    controller.request_undo()
    controller.export_history()
    controller.clear_history()
    controller.shutdown_session()

    assert session.calls == [
        "Hello Omega",
        "show history",
        "undo last action",
        "export history",
        "clear history",
        "Shut down Omega",
    ]


def test_worker_exception_is_safe_and_not_retried():
    controller, session, _, _, view = _controller()

    def fail(_text):
        raise RuntimeError("private diagnostic")

    session.handle_input = fail
    assert controller.submit_command("Open Chrome")

    assert len(view.messages) == 2
    assert "private diagnostic" not in view.messages[-1].text
    assert view.statuses[-1][0] is GuiStatus.ERROR


def test_start_loads_preferences_and_bounded_activity():
    controller, _, history, _, view = _controller()

    controller.start()

    assert controller.current_preferences.theme == "dark"
    assert view.preferences[-1].history_limit == 5
    assert history.limits == [20]


def test_real_session_activation_command_and_shutdown_lifecycle():
    gateway = SafeExecutionGateway()
    session = OmegaSession(
        {"display_name": "Anshuman"},
        {
            "activation_phrase": "Hello Omega",
            "shutdown_phrase": "Shut down Omega",
            "active_session_timeout_seconds": 300,
        },
        safety_gateway=gateway,
    )
    history = FakeHistory()
    view = FakeView()
    controller = GuiController(
        session,
        history,
        FakePreferences(),
        gateway,
        ImmediateRunner(),
        view,
    )

    assert controller.activate()
    assert session.state is SessionState.ACTIVE
    assert controller.submit_command("Open Chrome")
    assert session.history[-1].original_text == "Open Chrome"
    assert controller.shutdown_session()
    assert session.state is SessionState.TERMINATED


def test_active_undo_record_is_presented_safely():
    controller, _, history, _, view = _controller()
    history.records = (
        SimpleNamespace(
            action_type=SimpleNamespace(value="recycle_file"),
            item=SimpleNamespace(display_name="notes.txt"),
            expires_at=datetime.now(UTC) + timedelta(minutes=2),
        ),
    )

    controller.refresh_activity()

    assert view.undo.available
    assert "notes.txt" in view.undo.description
    assert "expires" in view.undo.description
