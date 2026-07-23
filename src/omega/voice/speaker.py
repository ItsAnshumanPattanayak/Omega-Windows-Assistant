"""Bounded Windows SAPI speech output using optional comtypes."""

from __future__ import annotations

import importlib
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread, current_thread
from types import ModuleType
from typing import Any

from omega.core.exceptions import SpeechSynthesisError

_MAX_SPOKEN_CHARACTERS = 500
_SENTINEL = object()


class SapiSpeechSynthesizer:
    """Speak queued safe responses sequentially on one explicit worker."""

    def __init__(
        self,
        *,
        rate: int,
        volume: float,
        voice_name: str | None,
        queue_capacity: int = 8,
    ) -> None:
        self.rate = rate
        self.volume = volume
        self.voice_name = voice_name
        self._queue: Queue[str | object] = Queue(maxsize=queue_capacity)
        self._stop = Event()
        self._cancel = Event()
        self._ready = Event()
        self._failure: BaseException | None = None
        self._thread: Thread | None = None
        self._lock = Lock()

    @staticmethod
    def _module() -> ModuleType:
        try:
            return importlib.import_module("comtypes")
        except (ImportError, OSError) as error:
            raise SpeechSynthesisError(
                "Local Windows speech output is unavailable. Install Omega with "
                "the voice extra: pip install -e .[voice]"
            ) from error

    def start(self) -> None:
        """Start exactly one bounded SAPI worker and verify initialization."""

        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._cancel.clear()
            self._ready.clear()
            self._failure = None
            worker = Thread(
                target=self._run,
                name="omega-voice-speaker",
                daemon=True,
            )
            self._thread = worker
            worker.start()
        if not self._ready.wait(timeout=5):
            self.close()
            raise SpeechSynthesisError("The local speech engine timed out.")
        failure = self._initialization_failure()
        if failure is not None:
            self.close()
            raise SpeechSynthesisError(
                "The local Windows speech engine could not initialize."
            ) from failure

    def speak(self, text: str) -> bool:
        """Queue one bounded non-empty response without blocking the caller."""

        if not isinstance(text, str) or not text.strip():
            return False
        safe_text = text.strip()
        if len(safe_text) > _MAX_SPOKEN_CHARACTERS:
            safe_text = safe_text[: _MAX_SPOKEN_CHARACTERS - 1].rstrip() + "…"
        thread = self._thread
        if thread is None or not thread.is_alive():
            raise SpeechSynthesisError("The local speech engine is not running.")
        try:
            self._queue.put_nowait(safe_text)
        except Full:
            return False
        return True

    def cancel(self) -> None:
        """Cancel queued and current output without approving any command."""

        self._cancel.set()
        self._clear_queue()

    def close(self) -> None:
        """Stop the worker idempotently with a bounded join."""

        with self._lock:
            worker = self._thread
            self._thread = None
            self._stop.set()
            self._cancel.set()
            self._clear_queue()
            try:
                self._queue.put_nowait(_SENTINEL)
            except Full:
                self._stop.set()
        if worker is not None and worker is not current_thread():
            worker.join(timeout=5)

    def _clear_queue(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except Empty:
                return

    def _initialization_failure(self) -> BaseException | None:
        """Read a worker-produced initialization result for type checkers."""

        return self._failure

    def _run(self) -> None:
        module: ModuleType | None = None
        voice: Any | None = None
        com_initialized = False
        try:
            module = self._module()
            module.CoInitialize()
            com_initialized = True
            client = importlib.import_module("comtypes.client")
            voice = client.CreateObject("SAPI.SpVoice")
            voice.Rate = max(-10, min(10, round((self.rate - 180) / 22)))
            voice.Volume = round(self.volume * 100)
            self._select_voice(voice)
        except BaseException as error:
            self._failure = error
            self._ready.set()
            if module is not None and com_initialized:
                module.CoUninitialize()
            return
        self._ready.set()
        try:
            while not self._stop.is_set():
                try:
                    item = self._queue.get(timeout=0.1)
                except Empty:
                    continue
                if item is _SENTINEL:
                    break
                if not isinstance(item, str):
                    continue
                self._cancel.clear()
                voice.Speak(item, 1)
                while not self._stop.is_set() and not bool(voice.WaitUntilDone(100)):
                    if self._cancel.is_set():
                        voice.Speak("", 3)
                        break
        finally:
            if voice is not None:
                try:
                    voice.Speak("", 3)
                except Exception:
                    self._cancel.set()
            if module is not None and com_initialized:
                module.CoUninitialize()

    def _select_voice(self, engine: Any) -> None:
        if self.voice_name is None:
            return
        requested = self.voice_name.casefold()
        try:
            voices = engine.GetVoices()
            for index in range(int(voices.Count)):
                candidate = voices.Item(index)
                description = str(candidate.GetDescription())
                if requested in description.casefold():
                    engine.Voice = candidate
                    return
        except Exception:
            return
