"""Safe restore orchestration for registered recovery records."""

from __future__ import annotations

from pathlib import Path

from omega.models._serialization import JsonValue
from omega.recovery.configuration import RecoveryConfiguration
from omega.recovery.models import (
    RecoveryRecord,
    RecoveryRecordStatus,
)
from omega.recovery.protocols import (
    ProtectedPathChecker,
    RestoreBackend,
    RestoreBackendResult,
)
from omega.recovery.results import RecoveryResult


class UnavailableRestoreBackend:
    """Fail-closed backend used until a native restore adapter is supplied."""

    def restore(
        self,
        record: RecoveryRecord,
        destination: Path,
    ) -> RestoreBackendResult:
        """Return a structured unavailable-backend result."""

        del record
        del destination

        return RestoreBackendResult(
            success=False,
            code="restore_backend_unavailable",
            message="No native Recycle Bin restore backend is configured.",
        )


class RecoveryRestoreService:
    """Validate and execute restoration of one recovery record."""

    def __init__(
        self,
        configuration: RecoveryConfiguration,
        backend: RestoreBackend | None = None,
        protected_path_checker: ProtectedPathChecker | None = None,
    ) -> None:
        if not isinstance(configuration, RecoveryConfiguration):
            raise TypeError("configuration must be a RecoveryConfiguration.")

        self._configuration = configuration
        self._backend = backend or UnavailableRestoreBackend()
        self._protected_path_checker = (
            protected_path_checker or self._path_is_not_protected
        )

    def restore(
        self,
        record: RecoveryRecord,
        destination: Path,
    ) -> RecoveryResult:
        """Restore one completed recovery record to a safe destination."""

        validation_failure = self._validate_request(
            record=record,
            destination=destination,
        )

        if validation_failure is not None:
            return validation_failure

        try:
            normalized_destination = destination.resolve(strict=False)
        except (OSError, RuntimeError) as error:
            return self._failure(
                code="restore_destination_resolution_failed",
                message="The restore destination could not be resolved safely.",
                metadata={
                    "error_type": type(error).__name__,
                },
            )

        try:
            is_protected = self._protected_path_checker(normalized_destination)
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
                code="protected_restore_destination",
                message="The requested restore destination is protected.",
            )

        if normalized_destination.exists():
            return self._failure(
                code="restore_destination_conflict",
                message="The restore destination already exists.",
            )

        parent = normalized_destination.parent

        if not parent.exists():
            return self._failure(
                code="restore_parent_not_found",
                message="The restore destination parent does not exist.",
            )

        if not parent.is_dir():
            return self._failure(
                code="restore_parent_not_directory",
                message="The restore destination parent is not a directory.",
            )

        try:
            backend_result = self._backend.restore(
                record,
                normalized_destination,
            )
        except Exception as error:
            return self._failure(
                code="restore_backend_error",
                message="The restore backend failed safely.",
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

        return RecoveryResult(
            success=True,
            code="restored",
            message=(f"{record.resource_type.value.title()} restored successfully."),
            record=record,
            metadata={
                "resource_type": record.resource_type.value,
                "backend_code": backend_result.code,
            },
        )

    def _validate_request(
        self,
        *,
        record: RecoveryRecord,
        destination: Path,
    ) -> RecoveryResult | None:
        if not self._configuration.enabled:
            return self._failure(
                code="recovery_disabled",
                message="Recovery operations are disabled.",
            )

        if record.status is RecoveryRecordStatus.EXPIRED:
            return self._failure(
                code="recovery_record_expired",
                message="The recovery record has expired.",
            )

        if record.status is RecoveryRecordStatus.RESTORED:
            return self._failure(
                code="recovery_record_already_restored",
                message="The recovery record has already been restored.",
            )

        if record.status is not RecoveryRecordStatus.COMPLETED:
            return self._failure(
                code="recovery_record_not_restorable",
                message="The recovery record is not currently restorable.",
            )

        if not destination.is_absolute():
            return self._failure(
                code="relative_restore_destination",
                message="The restore destination must be absolute.",
            )

        if record.item.recycle_bin_reference is None:
            return self._failure(
                code="missing_recycle_bin_reference",
                message=(
                    "The recovery record does not contain a restorable "
                    "Recycle Bin reference."
                ),
            )

        return None

    @staticmethod
    def _backend_metadata(
        result: RestoreBackendResult,
    ) -> dict[str, JsonValue]:
        metadata: dict[str, JsonValue] = {
            "backend_code": result.code,
            "operation_aborted": result.operation_aborted,
        }

        if result.native_error_code is not None:
            metadata["native_error_code"] = result.native_error_code

        return metadata

    @staticmethod
    def _path_is_not_protected(path: Path) -> bool:
        del path
        return False

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
