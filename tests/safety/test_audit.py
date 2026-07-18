from omega.models import (
    ConfirmationStatus,
    IntentType,
    PermissionDecision,
    RiskLevel,
)
from omega.safety import InMemorySafetyAudit, SafetyAuditEvent, SafetyAuditRecord


def test_audit_defaults_are_independent_and_serializable():
    first = InMemorySafetyAudit()
    second = InMemorySafetyAudit()
    record = SafetyAuditRecord(
        SafetyAuditEvent.DENIED,
        IntentType.DELETE_FILE,
        RiskLevel.CRITICAL,
        PermissionDecision.DENY,
        "PERMANENT_DELETION_DISABLED",
        ("SAFETY-DELETE-DEFER-001",),
        ConfirmationStatus.NOT_REQUIRED,
        "notes.txt on Documents",
    )
    first.append(record)
    assert second.records == ()
    assert record.to_dict()["event"] == "denied"
    assert record.occurred_at.utcoffset() is not None
