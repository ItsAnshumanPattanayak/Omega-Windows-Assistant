"""Windows filename and resolved-path safety validation."""

from __future__ import annotations

import os
import re
from pathlib import Path, PureWindowsPath

from omega.core.exceptions import FilePathValidationError
from omega.files.definitions import BLOCKED_EXTENSIONS, OPEN_EXTENSIONS, TEXT_EXTENSIONS
from omega.files.results import (
    PathValidationOutcome,
    ResolvedLocation,
    ValidatedFilePath,
)
from omega.utils.paths import project_root

_INVALID_FILENAME = re.compile(r'[<>:"/\\|?*]|[\x00-\x1f]')
_RESERVED_STEMS = frozenset(
    {"con", "prn", "aux", "nul", "clock$"}
    | {f"com{number}" for number in range(1, 10)}
    | {f"lpt{number}" for number in range(1, 10)}
)


class WindowsFilenameValidator:
    """Apply deterministic Windows filename and extension policy on every OS."""

    @staticmethod
    def validate_component(name: str) -> str:
        if not isinstance(name, str) or not name or not name.strip():
            raise FilePathValidationError("A file name is required.")
        if len(name) > 240:
            raise FilePathValidationError("That file name is too long.")
        if name != name.rstrip() or name.endswith("."):
            raise FilePathValidationError(
                "File names cannot end with a space or period."
            )
        if _INVALID_FILENAME.search(name):
            raise FilePathValidationError("That file name contains invalid characters.")
        stem = name.split(".", 1)[0].casefold()
        if stem in _RESERVED_STEMS:
            raise FilePathValidationError("That name is reserved by Windows.")
        return name

    @classmethod
    def normalize_text_filename(
        cls,
        name: str,
        requested_extension: str | None = None,
        *,
        default_extension: str | None = None,
    ) -> str:
        """Validate a text/data filename and apply one explicit safe extension."""
        cls.validate_component(name)
        requested = requested_extension.casefold() if requested_extension else None
        if requested is not None and not requested.startswith("."):
            requested = "." + requested
        if requested is not None and requested not in TEXT_EXTENSIONS:
            raise FilePathValidationError(
                "That file type is not supported for text operations."
            )
        suffix = Path(name).suffix.casefold()
        if not suffix:
            selected = requested or default_extension
            if selected:
                name += selected
                suffix = selected
        elif requested is not None and suffix != requested:
            raise FilePathValidationError(
                f"The requested file type conflicts with the {suffix} filename."
            )
        if suffix in BLOCKED_EXTENSIONS:
            raise FilePathValidationError(
                "Omega does not create executable or command-script files."
            )
        if suffix not in TEXT_EXTENSIONS:
            raise FilePathValidationError(
                "That file type is not supported for text operations."
            )
        return name

    @classmethod
    def validate_open_filename(cls, name: str) -> str:
        """Validate an existing document name before default-application opening."""
        cls.validate_component(name)
        suffix = Path(name).suffix.casefold()
        if suffix in BLOCKED_EXTENSIONS or suffix not in OPEN_EXTENSIONS:
            raise FilePathValidationError(
                "Omega does not open executable or unsupported files."
            )
        return name


class FilePathValidator:
    """Build contained paths and reject traversal, links, and protected targets."""

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
            )
        )
        return tuple(candidates)

    def validate(
        self,
        location: ResolvedLocation,
        relative_path: str,
        *,
        expect_file: bool = True,
    ) -> PathValidationOutcome:
        """Return a structured outcome rather than leaking raw path exceptions."""
        try:
            result = self.require_file_path(
                location, relative_path, expect_file=expect_file
            )
        except FilePathValidationError as error:
            return PathValidationOutcome(
                False, code="INVALID_FILE_PATH", message=str(error)
            )
        return PathValidationOutcome(True, validated_path=result)

    def require_file_path(
        self,
        location: ResolvedLocation,
        relative_path: str,
        *,
        expect_file: bool = True,
    ) -> ValidatedFilePath:
        """Return a safe path contained under the supplied approved location."""
        if not isinstance(relative_path, str) or not relative_path.strip():
            raise FilePathValidationError("A relative file path is required.")
        raw = relative_path.strip()
        if raw.startswith("~") or "%" in raw or raw.startswith("$"):
            raise FilePathValidationError(
                "Environment and home expansion are not supported."
            )
        windows_path = PureWindowsPath(raw)
        if windows_path.is_absolute() or windows_path.drive or windows_path.root:
            raise FilePathValidationError(
                "Phase 5 supports approved user locations, not absolute paths."
            )
        parts = windows_path.parts
        if any(part in {".", ".."} for part in parts):
            raise FilePathValidationError(
                "The path cannot leave its approved location."
            )
        if not parts:
            raise FilePathValidationError("A relative file path is required.")
        for directory in parts[:-1]:
            WindowsFilenameValidator.validate_component(directory)
        WindowsFilenameValidator.validate_component(parts[-1])
        root = location.root.resolve(strict=False)
        candidate = root.joinpath(*parts)
        resolved = candidate.resolve(strict=False)
        if not self._contained(resolved, root):
            raise FilePathValidationError(
                "The path cannot leave its approved location."
            )
        existing_parent = candidate.parent
        while not existing_parent.exists() and existing_parent != root:
            existing_parent = existing_parent.parent
        if existing_parent.exists() and not self._contained(
            existing_parent.resolve(), root
        ):
            raise FilePathValidationError("A link leaves the approved location.")
        if candidate.exists() and candidate.is_symlink():
            if not self._contained(candidate.resolve(), root):
                raise FilePathValidationError("A link leaves the approved location.")
        if self._is_protected(resolved):
            raise FilePathValidationError(
                "That path is protected from file operations."
            )
        if expect_file and candidate.exists() and candidate.is_dir():
            raise FilePathValidationError(
                "A file was expected, but that path is a directory."
            )
        relative = Path(*parts)
        return ValidatedFilePath(location, relative, candidate)

    @staticmethod
    def _contained(candidate: Path, root: Path) -> bool:
        try:
            return os.path.commonpath(
                (os.path.normcase(candidate), os.path.normcase(root))
            ) == os.path.normcase(root)
        except ValueError:
            return False

    def _is_protected(self, candidate: Path) -> bool:
        return any(
            self._contained(candidate, protected) for protected in self._protected_paths
        )
