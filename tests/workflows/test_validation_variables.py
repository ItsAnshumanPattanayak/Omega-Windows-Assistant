import pytest

from omega.workflows import (
    ConditionOperator,
    WorkflowCondition,
    WorkflowConfiguration,
    WorkflowDefinition,
    WorkflowPlanner,
    WorkflowStep,
    WorkflowStepType,
    WorkflowValidator,
)
from omega.workflows.exceptions import WorkflowValidationError
from omega.workflows.variables import evaluate, substitute


def validator(**kwargs: object) -> WorkflowValidator:
    return WorkflowValidator(WorkflowConfiguration.from_mapping(kwargs))


def test_empty_and_excessive_workflows_invalid() -> None:
    assert not validator().validate(WorkflowDefinition("Empty", ())).valid
    steps = tuple(WorkflowStep(f"s{i}", WorkflowStepType.ASSIGN) for i in range(3))
    assert (
        not validator(maximum_steps_per_workflow=2)
        .validate(WorkflowDefinition("Large", steps))
        .valid
    )


def test_missing_branch_target_invalid() -> None:
    step = WorkflowStep("choose", WorkflowStepType.CONDITION, if_true="missing")
    assert not validator().validate(WorkflowDefinition("Branch", (step,))).valid


def test_backward_branch_is_rejected_to_keep_execution_statically_bounded() -> None:
    item = WorkflowDefinition(
        "Branch",
        (
            WorkflowStep("first", WorkflowStepType.ASSIGN),
            WorkflowStep(
                "choose",
                WorkflowStepType.CONDITION,
                condition=WorkflowCondition(True, ConditionOperator.IS_TRUE),
                if_true="first",
                if_false="first",
            ),
        ),
    )
    assert not validator().validate(item).valid


def test_invalid_delay_and_retry() -> None:
    steps = (WorkflowStep("wait", WorkflowStepType.WAIT, {"seconds": 5000}, retries=3),)
    assert (
        len(
            validator(maximum_delay_seconds=10, maximum_retries=2)
            .validate(WorkflowDefinition("Delay", steps))
            .errors
        )
        == 2
    )


def test_preview_is_deterministic_and_side_effect_free() -> None:
    workflow = WorkflowDefinition(
        "Preview", (WorkflowStep("shot", WorkflowStepType.CAPTURE_SCREENSHOT),)
    )
    plan = WorkflowPlanner(validator()).plan(workflow)
    assert plan.steps[0].sensitive and plan.steps[0].service == "desktop_utilities"


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        (WorkflowCondition("a", ConditionOperator.EQUALS, "a"), True),
        (WorkflowCondition("abc", ConditionOperator.CONTAINS, "b"), True),
        (WorkflowCondition(3, ConditionOperator.GREATER_THAN, 2), True),
        (WorkflowCondition("", ConditionOperator.IS_EMPTY), True),
        (WorkflowCondition(True, ConditionOperator.IS_TRUE), True),
    ],
)
def test_conditions(condition: WorkflowCondition, expected: bool) -> None:
    assert evaluate(condition, {}, 100) is expected


def test_substitution_and_missing_variable() -> None:
    assert (
        substitute("Hello ${input.name}", {"input.name": "Omega"}, 100) == "Hello Omega"
    )
    with pytest.raises(WorkflowValidationError):
        substitute("${input.missing}", {}, 100)


def test_substitution_bound() -> None:
    with pytest.raises(WorkflowValidationError):
        substitute("${input.text}", {"input.text": "long"}, 2)
