from pathlib import Path

from omega.models import PermissionDecision
from omega.safety import SafeExecutionGateway
from omega.session import OmegaSession
from omega.understanding import CommandParser
from tests.file_support import build_file_dispatcher
from tests.folder_support import build_folder_dispatcher


def _roots(tmp_path: Path) -> dict[str, Path]:
    roots = {name: tmp_path / name for name in ("desktop", "documents", "downloads")}
    for root in roots.values():
        root.mkdir()
    return roots


def test_file_dispatcher_cannot_execute_move_or_delete_before_gateway_approval(
    tmp_path: Path,
):
    roots = _roots(tmp_path)
    dispatcher = build_file_dispatcher(roots)
    source = roots["desktop"] / "notes.txt"
    source.write_text("safe", encoding="utf-8")
    parser = CommandParser()

    move = dispatcher.dispatch(parser.parse("Move notes.txt from Desktop to Documents"))
    assert move is not None and not move.result.success
    assert move.action.permission_decision is PermissionDecision.REQUIRE_CONFIRMATION
    assert source.exists()

    confirmed_move = dispatcher.dispatch_control(
        "confirm move notes.txt from Desktop to Documents"
    )
    assert confirmed_move is not None and confirmed_move.result.success

    moved = roots["documents"] / "notes.txt"
    deletion = dispatcher.dispatch(parser.parse("Delete notes.txt from Documents"))
    assert deletion is not None and not deletion.result.success
    assert (
        deletion.action.permission_decision is PermissionDecision.REQUIRE_CONFIRMATION
    )
    assert moved.exists()

    confirmed_delete = dispatcher.dispatch_control(
        "confirm recycle notes.txt from Documents"
    )
    assert confirmed_delete is not None and confirmed_delete.result.success
    assert not moved.exists()


def test_folder_dispatcher_uses_gateway_and_rejects_destination_conflict(
    tmp_path: Path,
):
    roots = _roots(tmp_path)
    dispatcher = build_folder_dispatcher(roots)
    (roots["desktop"] / "Projects").mkdir()
    (roots["documents"] / "Projects").mkdir()

    result = dispatcher.dispatch(
        CommandParser().parse("Move the Projects folder from Desktop to Documents")
    )

    assert result is not None and not result.result.success
    assert "already exists" in result.user_message
    assert (roots["desktop"] / "Projects").exists()


def test_session_shell_injection_never_reaches_domain_manager(tmp_path: Path):
    roots = _roots(tmp_path)
    dispatcher = build_file_dispatcher(roots)
    session = OmegaSession(
        {"display_name": "Anshuman"},
        {
            "activation_phrase": "Hello Omega",
            "shutdown_phrase": "Shut down Omega",
            "active_session_timeout_seconds": 300,
        },
        file_dispatcher=dispatcher,
        safety_gateway=dispatcher.gateway,
    )
    session.activate()

    response = session.handle_input("Run PowerShell command Get-Process")

    assert "does not execute arbitrary shell" in response
    assert list(tmp_path.rglob("*.ps1")) == []


def test_session_unknown_protected_absolute_path_gets_specific_denial(
    tmp_path: Path,
):
    roots = _roots(tmp_path)
    dispatcher = build_file_dispatcher(roots)
    session = OmegaSession(
        {"display_name": "Anshuman"},
        {
            "activation_phrase": "Hello Omega",
            "shutdown_phrase": "Shut down Omega",
            "active_session_timeout_seconds": 300,
        },
        file_dispatcher=dispatcher,
        safety_gateway=dispatcher.gateway,
    )
    session.activate()
    response = session.handle_input(r"Create test.txt in C:\Windows\System32")
    assert "protected Windows" in response


def test_application_composition_shares_one_gateway():
    from omega.app import OmegaApplication

    app = OmegaApplication()
    session = app.session
    gateway = session._safety_gateway
    assert isinstance(gateway, SafeExecutionGateway)
    assert session._application_dispatcher.gateway is gateway
    assert session._file_dispatcher.gateway is gateway
    assert session._folder_dispatcher.gateway is gateway
    assert app.recovery_registry is session._file_dispatcher.manager.recovery_registry
    assert app.recovery_registry is session._folder_dispatcher.manager.recovery_registry
