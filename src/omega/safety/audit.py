"""Privacy-preserving, process-local safety audit records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from threading import RLock
from uuid import UUID, uuid4

from omega.core.exceptions import ModelValidationError
from omega.models import ConfirmationStatus, IntentType, PermissionDecision, RiskLevel
from omega.models._serialization import (
    JsonValue,
    serialize_value,
    utc_now,
    validate_utc_timestamp,
)


class SafetyAuditEvent(StrEnum):
    EVALUATED = "evaluated"
    ALLOWED = "allowed"
    DENIED = "denied"
    CONFIRMATION_CREATED = "confirmation_created"
    CONFIRMATION_APPROVED = "confirmation_approved"
    CONFIRMATION_REJECTED = "confirmation_rejected"
    CONFIRMATION_EXPIRED = "confirmation_expired"
    CONFIRMATION_REPLAY_BLOCKED = "confirmation_replay_blocked"
    RESOURCE_CHANGED = "resource_changed"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_FINISHED = "execution_finished"


@dataclass(frozen=True)
class SafetyAuditRecord:
    """One redacted safety event suitable for future persistence."""

    event: SafetyAuditEvent
    intent: IntentType
    risk_level: RiskLevel
    decision: PermissionDecision
    reason_code: str
    policy_ids: tuple[str, ...]
    confirmation_status: ConfirmationStatus
    safe_target_description: str
    event_id: UUID = field(default_factory=uuid4)
    session_id: UUID | None = None
    command_id: UUID | None = None
    action_id: UUID | None = None
    occurred_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not isinstance(self.event, SafetyAuditEvent):
            raise ModelValidationError("event must be a SafetyAuditEvent.")
        if not self.reason_code or not self.safe_target_description:
            raise ModelValidationError("Audit reason and safe target are required.")
        if not all(isinstance(item, str) and item for item in self.policy_ids):
            raise ModelValidationError("policy_ids must contain stable identifiers.")
        object.__setattr__(
            self, "occurred_at", validate_utc_timestamp(self.occurred_at, "occurred_at")
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "event_id": str(self.event_id),
            "event": self.event.value,
            "session_id": str(self.session_id) if self.session_id else None,
            "command_id": str(self.command_id) if self.command_id else None,
            "action_id": str(self.action_id) if self.action_id else None,
            "intent": self.intent.value,
            "risk_level": self.risk_level.value,
            "decision": self.decision.value,
            "reason_code": self.reason_code,
            "policy_ids": list(self.policy_ids),
            "confirmation_status": self.confirmation_status.value,
            "occurred_at": serialize_value(self.occurred_at),
            "safe_target_description": self.safe_target_description,
        }


class InMemorySafetyAudit:
    """Thread-safe process-local audit sink; no records are persisted in Phase 7."""

    def __init__(self) -> None:
        self._records: list[SafetyAuditRecord] = []
        self._lock = RLock()

    @property
    def records(self) -> tuple[SafetyAuditRecord, ...]:
        with self._lock:
            return tuple(self._records)

    def append(self, record: SafetyAuditRecord) -> None:
        if not isinstance(record, SafetyAuditRecord):
            raise ModelValidationError("audit record must be a SafetyAuditRecord.")
        with self._lock:
            self._records.append(record)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
