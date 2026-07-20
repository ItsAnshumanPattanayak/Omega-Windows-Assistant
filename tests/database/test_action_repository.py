from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from omega.core.exceptions import DatabaseError
from omega.database import (
    ActionRepository,
    CommandRepository,
    DatabaseConfiguration,
    DatabaseConnectionFactory,
    MigrationRunner,
)
from omega.models import (
    Action,
    ActionResult,
    ActionStatus,
    CommandSource,
    ConfirmationStatus,
    ErrorCategory,
    IntentType,
    OmegaErrorDetails,
    PermissionDecision,
    RiskLevel,
    UserCommand,
)


def _factory(
    tmp_path: Path,
) -> DatabaseConnectionFactory:
    return DatabaseConnectionFactory(
        DatabaseConfiguration(),
        database_path=tmp_path / "omega.db",
    )


def _repositories(
    tmp_path: Path,
) -> tuple[
    CommandRepository,
    ActionRepository,
]:
    factory = _factory(tmp_path)
    MigrationRunner(factory).migrate()

    return (
        CommandRepository(factory),
        ActionRepository(factory),
    )


def _command(
    *,
    text: str = "Open Chrome",
) -> UserCommand:
    return UserCommand(
        original_text=text,
        normalized_text=text.casefold(),
        intent=IntentType.OPEN_APPLICATION,
        confidence=0.95,
        source=CommandSource.TEXT,
    )


def _action(
    command_id,
    *,
    created_at: datetime | None = None,
) -> Action:
    return Action(
        command_id=command_id,
        intent=IntentType.OPEN_APPLICATION,
        parameters={
            "application": "chrome",
        },
        risk_level=RiskLevel.LOW,
        status=ActionStatus.APPROVED,
        permission_decision=PermissionDecision.ALLOW,
        confirmation_status=ConfirmationStatus.NOT_REQUIRED,
        requires_confirmation=False,
        created_at=created_at or datetime.now(UTC),
        metadata={
            "dispatcher": "application",
        },
    )


def test_action_round_trip_preserves_data(
    tmp_path: Path,
) -> None:
    command_repository, action_repository = _repositories(tmp_path)
    command = _command()
    command_repository.add(command)

    action = _action(command.command_id)
    action_repository.add(action)

    restored = action_repository.get(action.action_id)

    assert restored is not None
    assert restored.to_dict() == action.to_dict()
    assert action_repository.count() == 1


def test_action_requires_existing_command(
    tmp_path: Path,
) -> None:
    _, action_repository = _repositories(tmp_path)

    with pytest.raises(
        DatabaseError,
        match="command is unavailable",
    ):
        action_repository.add(_action(uuid4()))


def test_duplicate_action_is_rejected(
    tmp_path: Path,
) -> None:
    command_repository, action_repository = _repositories(tmp_path)
    command = _command()
    command_repository.add(command)

    action = _action(command.command_id)
    action_repository.add(action)

    with pytest.raises(
        DatabaseError,
        match="already exists",
    ):
        action_repository.add(action)


def test_action_can_be_updated(
    tmp_path: Path,
) -> None:
    command_repository, action_repository = _repositories(tmp_path)
    command = _command()
    command_repository.add(command)

    action = _action(command.command_id)
    action_repository.add(action)

    started_at = datetime.now(UTC)

    updated = Action(
        action_id=action.action_id,
        command_id=action.command_id,
        intent=action.intent,
        parameters=action.parameters,
        risk_level=action.risk_level,
        status=ActionStatus.RUNNING,
        permission_decision=action.permission_decision,
        confirmation_status=action.confirmation_status,
        requires_confirmation=action.requires_confirmation,
        dependencies=action.dependencies,
        created_at=action.created_at,
        started_at=started_at,
        metadata={
            "dispatcher": "application",
            "attempt": 1,
        },
    )

    action_repository.update(updated)

    restored = action_repository.get(action.action_id)

    assert restored is not None
    assert restored.to_dict() == updated.to_dict()


def test_updating_unknown_action_is_rejected(
    tmp_path: Path,
) -> None:
    command_repository, action_repository = _repositories(tmp_path)
    command = _command()
    command_repository.add(command)

    with pytest.raises(
        DatabaseError,
        match="does not exist",
    ):
        action_repository.update(_action(command.command_id))


def test_actions_are_listed_for_command(
    tmp_path: Path,
) -> None:
    command_repository, action_repository = _repositories(tmp_path)
    command = _command()
    other_command = _command(text="Open Notepad")
    command_repository.add(command)
    command_repository.add(other_command)

    start = datetime(
        2026,
        7,
        20,
        10,
        0,
        tzinfo=UTC,
    )

    first = _action(
        command.command_id,
        created_at=start,
    )
    second = _action(
        command.command_id,
        created_at=start + timedelta(seconds=1),
    )
    unrelated = _action(
        other_command.command_id,
        created_at=start,
    )

    action_repository.add(first)
    action_repository.add(second)
    action_repository.add(unrelated)

    stored = action_repository.list_for_command(command.command_id)

    assert [item.action_id for item in stored] == [
        first.action_id,
        second.action_id,
    ]


def test_recent_actions_are_newest_first(
    tmp_path: Path,
) -> None:
    command_repository, action_repository = _repositories(tmp_path)
    command = _command()
    command_repository.add(command)

    start = datetime(
        2026,
        7,
        20,
        10,
        0,
        tzinfo=UTC,
    )

    first = _action(
        command.command_id,
        created_at=start,
    )
    second = _action(
        command.command_id,
        created_at=start + timedelta(seconds=1),
    )

    action_repository.add(first)
    action_repository.add(second)

    recent = action_repository.list_recent(limit=1)

    assert [item.action_id for item in recent] == [second.action_id]


def test_success_result_round_trip(
    tmp_path: Path,
) -> None:
    command_repository, action_repository = _repositories(tmp_path)
    command = _command()
    command_repository.add(command)

    action = _action(command.command_id)
    action_repository.add(action)

    result = ActionResult.success_result(
        action.action_id,
        "Application opened.",
        "Chrome was opened successfully.",
        data={
            "application": "chrome",
            "process_id": 1234,
        },
        metadata={
            "service": "application_launcher",
        },
    )

    action_repository.save_result(result)

    restored = action_repository.get_result(action.action_id)

    assert restored is not None
    assert restored.to_dict() == result.to_dict()


def test_failure_result_round_trip(
    tmp_path: Path,
) -> None:
    command_repository, action_repository = _repositories(tmp_path)
    command = _command()
    command_repository.add(command)

    action = _action(command.command_id)
    action_repository.add(action)

    error = OmegaErrorDetails(
        code="APPLICATION_NOT_FOUND",
        category=ErrorCategory.NOT_FOUND,
        message="The registered application was unavailable.",
        user_message="Chrome could not be found.",
        recoverable=True,
        details={
            "application": "chrome",
        },
        action_id=action.action_id,
        command_id=command.command_id,
    )

    result = ActionResult.failure_result(
        action.action_id,
        "Application launch failed.",
        "Chrome could not be opened.",
        error,
    )

    action_repository.save_result(result)

    restored = action_repository.get_result(action.action_id)

    assert restored is not None
    assert restored.to_dict() == result.to_dict()


def test_duplicate_result_is_rejected(
    tmp_path: Path,
) -> None:
    command_repository, action_repository = _repositories(tmp_path)
    command = _command()
    command_repository.add(command)

    action = _action(command.command_id)
    action_repository.add(action)

    result = ActionResult.success_result(
        action.action_id,
        "Completed.",
        "The action completed.",
    )

    action_repository.save_result(result)

    with pytest.raises(
        DatabaseError,
        match="already exists",
    ):
        action_repository.save_result(result)


def test_result_requires_existing_action(
    tmp_path: Path,
) -> None:
    _, action_repository = _repositories(tmp_path)

    result = ActionResult.success_result(
        uuid4(),
        "Completed.",
        "The action completed.",
    )

    with pytest.raises(
        DatabaseError,
        match="action is unavailable",
    ):
        action_repository.save_result(result)


def test_unknown_action_and_result_return_none(
    tmp_path: Path,
) -> None:
    _, action_repository = _repositories(tmp_path)
    unknown_id = uuid4()

    assert action_repository.get(unknown_id) is None
    assert action_repository.get_result(unknown_id) is None


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
def test_invalid_action_limits_are_rejected(
    tmp_path: Path,
    limit: object,
) -> None:
    _, action_repository = _repositories(tmp_path)

    with pytest.raises(
        ValueError,
        match="between 1 and 1000",
    ):
        action_repository.list_recent(
            limit=limit,  # type: ignore[arg-type]
        )
