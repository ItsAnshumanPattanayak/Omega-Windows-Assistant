from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from omega.core.exceptions import (
    MicrophoneUnavailableError,
    RecognitionError,
    SpeechSynthesisError,
    VoiceInitializationError,
)
from omega.voice.microphone import SoundDeviceMicrophone
from omega.voice.recognizer import VoskSpeechRecognizer
from omega.voice.speaker import SapiSpeechSynthesizer


def test_importing_voice_package_loads_no_audio_dependency_or_worker() -> None:
    for name in ("sounddevice", "vosk", "comtypes", "comtypes.client"):
        sys.modules.pop(name, None)

    module = importlib.reload(importlib.import_module("omega.voice"))

    assert module.VoiceState.IDLE.value == "idle"
    assert "sounddevice" not in sys.modules
    assert "vosk" not in sys.modules
    assert "comtypes" not in sys.modules


def test_microphone_missing_dependency_is_actionable(monkeypatch) -> None:
    microphone = SoundDeviceMicrophone(
        device=None,
        sample_rate_hz=16_000,
        block_size=4_000,
    )

    def missing(name: str):
        raise ImportError(name)

    monkeypatch.setattr("omega.voice.microphone.importlib.import_module", missing)
    with pytest.raises(MicrophoneUnavailableError, match="voice extra"):
        microphone.start()


def test_microphone_capture_is_explicit_bounded_and_closes(monkeypatch) -> None:
    streams: list[object] = []

    class Stream:
        def __init__(self, **kwargs):
            self.callback = kwargs["callback"]
            self.started = False
            self.stopped = False
            self.closed = False
            self.active = True
            streams.append(self)

        def start(self):
            self.started = True

        def stop(self):
            self.stopped = True
            self.active = False

        def close(self):
            self.closed = True

    module = SimpleNamespace(
        RawInputStream=Stream,
        query_devices=lambda: [
            {
                "name": "Test microphone",
                "max_input_channels": 1,
                "default_samplerate": 16_000,
            },
            {
                "name": "Output only",
                "max_input_channels": 0,
                "default_samplerate": 48_000,
            },
        ],
    )
    monkeypatch.setattr(
        "omega.voice.microphone.importlib.import_module",
        lambda _: module,
    )
    microphone = SoundDeviceMicrophone(
        device=0,
        sample_rate_hz=16_000,
        block_size=4_000,
        queue_capacity=1,
    )
    assert streams == []

    microphone.start()
    stream = streams[0]
    stream.callback(b"first", 1, None, None)
    stream.callback(b"second", 1, None, None)
    assert microphone.read(0.01) == b"second"
    assert microphone.list_devices()[0].name == "Test microphone"
    microphone.stop()

    assert stream.started
    assert stream.stopped
    assert stream.closed


def test_microphone_disconnect_is_reported_safely(monkeypatch) -> None:
    class Stream:
        active = False

        def __init__(self, **kwargs):
            del kwargs

        def start(self):
            return None

        def stop(self):
            return None

        def close(self):
            return None

    monkeypatch.setattr(
        "omega.voice.microphone.importlib.import_module",
        lambda _: SimpleNamespace(RawInputStream=Stream),
    )
    microphone = SoundDeviceMicrophone(
        device=None,
        sample_rate_hz=16_000,
        block_size=4_000,
    )
    microphone.start()

    with pytest.raises(MicrophoneUnavailableError, match="disconnected"):
        microphone.read(0.001)
    microphone.stop()


def test_recognizer_requires_existing_configured_model(tmp_path: Path) -> None:
    with pytest.raises(VoiceInitializationError, match="No offline speech model"):
        VoskSpeechRecognizer(None, sample_rate_hz=16_000, maximum_characters=100)
    with pytest.raises(VoiceInitializationError, match="missing or invalid"):
        VoskSpeechRecognizer(
            tmp_path / "missing",
            sample_rate_hz=16_000,
            maximum_characters=100,
        )


def test_vosk_adapter_returns_final_typed_result(monkeypatch, tmp_path: Path) -> None:
    model_path = tmp_path / "model"
    model_path.mkdir()

    class Recognizer:
        def __init__(self, model, rate):
            self.model = model
            self.rate = rate

        def SetWords(self, enabled):
            assert enabled

        def AcceptWaveform(self, audio):
            return audio == b"pcm"

        def Result(self):
            return (
                '{"text":"Open Chrome","result":'
                '[{"word":"open","conf":0.9},{"word":"chrome","conf":0.8}]}'
            )

    module = SimpleNamespace(
        Model=lambda path: {"path": path},
        KaldiRecognizer=Recognizer,
    )
    monkeypatch.setattr(
        "omega.voice.recognizer.importlib.import_module",
        lambda _: module,
    )
    recognizer = VoskSpeechRecognizer(
        model_path,
        sample_rate_hz=16_000,
        maximum_characters=100,
    )

    result = recognizer.transcribe(b"pcm")

    assert result is not None
    assert result.transcript == "Open Chrome"
    assert result.normalized_transcript == "open chrome"
    assert result.confidence == pytest.approx(0.85)
    assert result.is_final
    recognizer.close()


def test_vosk_adapter_rejects_empty_audio_and_overlong_text(
    monkeypatch,
    tmp_path: Path,
) -> None:
    model_path = tmp_path / "model"
    model_path.mkdir()

    class Recognizer:
        def __init__(self, model, rate):
            del model, rate

        def SetWords(self, enabled):
            del enabled

        def AcceptWaveform(self, audio):
            del audio
            return True

        def Result(self):
            return '{"text":"too long","result":[]}'

    monkeypatch.setattr(
        "omega.voice.recognizer.importlib.import_module",
        lambda _: SimpleNamespace(Model=lambda _: object(), KaldiRecognizer=Recognizer),
    )
    recognizer = VoskSpeechRecognizer(
        model_path,
        sample_rate_hz=16_000,
        maximum_characters=3,
    )

    with pytest.raises(RecognitionError, match="non-empty"):
        recognizer.transcribe(b"")
    with pytest.raises(RecognitionError, match="too long"):
        recognizer.transcribe(b"pcm")


def test_sapi_speaker_is_explicit_bounded_and_sequential(monkeypatch) -> None:
    spoken: list[str] = []

    class Engine:
        Rate = 0
        Volume = 0

        def Speak(self, text, flags=0):
            del flags
            if text:
                spoken.append(text)

        def WaitUntilDone(self, timeout):
            del timeout
            return True

        def GetVoices(self):
            raise RuntimeError("use default")

    comtypes = SimpleNamespace(CoInitialize=lambda: None, CoUninitialize=lambda: None)
    client = SimpleNamespace(CreateObject=lambda _: Engine())

    def load(name: str):
        return client if name == "comtypes.client" else comtypes

    monkeypatch.setattr("omega.voice.speaker.importlib.import_module", load)
    speaker = SapiSpeechSynthesizer(
        rate=180,
        volume=1.0,
        voice_name="missing voice",
        queue_capacity=2,
    )
    assert spoken == []

    speaker.start()
    assert speaker.speak("first")
    assert speaker.speak("x" * 700)
    for _ in range(100):
        if len(spoken) == 2:
            break
        import threading

        threading.Event().wait(0.005)
    speaker.close()

    assert spoken[0] == "first"
    assert len(spoken[1]) <= 500


def test_sapi_missing_dependency_fails_without_creating_output(monkeypatch) -> None:
    def missing(name: str):
        raise ImportError(name)

    monkeypatch.setattr("omega.voice.speaker.importlib.import_module", missing)
    speaker = SapiSpeechSynthesizer(
        rate=180,
        volume=1.0,
        voice_name=None,
    )

    with pytest.raises(SpeechSynthesisError, match="could not initialize"):
        speaker.start()
    speaker.close()


def test_voice_adapters_create_no_audio_file(tmp_path: Path) -> None:
    before = set(tmp_path.iterdir())
    microphone = SoundDeviceMicrophone(
        device=None,
        sample_rate_hz=16_000,
        block_size=4_000,
    )

    assert microphone.read(0.001) is None
    assert set(tmp_path.iterdir()) == before
    assert uuid4()
