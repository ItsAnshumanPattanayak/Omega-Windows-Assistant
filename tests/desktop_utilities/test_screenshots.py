from pathlib import Path

import pytest

from omega.desktop_utilities import (
    DesktopUtilitiesConfiguration,
    DesktopUtilityError,
    FakeScreenshotBackend,
    ScreenshotError,
    ScreenshotRegion,
    ScreenshotRequest,
    ScreenshotService,
    ScreenshotTarget,
)


def make_service(
    tmp_path: Path, **kwargs: object
) -> tuple[ScreenshotService, FakeScreenshotBackend, list[Path]]:
    config = DesktopUtilitiesConfiguration.from_mapping(kwargs)
    backend = FakeScreenshotBackend()
    deleted: list[Path] = []
    return (
        ScreenshotService(
            config,
            backend,
            tmp_path / "shots",
            opener=lambda path: None,
            deleter=deleted.append,
        ),
        backend,
        deleted,
    )


def test_capture_is_explicit_and_uses_runtime_root(tmp_path: Path) -> None:
    value, backend, _ = make_service(tmp_path)
    assert backend.capture_count == 0
    record = value.capture(ScreenshotRequest())
    assert (
        backend.capture_count == 1
        and record.path.parent == (tmp_path / "shots").resolve()
    )
    assert record.path.read_bytes().startswith(b"\x89PNG")


def test_recent_is_process_local_and_bounded(tmp_path: Path) -> None:
    value, _, _ = make_service(tmp_path, maximum_recent_screenshots=2)
    for _ in range(3):
        value.capture(ScreenshotRequest())
    assert len(value.recent()) == 2


def test_delete_uses_injected_recovery_path(tmp_path: Path) -> None:
    value, _, deleted = make_service(tmp_path)
    record = value.capture(ScreenshotRequest())
    value.delete_selected()
    assert deleted == [record.path]


def test_open_uses_selected_file(tmp_path: Path) -> None:
    opened: list[Path] = []
    value = ScreenshotService(
        DesktopUtilitiesConfiguration(),
        FakeScreenshotBackend(),
        tmp_path,
        opener=opened.append,
    )
    record = value.capture(ScreenshotRequest())
    value.open_selected()
    assert opened == [record.path]


@pytest.mark.parametrize("width,height", [(0, 1), (1, 0), (20_000, 1)])
def test_invalid_region_rejected(width: int, height: int) -> None:
    with pytest.raises(DesktopUtilityError):
        ScreenshotRegion(0, 0, width, height).validate(16_384, 16_384, 1_000_000)


def test_region_capture_respects_policy(tmp_path: Path) -> None:
    value, backend, _ = make_service(tmp_path, allow_region_capture=False)
    with pytest.raises(ScreenshotError):
        value.capture(
            ScreenshotRequest(
                ScreenshotTarget.REGION, region=ScreenshotRegion(0, 0, 10, 10)
            )
        )
    assert backend.capture_count == 0


def test_virtual_capture_respects_policy(tmp_path: Path) -> None:
    value, backend, _ = make_service(tmp_path, allow_full_virtual_desktop_capture=False)
    with pytest.raises(ScreenshotError):
        value.capture(ScreenshotRequest(ScreenshotTarget.VIRTUAL_DESKTOP))
    assert backend.capture_count == 0


def test_stale_or_invalid_selection_fails(tmp_path: Path) -> None:
    value, _, _ = make_service(tmp_path)
    with pytest.raises(ScreenshotError):
        value.select(1)
