"""Exact-name process inspection and controlled process operations."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Iterable
from typing import Protocol, cast

import psutil

from omega.applications.definitions import ApplicationDefinition
from omega.applications.results import (
    ApplicationProcess,
    ProcessInspectionResult,
    ProcessOperationResult,
)

CRITICAL_PROCESS_NAMES = frozenset(
    {
        "system",
        "registry",
        "smss.exe",
        "csrss.exe",
        "wininit.exe",
        "services.exe",
        "lsass.exe",
        "svchost.exe",
        "winlogon.exe",
        "dwm.exe",
        "explorer.exe",
    }
)


class ProcessHandle(Protocol):
    """The narrow psutil surface used by Omega."""

    pid: int

    def name(self) -> str: ...

    def exe(self) -> str: ...

    def create_time(self) -> float: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...

    def wait(self, timeout: float | None = None) -> int | None: ...


class ApplicationProcessService:
    """Inspect and stop only exact processes registered for an application."""

    def __init__(
        self,
        *,
        process_iterator: Callable[[], Iterable[ProcessHandle]] | None = None,
        process_factory: Callable[[int], ProcessHandle] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._process_iterator = process_iterator or cast(
            Callable[[], Iterable[ProcessHandle]], psutil.process_iter
        )
        self._process_factory = process_factory or cast(
            Callable[[int], ProcessHandle], psutil.Process
        )
        self._logger = logger or logging.getLogger("omega.applications.processes")

    def inspect(
        self,
        definition: ApplicationDefinition,
        trusted_executable_path: str | None = None,
    ) -> ProcessInspectionResult:
        """Return exact registered matches without exposing live process handles."""
        expected = {name.casefold() for name in definition.process_names}
        executable_names = {name.casefold() for name in definition.executable_names}
        matches: list[ApplicationProcess] = []
        inaccessible = 0
        try:
            processes = self._process_iterator()
            for process in processes:
                try:
                    name = process.name()
                    if name.casefold() not in expected:
                        continue
                    executable_path: str | None
                    try:
                        executable_path = process.exe() or None
                    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
                        executable_path = None
                        inaccessible += 1
                    if (
                        executable_path is not None
                        and trusted_executable_path is not None
                        and not self._same_path(
                            executable_path, trusted_executable_path
                        )
                    ):
                        continue
                    try:
                        created_at = process.create_time()
                    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
                        created_at = None
                    matches.append(
                        ApplicationProcess(
                            pid=process.pid,
                            name=name,
                            application_id=definition.application_id,
                            executable_path=executable_path,
                            created_at=created_at,
                            is_primary_candidate=(
                                executable_path is not None
                                and executable_path.rsplit("\\", 1)[-1].casefold()
                                in executable_names
                            ),
                        )
                    )
                except (
                    psutil.AccessDenied,
                    psutil.NoSuchProcess,
                    psutil.ZombieProcess,
                ):
                    inaccessible += 1
        except (psutil.AccessDenied, psutil.Error, OSError):
            inaccessible += 1
        return ProcessInspectionResult(tuple(matches), inaccessible)

    @staticmethod
    def _same_path(left: str, right: str) -> bool:
        try:
            return os.path.normcase(os.path.realpath(left)) == os.path.normcase(
                os.path.realpath(right)
            )
        except OSError:
            return False

    def terminate(
        self,
        definition: ApplicationDefinition,
        processes: Iterable[ApplicationProcess],
        timeout_seconds: float,
    ) -> ProcessOperationResult:
        """Gracefully terminate validated snapshots, never critical processes."""
        return self._operate(definition, processes, timeout_seconds, force=False)

    def kill(
        self,
        definition: ApplicationDefinition,
        processes: Iterable[ApplicationProcess],
        timeout_seconds: float,
    ) -> ProcessOperationResult:
        """Kill validated snapshots only after higher layers authorize force close."""
        return self._operate(definition, processes, timeout_seconds, force=True)

    def _operate(
        self,
        definition: ApplicationDefinition,
        processes: Iterable[ApplicationProcess],
        timeout_seconds: float,
        *,
        force: bool,
    ) -> ProcessOperationResult:
        attempted = stopped = denied = timed_out = stale = protected = 0
        expected = {name.casefold() for name in definition.process_names}
        for snapshot in tuple(processes):
            attempted += 1
            if snapshot.name.casefold() in CRITICAL_PROCESS_NAMES:
                protected += 1
                continue
            try:
                process = self._process_factory(snapshot.pid)
                current_name = process.name()
                if current_name.casefold() not in expected:
                    stale += 1
                    continue
                if snapshot.created_at is not None:
                    current_created_at = process.create_time()
                    if abs(current_created_at - snapshot.created_at) > 0.001:
                        stale += 1
                        continue
                if force:
                    process.kill()
                else:
                    process.terminate()
                process.wait(timeout=timeout_seconds)
                stopped += 1
            except psutil.NoSuchProcess:
                stopped += 1
            except psutil.AccessDenied:
                denied += 1
                self._logger.warning(
                    "Access denied for registered process: %s",
                    definition.application_id,
                )
            except psutil.TimeoutExpired:
                timed_out += 1
            except (psutil.Error, OSError):
                stale += 1
        return ProcessOperationResult(
            attempted=attempted,
            stopped=stopped,
            access_denied=denied,
            timed_out=timed_out,
            stale=stale,
            protected=protected,
        )
