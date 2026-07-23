from pathlib import Path
from uuid import uuid4

from omega.database import (
    ActionRepository,
    CommandRepository,
    DatabaseConfiguration,
    DatabaseConnectionFactory,
    ExecutionPersistence,
    MigrationRunner,
)
from omega.models import (
    Action,
    ActionResult,
    ConfirmationStatus,
    IntentType,
    PermissionDecision,
    RiskLevel,
    UserCommand,
)
from omega.safety import SafeExecutionGateway, SafetyContext


def _context():
    command = UserCommand(
        "Read notes.txt",
        normalized_text="read notes.txt",
        intent=IntentType.READ_FILE,
        session_id=uuid4(),
    )
    action = Action(
        command.command_id,
        IntentType.READ_FILE,
        risk_level=RiskLevel.LOW,
        permission_decision=PermissionDecision.ALLOW,
        confirmation_status=ConfirmationStatus.NOT_REQUIRED,
        requires_confirmation=False,
    )
    return (
        command,
        action,
        SafetyContext(
            command, action, command.session_id, logical_source="Desktop/notes.txt"
        ),
    )


def test_gateway_persists_command_action_and_result_once(tmp_path: Path) -> None:
    factory = DatabaseConnectionFactory(
        DatabaseConfiguration(), database_path=tmp_path / "omega.db"
    )
    MigrationRunner(factory).migrate()
    commands = CommandRepository(factory)
    actions = ActionRepository(factory)
    gateway = SafeExecutionGateway(persistence=ExecutionPersistence(commands, actions))
    command, action, context = _context()
    calls = []

    dispatched = gateway.submit(
        context,
        lambda: calls.append("read")
        or ActionResult.success_result(action.action_id, "read", "Read."),
    )

    assert dispatched.result.success and calls == ["read"]
    assert commands.get(command.command_id) == command
    assert actions.get(action.action_id).status.value == "succeeded"  # type: ignore[union-attr]
    assert actions.get_result(action.action_id) == dispatched.result


def test_pre_execution_persistence_failure_blocks_executor() -> None:
    class FailingPersistence:
        def record_proposal(self, command, action):
            return None

        def update_action(self, action):
            raise RuntimeError("database unavailable")

    _, action, context = _context()
    calls = []
    result = SafeExecutionGateway(
        persistence=FailingPersistence()  # type: ignore[arg-type]
    ).submit(
        context,
        lambda: calls.append("executed")
        or ActionResult.success_result(action.action_id, "done", "Done."),
    )

    assert not result.result.success
    assert result.result.error.code == "PERSISTENCE_FAILED_CLOSED"  # type: ignore[union-attr]
    assert calls == []


def test_post_execution_failure_is_surfaced_without_retry() -> None:
    class FailingPersistence:
        def record_proposal(self, command, action):
            return None

        def update_action(self, action):
            return None

        def record_terminal(self, action, result):
            raise RuntimeError("disk full")

    _, action, context = _context()
    calls = []
    gateway = SafeExecutionGateway(
        persistence=FailingPersistence()  # type: ignore[arg-type]
    )

    first = gateway.submit(
        context,
        lambda: calls.append("executed")
        or ActionResult.success_result(action.action_id, "done", "Done."),
    )
    second = gateway.submit(
        context,
        lambda: calls.append("repeated")
        or ActionResult.success_result(action.action_id, "done", "Done."),
    )

    assert first.result.error.code == "RESULT_PERSISTENCE_FAILED"  # type: ignore[union-attr]
    assert not second.result.success
    assert calls == ["executed"]
