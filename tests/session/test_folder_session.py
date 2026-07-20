from pathlib import Path

from omega.session import OmegaSession
from tests.folder_support import build_folder_dispatcher


def _session(
    tmp_path: Path,
) -> tuple[OmegaSession, dict[str, Path]]:
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

    dispatcher = build_folder_dispatcher(roots)

    session = OmegaSession(
        {
            "display_name": "Anshuman",
        },
        {
            "activation_phrase": "Hello Omega",
            "shutdown_phrase": "Shut down Omega",
            "active_session_timeout_seconds": 300,
        },
        folder_dispatcher=dispatcher,
        safety_gateway=dispatcher.gateway,
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

    (roots["desktop"] / "Projects" / "README.md").write_text(
        "x",
        encoding="utf-8",
    )

    assert "README.md" in session.handle_input("List files inside Projects on Desktop")

    assert "renamed" in session.handle_input(
        "Rename Projects to Omega Projects on Desktop"
    )

    assert "copied" in session.handle_input(
        "Copy the Omega Projects folder from Desktop to Documents"
    )

    assert "confirm move folder" in session.handle_input(
        "Move the Omega Projects folder from Documents to Downloads"
    )

    assert "moved" in session.handle_input(
        "confirm move folder Omega Projects " "from Documents to Downloads"
    )

    assert "Omega Projects" in session.handle_input(
        "Find a folder named Omega Projects in Downloads"
    )

    target = roots["downloads"] / "Omega Projects"

    deletion = session.handle_input("Delete the Omega Projects folder from Downloads")

    assert "confirm recycle folder Omega Projects from Downloads" in deletion
    assert target.exists()

    recycled = session.handle_input(
        "confirm recycle folder Omega Projects from Downloads"
    )

    assert "Recycle Bin" in recycled
    assert not target.exists()

    assert "Shutting down" in session.handle_input("Shut down Omega")


def test_folder_failure_does_not_crash_help_history_or_shutdown(
    tmp_path: Path,
) -> None:
    session, _ = _session(tmp_path)

    session.handle_input("Hello Omega")

    assert "permission" in session.handle_input(
        "Create a folder named bad:name on Desktop"
    )

    assert "Create a folder" in session.handle_input("show history")

    assert "activate Omega" in session.handle_input("help")

    assert "Shutting down" in session.handle_input("Shut down Omega")
