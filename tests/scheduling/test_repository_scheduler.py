from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from omega.core.exceptions import DatabaseError
from omega.database import (
    DatabaseConfiguration,
    DatabaseConnectionFactory,
    MigrationRunner,
)
from omega.scheduling import (
    DeliveryStatus,
    RecurrenceFrequency,
    RecurrenceRule,
    ScheduledItem,
    SchedulerEngine,
    ScheduleRepository,
    ScheduleStatus,
    ScheduleType,
    SchedulingConfiguration,
    SchedulingService,
)


def factory(path: Path) -> DatabaseConnectionFactory:
    value = DatabaseConnectionFactory(
        DatabaseConfiguration(),
        database_path=path / "omega.db",
    )
    MigrationRunner(value).migrate()
    return value


def item(
    due: datetime,
    *,
    kind: ScheduleType = ScheduleType.REMINDER,
    recurrence: RecurrenceRule | None = None,
) -> ScheduledItem:
    return ScheduledItem(
        kind,
        kind.value,
        kind.value,
        due,
        "UTC",
        recurrence=recurrence,
        created_at=due - timedelta(seconds=1),
        updated_at=due - timedelta(seconds=1),
    )


def test_two_repositories_cannot_claim_the_same_occurrence(tmp_path: Path) -> None:
    database = factory(tmp_path)
    first = ScheduleRepository(database)
    second = ScheduleRepository(database)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    first.add(item(now))
    claims = first.claim_due(now)
    assert len(claims) == 1
    assert second.claim_due(now) == ()
    assert (
        second.delivery_status(claims[0].item.schedule_id, now)
        is DeliveryStatus.CLAIMED
    )


def test_recurring_claim_finalizes_the_original_occurrence(tmp_path: Path) -> None:
    repo = ScheduleRepository(factory(tmp_path))
    now = datetime(2026, 1, 1, tzinfo=UTC)
    scheduled = item(
        now,
        recurrence=RecurrenceRule(
            RecurrenceFrequency.DAILY,
            maximum_occurrences=3,
        ),
    )
    repo.add(scheduled)
    claim = repo.claim_due(now)[0]
    next_due = now + timedelta(days=1)
    assert repo.finalize_claim(
        claim,
        now,
        DeliveryStatus.DELIVERED,
        next_due=next_due,
        occurrence_count=1,
    )
    assert repo.delivery_status(scheduled.schedule_id, now) is DeliveryStatus.DELIVERED
    stored = repo.get(scheduled.schedule_id)
    assert stored is not None
    assert stored.due_at_utc == next_due
    assert stored.status is ScheduleStatus.PENDING


def test_stale_claim_is_missed_and_never_replayed(tmp_path: Path) -> None:
    repo = ScheduleRepository(factory(tmp_path))
    now = datetime(2026, 1, 1, tzinfo=UTC)
    scheduled = item(now)
    repo.add(scheduled)
    assert repo.claim_due(now)
    assert (
        repo.recover_stale_claims(
            now + timedelta(seconds=31),
            timeout_seconds=30,
            limit=10,
        )
        == 1
    )
    assert repo.claim_due(now + timedelta(minutes=1)) == ()
    stored = repo.get(scheduled.schedule_id)
    assert stored is not None
    assert stored.status is ScheduleStatus.MISSED


def test_optimistic_revision_rejects_stale_update(tmp_path: Path) -> None:
    repo = ScheduleRepository(factory(tmp_path))
    now = datetime(2026, 1, 1, tzinfo=UTC)
    scheduled = item(now)
    repo.add(scheduled)
    scheduled.title = "changed"
    scheduled.revision += 1
    repo.update(scheduled, 1)
    with pytest.raises(DatabaseError, match="revision conflict"):
        repo.update(scheduled, 1)


def test_notification_failure_is_recorded_without_retry(tmp_path: Path) -> None:
    repo = ScheduleRepository(factory(tmp_path))
    now = datetime(2026, 1, 1, tzinfo=UTC)
    scheduled = item(now, kind=ScheduleType.ALARM)
    repo.add(scheduled)

    class FailingNotifier:
        def notify(self, value: ScheduledItem) -> None:
            raise RuntimeError("speaker unavailable")

    engine = SchedulerEngine(
        SchedulingConfiguration(),
        repo,
        FailingNotifier(),
        lambda: now,
    )
    assert engine.run_once() == 0
    assert engine.run_once() == 0
    assert repo.delivery_status(scheduled.schedule_id, now) is DeliveryStatus.FAILED


def test_overdue_recurring_item_skips_missed_occurrences(tmp_path: Path) -> None:
    repo = ScheduleRepository(factory(tmp_path))
    due = datetime(2026, 1, 1, tzinfo=UTC)
    now = due + timedelta(days=4)
    scheduled = item(
        due,
        recurrence=RecurrenceRule(
            RecurrenceFrequency.DAILY,
            maximum_occurrences=10,
        ),
    )
    repo.add(scheduled)

    class Notifier:
        def notify(self, value: ScheduledItem) -> None:
            raise AssertionError("overdue item must not be delivered")

    engine = SchedulerEngine(
        SchedulingConfiguration(maximum_overdue_age_seconds=1),
        repo,
        Notifier(),
        lambda: now,
    )
    assert engine.run_once() == 0
    stored = repo.get(scheduled.schedule_id)
    assert stored is not None
    assert stored.due_at_utc == now + timedelta(days=1)
    assert stored.occurrence_count == 5


def test_timer_full_pause_resume_cancel_lifecycle(tmp_path: Path) -> None:
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    repo = ScheduleRepository(factory(tmp_path))
    service = SchedulingService(
        SchedulingConfiguration(),
        repo,
        lambda: now[0],
    )
    created = service.create(
        uuid4(),
        uuid4(),
        ScheduleType.TIMER,
        "cooking",
        "cooking",
        now[0] + timedelta(minutes=5),
        300,
    )
    schedule_id = created.data["schedule_id"]
    assert isinstance(schedule_id, str)
    identifier = __import__("uuid").UUID(schedule_id)
    assert service.mutate(uuid4(), uuid4(), identifier, "pause").success
    paused = repo.get(identifier)
    assert paused is not None and paused.remaining_seconds == 300
    now[0] += timedelta(minutes=1)
    assert service.mutate(uuid4(), uuid4(), identifier, "resume").success
    assert service.mutate(uuid4(), uuid4(), identifier, "cancel").success
    assert not service.mutate(uuid4(), uuid4(), identifier, "resume").success


def test_reminder_snooze_and_alarm_dismiss_lifecycle(tmp_path: Path) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    repo = ScheduleRepository(factory(tmp_path))
    service = SchedulingService(SchedulingConfiguration(), repo, lambda: now)
    reminder = service.create(
        uuid4(),
        uuid4(),
        ScheduleType.REMINDER,
        "medicine",
        "medicine",
        now + timedelta(hours=1),
    )
    alarm = service.create(
        uuid4(),
        uuid4(),
        ScheduleType.ALARM,
        "wake",
        "wake",
        now + timedelta(hours=2),
    )
    reminder_id = reminder.data["schedule_id"]
    alarm_id = alarm.data["schedule_id"]
    assert isinstance(reminder_id, str) and isinstance(alarm_id, str)
    reminder_uuid = __import__("uuid").UUID(reminder_id)
    alarm_uuid = __import__("uuid").UUID(alarm_id)
    assert service.mutate(uuid4(), uuid4(), reminder_uuid, "snooze", 15).success
    snoozed = repo.get(reminder_uuid)
    assert snoozed is not None
    assert snoozed.status is ScheduleStatus.SNOOZED
    assert snoozed.due_at_utc == now + timedelta(minutes=15)
    assert service.mutate(uuid4(), uuid4(), alarm_uuid, "dismiss").success
    dismissed = repo.get(alarm_uuid)
    assert dismissed is not None
    assert dismissed.status is ScheduleStatus.COMPLETED


def test_scheduler_start_stop_and_disabled_state(tmp_path: Path) -> None:
    repo = ScheduleRepository(factory(tmp_path))

    class Notifier:
        def notify(self, value: ScheduledItem) -> None:
            pass

    disabled = SchedulerEngine(
        SchedulingConfiguration(enabled=False),
        repo,
        Notifier(),
    )
    disabled.start()
    assert not disabled.running
    enabled = SchedulerEngine(
        SchedulingConfiguration(scheduler_poll_interval_seconds=60),
        repo,
        Notifier(),
    )
    enabled.start()
    assert enabled.running
    enabled.stop()
    assert not enabled.running
