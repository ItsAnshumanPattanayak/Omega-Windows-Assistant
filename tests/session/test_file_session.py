from pathlib import Path

from omega.session import OmegaSession
from tests.file_support import build_file_dispatcher


def _session(
    tmp_path: Path, clock: list[float] | None = None
) -> tuple[OmegaSession, dict[str, Path]]:
    roots = {name: tmp_path / name for name in ("desktop", "documents", "downloads")}
    for root in roots.values():
        root.mkdir()
    current = clock or [0.0]
    session = OmegaSession(
        {"display_name": "Anshuman"},
        {
            "activation_phrase": "Hello Omega",
            "shutdown_phrase": "Shut down Omega",
            "active_session_timeout_seconds": 10,
        },
        monotonic_clock=lambda: current[0],
        file_dispatcher=build_file_dispatcher(roots, clock=lambda: current[0]),
    )
    return session, roots


def test_inactive_command_has_no_effect_and_full_file_lifecycle_is_safe(
    tmp_path: Path,
) -> None:
    session, roots = _session(tmp_path)
    inactive = session.handle_input("Create a text file named author on Desktop")
    assert "inactive" in inactive and not (roots["desktop"] / "author.txt").exists()

    session.handle_input("Hello Omega")
    assert "created successfully" in session.handle_input(
        "Create a text file named author on Desktop"
    )
    assert "updated successfully" in session.handle_input(
        'Write "Anshuman" into author.txt on Desktop'
    )
    assert session.handle_input("Read author.txt from Desktop") == "Anshuman"
    assert "appended" in session.handle_input(
        'Append "Second line" to author.txt on Desktop'
    )
    assert "renamed" in session.handle_input("Rename author.txt to writer.txt")
    assert "copied" in session.handle_input("Copy writer.txt from Desktop to Documents")
    assert "moved" in session.handle_input(
        "Move writer.txt from Documents to Downloads"
    )
    assert "writer.txt" in session.handle_input("Find writer.txt in Downloads")
    deletion = session.handle_input("Delete writer.txt from Downloads")
    assert "Phase 8" in deletion and (roots["downloads"] / "writer.txt").exists()
    assert "Shutting down" in session.handle_input("Shut down Omega")


def test_overwrite_confirmation_cancel_and_history(tmp_path: Path) -> None:
    session, roots = _session(tmp_path)
    path = roots["desktop"] / "notes.txt"
    path.write_text("old", encoding="utf-8")
    session.handle_input("Hello Omega")
    pending = session.handle_input('Write "new" into notes.txt on Desktop')
    assert "confirm overwrite notes.txt" in pending
    assert session.handle_input("yes") == "I don't understand that command yet."
    assert path.read_text(encoding="utf-8") == "old"
    assert "cancelled" in session.handle_input("cancel overwrite notes.txt on Desktop")
    assert path.read_text(encoding="utf-8") == "old"
    session.handle_input('Write "new" into notes.txt on Desktop')
    assert "updated successfully" in session.handle_input(
        "confirm overwrite notes.txt on Desktop"
    )
    assert path.read_text(encoding="utf-8") == "new"
    history = session.handle_input("show history")
    assert 'Write "new"' in history and "confirm overwrite" in history


def test_timeout_clears_pending_file_content_and_application_commands_remain_parsed(
    tmp_path: Path,
) -> None:
    clock = [0.0]
    session, roots = _session(tmp_path, clock)
    path = roots["desktop"] / "notes.txt"
    path.write_text("old", encoding="utf-8")
    session.handle_input("Hello Omega")
    session.handle_input('Write "new" into notes.txt on Desktop')
    clock[0] = 11
    assert "timed out" in (session.check_timeout() or "")
    session.handle_input("Hello Omega")
    assert "No matching" in session.handle_input(
        "confirm overwrite notes.txt on Desktop"
    )
    application = session.handle_input("Open Chrome")
    assert "open Chrome" in application and "not available" in application


def test_file_failure_does_not_crash_and_shutdown_has_priority(tmp_path: Path) -> None:
    session, roots = _session(tmp_path)
    session.handle_input("Hello Omega")
    assert "does not create executable" in session.handle_input(
        "Create virus.bat on Desktop"
    )
    assert not (roots["desktop"] / "virus.bat").exists()
    assert "Shutting down" in session.handle_input("Shut down Omega")
