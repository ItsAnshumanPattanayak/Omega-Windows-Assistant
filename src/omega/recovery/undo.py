"""Undo execution over the process-local recovery registry."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import UUID

from omega.core.exceptions import RecoveryRecordError
from omega.models._serialization import utc_now
from omega.recovery.models import RecoveryRecordStatus
from omega.recovery.registry import RecoveryRegistry
from omega.recovery.restore import RecoveryRestoreService
from omega.recovery.results import RecoveryResult


class RecoveryUndoService:
    """Restore registered recovery records and update their lifecycle."""

    def __init__(
        self,
        registry: RecoveryRegistry,
        restore_service: RecoveryRestoreService,
    ) -> None:
        if not isinstance(registry, RecoveryRegistry):
            raise TypeError("registry must be a RecoveryRegistry.")

        if not isinstance(restore_service, RecoveryRestoreService):
            raise TypeError("restore_service must be a RecoveryRestoreService.")

        self._registry = registry
        self._restore_service = restore_service

    def undo(
        self,
        record_id: UUID,
        destination: Path,
    ) -> RecoveryResult:
        """Undo one registered recovery action by record identifier."""

        try:
            record = self._registry.require(
                record_id,
                now=utc_now(),
            )
        except RecoveryRecordError:
            return RecoveryResult(
                success=False,
                code="recovery_record_not_found",
                message="The requested recovery record was not found.",
            )

        if record.status is RecoveryRecordStatus.EXPIRED:
            return RecoveryResult(
                success=False,
                code="recovery_record_expired",
                message="The recovery record has expired.",
                record=record,
            )

        if record.status is RecoveryRecordStatus.RESTORED:
            return RecoveryResult(
                success=False,
                code="recovery_record_already_restored",
                message="The recovery record has already been restored.",
                record=record,
            )

        if record.status is not RecoveryRecordStatus.COMPLETED:
            return RecoveryResult(
                success=False,
                code="recovery_record_not_restorable",
                message="The recovery record is not currently restorable.",
                record=record,
            )

        result = self._restore_service.restore(
            record,
            destination,
        )

        if result.success:
            try:
                updated_record = self._registry.mark_restored(
                    record.record_id,
                    restored_at=result.completed_at,
                )
            except RecoveryRecordError:
                return RecoveryResult(
                    success=False,
                    code="restore_registry_update_failed",
                    message=(
                        "The item was restored, but Omega could not update "
                        "its recovery registry."
                    ),
                    record=record,
                )

            return RecoveryResult(
                success=True,
                code=result.code,
                message=result.message,
                record=updated_record,
                completed_at=result.completed_at,
                metadata=result.metadata,
            )

        self._mark_failed_when_possible(
            record_id=record.record_id,
            failure_code=result.code,
            failed_at=result.completed_at,
        )

        return result

    def undo_latest(
        self,
        destination: Path,
    ) -> RecoveryResult:
        """Undo the newest currently restorable recovery record."""

        record = self._registry.latest_restorable(now=utc_now())

        if record is None:
            return RecoveryResult(
                success=False,
                code="no_restorable_record",
                message="There is no recovery action available to undo.",
            )

        return self.undo(
            record.record_id,
            destination,
        )

    def _mark_failed_when_possible(
        self,
        *,
        record_id: UUID,
        failure_code: str,
        failed_at: datetime,
    ) -> None:
        try:
            self._registry.mark_failed(
                record_id,
                failure_code=failure_code,
                failed_at=failed_at,
            )
        except RecoveryRecordError:
            return
