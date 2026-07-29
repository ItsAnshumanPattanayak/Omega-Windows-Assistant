"""Optional offline voice adapters with no import-time device side effects."""

from omega.voice.configuration import VoiceConfiguration
from omega.voice.models import (
    AudioDevice,
    TranscriptionResult,
    VoiceDiagnostics,
    VoiceEvent,
    VoiceState,
    VoiceStateMachine,
)
from omega.voice.wake_word import WakeMatch, WakeWordDetector

__all__ = [
    "AudioDevice",
    "TranscriptionResult",
    "VoiceDiagnostics",
    "VoiceConfiguration",
    "VoiceEvent",
    "VoiceState",
    "VoiceStateMachine",
    "WakeMatch",
    "WakeWordDetector",
]
