"""Typed execution result data for a future executor layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from omega.core.exceptions import ModelValidationError
from omega.models._serialization import (
    JsonValue,
    parse_utc_timestamp,
    parse_uuid,
    serialize_value,
    utc_now,
    validate_json_mapping,
    validate_json_value,
    validate_utc_timestamp,
)
from omega.models.enums import ActionStatus
from omega.models.error import OmegaErrorDetails


@dataclass
class ActionResult:
    """A serializable outcome record; creating it has no execution side effect."""

    action_id: UUID
    success: bool
    status: ActionStatus
    message: str
    user_message: str
    data: JsonValue = field(default_factory=dict)
    error: OmegaErrorDetails | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.action_id, UUID):
            raise ModelValidationError("action_id must be a UUID.")
        if not isinstance(self.success, bool):
            raise ModelValidationError("success must be a boolean.")
        if not isinstance(self.status, ActionStatus):
            raise ModelValidationError("status must be an ActionStatus.")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ModelValidationError("message must be a non-empty string.")
        if not isinstance(self.user_message, str) or not self.user_message.strip():
            raise ModelValidationError("user_message must be a non-empty string.")
        if self.success:
            if self.status is not ActionStatus.SUCCEEDED:
                raise ModelValidationError(
                    "Successful results must have SUCCEEDED status."
                )
            if self.error is not None:
                raise ModelValidationError(
                    "Successful results must not contain an error."
                )
        else:
            if self.status is not ActionStatus.FAILED:
                raise ModelValidationError("Failed results must have FAILED status.")
            if self.error is None:
                raise ModelValidationError(
                    "Failed results must contain structured error details."
                )
        if self.error is not None and not isinstance(self.error, OmegaErrorDetails):
            raise ModelValidationError("error must be OmegaErrorDetails or None.")
        self.data = validate_json_value(self.data, "data")
        self.metadata = validate_json_mapping(self.metadata, "metadata")
        if self.started_at is not None:
            self.started_at = validate_utc_timestamp(self.started_at, "started_at")
        if self.completed_at is not None:
            self.completed_at = validate_utc_timestamp(
                self.completed_at, "completed_at"
            )
        if self.completed_at is not None and self.started_at is not None:
            if self.completed_at < self.started_at:
                raise ModelValidationError("completed_at must not precede started_at.")
        if self.duration_ms is not None:
            if isinstance(self.duration_ms, bool) or self.duration_ms < 0:
                raise ModelValidationError(
                    "duration_ms must be a non-negative integer or None."
                )
            if not isinstance(self.duration_ms, int):
                raise ModelValidationError(
                    "duration_ms must be a non-negative integer or None."
                )

    @classmethod
    def success_result(
        cls,
        action_id: UUID,
        message: str,
        user_message: str,
        *,
        data: JsonValue = None,
        metadata: dict[str, JsonValue] | None = None,
    ) -> ActionResult:
        """Build a valid successful result with captured UTC completion times."""
        timestamp = utc_now()
        return cls(
            action_id=action_id,
            success=True,
            status=ActionStatus.SUCCEEDED,
            message=message,
            user_message=user_message,
            data=data,
            started_at=timestamp,
            completed_at=timestamp,
            duration_ms=0,
            metadata={} if metadata is None else metadata,
        )

    @classmethod
    def failure_result(
        cls,
        action_id: UUID,
        message: str,
        user_message: str,
        error: OmegaErrorDetails,
        *,
        metadata: dict[str, JsonValue] | None = None,
    ) -> ActionResult:
        """Build a valid failed result with captured UTC completion times."""
        timestamp = utc_now()
        return cls(
            action_id=action_id,
            success=False,
            status=ActionStatus.FAILED,
            message=message,
            user_message=user_message,
            error=error,
            started_at=timestamp,
            completed_at=timestamp,
            duration_ms=0,
            metadata={} if metadata is None else metadata,
        )

    def to_dict(self) -> dict[str, JsonValue]:
        """Serialize the result and nested structured error record."""
        return {
            "action_id": str(self.action_id),
            "success": self.success,
            "status": self.status.value,
            "message": self.message,
            "user_message": self.user_message,
            "data": self.data,
            "error": self.error.to_dict() if self.error else None,
            "started_at": serialize_value(self.started_at),
            "completed_at": serialize_value(self.completed_at),
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionResult:
        """Deserialize a previously serialized action result."""
        try:
            error_data = data.get("error")
            if error_data is not None and not isinstance(error_data, dict):
                raise ModelValidationError("error must be an object or None.")
            started_at = data.get("started_at")
            completed_at = data.get("completed_at")
            return cls(
                action_id=parse_uuid(data["action_id"], "action_id"),
                success=data["success"],
                status=ActionStatus(data["status"]),
                message=data["message"],
                user_message=data["user_message"],
                data=data.get("data", {}),
                error=OmegaErrorDetails.from_dict(error_data) if error_data else None,
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
                duration_ms=data.get("duration_ms"),
                metadata=data.get("metadata", {}),
            )
        except KeyError as error:
            raise ModelValidationError(
                f"Missing result field: {error.args[0]}."
            ) from error
