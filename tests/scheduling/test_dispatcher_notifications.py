import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from omega.database import (
    DatabaseConfiguration,
    DatabaseConnectionFactory,
    MigrationRunner,
)
from omega.execution import SchedulingActionDispatcher
from omega.interfaces.terminal import TerminalInterface
from omega.models import CommandSource, IntentType
from omega.safety import SafeExecutionGateway
from omega.scheduling import (
    NotificationCenter,
    RecurrenceFrequency,
    ScheduledItem,
    ScheduleRepository,
    ScheduleType,
    SchedulingConfiguration,
    SchedulingService,
)
from omega.session import OmegaSession
from omega.understanding.parser import CommandParser


def dispatcher(
    path: Path,
    now: datetime,
) -> tuple[SchedulingActionDispatcher, ScheduleRepository]:
    factory = DatabaseConnectionFactory(
        DatabaseConfiguration(),
        database_path=path / "omega.db",
    )
    MigrationRunner(factory).migrate()
    repository = ScheduleRepository(factory)
    service = SchedulingService(
        SchedulingConfiguration(timezone="UTC"),
        repository,
        lambda: now,
    )
    return (
        SchedulingActionDispatcher(
            service,
            SafeExecutionGateway(),
            lambda: now,
        ),
        repository,
    )


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("Remind me tomorrow at 7 PM", IntentType.CREATE_REMINDER),
        (
            "Remind me every Monday at 10 AM",
            IntentType.CREATE_RECURRING_REMINDER,
        ),
        ("Set an alarm every weekday at 7 AM", IntentType.CREATE_RECURRING_ALARM),
        ("Show the reminder", IntentType.SHOW_REMINDER),
        ("Update the reminder to 8 PM", IntentType.UPDATE_REMINDER),
        ("Cancel the reminder", IntentType.CANCEL_REMINDER),
        ("Complete the reminder", IntentType.COMPLETE_REMINDER),
        ("Dismiss the alarm", IntentType.DISMISS_ALARM),
    ],
)
def test_scheduling_parser_uses_existing_understanding_layer(
    text: str,
    intent: IntentType,
) -> None:
    parsed = CommandParser().parse(text)
    assert parsed.command.intent is intent


def test_dispatcher_creates_recurring_reminder_through_gateway(tmp_path: Path) -> None:
    now = datetime(2026, 1, 5, 8, tzinfo=UTC)
    value, repository = dispatcher(tmp_path, now)
    parsed = CommandParser().parse(
        "Remind me every Monday at 10 AM",
        uuid4(),
        source=CommandSource.VOICE,
    )
    result = value.dispatch(parsed)
    assert result is not None and result.result.success
    stored = repository.list_items(schedule_type=ScheduleType.REMINDER)[0]
    assert stored.recurrence is not None
    assert stored.recurrence.frequency is RecurrenceFrequency.WEEKDAYS
    assert stored.recurrence.weekdays == (0,)


def test_dispatcher_mutation_is_revision_scoped(tmp_path: Path) -> None:
    now = datetime(2026, 1, 1, 8, tzinfo=UTC)
    value, repository = dispatcher(tmp_path, now)
    created = value.dispatch(CommandParser().parse("Remind me in 30 minutes", uuid4()))
    assert created is not None and created.result.success
    cancelled = value.dispatch(CommandParser().parse("Cancel the reminder", uuid4()))
    assert cancelled is not None and cancelled.result.success
    assert cancelled.action.parameters["revision"] == 1
    assert repository.list_items(schedule_type=ScheduleType.REMINDER) == ()


def test_notification_center_is_bounded_and_terminal_consumes_it() -> None:
    center = NotificationCenter(logging.getLogger("test"), maximum_pending=2)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    for title in ("one", "two", "three"):
        center.notify(
            ScheduledItem(
                ScheduleType.REMINDER,
                title,
                title,
                now,
                "UTC",
                created_at=now,
                updated_at=now,
            )
        )
    output: list[str] = []

    def eof(_prompt: str) -> str:
        raise EOFError

    terminal = TerminalInterface(
        OmegaSession(
            {"display_name": "Tester"},
            {
                "activation_phrase": "Hello Omega",
                "shutdown_phrase": "Shut down Omega",
                "active_session_timeout_seconds": 300,
            },
        ),
        notifications=center,
        input_func=eof,
        output_func=output.append,
    )
    assert terminal.run() == 0
    combined = "\n".join(output)
    assert "one" not in combined
    assert "two" in combined
    assert "three" in combined
