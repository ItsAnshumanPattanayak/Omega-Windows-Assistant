import os
from pathlib import Path

import pytest

from omega.understanding import CommandParser
from tests.file_support import build_file_dispatcher

pytestmark = pytest.mark.skipif(
    os.environ.get("OMEGA_RUN_WINDOWS_FILE_INTEGRATION_TESTS") != "1",
    reason="Windows file integration tests are explicit opt-in tests.",
)


def test_isolated_phase5_file_workflow(tmp_path: Path) -> None:
    roots = {name: tmp_path / name for name in ("desktop", "documents", "downloads")}
    for root in roots.values():
        root.mkdir()
    dispatcher = build_file_dispatcher(roots)
    parser = CommandParser()

    commands = (
        "Create a text file named author on Desktop",
        'Write "Hello from Omega" into author.txt on Desktop',
        'Append "Second line" to author.txt on Desktop',
        "Read author.txt from Desktop",
        "Rename author.txt to writer.txt",
        "Copy writer.txt from Desktop to Documents",
        "Move writer.txt from Documents to Downloads",
        "Find writer.txt in Downloads",
    )
    results = [dispatcher.dispatch(parser.parse(command)) for command in commands]

    assert all(result is not None and result.result.success for result in results)
    destination = roots["downloads"] / "writer.txt"
    assert destination.read_text(encoding="utf-8") == "Hello from OmegaSecond line"
    assert not (roots["documents"] / "writer.txt").exists()
    assert (roots["desktop"] / "writer.txt").exists()
