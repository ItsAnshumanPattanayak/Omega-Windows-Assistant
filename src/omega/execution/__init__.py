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
from omega.execution.knowledge_dispatcher import (
    KnowledgeActionDispatcher,
    KnowledgeDispatchResult,
)
from omega.execution.productivity_dispatcher import (
    ProductivityActionDispatcher,
    ProductivityDispatchResult,
)
from omega.execution.scheduling_dispatcher import (
    SchedulingActionDispatcher,
    SchedulingDispatchResult,
)
from omega.execution.system_dispatcher import (
    SystemActionDispatcher,
    SystemDispatchResult,
)

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
    "KnowledgeActionDispatcher",
    "KnowledgeDispatchResult",
    "ProductivityActionDispatcher",
    "ProductivityDispatchResult",
    "SchedulingActionDispatcher",
    "SchedulingDispatchResult",
    "SystemActionDispatcher",
    "SystemDispatchResult",
]
