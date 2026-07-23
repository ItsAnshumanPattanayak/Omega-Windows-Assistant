"""History commands routed through the central safety gateway."""

from __future__ import annotations

from datetime import UTC, datetime

from omega.history import HistoryService
from omega.models import (
    Action,
    ActionResult,
    ConfirmationStatus,
    ErrorCategory,
    IntentType,
    OmegaErrorDetails,
    PermissionDecision,
    RiskLevel,
)
from omega.safety import ConfirmationSpec, SafeExecutionGateway, SafetyContext
from omega.understanding.result import CommandParseResult

_INTENTS = {
    IntentType.SHOW_HISTORY,
    IntentType.CLEAR_HISTORY,
    IntentType.EXPORT_HISTORY,
    IntentType.UNDO_LAST_ACTION,
}


class HistoryActionDispatcher:
    """Provide bounded history operations without direct OS execution."""

    def __init__(self, history: HistoryService, gateway: SafeExecutionGateway) -> None:
        self.history = history
        self.gateway = gateway

    def dispatch(self, parsed: CommandParseResult) -> str | None:
        command = parsed.command
        if not parsed.matched or command.intent not in _INTENTS:
            return None
        risk = (
            RiskLevel.HIGH
            if command.intent in {IntentType.CLEAR_HISTORY, IntentType.UNDO_LAST_ACTION}
            else (
                RiskLevel.MEDIUM
                if command.intent is IntentType.EXPORT_HISTORY
                else RiskLevel.LOW
            )
        )
        action = Action(
            command_id=command.command_id,
            intent=command.intent,
            risk_level=risk,
            permission_decision=PermissionDecision.ALLOW,
            confirmation_status=ConfirmationStatus.NOT_REQUIRED,
            requires_confirmation=False,
        )
        context = SafetyContext(
            command=command,
            action=action,
            session_id=command.session_id,
            logical_source="local Omega history",
            target_type="history",
        )
        confirmation = None
        if command.intent is IntentType.CLEAR_HISTORY:
            confirmation = ConfirmationSpec(
                "local Omega history",
                'History cleanup cannot be undone. Type "confirm clear history" '
                "to continue.",
                "confirm clear history",
                "cancel clear history",
            )

            def executor() -> ActionResult:
                return self._clear(action, command.received_at)

        elif command.intent is IntentType.UNDO_LAST_ACTION:
            confirmation = ConfirmationSpec(
                "latest recovery record",
                'Undo requires confirmation. Type "confirm undo last action" '
                "to continue.",
                "confirm undo last action",
                "cancel undo last action",
            )

            def executor() -> ActionResult:
                return self._undo_information(action)

        elif command.intent is IntentType.EXPORT_HISTORY:

            def executor() -> ActionResult:
                return self._export(action)

        else:

            def executor() -> ActionResult:
                return self._show(action, command.original_text)

        dispatched = self.gateway.submit(context, executor, confirmation=confirmation)
        return dispatched.user_message

    def _show(self, action: Action, text: str) -> ActionResult:
        normalized = text.casefold()
        if "failed" in normalized:
            actions = self.history.failed_actions()
            lines = [f"{item.intent.value}: {item.status.value}" for item in actions]
        elif "last command" in normalized:
            commands = self.history.recent_commands(2)
            actions = (
                self.history.actions_for_command(commands[1].command_id)
                if len(commands) > 1
                else ()
            )
            lines = [f"{item.intent.value}: {item.status.value}" for item in actions]
        elif "actions" in normalized:
            actions = self.history.recent_actions()
            lines = [f"{item.intent.value}: {item.status.value}" for item in actions]
        else:
            commands = self.history.recent_commands()
            lines = [item.original_text for item in commands]
        message = "\n".join(lines) if lines else "No persistent history is available."
        return ActionResult.success_result(action.action_id, "History read.", message)

    def _clear(self, action: Action, cutoff: datetime) -> ActionResult:
        summary = self.history.cleanup(before=cutoff.astimezone(UTC))
        message = (
            f"Cleared {summary.commands} command(s), {summary.actions} action(s), "
            f"and {summary.results} result(s)."
        )
        return ActionResult.success_result(
            action.action_id, "History cleared.", message
        )

    def _export(self, action: Action) -> ActionResult:
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        result = self.history.export_json(f"omega-history-{stamp}.json")
        return ActionResult.success_result(
            action.action_id,
            "History exported.",
            f"History was exported as {result.path.name}.",
            data={"filename": result.path.name, "size_bytes": result.size_bytes},
        )

    def _undo_information(self, action: Action) -> ActionResult:
        records = self.history.active_undo_records()
        if not records:
            code = "NO_UNDO_RECORD"
            message = "There is no action available to undo."
        else:
            code = "RESTORE_BACKEND_UNAVAILABLE"
            message = (
                "The recovery record is available, but no native restore backend "
                "is configured. Nothing was changed."
            )
        error = OmegaErrorDetails(
            code=code,
            category=ErrorCategory.UNSUPPORTED,
            message=message,
            user_message=message,
            recoverable=False,
            action_id=action.action_id,
            command_id=action.command_id,
        )
        return ActionResult.failure_result(action.action_id, message, message, error)
