from pathlib import Path
from uuid import uuid4

from omega.database import (
    DatabaseConfiguration,
    DatabaseConnectionFactory,
    MigrationRunner,
)
from omega.execution import WorkflowDispatcher
from omega.safety import SafeExecutionGateway
from omega.understanding import CommandParser
from omega.workflows import (
    FakeWorkflowHandlers,
    WorkflowConfiguration,
    WorkflowDefinition,
    WorkflowExecutor,
    WorkflowPlanner,
    WorkflowRepository,
    WorkflowRunRepository,
    WorkflowService,
    WorkflowStep,
    WorkflowStepType,
    WorkflowValidator,
)


def components(
    tmp_path: Path,
) -> tuple[WorkflowDispatcher, WorkflowService, SafeExecutionGateway]:
    factory = DatabaseConnectionFactory(
        DatabaseConfiguration(), database_path=tmp_path / "omega.db"
    )
    MigrationRunner(factory).migrate()
    config = WorkflowConfiguration()
    validator = WorkflowValidator(config)
    service = WorkflowService(
        config,
        WorkflowRepository(factory),
        WorkflowRunRepository(factory),
        validator,
        WorkflowPlanner(validator),
        WorkflowExecutor(config, validator, FakeWorkflowHandlers().registry()),
    )
    gateway = SafeExecutionGateway()
    return WorkflowDispatcher(service, gateway), service, gateway


def test_create_draft_is_redacted_and_does_not_execute(tmp_path: Path) -> None:
    dispatcher, service, _ = components(tmp_path)
    result = dispatcher.dispatch(
        CommandParser().parse("create workflow named Morning Setup", uuid4())
    )
    assert result is not None and result.result.success
    assert service.draft().name == "Morning Setup"
    assert "Morning Setup" not in result.command.original_text


def test_structured_step_editing_is_allowlisted(tmp_path: Path) -> None:
    dispatcher, service, _ = components(tmp_path)
    dispatcher.dispatch(CommandParser().parse("create workflow named Edited", uuid4()))
    added = dispatcher.dispatch(
        CommandParser().parse("add step: display message Hello", uuid4())
    )
    assert added is not None and added.result.success
    assert service.draft().steps[0].step_type is WorkflowStepType.DISPLAY_MESSAGE
    rejected = dispatcher.dispatch(
        CommandParser().parse("add step: execute powershell dir", uuid4())
    )
    assert rejected is not None and not rejected.result.success


def test_save_requires_exact_confirmation(tmp_path: Path) -> None:
    dispatcher, service, gateway = components(tmp_path)
    session_id = uuid4()
    draft = service.create_draft("Reviewed")
    service.replace_draft(
        WorkflowDefinition(
            draft.name,
            (WorkflowStep("show", WorkflowStepType.DISPLAY_MESSAGE),),
            workflow_id=draft.workflow_id,
        )
    )
    proposal = dispatcher.dispatch(
        CommandParser().parse("save this workflow", session_id)
    )
    assert proposal is not None and not proposal.result.success and service.list() == ()
    confirmed = gateway.handle_confirmation(
        f"confirm save workflow {draft.workflow_id}", session_id
    )
    assert (
        confirmed is not None and confirmed.result.success and len(service.list()) == 1
    )


def test_edit_invalidates_save_confirmation(tmp_path: Path) -> None:
    dispatcher, service, gateway = components(tmp_path)
    session_id = uuid4()
    draft = service.create_draft("Changing")
    service.replace_draft(
        WorkflowDefinition(
            draft.name,
            (WorkflowStep("one", WorkflowStepType.ASSIGN),),
            workflow_id=draft.workflow_id,
        )
    )
    dispatcher.dispatch(CommandParser().parse("save workflow", session_id))
    service.replace_draft(
        WorkflowDefinition(
            draft.name,
            (WorkflowStep("changed", WorkflowStepType.ASSIGN),),
            workflow_id=draft.workflow_id,
        )
    )
    result = gateway.handle_confirmation(
        f"confirm save workflow {draft.workflow_id}", session_id
    )
    assert result is not None and not result.result.success and service.list() == ()


def test_unrelated_command_not_claimed(tmp_path: Path) -> None:
    dispatcher, _, _ = components(tmp_path)
    assert dispatcher.dispatch(CommandParser().parse("open chrome")) is None
