"""Controlled Windows application launching with no user-derived arguments."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, cast

from omega.applications.definitions import (
    ALLOWED_APPLICATION_URIS,
    ApplicationDefinition,
)
from omega.applications.results import (
    ApplicationLaunchResult,
    ApplicationLaunchTarget,
    LaunchTargetKind,
)


class _LaunchedProcess(Protocol):
    pid: int

    def poll(self) -> int | None: ...


def _windows_startfile(target: str) -> None:
    startfile = getattr(os, "startfile", None)
    if startfile is None:
        raise OSError("Windows URI launching is unavailable.")
    startfile(target)


class WindowsApplicationLauncher:
    """Launch one validated registry target using a fixed argument sequence."""

    def __init__(
        self,
        *,
        platform_name: str = sys.platform,
        popen_factory: Callable[..., _LaunchedProcess] | None = None,
        uri_launcher: Callable[[str], None] = _windows_startfile,
        logger: logging.Logger | None = None,
    ) -> None:
        self._platform_name = platform_name
        self._popen = popen_factory or cast(
            Callable[..., _LaunchedProcess], subprocess.Popen[Any]
        )
        self._uri_launcher = uri_launcher
        self._logger = logger or logging.getLogger("omega.applications.launcher")

    def launch(
        self, definition: ApplicationDefinition, target: ApplicationLaunchTarget
    ) -> ApplicationLaunchResult:
        """Send a launch request only when the target matches its definition."""
        if self._platform_name != "win32":
            return ApplicationLaunchResult(
                False,
                definition.application_id,
                reason="unsupported_platform",
                unsupported_platform=True,
            )
        if target.application_id != definition.application_id:
            return ApplicationLaunchResult(
                False, definition.application_id, reason="target_mismatch"
            )
        self._logger.info("Sending safe launch request: %s", definition.application_id)
        try:
            if target.kind is LaunchTargetKind.URI:
                if (
                    target.value != definition.uri
                    or target.value not in ALLOWED_APPLICATION_URIS
                ):
                    return ApplicationLaunchResult(
                        False, definition.application_id, reason="unsafe_uri"
                    )
                self._uri_launcher(target.value)
                return ApplicationLaunchResult(
                    True, definition.application_id, verified=False
                )

            path = Path(target.value)
            expected = {name.casefold() for name in definition.executable_names}
            if (
                path.name.casefold() not in expected
                or path.is_symlink()
                or not path.is_file()
            ):
                return ApplicationLaunchResult(
                    False, definition.application_id, reason="unsafe_target"
                )
            process = self._popen([str(path)], shell=False)
            running = process.poll() is None
            return ApplicationLaunchResult(
                running,
                definition.application_id,
                pid=process.pid,
                verified=running,
                reason=None if running else "process_exited",
            )
        except FileNotFoundError:
            return ApplicationLaunchResult(
                False, definition.application_id, reason="not_found"
            )
        except PermissionError:
            return ApplicationLaunchResult(
                False,
                definition.application_id,
                reason="permission_denied",
                permission_denied=True,
            )
        except OSError:
            self._logger.exception(
                "Registered application launch failed: %s", definition.application_id
            )
            return ApplicationLaunchResult(
                False, definition.application_id, reason="launch_failed"
            )
