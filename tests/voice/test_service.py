from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event, Thread
from time import monotonic
from uuid import UUID, uuid4

import pytest

from omega.core.exceptions import (
    RecognitionError,
    SpeechSynthesisError,
    VoiceInitializationError,
)
from omega.models import CommandSource
from omega.session import SessionState
from omega.voice.configuration import VoiceConfiguration
from omega.voice.models import TranscriptionResult, VoiceEvent, VoiceState
from omega.voice.service import VoiceService


def enabled_configuration(**overrides: object) -> VoiceConfiguration:
    values: dict[str, object] = {"enabled": True, **overrides}
    return VoiceConfiguration.from_mapping(
        values,
        wake_phrase="Hello Omega",
        shutdown_phrase="Shut down Omega",
        model_root=Path.cwd() / "data" / "voice_models",
    )


class FakeAudio:
    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0
        self.release = Event()

    def start(self) -> None:
        self.started += 1

    def read(self, timeout_seconds: float) -> bytes | None:
        self.release.wait(min(timeout_seconds, 0.01))
        return None

    def stop(self) -> None:
        self.stopped += 1
        self.release.set()

    def list_devices(self) -> tuple[object, ...]:
        return ()


class FakeRecognizer:
    def __init__(self, *, failure: bool = False) -> None:
        self.closed = 0
        self.failure = failure

    def transcribe(self, audio: bytes) -> TranscriptionResult | None:
        if self.failure:
            raise RecognitionError("failed")
        return None

    def close(self) -> None:
        self.closed += 1


class FakeSpeaker:
    def __init__(self, *, fail_speak: bool = False) -> None:
        self.started = 0
        self.spoken: list[str] = []
        self.cancelled = 0
        self.closed = 0
        self.fail_speak = fail_speak

    def start(self) -> None:
        self.started += 1

    def speak(self, text: str) -> bool:
        if self.fail_speak:
            raise SpeechSynthesisError("output failed")
        self.spoken.append(text)
        return True

    def cancel(self) -> None:
        self.cancelled += 1

    def close(self) -> None:
        self.closed += 1


@dataclass
class FakePending:
    expected_confirmation: str = "confirm close notepad"
    expected_cancellation: str = "cancel close notepad"


class FakeConfirmations:
    def __init__(self) -> None:
        self.pending: FakePending | None = None

    def get(self, session_id: UUID) -> FakePending | None:
        del session_id
        return self.pending


class FakeGateway:
    def __init__(self) -> None:
        self.confirmations = FakeConfirmations()


class FakeSession:
    def __init__(self) -> None:
        self.state = SessionState.INACTIVE
        self.session_id: UUID | None = None
        self.calls: list[tuple[str, CommandSource]] = []
        self.timeout_message: str | None = None

    def handle_input(self, text: str, *, source: CommandSource) -> str:
        self.calls.append((text, source))
        if text.casefold() == "hello omega":
            self.state = SessionState.ACTIVE
            self.session_id = uuid4()
            return "Good morning, Anshuman. How can I help you?"
        if text.casefold() == "shut down omega":
            self.state = SessionState.TERMINATED
            return "Shutting down. Have a good day, Anshuman."
        return f"Processed: {text}"

    def check_timeout(self) -> str | None:
        result = self.timeout_message
        self.timeout_message = None
        if result is not None:
            self.state = SessionState.INACTIVE
        return result

    def deactivate_for_timeout(self) -> str:
        self.state = SessionState.INACTIVE
        self.session_id = None
        return (
            "Omega became inactive because the session timed out. "
            'Say "Hello Omega" to activate me again.'
        )


def result(
    text: str,
    confidence: float = 0.95,
    *,
    final: bool = True,
    result_id: UUID | None = None,
) -> TranscriptionResult:
    return TranscriptionResult.now(
        text,
        text.casefold(),
        confidence,
        is_final=final,
        result_id=result_id,
    )


def service_components(
    *,
    configuration: VoiceConfiguration | None = None,
    speaker: FakeSpeaker | None = None,
) -> tuple[
    VoiceService,
    FakeSession,
    FakeGateway,
    FakeAudio,
    FakeRecognizer,
    FakeSpeaker,
    list[VoiceEvent],
]:
    session = FakeSession()
    gateway = FakeGateway()
    audio = FakeAudio()
    recognizer = FakeRecognizer()
    output = speaker or FakeSpeaker()
    events: list[VoiceEvent] = []
    service = VoiceService(
        configuration or enabled_configuration(),
        session,  # type: ignore[arg-type]
        gateway,  # type: ignore[arg-type]
        audio,  # type: ignore[arg-type]
        recognizer,
        output,
        event_sink=events.append,
    )
    return service, session, gateway, audio, recognizer, output, events


def test_disabled_voice_does_not_initialize_audio() -> None:
    service, _, _, audio, _, _, _ = service_components(
        configuration=enabled_configuration(enabled=False)
    )

    with pytest.raises(VoiceInitializationError, match="disabled"):
        service.start()
    assert audio.started == 0
    assert service.state is VoiceState.DISABLED


def test_explicit_start_and_stop_release_resources_once() -> None:
    service, _, _, audio, recognizer, speaker, _ = service_components()

    service.start()
    assert service.running
    assert audio.started == 1
    assert speaker.started == 1
    assert service.state is VoiceState.PASSIVE_LISTENING
    service.stop()
    service.stop()

    assert not service.running
    assert audio.stopped >= 1
    assert recognizer.closed >= 1
    assert speaker.closed >= 1
    assert service.state is VoiceState.IDLE


def test_duplicate_start_is_rejected() -> None:
    service, *_ = service_components()
    service.start()
    try:
        with pytest.raises(VoiceInitializationError, match="already running"):
            service.start()
    finally:
        service.stop()


def test_wake_only_uses_existing_session_and_speaks_greeting() -> None:
    service, session, _, _, _, speaker, events = service_components()
    service.start()
    try:
        event = service.process_transcription(result("Hello Omega"))
    finally:
        service.stop()

    assert event is not None
    assert session.calls == [("Hello Omega", CommandSource.VOICE)]
    assert speaker.spoken == ["Good morning, Anshuman. How can I help you?"]
    assert any(item.transcript == "Hello Omega" for item in events)


def test_wake_plus_command_is_deterministic_and_each_input_runs_once() -> None:
    service, session, *_ = service_components()
    service.start()
    try:
        event = service.process_transcription(result("Hello Omega, open Chrome"))
    finally:
        service.stop()

    assert event is not None
    assert session.calls == [
        ("Hello Omega", CommandSource.VOICE),
        ("open Chrome", CommandSource.VOICE),
    ]
    assert event.response == "Processed: open Chrome"


def test_active_command_does_not_require_wake_phrase() -> None:
    service, session, *_ = service_components()
    session.state = SessionState.ACTIVE
    session.session_id = uuid4()
    service.start()
    try:
        event = service.process_transcription(result("Open Chrome"))
    finally:
        service.stop()

    assert event is not None
    assert session.calls == [("Open Chrome", CommandSource.VOICE)]


@pytest.mark.parametrize(
    "transcription",
    [
        result("", 1.0),
        result("Open Chrome", 1.0, final=False),
        result("Open Chrome", 0.49),
    ],
)
def test_uncertain_or_incomplete_speech_never_reaches_session(
    transcription: TranscriptionResult,
) -> None:
    service, session, *_ = service_components()
    service.start()
    try:
        service.process_transcription(transcription)
    finally:
        service.stop()

    assert session.calls == []


def test_overlong_transcript_is_rejected() -> None:
    service, session, *_ = service_components(
        configuration=enabled_configuration(maximum_transcript_characters=5)
    )
    service.start()
    try:
        service.process_transcription(result("sixteen characters"))
    finally:
        service.stop()

    assert session.calls == []


def test_duplicate_final_result_id_is_processed_at_most_once() -> None:
    service, session, *_ = service_components()
    session.state = SessionState.ACTIVE
    session.session_id = uuid4()
    duplicate_id = uuid4()
    transcription = result("Open Chrome", result_id=duplicate_id)
    service.start()
    try:
        assert service.process_transcription(transcription) is not None
        assert service.process_transcription(transcription) is None
    finally:
        service.stop()

    assert session.calls == [("Open Chrome", CommandSource.VOICE)]


def test_low_confidence_or_wrong_confirmation_cannot_approve() -> None:
    service, session, gateway, *_ = service_components()
    session.state = SessionState.ACTIVE
    session.session_id = uuid4()
    gateway.confirmations.pending = FakePending()
    service.start()
    try:
        low = service.process_transcription(result("confirm close notepad", 0.84))
        wrong = service.process_transcription(result("yes", 1.0))
    finally:
        service.stop()

    assert low is not None
    assert wrong is not None
    assert session.calls == []


def test_confirmation_does_not_relax_exact_punctuation_contract() -> None:
    service, session, gateway, *_ = service_components()
    session.state = SessionState.ACTIVE
    session.session_id = uuid4()
    gateway.confirmations.pending = FakePending()
    service.start()
    try:
        service.process_transcription(result("confirm close notepad!", 1.0))
    finally:
        service.stop()

    assert session.calls == []


def test_exact_high_confidence_confirmation_uses_existing_contract() -> None:
    service, session, gateway, *_ = service_components()
    session.state = SessionState.ACTIVE
    session.session_id = uuid4()
    gateway.confirmations.pending = FakePending()

    original_handle = session.handle_input

    def consume(text: str, *, source: CommandSource) -> str:
        gateway.confirmations.pending = None
        return original_handle(text, source=source)

    session.handle_input = consume  # type: ignore[method-assign]
    service.start()
    try:
        event = service.process_transcription(result("confirm close notepad", 0.9))
    finally:
        service.stop()

    assert event is not None
    assert session.calls == [("confirm close notepad", CommandSource.VOICE)]


def test_exact_cancellation_is_supported_without_implicit_approval() -> None:
    service, session, gateway, *_ = service_components()
    session.state = SessionState.ACTIVE
    session.session_id = uuid4()
    gateway.confirmations.pending = FakePending()
    service.start()
    try:
        service.process_transcription(result("cancel close notepad", 0.9))
    finally:
        service.stop()

    assert session.calls == [("cancel close notepad", CommandSource.VOICE)]


def test_speaker_failure_does_not_repeat_command() -> None:
    service, session, *_ = service_components(speaker=FakeSpeaker(fail_speak=True))
    session.state = SessionState.ACTIVE
    session.session_id = uuid4()
    service.start()
    try:
        service.process_transcription(result("Open Chrome"))
    finally:
        service.stop()

    assert session.calls == [("Open Chrome", CommandSource.VOICE)]


def test_shutdown_uses_session_handler_and_stops_listener() -> None:
    service, session, _, audio, _, speaker, _ = service_components()
    session.state = SessionState.ACTIVE
    session.session_id = uuid4()
    service.start()
    service.process_transcription(result("Shut down Omega"))
    deadline = monotonic() + 1
    while service.running and monotonic() < deadline:
        Event().wait(0.01)
    service.stop()

    assert session.state is SessionState.TERMINATED
    assert session.calls == [("Shut down Omega", CommandSource.VOICE)]
    assert speaker.spoken == ["Shutting down. Have a good day, Anshuman."]
    assert audio.stopped >= 1


def test_runtime_speech_preference_can_only_disable_output() -> None:
    service, session, _, _, _, speaker, _ = service_components()
    session.state = SessionState.ACTIVE
    session.session_id = uuid4()
    service.set_speech_enabled(False)
    service.start()
    try:
        service.process_transcription(result("status"))
    finally:
        service.stop()

    assert speaker.cancelled >= 1
    assert speaker.spoken == []


def test_configured_voice_timeout_returns_to_passive_without_real_sleep() -> None:
    clock = [10.0]
    session = FakeSession()
    gateway = FakeGateway()
    audio = FakeAudio()
    recognizer = FakeRecognizer()
    events: list[VoiceEvent] = []
    service = VoiceService(
        enabled_configuration(active_session_timeout_seconds=1),
        session,  # type: ignore[arg-type]
        gateway,  # type: ignore[arg-type]
        audio,  # type: ignore[arg-type]
        recognizer,
        FakeSpeaker(),
        event_sink=events.append,
        monotonic_clock=lambda: clock[0],
    )
    service.start()
    service.process_transcription(result("Hello Omega"))
    clock[0] = 12.0
    deadline = monotonic() + 1
    while session.state is SessionState.ACTIVE and monotonic() < deadline:
        Event().wait(0.01)
    service.stop()

    assert session.state is SessionState.INACTIVE
    assert any("timed out" in (event.response or "") for event in events)


def test_two_distinct_voice_callbacks_cannot_process_concurrently() -> None:
    service, session, *_ = service_components()
    session.state = SessionState.ACTIVE
    session.session_id = uuid4()
    entered = Event()
    release = Event()
    original = session.handle_input

    def slow(text: str, *, source: CommandSource) -> str:
        entered.set()
        release.wait(1)
        return original(text, source=source)

    session.handle_input = slow  # type: ignore[method-assign]
    service.start()
    worker = Thread(target=lambda: service.process_transcription(result("status")))
    worker.start()
    assert entered.wait(1)
    busy = service.process_transcription(result("show history"))
    release.set()
    worker.join(1)
    service.stop()

    assert busy is not None
    assert "already processing" in busy.message
    assert session.calls == [("status", CommandSource.VOICE)]
