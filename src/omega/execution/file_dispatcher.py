"""File action adapter protected by the central execution gateway."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from functools import partial
from pathlib import Path, PureWindowsPath
from uuid import UUID

from omega.core.exceptions import FileManagementError
from omega.files.manager import FileManager
from omega.models import (
    Action,
    ActionResult,
    ConfirmationStatus,
    IntentType,
    PermissionDecision,
    RiskLevel,
    UserCommand,
)
from omega.safety import (
    ConfirmationSpec,
    GatewayDispatchResult,
    ResourceFingerprint,
    SafeExecutionGateway,
    SafetyContext,
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
    IntentType.MOVE_FILE: RiskLevel.HIGH,
    IntentType.WRITE_FILE: RiskLevel.MEDIUM,
    IntentType.DELETE_FILE: RiskLevel.CRITICAL,
}


class FileControlCommand(StrEnum):
    CONFIRM_OVERWRITE = "confirm overwrite"
    CANCEL_OVERWRITE = "cancel overwrite"


@dataclass(frozen=True)
class FileDispatchResult:
    command: UserCommand
    action: Action
    result: ActionResult

    @property
    def user_message(self) -> str:
        return self.result.user_message

    @classmethod
    def from_gateway(
        cls,
        value: GatewayDispatchResult,
    ) -> FileDispatchResult:
        return cls(
            value.command,
            value.action,
            value.result,
        )


class FileActionDispatcher:
    """Build file proposals and submit every supported action to one gateway."""

    def __init__(
        self,
        manager: FileManager,
        *,
        gateway: SafeExecutionGateway | None = None,
    ) -> None:
        self.manager = manager
        self.gateway = gateway or SafeExecutionGateway()

    def dispatch(
        self,
        parsed: CommandParseResult,
    ) -> FileDispatchResult | None:
        command = parsed.command

        if (
            not parsed.matched
            or parsed.requires_clarification
            or command.intent not in _FILE_INTENTS
        ):
            return None

        values = self._values(command)
        action = self._action(command)
        source, destination = self._preview_paths(
            command.intent,
            values,
        )

        conflict = (
            destination is not None
            and destination.exists()
            and command.intent
            in {
                IntentType.CREATE_FILE,
                IntentType.RENAME_FILE,
                IntentType.COPY_FILE,
                IntentType.MOVE_FILE,
            }
        )

        target = destination or source
        has_content = bool(
            command.intent is IntentType.WRITE_FILE
            and target is not None
            and target.exists()
            and target.stat().st_size > 0
        )

        context = SafetyContext(
            command=command,
            action=action,
            session_id=command.session_id or UUID(int=0),
            source_path=source,
            destination_path=destination,
            logical_source=self._logical_source(values),
            logical_destination=self._logical_destination(values),
            target_exists=(target.exists() if target is not None else None),
            target_type="file",
            additional_context={
                "destination_conflict": conflict,
                "target_has_content": has_content,
                "recoverable_deletion": (command.intent is IntentType.DELETE_FILE),
                "permanent_deletion": False,
            },
        )

        executor = self._executor(
            command,
            action,
            values,
            target_has_content=has_content,
        )

        if executor is None:
            return None

        confirmation = self._confirmation(
            command.intent,
            values,
            source,
            destination,
        )
        fingerprint = self._fingerprint(
            command.intent,
            source,
            destination,
        )

        def revalidator() -> ResourceFingerprint | None:
            return self._fingerprint(
                command.intent,
                source,
                destination,
            )

        submitted = self.gateway.submit(
            context,
            executor,
            confirmation=confirmation,
            fingerprint=fingerprint,
            revalidator=revalidator,
        )
        return FileDispatchResult.from_gateway(submitted)

    def dispatch_control(
        self,
        text: str,
        session_id: UUID | None = None,
    ) -> FileDispatchResult | None:
        handled = self.gateway.handle_confirmation(
            text,
            session_id or UUID(int=0),
        )
        return FileDispatchResult.from_gateway(handled) if handled else None

    def clear_pending_confirmations(self) -> None:
        self.gateway.clear_confirmations()

    def _executor(
        self,
        command: UserCommand,
        action: Action,
        values: dict[str, str],
        *,
        target_has_content: bool,
    ) -> Callable[[], ActionResult] | None:
        location = values.get("location")
        action_id = action.action_id
        command_id = command.command_id
        session_id = command.session_id or UUID(int=0)

        if command.intent is IntentType.CREATE_FILE:
            name = self._with_subpath(
                values.get("file_name"),
                values.get("relative_subpath"),
            )

            if name is None:
                return None

            return partial(
                self.manager.create_file,
                name,
                location,
                action_id,
                command_id,
                requested_extension=values.get("file_extension"),
            )

        if command.intent is IntentType.READ_FILE:
            return self._named_executor(
                values,
                self.manager.read_text_file,
                location,
                action,
                command,
            )

        if command.intent is IntentType.WRITE_FILE:
            name = values.get("file_name")
            content = values.get("text_content")

            if name is None or content is None:
                return None

            if target_has_content:
                return partial(
                    self.manager.replace_text_file,
                    name,
                    location,
                    content,
                    action_id,
                    command_id,
                )

            return partial(
                self.manager.write_text_file,
                name,
                location,
                content,
                action_id,
                command_id,
            )

        if command.intent is IntentType.APPEND_FILE:
            name = values.get("file_name")
            content = values.get("text_content")

            if name is None or content is None:
                return None

            return partial(
                self.manager.append_text_file,
                name,
                location,
                content,
                action_id,
                command_id,
            )

        if command.intent is IntentType.RENAME_FILE:
            source = values.get("source_file")
            new_name = values.get("new_name")

            if source is None or new_name is None:
                return None

            return partial(
                self.manager.rename_file,
                source,
                new_name,
                location,
                action_id,
                command_id,
            )

        if command.intent in {
            IntentType.COPY_FILE,
            IntentType.MOVE_FILE,
        }:
            source = values.get("source_file")
            destination = values.get("destination")

            if source is None or destination is None:
                return None

            source_location = values.get("source_location")

            if command.intent is IntentType.COPY_FILE:
                return partial(
                    self.manager.copy_file,
                    source,
                    source_location,
                    destination,
                    action_id,
                    command_id,
                )

            return partial(
                self.manager.move_file,
                source,
                source_location,
                destination,
                action_id,
                command_id,
            )

        if command.intent is IntentType.DELETE_FILE:
            name = values.get("file_name")

            if name is None:
                return None

            return partial(
                self.manager.recycle_file,
                name,
                location,
                action_id,
                command_id,
                session_id,
            )

        if command.intent is IntentType.OPEN_FILE:
            return self._named_executor(
                values,
                self.manager.open_file,
                location,
                action,
                command,
            )

        if command.intent is IntentType.CHECK_FILE_EXISTENCE:
            return self._named_executor(
                values,
                self.manager.file_exists,
                location,
                action,
                command,
            )

        if command.intent is IntentType.GET_FILE_INFORMATION:
            return self._named_executor(
                values,
                self.manager.get_file_information,
                location,
                action,
                command,
            )

        if command.intent is IntentType.SEARCH_FILE:
            query = values.get("file_name") or values.get("search_extension")

            if query is None:
                return None

            return partial(
                self.manager.search_files,
                query,
                location,
                action_id,
                command_id,
                extension=values.get("search_extension"),
            )

        return None

    def _preview_paths(
        self,
        intent: IntentType,
        values: dict[str, str],
    ) -> tuple[Path | None, Path | None]:
        try:
            location = values.get("location")

            if intent is IntentType.CREATE_FILE:
                name = self._with_subpath(
                    values.get("file_name"),
                    values.get("relative_subpath"),
                )

                if name:
                    safe = self.manager._normalize_text_path(
                        name,
                        values.get("file_extension"),
                        default_extension=".txt",
                    )
                    return (
                        None,
                        self.manager._resolve(
                            location,
                            safe,
                        ).path,
                    )

            if intent in {
                IntentType.READ_FILE,
                IntentType.WRITE_FILE,
                IntentType.APPEND_FILE,
                IntentType.OPEN_FILE,
                IntentType.CHECK_FILE_EXISTENCE,
                IntentType.GET_FILE_INFORMATION,
                IntentType.DELETE_FILE,
            }:
                name = values.get("file_name")

                if name:
                    safe = (
                        self.manager._normalize_text_path(name)
                        if intent
                        in {
                            IntentType.WRITE_FILE,
                            IntentType.APPEND_FILE,
                        }
                        else name
                    )
                    path = self.manager._resolve(
                        location,
                        safe,
                    ).path

                    return (
                        path,
                        (path if intent is IntentType.WRITE_FILE else None),
                    )

            if intent is IntentType.RENAME_FILE:
                source_name = values.get("source_file")
                new_name = values.get("new_name")

                if source_name and new_name:
                    source = self.manager._resolve(
                        location,
                        source_name,
                    ).path
                    destination = self.manager._resolve(
                        location,
                        str(Path(source_name).with_name(new_name)),
                    ).path
                    return source, destination

            if intent in {
                IntentType.COPY_FILE,
                IntentType.MOVE_FILE,
            }:
                source_name = values.get("source_file")
                destination_location = values.get("destination")

                if source_name and destination_location:
                    source = self.manager._resolve(
                        values.get("source_location"),
                        source_name,
                    ).path
                    destination = self.manager.path_resolver.resolve(
                        destination_location,
                        source.name,
                    ).path
                    return source, destination

        except (
            FileManagementError,
            OSError,
            ValueError,
        ):
            return None, None

        return None, None

    def _confirmation(
        self,
        intent: IntentType,
        values: dict[str, str],
        source: Path | None,
        destination: Path | None,
    ) -> ConfirmationSpec | None:
        if (
            intent is IntentType.WRITE_FILE
            and destination is not None
            and destination.exists()
            and destination.stat().st_size > 0
        ):
            name = destination.name
            location = self._display(
                values.get("location") or self.manager.settings.default_location
            )
            exact = f"confirm overwrite {name} on {location}"
            return ConfirmationSpec(
                f"{name} on {location}",
                f"Replacing {name} may discard its current contents. "
                f'Type "{exact}" to continue.',
                exact,
                f"cancel overwrite {name} on {location}",
            )

        if (
            intent is IntentType.MOVE_FILE
            and source is not None
            and destination is not None
        ):
            source_location = self._display(
                values.get("source_location") or self.manager.settings.default_location
            )
            destination_location = self._display(values.get("destination"))
            exact = (
                f"confirm move {source.name} from "
                f"{source_location} to {destination_location}"
            )
            return ConfirmationSpec(
                source.name,
                f"Moving {source.name} will remove it from "
                f'{source_location}. Type "{exact}" to continue.',
                exact,
                f"cancel move {source.name} from "
                f"{source_location} to {destination_location}",
            )

        if intent is IntentType.DELETE_FILE and source is not None:
            location = self._display(
                values.get("location") or self.manager.settings.default_location
            )
            exact = f"confirm recycle {source.name} from {location}"
            return ConfirmationSpec(
                source.name,
                f"{source.name} will be moved to the Windows Recycle Bin. "
                f'Type "{exact}" to continue.',
                exact,
                f"cancel recycle {source.name} from {location}",
            )

        return None

    def _fingerprint(
        self,
        intent: IntentType,
        source: Path | None,
        destination: Path | None,
    ) -> ResourceFingerprint | None:
        if intent not in {
            IntentType.WRITE_FILE,
            IntentType.MOVE_FILE,
            IntentType.DELETE_FILE,
        }:
            return None

        items = [
            SafeExecutionGateway.fingerprint_path(path)
            for path in (
                source,
                destination,
            )
            if path is not None
        ]

        if not items:
            return None

        digest = hashlib.sha256(repr(items).encode("utf-8")).hexdigest()

        return ResourceFingerprint(
            "file_operation",
            digest,
            True,
            item_count=len(items),
        )

    @staticmethod
    def _values(
        command: UserCommand,
    ) -> dict[str, str]:
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
    def _with_subpath(
        name: str | None,
        subpath: str | None,
    ) -> str | None:
        if name is None:
            return None

        return str(PureWindowsPath(subpath, name)) if subpath else name

    @staticmethod
    def _named_executor(
        values: dict[str, str],
        method: Callable[
            [
                str,
                str | None,
                UUID,
                UUID | None,
            ],
            ActionResult,
        ],
        location: str | None,
        action: Action,
        command: UserCommand,
    ) -> Callable[[], ActionResult] | None:
        name = values.get("file_name")

        if name is None:
            return None

        return lambda: method(
            name,
            location,
            action.action_id,
            command.command_id,
        )

    @staticmethod
    def _display(value: str | None) -> str:
        return (value or "Desktop").replace("_", " ").title()

    @staticmethod
    def _logical_source(
        values: dict[str, str],
    ) -> str | None:
        return values.get("source_location") or values.get("location")

    @staticmethod
    def _logical_destination(
        values: dict[str, str],
    ) -> str | None:
        return values.get("destination") or values.get("location")

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
            confirmation_status=(ConfirmationStatus.NOT_REQUIRED),
            requires_confirmation=False,
        )
