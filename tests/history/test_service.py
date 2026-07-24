import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from omega.core.exceptions import HistoryCleanupError, HistoryExportError
from omega.database import (
    ActionRepository,
    CommandRepository,
    DatabaseConfiguration,
    DatabaseConnectionFactory,
    MigrationRunner,
    SqliteRecoveryRecordStore,
)
from omega.history import HistoryService
from omega.models import (
    Action,
    ActionResult,
    ActionStatus,
    CommandSource,
    ConfirmationStatus,
    IntentType,
    PermissionDecision,
    RiskLevel,
    UserCommand,
)


def _service(tmp_path: Path):
    factory = DatabaseConnectionFactory(
        DatabaseConfiguration(), database_path=tmp_path / "omega.db"
    )
    MigrationRunner(factory).migrate()
    commands = CommandRepository(factory)
    actions = ActionRepository(factory)
    recovery = SqliteRecoveryRecordStore(factory, 20)
    service = HistoryService(
        factory, commands, actions, recovery, export_root=tmp_path / "exports"
    )
    return service, commands, actions, factory


def _activity(commands, actions, text="Open Chrome"):
    command = UserCommand(
        text,
        normalized_text=text.casefold(),
        intent=IntentType.OPEN_APPLICATION,
        source=CommandSource.TEXT,
    )
    action = Action(
        command.command_id,
        IntentType.OPEN_APPLICATION,
        status=ActionStatus.APPROVED,
        risk_level=RiskLevel.LOW,
        permission_decision=PermissionDecision.ALLOW,
        confirmation_status=ConfirmationStatus.NOT_REQUIRED,
        requires_confirmation=False,
    )
    commands.add(command)
    actions.add(action)
    return command, action


def test_recent_history_results_limits_and_retry(tmp_path: Path) -> None:
    service, commands, actions, _ = _service(tmp_path)
    command, action = _activity(commands, actions)
    result = ActionResult.success_result(action.action_id, "opened", "Opened.")
    actions.save_result(result)

    assert service.recent_commands() == (command,)
    assert service.recent_actions() == (action,)
    assert service.actions_for_command(command.command_id) == (action,)
    assert service.result_for_action(action.action_id) == result
    assert not service.retry_eligibility(action.action_id).eligible
    with pytest.raises(ValueError):
        service.recent_commands(True)
    with pytest.raises(ValueError):
        service.recent_actions(101)


def test_cleanup_preserves_migrations_settings_and_files(tmp_path: Path) -> None:
    service, commands, actions, factory = _service(tmp_path)
    _activity(commands, actions)
    marker = tmp_path / "user-file.txt"
    marker.write_text("keep", encoding="utf-8")

    summary = service.cleanup(before=datetime.now(UTC) + timedelta(seconds=1))

    assert summary.commands == 1 and summary.actions == 1
    assert marker.read_text(encoding="utf-8") == "keep"
    connection = factory.connect()
    try:
        assert (
            connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
            == 8
        )
    finally:
        connection.close()


def test_export_is_utf8_bounded_deterministic_shape_and_no_overwrite(
    tmp_path: Path,
) -> None:
    service, commands, actions, _ = _service(tmp_path)
    _activity(commands, actions, "Open Café token=private-value")
    payload = service.serialize_json()
    assert '"export_version":1' in payload
    assert "Café" in payload
    assert "private-value" not in payload

    exported = service.export_json()
    exported_payload = json.loads(exported.path.read_text(encoding="utf-8"))
    assert exported_payload["export_version"] == 1
    assert "[REDACTED]" in exported_payload["commands"][0]["original_text"]
    with pytest.raises(HistoryExportError, match="already exists"):
        service.export_json()
    with pytest.raises(HistoryExportError):
        service.export_json("../unsafe.json")


def test_cleanup_error_when_active_undo_would_be_invalidated(tmp_path: Path) -> None:
    service, _, _, _ = _service(tmp_path)
    service.active_undo_records = lambda: (object(),)  # type: ignore[method-assign,return-value]
    with pytest.raises(HistoryCleanupError, match="Active undo"):
        service.cleanup()
