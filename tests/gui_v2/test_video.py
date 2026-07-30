from __future__ import annotations

from pathlib import Path
from typing import Any

from omega.gui_v2.video import SilentLoopingVideoController


class FakeDecoder:
    def __init__(self, frames: list[Any], *, opens: bool = True) -> None:
        self.frames = frames
        self.opens = opens
        self.index = 0
        self.closed = 0
        self.rewinds = 0

    @property
    def frames_per_second(self) -> float:
        return 25.0

    def open(self, _path: Path) -> bool:
        return self.opens

    def read(self) -> Any | None:
        if self.index >= len(self.frames):
            return None
        frame = self.frames[self.index]
        self.index += 1
        return frame

    def rewind(self) -> bool:
        self.index = 0
        self.rewinds += 1
        return True

    def close(self) -> None:
        self.closed += 1


def test_video_is_always_muted_and_loops(tmp_path: Path) -> None:
    path = tmp_path / "loop.mp4"
    path.write_bytes(b"video")
    decoder = FakeDecoder(["frame"])
    controller = SilentLoopingVideoController(path, decoder_factory=lambda: decoder)

    assert controller.muted is True
    assert controller.open()
    assert controller.frame_interval_ms == 40
    assert controller.next_frame() == "frame"
    assert controller.next_frame() == "frame"
    assert decoder.rewinds == 1
    controller.close()
    controller.close()
    assert decoder.closed == 1


def test_missing_file_and_backend_fail_gracefully(tmp_path: Path) -> None:
    missing = SilentLoopingVideoController(tmp_path / "missing.mp4")
    assert not missing.open()
    assert "unavailable" in missing.failure_reason

    path = tmp_path / "video.mp4"
    path.write_bytes(b"video")
    decoder = FakeDecoder([], opens=False)
    unavailable = SilentLoopingVideoController(path, decoder_factory=lambda: decoder)
    assert not unavailable.open()
    assert unavailable.next_frame() is None
    assert decoder.closed == 1
