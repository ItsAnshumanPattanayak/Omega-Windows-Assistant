"""Tests for the safe Windows Recycle Bin service."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import pytest

from omega.recovery.configuration import RecoveryConfiguration
from omega.recovery.models import (
    RecoverableActionType,
    RecoveryRecordStatus,
    RecoveryResourceType,
)
from omega.recovery.protocols import RecycleBinBackendResult
from omega.recovery.results import RecoveryResult
from omega.recovery.windows_recycle_bin import WindowsRecycleBinService


class FakeRecycleBinBackend:
    """Non-destructive backend used by unit tests."""

    def __init__(
        self,
        result: RecycleBinBackendResult | None = None,
    ) -> None:
        self.result = result or RecycleBinBackendResult(
            success=True,
            code="recycled",
            message="Item recycled by the fake backend.",
            recycle_bin_reference="test-reference",
        )
        self.paths: list[Path] = []

    def recycle(self, path: Path) -> RecycleBinBackendResult:
        self.paths.append(path)
        return self.result


class RaisingRecycleBinBackend:
    """Backend that simulates an unexpected native failure."""

    def recycle(self, path: Path) -> RecycleBinBackendResult:
        del path
        raise OSError("Simulated backend failure.")


def _service(
    *,
    configuration: RecoveryConfiguration | None = None,
    backend: FakeRecycleBinBackend | RaisingRecycleBinBackend | None = None,
    protected_path_checker: Callable[[Path], bool] | None = None,
    platform_name: str = "win32",
) -> WindowsRecycleBinService:
    return WindowsRecycleBinService(
        configuration=configuration or RecoveryConfiguration(),
        backend=backend or FakeRecycleBinBackend(),
        protected_path_checker=protected_path_checker,
        platform_name=platform_name,
    )


def _recycle(
    service: WindowsRecycleBinService,
    path: Path,
) -> RecoveryResult:
    return service.recycle(
        path,
        logical_location="desktop",
        relative_path=path.name,
        command_id=uuid4(),
        action_id=uuid4(),
        session_id=uuid4(),
    )


def test_recycle_file_returns_completed_recovery_record(
    tmp_path: Path,
) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("Omega recovery test", encoding="utf-8")

    backend = FakeRecycleBinBackend()
    service = _service(backend=backend)

    result = _recycle(service, target)

    assert result.success is True
    assert result.code == "recycled"
    assert result.record is not None
    assert result.record.status is RecoveryRecordStatus.COMPLETED
    assert result.record.action_type is RecoverableActionType.RECYCLE_FILE
    assert result.record.resource_type is RecoveryResourceType.FILE
    assert result.record.item.display_name == "notes.txt"
    assert result.record.item.logical_location == "desktop"
    assert result.record.item.relative_path == "notes.txt"
    assert result.record.item.size_bytes == len(b"Omega recovery test")
    assert result.record.item.recycle_bin_reference == "test-reference"
    assert result.record.can_restore is True
    assert backend.paths == [target.resolve(strict=True)]

    public_item = result.record.item.to_dict()

    assert "original_path_fingerprint" not in public_item
    assert "recycle_bin_reference" not in public_item


def test_recycle_folder_measures_nested_file_sizes(
    tmp_path: Path,
) -> None:
    target = tmp_path / "project"
    nested = target / "nested"
    nested.mkdir(parents=True)

    (target / "one.txt").write_bytes(b"1234")
    (nested / "two.txt").write_bytes(b"123456")

    service = _service()

    result = _recycle(service, target)

    assert result.success is True
    assert result.record is not None
    assert result.record.action_type is RecoverableActionType.RECYCLE_FOLDER
    assert result.record.resource_type is RecoveryResourceType.FOLDER
    assert result.record.item.size_bytes == 10


def test_relative_path_is_rejected() -> None:
    service = _service()

    result = _recycle(service, Path("relative-file.txt"))

    assert result.success is False
    assert result.code == "relative_recycle_path"
    assert result.record is None


def test_missing_target_is_rejected(
    tmp_path: Path,
) -> None:
    service = _service()

    result = _recycle(service, tmp_path / "missing.txt")

    assert result.success is False
    assert result.code == "recycle_target_not_found"


def test_non_windows_platform_is_rejected(
    tmp_path: Path,
) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("data", encoding="utf-8")

    service = _service(platform_name="linux")

    result = _recycle(service, target)

    assert result.success is False
    assert result.code == "unsupported_platform"


def test_disabled_recovery_is_rejected(
    tmp_path: Path,
) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("data", encoding="utf-8")

    service = _service(configuration=RecoveryConfiguration(enabled=False))

    result = _recycle(service, target)

    assert result.success is False
    assert result.code == "recovery_disabled"


def test_protected_path_is_rejected_before_backend_execution(
    tmp_path: Path,
) -> None:
    target = tmp_path / "protected.txt"
    target.write_text("protected", encoding="utf-8")

    backend = FakeRecycleBinBackend()
    service = _service(
        backend=backend,
        protected_path_checker=lambda path: True,
    )

    result = _recycle(service, target)

    assert result.success is False
    assert result.code == "protected_path_rejected"
    assert backend.paths == []


def test_size_limit_is_enforced_before_backend_execution(
    tmp_path: Path,
) -> None:
    target = tmp_path / "large.txt"
    target.write_bytes(b"12345")

    configuration = RecoveryConfiguration(maximum_recycle_size_bytes=4)
    backend = FakeRecycleBinBackend()
    service = _service(
        configuration=configuration,
        backend=backend,
    )

    result = _recycle(service, target)

    assert result.success is False
    assert result.code == "recycle_size_limit_exceeded"
    assert backend.paths == []


def test_backend_failure_returns_structured_failure(
    tmp_path: Path,
) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("data", encoding="utf-8")

    backend = FakeRecycleBinBackend(
        RecycleBinBackendResult(
            success=False,
            code="native_recycle_failed",
            message="The simulated native operation failed.",
            native_error_code=5,
        )
    )
    service = _service(backend=backend)

    result = _recycle(service, target)

    assert result.success is False
    assert result.code == "native_recycle_failed"
    assert result.record is None
    assert result.metadata["native_error_code"] == 5


def test_unexpected_backend_exception_fails_safely(
    tmp_path: Path,
) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("data", encoding="utf-8")

    service = _service(backend=RaisingRecycleBinBackend())

    result = _recycle(service, target)

    assert result.success is False
    assert result.code == "recycle_backend_error"
    assert result.record is None
    assert result.metadata["error_type"] == "OSError"


def test_symlink_is_rejected_when_supported(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target.txt"
    target.write_text("data", encoding="utf-8")

    link = tmp_path / "link.txt"

    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Creating a file symlink is not permitted on this host.")

    backend = FakeRecycleBinBackend()
    service = _service(backend=backend)

    result = _recycle(service, link)

    assert result.success is False
    assert result.code == "reparse_point_rejected"
    assert backend.paths == []


def test_result_serialization_does_not_expose_absolute_path(
    tmp_path: Path,
) -> None:
    target = tmp_path / "private.txt"
    target.write_text("private", encoding="utf-8")

    service = _service()

    result = _recycle(service, target)
    serialized = result.to_dict()
    serialized_text = str(serialized)

    assert result.success is True
    assert str(target) not in serialized_text
    assert str(target.resolve(strict=True)) not in serialized_text
