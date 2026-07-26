import pytest

from omega.workflows import (
    ConditionOperator,
    FailurePolicy,
    FakeWorkflowHandlers,
    WorkflowCancellationToken,
    WorkflowCondition,
    WorkflowConfiguration,
    WorkflowDefinition,
    WorkflowExecutor,
    WorkflowRunStatus,
    WorkflowStatus,
    WorkflowStep,
    WorkflowStepType,
    WorkflowValidator,
)
from omega.workflows.exceptions import WorkflowStateError


def executor(
    handlers: FakeWorkflowHandlers | None = None, clock=lambda: 0.0
) -> tuple[WorkflowExecutor, FakeWorkflowHandlers]:
    fake = handlers or FakeWorkflowHandlers()
    config = WorkflowConfiguration()
    return (
        WorkflowExecutor(
            config, WorkflowValidator(config), fake.registry(), clock=clock
        ),
        fake,
    )


def workflow(
    *steps: WorkflowStep, policy: FailurePolicy = FailurePolicy.STOP
) -> WorkflowDefinition:
    return WorkflowDefinition(
        "Run Test", steps, status=WorkflowStatus.ACTIVE, failure_policy=policy
    )


def test_sequential_execution_and_variable_substitution() -> None:
    value, fake = executor()
    item = workflow(
        WorkflowStep("first", WorkflowStepType.ASSIGN, {"result": "Omega"}),
        WorkflowStep(
            "second",
            WorkflowStepType.DISPLAY_MESSAGE,
            {"result": "${steps.first.output}"},
        ),
    )
    run = value.execute(item)
    assert run.status is WorkflowRunStatus.SUCCEEDED and fake.calls == [
        "first",
        "second",
    ]
    assert run.results[1].output == "Omega"


def test_stop_on_failure() -> None:
    value, fake = executor()
    run = value.execute(
        workflow(
            WorkflowStep("bad", WorkflowStepType.ASSIGN, {"fail": True}),
            WorkflowStep("later", WorkflowStepType.ASSIGN),
        )
    )
    assert run.status is WorkflowRunStatus.FAILED and fake.calls == ["bad"]


def test_safe_continue_policy() -> None:
    value, fake = executor()
    run = value.execute(
        workflow(
            WorkflowStep("bad", WorkflowStepType.ASSIGN, {"fail": True}),
            WorkflowStep("later", WorkflowStepType.ASSIGN),
            policy=FailurePolicy.CONTINUE_SAFE_READS,
        )
    )
    assert run.status is WorkflowRunStatus.SUCCEEDED and fake.calls == ["bad", "later"]


def test_cancelled_token_performs_no_step() -> None:
    value, fake = executor()
    token = WorkflowCancellationToken()
    token.cancel()
    run = value.execute(
        workflow(WorkflowStep("never", WorkflowStepType.ASSIGN)), token=token
    )
    assert run.status is WorkflowRunStatus.CANCELLED and fake.calls == []


def test_paused_token_performs_no_step() -> None:
    value, fake = executor()
    token = WorkflowCancellationToken()
    token.pause()
    item = workflow(WorkflowStep("later", WorkflowStepType.ASSIGN))
    run = value.execute(item, token=token)
    assert run.status is WorkflowRunStatus.PAUSED and fake.calls == []
    resumed = value.resume(item)
    assert resumed.status is WorkflowRunStatus.SUCCEEDED and fake.calls == ["later"]


def test_timeout() -> None:
    times = iter((0.0, 2000.0))
    value, fake = executor(clock=lambda: next(times))
    run = value.execute(workflow(WorkflowStep("never", WorkflowStepType.ASSIGN)))
    assert run.status is WorkflowRunStatus.TIMED_OUT and fake.calls == []


def test_step_timeout_is_reported_after_a_bounded_handler_call() -> None:
    times = iter((0.0, 0.0, 0.0, 2.0))
    value, _ = executor(clock=lambda: next(times))
    run = value.execute(
        workflow(WorkflowStep("slow", WorkflowStepType.ASSIGN, timeout_seconds=1))
    )
    assert run.status is WorkflowRunStatus.FAILED
    assert run.safe_error_code == "STEP_TIMEOUT"


def test_condition_chooses_one_forward_branch() -> None:
    value, fake = executor()
    run = value.execute(
        workflow(
            WorkflowStep(
                "choose",
                WorkflowStepType.CONDITION,
                condition=WorkflowCondition("no", ConditionOperator.EQUALS, "yes"),
                if_true="selected",
                if_false="other",
            ),
            WorkflowStep("selected", WorkflowStepType.DISPLAY_MESSAGE),
            WorkflowStep("other", WorkflowStepType.DISPLAY_MESSAGE),
        )
    )
    assert run.status is WorkflowRunStatus.SUCCEEDED
    assert fake.calls == ["other"]


def test_duplicate_run_rejected() -> None:
    value, _ = executor()
    item = workflow(WorkflowStep("step", WorkflowStepType.ASSIGN))
    token = WorkflowCancellationToken()
    token.pause()
    value.execute(item, token=token)
    with pytest.raises(WorkflowStateError):
        value.execute(item)


def test_fake_handlers_have_zero_external_side_effects() -> None:
    value, fake = executor()
    value.execute(workflow(WorkflowStep("clipboard", WorkflowStepType.COPY_CLIPBOARD)))
    assert (fake.shell_calls, fake.network_calls, fake.desktop_calls) == (0, 0, 0)
