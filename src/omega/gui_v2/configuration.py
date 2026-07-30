"""Typed, backward-compatible configuration for the Omega V2 GUI foundation."""

from __future__ import annotations

from dataclasses import dataclass, field

from omega.core.exceptions import ConfigurationError
from omega.gui_v2.state import GuiState


@dataclass(frozen=True, slots=True)
class V2GuiConfiguration:
    """Static Phase 1 presentation settings with permanently muted video."""

    window_title: str = "Omega Windows Assistant — Version 2"
    minimum_width: int = 900
    minimum_height: int = 640
    default_state: GuiState = GuiState.SLEEPING
    video_asset_relative_path: str = "assets/videos/omega_core_loop.mp4"
    video_loop: bool = field(default=True, init=False)
    demo_mode: bool = False
    fullscreen: bool = False
    animation_enabled: bool = True
    video_muted: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        if not self.window_title.strip():
            raise ConfigurationError("The Omega V2 window title cannot be empty.")
        if self.minimum_width < 640 or self.minimum_height < 480:
            raise ConfigurationError(
                "Omega V2 minimum window dimensions are too small."
            )
        path = self.video_asset_relative_path.replace("\\", "/")
        if not path or path.startswith("/") or ".." in path.split("/"):
            raise ConfigurationError("The Omega V2 video asset path must be relative.")
