"""Read-only Windows discovery for registered application launch targets."""

from __future__ import annotations

import logging
import os
import re
import shutil
import sys
from collections.abc import Callable, Mapping
from pathlib import Path

from omega.applications.definitions import (
    ALLOWED_APPLICATION_URIS,
    ApplicationDefinition,
)
from omega.applications.results import (
    ApplicationDiscoveryResult,
    ApplicationLaunchTarget,
    LaunchTargetKind,
)

_ENVIRONMENT_VARIABLE = re.compile(r"%([^%]+)%")


class WindowsApplicationDiscovery:
    """Resolve allowlisted paths or URIs without scanning user storage."""

    def __init__(
        self,
        *,
        platform_name: str = sys.platform,
        environment: Mapping[str, str] | None = None,
        which: Callable[[str], str | None] = shutil.which,
        logger: logging.Logger | None = None,
    ) -> None:
        self._platform_name = platform_name
        self._environment = dict(os.environ if environment is None else environment)
        self._which = which
        self._logger = logger or logging.getLogger("omega.applications.discovery")
        self._cache: dict[str, ApplicationLaunchTarget] = {}

    def discover(self, definition: ApplicationDefinition) -> ApplicationDiscoveryResult:
        """Return the first safe registered target, or a clear missing result."""
        if self._platform_name != "win32":
            self._logger.info(
                "Application discovery is unsupported on this platform: %s",
                definition.application_id,
            )
            return ApplicationDiscoveryResult(
                False,
                definition.application_id,
                reason="unsupported_platform",
                unsupported_platform=True,
            )

        cached = self._cache.get(definition.application_id)
        if cached is not None and self._target_is_current(cached, definition):
            return ApplicationDiscoveryResult(
                True, definition.application_id, cached, cached=True
            )
        self._cache.pop(definition.application_id, None)
        self._logger.info(
            "Discovering registered application: %s", definition.application_id
        )

        for configured_path in definition.candidate_paths:
            expanded = self._expand_environment(configured_path)
            if expanded is None:
                continue
            path = Path(expanded)
            if self._safe_executable(path, definition):
                return self._remember(definition, path)

        for executable_name in definition.executable_names:
            located = self._which(executable_name)
            if located and self._safe_executable(Path(located), definition):
                return self._remember(definition, Path(located))

        if definition.uri in ALLOWED_APPLICATION_URIS:
            target = ApplicationLaunchTarget(
                definition.application_id, LaunchTargetKind.URI, definition.uri
            )
            self._cache[definition.application_id] = target
            return ApplicationDiscoveryResult(True, definition.application_id, target)
        return ApplicationDiscoveryResult(
            False, definition.application_id, reason="not_found"
        )

    def invalidate(self, application_id: str | None = None) -> None:
        """Forget one discovery result, or all process-local cached results."""
        if application_id is None:
            self._cache.clear()
        else:
            self._cache.pop(application_id, None)

    def _remember(
        self, definition: ApplicationDefinition, path: Path
    ) -> ApplicationDiscoveryResult:
        target = ApplicationLaunchTarget(
            definition.application_id,
            LaunchTargetKind.EXECUTABLE,
            str(path.resolve()),
        )
        self._cache[definition.application_id] = target
        return ApplicationDiscoveryResult(True, definition.application_id, target)

    def _expand_environment(self, configured_path: str) -> str | None:
        lookup = {key.casefold(): value for key, value in self._environment.items()}
        missing = False

        def replace(match: re.Match[str]) -> str:
            nonlocal missing
            value = lookup.get(match.group(1).casefold())
            if value is None:
                missing = True
                return ""
            return value

        expanded = _ENVIRONMENT_VARIABLE.sub(replace, configured_path)
        return None if missing or "%" in expanded else expanded

    def _target_is_current(
        self, target: ApplicationLaunchTarget, definition: ApplicationDefinition
    ) -> bool:
        if target.kind is LaunchTargetKind.URI:
            return (
                target.value == definition.uri
                and target.value in ALLOWED_APPLICATION_URIS
            )
        return self._safe_executable(Path(target.value), definition)

    def _safe_executable(self, path: Path, definition: ApplicationDefinition) -> bool:
        try:
            if path.is_symlink() or not path.is_file():
                return False
            resolved = path.resolve(strict=True)
        except OSError:
            return False
        expected = {name.casefold() for name in definition.executable_names}
        if resolved.name.casefold() not in expected:
            return False
        temp_roots = {
            value.casefold()
            for name, value in self._environment.items()
            if name.casefold() in {"temp", "tmp"} and value
        }
        resolved_text = str(resolved).casefold()
        return not any(
            resolved_text == root
            or resolved_text.startswith(root.rstrip("\\/") + os.sep)
            for root in temp_roots
        )
