"""Typed, non-executing models for Omega recovery operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from omega.core.exceptions import ModelValidationError
from omega.models._serialization import (
    JsonValue,
    serialize_value,
    utc_now,
    validate_json_mapping,
    validate_utc_timestamp,
)


class RecoverableActionType(StrEnum):
    """Recoverable actions supported by the Phase 8 architecture."""

    RECYCLE_FILE = "recycle_file"
    RECYCLE_FOLDER = "recycle_folder"
    RESTORE_FILE = "restore_file"
    RESTORE_FOLDER = "restore_folder"


class RecoveryRecordStatus(StrEnum):
    """Lifecycle state of a recoverable action record."""

    PENDING = "pending"
    COMPLETED = "completed"
    RESTORED = "restored"
    EXPIRED = "expired"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RecoveryResourceType(StrEnum):
    """Filesystem resource kinds handled by recovery services."""

    FILE = "file"
    FOLDER = "folder"


@dataclass(frozen=True)
class RecycleBinItem:
    """Privacy-safe information about one recycled resource.

    Sensitive operating-system paths and Recycle Bin identifiers are retained
    only in process memory and intentionally omitted from public serialization.
    """

    resource_type: RecoveryResourceType
    display_name: str
    logical_location: str
    relative_path: str
    original_path_fingerprint: str
    recycled_at: datetime = field(default_factory=utc_now)
    recycle_bin_reference: str | None = None
    size_bytes: int | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.resource_type, RecoveryResourceType):
            raise ModelValidationError("resource_type must be a RecoveryResourceType.")

        for field_name in (
            "display_name",
            "logical_location",
            "relative_path",
            "original_path_fingerprint",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ModelValidationError(f"{field_name} must be a non-empty string.")

        if self.recycle_bin_reference is not None:
            if (
                not isinstance(self.recycle_bin_reference, str)
                or not self.recycle_bin_reference.strip()
            ):
                raise ModelValidationError(
                    "recycle_bin_reference must be non-empty when supplied."
                )

        if self.size_bytes is not None:
            if (
                isinstance(self.size_bytes, bool)
                or not isinstance(self.size_bytes, int)
                or self.size_bytes < 0
            ):
                raise ModelValidationError(
                    "size_bytes must be a non-negative integer or None."
                )

        object.__setattr__(
            self,
            "recycled_at",
            validate_utc_timestamp(self.recycled_at, "recycled_at"),
        )
        object.__setattr__(
            self,
            "metadata",
            validate_json_mapping(self.metadata, "metadata"),
        )

    def to_dict(self) -> dict[str, JsonValue]:
        """Return a privacy-safe JSON-compatible representation."""

        return {
            "resource_type": self.resource_type.value,
            "display_name": self.display_name,
            "logical_location": self.logical_location,
            "relative_path": self.relative_path,
            "recycled_at": serialize_value(self.recycled_at),
            "size_bytes": self.size_bytes,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class RecoveryRecord:
    """Process-local record of one recoverable filesystem operation."""

    action_type: RecoverableActionType
    resource_type: RecoveryResourceType
    command_id: UUID
    action_id: UUID
    session_id: UUID
    item: RecycleBinItem
    status: RecoveryRecordStatus = RecoveryRecordStatus.PENDING
    record_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    expires_at: datetime | None = None
    restored_at: datetime | None = None
    failure_code: str | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.action_type, RecoverableActionType):
            raise ModelValidationError("action_type must be a RecoverableActionType.")

        if not isinstance(self.resource_type, RecoveryResourceType):
            raise ModelValidationError("resource_type must be a RecoveryResourceType.")

        for field_name in (
            "record_id",
            "command_id",
            "action_id",
            "session_id",
        ):
            if not isinstance(getattr(self, field_name), UUID):
                raise ModelValidationError(f"{field_name} must be a UUID.")

        if not isinstance(self.item, RecycleBinItem):
            raise ModelValidationError("item must be a RecycleBinItem.")

        if self.item.resource_type is not self.resource_type:
            raise ModelValidationError(
                "Recovery record and item resource types must agree."
            )

        if not isinstance(self.status, RecoveryRecordStatus):
            raise ModelValidationError("status must be a RecoveryRecordStatus.")

        object.__setattr__(
            self,
            "created_at",
            validate_utc_timestamp(self.created_at, "created_at"),
        )

        if self.expires_at is not None:
            normalized_expiry = validate_utc_timestamp(
                self.expires_at,
                "expires_at",
            )

            if normalized_expiry <= self.created_at:
                raise ModelValidationError("expires_at must follow created_at.")

            object.__setattr__(
                self,
                "expires_at",
                normalized_expiry,
            )

        if self.restored_at is not None:
            normalized_restored_at = validate_utc_timestamp(
                self.restored_at,
                "restored_at",
            )

            if normalized_restored_at < self.created_at:
                raise ModelValidationError("restored_at must not precede created_at.")

            object.__setattr__(
                self,
                "restored_at",
                normalized_restored_at,
            )

        if self.status is RecoveryRecordStatus.RESTORED:
            if self.restored_at is None:
                raise ModelValidationError("Restored records require restored_at.")
        elif self.restored_at is not None:
            raise ModelValidationError(
                "restored_at is valid only for restored records."
            )

        if self.failure_code is not None:
            if not isinstance(self.failure_code, str) or not self.failure_code.strip():
                raise ModelValidationError(
                    "failure_code must be non-empty when supplied."
                )

        if self.status is RecoveryRecordStatus.FAILED:
            if self.failure_code is None:
                raise ModelValidationError(
                    "Failed recovery records require failure_code."
                )
        elif self.failure_code is not None:
            raise ModelValidationError("failure_code is valid only for failed records.")

        object.__setattr__(
            self,
            "metadata",
            validate_json_mapping(self.metadata, "metadata"),
        )

    @property
    def can_restore(self) -> bool:
        """Return whether this record currently represents a restorable item."""

        return self.status is RecoveryRecordStatus.COMPLETED

    def to_dict(self) -> dict[str, JsonValue]:
        """Return a privacy-safe JSON-compatible representation."""

        return {
            "record_id": str(self.record_id),
            "action_type": self.action_type.value,
            "resource_type": self.resource_type.value,
            "command_id": str(self.command_id),
            "action_id": str(self.action_id),
            "session_id": str(self.session_id),
            "item": self.item.to_dict(),
            "status": self.status.value,
            "created_at": serialize_value(self.created_at),
            "expires_at": serialize_value(self.expires_at),
            "restored_at": serialize_value(self.restored_at),
            "failure_code": self.failure_code,
            "can_restore": self.can_restore,
            "metadata": self.metadata,
        }
