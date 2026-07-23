"""Narrow execution dispatchers for approved Omega domains."""

from omega.execution.browser_dispatcher import (
    BrowserActionDispatcher,
    BrowserDispatchResult,
)
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
from omega.execution.history_dispatcher import HistoryActionDispatcher

__all__ = [
    "ApplicationActionDispatcher",
    "ApplicationControlCommand",
    "ApplicationDispatchResult",
    "BrowserActionDispatcher",
    "BrowserDispatchResult",
    "FileActionDispatcher",
    "FileControlCommand",
    "FileDispatchResult",
    "FolderActionDispatcher",
    "FolderDispatchResult",
    "HistoryActionDispatcher",
]
