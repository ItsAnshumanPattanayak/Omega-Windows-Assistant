"""Narrow dispatcher for complete deterministic Phase 6 folder commands."""

from __future__ import annotations

from dataclasses import dataclass

from omega.folders.manager import FolderManager
from omega.models import (
    Action,
    ActionResult,
    ActionStatus,
    ConfirmationStatus,
    ErrorCategory,
    IntentType,
    OmegaErrorDetails,
    PermissionDecision,
    RiskLevel,
    UserCommand,
)
from omega.models._serialization import JsonValue
from omega.understanding.result import CommandParseResult

_FOLDER_INTENTS = frozenset(
    {
        IntentType.CREATE_FOLDER,
        IntentType.OPEN_FOLDER,
        IntentType.LIST_FOLDER,
        IntentType.RENAME_FOLDER,
        IntentType.COPY_FOLDER,
        IntentType.MOVE_FOLDER,
        IntentType.DELETE_FOLDER,
        IntentType.CHECK_FOLDER_EXISTENCE,
        IntentType.GET_FOLDER_INFORMATION,
        IntentType.SEARCH_FOLDER,
    }
)

_RISK = {
    IntentType.OPEN_FOLDER: RiskLevel.LOW,
    IntentType.LIST_FOLDER: RiskLevel.LOW,
    IntentType.CHECK_FOLDER_EXISTENCE: RiskLevel.LOW,
    IntentType.GET_FOLDER_INFORMATION: RiskLevel.LOW,
    IntentType.SEARCH_FOLDER: RiskLevel.LOW,
    IntentType.CREATE_FOLDER: RiskLevel.MEDIUM,
    IntentType.RENAME_FOLDER: RiskLevel.MEDIUM,
    IntentType.COPY_FOLDER: RiskLevel.MEDIUM,
    IntentType.MOVE_FOLDER: RiskLevel.HIGH,
    IntentType.DELETE_FOLDER: RiskLevel.CRITICAL,
}


@dataclass(frozen=True)
class FolderDispatchResult:
    """The parsed command, typed action proposal, and structured result."""

    command: UserCommand
    action: Action
    result: ActionResult

    @property
    def user_message(self) -> str:
        return self.result.user_message


class FolderActionDispatcher:
    """Dispatch only complete folder intents through the folder manager."""

    def __init__(self, manager: FolderManager) -> None:
        self.manager = manager

    def dispatch(self, parsed: CommandParseResult) -> FolderDispatchResult | None:
        command = parsed.command
        if (
            not parsed.matched
            or parsed.requires_clarification
            or command.intent not in _FOLDER_INTENTS
        ):
            return None
        denied = command.intent is IntentType.DELETE_FOLDER
        action = self._action(command, _RISK[command.intent], denied=denied)
        if denied:
            return FolderDispatchResult(
                command, action, self._delete_deferred(command, action)
            )
        values = self._values(command)
        location = self._string(values, "location")
        folder_name = self._string(values, "folder_name")
        result: ActionResult | None = None
        if command.intent is IntentType.CREATE_FOLDER and folder_name:
            result = self.manager.create_folder(
                folder_name,
                location,
                action.action_id,
                command.command_id,
                parent_path=self._string(values, "parent_path"),
            )
        elif command.intent is IntentType.OPEN_FOLDER:
            result = self.manager.open_folder(
                folder_name, location, action.action_id, command.command_id
            )
        elif command.intent is IntentType.LIST_FOLDER:
            result = self.manager.list_folder(
                folder_name, location, action.action_id, command.command_id
            )
        elif command.intent is IntentType.CHECK_FOLDER_EXISTENCE:
            result = self.manager.folder_exists(
                folder_name, location, action.action_id, command.command_id
            )
        elif command.intent is IntentType.GET_FOLDER_INFORMATION:
            result = self.manager.get_folder_information(
                folder_name,
                location,
                action.action_id,
                command.command_id,
                recursive=values.get("recursive") is True,
            )
        elif command.intent is IntentType.RENAME_FOLDER:
            source = self._string(values, "source_folder")
            new_name = self._string(values, "new_name")
            if source and new_name:
                result = self.manager.rename_folder(
                    source, new_name, location, action.action_id, command.command_id
                )
        elif command.intent in {IntentType.COPY_FOLDER, IntentType.MOVE_FOLDER}:
            source = self._string(values, "source_folder")
            destination = self._string(values, "destination")
            if source and destination:
                method = (
                    self.manager.copy_folder
                    if command.intent is IntentType.COPY_FOLDER
                    else self.manager.move_folder
                )
                result = method(
                    source,
                    self._string(values, "source_location"),
                    destination,
                    action.action_id,
                    command.command_id,
                )
        elif command.intent is IntentType.SEARCH_FOLDER and folder_name:
            result = self.manager.search_folders(
                folder_name, location, action.action_id, command.command_id
            )
        if result is None:
            return None
        return FolderDispatchResult(command, action, result)

    @staticmethod
    def _values(command: UserCommand) -> dict[str, JsonValue]:
        values: dict[str, JsonValue] = {}
        duplicates: set[str] = set()
        for entity in command.entities:
            if entity.name is None:
                continue
            if entity.name in values:
                duplicates.add(entity.name)
            values[entity.name] = entity.value
        for name in duplicates:
            values.pop(name, None)
        return values

    @staticmethod
    def _string(values: dict[str, JsonValue], name: str) -> str | None:
        value = values.get(name)
        return value if isinstance(value, str) else None

    @staticmethod
    def _action(command: UserCommand, risk: RiskLevel, *, denied: bool) -> Action:
        return Action(
            command_id=command.command_id,
            intent=command.intent,
            parameters={
                entity.name: entity.value
                for entity in command.entities
                if entity.name is not None
            },
            risk_level=risk,
            status=ActionStatus.REJECTED if denied else ActionStatus.PENDING,
            permission_decision=(
                PermissionDecision.DENY if denied else PermissionDecision.ALLOW
            ),
            confirmation_status=ConfirmationStatus.NOT_REQUIRED,
            requires_confirmation=False,
        )

    @staticmethod
    def _delete_deferred(command: UserCommand, action: Action) -> ActionResult:
        message = (
            "Safe folder deletion will be added with Recycle Bin and undo support "
            "in Phase 8."
        )
        error = OmegaErrorDetails(
            code="FOLDER_DELETION_DEFERRED",
            category=ErrorCategory.SAFETY,
            message="Permanent folder deletion is disabled in Phase 6.",
            user_message=message,
            recoverable=False,
            action_id=action.action_id,
            command_id=command.command_id,
        )
        return ActionResult.failure_result(
            action.action_id,
            "Permanent folder deletion is disabled.",
            message,
            error,
        )
