from datetime import UTC, datetime
from uuid import uuid4

from omega.models import ActionResult, IntentType, RiskLevel
from omega.safety import (
    ConfirmationManager,
    ConfirmationOutcome,
    ResourceFingerprint,
)


def _create(manager, context, *, phrase="confirm move notes.txt"):
    return manager.create(
        session_id=context.session_id,
        command=context.command,
        action=context.action,
        display_target="notes.txt",
        prompt="Confirm move.",
        expected_confirmation=phrase,
        expected_cancellation="cancel move notes.txt",
        fingerprint=ResourceFingerprint("file", "notes", True),
        executor=lambda: ActionResult.success_result(
            context.action.action_id, "moved", "moved"
        ),
        revalidator=lambda: ResourceFingerprint("file", "notes", True),
        context=context,
    )


def test_exact_case_insensitive_confirmation_is_consumed_once(context_factory):
    context = context_factory(IntentType.MOVE_FILE, risk=RiskLevel.HIGH)
    manager = ConfirmationManager()
    first, _ = _create(manager, context)

    approved = manager.resolve("  CONFIRM MOVE NOTES.TXT  ", context.session_id)
    replay = manager.resolve("confirm move notes.txt", context.session_id)

    assert len(first.confirmation_id) >= 16
    assert approved.outcome is ConfirmationOutcome.APPROVED
    assert replay.outcome is ConfirmationOutcome.REPLAYED


def test_wrong_generic_partial_and_different_session_do_not_approve(context_factory):
    context = context_factory(IntentType.MOVE_FILE, risk=RiskLevel.HIGH)
    manager = ConfirmationManager(maximum_attempts=5)
    _create(manager, context)
    assert (
        manager.resolve("yes", context.session_id).outcome
        is ConfirmationOutcome.MISMATCH
    )
    assert (
        manager.resolve("confirm move", context.session_id).outcome
        is ConfirmationOutcome.MISMATCH
    )
    assert (
        manager.resolve("confirm move notes.txt", uuid4()).outcome
        is ConfirmationOutcome.SESSION_MISMATCH
    )
    assert manager.get(context.session_id) is not None


def test_attempt_limit_cancellation_and_replacement(context_factory):
    first = context_factory(IntentType.MOVE_FILE, risk=RiskLevel.HIGH)
    second = context_factory(IntentType.MOVE_FOLDER, risk=RiskLevel.HIGH)
    manager = ConfirmationManager(maximum_attempts=2)
    _create(manager, first)
    outcome = manager.resolve("confirm wrong", first.session_id)
    assert outcome.outcome is ConfirmationOutcome.MISMATCH
    outcome = manager.resolve("confirm wrong again", first.session_id)
    assert outcome.outcome is ConfirmationOutcome.ATTEMPTS_EXCEEDED

    _create(manager, first)
    _, replaced = _create(manager, second, phrase="confirm move folder projects")
    assert replaced is None  # different session IDs keep independent scope
    cancelled = manager.resolve("cancel move notes.txt", first.session_id)
    assert cancelled.outcome is ConfirmationOutcome.CANCELLED


def test_new_pending_action_in_same_session_cancels_old(context_factory):
    session_id = uuid4()
    first = context_factory(
        IntentType.MOVE_FILE, risk=RiskLevel.HIGH, session_id=session_id
    )
    second = context_factory(
        IntentType.MOVE_FOLDER, risk=RiskLevel.HIGH, session_id=session_id
    )
    manager = ConfirmationManager()
    _create(manager, first)
    _, replaced = _create(manager, second, phrase="confirm move folder projects")
    assert replaced is not None and replaced.action_id == first.action.action_id


def test_expiry_uses_injected_monotonic_clock_without_sleep(context_factory):
    clock = [0.0]
    manager = ConfirmationManager(
        timeout_seconds=5,
        monotonic_clock=lambda: clock[0],
        now_provider=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )
    context = context_factory(IntentType.MOVE_FILE, risk=RiskLevel.HIGH)
    _create(manager, context)
    clock[0] = 5.1
    assert (
        manager.resolve("confirm move notes.txt", context.session_id).outcome
        is ConfirmationOutcome.EXPIRED
    )
