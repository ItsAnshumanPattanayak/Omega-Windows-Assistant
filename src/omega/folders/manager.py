"""Coordinating facade for validated and structured folder operations."""

from __future__ import annotations

import logging
from pathlib import Path, PureWindowsPath
from uuid import UUID

from omega.core.exceptions import (
    FileLocationError,
    FolderConflictError,
    FolderCrossVolumeMoveError,
    FolderManagementError,
    FolderOpenError,
    FolderResourceLimitError,
    FolderSearchError,
    FolderValidationError,
    RecoveryRecordError,
)
from omega.files.locations import FileLocationResolver
from omega.files.results import ResolvedLocation
from omega.folders.creator import FolderCreator
from omega.folders.definitions import FolderOperationSettings
from omega.folders.inspector import FolderInspector
from omega.folders.opener import WindowsFolderOpener
from omega.folders.operations import FolderOperations
from omega.folders.results import ValidatedFolderPath
from omega.folders.search import FolderSearch
from omega.folders.validator import (
    FolderPathValidator,
    WindowsFolderNameValidator,
)
from omega.models import ActionResult, ErrorCategory, OmegaErrorDetails
from omega.models._serialization import JsonValue
from omega.recovery import (
    RecoveryRegistry,
    RecoveryResourceType,
    WindowsRecycleBinService,
)


class FolderManager:
    """Expose folder capabilities over injected, testable services."""

    def __init__(
        self,
        location_resolver: FileLocationResolver,
        validator: FolderPathValidator,
        creator: FolderCreator,
        inspector: FolderInspector,
        operations: FolderOperations,
        search: FolderSearch,
        opener: WindowsFolderOpener,
        *,
        settings: FolderOperationSettings,
        recycle_bin_service: WindowsRecycleBinService | None = None,
        recovery_registry: RecoveryRegistry | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.location_resolver = location_resolver
        self.validator = validator
        self.creator = creator
        self.inspector = inspector
        self.operations = operations
        self.search = search
        self.opener = opener
        self.settings = settings
        self.recycle_bin_service = recycle_bin_service
        self.recovery_registry = recovery_registry
        self._logger = logger or logging.getLogger("omega.folders.manager")

    def create_folder(
        self,
        folder_name: str,
        location: str | None,
        action_id: UUID,
        command_id: UUID | None = None,
        *,
        parent_path: str | None = None,
    ) -> ActionResult:
        try:
            safe_name = WindowsFolderNameValidator.validate_component(folder_name)
            relative = (
                str(
                    PureWindowsPath(
                        parent_path,
                        safe_name,
                    )
                )
                if parent_path
                else safe_name
            )
            target = self._resolve(location, relative)
            self.creator.create(target)
            self._logger.info(
                "Folder created: location=%s relative=%s",
                target.location.logical_name,
                target.relative_path.as_posix(),
            )
            return self._success(
                action_id,
                "Folder created and verified.",
                f"The {safe_name} folder was created successfully on your "
                f"{target.location.display_name}.",
                self._target_data(target),
            )
        except FolderConflictError as error:
            message = (
                f"The {Path(folder_name).name} folder already exists on your "
                f"{self._display(location)}."
                if "folder already" in str(error).casefold()
                else (
                    f"I could not create the {Path(folder_name).name} folder "
                    "because a file with that name already exists."
                )
            )
            return self._failure(
                action_id,
                command_id,
                "FOLDER_CONFLICT",
                ErrorCategory.ALREADY_EXISTS,
                str(error),
                message,
            )
        except FolderManagementError as error:
            return self._managed_failure(
                action_id,
                command_id,
                error,
            )

    def folder_exists(
        self,
        folder_path: str | None,
        location: str | None,
        action_id: UUID,
        command_id: UUID | None = None,
    ) -> ActionResult:
        try:
            target = self._resolve(
                location,
                folder_path,
                allow_root=True,
            )
            exists = self.inspector.exists(target)
            name = self._name(target)
            phrase = "exists" if exists else "does not exist"
            return self._success(
                action_id,
                "Folder existence checked.",
                f"The {name} folder {phrase} on your "
                f"{target.location.display_name}.",
                {
                    **self._target_data(target),
                    "exists": exists,
                },
            )
        except FolderManagementError as error:
            return self._managed_failure(
                action_id,
                command_id,
                error,
            )

    def list_folder(
        self,
        folder_path: str | None,
        location: str | None,
        action_id: UUID,
        command_id: UUID | None = None,
    ) -> ActionResult:
        try:
            target = self._resolve(
                location,
                folder_path,
                allow_root=True,
                require_existing=True,
            )
            listing = self.inspector.list_folder(
                target,
                self.settings.maximum_listing_items,
            )
            lines = [
                f"{self._name(target)} contains:",
                "Folders:",
            ]
            lines.extend(f"- {name}" for name in listing.folders)

            if not listing.folders:
                lines.append("- None")

            lines.append("Files:")
            lines.extend(f"- {name}" for name in listing.files)

            if not listing.files:
                lines.append("- None")

            if listing.truncated:
                lines.append(
                    "The folder contains more items than Omega can display "
                    "safely. "
                    f"Showing the first "
                    f"{self.settings.maximum_listing_items}."
                )

            if listing.skipped_entries:
                lines.append(
                    "Some protected, linked, or inaccessible entries were " "omitted."
                )

            self._logger.info(
                "Folder listed: location=%s items=%d truncated=%s",
                target.location.logical_name,
                len(listing.folders) + len(listing.files),
                listing.truncated,
            )
            return self._success(
                action_id,
                "Bounded folder listing completed.",
                "\n".join(lines),
                {
                    **self._target_data(target),
                    "folders": list(listing.folders),
                    "files": list(listing.files),
                    "truncated": listing.truncated,
                    "skipped_entries": listing.skipped_entries,
                },
            )
        except FolderManagementError as error:
            return self._managed_failure(
                action_id,
                command_id,
                error,
            )

    def get_folder_information(
        self,
        folder_path: str | None,
        location: str | None,
        action_id: UUID,
        command_id: UUID | None = None,
        *,
        recursive: bool = False,
    ) -> ActionResult:
        try:
            target = self._resolve(
                location,
                folder_path,
                allow_root=True,
                require_existing=True,
            )
            metadata = self.inspector.metadata(
                target,
                recursive=recursive,
                maximum_depth=self.settings.maximum_scan_depth,
                maximum_items=self.settings.maximum_scan_items,
                maximum_bytes=self.settings.maximum_scan_bytes,
            )
            message = (
                f"{metadata.name} contains "
                f"{metadata.immediate_folder_count} folders and "
                f"{metadata.immediate_file_count} files."
            )

            if recursive:
                qualifier = "at least " if metadata.truncated else ""
                message += (
                    " Recursively it contains "
                    f"{qualifier}{metadata.recursive_folder_count} folders, "
                    f"{qualifier}{metadata.recursive_file_count} files, and "
                    f"uses {qualifier}{metadata.total_bytes} bytes."
                )

                if metadata.truncated:
                    message += " The scan stopped at a configured safety limit."

            data: dict[str, JsonValue] = {
                "name": metadata.name,
                "logical_location": metadata.logical_location,
                "relative_path": metadata.relative_path,
                "immediate_file_count": metadata.immediate_file_count,
                "immediate_folder_count": metadata.immediate_folder_count,
                "created_at": metadata.created_at.isoformat(),
                "modified_at": metadata.modified_at.isoformat(),
                "read_only": metadata.read_only,
                "recursive_file_count": metadata.recursive_file_count,
                "recursive_folder_count": metadata.recursive_folder_count,
                "total_bytes": metadata.total_bytes,
                "maximum_depth": metadata.maximum_depth,
                "truncated": metadata.truncated,
            }

            return self._success(
                action_id,
                "Folder metadata inspected.",
                message,
                data,
            )
        except FolderManagementError as error:
            return self._managed_failure(
                action_id,
                command_id,
                error,
            )

    def open_folder(
        self,
        folder_path: str | None,
        location: str | None,
        action_id: UUID,
        command_id: UUID | None = None,
    ) -> ActionResult:
        try:
            target = self._resolve(
                location,
                folder_path,
                allow_root=True,
                require_existing=True,
            )
            self.opener.open(target)
            return self._success(
                action_id,
                "Validated folder open request accepted.",
                f"Opening the {self._name(target)} folder.",
                self._target_data(target),
            )
        except FolderManagementError as error:
            return self._managed_failure(
                action_id,
                command_id,
                error,
            )

    def rename_folder(
        self,
        source_path: str,
        new_name: str,
        location: str | None,
        action_id: UUID,
        command_id: UUID | None = None,
    ) -> ActionResult:
        try:
            source = self._resolve(
                location,
                source_path,
                require_existing=True,
            )
            safe_name = WindowsFolderNameValidator.validate_component(new_name)
            destination = self._resolve(
                source.location.logical_name,
                str(source.relative_path.with_name(safe_name)),
            )
            self.operations.rename(
                source,
                destination,
            )
            return self._success(
                action_id,
                "Folder renamed and verified.",
                f"The {source.path.name} folder was renamed to {safe_name}.",
                self._target_data(destination),
            )
        except FolderManagementError as error:
            return self._managed_failure(
                action_id,
                command_id,
                error,
            )

    def copy_folder(
        self,
        source_path: str,
        source_location: str | None,
        destination_location: str,
        action_id: UUID,
        command_id: UUID | None = None,
    ) -> ActionResult:
        return self._transfer(
            "copy",
            source_path,
            source_location,
            destination_location,
            action_id,
            command_id,
        )

    def move_folder(
        self,
        source_path: str,
        source_location: str | None,
        destination_location: str,
        action_id: UUID,
        command_id: UUID | None = None,
    ) -> ActionResult:
        return self._transfer(
            "move",
            source_path,
            source_location,
            destination_location,
            action_id,
            command_id,
        )

    def recycle_folder(
        self,
        folder_path: str,
        location: str | None,
        action_id: UUID,
        command_id: UUID,
        session_id: UUID,
    ) -> ActionResult:
        """Move one validated folder to the Recycle Bin and register undo."""

        if self.recycle_bin_service is None or self.recovery_registry is None:
            return self._failure(
                action_id,
                command_id,
                "FOLDER_RECOVERY_NOT_CONFIGURED",
                ErrorCategory.INTERNAL,
                "Folder recovery services are not configured.",
                "Omega could not prepare a safe Recycle Bin operation.",
            )

        try:
            target = self._resolve(
                location,
                folder_path,
                require_existing=True,
            )
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
                )

            if recycle_result.record is None:
                return self._failure(
                    action_id,
                    command_id,
                    "FOLDER_RECOVERY_RECORD_MISSING",
                    ErrorCategory.INTERNAL,
                    "The Recycle Bin operation returned no recovery record.",
                    "The folder was processed, but Omega could not register undo.",
                )

            if recycle_result.record.resource_type is not RecoveryResourceType.FOLDER:
                return self._failure(
                    action_id,
                    command_id,
                    "FOLDER_RECOVERY_TYPE_MISMATCH",
                    ErrorCategory.INTERNAL,
                    "The recovery record did not describe a folder.",
                    "Omega rejected an invalid folder recovery result.",
                )

            registered = self.recovery_registry.register(
                recycle_result.record,
                registered_at=recycle_result.completed_at,
            )

            self._logger.info(
                "Folder recycled: location=%s relative=%s record=%s",
                target.location.logical_name,
                target.relative_path.as_posix(),
                registered.record_id,
            )

            return self._success(
                action_id,
                "Folder moved to the Recycle Bin and registered for undo.",
                f"The {target.path.name} folder was moved to the Recycle Bin. "
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
        except FolderManagementError as error:
            return self._managed_failure(
                action_id,
                command_id,
                error,
            )
        except RecoveryRecordError as error:
            self._logger.warning(
                "Folder recovery registration failed: %s",
                error,
            )
            return self._failure(
                action_id,
                command_id,
                "FOLDER_RECOVERY_REGISTRATION_FAILED",
                ErrorCategory.INTERNAL,
                str(error),
                "The folder was processed, but Omega could not register undo.",
            )

    def search_folders(
        self,
        folder_name: str,
        location: str | None,
        action_id: UUID,
        command_id: UUID | None = None,
    ) -> ActionResult:
        try:
            resolved = self._resolve_location(location)
            matches, truncated = self.search.search(
                resolved,
                folder_name,
                maximum_depth=self.settings.search_max_depth,
                maximum_results=self.settings.search_max_results,
            )

            if matches:
                message = "\n".join(match.relative_path for match in matches)

                if truncated:
                    message += (
                        "\nI found more folders than I can safely display. "
                        f"Showing the first "
                        f"{self.settings.search_max_results}."
                    )
            else:
                message = (
                    f"I did not find a folder named {folder_name} in "
                    f"{resolved.display_name}."
                )

            self._logger.info(
                "Folder search completed: location=%s results=%d truncated=%s",
                resolved.logical_name,
                len(matches),
                truncated,
            )
            return self._success(
                action_id,
                "Bounded folder search completed.",
                message,
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
        except FolderManagementError as error:
            return self._managed_failure(
                action_id,
                command_id,
                error,
            )

    def _transfer(
        self,
        operation: str,
        source_path: str,
        source_location: str | None,
        destination_location: str,
        action_id: UUID,
        command_id: UUID | None,
    ) -> ActionResult:
        try:
            source = self._resolve(
                source_location,
                source_path,
                require_existing=True,
            )
            destination = self._resolve(
                destination_location,
                source.path.name,
            )
            method = (
                self.operations.copy if operation == "copy" else self.operations.move
            )
            snapshot = method(
                source,
                destination,
                maximum_depth=self.settings.maximum_copy_depth,
                maximum_items=self.settings.maximum_copy_items,
                maximum_bytes=self.settings.maximum_copy_bytes,
            )
            past = "copied" if operation == "copy" else "moved"
            return self._success(
                action_id,
                f"Folder {operation} completed and verified.",
                f"The {source.path.name} folder was {past} to "
                f"{destination.location.display_name}.",
                {
                    **self._target_data(destination),
                    "file_count": snapshot.file_count,
                    "folder_count": snapshot.folder_count,
                    "total_bytes": snapshot.total_bytes,
                },
            )
        except FolderManagementError as error:
            return self._managed_failure(
                action_id,
                command_id,
                error,
            )

    def _location(
        self,
        location: str | None,
    ) -> str:
        return location or self.settings.default_location

    def _resolve(
        self,
        location: str | None,
        relative_path: str | None,
        *,
        allow_root: bool = False,
        require_existing: bool = False,
    ) -> ValidatedFolderPath:
        resolved = self._resolve_location(location)
        return self.validator.require_folder_path(
            resolved,
            relative_path,
            allow_root=allow_root,
            require_existing=require_existing,
        )

    def _display(
        self,
        location: str | None,
    ) -> str:
        return self._resolve_location(location).display_name

    def _resolve_location(
        self,
        location: str | None,
    ) -> ResolvedLocation:
        try:
            return self.location_resolver.resolve(self._location(location))
        except FileLocationError as error:
            raise FolderValidationError(str(error)) from error

    @staticmethod
    def _name(
        target: ValidatedFolderPath,
    ) -> str:
        return (
            target.location.display_name
            if target.relative_path == Path(".")
            else target.path.name
        )

    @staticmethod
    def _target_data(
        target: ValidatedFolderPath,
    ) -> dict[str, JsonValue]:
        relative = (
            "" if target.relative_path == Path(".") else target.relative_path.as_posix()
        )
        return {
            "name": target.path.name,
            "logical_location": target.location.logical_name,
            "relative_path": relative,
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
        error: FolderManagementError,
    ) -> ActionResult:
        if isinstance(error, FolderConflictError):
            code = "FOLDER_CONFLICT"
            category = ErrorCategory.ALREADY_EXISTS
        elif isinstance(error, FolderResourceLimitError):
            code = "FOLDER_RESOURCE_LIMIT"
            category = ErrorCategory.SAFETY
        elif isinstance(error, FolderCrossVolumeMoveError):
            code = "CROSS_VOLUME_MOVE_BLOCKED"
            category = ErrorCategory.SAFETY
        elif isinstance(error, FolderValidationError):
            code = "FOLDER_PATH_REJECTED"
            category = ErrorCategory.SAFETY
        elif isinstance(error, FolderSearchError):
            code = "FOLDER_SEARCH_FAILED"
            category = ErrorCategory.EXECUTION
        elif isinstance(error, FolderOpenError):
            code = "FOLDER_OPEN_FAILED"
            category = ErrorCategory.EXECUTION
        else:
            code = "FOLDER_OPERATION_FAILED"
            category = ErrorCategory.EXECUTION

        self._logger.warning(
            "Folder operation failed: code=%s",
            code,
        )

        return self._failure(
            action_id,
            command_id,
            code,
            category,
            str(error),
            str(error),
        )

    @staticmethod
    def _failure(
        action_id: UUID,
        command_id: UUID | None,
        code: str,
        category: ErrorCategory,
        message: str,
        user_message: str,
    ) -> ActionResult:
        error = OmegaErrorDetails(
            code=code,
            category=category,
            message=message,
            user_message=user_message,
            recoverable=True,
            action_id=action_id,
            command_id=command_id,
        )

        return ActionResult.failure_result(
            action_id,
            message,
            user_message,
            error,
        )
