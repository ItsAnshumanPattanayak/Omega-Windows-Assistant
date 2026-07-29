"""Frozen executable mode selection shared by packaging and tests."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

from omega.__main__ import main as omega_main


def selected_arguments(executable: Path, arguments: Sequence[str]) -> list[str]:
    """Default only the windowed Omega executable to GUI mode."""

    values = list(arguments)
    if executable.stem.casefold() == "omega" and not values:
        return ["--gui"]
    return values


def frozen_main() -> int:
    """Run the shared Omega CLI with executable-specific defaults."""

    return omega_main(selected_arguments(Path(sys.executable), sys.argv[1:]))
