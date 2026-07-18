import os
from pathlib import Path

import pytest

from omega.understanding import CommandParser
from tests.folder_support import build_folder_dispatcher

pytestmark = pytest.mark.skipif(
    os.environ.get("OMEGA_RUN_WINDOWS_FOLDER_INTEGRATION_TESTS") != "1",
    reason="Windows folder integration tests are explicit opt-in tests.",
)


def test_isolated_folder_workflow(tmp_path: Path) -> None:
    roots = {name: tmp_path / name for name in ("desktop", "documents", "downloads")}
    for root in roots.values():
        root.mkdir()
    dispatcher = build_folder_dispatcher(roots)
    parser = CommandParser()
    commands = (
        "Create a folder named Projects on Desktop",
        "Rename Projects to Omega Projects on Desktop",
        "Copy the Omega Projects folder from Desktop to Documents",
        "Move the Omega Projects folder from Documents to Downloads",
        "Find a folder named Omega Projects in Downloads",
        "Delete the Omega Projects folder",
    )
    results = [dispatcher.dispatch(parser.parse(command)) for command in commands]
    assert all(result is not None for result in results)
    assert (roots["desktop"] / "Omega Projects").is_dir()
    assert (roots["downloads"] / "Omega Projects").is_dir()
    assert results[-1] is not None and "Phase 8" in results[-1].user_message
