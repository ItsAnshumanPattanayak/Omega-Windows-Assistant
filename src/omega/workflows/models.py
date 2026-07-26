"""Serializable, code-free workflow models."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from omega.models._serialization import (
    JsonValue,
    serialize_value,
    validate_json_mapping,
    validate_json_value,
)
from omega.workflows.exceptions import WorkflowValidationError

_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9 _.-]*$")
_VARIABLE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")


class WorkflowStepType(StrEnum):
    OPEN_APPLICATION = "open_application"
    CREATE_FILE = "create_file"
    WRITE_FILE = "write_file"
    OPEN_FILE = "open_file"
    CREATE_FOLDER = "create_folder"
    OPEN_FOLDER = "open_folder"
    CREATE_NOTE = "create_note"
    CREATE_TASK = "create_task"
    CREATE_REMINDER = "create_reminder"
    SEARCH_KNOWLEDGE = "search_knowledge"
    COPY_CLIPBOARD = "copy_clipboard"
    CAPTURE_SCREENSHOT = "capture_screenshot"
    CREATE_EMAIL_DRAFT = "create_email_draft"
    CREATE_CALENDAR_PROPOSAL = "create_calendar_proposal"
    SHOW_SYSTEM_INFORMATION = "show_system_information"
    DISPLAY_MESSAGE = "display_message"
    ASK_TEXT = "ask_text"
    ASK_CHOICE = "ask_choice"
    REQUEST_CONFIRMATION = "request_confirmation"
    WAIT = "wait"
    ASSIGN = "assign"
    CONDITION = "condition"
    STOP = "stop"


class WorkflowStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class WorkflowRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class FailurePolicy(StrEnum):
    STOP = "stop"
    CONTINUE_SAFE_READS = "continue_safe_reads"


class WorkflowTriggerType(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    RECURRING = "recurring"


class ConditionOperator(StrEnum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    IS_EMPTY = "is_empty"
    IS_NOT_EMPTY = "is_not_empty"
    IS_TRUE = "is_true"
    IS_FALSE = "is_false"


@dataclass(frozen=True)
class WorkflowCondition:
    left: JsonValue
    operator: ConditionOperator
    right: JsonValue = None


@dataclass(frozen=True)
class WorkflowVariable:
    name: str
    value: JsonValue
    sensitive: bool = False

    def __post_init__(self) -> None:
        if not _VARIABLE.fullmatch(self.name):
            raise WorkflowValidationError("Workflow variable name is invalid.")
        validate_json_value(self.value, "workflow variable")


@dataclass(frozen=True)
class WorkflowTrigger:
    trigger_type: WorkflowTriggerType = WorkflowTriggerType.MANUAL
    schedule_id: str | None = None

    def __post_init__(self) -> None:
        if self.trigger_type is not WorkflowTriggerType.MANUAL and not self.schedule_id:
            raise WorkflowValidationError("Scheduled triggers require a schedule ID.")


@dataclass
class WorkflowContext:
    variables: dict[str, JsonValue] = field(default_factory=dict)
    maximum_characters: int = 10_000

    def set(self, name: str, value: JsonValue) -> None:
        variable = WorkflowVariable(name, value)
        if len(str(variable.value)) > self.maximum_characters:
            raise WorkflowValidationError("Workflow context value exceeds its bound.")
        self.variables[name] = validate_json_value(value, "workflow context")


@dataclass(frozen=True)
class WorkflowStep:
    step_id: str
    step_type: WorkflowStepType
    arguments: dict[str, JsonValue] = field(default_factory=dict)
    description: str = ""
    timeout_seconds: int | None = None
    retries: int = 0
    condition: WorkflowCondition | None = None
    if_true: str | None = None
    if_false: str | None = None

    def __post_init__(self) -> None:
        if not _VARIABLE.fullmatch(self.step_id):
            raise WorkflowValidationError(
                "Step identifiers must be simple bounded names."
            )
        object.__setattr__(
            self, "arguments", validate_json_mapping(self.arguments, "step arguments")
        )
        if self.retries < 0:
            raise WorkflowValidationError("Step retries cannot be negative.")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "step_id": self.step_id,
            "step_type": self.step_type.value,
            "arguments": serialize_value(self.arguments),
            "description": self.description,
            "timeout_seconds": self.timeout_seconds,
            "retries": self.retries,
            "condition": (
                None
                if self.condition is None
                else {
                    "left": self.condition.left,
                    "operator": self.condition.operator.value,
                    "right": self.condition.right,
                }
            ),
            "if_true": self.if_true,
            "if_false": self.if_false,
        }


@dataclass(frozen=True)
class WorkflowDefinition:
    name: str
    steps: tuple[WorkflowStep, ...]
    workflow_id: UUID = field(default_factory=uuid4)
    description: str = ""
    status: WorkflowStatus = WorkflowStatus.DRAFT
    version: int = 1
    tags: tuple[str, ...] = ()
    default_timeout_seconds: int | None = None
    failure_policy: FailurePolicy = FailurePolicy.STOP
    trigger: WorkflowTriggerType = WorkflowTriggerType.MANUAL
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if len(self.name) > 300 or not _NAME.fullmatch(self.name.strip()):
            raise WorkflowValidationError(
                "Workflow name contains unsupported characters."
            )
        if self.version < 1 or len(set(step.step_id for step in self.steps)) != len(
            self.steps
        ):
            raise WorkflowValidationError(
                "Workflow version and step identifiers must be valid and unique."
            )
        if any(
            value.tzinfo is None or value.utcoffset() is None
            for value in (self.created_at, self.updated_at)
        ):
            raise WorkflowValidationError("Workflow timestamps must be timezone-aware.")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "workflow_id": str(self.workflow_id),
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "steps": [step.to_dict() for step in self.steps],
            "version": self.version,
            "tags": list(self.tags),
            "default_timeout_seconds": self.default_timeout_seconds,
            "failure_policy": self.failure_policy.value,
            "trigger": self.trigger.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, value: dict[str, JsonValue]) -> WorkflowDefinition:
        try:
            raw_steps = value["steps"]
            if not isinstance(raw_steps, list):
                raise TypeError
            steps = []
            for raw in raw_steps:
                if not isinstance(raw, dict):
                    raise TypeError
                raw_condition = raw.get("condition")
                condition = None
                if isinstance(raw_condition, dict):
                    condition = WorkflowCondition(
                        raw_condition.get("left"),
                        ConditionOperator(str(raw_condition["operator"])),
                        raw_condition.get("right"),
                    )
                args = raw.get("arguments", {})
                if not isinstance(args, dict):
                    raise TypeError
                timeout_value = raw.get("timeout_seconds")
                timeout = timeout_value if isinstance(timeout_value, int) else None
                retries_value = raw.get("retries", 0)
                if not isinstance(retries_value, int):
                    raise TypeError
                steps.append(
                    WorkflowStep(
                        str(raw["step_id"]),
                        WorkflowStepType(str(raw["step_type"])),
                        args,
                        str(raw.get("description", "")),
                        timeout,
                        retries_value,
                        condition,
                        str(raw["if_true"]) if raw.get("if_true") else None,
                        str(raw["if_false"]) if raw.get("if_false") else None,
                    )
                )
            version_value = value.get("version", 1)
            tags_value = value.get("tags", [])
            default_timeout_value = value.get("default_timeout_seconds")
            if not isinstance(version_value, int) or not isinstance(tags_value, list):
                raise TypeError
            return cls(
                str(value["name"]),
                tuple(steps),
                workflow_id=UUID(str(value["workflow_id"])),
                description=str(value.get("description", "")),
                status=WorkflowStatus(str(value.get("status", "draft"))),
                version=version_value,
                tags=tuple(str(item) for item in tags_value if isinstance(item, str)),
                default_timeout_seconds=(
                    default_timeout_value
                    if isinstance(default_timeout_value, int)
                    else None
                ),
                failure_policy=FailurePolicy(str(value.get("failure_policy", "stop"))),
                trigger=WorkflowTriggerType(str(value.get("trigger", "manual"))),
                created_at=datetime.fromisoformat(str(value["created_at"])),
                updated_at=datetime.fromisoformat(str(value["updated_at"])),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise WorkflowValidationError(
                "Serialized workflow definition is invalid."
            ) from error


@dataclass(frozen=True)
class WorkflowStepResult:
    step_id: str
    success: bool
    output: JsonValue = None
    error_code: str | None = None


@dataclass
class WorkflowRun:
    workflow_id: UUID
    workflow_version: int
    run_id: UUID = field(default_factory=uuid4)
    status: WorkflowRunStatus = WorkflowRunStatus.PENDING
    current_step: int = 0
    results: list[WorkflowStepResult] = field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    safe_error_code: str | None = None


@dataclass(frozen=True)
class WorkflowRunSummary:
    run_id: UUID
    workflow_id: UUID
    workflow_name: str
    status: WorkflowRunStatus
    completed_steps: int
    failed_step_number: int | None
    safe_error_code: str | None
    started_at: datetime | None
    completed_at: datetime | None


@dataclass(frozen=True)
class WorkflowValidationResult:
    valid: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkflowPlanStep:
    number: int
    step_id: str
    description: str
    service: str
    sensitive: bool
    irreversible: bool


@dataclass(frozen=True)
class WorkflowPlan:
    workflow_name: str
    steps: tuple[WorkflowPlanStep, ...]
    maximum_execution_seconds: int
    failure_policy: FailurePolicy
    trigger: WorkflowTriggerType
