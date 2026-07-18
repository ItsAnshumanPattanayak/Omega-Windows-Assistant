"""Module and console-script entry point for Omega."""

from __future__ import annotations

import sys

from omega.app import OmegaApplication
from omega.core.exceptions import OmegaError


def main() -> int:
    """Initialize Omega and return a conventional process exit code."""
    try:
        return OmegaApplication().run()
    except OmegaError as error:
        print(f"Omega initialization failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
