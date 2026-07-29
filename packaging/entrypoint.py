"""Shared frozen entry point for the console and windowed executables."""

from __future__ import annotations

from omega.distribution.entrypoint import frozen_main

if __name__ == "__main__":
    raise SystemExit(frozen_main())
