from uuid import UUID

from omega.applications import ApplicationDefinition, ApplicationRegistry
from omega.execution import ApplicationActionDispatcher
from omega.models import ActionResult, IntentType, RiskLevel
from omega.understanding import CommandParser


class StubManager:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, UUID, UUID | None]] = []
        self.cleared = False

    def _result(
        self,
        operation: str,
        application_id: str,
        action_id: UUID,
        command_id: UUID | None,
    ) -> ActionResult:
        self.calls.append((operation, application_id, action_id, command_id))
        return ActionResult.success_result(
            action_id,
            f"{operation} succeeded",
            f"{operation} {application_id}",
        )

    def open_application(
        self, application_id: str, action_id: UUID, command_id: UUID | None = None
    ) -> ActionResult:
        return self._result("open", application_id, action_id, command_id)

    def check_application_status(
        self, application_id: str, action_id: UUID, command_id: UUID | None = None
    ) -> ActionResult:
        return self._result("status", application_id, action_id, command_id)

    def request_close_application(
        self, application_id: str, action_id: UUID, command_id: UUID | None = None
    ) -> ActionResult:
        return self._result("close", application_id, action_id, command_id)

    def close_application(
        self, application_id: str, action_id: UUID, command_id: UUID | None = None
    ) -> ActionResult:
        return self._result("close", application_id, action_id, command_id)

    def confirm_close_application(
        self, application_id: str, action_id: UUID, command_id: UUID | None = None
    ) -> ActionResult:
        return self._result("confirm_close", application_id, action_id, command_id)

    def cancel_close_application(
        self, application_id: str, action_id: UUID, command_id: UUID | None = None
    ) -> ActionResult:
        return self._result("cancel_close", application_id, action_id, command_id)

    def request_force_close_application(
        self, application_id: str, action_id: UUID, command_id: UUID | None = None
    ) -> ActionResult:
        return self._result("force_close", application_id, action_id, command_id)

    def confirm_force_close_application(
        self, application_id: str, action_id: UUID, command_id: UUID | None = None
    ) -> ActionResult:
        return self._result("confirm_force", application_id, action_id, command_id)

    def cancel_force_close_application(
        self, application_id: str, action_id: UUID, command_id: UUID | None = None
    ) -> ActionResult:
        return self._result("cancel_force", application_id, action_id, command_id)

    def clear_pending_confirmations(self) -> None:
        self.cleared = True


def _dispatcher(
    *, confirmation: bool = True
) -> tuple[ApplicationActionDispatcher, StubManager]:
    registry = ApplicationRegistry(
        [
            ApplicationDefinition(
                "chrome",
                "Google Chrome",
                ("chrome", "google chrome"),
                executable_names=("chrome.exe",),
                process_names=("chrome.exe",),
                supports_graceful_close=True,
                requires_close_confirmation=confirmation,
            )
        ]
    )
    manager = StubManager()
    return (
        ApplicationActionDispatcher(manager, registry),  # type: ignore[arg-type]
        manager,
    )


def test_dispatches_open_status_and_close_with_preserved_ids_and_risk() -> None:
    dispatcher, manager = _dispatcher()
    parser = CommandParser()

    opened = dispatcher.dispatch(parser.parse("Open Chrome"))
    status = dispatcher.dispatch(parser.parse("Is Chrome running?"))
    closed = dispatcher.dispatch(parser.parse("Close Chrome"))

    assert opened.action.risk_level is RiskLevel.LOW  # type: ignore[union-attr]
    assert status.command.intent is IntentType.CHECK_APPLICATION_STATUS  # type: ignore[union-attr]
    assert closed.action.risk_level is RiskLevel.HIGH  # type: ignore[union-attr]
    assert closed.action.requires_confirmation is True  # type: ignore[union-attr]
    assert manager.calls[0][2] == opened.action.action_id  # type: ignore[union-attr]
    assert manager.calls[0][3] == opened.command.command_id  # type: ignore[union-attr]


def test_incomplete_or_non_application_commands_do_not_dispatch() -> None:
    dispatcher, manager = _dispatcher()
    parser = CommandParser()

    assert dispatcher.dispatch(parser.parse("Open")) is None
    assert dispatcher.dispatch(parser.parse("Open Discord")) is None
    assert dispatcher.dispatch(parser.parse("Tell me a joke")) is None
    assert dispatcher.dispatch(parser.parse("Create a folder named Work")) is None
    assert manager.calls == []


def test_control_commands_are_exact_scoped_and_canonical() -> None:
    dispatcher, manager = _dispatcher()

    requested = dispatcher.dispatch(CommandParser().parse("Close Chrome"))
    confirmed = dispatcher.dispatch_control("  CONFIRM CLOSE Chrome  ")
    cancelled = dispatcher.dispatch_control("cancel close chrome")
    forced = dispatcher.dispatch_control("force close chrome")

    assert requested is not None and not requested.result.success
    assert confirmed is not None and confirmed.result.success
    assert confirmed.command.original_text.startswith("  CONFIRM")  # type: ignore[union-attr]
    assert cancelled is not None and not cancelled.result.success
    assert forced is None
    assert [call[0] for call in manager.calls] == ["close"]
    assert dispatcher.dispatch_control("yes") is not None
    assert dispatcher.dispatch_control("confirm close unknown") is not None
    assert dispatcher.dispatch_control("confirm close chrome please") is not None


def test_dispatcher_clears_session_confirmations() -> None:
    dispatcher, manager = _dispatcher()
    dispatcher.clear_pending_confirmations()
    assert manager.cleared is True
