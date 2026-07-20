from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from omega.core.exceptions import DatabaseError
from omega.database import (
    CommandRepository,
    DatabaseConfiguration,
    DatabaseConnectionFactory,
    MigrationRunner,
)
from omega.models import (
    CommandEntity,
    CommandSource,
    EntityType,
    IntentType,
    UserCommand,
)


def _factory(
    tmp_path: Path,
) -> DatabaseConnectionFactory:
    return DatabaseConnectionFactory(
        DatabaseConfiguration(),
        database_path=tmp_path / "omega.db",
    )


def _repository(
    tmp_path: Path,
) -> CommandRepository:
    factory = _factory(tmp_path)
    MigrationRunner(factory).migrate()
    return CommandRepository(factory)


def _command(
    *,
    text: str = "Open Chrome",
    session_id: UUID | None = None,
    received_at: datetime | None = None,
) -> UserCommand:
    return UserCommand(
        original_text=text,
        normalized_text=text.casefold(),
        intent=IntentType.OPEN_APPLICATION,
        entities=[
            CommandEntity(
                entity_type=EntityType.APPLICATION,
                value="chrome",
                confidence=0.98,
            )
        ],
        confidence=0.95,
        received_at=received_at or datetime.now(UTC),
        source=CommandSource.TEXT,
        session_id=session_id,
        metadata={
            "parser": "rule_based",
            "attempt": 1,
        },
    )


def test_repository_round_trip_preserves_command(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    command = _command(session_id=uuid4())

    repository.add(command)

    restored = repository.get(command.command_id)

    assert restored is not None
    assert restored.to_dict() == command.to_dict()
    assert repository.count() == 1


def test_repository_returns_none_for_unknown_command(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)

    assert repository.get(uuid4()) is None


def test_repository_rejects_duplicate_command_id(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    command = _command()

    repository.add(command)

    with pytest.raises(
        DatabaseError,
        match="already present",
    ):
        repository.add(command)

    assert repository.count() == 1


def test_recent_commands_are_returned_newest_first(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    start = datetime(
        2026,
        7,
        20,
        10,
        0,
        tzinfo=UTC,
    )

    first = _command(
        text="Open Chrome",
        received_at=start,
    )
    second = _command(
        text="Open Notepad",
        received_at=start + timedelta(seconds=1),
    )
    third = _command(
        text="Open Calculator",
        received_at=start + timedelta(seconds=2),
    )

    repository.add(first)
    repository.add(second)
    repository.add(third)

    recent = repository.list_recent(limit=2)

    assert [command.command_id for command in recent] == [
        third.command_id,
        second.command_id,
    ]


def test_session_query_returns_only_matching_commands(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    selected_session = uuid4()
    other_session = uuid4()

    first = _command(
        text="Open Chrome",
        session_id=selected_session,
    )
    second = _command(
        text="Open Notepad",
        session_id=selected_session,
        received_at=first.received_at + timedelta(seconds=1),
    )
    unrelated = _command(
        text="Open Calculator",
        session_id=other_session,
    )

    repository.add(first)
    repository.add(second)
    repository.add(unrelated)

    commands = repository.list_for_session(selected_session)

    assert [command.command_id for command in commands] == [
        first.command_id,
        second.command_id,
    ]


@pytest.mark.parametrize(
    "limit",
    [
        0,
        -1,
        1_001,
        True,
        1.5,
    ],
)
def test_invalid_history_limits_are_rejected(
    tmp_path: Path,
    limit: object,
) -> None:
    repository = _repository(tmp_path)

    with pytest.raises(
        ValueError,
        match="between 1 and 1000",
    ):
        repository.list_recent(
            limit=limit,  # type: ignore[arg-type]
        )


def test_repository_does_not_create_schema_implicitly(
    tmp_path: Path,
) -> None:
    factory = _factory(tmp_path)
    repository = CommandRepository(factory)

    with pytest.raises(DatabaseError):
        repository.add(_command())
