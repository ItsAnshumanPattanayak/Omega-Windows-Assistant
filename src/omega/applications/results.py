"""Small structured records used by controlled application services."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from omega.core.exceptions import ModelValidationError
from omega.models._serialization import JsonValue


class LaunchTargetKind(StrEnum):
    """Kinds of launch targets that may appear in the application registry."""

    EXECUTABLE = "executable"
    URI = "uri"


@dataclass(frozen=True)
class ApplicationLaunchTarget:
    """A discovered target derived only from a registered definition."""

    application_id: str
    kind: LaunchTargetKind
    value: str

    def __post_init__(self) -> None:
        if not self.application_id or not self.value:
            raise ModelValidationError("Launch targets require an ID and value.")
        if not isinstance(self.kind, LaunchTargetKind):
            raise ModelValidationError("kind must be a LaunchTargetKind.")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "application_id": self.application_id,
            "kind": self.kind.value,
            "value": self.value,
        }


@dataclass(frozen=True)
class ApplicationDiscoveryResult:
    """Outcome of a read-only application discovery attempt."""

    found: bool
    application_id: str
    target: ApplicationLaunchTarget | None = None
    reason: str | None = None
    cached: bool = False
    unsupported_platform: bool = False

    def __post_init__(self) -> None:
        if self.found != (self.target is not None):
            raise ModelValidationError(
                "A successful discovery result requires exactly one target."
            )


@dataclass(frozen=True)
class ApplicationLaunchResult:
    """Internal result of sending a controlled launch request."""

    success: bool
    application_id: str
    pid: int | None = None
    verified: bool = False
    reason: str | None = None
    permission_denied: bool = False
    unsupported_platform: bool = False

    def __post_init__(self) -> None:
        if self.pid is not None and (isinstance(self.pid, bool) or self.pid <= 0):
            raise ModelValidationError("pid must be positive when supplied.")


@dataclass(frozen=True)
class ApplicationProcess:
    """Safe process snapshot without a live psutil process object."""

    pid: int
    name: str
    application_id: str
    executable_path: str | None = None
    created_at: float | None = None
    is_primary_candidate: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.pid, bool) or not isinstance(self.pid, int) or self.pid <= 0:
            raise ModelValidationError("Process PID must be a positive integer.")
        if not self.name or not self.application_id:
            raise ModelValidationError("Process snapshots require a name and ID.")
        if self.created_at is not None and self.created_at < 0:
            raise ModelValidationError("created_at must be non-negative.")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "pid": self.pid,
            "name": self.name,
            "application_id": self.application_id,
            "executable_path": self.executable_path,
            "created_at": self.created_at,
            "is_primary_candidate": self.is_primary_candidate,
        }


@dataclass(frozen=True)
class ProcessInspectionResult:
    """Read-only process inspection with partial-visibility information."""

    processes: tuple[ApplicationProcess, ...] = ()
    inaccessible_count: int = 0

    def __post_init__(self) -> None:
        if self.inaccessible_count < 0:
            raise ModelValidationError("inaccessible_count must be non-negative.")


@dataclass(frozen=True)
class ProcessOperationResult:
    """Summary of a controlled terminate or kill operation."""

    attempted: int = 0
    stopped: int = 0
    access_denied: int = 0
    timed_out: int = 0
    stale: int = 0
    protected: int = 0

    def __post_init__(self) -> None:
        values = (
            self.attempted,
            self.stopped,
            self.access_denied,
            self.timed_out,
            self.stale,
            self.protected,
        )
        if any(isinstance(value, bool) or value < 0 for value in values):
            raise ModelValidationError("Process-operation counts must be non-negative.")

    @property
    def complete(self) -> bool:
        return self.attempted > 0 and self.stopped == self.attempted
