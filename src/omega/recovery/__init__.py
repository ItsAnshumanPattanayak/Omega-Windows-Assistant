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
)
from omega.recovery.results import RecoveryResult
from omega.recovery.windows_recycle_bin import (
    WindowsRecycleBinService,
    WindowsShellRecycleBinBackend,
)

__all__ = [
    "ProtectedPathChecker",
    "RecoverableActionType",
    "RecoveryConfiguration",
    "RecoveryRecord",
    "RecoveryRecordStatus",
    "RecoveryResourceType",
    "RecoveryResult",
    "RecycleBinBackend",
    "RecycleBinBackendResult",
    "RecycleBinItem",
    "WindowsRecycleBinService",
    "WindowsShellRecycleBinBackend",
]
