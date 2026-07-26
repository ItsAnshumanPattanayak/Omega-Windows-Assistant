"""Sequential bounded executor over explicitly injected handlers."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from threading import Event, RLock
from time import monotonic
from typing import Protocol

from omega.models._serialization import JsonValue, validate_json_value
from omega.workflows.configuration import WorkflowConfiguration
from omega.workflows.exceptions import WorkflowStateError, WorkflowValidationError
from omega.workflows.models import (
    FailurePolicy,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowRunStatus,
    WorkflowStep,
    WorkflowStepResult,
    WorkflowStepType,
)
from omega.workflows.validation import WorkflowValidator
from omega.workflows.variables import evaluate, substitute


class WorkflowStepHandler(Protocol):
    def __call__(
        self, step: WorkflowStep, context: Mapping[str, JsonValue]
    ) -> JsonValue: ...


class WorkflowEventSink(Protocol):
    def workflow_updated(self, run: WorkflowRun) -> None: ...


class WorkflowCancellationToken:
    def __init__(self) -> None:
        self._cancelled = Event()
        self._paused = Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def pause(self) -> None:
        self._paused.set()

    def resume(self) -> None:
        self._paused.clear()

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    @property
    def paused(self) -> bool:
        return self._paused.is_set()


class WorkflowExecutor:
    def __init__(
        self,
        configuration: WorkflowConfiguration,
        validator: WorkflowValidator,
        handlers: Mapping[WorkflowStepType, WorkflowStepHandler],
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self.configuration, self.validator, self.handlers, self.clock = (
            configuration,
            validator,
            dict(handlers),
            clock,
        )
        self._active: dict[str, tuple[WorkflowRun, WorkflowCancellationToken]] = {}
        self._lock = RLock()

    def execute(
        self,
        workflow: WorkflowDefinition,
        inputs: Mapping[str, JsonValue] | None = None,
        token: WorkflowCancellationToken | None = None,
    ) -> WorkflowRun:
        validation = self.validator.validate(workflow)
        if not validation.valid:
            raise WorkflowValidationError("; ".join(validation.errors))
        token = token or WorkflowCancellationToken()
        run = WorkflowRun(
            workflow.workflow_id,
            workflow.version,
            status=WorkflowRunStatus.RUNNING,
            started_at=datetime.now(UTC),
        )
        with self._lock:
            if (
                len(self._active) >= self.configuration.maximum_concurrent_runs
                or str(workflow.workflow_id) in self._active
            ):
                raise WorkflowStateError("A workflow run is already active.")
            self._active[str(workflow.workflow_id)] = (run, token)
        values: dict[str, JsonValue] = {
            f"input.{key}": validate_json_value(value, "workflow input")
            for key, value in (inputs or {}).items()
        }
        started = self.clock()
        try:
            positions = {
                step.step_id: index for index, step in enumerate(workflow.steps)
            }
            index = 0
            while index < len(workflow.steps):
                step = workflow.steps[index]
                run.current_step = index
                if token.cancelled:
                    run.status = WorkflowRunStatus.CANCELLED
                    break
                if token.paused:
                    run.status = WorkflowRunStatus.PAUSED
                    return run
                if (
                    self.clock() - started
                    > self.configuration.maximum_execution_seconds
                ):
                    run.status = WorkflowRunStatus.TIMED_OUT
                    break
                condition_result = (
                    evaluate(
                        step.condition,
                        values,
                        self.configuration.maximum_variable_characters,
                    )
                    if step.condition is not None
                    else True
                )
                if step.if_true is not None and step.if_false is not None:
                    run.results.append(
                        WorkflowStepResult(
                            step.step_id,
                            True,
                            {
                                "branch": (
                                    step.if_true if condition_result else step.if_false
                                )
                            },
                        )
                    )
                    index = positions[
                        step.if_true if condition_result else step.if_false
                    ]
                    continue
                if step.condition is not None and not condition_result:
                    run.results.append(
                        WorkflowStepResult(step.step_id, True, {"skipped": True})
                    )
                    index += 1
                    continue
                rendered = {
                    key: substitute(
                        value, values, self.configuration.maximum_variable_characters
                    )
                    for key, value in step.arguments.items()
                }
                safe_step = WorkflowStep(
                    step.step_id,
                    step.step_type,
                    rendered,
                    step.description,
                    step.timeout_seconds,
                    step.retries,
                    step.condition,
                    step.if_true,
                    step.if_false,
                )
                handler = self.handlers.get(step.step_type)
                if handler is None:
                    outcome = WorkflowStepResult(
                        step.step_id, False, error_code="UNSUPPORTED_STEP"
                    )
                else:
                    try:
                        step_started = self.clock()
                        output = validate_json_value(
                            handler(safe_step, values), "step output"
                        )
                        elapsed = self.clock() - step_started
                        step_limit = (
                            step.timeout_seconds
                            or self.configuration.maximum_step_seconds
                        )
                        if elapsed > step_limit:
                            outcome = WorkflowStepResult(
                                step.step_id, False, error_code="STEP_TIMEOUT"
                            )
                        else:
                            outcome = WorkflowStepResult(step.step_id, True, output)
                            values[f"steps.{step.step_id}.output"] = output
                            values[f"steps.{step.step_id}.succeeded"] = True
                    except Exception:
                        outcome = WorkflowStepResult(
                            step.step_id, False, error_code="STEP_FAILED"
                        )
                run.results.append(outcome)
                if (
                    not outcome.success
                    and workflow.failure_policy is FailurePolicy.STOP
                ):
                    run.status = WorkflowRunStatus.FAILED
                    run.safe_error_code = outcome.error_code
                    break
                index += 1
            else:
                run.status = WorkflowRunStatus.SUCCEEDED
            if run.status is not WorkflowRunStatus.PAUSED:
                run.completed_at = datetime.now(UTC)
            return run
        finally:
            if run.status is not WorkflowRunStatus.PAUSED:
                with self._lock:
                    self._active.pop(str(workflow.workflow_id), None)

    def cancel(self, workflow_id: str) -> None:
        with self._lock:
            item = self._active.get(workflow_id)
            if item is None:
                raise WorkflowStateError("No active workflow run is selected.")
            item[1].cancel()

    def pause(self, workflow_id: str) -> None:
        with self._lock:
            item = self._active.get(workflow_id)
            if item is None:
                raise WorkflowStateError("No active workflow run is selected.")
            item[1].pause()

    def resume(self, workflow: WorkflowDefinition) -> WorkflowRun:
        """Resume only the not-yet-started suffix of a matching paused version."""
        key = str(workflow.workflow_id)
        with self._lock:
            item = self._active.get(key)
            if item is None or item[0].status is not WorkflowRunStatus.PAUSED:
                raise WorkflowStateError("No paused workflow run is selected.")
            paused, token = item
            if paused.workflow_version != workflow.version:
                raise WorkflowStateError("The paused workflow version is stale.")
            token.resume()
            self._active.pop(key)
        remaining = replace(workflow, steps=workflow.steps[paused.current_step :])
        resumed = self.execute(remaining, token=token)
        resumed.results = paused.results + resumed.results
        return resumed
