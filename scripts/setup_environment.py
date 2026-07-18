"""Safe helper for preparing an Omega development environment."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from omega.utils.constants import MINIMUM_PYTHON_VERSION  # noqa: E402
from omega.utils.paths import ensure_runtime_directories  # noqa: E402


def main() -> int:
    """Confirm prerequisites and display safe, repeatable setup guidance."""
    minimum = ".".join(str(part) for part in MINIMUM_PYTHON_VERSION)
    if sys.version_info < MINIMUM_PYTHON_VERSION:
        print(f"Python {minimum}+ is required; found {sys.version.split()[0]}.")
        return 1

    ensure_runtime_directories()
    print(f"Python {sys.version.split()[0]} is supported.")
    print("Required runtime directories are ready.")
    print("\nWindows PowerShell setup:")
    print("  py -m venv .venv")
    print("  .\\.venv\\Scripts\\Activate.ps1")
    print("  python -m pip install --upgrade pip")
    print("  python -m pip install -r requirements-dev.txt")
    print("\nThese commands install only into the project virtual environment.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
