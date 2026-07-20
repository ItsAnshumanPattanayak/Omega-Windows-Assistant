"""Test-only recovery helpers with an isolated fake Recycle Bin."""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from omega.recovery import (
    RecoveryConfiguration,
    RecoveryRegistry,
    RecycleBinBackendResult,
    WindowsRecycleBinService,
)


class IsolatedRecycleBinBackend:
    """Move resources into a private temporary recycle directory."""

    def __init__(self, recycle_root: Path) -> None:
        self.recycle_root = recycle_root
        self.recycle_root.mkdir(parents=True, exist_ok=True)

    def recycle(self, path: Path) -> RecycleBinBackendResult:
        destination = self.recycle_root / f"{uuid4().hex}-{path.name}"
        shutil.move(str(path), str(destination))
        return RecycleBinBackendResult(
            success=True,
            code="recycled",
            message="The item was moved to the isolated test Recycle Bin.",
            recycle_bin_reference=str(destination),
        )


def build_test_recovery(
    root: Path,
) -> tuple[WindowsRecycleBinService, RecoveryRegistry]:
    configuration = RecoveryConfiguration()
    registry = RecoveryRegistry(configuration)
    service = WindowsRecycleBinService(
        configuration,
        backend=IsolatedRecycleBinBackend(root / ".omega-test-recycle-bin"),
        protected_path_checker=lambda path: False,
        platform_name="win32",
    )
    return service, registry
