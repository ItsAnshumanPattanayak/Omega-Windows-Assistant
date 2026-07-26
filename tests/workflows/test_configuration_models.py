from datetime import UTC, datetime

import pytest

from omega.core.exceptions import ModelValidationError
from omega.workflows import (
    ConditionOperator,
    WorkflowCondition,
    WorkflowConfiguration,
    WorkflowContext,
    WorkflowDefinition,
    WorkflowStatus,
    WorkflowStep,
    WorkflowStepType,
    WorkflowTrigger,
    WorkflowTriggerType,
    WorkflowVariable,
)
from omega.workflows.exceptions import (
    WorkflowConfigurationError,
    WorkflowValidationError,
)


def test_configuration_defaults_are_conservative() -> None:
    value = WorkflowConfiguration()
    assert value.maximum_concurrent_runs == 1 and not value.allow_shell_steps
    assert not value.allow_code_execution_steps and not value.allow_background_triggers


@pytest.mark.parametrize(
    "field",
    [
        "allow_shell_steps",
        "allow_code_execution_steps",
        "allow_network_request_steps",
        "allow_background_triggers",
    ],
)
def test_forbidden_configuration(field: str) -> None:
    with pytest.raises(WorkflowConfigurationError):
        WorkflowConfiguration.from_mapping({field: True})


@pytest.mark.parametrize(
    "field",
    [
        "maximum_workflows",
        "maximum_steps_per_workflow",
        "maximum_execution_seconds",
        "maximum_variable_characters",
    ],
)
def test_invalid_bounds(field: str) -> None:
    with pytest.raises(WorkflowConfigurationError):
        WorkflowConfiguration.from_mapping({field: 0})


def test_unknown_configuration_rejected() -> None:
    with pytest.raises(WorkflowConfigurationError):
        WorkflowConfiguration.from_mapping({"allow_python": True})


def test_definition_round_trip() -> None:
    now = datetime.now(UTC)
    value = WorkflowDefinition(
        "Morning Setup",
        (WorkflowStep("show", WorkflowStepType.DISPLAY_MESSAGE, {"message": "hello"}),),
        status=WorkflowStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    assert WorkflowDefinition.from_dict(value.to_dict()) == value


@pytest.mark.parametrize("name", ["", "bad/name", "x" * 400])
def test_invalid_names(name: str) -> None:
    with pytest.raises(WorkflowValidationError):
        WorkflowDefinition(name, ())


def test_duplicate_steps_rejected() -> None:
    step = WorkflowStep("same", WorkflowStepType.ASSIGN)
    with pytest.raises(WorkflowValidationError):
        WorkflowDefinition("Duplicate", (step, step))


def test_json_only_arguments() -> None:
    with pytest.raises(ModelValidationError):
        WorkflowStep("bad", WorkflowStepType.ASSIGN, {"value": object()})


def test_condition_is_code_free() -> None:
    value = WorkflowCondition("${input.ok}", ConditionOperator.IS_TRUE)
    assert value.operator is ConditionOperator.IS_TRUE


def test_typed_context_and_variable_are_bounded() -> None:
    context = WorkflowContext(maximum_characters=10)
    context.set("project", "Omega")
    assert context.variables == {"project": "Omega"}
    assert WorkflowVariable("safe_name", True).value is True
    with pytest.raises(WorkflowValidationError):
        context.set("large", "x" * 20)


def test_scheduled_trigger_requires_existing_schedule_reference() -> None:
    with pytest.raises(WorkflowValidationError):
        WorkflowTrigger(WorkflowTriggerType.SCHEDULED)
    assert WorkflowTrigger(WorkflowTriggerType.SCHEDULED, "schedule-id").schedule_id
