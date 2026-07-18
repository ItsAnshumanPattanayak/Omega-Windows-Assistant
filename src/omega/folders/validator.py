"""Windows-safe folder names, containment, and link/reparse protection."""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path, PureWindowsPath

from omega.core.exceptions import FolderValidationError
from omega.files.results import ResolvedLocation
from omega.folders.results import ValidatedFolderPath
from omega.utils.paths import project_root

_INVALID_FOLDER_NAME = re.compile(r'[<>:"/\\|?*]|[\x00-\x1f]')
_RESERVED_STEMS = frozenset(
    {"con", "prn", "aux", "nul", "clock$"}
    | {f"com{number}" for number in range(1, 10)}
    | {f"lpt{number}" for number in range(1, 10)}
)


def is_link_or_reparse(path: Path) -> bool:
    """Detect symbolic links and Windows directory junction/reparse points."""
    try:
        if path.is_symlink():
            return True
        junction = getattr(path, "is_junction", None)
        if junction is not None and junction():
            return True
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        return bool(attributes & flag)
    except OSError:
        return False


class WindowsFolderNameValidator:
    """Apply Windows component rules consistently on every supported platform."""

    @staticmethod
    def validate_component(name: str) -> str:
        if not isinstance(name, str) or not name or not name.strip():
            raise FolderValidationError("A folder name is required.")
        if len(name) > 240:
            raise FolderValidationError("That folder name is too long.")
        if name in {".", ".."}:
            raise FolderValidationError("Relative traversal is not supported.")
        if name != name.rstrip() or name.endswith("."):
            raise FolderValidationError(
                "Folder names cannot end with a space or period."
            )
        if _INVALID_FOLDER_NAME.search(name):
            raise FolderValidationError("That folder name contains invalid characters.")
        if name.split(".", 1)[0].casefold() in _RESERVED_STEMS:
            raise FolderValidationError("That folder name is reserved by Windows.")
        return name


class FolderPathValidator:
    """Resolve safe relative directory paths beneath approved logical roots."""

    def __init__(self, protected_paths: tuple[Path, ...] | None = None) -> None:
        selected = (
            self._default_protected_paths()
            if protected_paths is None
            else protected_paths
        )
        self._protected_paths = tuple(path.resolve(strict=False) for path in selected)

    @staticmethod
    def _default_protected_paths() -> tuple[Path, ...]:
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
        system_drive = os.environ.get("SystemDrive")
        if system_drive:
            candidates.extend(
                Path(system_drive) / name
                for name in (
                    "Boot",
                    "Recovery",
                    "System Volume Information",
                    "$Recycle.Bin",
                )
            )
        root = project_root()
        candidates.extend(
            (
                root / ".git",
                root / "config",
                root / "data" / "logs",
                root / "data" / "action_backups",
                root / "data" / "command_history",
                root / "build",
                root / "dist",
                root / ".venv",
                root / "venv",
            )
        )
        return tuple(candidates)

    def require_folder_path(
        self,
        location: ResolvedLocation,
        relative_path: str | None,
        *,
        allow_root: bool = False,
        require_existing: bool = False,
    ) -> ValidatedFolderPath:
        """Return one contained directory target without expanding user text."""
        if relative_path is None or not relative_path.strip():
            if not allow_root:
                raise FolderValidationError("A relative folder path is required.")
            parts: tuple[str, ...] = ()
        else:
            raw = relative_path.strip()
            if raw.startswith("~") or "%" in raw or raw.startswith("$"):
                raise FolderValidationError(
                    "Environment and home expansion are not supported."
                )
            windows_path = PureWindowsPath(raw)
            if windows_path.is_absolute() or windows_path.drive or windows_path.root:
                raise FolderValidationError(
                    "Phase 6 supports approved user locations, not absolute paths."
                )
            parts = windows_path.parts
            if any(part in {".", ".."} for part in parts):
                raise FolderValidationError(
                    "The path cannot leave its approved location."
                )
            for part in parts:
                WindowsFolderNameValidator.validate_component(part)

        root = location.root.resolve(strict=False)
        candidate = location.root.joinpath(*parts)
        self._reject_link_chain(location.root, parts)
        resolved = candidate.resolve(strict=False)
        if not self._contained(resolved, root):
            raise FolderValidationError("The path cannot leave its approved location.")
        if self.is_protected_path(resolved):
            raise FolderValidationError("That folder is protected from operations.")
        if require_existing:
            if not candidate.exists():
                raise FolderValidationError("The requested folder was not found.")
            if is_link_or_reparse(candidate) or not candidate.is_dir():
                raise FolderValidationError("The target must be a real directory.")
        relative = Path(*parts) if parts else Path(".")
        return ValidatedFolderPath(location, relative, candidate)

    def _reject_link_chain(self, root: Path, parts: tuple[str, ...]) -> None:
        current = root
        for part in parts:
            current = current / part
            if (current.exists() or current.is_symlink()) and is_link_or_reparse(
                current
            ):
                raise FolderValidationError(
                    "Symbolic links and junctions are not supported."
                )

    def is_protected_path(self, candidate: Path) -> bool:
        """Report whether the resolved target is within a protected real path."""
        resolved = candidate.resolve(strict=False)
        return any(
            self._contained(resolved, protected) for protected in self._protected_paths
        )

    @staticmethod
    def _contained(candidate: Path, root: Path) -> bool:
        try:
            return os.path.commonpath(
                (os.path.normcase(candidate), os.path.normcase(root))
            ) == os.path.normcase(root)
        except ValueError:
            return False
