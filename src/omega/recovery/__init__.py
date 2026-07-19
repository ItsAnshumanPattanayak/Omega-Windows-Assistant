"""Recoverable deletion and undo foundations for Omega."""

from omega.recovery.configuration import RecoveryConfiguration
from omega.recovery.models import (
    RecoverableActionType,
    RecoveryRecord,
    RecoveryRecordStatus,
    RecoveryResourceType,
    RecycleBinItem,
)
from omega.recovery.protocols import (
    ProtectedPathChecker,
    RecycleBinBackend,
    RecycleBinBackendResult,
    RestoreBackend,
    RestoreBackendResult,
)
from omega.recovery.registry import RecoveryRegistry
from omega.recovery.restore import (
    RecoveryRestoreService,
    UnavailableRestoreBackend,
)
from omega.recovery.results import RecoveryResult
from omega.recovery.store import InMemoryRecoveryRecordStore
from omega.recovery.undo import RecoveryUndoService
from omega.recovery.windows_recycle_bin import (
    WindowsRecycleBinService,
    WindowsShellRecycleBinBackend,
)

__all__ = [
    "InMemoryRecoveryRecordStore",
    "ProtectedPathChecker",
    "RecoverableActionType",
    "RecoveryConfiguration",
    "RecoveryRecord",
    "RecoveryRecordStatus",
    "RecoveryRegistry",
    "RecoveryResourceType",
    "RecoveryRestoreService",
    "RecoveryResult",
    "RecoveryUndoService",
    "RecycleBinBackend",
    "RecycleBinBackendResult",
    "RecycleBinItem",
    "RestoreBackend",
    "RestoreBackendResult",
    "UnavailableRestoreBackend",
    "WindowsRecycleBinService",
    "WindowsShellRecycleBinBackend",
]
