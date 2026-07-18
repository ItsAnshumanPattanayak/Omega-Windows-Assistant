from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from omega.core.exceptions import ModelValidationError
from omega.models import (
    ConfirmationStatus,
    IntentType,
    PermissionDecision,
    RiskLevel,
)
from omega.safety import PendingConfirmation, ResourceFingerprint, SafetyEvaluation


def test_valid_evaluation_serializes_stable_values():
    evaluation = SafetyEvaluation(
        PermissionDecision.ALLOW,
        RiskLevel.LOW,
        "FILE_READ_ALLOWED",
        "Validated read.",
        "Reading the file is allowed.",
        matched_policies=("SAFETY-FILE-READ-001",),
    )
    data = evaluation.to_dict()
    assert data["decision"] == "allow"
    assert data["risk_level"] == "low"
    assert data["evaluated_at"].endswith("+00:00")


@pytest.mark.parametrize(
    "values, message",
    [
        (
            dict(
                decision=PermissionDecision.ALLOW,
                risk_level=RiskLevel.LOW,
                reason_code="bad code",
                reason="x",
                user_message="x",
            ),
            "reason_code",
        ),
        (
            dict(
                decision=PermissionDecision.DENY,
                risk_level=RiskLevel.CRITICAL,
                reason_code="DENIED",
                reason="x",
                user_message="x",
            ),
            "identify a policy",
        ),
        (
            dict(
                decision=PermissionDecision.REQUIRE_CONFIRMATION,
                risk_level=RiskLevel.HIGH,
                reason_code="CONFIRM_REQUIRED",
                reason="x",
                user_message="x",
                requires_confirmation=False,
            ),
            "agree",
        ),
    ],
)
def test_invalid_evaluation_combinations_fail(values, message):
    with pytest.raises(ModelValidationError, match=message):
        SafetyEvaluation(**values)


def test_pending_confirmation_never_serializes_fingerprint_payload():
    now = datetime.now(UTC)
    pending = PendingConfirmation(
        "secure-confirmation-id-123",
        uuid4(),
        uuid4(),
        uuid4(),
        IntentType.WRITE_FILE,
        ResourceFingerprint("file", "private-fingerprint", True, size=10),
        "notes.txt on Desktop",
        "Confirm replacement.",
        "confirm overwrite notes.txt on desktop",
        "cancel overwrite notes.txt on desktop",
        now,
        now + timedelta(seconds=30),
        ConfirmationStatus.PENDING,
    )
    serialized = pending.to_dict()
    assert "target_fingerprint" not in serialized
    assert "private-fingerprint" not in str(serialized)
