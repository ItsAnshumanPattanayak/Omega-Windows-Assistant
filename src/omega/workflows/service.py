"""Application-facing workflow lifecycle and safe JSON import/export."""

import json
from dataclasses import replace
from datetime import UTC, datetime

from omega.core.exceptions import SecurityValidationError
from omega.security import JsonSecurityLimits, load_bounded_json
from omega.workflows.configuration import WorkflowConfiguration
from omega.workflows.exceptions import WorkflowImportError, WorkflowValidationError
from omega.workflows.execution import WorkflowExecutor
from omega.workflows.models import (
    WorkflowDefinition,
    WorkflowRun,
    WorkflowRunSummary,
    WorkflowStatus,
    WorkflowStep,
)
from omega.workflows.repository import WorkflowRepository, WorkflowRunRepository
from omega.workflows.validation import WorkflowPlanner, WorkflowValidator


class WorkflowService:
    def __init__(
        self,
        configuration: WorkflowConfiguration,
        repository: WorkflowRepository,
        runs: WorkflowRunRepository,
        validator: WorkflowValidator,
        planner: WorkflowPlanner,
        executor: WorkflowExecutor,
    ) -> None:
        self.configuration, self.repository, self.runs = configuration, repository, runs
        self.validator, self.planner, self.executor = validator, planner, executor
        self._selection: str | None = None
        self._draft: WorkflowDefinition | None = None

    def create_draft(self, name: str) -> WorkflowDefinition:
        self._draft = WorkflowDefinition(name, ())
        return self._draft

    def draft(self) -> WorkflowDefinition:
        if self._draft is None:
            raise WorkflowValidationError("Create or import a workflow draft first.")
        return self._draft

    def replace_draft(self, workflow: WorkflowDefinition) -> None:
        self._draft = workflow

    def add_step(self, step: WorkflowStep) -> WorkflowDefinition:
        draft = self.draft()
        self._draft = replace(
            draft,
            steps=(*draft.steps, step),
            version=draft.version + 1,
            updated_at=datetime.now(UTC),
        )
        return self._draft

    def remove_step(self, number: int) -> WorkflowDefinition:
        draft = self.draft()
        if isinstance(number, bool) or not 1 <= number <= len(draft.steps):
            raise WorkflowValidationError("Workflow step number is invalid.")
        steps = list(draft.steps)
        steps.pop(number - 1)
        self._draft = replace(
            draft,
            steps=tuple(steps),
            version=draft.version + 1,
            updated_at=datetime.now(UTC),
        )
        return self._draft

    def move_step(self, source: int, destination: int) -> WorkflowDefinition:
        draft = self.draft()
        if any(
            isinstance(value, bool) or not 1 <= value <= len(draft.steps)
            for value in (source, destination)
        ):
            raise WorkflowValidationError("Workflow step position is invalid.")
        steps = list(draft.steps)
        step = steps.pop(source - 1)
        steps.insert(destination - 1, step)
        self._draft = replace(
            draft,
            steps=tuple(steps),
            version=draft.version + 1,
            updated_at=datetime.now(UTC),
        )
        return self._draft

    def save(self, workflow: WorkflowDefinition) -> WorkflowDefinition:
        existing = self.repository.list(self.configuration.maximum_workflows)
        is_update = any(item.workflow_id == workflow.workflow_id for item in existing)
        if len(existing) >= self.configuration.maximum_workflows and not is_update:
            raise WorkflowValidationError("Workflow limit reached.")
        result = self.validator.validate(workflow)
        if not result.valid:
            raise WorkflowValidationError("; ".join(result.errors))
        saved = self.repository.save(workflow)
        self._selection = str(saved.workflow_id)
        return saved

    def list(self) -> tuple[WorkflowDefinition, ...]:
        items = self.repository.list(self.configuration.maximum_history_results)
        self._selection = None
        return items

    def select(self, reference: str) -> WorkflowDefinition:
        item = self.repository.get(reference)
        self._selection = str(item.workflow_id)
        return item

    def selected(self) -> WorkflowDefinition:
        if self._selection is None:
            raise WorkflowValidationError("Select a workflow first.")
        return self.repository.get(self._selection)

    def run(self, workflow: WorkflowDefinition) -> WorkflowRun:
        if workflow.status is not WorkflowStatus.ACTIVE:
            raise WorkflowValidationError("Only an enabled reviewed workflow can run.")
        result = self.executor.execute(workflow)
        self.runs.save(workflow.name, result)
        return result

    def history(self) -> tuple[WorkflowRunSummary, ...]:
        return self.runs.list(self.configuration.maximum_history_results)

    def import_json(self, payload: bytes) -> WorkflowDefinition:
        if len(payload) > self.configuration.maximum_serialized_definition_bytes:
            raise WorkflowImportError("Workflow import exceeds the size limit.")
        try:
            value = load_bounded_json(
                payload,
                JsonSecurityLimits(
                    self.configuration.maximum_serialized_definition_bytes,
                    maximum_depth=self.configuration.maximum_condition_depth + 8,
                    maximum_items=self.configuration.maximum_steps_per_workflow * 50,
                ),
            )
        except SecurityValidationError as error:
            raise WorkflowImportError("Workflow import is not valid JSON.") from error
        if (
            not isinstance(value, dict)
            or value.get("schema_version") != 1
            or not isinstance(value.get("workflow"), dict)
        ):
            raise WorkflowImportError("Workflow import schema is unsupported.")
        workflow_value = value["workflow"]
        assert isinstance(workflow_value, dict)
        workflow = WorkflowDefinition.from_dict(workflow_value)
        return replace(workflow, status=WorkflowStatus.DISABLED)

    def export_json(self, workflow: WorkflowDefinition) -> bytes:
        safe = workflow.to_dict()
        steps = safe.get("steps")
        for step in steps if isinstance(steps, list) else []:
            if isinstance(step, dict) and isinstance(step.get("arguments"), dict):
                arguments = step["arguments"]
                assert isinstance(arguments, dict)
                step["arguments"] = {
                    key: (
                        "[redacted]"
                        if any(
                            word in key.casefold()
                            for word in (
                                "password",
                                "token",
                                "secret",
                                "body",
                                "clipboard",
                            )
                        )
                        else value
                    )
                    for key, value in arguments.items()
                }
        return json.dumps(
            {"schema_version": 1, "workflow": safe}, sort_keys=True
        ).encode()

    def clear_session(self) -> None:
        self._selection = None
        self._draft = None
