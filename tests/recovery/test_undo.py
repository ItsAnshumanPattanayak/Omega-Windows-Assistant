"""Tests for recovery undo execution."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from omega.recovery.configuration import RecoveryConfiguration
from omega.recovery.models import (
    RecoverableActionType,
    RecoveryRecord,
    RecoveryRecordStatus,
    RecoveryResourceType,
    RecycleBinItem,
)
from omega.recovery.protocols import RestoreBackendResult
from omega.recovery.registry import RecoveryRegistry
from omega.recovery.restore import RecoveryRestoreService
from omega.recovery.undo import RecoveryUndoService


class FakeRestoreBackend:
    """Non-destructive backend for undo tests."""

    def __init__(
        self,
        result: RestoreBackendResult | None = None,
    ) -> None:
        self.result = result or RestoreBackendResult(
            success=True,
            code="restored",
            message="Fake restore completed.",
        )

    def restore(
        self,
        record: RecoveryRecord,
        destination: Path,
    ) -> RestoreBackendResult:
        del record
        del destination
        return self.result


def _record() -> RecoveryRecord:
    item = RecycleBinItem(
        resource_type=RecoveryResourceType.FILE,
        display_name="notes.txt",
        logical_location="desktop",
        relative_path="notes.txt",
        original_path_fingerprint="d" * 64,
        recycle_bin_reference="test-reference",
        size_bytes=10,
    )

    return RecoveryRecord(
        action_type=RecoverableActionType.RECYCLE_FILE,
        resource_type=RecoveryResourceType.FILE,
        command_id=uuid4(),
        action_id=uuid4(),
        session_id=uuid4(),
        item=item,
        status=RecoveryRecordStatus.COMPLETED,
    )


def _services(
    *,
    backend_result: RestoreBackendResult | None = None,
) -> tuple[RecoveryRegistry, RecoveryUndoService]:
    configuration = RecoveryConfiguration()
    registry = RecoveryRegistry(configuration)
    restore_service = RecoveryRestoreService(
        configuration=configuration,
        backend=FakeRestoreBackend(backend_result),
    )
    undo_service = RecoveryUndoService(
        registry=registry,
        restore_service=restore_service,
    )

    return registry, undo_service


def test_undo_restores_and_marks_record_restored(
    tmp_path: Path,
) -> None:
    registry, undo_service = _services()
    record = _record()
    registered = registry.register(
        record,
        registered_at=record.created_at,
    )

    result = undo_service.undo(
        registered.record_id,
        (tmp_path / "notes.txt").resolve(),
    )

    assert result.success is True
    assert result.record is not None
    assert result.record.status is RecoveryRecordStatus.RESTORED
    assert result.record.restored_at is not None

    stored = registry.require(
        registered.record_id,
        now=result.completed_at,
    )

    assert stored.status is RecoveryRecordStatus.RESTORED


def test_unknown_record_returns_structured_failure(
    tmp_path: Path,
) -> None:
    _, undo_service = _services()

    result = undo_service.undo(
        uuid4(),
        (tmp_path / "notes.txt").resolve(),
    )

    assert result.success is False
    assert result.code == "recovery_record_not_found"


def test_undo_latest_restores_latest_record(
    tmp_path: Path,
) -> None:
    registry, undo_service = _services()

    first = _record()
    second = _record()

    registry.register(
        first,
        registered_at=first.created_at,
    )
    registered_second = registry.register(
        second,
        registered_at=second.created_at,
    )

    result = undo_service.undo_latest((tmp_path / "notes.txt").resolve())

    assert result.success is True
    assert result.record is not None
    assert result.record.record_id == registered_second.record_id


def test_undo_latest_without_records_returns_failure(
    tmp_path: Path,
) -> None:
    _, undo_service = _services()

    result = undo_service.undo_latest((tmp_path / "notes.txt").resolve())

    assert result.success is False
    assert result.code == "no_restorable_record"


def test_restore_failure_marks_record_failed(
    tmp_path: Path,
) -> None:
    backend_result = RestoreBackendResult(
        success=False,
        code="native_restore_failed",
        message="Fake restore failure.",
    )
    registry, undo_service = _services(backend_result=backend_result)

    record = _record()
    registered = registry.register(
        record,
        registered_at=record.created_at,
    )

    result = undo_service.undo(
        registered.record_id,
        (tmp_path / "notes.txt").resolve(),
    )

    assert result.success is False
    assert result.code == "native_restore_failed"

    stored = registry.require(
        registered.record_id,
        now=result.completed_at,
    )

    assert stored.status is RecoveryRecordStatus.FAILED
    assert stored.failure_code == "native_restore_failed"
