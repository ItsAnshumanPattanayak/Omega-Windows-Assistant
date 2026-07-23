from __future__ import annotations

from concurrent.futures import Future
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from omega.__main__ import main
from omega.gui.controller import GuiController
from omega.gui.models import GuiPreferences
from omega.history import HistoryActivity
from omega.models import CommandSource
from omega.session import OmegaSession
from omega.voice.models import AudioDevice, VoiceEvent, VoiceState
from omega.voice.terminal import VoiceTerminalInterface


def test_existing_session_creates_voice_source_command_once() -> None:
    session = OmegaSession(
        {"display_name": "Anshuman"},
        {
            "activation_phrase": "Hello Omega",
            "shutdown_phrase": "Shut down Omega",
            "active_session_timeout_seconds": 300,
        },
    )
    session.handle_input("Hello Omega")

    session.handle_input("Open Chrome", source=CommandSource.VOICE)

    assert len(session.history) == 1
    assert session.history[0].original_text == "Open Chrome"
    assert session.history[0].source is CommandSource.VOICE
    assert session.history[0].session_id == session.session_id


class TerminalService:
    def __init__(self, sink) -> None:
        self.sink = sink
        self.running = False
        self.stopped = 0

    def start(self) -> None:
        self.sink(
            VoiceEvent(
                VoiceState.ACTIVE_LISTENING,
                transcript="status",
                response="Omega is active.",
            )
        )

    def stop(self) -> None:
        self.stopped += 1


def test_terminal_voice_adapter_displays_safe_transcript_and_response() -> None:
    output: list[str] = []
    services: list[TerminalService] = []

    def factory(sink):
        service = TerminalService(sink)
        services.append(service)
        return service

    interface = VoiceTerminalInterface(factory, output_func=output.append)  # type: ignore[arg-type]

    assert interface.run() == 0
    assert output == [
        "Omega voice mode is ready.",
        "You: status",
        "Omega: Omega is active.",
    ]
    assert services[0].stopped == 1


def test_cli_voice_mode_is_explicit_and_terminal_is_preserved(monkeypatch) -> None:
    calls: list[str] = []

    class Application:
        def run(self):
            calls.append("terminal")
            return 0

        def run_gui(self):
            calls.append("gui")
            return 0

        def run_voice(self):
            calls.append("voice")
            return 0

    monkeypatch.setattr("omega.__main__.OmegaApplication", Application)

    assert main([]) == 0
    assert main(["--voice"]) == 0
    assert calls == ["terminal", "voice"]


def test_cli_lists_safe_audio_metadata_without_starting_voice(
    monkeypatch, capsys
) -> None:
    calls: list[str] = []

    class Application:
        def list_audio_devices(self):
            calls.append("list")
            return (AudioDevice(2, "Local microphone", 1, 16_000),)

    monkeypatch.setattr("omega.__main__.OmegaApplication", Application)

    assert main(["--list-audio-devices"]) == 0
    assert calls == ["list"]
    output = capsys.readouterr().out
    assert "2: Local microphone" in output
    assert "16000 Hz" in output


def test_cli_rejects_conflicting_modes_before_application_start(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "omega.__main__.OmegaApplication",
        lambda: (_ for _ in ()).throw(AssertionError("must not initialize")),
    )

    assert main(["--gui", "--voice"]) == 2
    assert "choose one startup mode" in capsys.readouterr().err


class ImmediateRunner:
    def submit(self, operation, on_success, on_error):
        future = Future()
        try:
            value = operation()
        except BaseException as error:
            future.set_exception(error)
            on_error(error)
        else:
            future.set_result(value)
            on_success(value)
        return future

    def post(self, callback):
        callback()

    def shutdown(self, *, wait=False):
        del wait


class View:
    def __init__(self) -> None:
        self.voice_states: list[tuple[VoiceState, str]] = []
        self.transcripts: list[str] = []
        self.messages = []
        self.notifications = []

    def add_message(self, message):
        self.messages.append(message)

    def set_status(self, status, detail):
        del status, detail

    def set_busy(self, busy):
        del busy

    def show_activity(self, items):
        del items

    def set_undo_availability(self, availability):
        del availability

    def show_confirmation(self, request):
        del request

    def dismiss_confirmation(self):
        return None

    def notify(self, notification):
        self.notifications.append(notification)

    def apply_preferences(self, preferences):
        del preferences

    def update_session_state(self, state):
        self.session_state = state

    def update_voice_state(self, state, detail):
        self.voice_states.append((state, detail))

    def show_voice_transcription(self, transcript):
        self.transcripts.append(transcript)


class GuiVoice:
    def __init__(self, sink) -> None:
        self.sink = sink
        self.running = False
        self.state = VoiceState.IDLE
        self.stops = 0
        self.speech_preferences: list[bool] = []

    def set_speech_enabled(self, enabled):
        self.speech_preferences.append(enabled)

    def start(self):
        self.running = True
        self.state = VoiceState.PASSIVE_LISTENING
        self.sink(
            VoiceEvent(
                VoiceState.ACTIVE_LISTENING,
                transcript="status",
                response="Omega is active.",
            )
        )

    def stop(self):
        self.running = False
        self.state = VoiceState.IDLE
        self.stops += 1


class History:
    def latest_activity(self, limit):
        del limit
        return (HistoryActivity("command", uuid4(), datetime.now(UTC), "status"),)

    def active_undo_records(self):
        return ()


class Preferences:
    def load(self):
        return GuiPreferences()

    def save(self, preferences):
        return preferences


class Gateway:
    confirmations = SimpleNamespace(get=lambda session_id: None)


class Session:
    activation_phrase = "Hello Omega"
    shutdown_phrase = "Shut down Omega"
    session_id = uuid4()
    state = SimpleNamespace(value="active")

    def handle_input(self, text):
        return text

    def interrupt(self):
        return "interrupted"


def test_gui_voice_controls_marshal_events_and_prevent_duplicate_start() -> None:
    view = View()
    voices: list[GuiVoice] = []

    def factory(sink):
        voice = GuiVoice(sink)
        voices.append(voice)
        return voice

    controller = GuiController(
        Session(),  # type: ignore[arg-type]
        History(),  # type: ignore[arg-type]
        Preferences(),  # type: ignore[arg-type]
        Gateway(),  # type: ignore[arg-type]
        ImmediateRunner(),  # type: ignore[arg-type]
        view,
        voice_factory=factory,  # type: ignore[arg-type]
    )

    assert controller.start_voice()
    assert not controller.start_voice()
    assert view.transcripts == ["status"]
    assert [message.text for message in view.messages] == [
        "status",
        "Omega is active.",
    ]
    assert controller.stop_voice()
    assert voices[0].stops == 1
    assert view.voice_states[-1][0] is VoiceState.IDLE


def test_gui_close_stops_voice_before_worker_shutdown() -> None:
    view = View()
    voices: list[GuiVoice] = []

    def factory(sink):
        voice = GuiVoice(sink)
        voices.append(voice)
        return voice

    controller = GuiController(
        Session(),  # type: ignore[arg-type]
        History(),  # type: ignore[arg-type]
        Preferences(),  # type: ignore[arg-type]
        Gateway(),  # type: ignore[arg-type]
        ImmediateRunner(),  # type: ignore[arg-type]
        view,
        voice_factory=factory,  # type: ignore[arg-type]
    )
    controller.start_voice()

    controller.close()

    assert voices[0].stops == 1
