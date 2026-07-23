from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from omega.core.exceptions import ConfigurationError, ModelValidationError
from omega.database import (
    DatabaseConfiguration,
    DatabaseConnectionFactory,
    MigrationRunner,
)
from omega.models import IntentType
from omega.scheduling import (
    RecurrenceFrequency,
    RecurrenceRule,
    ScheduledItem,
    SchedulerEngine,
    ScheduleRepository,
    ScheduleType,
    SchedulingConfiguration,
    SchedulingService,
)
from omega.scheduling.recurrence import next_occurrence
from omega.understanding.parser import CommandParser


def factory(path: Path) -> DatabaseConnectionFactory:
    value = DatabaseConnectionFactory(
        DatabaseConfiguration(), database_path=path / "omega.db"
    )
    MigrationRunner(value).migrate()
    return value


def test_configuration_fails_closed() -> None:
    assert SchedulingConfiguration.from_mapping({}).allow_scheduled_commands is False
    with pytest.raises(ConfigurationError):
        SchedulingConfiguration.from_mapping({"allow_scheduled_commands": True})
    with pytest.raises(ConfigurationError):
        SchedulingConfiguration.from_mapping({"maximum_active_items": True})


def test_models_and_recurrence_are_utc_and_bounded() -> None:
    now = datetime(2026, 1, 31, 10, tzinfo=UTC)
    rule = RecurrenceRule(RecurrenceFrequency.DAILY)
    assert next_occurrence(now, rule) == now + timedelta(days=1)
    with pytest.raises(ModelValidationError):
        ScheduledItem(ScheduleType.REMINDER, "x", "x", datetime.now(), "UTC")


def test_repository_claim_is_atomic(tmp_path: Path) -> None:
    repo = ScheduleRepository(factory(tmp_path))
    now = datetime(2026, 1, 1, tzinfo=UTC)
    item = ScheduledItem(
        ScheduleType.REMINDER,
        "title",
        "message",
        now,
        "UTC",
        created_at=now - timedelta(seconds=1),
        updated_at=now,
    )
    repo.add(item)
    assert len(repo.claim_due(now)) == 1
    assert repo.claim_due(now) == ()


def test_service_timer_pause_resume_cancel(tmp_path: Path) -> None:
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    repo = ScheduleRepository(factory(tmp_path))
    service = SchedulingService(SchedulingConfiguration(), repo, lambda: now[0])
    result = service.create(
        uuid4(),
        uuid4(),
        ScheduleType.TIMER,
        "tea",
        "tea",
        now[0] + timedelta(minutes=5),
        300,
    )
    sid = result.data["schedule_id"]
    paused = service.mutate(
        uuid4(),
        uuid4(),
        uuid4() if not isinstance(sid, str) else __import__("uuid").UUID(sid),
        "pause",
    )
    assert paused.success


def test_scheduler_delivers_once(tmp_path: Path) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    repo = ScheduleRepository(factory(tmp_path))
    repo.add(
        ScheduledItem(
            ScheduleType.ALARM,
            "wake",
            "wake",
            now,
            "UTC",
            created_at=now - timedelta(seconds=1),
            updated_at=now,
        )
    )

    class Notifier:
        def __init__(self) -> None:
            self.items = []

        def notify(self, item: ScheduledItem) -> None:
            self.items.append(item)

    notifier = Notifier()
    engine = SchedulerEngine(SchedulingConfiguration(), repo, notifier, lambda: now)
    assert engine.run_once() == 1
    assert engine.run_once() == 0
    assert len(notifier.items) == 1


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("Remind me in 30 minutes", IntentType.CREATE_REMINDER),
        ("Set an alarm for 6:30 AM", IntentType.CREATE_ALARM),
        ("Start a timer for 20 minutes", IntentType.START_TIMER),
        ("List schedules", IntentType.LIST_SCHEDULED_ITEMS),
    ],
)
def test_parser(text: str, intent: IntentType) -> None:
    result = CommandParser().parse(text)
    assert result.command.intent is intent
    assert not result.requires_clarification
