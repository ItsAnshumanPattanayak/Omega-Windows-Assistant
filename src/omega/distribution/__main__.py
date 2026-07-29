"""Developer command for validating an already-built distribution."""

from __future__ import annotations

import argparse
from pathlib import Path

from omega.core.exceptions import DistributionError
from omega.distribution.verification import require_safe_distribution


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify an Omega distribution")
    parser.add_argument("directory", type=Path)
    arguments = parser.parse_args()
    try:
        result = require_safe_distribution(arguments.directory)
    except DistributionError as error:
        print(f"Omega package verification failed: {error}")
        return 1
    print(
        f"Omega package verification passed: {result.files_inspected} files inspected."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
