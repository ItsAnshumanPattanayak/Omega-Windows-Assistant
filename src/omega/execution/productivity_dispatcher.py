"""Productivity proposals routed exclusively through the central safety gateway."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from omega.models import (
    Action,
    ActionResult,
    ConfirmationStatus,
    ErrorCategory,
    IntentType,
    OmegaErrorDetails,
    PermissionDecision,
    RiskLevel,
    UserCommand,
)
from omega.models._serialization import JsonValue
from omega.productivity import (
    ExportFormat,
    Note,
    Task,
    TaskList,
    TaskPriority,
    TaskStatus,
)
from omega.productivity.export import ProductivityExportService
from omega.productivity.importers import ProductivityImportService
from omega.productivity.service import ProductivityService
from omega.safety import (
    ConfirmationSpec,
    GatewayDispatchResult,
    SafeExecutionGateway,
    SafetyContext,
)
from omega.safety.models import ResourceFingerprint
from omega.understanding.result import CommandParseResult

_NOTE = {
    IntentType.CREATE_NOTE,
    IntentType.LIST_NOTES,
    IntentType.SHOW_NOTE,
    IntentType.UPDATE_NOTE,
    IntentType.APPEND_NOTE,
    IntentType.SEARCH_NOTES,
    IntentType.PIN_NOTE,
    IntentType.UNPIN_NOTE,
    IntentType.ARCHIVE_NOTE,
    IntentType.RESTORE_NOTE,
    IntentType.DELETE_NOTE,
    IntentType.TAG_NOTE,
    IntentType.UNTAG_NOTE,
    IntentType.EXPORT_NOTES,
    IntentType.IMPORT_NOTES,
}
_LISTS = {
    IntentType.CREATE_TASK_LIST,
    IntentType.LIST_TASK_LISTS,
    IntentType.SHOW_TASK_LIST,
    IntentType.UPDATE_TASK_LIST,
    IntentType.ARCHIVE_TASK_LIST,
    IntentType.RESTORE_TASK_LIST,
    IntentType.DELETE_TASK_LIST,
}
_TASK = {
    IntentType.CREATE_TASK,
    IntentType.LIST_TASKS,
    IntentType.SHOW_TASK,
    IntentType.UPDATE_TASK,
    IntentType.COMPLETE_TASK,
    IntentType.REOPEN_TASK,
    IntentType.CANCEL_TASK,
    IntentType.ARCHIVE_TASK,
    IntentType.RESTORE_TASK,
    IntentType.DELETE_TASK,
    IntentType.SET_TASK_PRIORITY,
    IntentType.SET_TASK_DEADLINE,
    IntentType.REMOVE_TASK_DEADLINE,
    IntentType.SEARCH_TASKS,
    IntentType.SHOW_DUE_TASKS,
    IntentType.SHOW_OVERDUE_TASKS,
    IntentType.MOVE_TASK,
    IntentType.TAG_TASK,
    IntentType.UNTAG_TASK,
    IntentType.LINK_TASK_REMINDER,
    IntentType.UNLINK_TASK_REMINDER,
}
_HANDLED = _NOTE | _LISTS | _TASK
_DESTRUCTIVE = {
    IntentType.DELETE_NOTE,
    IntentType.DELETE_TASK,
    IntentType.DELETE_TASK_LIST,
}


@dataclass(frozen=True)
class ProductivityDispatchResult:
    command: UserCommand
    action: Action
    result: ActionResult

    @property
    def user_message(self) -> str:
        return self.result.user_message

    @classmethod
    def from_gateway(cls, value: GatewayDispatchResult) -> ProductivityDispatchResult:
        return cls(value.command, value.action, value.result)


class ProductivityActionDispatcher:
    """Build one typed action and execute it once only after gateway approval."""

    def __init__(
        self,
        service: ProductivityService,
        gateway: SafeExecutionGateway,
        export_service: ProductivityExportService | None = None,
        import_service: ProductivityImportService | None = None,
    ) -> None:
        self.service = service
        self.gateway = gateway
        self.export_service = export_service
        self.import_service = import_service

    def dispatch(self, parsed: CommandParseResult) -> ProductivityDispatchResult | None:
        command = parsed.command
        if (
            not parsed.matched
            or parsed.requires_clarification
            or command.intent not in _HANDLED
        ):
            return None
        target = self._target(command)
        reference = self._text(command, "reference") or command.intent.value
        revision = getattr(target, "revision", None)
        risk = (
            RiskLevel.HIGH
            if command.intent in _DESTRUCTIVE
            else (
                RiskLevel.MEDIUM
                if command.intent
                in {
                    IntentType.ARCHIVE_NOTE,
                    IntentType.RESTORE_NOTE,
                    IntentType.ARCHIVE_TASK,
                    IntentType.RESTORE_TASK,
                    IntentType.ARCHIVE_TASK_LIST,
                    IntentType.RESTORE_TASK_LIST,
                    IntentType.CANCEL_TASK,
                }
                else RiskLevel.LOW
            )
        )
        action = Action(
            command.command_id,
            command.intent,
            parameters={
                "reference": reference,
                "revision": revision,
                "content_is_inert": True,
            },
            risk_level=risk,
            permission_decision=PermissionDecision.ALLOW,
            confirmation_status=ConfirmationStatus.NOT_REQUIRED,
            requires_confirmation=False,
        )
        context = SafetyContext(
            command,
            action,
            command.session_id or UUID(int=0),
            logical_source=reference,
            target_type="productivity_record",
            target_exists=target is not None,
            additional_context={
                "revision": revision,
                "content_is_inert": True,
                "scheduled_command": False,
            },
        )
        confirmation = (
            ConfirmationSpec(
                reference,
                f"Deleting {reference} requires confirmation. "
                f'Type "confirm delete {reference}".',
                f"confirm delete {reference}",
                f"cancel delete {reference}",
            )
            if command.intent in _DESTRUCTIVE
            else None
        )
        fingerprint = self._fingerprint(target)
        result = self.gateway.submit(
            context,
            lambda: self._execute(command, action, target),
            confirmation=confirmation,
            fingerprint=fingerprint,
            revalidator=lambda: self._current_fingerprint(command),
        )
        return ProductivityDispatchResult.from_gateway(result)

    def _execute(
        self, command: UserCommand, action: Action, target: object | None
    ) -> ActionResult:
        try:
            return self._execute_validated(command, action, target)
        except Exception as error:
            details = OmegaErrorDetails(
                "PRODUCTIVITY_FAILED",
                ErrorCategory.VALIDATION,
                type(error).__name__,
                str(error) or "The productivity request failed safely.",
                True,
                action_id=action.action_id,
                command_id=command.command_id,
            )
            return ActionResult.failure_result(
                action.action_id,
                type(error).__name__,
                str(error) or "The productivity request failed safely.",
                details,
            )

    def _execute_validated(
        self, command: UserCommand, action: Action, target: object | None
    ) -> ActionResult:
        intent = command.intent
        if intent is IntentType.CREATE_NOTE:
            item = self.service.create_note(
                self._required(command, "note_title"),
                self._text(command, "note_body") or "",
                command_id=(
                    command.command_id if self.gateway.persistence is not None else None
                ),
            )
            return self._success(
                action, "Note created.", f"Created note “{item.title}”.", item.to_dict()
            )
        if intent is IntentType.EXPORT_NOTES:
            if self.export_service is None:
                raise ValueError("Productivity export is unavailable.")
            name = self._text(command, "file_name") or "omega-productivity.json"
            format = (
                ExportFormat.MARKDOWN
                if name.casefold().endswith(".md")
                else ExportFormat.JSON
            )
            exported = self.export_service.export(name, format)
            return self._success(
                action,
                "Productivity exported.",
                f"Exported {exported.item_count} items.",
                {
                    "path": exported.path,
                    "format": exported.format.value,
                    "item_count": exported.item_count,
                    "bytes_written": exported.bytes_written,
                },
            )
        if intent is IntentType.IMPORT_NOTES:
            if self.import_service is None:
                raise ValueError("Productivity import is unavailable.")
            imported = self.import_service.import_json(
                self._required(command, "file_name")
            )
            return self._success(
                action,
                "Productivity imported.",
                "The validated productivity JSON was imported.",
                {
                    "notes_created": imported.notes_created,
                    "task_lists_created": imported.task_lists_created,
                    "tasks_created": imported.tasks_created,
                },
            )
        if intent is IntentType.LIST_NOTES:
            items = self.service.repository.list_notes(
                limit=self.service.configuration.maximum_search_results
            )
            return self._collection(action, "notes", items)
        if intent is IntentType.SEARCH_NOTES:
            items = self.service.repository.list_notes(
                query=self._required(command, "search_query"),
                limit=self.service.configuration.maximum_search_results,
            )
            return self._collection(action, "notes", items)
        if intent in _NOTE:
            if target is None:
                raise ValueError("Specify one existing note.")
            note = cast(Note, target)
            if intent is IntentType.SHOW_NOTE:
                return self._success(
                    action,
                    "Note found.",
                    f"{note.title}\n{note.body}",
                    note.to_dict(),
                )
            if intent is IntentType.DELETE_NOTE:
                self.service.delete_note(note.note_id, note.revision)
                return self._success(
                    action, "Note deleted.", "The note was deleted.", {}
                )
            if intent is IntentType.APPEND_NOTE:
                updated_note = self.service.update_note(
                    note.note_id,
                    note.revision,
                    append=self._required(command, "note_body"),
                )
                return self._success(
                    action,
                    "Note updated.",
                    f"Updated note “{updated_note.title}”.",
                    updated_note.to_dict(),
                )
            if intent in {IntentType.TAG_NOTE, IntentType.UNTAG_NOTE}:
                tag = self._required(command, "tag")
                tags = {item.casefold(): item for item in note.tags}
                if intent is IntentType.TAG_NOTE:
                    tags[tag.casefold()] = tag
                else:
                    tags.pop(tag.casefold(), None)
                updated_note = self.service.set_note_tags(
                    note.note_id,
                    note.revision,
                    tuple(tags.values()),
                )
                return self._success(
                    action,
                    "Note tags updated.",
                    f"Updated tags for “{updated_note.title}”.",
                    updated_note.to_dict(),
                )
            updated_note = self.service.update_note(
                note.note_id,
                note.revision,
                pinned=(
                    True
                    if intent is IntentType.PIN_NOTE
                    else False if intent is IntentType.UNPIN_NOTE else None
                ),
                archived=(
                    True
                    if intent is IntentType.ARCHIVE_NOTE
                    else False if intent is IntentType.RESTORE_NOTE else None
                ),
            )
            return self._success(
                action,
                "Note updated.",
                f"Updated note “{updated_note.title}”.",
                updated_note.to_dict(),
            )
        if intent is IntentType.CREATE_TASK_LIST:
            created_list = self.service.create_task_list(
                self._required(command, "task_list_name")
            )
            return self._success(
                action,
                "Task list created.",
                f"Created task list “{created_list.name}”.",
                created_list.to_dict(),
            )
        if intent is IntentType.LIST_TASK_LISTS:
            return self._collection(
                action, "task lists", self.service.repository.list_task_lists()
            )
        if intent in _LISTS:
            if target is None:
                raise ValueError("Specify one existing task list.")
            task_list = cast(TaskList, target)
            if intent is IntentType.SHOW_TASK_LIST:
                return self._success(
                    action,
                    "Task list found.",
                    task_list.name,
                    task_list.to_dict(),
                )
            if intent is IntentType.DELETE_TASK_LIST:
                self.service.delete_task_list(
                    task_list.task_list_id, task_list.revision
                )
                return self._success(
                    action, "Task list deleted.", "The empty task list was deleted.", {}
                )
            updated_list = self.service.update_task_list(
                task_list.task_list_id,
                task_list.revision,
                archived=intent is IntentType.ARCHIVE_TASK_LIST,
            )
            return self._success(
                action,
                "Task list updated.",
                f"Updated task list “{updated_list.name}”.",
                updated_list.to_dict(),
            )
        if intent is IntentType.CREATE_TASK:
            created_task = self.service.create_task(
                self._required(command, "task_title"),
                task_list_id=(
                    self.service.resolve_task_list(
                        self._required(command, "task_list_name")
                    ).task_list_id
                    if self._text(command, "task_list_name")
                    else None
                ),
                command_id=(
                    command.command_id if self.gateway.persistence is not None else None
                ),
            )
            return self._success(
                action,
                "Task created.",
                f"Created task “{created_task.title}”.",
                created_task.to_dict(),
            )
        if intent in {
            IntentType.LIST_TASKS,
            IntentType.SHOW_DUE_TASKS,
            IntentType.SHOW_OVERDUE_TASKS,
            IntentType.SEARCH_TASKS,
        }:
            now = datetime.now(UTC)
            selected_tasks = self.service.repository.list_tasks(
                query=(
                    self._text(command, "search_query")
                    if intent is IntentType.SEARCH_TASKS
                    else None
                ),
                overdue_at=now if intent is IntentType.SHOW_OVERDUE_TASKS else None,
                due_from=now if intent is IntentType.SHOW_DUE_TASKS else None,
                due_before=(
                    now + timedelta(days=1)
                    if intent is IntentType.SHOW_DUE_TASKS
                    else None
                ),
                limit=self.service.configuration.maximum_search_results,
            )
            return self._collection(action, "tasks", selected_tasks)
        if target is None:
            raise ValueError("Specify one existing task.")
        task = cast(Task, target)
        if intent is IntentType.SHOW_TASK:
            return self._success(action, "Task found.", task.title, task.to_dict())
        if intent is IntentType.DELETE_TASK:
            self.service.delete_task(task.task_id, task.revision)
            return self._success(action, "Task deleted.", "The task was deleted.", {})
        if intent in {
            IntentType.LINK_TASK_REMINDER,
            IntentType.UNLINK_TASK_REMINDER,
        }:
            raw_schedule_id = self._text(command, "schedule_id")
            if intent is IntentType.LINK_TASK_REMINDER and raw_schedule_id is None:
                task = self.service.update_task(
                    task.task_id,
                    task.revision,
                    due_at_utc=self._deadline(command.original_text),
                )
                link = self.service.create_deadline_reminder(
                    task.task_id, action.action_id, command.command_id
                )
                return self._success(
                    action,
                    "Deadline reminder created.",
                    "A notification reminder is linked to the task deadline.",
                    {
                        "task_id": str(link.task_id),
                        "schedule_id": str(link.schedule_id),
                        "link_type": link.link_type.value,
                    },
                )
            if raw_schedule_id is None:
                raise ValueError("schedule_id is required.")
            schedule_id = UUID(raw_schedule_id)
            if intent is IntentType.LINK_TASK_REMINDER:
                link = self.service.link_reminder(task.task_id, schedule_id)
                data: dict[str, JsonValue] = {
                    "task_id": str(link.task_id),
                    "schedule_id": str(link.schedule_id),
                    "link_type": link.link_type.value,
                }
                return self._success(
                    action,
                    "Reminder linked.",
                    "The reminder is linked to the task.",
                    data,
                )
            removed = self.service.unlink_reminder(task.task_id, schedule_id)
            return self._success(
                action,
                "Reminder unlinked.",
                (
                    "The reminder link was removed."
                    if removed
                    else "No matching reminder link was found."
                ),
                {"removed": removed},
            )
        if intent in {IntentType.TAG_TASK, IntentType.UNTAG_TASK}:
            tag = self._required(command, "tag")
            tags = {item.casefold(): item for item in task.tags}
            if intent is IntentType.TAG_TASK:
                tags[tag.casefold()] = tag
            else:
                tags.pop(tag.casefold(), None)
            updated_task = self.service.set_task_tags(
                task.task_id, task.revision, tuple(tags.values())
            )
            return self._success(
                action,
                "Task tags updated.",
                f"Updated tags for “{updated_task.title}”.",
                updated_task.to_dict(),
            )
        transitions = {
            IntentType.COMPLETE_TASK: TaskStatus.COMPLETED,
            IntentType.REOPEN_TASK: TaskStatus.PENDING,
            IntentType.CANCEL_TASK: TaskStatus.CANCELLED,
        }
        if intent in transitions:
            updated_task = self.service.transition_task(
                task.task_id, task.revision, transitions[intent]
            )
        else:
            updated_task = self.service.update_task(
                task.task_id,
                task.revision,
                archived=(
                    True
                    if intent is IntentType.ARCHIVE_TASK
                    else False if intent is IntentType.RESTORE_TASK else None
                ),
                priority=(
                    TaskPriority(self._required(command, "priority"))
                    if intent is IntentType.SET_TASK_PRIORITY
                    else None
                ),
                task_list_id=(
                    self.service.resolve_task_list(
                        self._required(command, "task_list_name")
                    ).task_list_id
                    if intent is IntentType.MOVE_TASK
                    else None
                ),
                due_at_utc=(
                    None
                    if intent is IntentType.REMOVE_TASK_DEADLINE
                    else (
                        self._deadline(command.original_text)
                        if intent is IntentType.SET_TASK_DEADLINE
                        else ...
                    )
                ),
            )
        return self._success(
            action,
            "Task updated.",
            f"Updated task “{updated_task.title}”.",
            updated_task.to_dict(),
        )

    def _target(self, command: UserCommand) -> object | None:
        reference = self._text(command, "reference")
        if not reference:
            return None
        try:
            if command.intent in _NOTE:
                return self.service.resolve_note(reference, include_archived=True)
            if command.intent in _LISTS:
                return self.service.resolve_task_list(reference)
            if command.intent in _TASK:
                return self.service.resolve_task(reference, include_archived=True)
        except Exception:
            return None
        return None

    def _current_fingerprint(self, command: UserCommand) -> ResourceFingerprint | None:
        return self._fingerprint(self._target(command))

    @staticmethod
    def _fingerprint(target: object | None) -> ResourceFingerprint | None:
        if target is None:
            return None
        item_id = (
            getattr(target, "note_id", None)
            or getattr(target, "task_id", None)
            or getattr(target, "task_list_id", None)
        )
        return ResourceFingerprint(
            "productivity_record",
            f"{item_id}:{getattr(target, 'revision', 0)}",
            True,
        )

    @staticmethod
    def _text(command: UserCommand, name: str) -> str | None:
        for item in command.entities:
            if item.name == name and isinstance(item.value, str):
                return item.value
        return None

    @classmethod
    def _required(cls, command: UserCommand, name: str) -> str:
        value = cls._text(command, name)
        if value is None or not value.strip():
            raise ValueError(f"{name} is required.")
        return value

    @staticmethod
    def _success(
        action: Action, message: str, user_message: str, data: dict[str, JsonValue]
    ) -> ActionResult:
        return ActionResult.success_result(
            action.action_id, message, user_message, data=data
        )

    @classmethod
    def _collection(
        cls,
        action: Action,
        label: str,
        items: Sequence[Note | Task | TaskList],
    ) -> ActionResult:
        selected = tuple(items)
        data: dict[str, JsonValue] = {"items": [item.to_dict() for item in selected]}
        names = [getattr(item, "title", getattr(item, "name", "")) for item in selected]
        message = "\n".join(str(item) for item in names) or f"No {label} found."
        return cls._success(action, f"{label.title()} listed.", message, data)

    @staticmethod
    def _deadline(text: str) -> datetime:
        now = datetime.now().astimezone()
        time_match = re.search(
            r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", text, re.IGNORECASE
        )
        hour, minute = 9, 0
        if time_match:
            hour = int(time_match.group(1)) % 12
            if time_match.group(3).casefold() == "pm":
                hour += 12
            minute = int(time_match.group(2) or 0)
        day = (
            now.date() + timedelta(days=1)
            if "tomorrow" in text.casefold()
            else now.date()
        )
        value = datetime(day.year, day.month, day.day, hour, minute, tzinfo=now.tzinfo)
        if value <= now:
            value += timedelta(days=1)
        return value.astimezone(UTC)
