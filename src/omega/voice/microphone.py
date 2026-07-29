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
        self._selected_device: str = "system default"

    @property
    def selected_device(self) -> str:
        """Return bounded display metadata for the selected input device."""

        return self._selected_device

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
                selected = self._resolve_configured_device(module)
                stream = module.RawInputStream(
                    samplerate=self.sample_rate_hz,
                    blocksize=self.block_size,
                    device=selected,
                    dtype="int16",
                    channels=1,
                    callback=self._callback,
                )
                stream.start()
            except MicrophoneUnavailableError:
                raise
            except Exception as error:
                raise MicrophoneUnavailableError(
                    "Omega could not open the selected microphone."
                ) from error
            self._stream = stream

    def _resolve_configured_device(self, module: ModuleType) -> int | None:
        if self.device is None:
            self._selected_device = "system default"
            return None
        devices = self._query_devices(module)
        if isinstance(self.device, int):
            matched = next(
                (item for item in devices if item.identifier == self.device), None
            )
            if matched is None:
                raise MicrophoneUnavailableError(
                    f"Configured microphone index {self.device} is unavailable."
                )
        else:
            key = " ".join(self.device.strip().casefold().split())
            exact = [
                item
                for item in devices
                if " ".join(item.name.casefold().split()) == key
            ]
            if len(exact) != 1:
                raise MicrophoneUnavailableError(
                    f'Configured microphone "{self.device}" is unavailable or '
                    "ambiguous. Use --list-audio-devices to choose an index."
                )
            matched = exact[0]
        self._selected_device = f"{matched.identifier}: {matched.name}"
        return matched.identifier

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

        return self._query_devices(self._module())

    def _query_devices(self, module: ModuleType) -> tuple[AudioDevice, ...]:
        """Return bounded input metadata from one already imported adapter."""

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
