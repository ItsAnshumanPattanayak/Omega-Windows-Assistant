import pytest

from omega.desktop_utilities import (
    DesktopUtilitiesConfiguration,
    DesktopUtilityConfigurationError,
)


def test_defaults_are_private_and_bounded() -> None:
    value = DesktopUtilitiesConfiguration()
    assert not value.clipboard_history_enabled
    assert not value.allow_background_clipboard_monitoring
    assert not value.allow_background_screenshot_capture
    assert value.screenshot_directory is None


@pytest.mark.parametrize(
    "field",
    [
        "clipboard_history_enabled",
        "allow_background_clipboard_monitoring",
        "allow_background_screenshot_capture",
    ],
)
def test_forbidden_background_or_history_setting(field: str) -> None:
    with pytest.raises(DesktopUtilityConfigurationError):
        DesktopUtilitiesConfiguration.from_mapping({field: True})


@pytest.mark.parametrize(
    "field",
    [
        "require_confirmation_for_clear_clipboard",
        "require_confirmation_for_delete_screenshot",
    ],
)
def test_destructive_confirmation_cannot_be_disabled(field: str) -> None:
    with pytest.raises(DesktopUtilityConfigurationError):
        DesktopUtilitiesConfiguration.from_mapping({field: False})


@pytest.mark.parametrize("value", ["bmp", "gif", "PNG"])
def test_invalid_screenshot_format(value: str) -> None:
    with pytest.raises(DesktopUtilityConfigurationError):
        DesktopUtilitiesConfiguration(screenshot_format=value)


def test_unknown_setting_rejected() -> None:
    with pytest.raises(DesktopUtilityConfigurationError):
        DesktopUtilitiesConfiguration.from_mapping({"monitor_clipboard": True})
