"""Stable productivity identifiers."""

from enum import StrEnum


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ProductivityItemType(StrEnum):
    NOTE = "note"
    TASK_LIST = "task_list"
    TASK = "task"


class ReminderLinkType(StrEnum):
    DEADLINE = "deadline"
    MANUAL = "manual"


class ExportFormat(StrEnum):
    JSON = "json"
    MARKDOWN = "markdown"
