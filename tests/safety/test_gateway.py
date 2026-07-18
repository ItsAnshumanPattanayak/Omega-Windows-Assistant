from omega.models import ActionResult, IntentType, PermissionDecision, RiskLevel
from omega.safety import (
    ConfirmationManager,
    ConfirmationSpec,
    InMemorySafetyAudit,
    ResourceFingerprint,
    SafeExecutionGateway,
    SafetyAuditEvent,
)


def test_allowed_action_dispatches_once_and_preserves_ids(context_factory):
    context = context_factory(IntentType.READ_FILE, risk=RiskLevel.LOW)
    calls = []
    gateway = SafeExecutionGateway()

    result = gateway.submit(
        context,
        lambda: calls.append("read")
        or ActionResult.success_result(context.action.action_id, "read", "read"),
    )

    assert result.result.success
    assert result.result.action_id == context.action.action_id
    assert calls == ["read"]
    assert result.evaluation.decision is PermissionDecision.ALLOW


def test_denied_and_unknown_actions_never_dispatch(context_factory):
    calls = []
    gateway = SafeExecutionGateway()
    deletion = context_factory(IntentType.DELETE_FILE, risk=RiskLevel.LOW)

    result = gateway.submit(
        deletion,
        lambda: calls.append("delete")
        or ActionResult.success_result(deletion.action.action_id, "bad", "bad"),
    )

    assert not result.result.success
    assert "Phase 8" in result.user_message
    assert calls == []


def test_confirmation_dispatches_once_after_exact_match(context_factory):
    context = context_factory(IntentType.MOVE_FILE, risk=RiskLevel.HIGH)
    fingerprint = ResourceFingerprint("file", "notes", True)
    calls = []
    gateway = SafeExecutionGateway()
    requested = gateway.submit(
        context,
        lambda: calls.append("move")
        or ActionResult.success_result(context.action.action_id, "moved", "moved"),
        confirmation=ConfirmationSpec(
            "notes.txt",
            'Move requires confirmation. Type "confirm move notes.txt".',
            "confirm move notes.txt",
            "cancel move notes.txt",
        ),
        fingerprint=fingerprint,
        revalidator=lambda: fingerprint,
    )
    assert not requested.result.success and calls == []

    confirmed = gateway.handle_confirmation(
        "CONFIRM MOVE notes.txt", context.session_id
    )
    replay = gateway.handle_confirmation("confirm move notes.txt", context.session_id)

    assert confirmed is not None and confirmed.result.success
    assert replay is not None and not replay.result.success
    assert calls == ["move"]


def test_changed_resource_and_executor_exception_fail_safely(context_factory):
    context = context_factory(IntentType.MOVE_FOLDER, risk=RiskLevel.HIGH)
    initial = ResourceFingerprint("folder", "projects", True, item_count=1)
    changed = ResourceFingerprint("folder", "projects", True, item_count=2)
    gateway = SafeExecutionGateway()
    calls = []
    gateway.submit(
        context,
        lambda: calls.append("move")
        or ActionResult.success_result(context.action.action_id, "moved", "moved"),
        confirmation=ConfirmationSpec(
            "Projects",
            'Confirm with "confirm move folder projects".',
            "confirm move folder projects",
            "cancel move folder projects",
        ),
        fingerprint=initial,
        revalidator=lambda: changed,
    )
    result = gateway.handle_confirmation(
        "confirm move folder projects", context.session_id
    )
    assert result is not None and not result.result.success
    assert "target changed" in result.user_message
    assert calls == []

    read = context_factory(IntentType.READ_FILE)
    failed = gateway.submit(
        read, lambda: (_ for _ in ()).throw(RuntimeError("private"))
    )
    assert not failed.result.success
    assert "private" not in failed.user_message


def test_audit_is_redacted_and_records_decision_lifecycle(context_factory):
    audit = InMemorySafetyAudit()
    gateway = SafeExecutionGateway(audit=audit)
    context = context_factory(
        IntentType.READ_FILE,
        logical_source="Desktop/notes.txt",
    )
    gateway.submit(
        context,
        lambda: ActionResult.success_result(context.action.action_id, "read", "read"),
    )
    assert [record.event for record in audit.records] == [
        SafetyAuditEvent.EVALUATED,
        SafetyAuditEvent.ALLOWED,
        SafetyAuditEvent.EXECUTION_STARTED,
        SafetyAuditEvent.EXECUTION_FINISHED,
    ]
    assert all("E:\\" not in str(record.to_dict()) for record in audit.records)


def test_expired_confirmation_does_not_execute(context_factory):
    clock = [0.0]
    confirmations = ConfirmationManager(
        timeout_seconds=1, monotonic_clock=lambda: clock[0]
    )
    gateway = SafeExecutionGateway(confirmations=confirmations)
    context = context_factory(IntentType.MOVE_FILE, risk=RiskLevel.HIGH)
    calls = []
    gateway.submit(
        context,
        lambda: calls.append("move")
        or ActionResult.success_result(context.action.action_id, "moved", "moved"),
        confirmation=ConfirmationSpec(
            "notes",
            "confirm move notes",
            "confirm move notes",
            "cancel move notes",
        ),
    )
    clock[0] = 2
    expired = gateway.handle_confirmation("confirm move notes", context.session_id)
    assert expired is not None and "expired" in expired.user_message
    assert calls == []
