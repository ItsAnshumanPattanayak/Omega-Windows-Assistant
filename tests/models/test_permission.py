"""Tests for future permission evaluation records."""

import pytest

from omega.core.exceptions import ModelValidationError
from omega.models import PermissionDecision, PermissionEvaluation, RiskLevel


def test_permission_decisions_validate_and_round_trip() -> None:
    allowed = PermissionEvaluation(
        PermissionDecision.ALLOW, RiskLevel.LOW, "Safe", "safe_read"
    )
    confirm = PermissionEvaluation(
        PermissionDecision.REQUIRE_CONFIRMATION,
        RiskLevel.HIGH,
        "Confirm",
        "delete",
        True,
    )
    denied = PermissionEvaluation(
        PermissionDecision.DENY, RiskLevel.CRITICAL, "Blocked", "system_path"
    )
    assert (
        PermissionEvaluation.from_dict(allowed.to_dict()).to_dict() == allowed.to_dict()
    )
    assert confirm.requires_confirmation is True
    assert denied.requires_confirmation is False


def test_permission_rejects_inconsistent_confirmation() -> None:
    with pytest.raises(ModelValidationError):
        PermissionEvaluation(
            PermissionDecision.ALLOW, RiskLevel.LOW, "Safe", "read", True
        )
    with pytest.raises(ModelValidationError):
        PermissionEvaluation(
            PermissionDecision.REQUIRE_CONFIRMATION, RiskLevel.HIGH, "Confirm", "write"
        )
