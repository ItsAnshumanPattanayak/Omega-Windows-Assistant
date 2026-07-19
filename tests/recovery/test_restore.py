"""Tests for safe recovery restoration."""

from __future__ import annotations

from dataclasses import replace
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
from omega.recovery.restore import RecoveryRestoreService


class FakeRestoreBackend:
    """Non-destructive restore backend used by tests."""

    def __init__(
        self,
        result: RestoreBackendResult | None = None,
    ) -> None:
        self.result = result or RestoreBackendResult(
            success=True,
            code="restored",
            message="Item restored by fake backend.",
        )
        self.calls: list[tuple[RecoveryRecord, Path]] = []

    def restore(
        self,
        record: RecoveryRecord,
        destination: Path,
    ) -> RestoreBackendResult:
        self.calls.append((record, destination))
        return self.result


class RaisingRestoreBackend:
    """Restore backend that simulates an unexpected failure."""

    def restore(
        self,
        record: RecoveryRecord,
        destination: Path,
    ) -> RestoreBackendResult:
        del record
        del destination
        raise OSError("Simulated restore failure.")


def _record(
    *,
    status: RecoveryRecordStatus = RecoveryRecordStatus.COMPLETED,
    recycle_bin_reference: str | None = "test-reference",
) -> RecoveryRecord:
    item = RecycleBinItem(
        resource_type=RecoveryResourceType.FILE,
        display_name="notes.txt",
        logical_location="desktop",
        relative_path="notes.txt",
        original_path_fingerprint="c" * 64,
        recycle_bin_reference=recycle_bin_reference,
        size_bytes=10,
    )

    return RecoveryRecord(
        action_type=RecoverableActionType.RECYCLE_FILE,
        resource_type=RecoveryResourceType.FILE,
        command_id=uuid4(),
        action_id=uuid4(),
        session_id=uuid4(),
        item=item,
        status=status,
    )


def _service(
    *,
    backend=None,
    protected_path_checker=None,
    enabled: bool = True,
) -> RecoveryRestoreService:
    return RecoveryRestoreService(
        configuration=RecoveryConfiguration(enabled=enabled),
        backend=backend or FakeRestoreBackend(),
        protected_path_checker=protected_path_checker,
    )


def test_completed_record_is_restored(
    tmp_path: Path,
) -> None:
    backend = FakeRestoreBackend()
    service = _service(backend=backend)
    record = _record()
    destination = (tmp_path / "notes.txt").resolve()

    result = service.restore(record, destination)

    assert result.success is True
    assert result.code == "restored"
    assert result.record == record
    assert backend.calls == [(record, destination)]


def test_relative_destination_is_rejected() -> None:
    service = _service()

    result = service.restore(
        _record(),
        Path("notes.txt"),
    )

    assert result.success is False
    assert result.code == "relative_restore_destination"


def test_existing_destination_is_rejected(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "notes.txt"
    destination.write_text("existing", encoding="utf-8")

    backend = FakeRestoreBackend()
    service = _service(backend=backend)

    result = service.restore(
        _record(),
        destination.resolve(),
    )

    assert result.success is False
    assert result.code == "restore_destination_conflict"
    assert backend.calls == []


def test_missing_parent_is_rejected(
    tmp_path: Path,
) -> None:
    destination = (tmp_path / "missing-parent" / "notes.txt").resolve()

    service = _service()

    result = service.restore(
        _record(),
        destination,
    )

    assert result.success is False
    assert result.code == "restore_parent_not_found"


def test_protected_destination_is_rejected(
    tmp_path: Path,
) -> None:
    destination = (tmp_path / "notes.txt").resolve()
    backend = FakeRestoreBackend()

    service = _service(
        backend=backend,
        protected_path_checker=lambda path: True,
    )

    result = service.restore(
        _record(),
        destination,
    )

    assert result.success is False
    assert result.code == "protected_restore_destination"
    assert backend.calls == []


def test_expired_record_is_rejected(
    tmp_path: Path,
) -> None:
    service = _service()

    result = service.restore(
        _record(status=RecoveryRecordStatus.EXPIRED),
        (tmp_path / "notes.txt").resolve(),
    )

    assert result.success is False
    assert result.code == "recovery_record_expired"


def test_already_restored_record_is_rejected(
    tmp_path: Path,
) -> None:
    record = _record()
    restored_record = replace(
        record,
        status=RecoveryRecordStatus.RESTORED,
        restored_at=record.created_at,
    )

    service = _service()

    result = service.restore(
        restored_record,
        (tmp_path / "notes.txt").resolve(),
    )

    assert result.success is False
    assert result.code == "recovery_record_already_restored"


def test_missing_recycle_bin_reference_is_rejected(
    tmp_path: Path,
) -> None:
    service = _service()

    result = service.restore(
        _record(recycle_bin_reference=None),
        (tmp_path / "notes.txt").resolve(),
    )

    assert result.success is False
    assert result.code == "missing_recycle_bin_reference"


def test_backend_failure_is_returned(
    tmp_path: Path,
) -> None:
    backend = FakeRestoreBackend(
        RestoreBackendResult(
            success=False,
            code="native_restore_failed",
            message="Simulated native restore failure.",
            native_error_code=5,
        )
    )
    service = _service(backend=backend)

    result = service.restore(
        _record(),
        (tmp_path / "notes.txt").resolve(),
    )

    assert result.success is False
    assert result.code == "native_restore_failed"
    assert result.metadata["native_error_code"] == 5


def test_backend_exception_fails_safely(
    tmp_path: Path,
) -> None:
    service = _service(backend=RaisingRestoreBackend())

    result = service.restore(
        _record(),
        (tmp_path / "notes.txt").resolve(),
    )

    assert result.success is False
    assert result.code == "restore_backend_error"
    assert result.metadata["error_type"] == "OSError"


def test_disabled_recovery_is_rejected(
    tmp_path: Path,
) -> None:
    service = _service(enabled=False)

    result = service.restore(
        _record(),
        (tmp_path / "notes.txt").resolve(),
    )

    assert result.success is False
    assert result.code == "recovery_disabled"
