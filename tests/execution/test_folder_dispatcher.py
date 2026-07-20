from pathlib import Path
from uuid import UUID

import pytest

from omega.models import IntentType, PermissionDecision, RiskLevel
from omega.understanding import CommandParser
from tests.folder_support import build_folder_dispatcher


@pytest.fixture
def logical_roots(tmp_path: Path) -> dict[str, Path]:
    roots = {
        name: tmp_path / name
        for name in (
            "desktop",
            "documents",
            "downloads",
        )
    }

    for root in roots.values():
        root.mkdir()

    return roots


def test_dispatcher_builds_actions_and_preserves_ids(
    logical_roots: dict[str, Path],
) -> None:
    dispatcher = build_folder_dispatcher(logical_roots)

    dispatched = dispatcher.dispatch(
        CommandParser().parse("Create a folder named Projects on Desktop")
    )

    assert dispatched is not None
    assert dispatched.result.success
    assert dispatched.command.command_id == dispatched.action.command_id
    assert dispatched.action.intent is IntentType.CREATE_FOLDER
    assert dispatched.action.risk_level is RiskLevel.MEDIUM


def test_delete_requires_confirmation_and_registers_recovery(
    logical_roots: dict[str, Path],
) -> None:
    dispatcher = build_folder_dispatcher(logical_roots)
    folder = logical_roots["desktop"] / "Projects"
    folder.mkdir()

    pending = dispatcher.dispatch(CommandParser().parse("Delete the Projects folder"))

    assert pending is not None
    assert not pending.result.success
    assert pending.action.permission_decision is PermissionDecision.REQUIRE_CONFIRMATION
    assert pending.action.risk_level is RiskLevel.CRITICAL
    assert "confirm recycle folder Projects from Desktop" in pending.user_message
    assert folder.exists()

    confirmed = dispatcher.gateway.handle_confirmation(
        "confirm recycle folder Projects from Desktop",
        UUID(int=0),
    )

    assert confirmed is not None
    assert confirmed.result.success
    assert not folder.exists()

    registry = dispatcher.manager.recovery_registry

    assert registry is not None
    assert len(registry.list_restorable()) == 1


def test_other_domains_are_ignored(
    logical_roots: dict[str, Path],
) -> None:
    dispatcher = build_folder_dispatcher(logical_roots)

    assert dispatcher.dispatch(CommandParser().parse("Open Chrome")) is None
    assert dispatcher.dispatch(CommandParser().parse("Read notes.txt")) is None


def test_incomplete_and_absolute_commands_do_not_execute(
    logical_roots: dict[str, Path],
) -> None:
    dispatcher = build_folder_dispatcher(logical_roots)

    assert dispatcher.dispatch(CommandParser().parse("Create a folder")) is None

    parsed = CommandParser().parse(r"Create a folder named C:\Unsafe on Desktop")
    dispatched = dispatcher.dispatch(parsed)

    assert dispatched is not None
    assert not dispatched.result.success
    assert not (logical_roots["desktop"] / "Unsafe").exists()
