from datetime import UTC, datetime, timedelta

import pytest

from omega.core.exceptions import ModelValidationError, VoiceStateError
from omega.voice.models import (
    TranscriptionResult,
    VoiceEvent,
    VoiceState,
    VoiceStateMachine,
)
from omega.voice.wake_word import WakeWordDetector, normalize_system_phrase


def test_voice_state_values_are_stable() -> None:
    assert VoiceState.PASSIVE_LISTENING.value == "passive_listening"
    assert VoiceState.AWAITING_CONFIRMATION.value == "awaiting_confirmation"
    assert len({state.value for state in VoiceState}) == len(VoiceState)


def test_state_machine_accepts_lifecycle_and_idempotent_state() -> None:
    states = VoiceStateMachine()

    assert (
        states.transition_to(VoiceState.PASSIVE_LISTENING)
        is VoiceState.PASSIVE_LISTENING
    )
    assert states.transition_to(VoiceState.TRANSCRIBING) is VoiceState.TRANSCRIBING
    assert states.transition_to(VoiceState.WAKE_DETECTED) is VoiceState.WAKE_DETECTED
    assert (
        states.transition_to(VoiceState.ACTIVE_LISTENING) is VoiceState.ACTIVE_LISTENING
    )
    assert states.transition_to(VoiceState.STOPPING) is VoiceState.STOPPING
    assert states.transition_to(VoiceState.IDLE) is VoiceState.IDLE
    assert states.transition_to(VoiceState.IDLE) is VoiceState.IDLE


@pytest.mark.parametrize(
    "initial, target",
    [
        (VoiceState.DISABLED, VoiceState.PASSIVE_LISTENING),
        (VoiceState.STOPPING, VoiceState.ACTIVE_LISTENING),
        (VoiceState.IDLE, VoiceState.PROCESSING_COMMAND),
        (VoiceState.UNAVAILABLE, VoiceState.ACTIVE_LISTENING),
    ],
)
def test_invalid_state_transitions_are_rejected(
    initial: VoiceState,
    target: VoiceState,
) -> None:
    with pytest.raises(VoiceStateError, match="Cannot transition"):
        VoiceStateMachine(initial).transition_to(target)


def test_transcription_model_accepts_valid_utc_data() -> None:
    result = TranscriptionResult.now("Open Chrome", "open chrome", 0.9)

    assert result.is_final
    assert result.started_at.tzinfo is UTC
    assert result.completed_at >= result.started_at
    assert result.result_id


@pytest.mark.parametrize("confidence", [-0.1, 1.1, True])
def test_transcription_rejects_invalid_confidence(confidence: object) -> None:
    now = datetime.now(UTC)
    with pytest.raises(ModelValidationError, match="confidence"):
        TranscriptionResult(
            "text",
            "text",
            confidence,  # type: ignore[arg-type]
            True,
            now,
            now,
            0,
            "test",
        )


def test_transcription_rejects_time_reversal_and_naive_time() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ModelValidationError, match="must not precede"):
        TranscriptionResult(
            "text", "text", 1.0, True, now, now - timedelta(seconds=1), 0, "test"
        )
    with pytest.raises(ModelValidationError, match="timezone-aware"):
        TranscriptionResult(
            "text",
            "text",
            1.0,
            True,
            datetime.now(),
            datetime.now(),
            0,
            "test",
        )


def test_voice_event_serialization_is_safe() -> None:
    event = VoiceEvent(
        VoiceState.ACTIVE_LISTENING,
        "Ready",
        "Open Chrome",
        "Opened Chrome.",
    )

    assert event.to_dict()["state"] == "active_listening"
    assert event.to_dict()["transcript"] == "Open Chrome"
    assert isinstance(event.to_dict()["occurred_at"], str)


@pytest.mark.parametrize(
    "spoken",
    [
        "Hello Omega",
        "hello omega",
        "  HELLO   OMEGA  ",
        "Hello Omega!",
        ", Hello Omega?",
    ],
)
def test_wake_phrase_accepts_safe_variations(spoken: str) -> None:
    detector = WakeWordDetector("Hello Omega", 0.5)

    assert detector.detect(spoken, 0.9).detected


@pytest.mark.parametrize(
    "spoken",
    [
        "Hello",
        "Omega",
        "Say hello Omega",
        "Hello Omegabyte",
        "Hello Omega please open Chrome",
        "unrelated words",
    ],
)
def test_wake_phrase_rejects_partial_and_unrelated_text(spoken: str) -> None:
    detector = WakeWordDetector("Hello Omega", 0.5)

    assert not detector.detect(spoken, 0.9).detected


def test_wake_phrase_requires_confidence_and_splits_exact_command() -> None:
    detector = WakeWordDetector("Hello Omega", 0.5)

    assert not detector.detect("Hello Omega", 0.49).detected
    match = detector.detect("Hello Omega, open Chrome", 0.9)
    assert match.detected
    assert match.command == "open Chrome"


def test_phrase_normalization_does_not_remove_internal_punctuation() -> None:
    assert normalize_system_phrase(" Hello   Omega! ") == "hello omega"
    assert normalize_system_phrase("Hello-Omega") == "hello-omega"
