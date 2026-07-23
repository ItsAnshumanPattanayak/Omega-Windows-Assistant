"""Lazy psutil-backed, read-only system information."""

from __future__ import annotations

import platform
import time

import psutil

from omega.system.models import (
    BatterySummary,
    CpuSummary,
    DiskSummary,
    MemorySummary,
    NetworkSummary,
    ProcessSummary,
    SystemSummary,
)

_PROTECTED = frozenset(
    {
        "system",
        "registry",
        "smss.exe",
        "csrss.exe",
        "wininit.exe",
        "services.exe",
        "lsass.exe",
        "winlogon.exe",
        "explorer.exe",
        "python.exe",
        "pythonw.exe",
        "omega.exe",
    }
)


class PsutilSystemInformationProvider:
    """Query bounded counters without command lines, environments, or file lists."""

    def cpu_summary(self) -> CpuSummary:
        return CpuSummary(
            logical_processors=psutil.cpu_count(logical=True) or 1,
            physical_processors=psutil.cpu_count(logical=False),
            usage_percent=float(psutil.cpu_percent(interval=None)),
        )

    def memory_summary(self) -> MemorySummary:
        value = psutil.virtual_memory()
        return MemorySummary(
            int(value.total),
            int(value.available),
            int(value.used),
            float(value.percent),
        )

    def system_summary(self) -> SystemSummary:
        return SystemSummary(
            operating_system=platform.system() or "Unknown",
            architecture=platform.machine() or "Unknown",
            uptime_seconds=max(0, int(time.time() - psutil.boot_time())),
            cpu=self.cpu_summary(),
            memory=self.memory_summary(),
        )

    def disk_summaries(self, limit: int) -> tuple[DiskSummary, ...]:
        results: list[DiskSummary] = []
        for partition in psutil.disk_partitions(all=False):
            if len(results) >= limit:
                break
            try:
                usage = psutil.disk_usage(partition.mountpoint)
            except (OSError, PermissionError):
                continue
            results.append(
                DiskSummary(
                    partition.device or partition.mountpoint,
                    int(usage.total),
                    int(usage.used),
                    int(usage.free),
                    float(usage.percent),
                )
            )
        return tuple(results)

    def battery_summary(self) -> BatterySummary:
        battery = psutil.sensors_battery()
        if battery is None:
            return BatterySummary(False)
        remaining = (
            None
            if battery.secsleft
            in {psutil.POWER_TIME_UNKNOWN, psutil.POWER_TIME_UNLIMITED}
            else max(0, int(battery.secsleft))
        )
        return BatterySummary(
            True, float(battery.percent), bool(battery.power_plugged), remaining
        )

    def network_summary(self, limit: int) -> NetworkSummary:
        counters = psutil.net_io_counters()
        stats = psutil.net_if_stats()
        names = tuple(
            sorted(name for name, value in stats.items() if value.isup)[:limit]
        )
        return NetworkSummary(
            connected=bool(names),
            interface_count=len(names),
            bytes_sent=int(counters.bytes_sent),
            bytes_received=int(counters.bytes_recv),
            interfaces=names,
        )

    def processes(
        self, limit: int, name: str | None = None
    ) -> tuple[ProcessSummary, ...]:
        query = name.casefold() if name else None
        results: list[ProcessSummary] = []
        for process in psutil.process_iter(
            attrs=("pid", "name", "cpu_percent", "memory_percent", "status")
        ):
            if len(results) >= limit:
                break
            try:
                info = process.info
                process_name = str(info.get("name") or "unknown")
                if query and query not in process_name.casefold():
                    continue
                results.append(
                    ProcessSummary(
                        pid=int(info["pid"]),
                        name=process_name,
                        cpu_percent=max(
                            0.0, min(100.0, float(info["cpu_percent"] or 0))
                        ),
                        memory_percent=max(
                            0.0, min(100.0, float(info["memory_percent"] or 0))
                        ),
                        status=str(info.get("status") or "unknown"),
                        protected=process_name.casefold() in _PROTECTED,
                    )
                )
            except (psutil.Error, OSError, ValueError):
                continue
        return tuple(results)
