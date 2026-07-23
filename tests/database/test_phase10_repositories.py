from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from omega.core.exceptions import RecoveryRecordError, SettingsRepositoryError
from omega.database import (
    ActionRepository,
    CommandRepository,
    DatabaseConfiguration,
    DatabaseConnectionFactory,
    MigrationRunner,
    RuntimeSettingsRepository,
    SqliteRecoveryRecordStore,
)
from omega.models import (
    Action,
    ActionStatus,
    CommandSource,
    ConfirmationStatus,
    IntentType,
    PermissionDecision,
    RiskLevel,
    UserCommand,
)
from omega.recovery import (
    RecoverableActionType,
    RecoveryRecord,
    RecoveryRecordStatus,
    RecoveryResourceType,
    RecycleBinItem,
)


def _setup(tmp_path: Path):
    factory = DatabaseConnectionFactory(
        DatabaseConfiguration(), database_path=tmp_path / "omega.db"
    )
    MigrationRunner(factory).migrate()
    commands = CommandRepository(factory)
    actions = ActionRepository(factory)
    command = UserCommand(
        "Delete notes.txt",
        normalized_text="delete notes.txt",
        intent=IntentType.DELETE_FILE,
        source=CommandSource.TEXT,
    )
    action = Action(
        command.command_id,
        IntentType.DELETE_FILE,
        status=ActionStatus.APPROVED,
        risk_level=RiskLevel.HIGH,
        permission_decision=PermissionDecision.ALLOW,
        confirmation_status=ConfirmationStatus.NOT_REQUIRED,
        requires_confirmation=False,
    )
    commands.add(command)
    actions.add(action)
    return factory, command, action


def _record(command: UserCommand, action: Action) -> RecoveryRecord:
    now = datetime.now(UTC)
    return RecoveryRecord(
        RecoverableActionType.RECYCLE_FILE,
        RecoveryResourceType.FILE,
        command.command_id,
        action.action_id,
        uuid4(),
        RecycleBinItem(
            RecoveryResourceType.FILE,
            "notes.txt",
            "desktop",
            "notes.txt",
            "fingerprint",
            recycle_bin_reference="private-reference",
        ),
        status=RecoveryRecordStatus.COMPLETED,
        created_at=now,
        expires_at=now + timedelta(minutes=5),
    )


def test_recovery_round_trip_update_and_prune(tmp_path: Path) -> None:
    factory, command, action = _setup(tmp_path)
    store = SqliteRecoveryRecordStore(factory, 10)
    record = _record(command, action)

    assert store.add(record) == record
    assert store.get(record.record_id) == record
    expired = RecoveryRecord(
        **{
            **record.__dict__,
            "status": RecoveryRecordStatus.EXPIRED,
            "record_id": uuid4(),
        }
    )
    store.add(expired)
    assert store.prune_inactive(before=datetime.now(UTC) + timedelta(days=1)) == 1
    assert store.list_newest_first() == (record,)


def test_recovery_capacity_preserves_active_records(tmp_path: Path) -> None:
    factory, command, action = _setup(tmp_path)
    store = SqliteRecoveryRecordStore(factory, 1)
    store.add(_record(command, action))
    with pytest.raises(RecoveryRecordError, match="active undo"):
        store.add(
            RecoveryRecord(
                **{
                    **_record(command, action).__dict__,
                    "record_id": uuid4(),
                }
            )
        )


def test_runtime_settings_json_crud_and_reserved_names(tmp_path: Path) -> None:
    factory, _, _ = _setup(tmp_path)
    repository = RuntimeSettingsRepository(factory)
    first = repository.upsert("ui.theme", {"name": "dark"})
    second = repository.upsert("ui.theme", ["light"])
    repository.upsert("assistant.locale", "en")

    assert first.created_at == second.created_at
    assert second.value == ["light"]
    assert [item.name for item in repository.list_all()] == [
        "assistant.locale",
        "ui.theme",
    ]
    assert repository.delete("ui.theme")
    assert repository.get("ui.theme") is None
    assert repository.clear() == 1
    with pytest.raises(SettingsRepositoryError, match="immutable"):
        repository.upsert("safety.default_decision", "allow")
    with pytest.raises(SettingsRepositoryError, match="invalid"):
        repository.upsert("Bad Name", True)


def test_runtime_settings_malformed_json_fails_safely(tmp_path: Path) -> None:
    factory, _, _ = _setup(tmp_path)
    connection = factory.connect()
    try:
        with connection:
            connection.execute(
                """
                INSERT INTO runtime_settings VALUES
                ('ui.theme','not-json',?,?)
                """,
                (datetime.now(UTC).isoformat(), datetime.now(UTC).isoformat()),
            )
    finally:
        connection.close()
    with pytest.raises(SettingsRepositoryError, match="invalid"):
        RuntimeSettingsRepository(factory).get("ui.theme")


def test_phase10_repository_construction_has_no_filesystem_side_effect(
    tmp_path: Path,
) -> None:
    path = tmp_path / "nested" / "omega.db"
    factory = DatabaseConnectionFactory(DatabaseConfiguration(), database_path=path)

    RuntimeSettingsRepository(factory)
    SqliteRecoveryRecordStore(factory, 20)

    assert not path.exists()
    assert not path.parent.exists()
