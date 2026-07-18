import os
from pathlib import Path

import pytest

from omega.session import OmegaSession
from tests.file_support import build_file_dispatcher
from tests.folder_support import build_folder_dispatcher

pytestmark = pytest.mark.skipif(
    os.environ.get("OMEGA_RUN_WINDOWS_SAFETY_INTEGRATION_TESTS") != "1",
    reason="Windows safety integration tests are explicit opt-in tests.",
)


def test_disposable_central_confirmation_workflow(tmp_path: Path):
    roots = {name: tmp_path / name for name in ("desktop", "documents", "downloads")}
    for root in roots.values():
        root.mkdir()
    file_dispatcher = build_file_dispatcher(roots)
    gateway = file_dispatcher.gateway
    folder_dispatcher = build_folder_dispatcher(roots)
    folder_dispatcher.gateway = gateway
    session = OmegaSession(
        {"display_name": "Anshuman"},
        {
            "activation_phrase": "Hello Omega",
            "shutdown_phrase": "Shut down Omega",
            "active_session_timeout_seconds": 300,
        },
        file_dispatcher=file_dispatcher,
        folder_dispatcher=folder_dispatcher,
        safety_gateway=gateway,
    )
    session.activate()

    assert "created" in session.handle_input(
        "Create a text file named omega-safety-test on Desktop"
    )
    assert "updated" in session.handle_input(
        'Write "First version" into omega-safety-test.txt on Desktop'
    )
    assert "confirm overwrite" in session.handle_input(
        'Write "Second version" into omega-safety-test.txt on Desktop'
    )
    assert "updated" in session.handle_input(
        "confirm overwrite omega-safety-test.txt on Desktop"
    )
    assert "confirm move" in session.handle_input(
        "Move omega-safety-test.txt from Desktop to Documents"
    )
    assert "moved" in session.handle_input(
        "confirm move omega-safety-test.txt from Desktop to Documents"
    )
    assert "created" in session.handle_input(
        "Create a folder named Omega Safety on Desktop"
    )
    assert "confirm move folder" in session.handle_input(
        "Move the Omega Safety folder from Desktop to Documents"
    )
    assert "moved" in session.handle_input(
        "confirm move folder Omega Safety from Desktop to Documents"
    )
    assert "Phase 8" in session.handle_input(
        "Delete omega-safety-test.txt from Documents"
    )
    assert "arbitrary shell" in session.handle_input(
        "Run PowerShell command Get-Process"
    )
    assert (roots["documents"] / "omega-safety-test.txt").read_text(
        encoding="utf-8"
    ) == "Second version"
