import subprocess
import sys
from pathlib import Path

from omega.app import OmegaApplication


def test_help_process_does_not_import_application_graph() -> None:
    script = (
        "import sys; from omega.__main__ import main; "
        "assert main(['--help']) == 0; assert 'omega.app' not in sys.modules"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_application_shutdown_is_idempotent(tmp_path: Path) -> None:
    application = OmegaApplication(database_path=tmp_path / "omega.db")
    application.shutdown()
    application.shutdown()
    assert application._shutdown_complete  # noqa: SLF001
