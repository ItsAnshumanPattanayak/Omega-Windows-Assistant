from pathlib import Path
from uuid import uuid4

from omega.database import (
    ActionRepository,
    CommandRepository,
    DatabaseConfiguration,
    DatabaseConnectionFactory,
    ExecutionPersistence,
    MigrationRunner,
    SqliteRecoveryRecordStore,
)
from omega.execution import HistoryActionDispatcher
from omega.history import HistoryService
from omega.safety import SafeExecutionGateway
from omega.understanding import CommandParser


def _dispatcher(tmp_path: Path):
    factory = DatabaseConnectionFactory(
        DatabaseConfiguration(), database_path=tmp_path / "omega.db"
    )
    MigrationRunner(factory).migrate()
    commands = CommandRepository(factory)
    actions = ActionRepository(factory)
    gateway = SafeExecutionGateway(persistence=ExecutionPersistence(commands, actions))
    history = HistoryService(
        factory,
        commands,
        actions,
        SqliteRecoveryRecordStore(factory, 20),
        export_root=tmp_path / "exports",
    )
    return HistoryActionDispatcher(history, gateway), gateway, commands


def test_show_export_and_clear_history_use_gateway(tmp_path: Path) -> None:
    dispatcher, gateway, commands = _dispatcher(tmp_path)
    parser = CommandParser()
    session_id = uuid4()

    shown = dispatcher.dispatch(parser.parse("show recent commands", session_id))
    exported = dispatcher.dispatch(parser.parse("export history", session_id))
    pending = dispatcher.dispatch(parser.parse("clear history", session_id))
    confirmed = gateway.handle_confirmation("confirm clear history", session_id)

    assert shown is not None and "show recent commands" in shown
    assert exported is not None and "exported" in exported
    assert pending is not None and "confirm clear history" in pending
    assert confirmed is not None and confirmed.result.success
    assert commands.count() >= 2


def test_undo_command_is_handled_without_unsafe_restore(tmp_path: Path) -> None:
    dispatcher, gateway, _ = _dispatcher(tmp_path)
    session_id = uuid4()
    pending = dispatcher.dispatch(CommandParser().parse("undo last action", session_id))
    result = gateway.handle_confirmation("confirm undo last action", session_id)

    assert pending is not None and "confirm undo last action" in pending
    assert result is not None and not result.result.success
    assert "no action" in result.user_message.casefold()
