"""Serializable, platform-neutral system information records."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from omega.core.exceptions import ModelValidationError


class PowerOperation(StrEnum):
    LOCK = "lock"
    SLEEP = "sleep"
    HIBERNATE = "hibernate"
    SIGN_OUT = "sign_out"
    RESTART = "restart"
    SHUTDOWN = "shutdown"
    CANCEL = "cancel"


def _percentage(value: float, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ModelValidationError(f"{field} must be numeric.")
    if not 0 <= float(value) <= 100:
        raise ModelValidationError(f"{field} must be between 0 and 100.")


@dataclass(frozen=True)
class CpuSummary:
    logical_processors: int
    physical_processors: int | None
    usage_percent: float

    def __post_init__(self) -> None:
        if self.logical_processors < 1:
            raise ModelValidationError("logical_processors must be positive.")
        if self.physical_processors is not None and self.physical_processors < 1:
            raise ModelValidationError("physical_processors must be positive.")
        _percentage(self.usage_percent, "usage_percent")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemorySummary:
    total_bytes: int
    available_bytes: int
    used_bytes: int
    usage_percent: float

    def __post_init__(self) -> None:
        if min(self.total_bytes, self.available_bytes, self.used_bytes) < 0:
            raise ModelValidationError("Memory byte values must be non-negative.")
        if (
            self.available_bytes > self.total_bytes
            or self.used_bytes > self.total_bytes
        ):
            raise ModelValidationError("Memory values cannot exceed total_bytes.")
        _percentage(self.usage_percent, "usage_percent")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DiskSummary:
    device: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    usage_percent: float

    def __post_init__(self) -> None:
        if not self.device.strip():
            raise ModelValidationError("device must not be empty.")
        if min(self.total_bytes, self.used_bytes, self.free_bytes) < 0:
            raise ModelValidationError("Disk byte values must be non-negative.")
        _percentage(self.usage_percent, "usage_percent")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BatterySummary:
    available: bool
    percent: float | None = None
    charging: bool | None = None
    seconds_remaining: int | None = None

    def __post_init__(self) -> None:
        if self.percent is not None:
            _percentage(self.percent, "percent")
        if not self.available and any(
            value is not None
            for value in (self.percent, self.charging, self.seconds_remaining)
        ):
            raise ModelValidationError("Unavailable battery data must be empty.")
        if self.seconds_remaining is not None and self.seconds_remaining < 0:
            raise ModelValidationError("seconds_remaining must be non-negative.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NetworkSummary:
    connected: bool
    interface_count: int
    bytes_sent: int
    bytes_received: int
    interfaces: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if min(self.interface_count, self.bytes_sent, self.bytes_received) < 0:
            raise ModelValidationError("Network counters must be non-negative.")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["interfaces"] = list(self.interfaces)
        return value


@dataclass(frozen=True)
class AudioState:
    volume_percent: int
    muted: bool

    def __post_init__(self) -> None:
        _percentage(self.volume_percent, "volume_percent")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BrightnessState:
    percentages: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.percentages:
            raise ModelValidationError("At least one display value is required.")
        for value in self.percentages:
            _percentage(value, "brightness percentage")

    def to_dict(self) -> dict[str, Any]:
        return {"percentages": list(self.percentages)}


@dataclass(frozen=True)
class ProcessSummary:
    pid: int
    name: str
    cpu_percent: float
    memory_percent: float
    status: str
    protected: bool = False

    def __post_init__(self) -> None:
        if self.pid < 0 or not self.name.strip() or not self.status.strip():
            raise ModelValidationError("Process identity fields are invalid.")
        _percentage(self.cpu_percent, "cpu_percent")
        _percentage(self.memory_percent, "memory_percent")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SystemSummary:
    operating_system: str
    architecture: str
    uptime_seconds: int
    cpu: CpuSummary
    memory: MemorySummary

    def __post_init__(self) -> None:
        if not self.operating_system.strip() or not self.architecture.strip():
            raise ModelValidationError("System identity must not be empty.")
        if self.uptime_seconds < 0:
            raise ModelValidationError("uptime_seconds must be non-negative.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "operating_system": self.operating_system,
            "architecture": self.architecture,
            "uptime_seconds": self.uptime_seconds,
            "cpu": self.cpu.to_dict(),
            "memory": self.memory.to_dict(),
        }


@dataclass(frozen=True)
class PowerActionRequest:
    operation: PowerOperation
    countdown_seconds: int = 0

    def __post_init__(self) -> None:
        if (
            isinstance(self.countdown_seconds, bool)
            or not 0 <= self.countdown_seconds <= 60
        ):
            raise ModelValidationError("countdown_seconds must be between 0 and 60.")
