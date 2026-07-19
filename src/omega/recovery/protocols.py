"""Protocols and low-level outcomes for Recycle Bin integrations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from omega.core.exceptions import ModelValidationError


@dataclass(frozen=True)
class RecycleBinBackendResult:
    """Result returned by a platform-specific Recycle Bin backend."""

    success: bool
    code: str
    message: str
    recycle_bin_reference: str | None = None
    native_error_code: int | None = None
    operation_aborted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise ModelValidationError("success must be a boolean.")

        for field_name in ("code", "message"):
            value = getattr(self, field_name)

            if not isinstance(value, str) or not value.strip():
                raise ModelValidationError(f"{field_name} must be a non-empty string.")

        if self.recycle_bin_reference is not None:
            if (
                not isinstance(self.recycle_bin_reference, str)
                or not self.recycle_bin_reference.strip()
            ):
                raise ModelValidationError(
                    "recycle_bin_reference must be non-empty when supplied."
                )

        if self.native_error_code is not None:
            if (
                isinstance(self.native_error_code, bool)
                or not isinstance(self.native_error_code, int)
                or self.native_error_code < 0
            ):
                raise ModelValidationError(
                    "native_error_code must be a non-negative integer or None."
                )

        if not isinstance(self.operation_aborted, bool):
            raise ModelValidationError("operation_aborted must be a boolean.")


@runtime_checkable
class RecycleBinBackend(Protocol):
    """Platform backend capable of recycling one validated path."""

    def recycle(self, path: Path) -> RecycleBinBackendResult:
        """Move one validated absolute path to the system Recycle Bin."""


@runtime_checkable
class ProtectedPathChecker(Protocol):
    """Callable boundary for checking protected filesystem paths."""

    def __call__(self, path: Path) -> bool:
        """Return whether a path must be protected from recycling."""
