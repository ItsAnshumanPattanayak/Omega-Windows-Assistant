"""Folder action adapter protected by the central execution gateway."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from omega.core.exceptions import FolderManagementError
from omega.folders.manager import FolderManager
from omega.models import (
    Action,
    ActionResult,
    ConfirmationStatus,
    IntentType,
    PermissionDecision,
    RiskLevel,
    UserCommand,
)
from omega.models._serialization import JsonValue
from omega.safety import (
    ConfirmationSpec,
    GatewayDispatchResult,
    ResourceFingerprint,
    SafeExecutionGateway,
    SafetyContext,
)
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
    command: UserCommand
    action: Action
    result: ActionResult

    @property
    def user_message(self) -> str:
        return self.result.user_message

    @classmethod
    def from_gateway(cls, value: GatewayDispatchResult) -> FolderDispatchResult:
        return cls(value.command, value.action, value.result)


class FolderActionDispatcher:
    """Build folder proposals and route all operations through one gateway."""

    def __init__(
        self, manager: FolderManager, *, gateway: SafeExecutionGateway | None = None
    ) -> None:
        self.manager = manager
        self.gateway = gateway or SafeExecutionGateway()

    def dispatch(self, parsed: CommandParseResult) -> FolderDispatchResult | None:
        command = parsed.command
        if (
            not parsed.matched
            or parsed.requires_clarification
            or command.intent not in _FOLDER_INTENTS
        ):
            return None
        values = self._values(command)
        action = self._action(command)
        source, destination = self._preview_paths(command.intent, values)
        conflict = (
            destination is not None
            and destination.exists()
            and command.intent
            in {
                IntentType.CREATE_FOLDER,
                IntentType.RENAME_FOLDER,
                IntentType.COPY_FOLDER,
                IntentType.MOVE_FOLDER,
            }
        )
        target = destination if destination is not None else source
        context = SafetyContext(
            command=command,
            action=action,
            session_id=command.session_id or UUID(int=0),
            source_path=source,
            destination_path=destination,
            logical_source=self._string(values, "source_location")
            or self._string(values, "location"),
            logical_destination=self._string(values, "destination")
            or self._string(values, "location"),
            target_exists=target.exists() if target is not None else None,
            target_type="folder",
            additional_context={"destination_conflict": conflict},
        )
        executor = self._executor(command, action, values)
        if executor is None:
            return None
        confirmation = self._confirmation(command.intent, values, source, destination)
        fingerprint = self._fingerprint(command.intent, source, destination)
        submitted = self.gateway.submit(
            context,
            executor,
            confirmation=confirmation,
            fingerprint=fingerprint,
            revalidator=lambda: self._fingerprint(command.intent, source, destination),
        )
        return FolderDispatchResult.from_gateway(submitted)

    def clear_pending_confirmations(self) -> None:
        self.gateway.clear_confirmations()

    def _executor(
        self,
        command: UserCommand,
        action: Action,
        values: dict[str, JsonValue],
    ) -> Callable[[], ActionResult] | None:
        location = self._string(values, "location")
        folder_name = self._string(values, "folder_name")
        action_id, command_id = action.action_id, command.command_id
        if command.intent is IntentType.CREATE_FOLDER and folder_name:
            return lambda: self.manager.create_folder(
                folder_name,
                location,
                action_id,
                command_id,
                parent_path=self._string(values, "parent_path"),
            )
        if command.intent is IntentType.OPEN_FOLDER:
            return lambda: self.manager.open_folder(
                folder_name, location, action_id, command_id
            )
        if command.intent is IntentType.LIST_FOLDER:
            return lambda: self.manager.list_folder(
                folder_name, location, action_id, command_id
            )
        if command.intent is IntentType.CHECK_FOLDER_EXISTENCE:
            return lambda: self.manager.folder_exists(
                folder_name, location, action_id, command_id
            )
        if command.intent is IntentType.GET_FOLDER_INFORMATION:
            return lambda: self.manager.get_folder_information(
                folder_name,
                location,
                action_id,
                command_id,
                recursive=values.get("recursive") is True,
            )
        if command.intent is IntentType.RENAME_FOLDER:
            source = self._string(values, "source_folder")
            new_name = self._string(values, "new_name")
            if source and new_name:
                safe_source, safe_new_name = source, new_name
                return lambda: self.manager.rename_folder(
                    safe_source,
                    safe_new_name,
                    location,
                    action_id,
                    command_id,
                )
        if command.intent in {IntentType.COPY_FOLDER, IntentType.MOVE_FOLDER}:
            source = self._string(values, "source_folder")
            destination = self._string(values, "destination")
            if source and destination:
                method = (
                    self.manager.copy_folder
                    if command.intent is IntentType.COPY_FOLDER
                    else self.manager.move_folder
                )
                return lambda: method(
                    source,
                    self._string(values, "source_location"),
                    destination,
                    action_id,
                    command_id,
                )
        if command.intent is IntentType.SEARCH_FOLDER and folder_name:
            return lambda: self.manager.search_folders(
                folder_name, location, action_id, command_id
            )
        if command.intent is IntentType.DELETE_FOLDER:
            return lambda: self._unreachable(action, command)
        return None

    def _preview_paths(
        self, intent: IntentType, values: dict[str, JsonValue]
    ) -> tuple[Path | None, Path | None]:
        try:
            location = self._string(values, "location")
            if intent is IntentType.CREATE_FOLDER:
                name = self._string(values, "folder_name")
                if name:
                    return None, self.manager._resolve(location, name).path
            if intent in {
                IntentType.OPEN_FOLDER,
                IntentType.LIST_FOLDER,
                IntentType.CHECK_FOLDER_EXISTENCE,
                IntentType.GET_FOLDER_INFORMATION,
            }:
                name = self._string(values, "folder_name")
                return self.manager._resolve(location, name, allow_root=True).path, None
            if intent is IntentType.RENAME_FOLDER:
                name = self._string(values, "source_folder")
                new_name = self._string(values, "new_name")
                if name and new_name:
                    source = self.manager._resolve(location, name).path
                    destination = self.manager._resolve(
                        location, str(Path(name).with_name(new_name))
                    ).path
                    return source, destination
            if intent in {IntentType.COPY_FOLDER, IntentType.MOVE_FOLDER}:
                name = self._string(values, "source_folder")
                target_location = self._string(values, "destination")
                if name and target_location:
                    source = self.manager._resolve(
                        self._string(values, "source_location"), name
                    ).path
                    destination = self.manager._resolve(
                        target_location, source.name
                    ).path
                    return source, destination
        except (FolderManagementError, OSError, ValueError):
            return None, None
        return None, None

    def _confirmation(
        self,
        intent: IntentType,
        values: dict[str, JsonValue],
        source: Path | None,
        destination: Path | None,
    ) -> ConfirmationSpec | None:
        if (
            intent is not IntentType.MOVE_FOLDER
            or source is None
            or destination is None
        ):
            return None
        source_location = self._display(
            self._string(values, "source_location")
            or self.manager.settings.default_location
        )
        destination_location = self._display(self._string(values, "destination"))
        exact = (
            f"confirm move folder {source.name} from {source_location} "
            f"to {destination_location}"
        )
        return ConfirmationSpec(
            source.name,
            f"Moving the {source.name} folder will remove it from "
            f'{source_location}. Type "{exact}" to continue.',
            exact,
            f"cancel move folder {source.name} from {source_location} "
            f"to {destination_location}",
        )

    def _fingerprint(
        self, intent: IntentType, source: Path | None, destination: Path | None
    ) -> ResourceFingerprint | None:
        if intent is not IntentType.MOVE_FOLDER:
            return None
        items = [
            SafeExecutionGateway.fingerprint_path(path)
            for path in (source, destination)
            if path is not None
        ]
        if not items:
            return None
        digest = hashlib.sha256(repr(items).encode("utf-8")).hexdigest()
        return ResourceFingerprint(
            "folder_operation", digest, True, item_count=len(items)
        )

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
    def _display(value: str | None) -> str:
        return (value or "Desktop").replace("_", " ").title()

    @staticmethod
    def _action(command: UserCommand) -> Action:
        return Action(
            command_id=command.command_id,
            intent=command.intent,
            parameters={
                entity.name: entity.value for entity in command.entities if entity.name
            },
            risk_level=_RISK[command.intent],
            permission_decision=PermissionDecision.ALLOW,
            confirmation_status=ConfirmationStatus.NOT_REQUIRED,
            requires_confirmation=False,
        )

    @staticmethod
    def _unreachable(action: Action, command: UserCommand) -> ActionResult:
        raise RuntimeError(
            f"Denied deletion reached executor {action.action_id} {command.command_id}."
        )
