"""Coordinating facade for validated, structured Phase 5 file operations."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from time import monotonic
from uuid import UUID

from omega.core.exceptions import (
    FileConflictError,
    FileLocationError,
    FileManagementError,
    FileOpenError,
    FileOperationError,
    FilePathValidationError,
    FileReadError,
    FileSearchError,
    FileWriteError,
)
from omega.files.definitions import FileOperationSettings
from omega.files.locations import FileLocationResolver
from omega.files.opener import WindowsFileOpener
from omega.files.operations import FileOperationsService
from omega.files.paths import SafeFilePathResolver
from omega.files.reader import TextFileReader
from omega.files.results import FileSnapshot, ValidatedFilePath
from omega.files.search import FileSearchService
from omega.files.validator import WindowsFilenameValidator
from omega.files.writer import TextFileWriter
from omega.models import ActionResult, ErrorCategory, OmegaErrorDetails
from omega.models._serialization import JsonValue


@dataclass(frozen=True)
class _PendingOverwrite:
    target: ValidatedFilePath
    content: str
    snapshot: FileSnapshot
    expires_at: float


class FileManager:
    """Expose structured file operations over injected, separately testable services."""

    def __init__(
        self,
        location_resolver: FileLocationResolver,
        path_resolver: SafeFilePathResolver,
        reader: TextFileReader,
        writer: TextFileWriter,
        operations: FileOperationsService,
        search: FileSearchService,
        opener: WindowsFileOpener,
        *,
        settings: FileOperationSettings,
        monotonic_clock: Callable[[], float] = monotonic,
        logger: logging.Logger | None = None,
    ) -> None:
        self.location_resolver = location_resolver
        self.path_resolver = path_resolver
        self.reader = reader
        self.writer = writer
        self.operations = operations
        self.search = search
        self.opener = opener
        self.settings = settings
        self._clock = monotonic_clock
        self._logger = logger or logging.getLogger("omega.files.manager")
        self._pending_overwrites: dict[str, _PendingOverwrite] = {}

    def create_file(
        self,
        file_name: str,
        location: str | None,
        action_id: UUID,
        command_id: UUID | None = None,
        *,
        requested_extension: str | None = None,
    ) -> ActionResult:
        """Create one empty supported text/data file without overwriting."""
        try:
            selected = self._location(location)
            safe_name = self._normalize_text_path(
                file_name, requested_extension, default_extension=".txt"
            )
            target = self.path_resolver.resolve(selected, safe_name)
            self.writer.create(target)
            self._logger.info(
                "File created: location=%s relative=%s",
                target.location.logical_name,
                target.relative_path.as_posix(),
            )
            return self._success(
                action_id,
                "File created and verified.",
                f"{target.path.name} was created successfully on your "
                f"{target.location.display_name}.",
                self._target_data(target),
            )
        except FileConflictError:
            return self._failure(
                action_id,
                command_id,
                "FILE_ALREADY_EXISTS",
                ErrorCategory.ALREADY_EXISTS,
                "The destination file already exists.",
                f"{Path(file_name).name} already exists. I did not overwrite it.",
                True,
            )
        except FileManagementError as error:
            return self._managed_failure(action_id, command_id, error)

    def file_exists(
        self,
        file_name: str,
        location: str | None,
        action_id: UUID,
        command_id: UUID | None = None,
    ) -> ActionResult:
        """Check regular-file existence without accessing file contents."""
        try:
            target = self._resolve(location, file_name)
            exists = self.operations.exists(target)
            message = (
                f"{target.path.name} exists in {target.location.display_name}."
                if exists
                else (
                    f"{target.path.name} does not exist in "
                    f"{target.location.display_name}."
                )
            )
            return self._success(
                action_id,
                "File existence checked.",
                message,
                {**self._target_data(target), "exists": exists},
            )
        except FileManagementError as error:
            return self._managed_failure(action_id, command_id, error)

    def get_file_information(
        self,
        file_name: str,
        location: str | None,
        action_id: UUID,
        command_id: UUID | None = None,
    ) -> ActionResult:
        """Return bounded basic metadata without private absolute paths."""
        try:
            target = self._resolve(location, file_name)
            metadata = self.operations.metadata(target)
            user_message = (
                f"{metadata.name}: {metadata.size_bytes} bytes, "
                f"modified {metadata.modified_at.isoformat()}, "
                f"location {target.location.display_name}/{metadata.relative_path}."
            )
            return self._success(
                action_id,
                "File metadata inspected.",
                user_message,
                {
                    "name": metadata.name,
                    "logical_location": metadata.logical_location,
                    "relative_path": metadata.relative_path,
                    "size_bytes": metadata.size_bytes,
                    "created_at": metadata.created_at.isoformat(),
                    "modified_at": metadata.modified_at.isoformat(),
                    "extension": metadata.extension,
                    "read_only": metadata.read_only,
                },
            )
        except FileManagementError as error:
            return self._managed_failure(action_id, command_id, error)

    def read_text_file(
        self,
        file_name: str,
        location: str | None,
        action_id: UUID,
        command_id: UUID | None = None,
    ) -> ActionResult:
        """Read and sanitize one bounded UTF-8 file without logging contents."""
        try:
            target = self._resolve(location, file_name)
            read = self.reader.read(target)
            displayed = read.content
            if read.truncated:
                displayed += "\n[Output truncated by Omega's safety limit.]"
            self._logger.info(
                "File read succeeded: location=%s relative=%s size=%d",
                target.location.logical_name,
                target.relative_path.as_posix(),
                read.size_bytes,
            )
            return self._success(
                action_id,
                "Bounded text file read succeeded.",
                displayed or "The file is empty.",
                {
                    **self._target_data(target),
                    "content": read.content,
                    "truncated": read.truncated,
                    "size_bytes": read.size_bytes,
                },
            )
        except FileManagementError as error:
            return self._managed_failure(action_id, command_id, error)

    def write_text_file(
        self,
        file_name: str,
        location: str | None,
        content: str,
        action_id: UUID,
        command_id: UUID | None = None,
    ) -> ActionResult:
        """Write empty files immediately or request exact overwrite confirmation."""
        try:
            target = self._resolve_text(location, file_name)
            snapshot = self.writer.snapshot(target.path)
            if snapshot.size_bytes == 0:
                self.writer.replace(target, content, snapshot)
                return self._success(
                    action_id,
                    "Text file updated and verified.",
                    f"{target.path.name} was updated successfully.",
                    self._target_data(target),
                )
            key = self._pending_key(target)
            self._pending_overwrites[key] = _PendingOverwrite(
                target,
                content,
                snapshot,
                self._clock() + self.settings.confirmation_timeout_seconds,
            )
            self._logger.info(
                "File overwrite confirmation created: location=%s relative=%s",
                target.location.logical_name,
                target.relative_path.as_posix(),
            )
            return self._failure(
                action_id,
                command_id,
                "FILE_OVERWRITE_CONFIRMATION_REQUIRED",
                ErrorCategory.PERMISSION,
                "Replacing existing text requires exact confirmation.",
                f"This will replace the existing contents of {target.path.name}.\n"
                f'Type "confirm overwrite {target.path.name}" to continue.',
                True,
            )
        except FileManagementError as error:
            return self._managed_failure(action_id, command_id, error)

    def confirm_overwrite(
        self,
        file_name: str,
        location: str | None,
        action_id: UUID,
        command_id: UUID | None = None,
    ) -> ActionResult:
        """Consume one matching unexpired confirmation after target revalidation."""
        try:
            target = self._resolve_text(location, file_name)
            pending = self._pending_overwrites.pop(self._pending_key(target), None)
            if pending is None:
                raise FileConflictError(
                    "No matching overwrite confirmation is pending."
                )
            if self._clock() > pending.expires_at:
                self._logger.info("File overwrite confirmation expired.")
                return self._failure(
                    action_id,
                    command_id,
                    "FILE_OVERWRITE_CONFIRMATION_EXPIRED",
                    ErrorCategory.TIMEOUT,
                    "The overwrite confirmation expired.",
                    "That overwrite confirmation expired. "
                    "Please request the write again.",
                    True,
                )
            if target.path.resolve() != pending.target.path.resolve():
                raise FileConflictError("The confirmation does not match that file.")
            self.writer.replace(target, pending.content, pending.snapshot)
            return self._success(
                action_id,
                "Confirmed text replacement completed.",
                f"{target.path.name} was updated successfully.",
                self._target_data(target),
            )
        except FileManagementError as error:
            return self._managed_failure(action_id, command_id, error)

    def cancel_overwrite(
        self,
        file_name: str,
        location: str | None,
        action_id: UUID,
        command_id: UUID | None = None,
    ) -> ActionResult:
        """Cancel only the pending overwrite bound to the exact target."""
        try:
            target = self._resolve_text(location, file_name)
            pending = self._pending_overwrites.pop(self._pending_key(target), None)
            if pending is None:
                raise FileConflictError(
                    "No matching overwrite confirmation is pending."
                )
            return self._success(
                action_id,
                "Pending overwrite cancelled.",
                f"The overwrite of {target.path.name} was cancelled.",
                self._target_data(target),
            )
        except FileManagementError as error:
            return self._managed_failure(action_id, command_id, error)

    def append_text_file(
        self,
        file_name: str,
        location: str | None,
        content: str,
        action_id: UUID,
        command_id: UUID | None = None,
    ) -> ActionResult:
        """Append exactly supplied text to one validated existing text file."""
        try:
            target = self._resolve_text(location, file_name)
            self.writer.append(target, content)
            return self._success(
                action_id,
                "Text appended and verified.",
                f"The text was appended to {target.path.name} successfully.",
                self._target_data(target),
            )
        except FileManagementError as error:
            return self._managed_failure(action_id, command_id, error)

    def rename_file(
        self,
        source_name: str,
        new_name: str,
        location: str | None,
        action_id: UUID,
        command_id: UUID | None = None,
    ) -> ActionResult:
        """Rename one file in place without replacing another file."""
        try:
            source = self._resolve(location, source_name)
            safe_new_name = WindowsFilenameValidator.normalize_text_filename(new_name)
            destination = self.path_resolver.resolve(
                source.location.logical_name,
                str(source.relative_path.with_name(safe_new_name)),
            )
            self.operations.rename(source, destination)
            return self._success(
                action_id,
                "File renamed and verified.",
                f"{source.path.name} was renamed to {destination.path.name}.",
                self._target_data(destination),
            )
        except FileManagementError as error:
            return self._managed_failure(action_id, command_id, error)

    def copy_file(
        self,
        source_name: str,
        source_location: str | None,
        destination_location: str,
        action_id: UUID,
        command_id: UUID | None = None,
    ) -> ActionResult:
        """Copy one validated regular file to an approved root without overwrite."""
        return self._transfer(
            "copy",
            source_name,
            source_location,
            destination_location,
            action_id,
            command_id,
        )

    def move_file(
        self,
        source_name: str,
        source_location: str | None,
        destination_location: str,
        action_id: UUID,
        command_id: UUID | None = None,
    ) -> ActionResult:
        """Move one validated regular file to an approved root without overwrite."""
        return self._transfer(
            "move",
            source_name,
            source_location,
            destination_location,
            action_id,
            command_id,
        )

    def open_file(
        self,
        file_name: str,
        location: str | None,
        action_id: UUID,
        command_id: UUID | None = None,
    ) -> ActionResult:
        """Open a validated safe document using its registered default application."""
        try:
            WindowsFilenameValidator.validate_open_filename(Path(file_name).name)
            target = self._resolve(location, file_name)
            self.opener.open(target)
            return self._success(
                action_id,
                "Validated document open request accepted.",
                f"Opening {target.path.name}.",
                self._target_data(target),
            )
        except FileManagementError as error:
            return self._managed_failure(action_id, command_id, error)

    def search_files(
        self,
        query: str,
        location: str | None,
        action_id: UUID,
        command_id: UUID | None = None,
        *,
        extension: str | None = None,
    ) -> ActionResult:
        """Run one bounded exact-name or extension search in an approved root."""
        try:
            resolved = self.location_resolver.resolve(self._location(location))
            matches, truncated = self.search.search(
                resolved,
                filename=None if extension else query,
                extension=extension,
            )
            self._logger.info(
                "File search completed: location=%s results=%d truncated=%s",
                resolved.logical_name,
                len(matches),
                truncated,
            )
            if not matches:
                user_message = f"I did not find {query} in {resolved.display_name}."
            else:
                user_message = "\n".join(match.relative_path for match in matches)
                if truncated:
                    user_message += (
                        "\nI found more results than I can safely display. "
                        f"Showing the first {self.settings.search_max_results}."
                    )
            return self._success(
                action_id,
                "Bounded filename search completed.",
                user_message,
                {
                    "logical_location": resolved.logical_name,
                    "matches": [
                        {
                            "name": match.name,
                            "logical_location": match.logical_location,
                            "relative_path": match.relative_path,
                        }
                        for match in matches
                    ],
                    "truncated": truncated,
                },
            )
        except FileManagementError as error:
            return self._managed_failure(action_id, command_id, error)

    def clear_pending_confirmations(self) -> None:
        """Drop in-memory text without logging it on timeout or shutdown."""
        self._pending_overwrites.clear()

    def _transfer(
        self,
        operation: str,
        source_name: str,
        source_location: str | None,
        destination_location: str,
        action_id: UUID,
        command_id: UUID | None,
    ) -> ActionResult:
        try:
            source = self._resolve(source_location, source_name)
            destination = self.path_resolver.resolve(
                destination_location, source.path.name
            )
            if operation == "copy":
                self.operations.copy(source, destination)
            else:
                self.operations.move(source, destination)
            past_tense = "copied" if operation == "copy" else "moved"
            return self._success(
                action_id,
                f"File {operation} completed and verified.",
                f"{source.path.name} was {past_tense} to "
                f"{destination.location.display_name}.",
                self._target_data(destination),
            )
        except FileManagementError as error:
            return self._managed_failure(action_id, command_id, error)

    def _location(self, location: str | None) -> str:
        return location or self.settings.default_location

    def _resolve(self, location: str | None, relative_path: str) -> ValidatedFilePath:
        return self.path_resolver.resolve(self._location(location), relative_path)

    def _resolve_text(
        self, location: str | None, relative_path: str
    ) -> ValidatedFilePath:
        safe = self._normalize_text_path(relative_path)
        return self._resolve(location, safe)

    @staticmethod
    def _normalize_text_path(
        relative_path: str,
        requested_extension: str | None = None,
        *,
        default_extension: str | None = None,
    ) -> str:
        parsed = PureWindowsPath(relative_path)
        if not parsed.parts:
            raise FilePathValidationError("A file name is required.")
        name = WindowsFilenameValidator.normalize_text_filename(
            parsed.name,
            requested_extension,
            default_extension=default_extension,
        )
        return str(PureWindowsPath(*parsed.parts[:-1], name))

    @staticmethod
    def _pending_key(target: ValidatedFilePath) -> str:
        return (
            f"{target.location.logical_name}:"
            f"{target.relative_path.as_posix().casefold()}"
        )

    @staticmethod
    def _target_data(target: ValidatedFilePath) -> dict[str, JsonValue]:
        return {
            "name": target.path.name,
            "logical_location": target.location.logical_name,
            "relative_path": target.relative_path.as_posix(),
        }

    @staticmethod
    def _success(
        action_id: UUID, message: str, user_message: str, data: JsonValue
    ) -> ActionResult:
        return ActionResult.success_result(action_id, message, user_message, data=data)

    def _managed_failure(
        self,
        action_id: UUID,
        command_id: UUID | None,
        error: FileManagementError,
    ) -> ActionResult:
        if isinstance(error, FileConflictError):
            code = "FILE_CONFLICT"
            category = ErrorCategory.ALREADY_EXISTS
        elif isinstance(error, (FilePathValidationError, FileLocationError)):
            code = "FILE_PATH_REJECTED"
            category = ErrorCategory.SAFETY
        elif isinstance(error, FileReadError):
            code = "FILE_READ_FAILED"
            category = ErrorCategory.EXECUTION
        elif isinstance(error, FileWriteError):
            code = "FILE_WRITE_FAILED"
            category = ErrorCategory.EXECUTION
        elif isinstance(error, FileSearchError):
            code = "FILE_SEARCH_FAILED"
            category = ErrorCategory.EXECUTION
        elif isinstance(error, FileOpenError):
            code = "FILE_OPEN_FAILED"
            category = ErrorCategory.EXECUTION
        elif isinstance(error, FileOperationError):
            code = "FILE_OPERATION_FAILED"
            category = ErrorCategory.EXECUTION
        else:
            code = "FILE_MANAGEMENT_FAILED"
            category = ErrorCategory.INTERNAL
        self._logger.warning("File operation failed: code=%s", code)
        return self._failure(
            action_id,
            command_id,
            code,
            category,
            str(error),
            str(error),
            True,
        )

    @staticmethod
    def _failure(
        action_id: UUID,
        command_id: UUID | None,
        code: str,
        category: ErrorCategory,
        message: str,
        user_message: str,
        recoverable: bool,
    ) -> ActionResult:
        error = OmegaErrorDetails(
            code=code,
            category=category,
            message=message,
            user_message=user_message,
            recoverable=recoverable,
            action_id=action_id,
            command_id=command_id,
        )
        return ActionResult.failure_result(action_id, message, user_message, error)
