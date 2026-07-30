from __future__ import annotations

from pathlib import Path

import pytest

from omega.core.exceptions import ConfigurationError
from omega.gui_v2 import GuiAssetError, V2GuiConfiguration, resolve_gui_asset


def test_configuration_is_safe_and_video_mute_cannot_be_disabled() -> None:
    configuration = V2GuiConfiguration()
    assert configuration.video_muted is True
    assert configuration.video_loop is True
    assert configuration.default_state.value == "sleeping"
    with pytest.raises(TypeError):
        V2GuiConfiguration(video_muted=False)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        V2GuiConfiguration(video_loop=False)  # type: ignore[call-arg]


def test_configuration_rejects_unsafe_asset_paths() -> None:
    with pytest.raises(ConfigurationError, match="relative"):
        V2GuiConfiguration(video_asset_relative_path="../private.mp4")


def test_asset_resolution_is_rooted_and_independent_of_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "bundle"
    expected = root / "assets" / "videos" / "omega_core_loop.mp4"
    expected.parent.mkdir(parents=True)
    expected.write_bytes(b"video")
    monkeypatch.chdir(tmp_path)

    assert resolve_gui_asset("assets/videos/omega_core_loop.mp4", root=root) == expected
    with pytest.raises(GuiAssetError):
        resolve_gui_asset("../outside.mp4", root=root)


def test_missing_asset_returns_stable_fallback_path(tmp_path: Path) -> None:
    path = resolve_gui_asset("assets/videos/missing.mp4", root=tmp_path)
    assert path == tmp_path / "assets" / "videos" / "missing.mp4"
    assert not path.exists()
