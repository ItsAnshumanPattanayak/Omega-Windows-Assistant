"""Explicit sounddevice microphone adapter with bounded buffering."""

from __future__ import annotations

import importlib
from queue import Empty, Full, Queue
from threading import Lock
from types import ModuleType
from typing import Any

from omega.core.exceptions import MicrophoneUnavailableError
from omega.voice.models import AudioDevice


class SoundDeviceMicrophone:
    """Capture mono 16-bit PCM only after explicit ``start``."""

    def __init__(
        self,
        *,
        device: int | str | None,
        sample_rate_hz: int,
        block_size: int,
        queue_capacity: int = 8,
    ) -> None:
        self.device = device
        self.sample_rate_hz = sample_rate_hz
        self.block_size = block_size
        self._blocks: Queue[bytes] = Queue(maxsize=queue_capacity)
        self._stream: Any | None = None
        self._lock = Lock()

    @staticmethod
    def _module() -> ModuleType:
        try:
            return importlib.import_module("sounddevice")
        except (ImportError, OSError) as error:
            raise MicrophoneUnavailableError(
                "Local microphone support is unavailable. Install Omega with "
                "the voice extra: pip install -e .[voice]"
            ) from error

    def start(self) -> None:
        """Open one validated input stream; duplicate starts are rejected."""

        with self._lock:
            if self._stream is not None:
                raise MicrophoneUnavailableError(
                    "The microphone listener is already running."
                )
            module = self._module()
            try:
                stream = module.RawInputStream(
                    samplerate=self.sample_rate_hz,
                    blocksize=self.block_size,
                    device=self.device,
                    dtype="int16",
                    channels=1,
                    callback=self._callback,
                )
                stream.start()
            except Exception as error:
                raise MicrophoneUnavailableError(
                    "Omega could not open the selected microphone."
                ) from error
            self._stream = stream

    def _callback(
        self,
        input_data: bytes,
        frames: int,
        timing: object,
        status: object,
    ) -> None:
        del frames, timing, status
        block = bytes(input_data)
        if not block:
            return
        try:
            self._blocks.put_nowait(block)
        except Full:
            try:
                self._blocks.get_nowait()
            except Empty:
                return
            try:
                self._blocks.put_nowait(block)
            except Full:
                return

    def read(self, timeout_seconds: float) -> bytes | None:
        """Return one block or ``None`` so stop checks remain responsive."""

        try:
            return self._blocks.get(timeout=timeout_seconds)
        except Empty:
            stream = self._stream
            if stream is not None and getattr(stream, "active", True) is False:
                raise MicrophoneUnavailableError(
                    "The selected microphone disconnected while listening."
                ) from None
            return None

    def stop(self) -> None:
        """Stop and close the stream idempotently."""

        with self._lock:
            stream = self._stream
            self._stream = None
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()
        while True:
            try:
                self._blocks.get_nowait()
            except Empty:
                break

    def list_devices(self) -> tuple[AudioDevice, ...]:
        """Discover at most 100 input devices only when explicitly requested."""

        module = self._module()
        try:
            raw_devices = module.query_devices()
        except Exception as error:
            raise MicrophoneUnavailableError(
                "Omega could not enumerate local audio input devices."
            ) from error
        devices: list[AudioDevice] = []
        for index, raw in enumerate(raw_devices):
            if len(devices) >= 100:
                break
            if not isinstance(raw, dict):
                continue
            channels = int(raw.get("max_input_channels", 0))
            if channels <= 0:
                continue
            name = str(raw.get("name", "Unnamed input device")).strip()
            rate = int(float(raw.get("default_samplerate", self.sample_rate_hz)))
            devices.append(AudioDevice(index, name[:120], channels, rate))
        return tuple(devices)
