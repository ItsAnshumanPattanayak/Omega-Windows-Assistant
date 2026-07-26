"""Conservative, non-overridable workflow security bounds."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from omega.workflows.exceptions import WorkflowConfigurationError


@dataclass(frozen=True)
class WorkflowConfiguration:
    enabled: bool = True
    maximum_workflows: int = 100
    maximum_steps_per_workflow: int = 50
    maximum_workflow_name_characters: int = 120
    maximum_description_characters: int = 1000
    maximum_serialized_definition_bytes: int = 262144
    maximum_execution_seconds: int = 1800
    maximum_step_seconds: int = 300
    maximum_delay_seconds: int = 3600
    maximum_retries: int = 2
    maximum_condition_depth: int = 4
    maximum_variable_characters: int = 10000
    maximum_result_characters: int = 20000
    maximum_history_results: int = 50
    maximum_concurrent_runs: int = 1
    allow_scheduled_workflows: bool = True
    allow_destructive_steps: bool = False
    allow_external_side_effect_steps: bool = True
    require_confirmation_before_run: bool = True
    require_confirmation_for_sensitive_steps: bool = True
    imported_workflows_enabled_by_default: bool = False
    stop_on_failure_by_default: bool = True
    allow_background_triggers: bool = False
    allow_shell_steps: bool = False
    allow_code_execution_steps: bool = False
    allow_network_request_steps: bool = False

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "WorkflowConfiguration":
        unknown = set(values) - set(cls.__dataclass_fields__)
        if unknown:
            raise WorkflowConfigurationError(
                "Unknown workflow setting(s): " + ", ".join(sorted(unknown))
            )
        try:
            return cls(**values)
        except TypeError as error:
            raise WorkflowConfigurationError(
                "Workflow configuration is invalid."
            ) from error

    def __post_init__(self) -> None:
        security_false = (
            "allow_background_triggers",
            "allow_shell_steps",
            "allow_code_execution_steps",
            "allow_network_request_steps",
        )
        if any(getattr(self, name) for name in security_false):
            raise WorkflowConfigurationError(
                "Background, shell, code, and raw-network workflow features "
                "must remain disabled."
            )
        if not self.require_confirmation_for_sensitive_steps:
            raise WorkflowConfigurationError(
                "Sensitive workflow confirmations cannot be disabled."
            )
        for name in (
            "enabled",
            "allow_scheduled_workflows",
            "allow_destructive_steps",
            "allow_external_side_effect_steps",
            "require_confirmation_before_run",
            "imported_workflows_enabled_by_default",
            "stop_on_failure_by_default",
        ):
            if not isinstance(getattr(self, name), bool):
                raise WorkflowConfigurationError(f"workflows.{name} must be boolean.")
        bounds = {
            "maximum_workflows": (1, 1000),
            "maximum_steps_per_workflow": (1, 200),
            "maximum_workflow_name_characters": (1, 300),
            "maximum_description_characters": (1, 10000),
            "maximum_serialized_definition_bytes": (1024, 1048576),
            "maximum_execution_seconds": (1, 86400),
            "maximum_step_seconds": (1, 3600),
            "maximum_delay_seconds": (0, 86400),
            "maximum_retries": (0, 5),
            "maximum_condition_depth": (1, 10),
            "maximum_variable_characters": (1, 100000),
            "maximum_result_characters": (1, 200000),
            "maximum_history_results": (1, 500),
            "maximum_concurrent_runs": (1, 4),
        }
        for name, (low, high) in bounds.items():
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not low <= value <= high
            ):
                raise WorkflowConfigurationError(
                    f"workflows.{name} must be between {low} and {high}."
                )
