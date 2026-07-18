from pathlib import Path

import pytest

from omega.models import IntentType, RiskLevel
from omega.understanding import CommandParser
from tests.folder_support import build_folder_dispatcher


@pytest.fixture
def logical_roots(tmp_path: Path) -> dict[str, Path]:
    roots = {name: tmp_path / name for name in ("desktop", "documents", "downloads")}
    for root in roots.values():
        root.mkdir()
    return roots


def test_dispatcher_builds_actions_and_preserves_ids(
    logical_roots: dict[str, Path],
) -> None:
    dispatcher = build_folder_dispatcher(logical_roots)
    parsed = CommandParser().parse("Create a folder named Projects on Desktop")
    dispatched = dispatcher.dispatch(parsed)
    assert dispatched is not None and dispatched.result.success
    assert dispatched.command.command_id == dispatched.action.command_id
    assert dispatched.action.intent is IntentType.CREATE_FOLDER
    assert dispatched.action.risk_level is RiskLevel.MEDIUM


def test_delete_is_denied_and_other_domains_are_ignored(
    logical_roots: dict[str, Path],
) -> None:
    dispatcher = build_folder_dispatcher(logical_roots)
    folder = logical_roots["desktop"] / "Projects"
    folder.mkdir()
    deleted = dispatcher.dispatch(CommandParser().parse("Delete the Projects folder"))
    assert deleted is not None and not deleted.result.success
    assert "Phase 8" in deleted.user_message and folder.exists()
    assert dispatcher.dispatch(CommandParser().parse("Open Chrome")) is None
    assert dispatcher.dispatch(CommandParser().parse("Read notes.txt")) is None


def test_incomplete_and_absolute_commands_do_not_execute(
    logical_roots: dict[str, Path],
) -> None:
    dispatcher = build_folder_dispatcher(logical_roots)
    assert dispatcher.dispatch(CommandParser().parse("Create a folder")) is None
    parsed = CommandParser().parse(r"Create a folder named C:\Unsafe on Desktop")
    dispatched = dispatcher.dispatch(parsed)
    assert dispatched is not None and not dispatched.result.success
    assert not (logical_roots["desktop"] / "Unsafe").exists()
