"""Static validation and side-effect-free workflow planning."""

import json

from omega.workflows.configuration import WorkflowConfiguration
from omega.workflows.models import (
    WorkflowDefinition,
    WorkflowPlan,
    WorkflowPlanStep,
    WorkflowStepType,
    WorkflowTriggerType,
    WorkflowValidationResult,
)

_SENSITIVE = {
    WorkflowStepType.CAPTURE_SCREENSHOT,
    WorkflowStepType.REQUEST_CONFIRMATION,
}
_EXTERNAL = {
    WorkflowStepType.CREATE_EMAIL_DRAFT,
    WorkflowStepType.CREATE_CALENDAR_PROPOSAL,
}
_SERVICES = {
    WorkflowStepType.OPEN_APPLICATION: "applications",
    WorkflowStepType.CREATE_FILE: "files",
    WorkflowStepType.WRITE_FILE: "files",
    WorkflowStepType.OPEN_FILE: "files",
    WorkflowStepType.CREATE_FOLDER: "folders",
    WorkflowStepType.OPEN_FOLDER: "folders",
    WorkflowStepType.CREATE_NOTE: "productivity",
    WorkflowStepType.CREATE_TASK: "productivity",
    WorkflowStepType.CREATE_REMINDER: "scheduling",
    WorkflowStepType.SEARCH_KNOWLEDGE: "knowledge",
    WorkflowStepType.COPY_CLIPBOARD: "desktop_utilities",
    WorkflowStepType.CAPTURE_SCREENSHOT: "desktop_utilities",
    WorkflowStepType.CREATE_EMAIL_DRAFT: "email",
    WorkflowStepType.CREATE_CALENDAR_PROPOSAL: "calendar",
    WorkflowStepType.SHOW_SYSTEM_INFORMATION: "system",
}


class WorkflowValidator:
    def __init__(self, configuration: WorkflowConfiguration) -> None:
        self.configuration = configuration

    def validate(self, workflow: WorkflowDefinition) -> WorkflowValidationResult:
        errors: list[str] = []
        if not self.configuration.enabled:
            errors.append("Workflow automation is disabled.")
        if len(workflow.name) > self.configuration.maximum_workflow_name_characters:
            errors.append("Workflow name exceeds the configured limit.")
        if (
            len(workflow.description)
            > self.configuration.maximum_description_characters
        ):
            errors.append("Workflow description exceeds the configured limit.")
        if not workflow.steps:
            errors.append("Workflow must contain at least one step.")
        if (
            workflow.trigger is not WorkflowTriggerType.MANUAL
            and not self.configuration.allow_scheduled_workflows
        ):
            errors.append("Scheduled workflow triggers are disabled.")
        if len(workflow.steps) > self.configuration.maximum_steps_per_workflow:
            errors.append("Workflow has too many steps.")
        identifiers = {step.step_id for step in workflow.steps}
        positions = {step.step_id: index for index, step in enumerate(workflow.steps)}
        for index, step in enumerate(workflow.steps):
            if (
                step.timeout_seconds is not None
                and not 1
                <= step.timeout_seconds
                <= self.configuration.maximum_step_seconds
            ):
                errors.append(f"Step {step.step_id} timeout is invalid.")
            if step.retries > self.configuration.maximum_retries:
                errors.append(f"Step {step.step_id} retry count is excessive.")
            if step.step_type is WorkflowStepType.WAIT:
                delay = step.arguments.get("seconds")
                if (
                    isinstance(delay, bool)
                    or not isinstance(delay, int)
                    or not 0 <= delay <= self.configuration.maximum_delay_seconds
                ):
                    errors.append(f"Step {step.step_id} delay is invalid.")
            for target in (step.if_true, step.if_false):
                if target is not None and target not in identifiers:
                    errors.append(f"Step {step.step_id} has a missing branch target.")
                elif target is not None and positions[target] <= index:
                    errors.append(
                        f"Step {step.step_id} has a backward or circular branch."
                    )
            if (step.if_true is None) != (step.if_false is None):
                errors.append(f"Step {step.step_id} must define both branch targets.")
            if (step.if_true is not None or step.if_false is not None) and (
                step.condition is None
            ):
                errors.append(f"Step {step.step_id} branch requires a condition.")
        size = len(json.dumps(workflow.to_dict(), sort_keys=True).encode())
        if size > self.configuration.maximum_serialized_definition_bytes:
            errors.append("Workflow definition exceeds the serialized-size limit.")
        return WorkflowValidationResult(not errors, tuple(errors))


class WorkflowPlanner:
    def __init__(self, validator: WorkflowValidator) -> None:
        self.validator = validator

    def plan(self, workflow: WorkflowDefinition) -> WorkflowPlan:
        result = self.validator.validate(workflow)
        if not result.valid:
            from omega.workflows.exceptions import WorkflowValidationError

            raise WorkflowValidationError("; ".join(result.errors))
        steps = tuple(
            WorkflowPlanStep(
                index,
                step.step_id,
                step.description or step.step_type.value.replace("_", " "),
                _SERVICES.get(step.step_type, "workflow"),
                step.step_type in _SENSITIVE,
                step.step_type in _EXTERNAL,
            )
            for index, step in enumerate(workflow.steps, 1)
        )
        maximum = (
            workflow.default_timeout_seconds
            or self.validator.configuration.maximum_execution_seconds
        )
        return WorkflowPlan(
            workflow.name, steps, maximum, workflow.failure_policy, workflow.trigger
        )
