import pytest

from omega.desktop_utilities import (
    ClipboardError,
    ClipboardService,
    DesktopUtilitiesConfiguration,
    DesktopUtilityUnavailableError,
    FakeClipboardBackend,
)


def service(text: str | None = "") -> tuple[ClipboardService, FakeClipboardBackend]:
    backend = FakeClipboardBackend(text)
    return ClipboardService(DesktopUtilitiesConfiguration(), backend), backend


def test_write_and_read_normalize_newlines() -> None:
    value, backend = service()
    assert value.write("one\r\ntwo") == 7
    assert backend.text == "one\ntwo"
    assert value.read() == "one\ntwo"


def test_display_is_bounded_and_reports_truncation() -> None:
    config = DesktopUtilitiesConfiguration(
        maximum_clipboard_characters=10, maximum_clipboard_display_characters=3
    )
    value = ClipboardService(config, FakeClipboardBackend("abcdef"))
    assert value.displayed() == ("abc", True)


def test_search_is_case_insensitive_and_bounded() -> None:
    value, _ = service("Alpha alpha")
    assert value.search("ALPHA") == (0, 6)


def test_clear_forgets_session_copy() -> None:
    value, backend = service("private")
    value.read()
    value.clear()
    assert backend.text == ""
    with pytest.raises(ClipboardError):
        _ = value.last_text


@pytest.mark.parametrize("length", [1, 50_001])
def test_invalid_or_oversized_text_rejected(length: int) -> None:
    value, _ = service()
    with pytest.raises(ClipboardError):
        value.write("x\x00y" if length == 1 else "x" * length)


def test_non_text_clipboard_rejected() -> None:
    value, _ = service(None)
    with pytest.raises(ClipboardError):
        value.read()


def test_disabled_clipboard_does_not_touch_backend() -> None:
    backend = FakeClipboardBackend("secret")
    value = ClipboardService(
        DesktopUtilitiesConfiguration(clipboard_enabled=False), backend
    )
    with pytest.raises(DesktopUtilityUnavailableError):
        value.read()
    assert backend.operations == 0


def test_instances_do_not_share_clipboard_state() -> None:
    first, _ = service()
    second, _ = service()
    first.write("one")
    with pytest.raises(ClipboardError):
        _ = second.last_text
