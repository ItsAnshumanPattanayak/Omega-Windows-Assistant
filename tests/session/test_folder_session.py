from pathlib import Path

from omega.session import OmegaSession
from tests.folder_support import build_folder_dispatcher


def _session(tmp_path: Path) -> tuple[OmegaSession, dict[str, Path]]:
    roots = {name: tmp_path / name for name in ("desktop", "documents", "downloads")}
    for root in roots.values():
        root.mkdir()
    session = OmegaSession(
        {"display_name": "Anshuman"},
        {
            "activation_phrase": "Hello Omega",
            "shutdown_phrase": "Shut down Omega",
            "active_session_timeout_seconds": 300,
        },
        folder_dispatcher=build_folder_dispatcher(roots),
    )
    return session, roots


def test_inactive_folder_command_has_no_effect_and_lifecycle_succeeds(
    tmp_path: Path,
) -> None:
    session, roots = _session(tmp_path)
    assert "inactive" in session.handle_input(
        "Create a folder named Projects on Desktop"
    )
    assert not (roots["desktop"] / "Projects").exists()
    session.handle_input("Hello Omega")
    assert "created successfully" in session.handle_input(
        "Create a folder named Projects on Desktop"
    )
    (roots["desktop"] / "Projects" / "README.md").write_text("x", encoding="utf-8")
    assert "README.md" in session.handle_input("List files inside Projects on Desktop")
    assert "renamed" in session.handle_input(
        "Rename Projects to Omega Projects on Desktop"
    )
    assert "copied" in session.handle_input(
        "Copy the Omega Projects folder from Desktop to Documents"
    )
    assert "moved" in session.handle_input(
        "Move the Omega Projects folder from Documents to Downloads"
    )
    assert "Omega Projects" in session.handle_input(
        "Find a folder named Omega Projects in Downloads"
    )
    deletion = session.handle_input("Delete the Omega Projects folder")
    assert "Phase 8" in deletion and (roots["downloads"] / "Omega Projects").exists()
    assert "Shutting down" in session.handle_input("Shut down Omega")


def test_folder_failure_does_not_crash_help_history_or_shutdown(tmp_path: Path) -> None:
    session, _ = _session(tmp_path)
    session.handle_input("Hello Omega")
    assert "invalid characters" in session.handle_input(
        "Create a folder named bad:name on Desktop"
    )
    assert "Create a folder" in session.handle_input("show history")
    assert "activate Omega" in session.handle_input("help")
    assert "Shutting down" in session.handle_input("Shut down Omega")
