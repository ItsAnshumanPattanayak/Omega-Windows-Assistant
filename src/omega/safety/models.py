"""Typed, non-executing records used by Omega's central safety boundary."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import UUID

from omega.core.exceptions import ModelValidationError
from omega.models import (
    Action,
    ConfirmationStatus,
    IntentType,
    PermissionDecision,
    RiskLevel,
    UserCommand,
)
from omega.models._serialization import (
    JsonValue,
    serialize_value,
    utc_now,
    validate_json_mapping,
    validate_utc_timestamp,
)

_REASON_CODE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")


@dataclass(frozen=True)
class SafetyContext:
    """All data needed to evaluate one action without executing it.

    Absolute paths are retained only in memory for canonical safety checks.  They
    are deliberately omitted from :meth:`to_dict` so normal audit serialization
    cannot disclose private filesystem locations.
    """

    command: UserCommand
    action: Action
    session_id: UUID | None = None
    platform: str = "unknown"
    application_id: str | None = None
    source_path: Path | None = None
    destination_path: Path | None = None
    logical_source: str | None = None
    logical_destination: str | None = None
    target_exists: bool | None = None
    target_type: str | None = None
    requested_at: datetime = field(default_factory=utc_now)
    additional_context: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.command, UserCommand):
            raise ModelValidationError("command must be a UserCommand.")
        if not isinstance(self.action, Action):
            raise ModelValidationError("action must be an Action.")
        if self.command.command_id != self.action.command_id:
            raise ModelValidationError("Action and command IDs must match.")
        if self.session_id is not None and not isinstance(self.session_id, UUID):
            raise ModelValidationError("session_id must be a UUID or None.")
        if not isinstance(self.platform, str) or not self.platform.strip():
            raise ModelValidationError("platform must be a non-empty string.")
        for name in ("application_id", "logical_source", "logical_destination"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ModelValidationError(f"{name} must be non-empty when supplied.")
        if self.target_exists is not None and not isinstance(self.target_exists, bool):
            raise ModelValidationError("target_exists must be a boolean or None.")
        if self.target_type is not None and not isinstance(self.target_type, str):
            raise ModelValidationError("target_type must be a string or None.")
        object.__setattr__(
            self,
            "requested_at",
            validate_utc_timestamp(self.requested_at, "requested_at"),
        )
        object.__setattr__(
            self,
            "additional_context",
            validate_json_mapping(self.additional_context, "additional_context"),
        )

    def to_dict(self) -> dict[str, JsonValue]:
        """Serialize only safe, non-private context data."""
        return {
            "command_id": str(self.command.command_id),
            "action_id": str(self.action.action_id),
            "intent": self.action.intent.value,
            "session_id": str(self.session_id) if self.session_id else None,
            "platform": self.platform,
            "application_id": self.application_id,
            "logical_source": self.logical_source,
            "logical_destination": self.logical_destination,
            "target_exists": self.target_exists,
            "target_type": self.target_type,
            "requested_at": serialize_value(self.requested_at),
            "additional_context": self.additional_context,
        }


@dataclass(frozen=True)
class SafetyEvaluation:
    """Serializable final decision produced by the permission policy engine."""

    decision: PermissionDecision
    risk_level: RiskLevel
    reason_code: str
    reason: str
    user_message: str
    requires_confirmation: bool = False
    confirmation_prompt: str | None = None
    matched_policies: tuple[str, ...] = ()
    denied_by: str | None = None
    evaluated_at: datetime = field(default_factory=utc_now)
    expires_at: datetime | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.decision, PermissionDecision):
            raise ModelValidationError("decision must be a PermissionDecision.")
        if not isinstance(self.risk_level, RiskLevel):
            raise ModelValidationError("risk_level must be a RiskLevel.")
        if not isinstance(self.reason_code, str) or not _REASON_CODE.fullmatch(
            self.reason_code
        ):
            raise ModelValidationError(
                "reason_code must be stable machine-readable text."
            )
        for name in ("reason", "user_message"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ModelValidationError(f"{name} must be a non-empty string.")
        if not isinstance(self.requires_confirmation, bool):
            raise ModelValidationError("requires_confirmation must be a boolean.")
        expected = self.decision is PermissionDecision.REQUIRE_CONFIRMATION
        if self.requires_confirmation != expected:
            raise ModelValidationError(
                "requires_confirmation must agree with the permission decision."
            )
        if expected and (
            not isinstance(self.confirmation_prompt, str)
            or not self.confirmation_prompt.strip()
        ):
            raise ModelValidationError(
                "Confirmation-required evaluations need a confirmation prompt."
            )
        if self.decision is PermissionDecision.DENY and not self.denied_by:
            raise ModelValidationError("Denied evaluations must identify a policy.")
        if not all(isinstance(item, str) and item for item in self.matched_policies):
            raise ModelValidationError("matched_policies must contain policy IDs.")
        object.__setattr__(
            self,
            "evaluated_at",
            validate_utc_timestamp(self.evaluated_at, "evaluated_at"),
        )
        if self.expires_at is not None:
            object.__setattr__(
                self,
                "expires_at",
                validate_utc_timestamp(self.expires_at, "expires_at"),
            )
            if self.expires_at <= self.evaluated_at:
                raise ModelValidationError("expires_at must follow evaluated_at.")
        object.__setattr__(
            self, "metadata", validate_json_mapping(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "decision": self.decision.value,
            "risk_level": self.risk_level.value,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "user_message": self.user_message,
            "requires_confirmation": self.requires_confirmation,
            "confirmation_prompt": self.confirmation_prompt,
            "matched_policies": list(self.matched_policies),
            "denied_by": self.denied_by,
            "evaluated_at": serialize_value(self.evaluated_at),
            "expires_at": serialize_value(self.expires_at),
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class ResourceFingerprint:
    """Bounded resource identity used to detect changes before execution."""

    kind: str
    identifier: str
    exists: bool
    size: int | None = None
    modified_ns: int | None = None
    item_count: int | None = None
    digest: str | None = None

    def __post_init__(self) -> None:
        if not self.kind or not self.identifier:
            raise ModelValidationError("Fingerprint kind and identifier are required.")
        for name in ("size", "modified_ns", "item_count"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or value < 0):
                raise ModelValidationError(f"{name} must be non-negative or None.")


@dataclass(frozen=True)
class PendingConfirmation:
    """Serializable public view of one process-local scoped confirmation."""

    confirmation_id: str
    session_id: UUID
    command_id: UUID
    action_id: UUID
    intent: IntentType
    target_fingerprint: ResourceFingerprint | None
    display_target: str
    prompt: str
    expected_confirmation: str
    expected_cancellation: str
    created_at: datetime
    expires_at: datetime
    status: ConfirmationStatus = ConfirmationStatus.PENDING
    attempt_count: int = 0
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.confirmation_id or len(self.confirmation_id) < 16:
            raise ModelValidationError("confirmation_id must be an unpredictable ID.")
        if not all(
            isinstance(item, UUID)
            for item in (self.session_id, self.command_id, self.action_id)
        ):
            raise ModelValidationError("Confirmation IDs must be UUID values.")
        if not isinstance(self.intent, IntentType):
            raise ModelValidationError("intent must be an IntentType.")
        for name in (
            "display_target",
            "prompt",
            "expected_confirmation",
            "expected_cancellation",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ModelValidationError(f"{name} must be non-empty.")
        if self.attempt_count < 0:
            raise ModelValidationError("attempt_count must be non-negative.")
        object.__setattr__(
            self, "created_at", validate_utc_timestamp(self.created_at, "created_at")
        )
        object.__setattr__(
            self, "expires_at", validate_utc_timestamp(self.expires_at, "expires_at")
        )
        if self.expires_at <= self.created_at:
            raise ModelValidationError("Confirmation expiry must follow creation.")
        object.__setattr__(
            self, "metadata", validate_json_mapping(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, JsonValue]:
        """Serialize without executor callbacks, action payload, or private content."""
        return {
            "confirmation_id": self.confirmation_id,
            "session_id": str(self.session_id),
            "command_id": str(self.command_id),
            "action_id": str(self.action_id),
            "intent": self.intent.value,
            "display_target": self.display_target,
            "prompt": self.prompt,
            "expected_confirmation": self.expected_confirmation,
            "expected_cancellation": self.expected_cancellation,
            "created_at": serialize_value(self.created_at),
            "expires_at": serialize_value(self.expires_at),
            "status": self.status.value,
            "attempt_count": self.attempt_count,
            "metadata": self.metadata,
        }
