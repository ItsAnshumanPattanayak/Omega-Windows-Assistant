"""Safe Windows Recycle Bin service with an injectable native backend."""

from __future__ import annotations

import ctypes
import hashlib
import os
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

from omega.models._serialization import JsonValue
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

_FILE_ATTRIBUTE_REPARSE_POINT = 0x0400

_FO_DELETE = 0x0003

_FOF_SILENT = 0x0004
_FOF_NOCONFIRMATION = 0x0010
_FOF_ALLOWUNDO = 0x0040
_FOF_NOERRORUI = 0x0400

_MAXIMUM_LEGACY_SHELL_PATH_LENGTH = 259


class WindowsShellRecycleBinBackend:
    """Move validated paths to the Windows Recycle Bin through Shell32."""

    def recycle(self, path: Path) -> RecycleBinBackendResult:
        """Recycle one path using the Windows Shell file-operation API."""

        if sys.platform != "win32":
            return RecycleBinBackendResult(
                success=False,
                code="unsupported_platform",
                message="The Windows Recycle Bin backend requires Windows.",
            )

        try:
            return self._execute_shell_operation(path)
        except (AttributeError, OSError, TypeError, ValueError) as error:
            return RecycleBinBackendResult(
                success=False,
                code="native_recycle_error",
                message="Windows could not complete the Recycle Bin operation.",
                native_error_code=self._extract_error_code(error),
            )

    @staticmethod
    def _execute_shell_operation(path: Path) -> RecycleBinBackendResult:
        class SHFileOperationStructure(ctypes.Structure):
            _fields_ = [
                ("hwnd", ctypes.c_void_p),
                ("wFunc", ctypes.c_uint),
                ("pFrom", ctypes.c_wchar_p),
                ("pTo", ctypes.c_wchar_p),
                ("fFlags", ctypes.c_ushort),
                ("fAnyOperationsAborted", ctypes.c_int),
                ("hNameMappings", ctypes.c_void_p),
                ("lpszProgressTitle", ctypes.c_wchar_p),
            ]

        shell32: Any = ctypes.WinDLL("shell32", use_last_error=True)
        shell_operation: Any = shell32.SHFileOperationW

        shell_operation.argtypes = [ctypes.POINTER(SHFileOperationStructure)]
        shell_operation.restype = ctypes.c_int

        source = f"{path}\0\0"

        operation = SHFileOperationStructure()
        operation.hwnd = None
        operation.wFunc = _FO_DELETE
        operation.pFrom = source
        operation.pTo = None
        operation.fFlags = (
            _FOF_ALLOWUNDO | _FOF_NOCONFIRMATION | _FOF_SILENT | _FOF_NOERRORUI
        )
        operation.fAnyOperationsAborted = 0
        operation.hNameMappings = None
        operation.lpszProgressTitle = None

        native_code = int(shell_operation(ctypes.byref(operation)))
        operation_aborted = bool(operation.fAnyOperationsAborted)

        if native_code != 0:
            return RecycleBinBackendResult(
                success=False,
                code="native_recycle_failed",
                message="Windows rejected the Recycle Bin operation.",
                native_error_code=native_code,
                operation_aborted=operation_aborted,
            )

        if operation_aborted:
            return RecycleBinBackendResult(
                success=False,
                code="recycle_operation_aborted",
                message="The Windows Recycle Bin operation was aborted.",
                native_error_code=native_code,
                operation_aborted=True,
            )

        return RecycleBinBackendResult(
            success=True,
            code="recycled",
            message="The item was moved to the Windows Recycle Bin.",
            native_error_code=native_code,
        )

    @staticmethod
    def _extract_error_code(error: BaseException) -> int | None:
        winerror = getattr(error, "winerror", None)

        if isinstance(winerror, int) and winerror >= 0:
            return winerror

        errno = getattr(error, "errno", None)

        if isinstance(errno, int) and errno >= 0:
            return errno

        return None


class WindowsRecycleBinService:
    """Validate and move files or folders to the Windows Recycle Bin."""

    def __init__(
        self,
        configuration: RecoveryConfiguration,
        backend: RecycleBinBackend | None = None,
        protected_path_checker: ProtectedPathChecker | None = None,
        platform_name: str | None = None,
    ) -> None:
        if not isinstance(configuration, RecoveryConfiguration):
            raise TypeError("configuration must be a RecoveryConfiguration.")

        self._configuration = configuration
        self._backend = backend or WindowsShellRecycleBinBackend()
        self._protected_path_checker = (
            protected_path_checker or self._path_is_not_protected
        )
        self._platform_name = platform_name or sys.platform

    def recycle(
        self,
        path: Path,
        *,
        logical_location: str,
        relative_path: str,
        command_id: UUID,
        action_id: UUID,
        session_id: UUID,
    ) -> RecoveryResult:
        """Move one validated file or folder to the Windows Recycle Bin."""

        validation_failure = self._validate_request(
            path=path,
            logical_location=logical_location,
            relative_path=relative_path,
        )

        if validation_failure is not None:
            return validation_failure

        try:
            normalized_path = path.resolve(strict=True)
            resource_type = self._resource_type(normalized_path)
            size_bytes = self._measure_size(normalized_path)
        except (OSError, RuntimeError) as error:
            return self._failure(
                code="recycle_inspection_failed",
                message="Omega could not inspect the requested item safely.",
                metadata={
                    "error_type": type(error).__name__,
                },
            )

        if size_bytes > self._configuration.maximum_recycle_size_bytes:
            return self._failure(
                code="recycle_size_limit_exceeded",
                message="The requested item exceeds the configured recycle limit.",
                metadata={
                    "resource_type": resource_type.value,
                    "size_bytes": size_bytes,
                    "maximum_size_bytes": (
                        self._configuration.maximum_recycle_size_bytes
                    ),
                },
            )

        try:
            backend_result = self._backend.recycle(normalized_path)
        except Exception as error:
            return self._failure(
                code="recycle_backend_error",
                message="The Recycle Bin backend failed safely.",
                metadata={
                    "error_type": type(error).__name__,
                },
            )

        if not backend_result.success:
            return self._failure(
                code=backend_result.code,
                message=backend_result.message,
                metadata=self._backend_metadata(backend_result),
            )

        record = self._create_completed_record(
            path=normalized_path,
            logical_location=logical_location,
            relative_path=relative_path,
            command_id=command_id,
            action_id=action_id,
            session_id=session_id,
            resource_type=resource_type,
            size_bytes=size_bytes,
            backend_result=backend_result,
        )

        return RecoveryResult(
            success=True,
            code="recycled",
            message=f"{resource_type.value.title()} moved to the Recycle Bin.",
            record=record,
            metadata={
                "resource_type": resource_type.value,
                "size_bytes": size_bytes,
            },
        )

    def _validate_request(
        self,
        *,
        path: Path,
        logical_location: str,
        relative_path: str,
    ) -> RecoveryResult | None:
        if not self._configuration.enabled:
            return self._failure(
                code="recovery_disabled",
                message="Recovery operations are disabled.",
            )

        if self._configuration.allow_permanent_deletion:
            return self._failure(
                code="unsafe_recovery_configuration",
                message="Permanent deletion cannot be enabled for this service.",
            )

        if self._platform_name != "win32":
            return self._failure(
                code="unsupported_platform",
                message="The Windows Recycle Bin service requires Windows.",
            )

        if not path.is_absolute():
            return self._failure(
                code="relative_recycle_path",
                message="The recycle target must be an absolute path.",
            )

        for context_name, context_value in (
            ("logical_location", logical_location),
            ("relative_path", relative_path),
        ):
            if not context_value.strip():
                return self._failure(
                    code="invalid_recycle_context",
                    message=f"{context_name} must be a non-empty string.",
                )

        if len(str(path)) > _MAXIMUM_LEGACY_SHELL_PATH_LENGTH:
            return self._failure(
                code="recycle_path_too_long",
                message="The path is too long for the Windows Shell operation.",
            )

        try:
            path_status = path.lstat()
        except FileNotFoundError:
            return self._failure(
                code="recycle_target_not_found",
                message="The requested item does not exist.",
            )
        except OSError as error:
            return self._failure(
                code="recycle_target_inaccessible",
                message="The requested item could not be inspected.",
                metadata={
                    "error_type": type(error).__name__,
                },
            )

        if self._is_reparse_point(path, path_status):
            return self._failure(
                code="reparse_point_rejected",
                message="Symlinks and filesystem reparse points cannot be recycled.",
            )

        if self._is_drive_root(path):
            return self._failure(
                code="drive_root_rejected",
                message="A filesystem drive root cannot be recycled.",
            )

        try:
            normalized_path = path.resolve(strict=True)
        except (OSError, RuntimeError):
            return self._failure(
                code="recycle_path_resolution_failed",
                message="The requested path could not be resolved safely.",
            )

        try:
            is_protected = self._protected_path_checker(normalized_path)
        except Exception as error:
            return self._failure(
                code="protected_path_check_failed",
                message="Omega could not evaluate the protected-path boundary.",
                metadata={
                    "error_type": type(error).__name__,
                },
            )

        if is_protected:
            return self._failure(
                code="protected_path_rejected",
                message="The requested item is protected and cannot be recycled.",
            )

        if not normalized_path.is_file() and not normalized_path.is_dir():
            return self._failure(
                code="unsupported_recycle_resource",
                message="Only regular files and folders can be recycled.",
            )

        return None

    def _measure_size(self, path: Path) -> int:
        if path.is_file():
            return path.stat().st_size

        total_size = 0
        pending_directories = [path]

        while pending_directories:
            current_directory = pending_directories.pop()

            with os.scandir(current_directory) as entries:
                for entry in entries:
                    entry_path = Path(entry.path)
                    entry_status = entry.stat(follow_symlinks=False)

                    if self._is_reparse_point(entry_path, entry_status):
                        raise OSError("A nested filesystem reparse point was rejected.")

                    if entry.is_dir(follow_symlinks=False):
                        pending_directories.append(entry_path)
                        continue

                    if entry.is_file(follow_symlinks=False):
                        total_size += entry_status.st_size

                        if total_size > self._configuration.maximum_recycle_size_bytes:
                            return total_size

        return total_size

    @staticmethod
    def _resource_type(path: Path) -> RecoveryResourceType:
        if path.is_file():
            return RecoveryResourceType.FILE

        return RecoveryResourceType.FOLDER

    @staticmethod
    def _is_drive_root(path: Path) -> bool:
        anchor = path.anchor

        if not anchor:
            return False

        try:
            return path.resolve(strict=False) == Path(anchor).resolve(strict=False)
        except (OSError, RuntimeError):
            return path == Path(anchor)

    @staticmethod
    def _is_reparse_point(
        path: Path,
        path_status: os.stat_result,
    ) -> bool:
        if path.is_symlink():
            return True

        file_attributes = getattr(
            path_status,
            "st_file_attributes",
            0,
        )

        return bool(file_attributes & _FILE_ATTRIBUTE_REPARSE_POINT)

    @staticmethod
    def _path_is_not_protected(path: Path) -> bool:
        del path
        return False

    @staticmethod
    def _fingerprint(path: Path) -> str:
        normalized = os.path.normcase(str(path))

        return hashlib.sha256(normalized.encode("utf-8", errors="strict")).hexdigest()

    @staticmethod
    def _backend_metadata(
        result: RecycleBinBackendResult,
    ) -> dict[str, JsonValue]:
        metadata: dict[str, JsonValue] = {
            "backend_code": result.code,
            "operation_aborted": result.operation_aborted,
        }

        if result.native_error_code is not None:
            metadata["native_error_code"] = result.native_error_code

        return metadata

    def _create_completed_record(
        self,
        *,
        path: Path,
        logical_location: str,
        relative_path: str,
        command_id: UUID,
        action_id: UUID,
        session_id: UUID,
        resource_type: RecoveryResourceType,
        size_bytes: int,
        backend_result: RecycleBinBackendResult,
    ) -> RecoveryRecord:
        if resource_type is RecoveryResourceType.FILE:
            action_type = RecoverableActionType.RECYCLE_FILE
        else:
            action_type = RecoverableActionType.RECYCLE_FOLDER

        item = RecycleBinItem(
            resource_type=resource_type,
            display_name=path.name,
            logical_location=logical_location,
            relative_path=relative_path,
            original_path_fingerprint=self._fingerprint(path),
            recycle_bin_reference=backend_result.recycle_bin_reference,
            size_bytes=size_bytes,
            metadata={
                "backend_code": backend_result.code,
            },
        )

        return RecoveryRecord(
            action_type=action_type,
            resource_type=resource_type,
            command_id=command_id,
            action_id=action_id,
            session_id=session_id,
            item=item,
            status=RecoveryRecordStatus.COMPLETED,
            metadata={
                "recoverable": True,
            },
        )

    @staticmethod
    def _failure(
        *,
        code: str,
        message: str,
        metadata: dict[str, JsonValue] | None = None,
    ) -> RecoveryResult:
        return RecoveryResult(
            success=False,
            code=code,
            message=message,
            metadata=metadata or {},
        )
