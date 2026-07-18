"""Convenience entry point for running Omega from a source checkout."""

from __future__ import annotations

import sys
from collections.abc import Callable
from importlib import import_module
from pathlib import Path
from typing import cast

PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = PROJECT_ROOT / "src"

if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

main = cast(Callable[[], int], import_module("omega.__main__").main)


if __name__ == "__main__":
    raise SystemExit(main())
