"""Public services and records for controlled folder management."""

from omega.folders.creator import FolderCreator
from omega.folders.definitions import FolderOperationSettings
from omega.folders.inspector import FolderInspector
from omega.folders.manager import FolderManager
from omega.folders.opener import WindowsFolderOpener
from omega.folders.operations import FolderOperations
from omega.folders.results import (
    FolderListing,
    FolderMetadata,
    FolderSearchMatch,
    FolderTreeSnapshot,
    ValidatedFolderPath,
)
from omega.folders.search import FolderSearch
from omega.folders.validator import (
    FolderPathValidator,
    WindowsFolderNameValidator,
    is_link_or_reparse,
)

__all__ = [
    "FolderCreator",
    "FolderInspector",
    "FolderListing",
    "FolderManager",
    "FolderMetadata",
    "FolderOperationSettings",
    "FolderOperations",
    "FolderPathValidator",
    "FolderSearch",
    "FolderSearchMatch",
    "FolderTreeSnapshot",
    "ValidatedFolderPath",
    "WindowsFolderNameValidator",
    "WindowsFolderOpener",
    "is_link_or_reparse",
]
