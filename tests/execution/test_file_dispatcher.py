from pathlib import Path

from omega.models import IntentType, PermissionDecision, RiskLevel
from omega.understanding import CommandParser
from tests.file_support import build_file_dispatcher


def _roots(tmp_path: Path) -> dict[str, Path]:
    roots = {name: tmp_path / name for name in ("desktop", "documents", "downloads")}
    for root in roots.values():
        root.mkdir()
    return roots


def test_dispatches_file_workflow_with_preserved_ids_and_risks(tmp_path: Path) -> None:
    roots = _roots(tmp_path)
    dispatcher = build_file_dispatcher(roots)
    parser = CommandParser()

    created = dispatcher.dispatch(
        parser.parse("Create a text file named author on Desktop")
    )
    written = dispatcher.dispatch(
        parser.parse('Write "Anshuman" into author.txt on Desktop')
    )
    read = dispatcher.dispatch(parser.parse("Read author.txt from Desktop"))
    copied = dispatcher.dispatch(
        parser.parse("Copy author.txt from Desktop to Documents")
    )

    assert created is not None and created.result.success
    assert written is not None and written.result.success
    assert read is not None and read.result.user_message == "Anshuman"
    assert copied is not None and copied.result.success
    assert created.action.risk_level is RiskLevel.MEDIUM
    assert read.action.risk_level is RiskLevel.LOW
    assert written.action.risk_level is RiskLevel.MEDIUM
    assert created.action.command_id == created.command.command_id
    assert (roots["documents"] / "author.txt").read_text(encoding="utf-8") == "Anshuman"


def test_delete_is_denied_and_folder_unknown_ambiguous_or_absolute_do_not_execute(
    tmp_path: Path,
) -> None:
    roots = _roots(tmp_path)
    dispatcher = build_file_dispatcher(roots)
    parser = CommandParser()
    target = roots["desktop"] / "notes.txt"
    target.write_text("safe", encoding="utf-8")

    deleted = dispatcher.dispatch(parser.parse("Delete notes.txt from Desktop"))
    absolute = dispatcher.dispatch(parser.parse(r"Create notes.txt in C:\Windows"))

    assert deleted is not None and not deleted.result.success
    assert deleted.action.permission_decision is PermissionDecision.DENY
    assert "Phase 8" in deleted.user_message and target.exists()
    assert dispatcher.dispatch(parser.parse("Create a folder named Work")) is None
    assert dispatcher.dispatch(parser.parse("Tell me a joke")) is None
    assert absolute is not None and not absolute.result.success


def test_exact_overwrite_controls_are_scoped_and_clearable(tmp_path: Path) -> None:
    roots = _roots(tmp_path)
    dispatcher = build_file_dispatcher(roots)
    parser = CommandParser()
    target = roots["desktop"] / "notes.txt"
    target.write_text("old", encoding="utf-8")

    pending = dispatcher.dispatch(parser.parse('Write "new" into notes.txt on Desktop'))
    wrong = dispatcher.dispatch_control("confirm overwrite other.txt on Desktop")
    confirmed = dispatcher.dispatch_control(
        "  CONFIRM OVERWRITE notes.txt on Desktop  "
    )

    assert pending is not None and not pending.result.success
    assert wrong is not None and not wrong.result.success
    assert confirmed is not None and confirmed.result.success
    assert target.read_text(encoding="utf-8") == "new"
    assert dispatcher.dispatch_control("yes") is not None
    dispatcher.clear_pending_confirmations()


def test_search_extension_and_metadata_dispatch(tmp_path: Path) -> None:
    roots = _roots(tmp_path)
    dispatcher = build_file_dispatcher(roots)
    parser = CommandParser()
    (roots["downloads"] / "tool.py").write_text("", encoding="utf-8")

    found = dispatcher.dispatch(parser.parse("Find Python files in Downloads"))
    info = dispatcher.dispatch(
        parser.parse("Show information about tool.py in Downloads")
    )

    assert found is not None and "tool.py" in found.user_message
    assert info is not None and info.command.intent is IntentType.GET_FILE_INFORMATION
