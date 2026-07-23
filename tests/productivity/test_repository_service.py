from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from omega.productivity import (
    ProductivitySearchQuery,
    TaskPriority,
    TaskStatus,
)
from omega.productivity.exceptions import (
    ProductivityConflictError,
    StaleProductivityRevisionError,
)
from omega.productivity.repositories import ProductivityRepository
from omega.productivity.service import ProductivityService
from omega.scheduling import (
    ScheduledItem,
    ScheduleRepository,
    ScheduleType,
    SchedulingConfiguration,
    SchedulingService,
)


def test_note_crud_search_archive_tags_and_revision(
    productivity: tuple[ProductivityService, ProductivityRepository],
) -> None:
    service, repository = productivity
    note = service.create_note("Project Ideas", "Use SQLite", tags=("Omega",))
    assert repository.get_note(note.note_id).tags == ("Omega",)  # type: ignore[union-attr]
    assert repository.list_notes(query="SQLite")[0].note_id == note.note_id
    assert repository.list_notes(tag="omega")[0].note_id == note.note_id
    updated = service.update_note(
        note.note_id, note.revision, append="\nAdd tests", pinned=True
    )
    assert updated.is_pinned and updated.revision == 2
    with pytest.raises(StaleProductivityRevisionError):
        service.update_note(note.note_id, note.revision, title="Stale")
    archived = service.update_note(note.note_id, updated.revision, archived=True)
    assert archived.archived_at is not None
    restored = service.update_note(note.note_id, archived.revision, archived=False)
    service.delete_note(restored.note_id, restored.revision)
    assert repository.get_note(note.note_id) is None


def test_task_lists_tasks_lifecycle_filters_and_move(
    productivity: tuple[ProductivityService, ProductivityRepository],
) -> None:
    service, repository = productivity
    work = service.create_task_list("Work")
    personal = service.create_task_list("Personal")
    due = datetime.now(UTC) - timedelta(minutes=1)
    task = service.create_task(
        "Finish documentation",
        task_list_id=work.task_list_id,
        priority=TaskPriority.HIGH,
        due_at_utc=due,
        tags=("Omega",),
    )
    assert (
        repository.list_tasks(overdue_at=datetime.now(UTC))[0].task_id == task.task_id
    )
    completed = service.transition_task(
        task.task_id, task.revision, TaskStatus.COMPLETED
    )
    assert completed.completed_at is not None
    reopened = service.transition_task(
        task.task_id, completed.revision, TaskStatus.PENDING
    )
    moved = service.update_task(
        task.task_id,
        reopened.revision,
        task_list_id=personal.task_list_id,
        due_at_utc=None,
    )
    assert moved.task_list_id == personal.task_list_id
    with pytest.raises(ProductivityConflictError):
        service.delete_task_list(personal.task_list_id, personal.revision)
    service.delete_task(moved.task_id, moved.revision)
    service.delete_task_list(personal.task_list_id, personal.revision)


def test_independent_repositories_and_sql_injection_is_data(
    productivity: tuple[ProductivityService, ProductivityRepository],
) -> None:
    service, repository = productivity
    service.create_note("SQL", "'; DROP TABLE notes; --")
    assert repository.list_notes(query="DROP TABLE")
    assert repository.list_notes(query="%' OR 1=1 --") == ()


def test_cross_item_search_is_bounded_and_deterministic(
    productivity: tuple[ProductivityService, ProductivityRepository],
) -> None:
    service, _repository = productivity
    service.create_note("Omega design", "Local first")
    task_list = service.create_task_list("Omega Work", "Project tasks")
    service.create_task("Document Omega", task_list_id=task_list.task_list_id)
    result = service.search(ProductivitySearchQuery("Omega", limit=10))
    assert len(result["notes"]) == 1
    assert len(result["tasks"]) == 1
    assert len(result["task_lists"]) == 1


def test_task_links_only_to_existing_non_cancelled_reminders(
    productivity: tuple[ProductivityService, ProductivityRepository],
) -> None:
    service, repository = productivity
    schedule_repository = ScheduleRepository(repository.factory)
    service.schedule_repository = schedule_repository
    task = service.create_task("Prepare report")
    reminder = ScheduledItem(
        ScheduleType.REMINDER,
        "Prepare report",
        "Notification only",
        datetime.now(UTC) + timedelta(hours=1),
        "UTC",
    )
    schedule_repository.add(reminder)
    link = service.link_reminder(task.task_id, reminder.schedule_id)
    assert link.schedule_id == reminder.schedule_id
    assert service.linked_reminders(task.task_id)[0]["status"].value == "pending"
    assert service.unlink_reminder(task.task_id, reminder.schedule_id)


def test_explicit_deadline_reminder_reuses_phase15_service(
    productivity: tuple[ProductivityService, ProductivityRepository],
) -> None:
    service, repository = productivity
    schedules = ScheduleRepository(repository.factory)
    service.schedule_repository = schedules
    service.scheduling_service = SchedulingService(SchedulingConfiguration(), schedules)
    task = service.create_task(
        "Submit report", due_at_utc=datetime.now(UTC) + timedelta(hours=2)
    )
    link = service.create_deadline_reminder(task.task_id, uuid4(), uuid4())
    scheduled = schedules.get(link.schedule_id)
    assert scheduled is not None
    assert scheduled.message == "A linked task deadline is due."
    assert scheduled.metadata.get("scheduled_command") is None
