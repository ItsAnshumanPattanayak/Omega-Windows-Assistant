"""Transactional minimal workflow definition and redacted run persistence."""

import json
import sqlite3
from datetime import UTC
from uuid import UUID

from omega.database import DatabaseConnectionFactory
from omega.workflows.exceptions import WorkflowNotFoundError, WorkflowPersistenceError
from omega.workflows.models import (
    WorkflowDefinition,
    WorkflowRun,
    WorkflowRunStatus,
    WorkflowRunSummary,
)


class WorkflowRepository:
    def __init__(self, factory: DatabaseConnectionFactory) -> None:
        self.factory = factory

    def save(self, workflow: WorkflowDefinition) -> WorkflowDefinition:
        payload = json.dumps(workflow.to_dict(), sort_keys=True, separators=(",", ":"))
        connection = self.factory.connect()
        try:
            connection.execute(
                """INSERT INTO workflow_definitions(
                workflow_id,name,status,version,definition_json,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?) ON CONFLICT(workflow_id) DO UPDATE SET
                name=excluded.name,status=excluded.status,version=excluded.version,
                definition_json=excluded.definition_json,updated_at=excluded.updated_at""",
                (
                    str(workflow.workflow_id),
                    workflow.name,
                    workflow.status.value,
                    workflow.version,
                    payload,
                    workflow.created_at.astimezone(UTC).isoformat(),
                    workflow.updated_at.astimezone(UTC).isoformat(),
                ),
            )
            connection.execute(
                "INSERT OR IGNORE INTO workflow_versions("
                "workflow_id,version,definition_json,created_at) VALUES(?,?,?,?)",
                (
                    str(workflow.workflow_id),
                    workflow.version,
                    payload,
                    workflow.updated_at.astimezone(UTC).isoformat(),
                ),
            )
            connection.commit()
            return workflow
        except sqlite3.Error as error:
            connection.rollback()
            raise WorkflowPersistenceError("Workflow could not be stored.") from error
        finally:
            connection.close()

    def get(self, reference: str) -> WorkflowDefinition:
        connection = self.factory.connect()
        try:
            row = connection.execute(
                "SELECT definition_json FROM workflow_definitions "
                "WHERE workflow_id=? OR name=? COLLATE NOCASE",
                (reference, reference),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise WorkflowNotFoundError("Workflow was not found.")
        return WorkflowDefinition.from_dict(json.loads(str(row[0])))

    def list(self, limit: int = 50) -> tuple[WorkflowDefinition, ...]:
        connection = self.factory.connect()
        try:
            rows = connection.execute(
                "SELECT definition_json FROM workflow_definitions "
                "ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        finally:
            connection.close()
        return tuple(
            WorkflowDefinition.from_dict(json.loads(str(row[0]))) for row in rows
        )

    def delete(self, workflow_id: UUID) -> None:
        connection = self.factory.connect()
        try:
            connection.execute(
                "DELETE FROM workflow_definitions WHERE workflow_id=?",
                (str(workflow_id),),
            )
            connection.commit()
        except sqlite3.Error as error:
            connection.rollback()
            raise WorkflowPersistenceError("Workflow could not be deleted.") from error
        finally:
            connection.close()


class WorkflowRunRepository:
    def __init__(self, factory: DatabaseConnectionFactory) -> None:
        self.factory = factory

    def save(self, workflow_name: str, run: WorkflowRun) -> None:
        connection = self.factory.connect()
        try:
            connection.execute(
                """INSERT OR REPLACE INTO workflow_runs(
                run_id,workflow_id,workflow_version,workflow_name,status,current_step,
                completed_steps,safe_error_code,started_at,completed_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    str(run.run_id),
                    str(run.workflow_id),
                    run.workflow_version,
                    workflow_name,
                    run.status.value,
                    run.current_step,
                    len([item for item in run.results if item.success]),
                    run.safe_error_code,
                    (
                        run.started_at.astimezone(UTC).isoformat()
                        if run.started_at
                        else None
                    ),
                    (
                        run.completed_at.astimezone(UTC).isoformat()
                        if run.completed_at
                        else None
                    ),
                ),
            )
            for sequence, result in enumerate(run.results):
                connection.execute(
                    "INSERT OR REPLACE INTO workflow_step_runs("
                    "run_id,step_id,sequence_number,success,safe_error_code) "
                    "VALUES(?,?,?,?,?)",
                    (
                        str(run.run_id),
                        result.step_id,
                        sequence,
                        int(result.success),
                        result.error_code,
                    ),
                )
            connection.commit()
        except sqlite3.Error as error:
            connection.rollback()
            raise WorkflowPersistenceError(
                "Workflow run could not be stored."
            ) from error
        finally:
            connection.close()

    def list(self, limit: int = 50) -> tuple[WorkflowRunSummary, ...]:
        if isinstance(limit, bool) or not 1 <= limit <= 500:
            raise WorkflowPersistenceError("Workflow history limit is invalid.")
        connection = self.factory.connect()
        try:
            rows = connection.execute(
                "SELECT run_id,workflow_id,workflow_name,status,current_step,"
                "completed_steps,safe_error_code,started_at,completed_at "
                "FROM workflow_runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        except sqlite3.Error as error:
            raise WorkflowPersistenceError(
                "Workflow history could not be read."
            ) from error
        finally:
            connection.close()
        from datetime import datetime

        return tuple(
            WorkflowRunSummary(
                UUID(str(row[0])),
                UUID(str(row[1])),
                str(row[2]),
                WorkflowRunStatus(str(row[3])),
                int(row[5]),
                int(row[4]) if row[6] else None,
                str(row[6]) if row[6] else None,
                datetime.fromisoformat(str(row[7])) if row[7] else None,
                datetime.fromisoformat(str(row[8])) if row[8] else None,
            )
            for row in rows
        )
