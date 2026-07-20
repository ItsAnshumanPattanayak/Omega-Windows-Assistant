"""Coordinating facade for validated, structured file operations."""

from __future__ import annotations

import logging
from pathlib import Path, PureWindowsPath
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
    RecoveryRecordError,
)
from omega.files.definitions import FileOperationSettings
from omega.files.locations import FileLocationResolver
from omega.files.opener import WindowsFileOpener
from omega.files.operations import FileOperationsService
from omega.files.paths import SafeFilePathResolver
from omega.files.reader import TextFileReader
from omega.files.results import ValidatedFilePath
from omega.files.search import FileSearchService
from omega.files.validator import WindowsFilenameValidator
from omega.files.writer import TextFileWriter
from omega.models import ActionResult, ErrorCategory, OmegaErrorDetails
from omega.models._serialization import JsonValue
from omega.recovery import (
    RecoveryRegistry,
    RecoveryResourceType,
    WindowsRecycleBinService,
)


class FileManager:
    """Expose structured file operations over injected, testable services."""

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
        recycle_bin_service: WindowsRecycleBinService | None = None,
        recovery_registry: RecoveryRegistry | None = None,
        monotonic_clock: object | None = None,
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
        self.recycle_bin_service = recycle_bin_service
        self.recovery_registry = recovery_registry
        del monotonic_clock
        self._logger = logger or logging.getLogger("omega.files.manager")

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
                file_name,
                requested_extension,
                default_extension=".txt",
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
                {
                    **self._target_data(target),
                    "exists": exists,
                },
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
        """Write empty files; reject direct replacement outside the gateway."""

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

            return self._failure(
                action_id,
                command_id,
                "FILE_OVERWRITE_CONFIRMATION_REQUIRED",
                ErrorCategory.PERMISSION,
                "Replacing existing text requires exact confirmation.",
                "A central safety confirmation is required before replacing "
                f"{target.path.name}.",
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
        """Reject legacy confirmation; only ConfirmationManager can approve."""

        return self._legacy_confirmation_failure(
            action_id,
            command_id,
        )

    def replace_text_file(
        self,
        file_name: str,
        location: str | None,
        content: str,
        action_id: UUID,
        command_id: UUID | None = None,
    ) -> ActionResult:
        """Replace text only after the central gateway grants confirmation."""

        try:
            target = self._resolve_text(location, file_name)
            snapshot = self.writer.snapshot(target.path)
            self.writer.replace(target, content, snapshot)
            return self._success(
                action_id,
                "Existing text was replaced and verified.",
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
        """Reject legacy cancellation because no confirmation is stored."""

        return self._legacy_confirmation_failure(
            action_id,
            command_id,
        )

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
        """Copy one validated regular file without overwrite."""

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
        """Move one validated regular file without overwrite."""

        return self._transfer(
            "move",
            source_name,
            source_location,
            destination_location,
            action_id,
            command_id,
        )

    def recycle_file(
        self,
        file_name: str,
        location: str | None,
        action_id: UUID,
        command_id: UUID,
        session_id: UUID,
    ) -> ActionResult:
        """Move one validated file to the Recycle Bin and register undo."""

        if self.recycle_bin_service is None or self.recovery_registry is None:
            return self._failure(
                action_id,
                command_id,
                "FILE_RECOVERY_NOT_CONFIGURED",
                ErrorCategory.INTERNAL,
                "File recovery services are not configured.",
                "Omega could not prepare a safe Recycle Bin operation.",
                True,
            )

        try:
            target = self._resolve(location, file_name)
            recycle_result = self.recycle_bin_service.recycle(
                target.path,
                logical_location=target.location.logical_name,
                relative_path=target.relative_path.as_posix(),
                command_id=command_id,
                action_id=action_id,
                session_id=session_id,
            )

            if not recycle_result.success:
                return self._failure(
                    action_id,
                    command_id,
                    recycle_result.code.upper(),
                    ErrorCategory.EXECUTION,
                    recycle_result.message,
                    recycle_result.message,
                    True,
                )

            if recycle_result.record is None:
                return self._failure(
                    action_id,
                    command_id,
                    "FILE_RECOVERY_RECORD_MISSING",
                    ErrorCategory.INTERNAL,
                    "The Recycle Bin operation returned no recovery record.",
                    "The file was processed, but Omega could not register undo.",
                    True,
                )

            if recycle_result.record.resource_type is not RecoveryResourceType.FILE:
                return self._failure(
                    action_id,
                    command_id,
                    "FILE_RECOVERY_TYPE_MISMATCH",
                    ErrorCategory.INTERNAL,
                    "The recovery record did not describe a file.",
                    "Omega rejected an invalid file recovery result.",
                    True,
                )

            registered = self.recovery_registry.register(
                recycle_result.record,
                registered_at=recycle_result.completed_at,
            )

            self._logger.info(
                "File recycled: location=%s relative=%s record=%s",
                target.location.logical_name,
                target.relative_path.as_posix(),
                registered.record_id,
            )

            return self._success(
                action_id,
                "File moved to the Recycle Bin and registered for undo.",
                f"{target.path.name} was moved to the Recycle Bin. "
                "You can undo this action for a limited time.",
                {
                    **self._target_data(target),
                    "recovery_record_id": str(registered.record_id),
                    "recovery_status": registered.status.value,
                    "can_undo": registered.can_restore,
                    "expires_at": (
                        registered.expires_at.isoformat()
                        if registered.expires_at is not None
                        else None
                    ),
                },
            )
        except FileManagementError as error:
            return self._managed_failure(
                action_id,
                command_id,
                error,
            )
        except RecoveryRecordError as error:
            self._logger.warning(
                "File recovery registration failed: %s",
                error,
            )
            return self._failure(
                action_id,
                command_id,
                "FILE_RECOVERY_REGISTRATION_FAILED",
                ErrorCategory.INTERNAL,
                str(error),
                "The file was processed, but Omega could not register undo.",
                True,
            )

    def open_file(
        self,
        file_name: str,
        location: str | None,
        action_id: UUID,
        command_id: UUID | None = None,
    ) -> ActionResult:
        """Open a validated safe document using its default application."""

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
        """Run one bounded exact-name or extension search."""

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
        """Compatibility no-op; confirmation lives in the gateway."""

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
            source = self._resolve(
                source_location,
                source_name,
            )
            destination = self.path_resolver.resolve(
                destination_location,
                source.path.name,
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

    def _resolve(
        self,
        location: str | None,
        relative_path: str,
    ) -> ValidatedFilePath:
        return self.path_resolver.resolve(
            self._location(location),
            relative_path,
        )

    def _resolve_text(
        self,
        location: str | None,
        relative_path: str,
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

        return str(
            PureWindowsPath(
                *parsed.parts[:-1],
                name,
            )
        )

    @staticmethod
    def _target_data(
        target: ValidatedFilePath,
    ) -> dict[str, JsonValue]:
        return {
            "name": target.path.name,
            "logical_location": target.location.logical_name,
            "relative_path": target.relative_path.as_posix(),
        }

    @staticmethod
    def _success(
        action_id: UUID,
        message: str,
        user_message: str,
        data: JsonValue,
    ) -> ActionResult:
        return ActionResult.success_result(
            action_id,
            message,
            user_message,
            data=data,
        )

    def _managed_failure(
        self,
        action_id: UUID,
        command_id: UUID | None,
        error: FileManagementError,
    ) -> ActionResult:
        if isinstance(error, FileConflictError):
            code = "FILE_CONFLICT"
            category = ErrorCategory.ALREADY_EXISTS
        elif isinstance(
            error,
            (
                FilePathValidationError,
                FileLocationError,
            ),
        ):
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

        self._logger.warning(
            "File operation failed: code=%s",
            code,
        )

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

        return ActionResult.failure_result(
            action_id,
            message,
            user_message,
            error,
        )

    @classmethod
    def _legacy_confirmation_failure(
        cls,
        action_id: UUID,
        command_id: UUID | None,
    ) -> ActionResult:
        return cls._failure(
            action_id,
            command_id,
            "CENTRAL_GATEWAY_REQUIRED",
            ErrorCategory.SAFETY,
            "Direct file confirmation is disabled.",
            "A central safety confirmation is required for that file operation.",
            True,
        )
