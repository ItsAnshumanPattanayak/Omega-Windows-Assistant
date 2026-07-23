from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from omega.core.exceptions import ModelValidationError
from omega.productivity import (
    Note,
    ProductivityConfiguration,
    ReminderLink,
    Tag,
    Task,
    TaskList,
    TaskPriority,
    TaskStatus,
)
from omega.productivity.exceptions import ProductivityConfigurationError


def test_configuration_is_strict_and_defaults_are_safe() -> None:
    values = ProductivityConfiguration.from_mapping({})
    assert values.enabled
    assert not values.allow_markdown_import
    assert not values.automatically_create_deadline_reminders
    with pytest.raises(ProductivityConfigurationError):
        ProductivityConfiguration.from_mapping({"maximum_notes": True})
    with pytest.raises(ProductivityConfigurationError):
        ProductivityConfiguration.from_mapping({"unknown": 1})
    with pytest.raises(ProductivityConfigurationError):
        ProductivityConfiguration.from_mapping({"allow_markdown_import": True})


def test_note_and_task_models_validate_lifecycle_and_utc() -> None:
    note = Note("Ideas", "Use SQLite")
    assert note.to_dict()["body"] == "Use SQLite"
    with pytest.raises(ModelValidationError):
        Note("", "")
    task_list = TaskList("Work")
    task = Task(task_list.task_list_id, "Write tests", priority=TaskPriority.HIGH)
    assert task.status is TaskStatus.PENDING
    with pytest.raises(ModelValidationError):
        replace(task, due_at_utc=datetime.now())
    with pytest.raises(ModelValidationError):
        replace(task, status=TaskStatus.COMPLETED)
    completed = replace(
        task, status=TaskStatus.COMPLETED, completed_at=datetime.now(UTC)
    )
    assert completed.to_dict()["status"] == "completed"


def test_tag_and_reminder_link_are_data_only() -> None:
    assert Tag("  Project   Omega ").normalized_name == "project omega"
    with pytest.raises(ModelValidationError):
        Tag("\x00bad")
    link = ReminderLink(uuid4(), uuid4())
    assert link.created_at.tzinfo is UTC
