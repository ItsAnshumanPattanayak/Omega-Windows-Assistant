import pytest

from omega.desktop_utilities import (
    DesktopInformationService,
    DesktopUtilitiesConfiguration,
    FakeScreenInformationProvider,
    FakeWindowInformationProvider,
    WindowInformation,
    WindowMetadataError,
)


def make_service() -> tuple[DesktopInformationService, FakeWindowInformationProvider]:
    windows = FakeWindowInformationProvider(
        (
            WindowInformation("1", "Editor\nPrivate title", "edit.exe"),
            WindowInformation("2", "Browser", "browser.exe"),
        )
    )
    return (
        DesktopInformationService(
            DesktopUtilitiesConfiguration(), FakeScreenInformationProvider(), windows
        ),
        windows,
    )


def test_display_metadata_is_bounded() -> None:
    service, _ = make_service()
    displays = service.displays()
    assert len(displays) == 1 and displays[0].primary


def test_active_window_sanitizes_title() -> None:
    service, _ = make_service()
    assert service.active_window().title == "Editor Private title"


def test_visible_windows_and_find_are_bounded() -> None:
    service, _ = make_service()
    assert len(service.visible_windows()) == 2
    assert [item.title for item in service.visible_windows("browser")] == ["Browser"]


def test_foreground_requires_prior_selection() -> None:
    service, _ = make_service()
    with pytest.raises(WindowMetadataError):
        service.bring_selected_to_front()


def test_foreground_targets_selected_identifier() -> None:
    service, backend = make_service()
    service.visible_windows()
    service.select_window(2)
    service.bring_selected_to_front()
    assert backend.foreground_ids == ["2"]


def test_clear_session_invalidates_selection() -> None:
    service, _ = make_service()
    service.visible_windows()
    service.select_window(1)
    service.clear_session()
    with pytest.raises(WindowMetadataError):
        service.bring_selected_to_front()
