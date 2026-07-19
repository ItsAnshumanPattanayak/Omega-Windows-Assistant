"""Structured outcomes for future recovery operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from omega.core.exceptions import ModelValidationError
from omega.models._serialization import (
    JsonValue,
    serialize_value,
    utc_now,
    validate_json_mapping,
    validate_utc_timestamp,
)
from omega.recovery.models import RecoveryRecord


@dataclass(frozen=True)
class RecoveryResult:
    """Safe result returned by future Recycle Bin and restore services."""

    success: bool
    code: str
    message: str
    record: RecoveryRecord | None = None
    completed_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise ModelValidationError("success must be a boolean.")

        for field_name in ("code", "message"):
            value = getattr(self, field_name)

            if not isinstance(value, str) or not value.strip():
                raise ModelValidationError(f"{field_name} must be a non-empty string.")

        if self.record is not None:
            if not isinstance(self.record, RecoveryRecord):
                raise ModelValidationError("record must be a RecoveryRecord or None.")

        object.__setattr__(
            self,
            "completed_at",
            validate_utc_timestamp(self.completed_at, "completed_at"),
        )
        object.__setattr__(
            self,
            "metadata",
            validate_json_mapping(self.metadata, "metadata"),
        )

    def to_dict(self) -> dict[str, JsonValue]:
        """Return a privacy-safe JSON-compatible result."""

        return {
            "success": self.success,
            "code": self.code,
            "message": self.message,
            "record": (self.record.to_dict() if self.record is not None else None),
            "completed_at": serialize_value(self.completed_at),
            "metadata": self.metadata,
        }
