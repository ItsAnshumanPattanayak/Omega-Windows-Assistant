"""Injectable boundaries for system queries and bounded controls."""

from __future__ import annotations

from typing import Protocol

from omega.system.models import (
    AudioState,
    BatterySummary,
    BrightnessState,
    CpuSummary,
    DiskSummary,
    MemorySummary,
    NetworkSummary,
    PowerActionRequest,
    ProcessSummary,
    SystemSummary,
)


class SystemInformationProvider(Protocol):
    def system_summary(self) -> SystemSummary: ...
    def cpu_summary(self) -> CpuSummary: ...
    def memory_summary(self) -> MemorySummary: ...
    def disk_summaries(self, limit: int) -> tuple[DiskSummary, ...]: ...
    def battery_summary(self) -> BatterySummary: ...
    def network_summary(self, limit: int) -> NetworkSummary: ...
    def processes(
        self, limit: int, name: str | None = None
    ) -> tuple[ProcessSummary, ...]: ...


class AudioController(Protocol):
    def get_state(self) -> AudioState: ...
    def set_volume(self, percent: int) -> AudioState: ...
    def set_muted(self, muted: bool) -> AudioState: ...


class BrightnessController(Protocol):
    def get_state(self) -> BrightnessState: ...
    def set_brightness(self, percent: int) -> BrightnessState: ...


class SettingsPageLauncher(Protocol):
    def open_page(self, page: str) -> None: ...


class PowerController(Protocol):
    def execute(self, request: PowerActionRequest) -> None: ...
