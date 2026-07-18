"""Central protected process, application, and resolved-path enforcement."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

from omega.core.exceptions import ProtectedResourceError
from omega.models import IntentType
from omega.safety.models import SafetyContext
from omega.utils.paths import config_dir, project_root

_PATH_FIELDS = frozenset(
    {
        "file_name",
        "folder_name",
        "source_file",
        "source_folder",
        "new_name",
        "parent_path",
        "relative_subpath",
        "destination_path",
        "path",
    }
)
_BLOCKED_APPLICATIONS = frozenset(
    {"file_explorer", "settings", "task_manager", "command_prompt", "powershell"}
)
_CRITICAL_PROCESSES = frozenset(
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
_SHELL_MARKERS = re.compile(r"(?:&&|\|\||[|;<>`]|\$\(|\r|\n)")


@dataclass(frozen=True)
class ProtectedResourceResult:
    denied: bool
    reason_code: str = "RESOURCE_ALLOWED"
    user_message: str = ""
    policy_id: str = "SAFETY-PROTECTED-PATH-001"


@dataclass(frozen=True)
class ProtectedResourceConfiguration:
    """Validated static resource names loaded without dynamic expansion."""

    protected_locations: tuple[str, ...]
    protected_project_paths: tuple[str, ...]
    protected_processes: frozenset[str]

    @classmethod
    def from_file(cls, path: Path | None = None) -> ProtectedResourceConfiguration:
        selected = path or config_dir() / "protected_paths.json"
        try:
            raw = json.loads(selected.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ProtectedResourceError(
                "Protected-resource configuration is invalid."
            ) from error
        if not isinstance(raw, Mapping):
            raise ProtectedResourceError(
                "Protected-resource configuration must be an object."
            )

        def strings(name: str) -> tuple[str, ...]:
            value = raw.get(name)
            if (
                isinstance(value, (str, bytes))
                or not isinstance(value, Sequence)
                or not all(isinstance(item, str) and item.strip() for item in value)
            ):
                raise ProtectedResourceError(f"{name} must be a list of strings.")
            result = tuple(value)
            if len({item.casefold() for item in result}) != len(result):
                raise ProtectedResourceError(f"{name} must not contain duplicates.")
            return result

        locations = strings("protected_locations")
        project_paths = strings("protected_project_paths")
        processes = strings("protected_processes")
        if any(PureWindowsPath(item).is_absolute() for item in project_paths):
            raise ProtectedResourceError(
                "Protected project paths must be repository-relative."
            )
        return cls(locations, project_paths, frozenset(processes))


class ProtectedResourceEvaluator:
    """Fail closed for non-contained, special, linked, or protected resources."""

    def __init__(self, protected_paths: tuple[Path, ...] | None = None) -> None:
        selected = protected_paths if protected_paths is not None else self._defaults()
        self._protected = tuple(path.resolve(strict=False) for path in selected)

    @classmethod
    def from_file(cls, path: Path | None = None) -> ProtectedResourceEvaluator:
        configuration = ProtectedResourceConfiguration.from_file(path)
        root = project_root()
        protected = tuple(Path(item) for item in configuration.protected_locations)
        protected += tuple(
            root / item for item in configuration.protected_project_paths
        )
        return cls(protected)

    @staticmethod
    def _defaults() -> tuple[Path, ...]:
        candidates: list[Path] = []
        for variable in (
            "SystemRoot",
            "ProgramFiles",
            "ProgramFiles(x86)",
            "ProgramData",
        ):
            value = os.environ.get(variable)
            if value:
                candidates.append(Path(value))
        drive = os.environ.get("SystemDrive", "C:")
        candidates.extend(
            Path(drive) / name
            for name in (
                "Windows",
                "Program Files",
                "Program Files (x86)",
                "ProgramData",
                "Recovery",
                "System Volume Information",
                "$Recycle.Bin",
                "Boot",
                "EFI",
                "pagefile.sys",
                "hiberfil.sys",
            )
        )
        root = project_root()
        candidates.extend(
            root / relative
            for relative in (
                ".git",
                "config",
                "data/logs",
                "data/action_backups",
                "data/command_history",
                "build",
                "dist",
                ".venv",
                "venv",
            )
        )
        return tuple(candidates)

    def evaluate(self, context: SafetyContext) -> ProtectedResourceResult:
        if context.action.intent is IntentType.CLOSE_APPLICATION:
            app = (context.application_id or "").casefold()
            process = str(context.action.parameters.get("process_name", "")).casefold()
            if app in _BLOCKED_APPLICATIONS or process in _CRITICAL_PROCESSES:
                return ProtectedResourceResult(
                    True,
                    "PROTECTED_APPLICATION",
                    "Omega cannot close that protected Windows application.",
                    "SAFETY-APP-CLOSE-001",
                )
        if context.command.original_text and _SHELL_MARKERS.search(
            context.command.original_text
        ):
            return ProtectedResourceResult(
                True,
                "SHELL_INJECTION_REJECTED",
                "Omega does not execute commands containing shell control syntax.",
                "SAFETY-SHELL-DENY-001",
            )
        for key, value in context.action.parameters.items():
            if key in _PATH_FIELDS and isinstance(value, str):
                invalid = self._unsafe_user_path(value)
                if invalid:
                    return invalid
        for path in (context.source_path, context.destination_path):
            if path is None:
                continue
            if self._linked(path):
                return ProtectedResourceResult(
                    True,
                    "LINKED_PATH_REJECTED",
                    "Omega cannot use symbolic links or junctions for that operation.",
                    "SAFETY-LINK-DENY-001",
                )
            resolved = path.resolve(strict=False)
            if any(self._within(resolved, root) for root in self._protected):
                return ProtectedResourceResult(
                    True,
                    "PROTECTED_PATH",
                    "Omega cannot modify or inspect protected Windows locations.",
                )
        return ProtectedResourceResult(False)

    @staticmethod
    def _unsafe_user_path(value: str) -> ProtectedResourceResult | None:
        raw = value.strip()
        if raw.startswith(("~", "$")) or "%" in raw:
            return ProtectedResourceResult(
                True,
                "PATH_EXPANSION_REJECTED",
                "Omega does not expand environment variables or home shortcuts.",
                "SAFETY-FILE-PATH-001",
            )
        if raw.startswith(("\\\\", "//", "\\\\?\\", "\\\\.\\")):
            return ProtectedResourceResult(
                True,
                "SPECIAL_PATH_REJECTED",
                "Omega accepts only approved local user locations.",
                "SAFETY-ABSOLUTE-PATH-001",
            )
        parsed = PureWindowsPath(raw)
        if parsed.is_absolute() or parsed.drive or parsed.root:
            return ProtectedResourceResult(
                True,
                "ABSOLUTE_PATH_REJECTED",
                "Omega accepts only approved logical user locations.",
                "SAFETY-ABSOLUTE-PATH-001",
            )
        if any(part in {".", ".."} for part in parsed.parts):
            return ProtectedResourceResult(
                True,
                "PATH_TRAVERSAL_REJECTED",
                "Omega cannot perform that operation because it leaves the "
                "approved user location.",
                "SAFETY-FILE-PATH-001",
            )
        if ":" in raw:
            return ProtectedResourceResult(
                True,
                "ALTERNATE_STREAM_REJECTED",
                "Omega does not use alternate data streams.",
                "SAFETY-FILE-PATH-001",
            )
        return None

    @staticmethod
    def _within(candidate: Path, root: Path) -> bool:
        try:
            return os.path.commonpath(
                (os.path.normcase(candidate), os.path.normcase(root))
            ) == os.path.normcase(root)
        except ValueError:
            return False

    @staticmethod
    def _linked(path: Path) -> bool:
        current = path
        while True:
            try:
                if current.exists() and (
                    current.is_symlink()
                    or bool(getattr(current, "is_junction", lambda: False)())
                ):
                    return True
            except OSError:
                return True
            if current == current.parent:
                return False
            current = current.parent
