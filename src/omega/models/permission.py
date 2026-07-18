"""Data representation of future permission-policy evaluations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from omega.core.exceptions import ModelValidationError
from omega.models._serialization import (
    JsonValue,
    parse_utc_timestamp,
    serialize_value,
    utc_now,
    validate_json_mapping,
    validate_utc_timestamp,
)
from omega.models.enums import PermissionDecision, RiskLevel


@dataclass
class PermissionEvaluation:
    """A future safety policy's non-executing permission decision record."""

    decision: PermissionDecision
    risk_level: RiskLevel
    reason: str
    policy_name: str
    requires_confirmation: bool = False
    evaluated_at: datetime = field(default_factory=utc_now)
    details: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.decision, PermissionDecision):
            raise ModelValidationError("decision must be a PermissionDecision.")
        if not isinstance(self.risk_level, RiskLevel):
            raise ModelValidationError("risk_level must be a RiskLevel.")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ModelValidationError(
                "reason must be a non-empty human-readable string."
            )
        if not isinstance(self.policy_name, str) or not self.policy_name.strip():
            raise ModelValidationError("policy_name must be a non-empty string.")
        if not isinstance(self.requires_confirmation, bool):
            raise ModelValidationError("requires_confirmation must be a boolean.")
        if self.decision is PermissionDecision.ALLOW and self.requires_confirmation:
            raise ModelValidationError("ALLOW decisions must not require confirmation.")
        if (
            self.decision is PermissionDecision.REQUIRE_CONFIRMATION
            and not self.requires_confirmation
        ):
            raise ModelValidationError(
                "REQUIRE_CONFIRMATION decisions must require confirmation."
            )
        if self.decision is PermissionDecision.DENY and self.requires_confirmation:
            raise ModelValidationError("DENY decisions must not require confirmation.")
        self.evaluated_at = validate_utc_timestamp(self.evaluated_at, "evaluated_at")
        self.details = validate_json_mapping(self.details, "details")

    def to_dict(self) -> dict[str, JsonValue]:
        """Serialize the evaluation into JSON-compatible data."""
        return {
            "decision": self.decision.value,
            "risk_level": self.risk_level.value,
            "reason": self.reason,
            "policy_name": self.policy_name,
            "requires_confirmation": self.requires_confirmation,
            "evaluated_at": serialize_value(self.evaluated_at),
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PermissionEvaluation:
        """Deserialize a previously serialized evaluation."""
        try:
            return cls(
                decision=PermissionDecision(data["decision"]),
                risk_level=RiskLevel(data["risk_level"]),
                reason=data["reason"],
                policy_name=data["policy_name"],
                requires_confirmation=data.get("requires_confirmation", False),
                evaluated_at=parse_utc_timestamp(data["evaluated_at"], "evaluated_at"),
                details=data.get("details", {}),
            )
        except KeyError as error:
            raise ModelValidationError(
                f"Missing permission evaluation field: {error.args[0]}."
            ) from error
