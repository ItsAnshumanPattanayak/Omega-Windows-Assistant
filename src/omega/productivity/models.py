"""Typed, non-executing records for notes and tasks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import datetime
from uuid import UUID, uuid4

from omega.core.exceptions import ModelValidationError
from omega.models._serialization import (
    JsonValue,
    serialize_value,
    utc_now,
    validate_json_mapping,
    validate_utc_timestamp,
)
from omega.productivity.enums import (
    ExportFormat,
    ProductivityItemType,
    ReminderLinkType,
    TaskPriority,
    TaskStatus,
)

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _text(value: str, name: str, maximum: int, *, empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ModelValidationError(f"{name} must be text.")
    if not empty and not value.strip():
        raise ModelValidationError(f"{name} must not be empty.")
    if len(value) > maximum:
        raise ModelValidationError(f"{name} is too long.")
    return value


def _time(value: datetime | None, name: str) -> datetime | None:
    return None if value is None else validate_utc_timestamp(value, name)


@dataclass(frozen=True)
class Note:
    """One revisioned note whose body is always inert text."""

    title: str
    body: str
    note_id: UUID = field(default_factory=uuid4)
    is_pinned: bool = False
    is_archived: bool = False
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    archived_at: datetime | None = None
    source_command_id: UUID | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)
    revision: int = 1
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.title, "note title", 200, empty=True)
        _text(self.body, "note body", 50_000, empty=True)
        if not self.title.strip() and not self.body.strip():
            raise ModelValidationError("A note needs a title or body.")
        object.__setattr__(self, "created_at", _time(self.created_at, "created_at"))
        object.__setattr__(self, "updated_at", _time(self.updated_at, "updated_at"))
        object.__setattr__(self, "archived_at", _time(self.archived_at, "archived_at"))
        if self.is_archived != (self.archived_at is not None):
            raise ModelValidationError("Archived note state is inconsistent.")
        if self.revision < 1:
            raise ModelValidationError("revision must be positive.")
        object.__setattr__(
            self, "metadata", validate_json_mapping(self.metadata, "metadata")
        )
        object.__setattr__(self, "tags", _unique_tags(self.tags))

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "note_id": str(self.note_id),
            "title": self.title,
            "body": self.body,
            "is_pinned": self.is_pinned,
            "is_archived": self.is_archived,
            "created_at": serialize_value(self.created_at),
            "updated_at": serialize_value(self.updated_at),
            "archived_at": serialize_value(self.archived_at),
            "source_command_id": (
                str(self.source_command_id) if self.source_command_id else None
            ),
            "metadata": self.metadata,
            "revision": self.revision,
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class TaskList:
    name: str
    description: str = ""
    task_list_id: UUID = field(default_factory=uuid4)
    is_archived: bool = False
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    archived_at: datetime | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)
    revision: int = 1

    def __post_init__(self) -> None:
        _text(self.name, "task-list name", 200)
        _text(self.description, "task-list description", 5_000, empty=True)
        object.__setattr__(self, "created_at", _time(self.created_at, "created_at"))
        object.__setattr__(self, "updated_at", _time(self.updated_at, "updated_at"))
        object.__setattr__(self, "archived_at", _time(self.archived_at, "archived_at"))
        if self.is_archived != (self.archived_at is not None):
            raise ModelValidationError("Archived task-list state is inconsistent.")
        if self.revision < 1:
            raise ModelValidationError("revision must be positive.")
        object.__setattr__(
            self, "metadata", validate_json_mapping(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "task_list_id": str(self.task_list_id),
            "name": self.name,
            "description": self.description,
            "is_archived": self.is_archived,
            "created_at": serialize_value(self.created_at),
            "updated_at": serialize_value(self.updated_at),
            "archived_at": serialize_value(self.archived_at),
            "metadata": self.metadata,
            "revision": self.revision,
        }


@dataclass(frozen=True)
class Task:
    task_list_id: UUID
    title: str
    description: str = ""
    task_id: UUID = field(default_factory=uuid4)
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NONE
    due_at_utc: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    is_archived: bool = False
    archived_at: datetime | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    source_command_id: UUID | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)
    revision: int = 1
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.title, "task title", 300)
        _text(self.description, "task description", 5_000, empty=True)
        for name in (
            "due_at_utc",
            "completed_at",
            "cancelled_at",
            "archived_at",
            "created_at",
            "updated_at",
        ):
            object.__setattr__(self, name, _time(getattr(self, name), name))
        if self.status is TaskStatus.COMPLETED and self.completed_at is None:
            raise ModelValidationError("Completed tasks require completed_at.")
        if self.status is not TaskStatus.COMPLETED and self.completed_at is not None:
            raise ModelValidationError("Only completed tasks may have completed_at.")
        if self.status is TaskStatus.CANCELLED and self.cancelled_at is None:
            raise ModelValidationError("Cancelled tasks require cancelled_at.")
        if self.status is not TaskStatus.CANCELLED and self.cancelled_at is not None:
            raise ModelValidationError("Only cancelled tasks may have cancelled_at.")
        if self.is_archived != (self.archived_at is not None):
            raise ModelValidationError("Archived task state is inconsistent.")
        if self.revision < 1:
            raise ModelValidationError("revision must be positive.")
        object.__setattr__(
            self, "metadata", validate_json_mapping(self.metadata, "metadata")
        )
        object.__setattr__(self, "tags", _unique_tags(self.tags))

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "task_id": str(self.task_id),
            "task_list_id": str(self.task_list_id),
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "due_at_utc": serialize_value(self.due_at_utc),
            "completed_at": serialize_value(self.completed_at),
            "cancelled_at": serialize_value(self.cancelled_at),
            "is_archived": self.is_archived,
            "archived_at": serialize_value(self.archived_at),
            "created_at": serialize_value(self.created_at),
            "updated_at": serialize_value(self.updated_at),
            "source_command_id": (
                str(self.source_command_id) if self.source_command_id else None
            ),
            "metadata": self.metadata,
            "revision": self.revision,
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class Tag:
    display_name: str
    tag_id: UUID = field(default_factory=uuid4)
    normalized_name: str = ""
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        display = normalize_tag(self.display_name)
        normalized = display.casefold()
        if self.normalized_name and self.normalized_name != normalized:
            raise ModelValidationError("normalized_name does not match display_name.")
        object.__setattr__(self, "display_name", display)
        object.__setattr__(self, "normalized_name", normalized)
        object.__setattr__(self, "created_at", _time(self.created_at, "created_at"))


@dataclass(frozen=True)
class ReminderLink:
    task_id: UUID
    schedule_id: UUID
    link_type: ReminderLinkType = ReminderLinkType.MANUAL
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "created_at", _time(self.created_at, "created_at"))


@dataclass(frozen=True)
class ProductivitySearchQuery:
    text: str = ""
    item_types: tuple[ProductivityItemType, ...] = ()
    statuses: tuple[TaskStatus, ...] = ()
    priorities: tuple[TaskPriority, ...] = ()
    tag: str | None = None
    include_archived: bool = False
    limit: int = 50

    def __post_init__(self) -> None:
        _text(self.text, "search query", 500, empty=True)
        if not 1 <= self.limit <= 200:
            raise ModelValidationError("Search limit must be between 1 and 200.")
        if self.tag is not None:
            object.__setattr__(self, "tag", normalize_tag(self.tag))


@dataclass(frozen=True)
class ProductivityExportResult:
    path: str
    format: ExportFormat
    item_count: int
    bytes_written: int


@dataclass(frozen=True)
class ProductivityImportResult:
    notes_created: int
    task_lists_created: int
    tasks_created: int
    preview: bool


def normalize_tag(value: str) -> str:
    display = " ".join(value.split())
    if not display or len(display) > 50 or _CONTROL.search(display):
        raise ModelValidationError("Tag text is empty, too long, or contains controls.")
    return display


def _unique_tags(values: tuple[str, ...]) -> tuple[str, ...]:
    normalized: dict[str, str] = {}
    for value in values:
        display = normalize_tag(value)
        key = display.casefold()
        if key in normalized:
            raise ModelValidationError("Tags must be unique.")
        normalized[key] = display
    return tuple(sorted(normalized.values(), key=str.casefold))


def task_with_status(task: Task, status: TaskStatus, now: datetime) -> Task:
    """Return a validated lifecycle transition without mutating the input record."""

    timestamp = validate_utc_timestamp(now, "now")
    completed = timestamp if status is TaskStatus.COMPLETED else None
    cancelled = timestamp if status is TaskStatus.CANCELLED else None
    return replace(
        task,
        status=status,
        completed_at=completed,
        cancelled_at=cancelled,
        updated_at=timestamp,
        revision=task.revision + 1,
    )
