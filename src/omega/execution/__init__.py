"""Narrow execution dispatchers for approved Omega domains."""

from omega.execution.dispatcher import (
    ApplicationActionDispatcher,
    ApplicationControlCommand,
    ApplicationDispatchResult,
)
from omega.execution.file_dispatcher import (
    FileActionDispatcher,
    FileControlCommand,
    FileDispatchResult,
)
from omega.execution.folder_dispatcher import (
    FolderActionDispatcher,
    FolderDispatchResult,
)

__all__ = [
    "ApplicationActionDispatcher",
    "ApplicationControlCommand",
    "ApplicationDispatchResult",
    "FileActionDispatcher",
    "FileControlCommand",
    "FileDispatchResult",
    "FolderActionDispatcher",
    "FolderDispatchResult",
]
