"""Action proposals and lifecycle validation without execution behavior."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from omega.core.exceptions import ModelValidationError
from omega.models._serialization import (
    JsonValue,
    parse_utc_timestamp,
    parse_uuid,
    serialize_value,
    utc_now,
    validate_json_mapping,
    validate_utc_timestamp,
)
from omega.models.enums import (
    ActionStatus,
    ConfirmationStatus,
    IntentType,
    PermissionDecision,
    RiskLevel,
)


@dataclass
class Action:
    """A proposed operation and its validated lifecycle state.

    Actions intentionally remain mutable for future controlled state transitions.
    This Phase 1 model never invokes a service, process, path, or operating-system
    API; it only represents a proposed operation.
    """

    command_id: UUID
    intent: IntentType
    action_id: UUID = field(default_factory=uuid4)
    parameters: dict[str, JsonValue] = field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.MEDIUM
    status: ActionStatus = ActionStatus.PENDING
    permission_decision: PermissionDecision = PermissionDecision.REQUIRE_CONFIRMATION
    confirmation_status: ConfirmationStatus = ConfirmationStatus.PENDING
    requires_confirmation: bool = True
    dependencies: list[UUID] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.action_id, UUID):
            raise ModelValidationError("action_id must be a UUID.")
        if not isinstance(self.command_id, UUID):
            raise ModelValidationError("command_id must be a UUID.")
        if not isinstance(self.intent, IntentType):
            raise ModelValidationError("intent must be an IntentType.")
        if not isinstance(self.risk_level, RiskLevel):
            raise ModelValidationError("risk_level must be a RiskLevel.")
        if not isinstance(self.status, ActionStatus):
            raise ModelValidationError("status must be an ActionStatus.")
        if not isinstance(self.permission_decision, PermissionDecision):
            raise ModelValidationError(
                "permission_decision must be a PermissionDecision."
            )
        if not isinstance(self.confirmation_status, ConfirmationStatus):
            raise ModelValidationError(
                "confirmation_status must be a ConfirmationStatus."
            )
        if not isinstance(self.requires_confirmation, bool):
            raise ModelValidationError("requires_confirmation must be a boolean.")
        self.parameters = validate_json_mapping(self.parameters, "parameters")
        self.metadata = validate_json_mapping(self.metadata, "metadata")
        self.dependencies = list(self.dependencies)
        if not all(isinstance(dependency, UUID) for dependency in self.dependencies):
            raise ModelValidationError("dependencies must contain UUID values.")
        if self.action_id in self.dependencies:
            raise ModelValidationError("An action must not depend on itself.")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ModelValidationError(
                "dependencies must not contain duplicate action IDs."
            )
        self.created_at = validate_utc_timestamp(self.created_at, "created_at")
        if self.started_at is not None:
            self.started_at = validate_utc_timestamp(self.started_at, "started_at")
        if self.completed_at is not None:
            self.completed_at = validate_utc_timestamp(
                self.completed_at, "completed_at"
            )
        self._validate_confirmation_state()
        self._validate_timestamps()

    def _validate_confirmation_state(self) -> None:
        if self.requires_confirmation:
            if self.permission_decision is not PermissionDecision.REQUIRE_CONFIRMATION:
                raise ModelValidationError(
                    "Actions requiring confirmation need a "
                    "REQUIRE_CONFIRMATION decision."
                )
            if self.confirmation_status is ConfirmationStatus.NOT_REQUIRED:
                raise ModelValidationError(
                    "Actions requiring confirmation cannot be NOT_REQUIRED."
                )
        else:
            if self.confirmation_status is not ConfirmationStatus.NOT_REQUIRED:
                raise ModelValidationError(
                    "Actions without confirmation must use NOT_REQUIRED "
                    "confirmation status."
                )
            if self.permission_decision is PermissionDecision.REQUIRE_CONFIRMATION:
                raise ModelValidationError(
                    "REQUIRE_CONFIRMATION decisions must set "
                    "requires_confirmation to true."
                )
        if self.confirmation_status is ConfirmationStatus.REJECTED:
            if self.status is not ActionStatus.REJECTED:
                raise ModelValidationError(
                    "A rejected confirmation requires REJECTED action status."
                )
        if self.status is ActionStatus.REJECTED:
            valid_rejection = (
                self.confirmation_status is ConfirmationStatus.REJECTED
                or self.permission_decision is PermissionDecision.DENY
            )
            if not valid_rejection:
                raise ModelValidationError(
                    "REJECTED actions need a rejected confirmation or DENY decision."
                )
        if self.status is ActionStatus.APPROVED:
            if self.confirmation_status is ConfirmationStatus.REJECTED:
                raise ModelValidationError(
                    "Rejected actions must not be marked APPROVED."
                )

    def _validate_timestamps(self) -> None:
        if self.status is ActionStatus.RUNNING and self.started_at is None:
            raise ModelValidationError("RUNNING actions require started_at.")
        if self.status is ActionStatus.SUCCEEDED and self.completed_at is None:
            raise ModelValidationError("SUCCEEDED actions require completed_at.")
        if self.completed_at is not None:
            if self.started_at is None:
                raise ModelValidationError("completed_at requires started_at.")
            if self.completed_at < self.started_at:
                raise ModelValidationError("completed_at must not precede started_at.")

    def to_dict(self) -> dict[str, JsonValue]:
        """Serialize the action proposal without serializing execution objects."""
        return {
            "action_id": str(self.action_id),
            "command_id": str(self.command_id),
            "intent": self.intent.value,
            "parameters": self.parameters,
            "risk_level": self.risk_level.value,
            "status": self.status.value,
            "permission_decision": self.permission_decision.value,
            "confirmation_status": self.confirmation_status.value,
            "requires_confirmation": self.requires_confirmation,
            "dependencies": [str(dependency) for dependency in self.dependencies],
            "created_at": serialize_value(self.created_at),
            "started_at": serialize_value(self.started_at),
            "completed_at": serialize_value(self.completed_at),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Action:
        """Deserialize a previously serialized action proposal."""
        try:
            dependencies = data.get("dependencies", [])
            if not isinstance(dependencies, list):
                raise ModelValidationError("dependencies must be a list.")
            started_at = data.get("started_at")
            completed_at = data.get("completed_at")
            return cls(
                action_id=parse_uuid(data["action_id"], "action_id"),
                command_id=parse_uuid(data["command_id"], "command_id"),
                intent=IntentType(data["intent"]),
                parameters=data.get("parameters", {}),
                risk_level=RiskLevel(data.get("risk_level", RiskLevel.MEDIUM.value)),
                status=ActionStatus(data.get("status", ActionStatus.PENDING.value)),
                permission_decision=PermissionDecision(
                    data.get(
                        "permission_decision",
                        PermissionDecision.REQUIRE_CONFIRMATION.value,
                    )
                ),
                confirmation_status=ConfirmationStatus(
                    data.get("confirmation_status", ConfirmationStatus.PENDING.value)
                ),
                requires_confirmation=data.get("requires_confirmation", True),
                dependencies=[parse_uuid(item, "dependency") for item in dependencies],
                created_at=parse_utc_timestamp(data["created_at"], "created_at"),
                started_at=(
                    parse_utc_timestamp(started_at, "started_at")
                    if started_at
                    else None
                ),
                completed_at=(
                    parse_utc_timestamp(completed_at, "completed_at")
                    if completed_at
                    else None
                ),
                metadata=data.get("metadata", {}),
            )
        except KeyError as error:
            raise ModelValidationError(
                f"Missing action field: {error.args[0]}."
            ) from error
