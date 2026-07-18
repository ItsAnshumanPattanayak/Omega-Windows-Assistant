"""Public services and definitions for controlled file management."""

from omega.files.definitions import (
    BLOCKED_EXTENSIONS,
    LOGICAL_LOCATIONS,
    OPEN_DOCUMENT_EXTENSIONS,
    OPEN_EXTENSIONS,
    TEXT_EXTENSIONS,
    FileOperationSettings,
)
from omega.files.locations import FileLocationResolver
from omega.files.manager import FileManager
from omega.files.opener import WindowsFileOpener
from omega.files.operations import FileOperationsService
from omega.files.paths import SafeFilePathResolver
from omega.files.reader import TextFileReader
from omega.files.results import (
    FileMetadata,
    FileSearchMatch,
    PathValidationOutcome,
    ResolvedLocation,
    TextReadResult,
    ValidatedFilePath,
)
from omega.files.search import FileSearchService
from omega.files.validator import FilePathValidator, WindowsFilenameValidator
from omega.files.writer import TextFileWriter

__all__ = [
    "BLOCKED_EXTENSIONS",
    "FileLocationResolver",
    "FileManager",
    "FileMetadata",
    "FileOperationSettings",
    "FileOperationsService",
    "FilePathValidator",
    "FileSearchMatch",
    "FileSearchService",
    "LOGICAL_LOCATIONS",
    "OPEN_DOCUMENT_EXTENSIONS",
    "OPEN_EXTENSIONS",
    "PathValidationOutcome",
    "ResolvedLocation",
    "SafeFilePathResolver",
    "TEXT_EXTENSIONS",
    "TextFileReader",
    "TextFileWriter",
    "TextReadResult",
    "ValidatedFilePath",
    "WindowsFilenameValidator",
    "WindowsFileOpener",
]
