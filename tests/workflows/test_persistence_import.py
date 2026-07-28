import json
from pathlib import Path

import pytest

from omega.database import (
    DatabaseConfiguration,
    DatabaseConnectionFactory,
    MigrationRunner,
)
from omega.workflows import (
    FakeWorkflowHandlers,
    WorkflowConfiguration,
    WorkflowDefinition,
    WorkflowExecutor,
    WorkflowPlanner,
    WorkflowRepository,
    WorkflowRunRepository,
    WorkflowService,
    WorkflowStatus,
    WorkflowStep,
    WorkflowStepType,
    WorkflowValidator,
)
from omega.workflows.exceptions import WorkflowImportError, WorkflowValidationError


def service(tmp_path: Path) -> tuple[WorkflowService, DatabaseConnectionFactory]:
    factory = DatabaseConnectionFactory(
        DatabaseConfiguration(), database_path=tmp_path / "omega.db"
    )
    assert MigrationRunner(factory).migrate() == 14
    config = WorkflowConfiguration()
    validator = WorkflowValidator(config)
    repository = WorkflowRepository(factory)
    runs = WorkflowRunRepository(factory)
    executor = WorkflowExecutor(config, validator, FakeWorkflowHandlers().registry())
    return (
        WorkflowService(
            config, repository, runs, validator, WorkflowPlanner(validator), executor
        ),
        factory,
    )


def sample(status: WorkflowStatus = WorkflowStatus.ACTIVE) -> WorkflowDefinition:
    return WorkflowDefinition(
        "Persisted Workflow",
        (WorkflowStep("one", WorkflowStepType.ASSIGN, {"result": 1}),),
        status=status,
    )


def test_migration_and_definition_round_trip(tmp_path: Path) -> None:
    value, factory = service(tmp_path)
    stored = value.save(sample())
    assert value.select(str(stored.workflow_id)) == stored
    connection = factory.connect()
    try:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {
            "workflow_definitions",
            "workflow_versions",
            "workflow_runs",
            "workflow_step_runs",
        } <= tables
    finally:
        connection.close()


def test_run_history_persists_only_safe_summary(tmp_path: Path) -> None:
    value, factory = service(tmp_path)
    item = value.save(sample())
    run = value.run(item)
    connection = factory.connect()
    try:
        row = connection.execute(
            "SELECT workflow_name,status,safe_error_code FROM workflow_runs "
            "WHERE run_id=?",
            (str(run.run_id),),
        ).fetchone()
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(workflow_runs)")
        }
    finally:
        connection.close()
    assert tuple(row) == (item.name, "succeeded", None)
    assert not {"clipboard_content", "email_body", "token"} & columns
    assert value.history()[0].workflow_name == item.name


def test_import_is_disabled_and_does_not_execute(tmp_path: Path) -> None:
    value, _ = service(tmp_path)
    payload = json.dumps({"schema_version": 1, "workflow": sample().to_dict()}).encode()
    imported = value.import_json(payload)
    assert imported.status is WorkflowStatus.DISABLED


@pytest.mark.parametrize(
    "payload",
    [
        b"not json",
        b'{"schema_version":99}',
        b'{"schema_version":1,"workflow":{"steps":[{"step_type":"shell"}]}}',
    ],
)
def test_import_rejects_invalid_or_executable_content(
    tmp_path: Path, payload: bytes
) -> None:
    value, _ = service(tmp_path)
    with pytest.raises((WorkflowImportError, WorkflowValidationError)):
        value.import_json(payload)


def test_export_redacts_sensitive_arguments(tmp_path: Path) -> None:
    value, _ = service(tmp_path)
    item = WorkflowDefinition(
        "Export",
        (
            WorkflowStep(
                "draft",
                WorkflowStepType.CREATE_EMAIL_DRAFT,
                {"body": "private", "token": "secret"},
            ),
        ),
    )
    payload = value.export_json(item)
    assert b"private" not in payload and b"secret" not in payload
