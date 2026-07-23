import subprocess
import sys
from pathlib import Path


def test_import_starts_no_worker_and_creates_no_runtime_files(
    tmp_path: Path,
) -> None:
    script = (
        "import pathlib, threading; "
        "before={p.name for p in pathlib.Path('.').iterdir()}; "
        "import omega.scheduling; "
        "after={p.name for p in pathlib.Path('.').iterdir()}; "
        "assert before == after; "
        "assert not any(t.name == 'omega-scheduler' for t in threading.enumerate())"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
