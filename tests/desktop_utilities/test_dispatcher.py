from pathlib import Path
from uuid import uuid4

from omega.desktop_utilities import (
    ClipboardService,
    DesktopInformationService,
    DesktopUtilitiesConfiguration,
    FakeClipboardBackend,
    FakeScreenInformationProvider,
    FakeScreenshotBackend,
    FakeWindowInformationProvider,
    ScreenshotService,
)
from omega.execution import DesktopUtilityActionDispatcher
from omega.safety import SafeExecutionGateway
from omega.understanding import CommandParser


def dispatcher(
    tmp_path: Path,
) -> tuple[
    DesktopUtilityActionDispatcher,
    FakeClipboardBackend,
    FakeScreenshotBackend,
    SafeExecutionGateway,
]:
    config = DesktopUtilitiesConfiguration()
    clipboard = FakeClipboardBackend()
    screenshot = FakeScreenshotBackend()
    gateway = SafeExecutionGateway()
    value = DesktopUtilityActionDispatcher(
        ClipboardService(config, clipboard),
        ScreenshotService(config, screenshot, tmp_path),
        DesktopInformationService(
            config, FakeScreenInformationProvider(), FakeWindowInformationProvider()
        ),
        gateway,
    )
    return value, clipboard, screenshot, gateway


def parse(text: str):
    return CommandParser().parse(text, uuid4())


def test_copy_routes_through_gateway_and_redacts_record(tmp_path: Path) -> None:
    value, clipboard, _, _ = dispatcher(tmp_path)
    result = value.dispatch(parse("copy private text to clipboard"))
    assert result is not None and result.result.success
    assert clipboard.text == "private text"
    assert "private text" not in result.command.original_text
    assert result.command.metadata["privacy_redacted"] is True


def test_capture_happens_only_when_dispatched(tmp_path: Path) -> None:
    value, _, backend, _ = dispatcher(tmp_path)
    assert backend.capture_count == 0
    result = value.dispatch(parse("take a screenshot"))
    assert result is not None and result.result.success
    assert backend.capture_count == 1


def test_selected_display_is_structured_for_capture(tmp_path: Path) -> None:
    value, _, backend, _ = dispatcher(tmp_path)
    result = value.dispatch(parse("capture monitor 2"))
    assert result is not None and result.result.success
    assert backend.capture_count == 1


def test_clear_requires_exact_confirmation(tmp_path: Path) -> None:
    value, clipboard, _, gateway = dispatcher(tmp_path)
    clipboard.text = "keep"
    session_id = uuid4()
    result = value.dispatch(CommandParser().parse("clear clipboard", session_id))
    assert result is not None and not result.result.success
    assert clipboard.text == "keep"
    assert gateway.handle_confirmation("yes", session_id) is not None
    assert clipboard.text == "keep"
    confirmed = gateway.handle_confirmation("confirm clear clipboard", session_id)
    assert confirmed is not None and confirmed.result.success
    assert clipboard.text == ""


def test_changed_clipboard_invalidates_confirmation(tmp_path: Path) -> None:
    value, clipboard, _, gateway = dispatcher(tmp_path)
    clipboard.text = "first"
    session_id = uuid4()
    value.dispatch(CommandParser().parse("clear clipboard", session_id))
    clipboard.text = "changed"
    result = gateway.handle_confirmation("confirm clear clipboard", session_id)
    assert result is not None and not result.result.success
    assert clipboard.text == "changed"


def test_screenshot_delete_requires_exact_confirmation_and_recovery(
    tmp_path: Path,
) -> None:
    value, _, _, gateway = dispatcher(tmp_path)
    deleted: list[Path] = []
    value.screenshots.deleter = deleted.append
    value.dispatch(parse("take a screenshot"))
    record = value.screenshots.select()
    session_id = uuid4()
    proposal = value.dispatch(
        CommandParser().parse("delete last screenshot", session_id)
    )
    assert proposal is not None and not proposal.result.success
    assert deleted == []
    confirmed = gateway.handle_confirmation(
        f"confirm delete screenshot {record.screenshot_id}", session_id
    )
    assert confirmed is not None and confirmed.result.success
    assert deleted == [record.path]


def test_unrelated_command_is_not_claimed(tmp_path: Path) -> None:
    value, _, _, _ = dispatcher(tmp_path)
    assert value.dispatch(parse("open chrome")) is None


def test_fake_adapters_make_no_real_desktop_or_network_operations(
    tmp_path: Path,
) -> None:
    value, _, screenshot, _ = dispatcher(tmp_path)
    value.dispatch(parse("take a screenshot"))
    assert screenshot.real_desktop_operations == 0
    assert screenshot.network_operations == 0
