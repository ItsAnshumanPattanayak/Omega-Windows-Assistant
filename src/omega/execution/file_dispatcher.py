"""Narrow dispatcher for complete, deterministic Phase 5 file commands."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PureWindowsPath
from uuid import UUID

from omega.files.manager import FileManager
from omega.models import (
    Action,
    ActionResult,
    ActionStatus,
    CommandEntity,
    ConfirmationStatus,
    EntityType,
    ErrorCategory,
    IntentType,
    OmegaErrorDetails,
    PermissionDecision,
    RiskLevel,
    UserCommand,
)
from omega.understanding.result import CommandParseResult

_FILE_INTENTS = frozenset(
    {
        IntentType.CREATE_FILE,
        IntentType.READ_FILE,
        IntentType.WRITE_FILE,
        IntentType.APPEND_FILE,
        IntentType.RENAME_FILE,
        IntentType.COPY_FILE,
        IntentType.MOVE_FILE,
        IntentType.DELETE_FILE,
        IntentType.OPEN_FILE,
        IntentType.SEARCH_FILE,
        IntentType.CHECK_FILE_EXISTENCE,
        IntentType.GET_FILE_INFORMATION,
    }
)

_RISK = {
    IntentType.READ_FILE: RiskLevel.LOW,
    IntentType.OPEN_FILE: RiskLevel.LOW,
    IntentType.SEARCH_FILE: RiskLevel.LOW,
    IntentType.CHECK_FILE_EXISTENCE: RiskLevel.LOW,
    IntentType.GET_FILE_INFORMATION: RiskLevel.LOW,
    IntentType.CREATE_FILE: RiskLevel.MEDIUM,
    IntentType.APPEND_FILE: RiskLevel.MEDIUM,
    IntentType.RENAME_FILE: RiskLevel.MEDIUM,
    IntentType.COPY_FILE: RiskLevel.MEDIUM,
    IntentType.MOVE_FILE: RiskLevel.MEDIUM,
    IntentType.WRITE_FILE: RiskLevel.HIGH,
    IntentType.DELETE_FILE: RiskLevel.CRITICAL,
}


class FileControlCommand(StrEnum):
    """Exact in-memory overwrite controls recognized outside normal parsing."""

    CONFIRM_OVERWRITE = "confirm overwrite"
    CANCEL_OVERWRITE = "cancel overwrite"


@dataclass(frozen=True)
class FileDispatchResult:
    """The parsed command, action proposal, and structured file result."""

    command: UserCommand
    action: Action
    result: ActionResult

    @property
    def user_message(self) -> str:
        return self.result.user_message


class FileActionDispatcher:
    """Dispatch only supported complete file intents through FileManager."""

    def __init__(self, manager: FileManager) -> None:
        self.manager = manager

    def dispatch(self, parsed: CommandParseResult) -> FileDispatchResult | None:
        """Return None without file side effects for unsupported/incomplete input."""
        command = parsed.command
        if (
            not parsed.matched
            or parsed.requires_clarification
            or command.intent not in _FILE_INTENTS
        ):
            return None
        denied = command.intent is IntentType.DELETE_FILE
        action = self._action(command, _RISK[command.intent], denied=denied)
        if denied:
            result = self._delete_deferred(command, action)
            return FileDispatchResult(command, action, result)

        values = self._values(command)
        location = values.get("location")
        method_result: ActionResult | None = None
        if command.intent is IntentType.CREATE_FILE:
            name = self._with_subpath(
                values.get("file_name"), values.get("relative_subpath")
            )
            if name:
                method_result = self.manager.create_file(
                    name,
                    location,
                    action.action_id,
                    command.command_id,
                    requested_extension=values.get("file_extension"),
                )
        elif command.intent is IntentType.READ_FILE:
            method_result = self._named(
                values, self.manager.read_text_file, location, action, command
            )
        elif command.intent is IntentType.WRITE_FILE:
            if (
                values.get("file_name") is not None
                and values.get("text_content") is not None
            ):
                method_result = self.manager.write_text_file(
                    values["file_name"],
                    location,
                    values["text_content"],
                    action.action_id,
                    command.command_id,
                )
        elif command.intent is IntentType.APPEND_FILE:
            if (
                values.get("file_name") is not None
                and values.get("text_content") is not None
            ):
                method_result = self.manager.append_text_file(
                    values["file_name"],
                    location,
                    values["text_content"],
                    action.action_id,
                    command.command_id,
                )
        elif command.intent is IntentType.RENAME_FILE:
            if values.get("source_file") and values.get("new_name"):
                method_result = self.manager.rename_file(
                    values["source_file"],
                    values["new_name"],
                    location,
                    action.action_id,
                    command.command_id,
                )
        elif command.intent in {IntentType.COPY_FILE, IntentType.MOVE_FILE}:
            source = values.get("source_file")
            destination = values.get("destination")
            if source and destination:
                method = (
                    self.manager.copy_file
                    if command.intent is IntentType.COPY_FILE
                    else self.manager.move_file
                )
                method_result = method(
                    source,
                    values.get("source_location"),
                    destination,
                    action.action_id,
                    command.command_id,
                )
        elif command.intent is IntentType.OPEN_FILE:
            method_result = self._named(
                values, self.manager.open_file, location, action, command
            )
        elif command.intent is IntentType.CHECK_FILE_EXISTENCE:
            method_result = self._named(
                values, self.manager.file_exists, location, action, command
            )
        elif command.intent is IntentType.GET_FILE_INFORMATION:
            method_result = self._named(
                values, self.manager.get_file_information, location, action, command
            )
        elif command.intent is IntentType.SEARCH_FILE:
            query = values.get("file_name") or values.get("search_extension")
            if query:
                method_result = self.manager.search_files(
                    query,
                    location,
                    action.action_id,
                    command.command_id,
                    extension=values.get("search_extension"),
                )
        if method_result is None:
            return None
        return FileDispatchResult(command, action, method_result)

    def dispatch_control(
        self, text: str, session_id: UUID | None = None
    ) -> FileDispatchResult | None:
        """Handle only exact scoped overwrite confirmation/cancellation phrases."""
        stripped = text.strip()
        match = re.fullmatch(
            r"(confirm overwrite|cancel overwrite)\s+(.+?)"
            r"(?:\s+on\s+(desktop|documents|downloads|pictures|music|videos|home|"
            r"current directory))?",
            stripped,
            re.IGNORECASE,
        )
        if match is None:
            return None
        command_type = FileControlCommand(match.group(1).casefold())
        file_name = match.group(2)
        location = match.group(3)
        entities = [
            CommandEntity(
                EntityType.FILE_NAME,
                file_name,
                raw_value=file_name,
                name="file_name",
                confidence=1.0,
            )
        ]
        if location:
            entities.append(
                CommandEntity(
                    EntityType.LOCATION,
                    location.casefold().replace(" ", "_"),
                    raw_value=location,
                    name="location",
                    confidence=1.0,
                )
            )
        command = UserCommand(
            text,
            normalized_text=" ".join(stripped.casefold().split()),
            intent=IntentType.WRITE_FILE,
            entities=entities,
            confidence=1.0,
            session_id=session_id,
        )
        action = self._action(command, RiskLevel.HIGH)
        method = (
            self.manager.confirm_overwrite
            if command_type is FileControlCommand.CONFIRM_OVERWRITE
            else self.manager.cancel_overwrite
        )
        result = method(
            file_name,
            location,
            action.action_id,
            command.command_id,
        )
        return FileDispatchResult(command, action, result)

    def clear_pending_confirmations(self) -> None:
        """Clear pending in-memory file content at session boundaries."""
        self.manager.clear_pending_confirmations()

    @staticmethod
    def _values(command: UserCommand) -> dict[str, str]:
        values: dict[str, str] = {}
        duplicate: set[str] = set()
        for entity in command.entities:
            if entity.name is None or not isinstance(entity.value, str):
                continue
            if entity.name in values:
                duplicate.add(entity.name)
            values[entity.name] = entity.value
        for name in duplicate:
            values.pop(name, None)
        return values

    @staticmethod
    def _with_subpath(name: str | None, subpath: str | None) -> str | None:
        if name is None:
            return None
        return str(PureWindowsPath(subpath, name)) if subpath else name

    @staticmethod
    def _named(
        values: dict[str, str],
        method: Callable[[str, str | None, UUID, UUID | None], ActionResult],
        location: str | None,
        action: Action,
        command: UserCommand,
    ) -> ActionResult | None:
        name = values.get("file_name")
        if name is None:
            return None
        return method(name, location, action.action_id, command.command_id)

    @staticmethod
    def _action(
        command: UserCommand, risk: RiskLevel, *, denied: bool = False
    ) -> Action:
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
            "Safe file deletion will be added with Recycle Bin and undo support "
            "in Phase 8."
        )
        error = OmegaErrorDetails(
            code="FILE_DELETION_DEFERRED",
            category=ErrorCategory.SAFETY,
            message="Permanent file deletion is disabled in Phase 5.",
            user_message=message,
            recoverable=False,
            action_id=action.action_id,
            command_id=command.command_id,
        )
        return ActionResult.failure_result(
            action.action_id,
            "Permanent file deletion is disabled.",
            message,
            error,
        )
