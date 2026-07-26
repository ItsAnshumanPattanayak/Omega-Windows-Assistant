import json

import pytest

from omega.workflows import (
    WorkflowConfiguration,
    WorkflowDefinition,
    WorkflowStep,
    WorkflowStepType,
    WorkflowTriggerType,
    WorkflowValidator,
)
from omega.workflows.exceptions import (
    WorkflowConfigurationError,
    WorkflowValidationError,
)


@pytest.mark.parametrize(
    "step_type",
    [
        "shell",
        "powershell",
        "cmd",
        "python",
        "javascript",
        "raw_sql",
        "http_request",
        "webhook",
        "keyboard_macro",
        "mouse_macro",
        "file_watcher",
        "clipboard_watcher",
        "email_trigger",
        "calendar_trigger",
        "screen_watcher",
    ],
)
def test_unknown_or_executable_step_types_rejected(step_type: str) -> None:
    with pytest.raises(ValueError):
        WorkflowStepType(step_type)


@pytest.mark.parametrize(
    "reference", ["bad-name", "9name", "has space", "x" * 70, "a/b", "a.b"]
)
def test_invalid_step_identifiers(reference: str) -> None:
    with pytest.raises(WorkflowValidationError):
        WorkflowStep(reference, WorkflowStepType.ASSIGN)


@pytest.mark.parametrize(
    "field",
    [
        "enabled",
        "allow_scheduled_workflows",
        "allow_destructive_steps",
        "allow_external_side_effect_steps",
        "require_confirmation_before_run",
        "imported_workflows_enabled_by_default",
        "stop_on_failure_by_default",
    ],
)
def test_boolean_settings_reject_non_boolean(field: str) -> None:
    with pytest.raises(WorkflowConfigurationError):
        WorkflowConfiguration.from_mapping({field: 1})


@pytest.mark.parametrize(
    "trigger", [WorkflowTriggerType.SCHEDULED, WorkflowTriggerType.RECURRING]
)
def test_scheduled_trigger_obeys_configuration(trigger: WorkflowTriggerType) -> None:
    config = WorkflowConfiguration(allow_scheduled_workflows=False)
    item = WorkflowDefinition(
        "Scheduled",
        (WorkflowStep("show", WorkflowStepType.DISPLAY_MESSAGE),),
        trigger=trigger,
    )
    assert not WorkflowValidator(config).validate(item).valid


@pytest.mark.parametrize(
    "value",
    [
        "filesystem",
        "clipboard",
        "email",
        "calendar",
        "webhook",
        "process",
        "keyboard",
        "microphone",
    ],
)
def test_unsupported_triggers_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        WorkflowTriggerType(value)


def test_serialized_definition_has_no_callable_or_code_field() -> None:
    item = WorkflowDefinition(
        "Safe", (WorkflowStep("assign", WorkflowStepType.ASSIGN, {"value": "data"}),)
    )
    payload = json.dumps(item.to_dict())
    assert all(
        word not in payload
        for word in ('"code"', '"callable"', '"module"', '"executable"')
    )
