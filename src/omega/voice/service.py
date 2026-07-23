"""Voice orchestration over Omega's existing session and safety gateway."""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Callable
from threading import Event, Lock, Thread, current_thread
from time import monotonic
from typing import Final
from uuid import UUID

from omega.core.exceptions import (
    RecognitionError,
    SpeechSynthesisError,
    VoiceError,
    VoiceInitializationError,
)
from omega.models import CommandSource
from omega.safety import PendingConfirmation, SafeExecutionGateway
from omega.session import OmegaSession, SessionState
from omega.voice.configuration import VoiceConfiguration
from omega.voice.models import (
    TranscriptionResult,
    VoiceEvent,
    VoiceState,
    VoiceStateMachine,
)
from omega.voice.protocols import (
    AudioSource,
    SpeechRecognizer,
    SpeechSynthesizer,
    VoiceEventSink,
)
from omega.voice.wake_word import WakeWordDetector

_MAX_DEDUPLICATION_IDS: Final = 64


class VoiceService:
    """Coordinate one listener and route every command through ``OmegaSession``."""

    def __init__(
        self,
        configuration: VoiceConfiguration,
        session: OmegaSession,
        gateway: SafeExecutionGateway,
        audio_source: AudioSource,
        recognizer: SpeechRecognizer,
        speaker: SpeechSynthesizer | None = None,
        *,
        event_sink: VoiceEventSink | None = None,
        logger: logging.Logger | None = None,
        monotonic_clock: Callable[[], float] = monotonic,
    ) -> None:
        self.configuration = configuration
        self.session = session
        self.gateway = gateway
        self.audio_source = audio_source
        self.recognizer = recognizer
        self.speaker = speaker
        initial = VoiceState.IDLE if configuration.enabled else VoiceState.DISABLED
        self._states = VoiceStateMachine(initial)
        self._wake = WakeWordDetector(
            configuration.wake_phrase,
            configuration.minimum_confidence,
        )
        self._event_sink = event_sink
        self._logger = logger or logging.getLogger("omega.voice")
        self._clock = monotonic_clock
        self._stop = Event()
        self._lock = Lock()
        self._processing_lock = Lock()
        self._thread: Thread | None = None
        self._processed_ids: deque[UUID] = deque(maxlen=_MAX_DEDUPLICATION_IDS)
        self._processed_set: set[UUID] = set()
        self._speech_enabled = configuration.speak_responses
        self._last_activity_at: float | None = None

    @property
    def state(self) -> VoiceState:
        return self._states.state

    @property
    def running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def set_speech_enabled(self, enabled: bool) -> None:
        """Allow a runtime UI preference to disable, but not policy-enable, TTS."""

        self._speech_enabled = bool(enabled) and self.configuration.speak_responses
        if not self._speech_enabled and self.speaker is not None:
            self.speaker.cancel()

    def start(self) -> None:
        """Explicitly initialize audio resources and start one listener."""

        if not self.configuration.enabled:
            raise VoiceInitializationError(
                "Voice is disabled. Set voice.enabled to true before starting it."
            )
        if self.state in {VoiceState.UNAVAILABLE, VoiceState.ERROR}:
            self._transition(VoiceState.IDLE)
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise VoiceInitializationError("Voice listening is already running.")
            self._stop.clear()
        try:
            self.audio_source.start()
        except VoiceError:
            self._safe_transition(VoiceState.UNAVAILABLE)
            self._emit("Microphone unavailable.")
            raise
        if self.speaker is not None and self._speech_enabled:
            try:
                self.speaker.start()
            except SpeechSynthesisError:
                self._logger.warning("Local speech output is unavailable.")
                self.speaker = None
        self._transition(VoiceState.PASSIVE_LISTENING)
        worker = Thread(
            target=self._run,
            name="omega-voice-listener",
            daemon=True,
        )
        with self._lock:
            self._thread = worker
        worker.start()
        self._logger.info("Omega voice service started.")
        self._emit("Listening for the configured wake phrase.")

    def stop(self) -> None:
        """Stop listening and release all audio resources idempotently."""

        if self.state is VoiceState.DISABLED:
            return
        self._stop.set()
        if self.state not in {VoiceState.IDLE, VoiceState.UNAVAILABLE}:
            self._safe_transition(VoiceState.STOPPING)
        self.audio_source.stop()
        with self._lock:
            worker = self._thread
            self._thread = None
        if worker is not None and worker is not current_thread():
            worker.join(timeout=5)
        self.recognizer.close()
        if self.speaker is not None:
            self.speaker.close()
        if self.state is not VoiceState.UNAVAILABLE:
            self._safe_transition(VoiceState.IDLE)
        self._logger.info("Omega voice service stopped.")
        self._emit("Voice listening stopped.")

    def process_transcription(self, result: TranscriptionResult) -> VoiceEvent | None:
        """Validate and process one recognizer callback at most once."""

        if not self._processing_lock.acquire(blocking=False):
            return self._emit("Omega is already processing one voice command.")
        try:
            return self._process_transcription(result)
        finally:
            self._processing_lock.release()

    def _process_transcription(
        self,
        result: TranscriptionResult,
    ) -> VoiceEvent | None:
        if self._remembered(result.result_id):
            return None
        if self.state in {
            VoiceState.DISABLED,
            VoiceState.UNAVAILABLE,
            VoiceState.IDLE,
            VoiceState.STOPPING,
            VoiceState.ERROR,
        }:
            return None
        prior = self.state
        self._safe_transition(VoiceState.TRANSCRIBING)
        transcript = result.transcript.strip()
        fallback = (
            VoiceState.AWAITING_CONFIRMATION
            if self._pending_confirmation() is not None
            else (
                VoiceState.ACTIVE_LISTENING
                if self.session.state is SessionState.ACTIVE
                else VoiceState.PASSIVE_LISTENING
            )
        )
        if (
            not result.is_final
            or not transcript
            or len(transcript) > self.configuration.maximum_transcript_characters
        ):
            self._safe_transition(fallback)
            return self._emit(
                "Partial, empty, or overlong speech was ignored.",
                transcript=transcript or None,
            )

        pending = self._pending_confirmation()
        if pending is not None:
            return self._process_confirmation(result, pending)
        if result.confidence < self.configuration.minimum_confidence:
            self._logger.info("Voice transcription rejected due to confidence.")
            self._safe_transition(fallback)
            return self._emit(
                "I could not hear that clearly enough. Please try again.",
                transcript=transcript,
            )
        if self.session.state is not SessionState.ACTIVE:
            match = self._wake.detect(transcript, result.confidence)
            if not match.detected:
                self._safe_transition(VoiceState.PASSIVE_LISTENING)
                return None
            self._safe_transition(VoiceState.WAKE_DETECTED)
            self._logger.info("Configured wake phrase detected.")
            activation = self._forward(self.configuration.wake_phrase)
            self._last_activity_at = self._clock()
            event = self._respond(transcript, activation)
            if match.command is None:
                self._safe_transition(VoiceState.ACTIVE_LISTENING)
                return event
            self._safe_transition(VoiceState.PROCESSING_COMMAND)
            response = self._forward(match.command)
            return self._finish_command(match.command, response)

        if prior is VoiceState.AWAITING_CONFIRMATION:
            self._safe_transition(VoiceState.AWAITING_CONFIRMATION)
        else:
            self._safe_transition(VoiceState.PROCESSING_COMMAND)
        response = self._forward(transcript)
        self._last_activity_at = self._clock()
        return self._finish_command(transcript, response)

    def _process_confirmation(
        self,
        result: TranscriptionResult,
        pending: PendingConfirmation,
    ) -> VoiceEvent:
        expected = pending.expected_confirmation
        cancellation = pending.expected_cancellation
        spoken = self._confirmation_key(result.transcript)
        matches = {
            self._confirmation_key(expected),
            self._confirmation_key(cancellation),
        }
        if (
            result.confidence < self.configuration.confirmation_confidence_threshold
            or spoken not in matches
        ):
            self._logger.info("Voice confirmation rejected safely.")
            self._safe_transition(VoiceState.AWAITING_CONFIRMATION)
            return self._emit(
                "Voice confirmation was not accepted. Say the exact displayed "
                "confirmation or cancellation phrase.",
                transcript=result.transcript,
            )
        self._safe_transition(VoiceState.PROCESSING_COMMAND)
        response = self._forward(result.transcript)
        self._last_activity_at = self._clock()
        return self._finish_command(result.transcript, response)

    def _finish_command(self, transcript: str, response: str) -> VoiceEvent:
        event = self._respond(transcript, response)
        if self.session.state is SessionState.TERMINATED:
            self._stop.set()
            self._safe_transition(VoiceState.STOPPING)
        elif self._pending_confirmation() is not None:
            self._safe_transition(VoiceState.AWAITING_CONFIRMATION)
        else:
            self._safe_transition(VoiceState.ACTIVE_LISTENING)
        return event

    def _forward(self, text: str) -> str:
        return self.session.handle_input(text, source=CommandSource.VOICE)

    def _pending_confirmation(self) -> PendingConfirmation | None:
        session_id = self.session.session_id
        if session_id is None:
            return None
        return self.gateway.confirmations.get(session_id)

    def _respond(self, transcript: str, response: str) -> VoiceEvent:
        if self.speaker is not None and self._speech_enabled:
            self._safe_transition(VoiceState.SPEAKING)
            try:
                if not self.speaker.speak(response):
                    self._logger.warning("Local speech queue is full.")
            except SpeechSynthesisError:
                self._logger.warning("Local speech output failed after command.")
        return self._emit(
            "Voice command processed.",
            transcript=transcript,
            response=response,
        )

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                timeout = (
                    self.configuration.passive_listening_timeout_seconds
                    if self.session.state is not SessionState.ACTIVE
                    else self.configuration.active_listening_timeout_seconds
                )
                audio = self.audio_source.read(timeout)
                if self._stop.is_set():
                    break
                if audio is None:
                    timeout_message = self._check_timeout()
                    if timeout_message is not None:
                        self._respond("", timeout_message)
                    continue
                try:
                    result = self.recognizer.transcribe(audio)
                except RecognitionError:
                    self._logger.warning("Offline recognition failed safely.")
                    self._safe_transition(VoiceState.ERROR)
                    self._emit("Speech recognition failed safely.")
                    self._safe_transition(VoiceState.IDLE)
                    break
                if result is not None:
                    self.process_transcription(result)
        except Exception:
            self._logger.exception("Unexpected voice worker failure.")
            self._safe_transition(VoiceState.ERROR)
            self._emit("Voice listening stopped after an internal error.")
        finally:
            try:
                self.audio_source.stop()
            except Exception:
                self._logger.warning("Microphone cleanup failed safely.")
            self.recognizer.close()
            if self.speaker is not None:
                self.speaker.close()

    def _check_timeout(self) -> str | None:
        if (
            self.session.state is not SessionState.ACTIVE
            or self._last_activity_at is None
            or self._clock() - self._last_activity_at
            <= self.configuration.active_session_timeout_seconds
        ):
            return None
        message = self.session.deactivate_for_timeout()
        self._last_activity_at = None
        if self.configuration.return_to_passive_after_session:
            self._safe_transition(VoiceState.PASSIVE_LISTENING)
        else:
            self._stop.set()
            self._safe_transition(VoiceState.STOPPING)
        self._logger.info("Omega voice session timed out.")
        return message

    def _remembered(self, result_id: UUID) -> bool:
        with self._lock:
            if result_id in self._processed_set:
                return True
            if len(self._processed_ids) == self._processed_ids.maxlen:
                oldest = self._processed_ids.popleft()
                self._processed_set.discard(oldest)
            self._processed_ids.append(result_id)
            self._processed_set.add(result_id)
            return False

    @staticmethod
    def _confirmation_key(text: str) -> str:
        """Use the central confirmation manager's exact comparison policy."""

        return " ".join(text.strip().split()).casefold()

    def _transition(self, target: VoiceState) -> None:
        state = self._states.transition_to(target)
        self._emit(f"Voice state changed to {state.value}.")

    def _safe_transition(self, target: VoiceState) -> None:
        try:
            self._transition(target)
        except VoiceError:
            if target is VoiceState.ERROR:
                raise

    def _emit(
        self,
        message: str,
        *,
        transcript: str | None = None,
        response: str | None = None,
    ) -> VoiceEvent:
        event = VoiceEvent(self.state, message, transcript, response)
        if self._event_sink is not None:
            try:
                self._event_sink(event)
            except Exception:
                self._logger.warning("Voice presentation callback failed safely.")
        return event
