"""Silent, looped frame decoding for the Omega V2 background animation."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from omega.utils.logger import get_logger


class FrameDecoder(Protocol):
    """Minimal frame-only decoder contract; audio is intentionally absent."""

    @property
    def frames_per_second(self) -> float: ...

    def open(self, path: Path) -> bool: ...

    def read(self) -> Any | None: ...

    def rewind(self) -> bool: ...

    def close(self) -> None: ...


class OpenCvFrameDecoder:
    """Decode visual frames only; never initialize an audio output path."""

    def __init__(self) -> None:
        self._module: Any | None = None
        self._capture: Any | None = None
        self._frames_per_second = 30.0

    @property
    def frames_per_second(self) -> float:
        return self._frames_per_second

    def open(self, path: Path) -> bool:
        self.close()
        try:
            module = importlib.import_module("cv2")
        except ImportError:
            return False
        capture = module.VideoCapture(str(path))
        if not capture.isOpened():
            capture.release()
            return False
        measured = float(capture.get(module.CAP_PROP_FPS))
        self._frames_per_second = measured if 1.0 <= measured <= 120.0 else 30.0
        self._module = module
        self._capture = capture
        return True

    def read(self) -> Any | None:
        if self._capture is None:
            return None
        success, frame = self._capture.read()
        return frame if success else None

    def rewind(self) -> bool:
        if self._capture is None or self._module is None:
            return False
        return bool(self._capture.set(self._module.CAP_PROP_POS_FRAMES, 0))

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
        self._capture = None
        self._module = None


DecoderFactory = Callable[[], FrameDecoder]


class SilentLoopingVideoController:
    """Own frame decoding with forced mute, bounded looping, and safe cleanup."""

    muted = True

    def __init__(
        self,
        path: Path,
        *,
        loop: bool = True,
        decoder_factory: DecoderFactory = OpenCvFrameDecoder,
    ) -> None:
        self.path = path
        self.loop = loop
        self._decoder_factory = decoder_factory
        self._decoder: FrameDecoder | None = None
        self.available = False
        self.failure_reason = ""
        self._logger = get_logger("gui_v2.video")

    @property
    def frame_interval_ms(self) -> int:
        fps = self._decoder.frames_per_second if self._decoder else 30.0
        return max(8, min(1000, round(1000 / fps)))

    def open(self) -> bool:
        """Open a video for frame-only decoding, reporting failure safely."""

        self.close()
        if not self.path.is_file():
            self.failure_reason = "Animation file is unavailable."
            return False
        decoder = self._decoder_factory()
        try:
            opened = decoder.open(self.path)
        except Exception:
            self._logger.exception("Omega V2 animation backend failed to initialize.")
            opened = False
        if not opened:
            decoder.close()
            self.failure_reason = "Animation playback is unavailable."
            return False
        self._decoder = decoder
        self.available = True
        self.failure_reason = ""
        return True

    def next_frame(self) -> Any | None:
        """Return the next visual frame, rewinding once at end when configured."""

        decoder = self._decoder
        if not self.available or decoder is None:
            return None
        try:
            frame = decoder.read()
            if frame is not None or not self.loop:
                return frame
            if decoder.rewind():
                return decoder.read()
        except Exception:
            self._logger.exception("Omega V2 animation frame decoding failed.")
        self.failure_reason = "Animation playback stopped safely."
        self.available = False
        return None

    def close(self) -> None:
        """Release decoder resources safely and idempotently."""

        decoder, self._decoder = self._decoder, None
        self.available = False
        if decoder is not None:
            try:
                decoder.close()
            except Exception:
                self._logger.exception("Omega V2 animation cleanup failed.")
