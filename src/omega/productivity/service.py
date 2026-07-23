"""Application-facing productivity operations over revisioned repositories."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from types import EllipsisType
from uuid import UUID

from omega.productivity.configuration import ProductivityConfiguration
from omega.productivity.enums import ReminderLinkType, TaskPriority, TaskStatus
from omega.productivity.exceptions import (
    ProductivityConflictError,
    ProductivityNotFoundError,
    ReminderLinkError,
)
from omega.productivity.models import (
    Note,
    ProductivitySearchQuery,
    ReminderLink,
    Task,
    TaskList,
    normalize_tag,
    task_with_status,
)
from omega.productivity.repositories import ProductivityRepository
from omega.scheduling import (
    ScheduleRepository,
    ScheduleStatus,
    ScheduleType,
    SchedulingService,
)


class ProductivityService:
    """Coordinate notes and tasks; stored text is never interpreted or executed."""

    def __init__(
        self,
        configuration: ProductivityConfiguration,
        repository: ProductivityRepository,
        schedule_repository: ScheduleRepository | None = None,
        scheduling_service: SchedulingService | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.configuration = configuration
        self.repository = repository
        self.schedule_repository = schedule_repository
        self.scheduling_service = scheduling_service
        self.clock = clock

    def create_note(
        self,
        title: str,
        body: str = "",
        *,
        tags: Sequence[str] = (),
        command_id: UUID | None = None,
    ) -> Note:
        self._enabled()
        if len(self.repository.list_notes(include_archived=True, limit=1_000_000)) >= (
            self.configuration.maximum_notes
        ):
            raise ProductivityConflictError("The configured note limit was reached.")
        self._note_text(title, body)
        selected_tags = self._tags(tags)
        note = self.repository.add_note(Note(title, body, source_command_id=command_id))
        if selected_tags:
            self.repository.set_note_tags(note.note_id, selected_tags)
            note = self._require_note(note.note_id)
        return note

    def resolve_note(self, reference: str, *, include_archived: bool = False) -> Note:
        return self.repository.resolve_note(
            reference, include_archived=include_archived
        )

    def resolve_task(self, reference: str, *, include_archived: bool = False) -> Task:
        return self.repository.resolve_task(
            reference, include_archived=include_archived
        )

    def resolve_task_list(self, reference: str) -> TaskList:
        return self.repository.resolve_task_list(reference)

    def search(
        self, query: ProductivitySearchQuery
    ) -> dict[str, tuple[Note | Task | TaskList, ...]]:
        """Search notes, tasks, and lists with one bounded typed query."""

        limit = min(query.limit, self.configuration.maximum_search_results)
        types = set(query.item_types)
        include_all = not types
        return {
            "notes": (
                self.repository.list_notes(
                    include_archived=query.include_archived,
                    query=query.text or None,
                    tag=query.tag,
                    limit=limit,
                )
                if include_all or any(item.value == "note" for item in types)
                else ()
            ),
            "tasks": (
                self.repository.list_tasks(
                    statuses=query.statuses,
                    priorities=query.priorities,
                    include_archived=query.include_archived,
                    query=query.text or None,
                    tag=query.tag,
                    limit=limit,
                )
                if include_all or any(item.value == "task" for item in types)
                else ()
            ),
            "task_lists": (
                self.repository.search_task_lists(query.text, limit=limit)
                if (include_all or any(item.value == "task_list" for item in types))
                and query.text
                else ()
            ),
        }

    def update_note(
        self,
        note_id: UUID,
        expected_revision: int,
        *,
        title: str | None = None,
        body: str | None = None,
        append: str | None = None,
        pinned: bool | None = None,
        archived: bool | None = None,
    ) -> Note:
        item = self._require_note(note_id)
        new_title = item.title if title is None else title
        new_body = item.body if body is None else body
        if append is not None:
            new_body += append
        self._note_text(new_title, new_body)
        now = self._now()
        selected_archived = item.is_archived if archived is None else archived
        updated = replace(
            item,
            title=new_title,
            body=new_body,
            is_pinned=item.is_pinned if pinned is None else pinned,
            is_archived=selected_archived,
            archived_at=(
                item.archived_at
                if selected_archived and item.archived_at
                else now if selected_archived else None
            ),
            updated_at=now,
            revision=item.revision + 1,
        )
        return self.repository.update_note(updated, expected_revision)

    def delete_note(self, note_id: UUID, expected_revision: int) -> None:
        self.repository.delete_note(note_id, expected_revision)

    def set_note_tags(
        self, note_id: UUID, expected_revision: int, tags: Sequence[str]
    ) -> Note:
        item = self._require_note(note_id)
        if item.revision != expected_revision:
            raise ProductivityConflictError("The note changed before tag update.")
        self.repository.set_note_tags(note_id, self._tags(tags))
        return self.update_note(note_id, expected_revision)

    def create_task_list(self, name: str, description: str = "") -> TaskList:
        self._enabled()
        if len(self.repository.list_task_lists(include_archived=True)) >= (
            self.configuration.maximum_task_lists
        ):
            raise ProductivityConflictError(
                "The configured task-list limit was reached."
            )
        if not name.strip() or len(name) > 200 or len(description) > 5_000:
            raise ProductivityConflictError("Task-list text is empty or too long.")
        return self.repository.add_task_list(TaskList(name, description))

    def update_task_list(
        self,
        task_list_id: UUID,
        expected_revision: int,
        *,
        name: str | None = None,
        description: str | None = None,
        archived: bool | None = None,
    ) -> TaskList:
        item = self.repository.get_task_list(task_list_id)
        if item is None:
            raise ProductivityNotFoundError("That task list was not found.")
        now = self._now()
        selected_archived = item.is_archived if archived is None else archived
        updated = replace(
            item,
            name=item.name if name is None else name,
            description=item.description if description is None else description,
            is_archived=selected_archived,
            archived_at=(
                item.archived_at
                if selected_archived and item.archived_at
                else now if selected_archived else None
            ),
            updated_at=now,
            revision=item.revision + 1,
        )
        return self.repository.update_task_list(updated, expected_revision)

    def delete_task_list(
        self, task_list_id: UUID, expected_revision: int, *, include_tasks: bool = False
    ) -> None:
        self.repository.delete_task_list(
            task_list_id, expected_revision, include_tasks=include_tasks
        )

    def create_task(
        self,
        title: str,
        *,
        task_list_id: UUID | None = None,
        description: str = "",
        priority: TaskPriority = TaskPriority.NONE,
        due_at_utc: datetime | None = None,
        tags: Sequence[str] = (),
        command_id: UUID | None = None,
    ) -> Task:
        self._enabled()
        if len(self.repository.list_tasks(include_archived=True, limit=1_000_000)) >= (
            self.configuration.maximum_tasks
        ):
            raise ProductivityConflictError("The configured task limit was reached.")
        selected_list = (
            self.repository.get_task_list(task_list_id) if task_list_id else None
        )
        if selected_list is None:
            lists = self.repository.list_task_lists()
            selected_list = next(
                (item for item in lists if item.name.casefold() == "inbox"), None
            ) or self.create_task_list("Inbox")
        if selected_list.is_archived:
            raise ProductivityConflictError(
                "Tasks cannot be added to an archived list."
            )
        self._task_text(title, description)
        selected_tags = self._tags(tags)
        task = self.repository.add_task(
            Task(
                selected_list.task_list_id,
                title,
                description,
                priority=priority,
                due_at_utc=due_at_utc,
                source_command_id=command_id,
            )
        )
        if selected_tags:
            self.repository.set_task_tags(task.task_id, selected_tags)
            task = self._require_task(task.task_id)
        return task

    def update_task(
        self,
        task_id: UUID,
        expected_revision: int,
        *,
        title: str | None = None,
        description: str | None = None,
        priority: TaskPriority | None = None,
        due_at_utc: datetime | None | EllipsisType = ...,
        task_list_id: UUID | None = None,
        archived: bool | None = None,
    ) -> Task:
        task = self._require_task(task_id)
        selected_title = task.title if title is None else title
        selected_description = task.description if description is None else description
        self._task_text(selected_title, selected_description)
        if task_list_id is not None:
            target = self.repository.get_task_list(task_list_id)
            if target is None or target.is_archived:
                raise ProductivityNotFoundError(
                    "The destination task list is unavailable."
                )
        now = self._now()
        selected_archived = task.is_archived if archived is None else archived
        updated = replace(
            task,
            task_list_id=task.task_list_id if task_list_id is None else task_list_id,
            title=selected_title,
            description=selected_description,
            priority=task.priority if priority is None else priority,
            due_at_utc=(
                task.due_at_utc if isinstance(due_at_utc, EllipsisType) else due_at_utc
            ),
            is_archived=selected_archived,
            archived_at=(
                task.archived_at
                if selected_archived and task.archived_at
                else now if selected_archived else None
            ),
            updated_at=now,
            revision=task.revision + 1,
        )
        return self.repository.update_task(updated, expected_revision)

    def transition_task(
        self, task_id: UUID, expected_revision: int, status: TaskStatus
    ) -> Task:
        task = self._require_task(task_id)
        if task.status is status:
            return task
        allowed = {
            TaskStatus.PENDING: {
                TaskStatus.IN_PROGRESS,
                TaskStatus.COMPLETED,
                TaskStatus.CANCELLED,
            },
            TaskStatus.IN_PROGRESS: {
                TaskStatus.PENDING,
                TaskStatus.COMPLETED,
                TaskStatus.CANCELLED,
            },
            TaskStatus.COMPLETED: {TaskStatus.PENDING},
            TaskStatus.CANCELLED: {TaskStatus.PENDING},
        }
        if status not in allowed[task.status]:
            raise ProductivityConflictError("That task transition is not valid.")
        updated = task_with_status(task, status, self._now())
        return self.repository.update_task(updated, expected_revision)

    def delete_task(self, task_id: UUID, expected_revision: int) -> None:
        self.repository.delete_task(task_id, expected_revision)

    def set_task_tags(
        self, task_id: UUID, expected_revision: int, tags: Sequence[str]
    ) -> Task:
        item = self._require_task(task_id)
        if item.revision != expected_revision:
            raise ProductivityConflictError("The task changed before tag update.")
        self.repository.set_task_tags(task_id, self._tags(tags))
        return self.update_task(task_id, expected_revision)

    def link_reminder(
        self,
        task_id: UUID,
        schedule_id: UUID,
        link_type: ReminderLinkType = ReminderLinkType.MANUAL,
    ) -> ReminderLink:
        if not self.configuration.reminder_linking_enabled:
            raise ReminderLinkError("Task reminder linking is disabled.")
        self._require_task(task_id)
        if self.schedule_repository is None:
            raise ReminderLinkError("Scheduling is unavailable.")
        schedule = self.schedule_repository.get(schedule_id)
        if schedule is None or schedule.schedule_type is not ScheduleType.REMINDER:
            raise ReminderLinkError("That reminder was not found.")
        if schedule.status is ScheduleStatus.CANCELLED:
            raise ReminderLinkError("A cancelled reminder cannot be linked.")
        return self.repository.link_reminder(
            ReminderLink(task_id, schedule_id, link_type)
        )

    def unlink_reminder(self, task_id: UUID, schedule_id: UUID) -> bool:
        self._require_task(task_id)
        return self.repository.unlink_reminder(task_id, schedule_id)

    def create_deadline_reminder(
        self, task_id: UUID, action_id: UUID, command_id: UUID
    ) -> ReminderLink:
        """Explicitly create one notification-only reminder for a task deadline."""

        task = self._require_task(task_id)
        if task.due_at_utc is None:
            raise ReminderLinkError("Set a task deadline before creating a reminder.")
        if self.scheduling_service is None:
            raise ReminderLinkError("Scheduling is unavailable.")
        existing = self.repository.reminder_links(task_id)
        if any(link.link_type is ReminderLinkType.DEADLINE for link in existing):
            raise ReminderLinkError("That task already has a deadline reminder.")
        result = self.scheduling_service.create(
            action_id,
            command_id,
            ScheduleType.REMINDER,
            f"Task deadline: {task.title}",
            "A linked task deadline is due.",
            task.due_at_utc,
            timezone_name=self.scheduling_service.configuration.timezone,
        )
        if not result.success:
            raise ReminderLinkError(result.user_message)
        raw_schedule_id = (
            result.data.get("schedule_id") if isinstance(result.data, dict) else None
        )
        if not isinstance(raw_schedule_id, str):
            raise ReminderLinkError("The reminder link could not be created.")
        schedule_id = UUID(raw_schedule_id)
        try:
            return self.repository.link_reminder(
                ReminderLink(task_id, schedule_id, ReminderLinkType.DEADLINE)
            )
        except Exception:
            self.scheduling_service.mutate(
                action_id,
                command_id,
                schedule_id,
                "cancel",
            )
            raise

    def linked_reminders(self, task_id: UUID) -> tuple[dict[str, object], ...]:
        links = self.repository.reminder_links(task_id)
        values: list[dict[str, object]] = []
        for link in links:
            schedule = (
                self.schedule_repository.get(link.schedule_id)
                if self.schedule_repository
                else None
            )
            values.append(
                {
                    "schedule_id": link.schedule_id,
                    "link_type": link.link_type,
                    "status": schedule.status if schedule else None,
                }
            )
        return tuple(values)

    def _require_note(self, note_id: UUID) -> Note:
        item = self.repository.get_note(note_id)
        if item is None:
            raise ProductivityNotFoundError("That note was not found.")
        return item

    def _require_task(self, task_id: UUID) -> Task:
        item = self.repository.get_task(task_id)
        if item is None:
            raise ProductivityNotFoundError("That task was not found.")
        return item

    def _note_text(self, title: str, body: str) -> None:
        if not title.strip() and not body.strip():
            raise ProductivityConflictError("A note needs a title or body.")
        if len(title) > self.configuration.maximum_note_title_characters:
            raise ProductivityConflictError("The note title is too long.")
        if len(body) > self.configuration.maximum_note_body_characters:
            raise ProductivityConflictError("The note body is too long.")

    def _task_text(self, title: str, description: str) -> None:
        if not title.strip():
            raise ProductivityConflictError("A task title is required.")
        if len(title) > self.configuration.maximum_task_title_characters:
            raise ProductivityConflictError("The task title is too long.")
        if len(description) > self.configuration.maximum_task_description_characters:
            raise ProductivityConflictError("The task description is too long.")

    def _tags(self, values: Sequence[str]) -> tuple[str, ...]:
        if len(values) > self.configuration.maximum_tags_per_item:
            raise ProductivityConflictError("Too many tags were supplied.")
        tags = tuple(normalize_tag(value) for value in values)
        if any(
            len(value) > self.configuration.maximum_tag_characters for value in tags
        ):
            raise ProductivityConflictError("A tag is too long.")
        if len({item.casefold() for item in tags}) != len(tags):
            raise ProductivityConflictError("Duplicate tags are not allowed.")
        return tags

    def _enabled(self) -> None:
        if not self.configuration.enabled:
            raise ProductivityConflictError("Productivity features are disabled.")

    def _now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ProductivityConflictError("The productivity clock must be aware.")
        return value.astimezone(UTC)
