"""Bounded filename-only search within one approved logical root."""

from __future__ import annotations

from pathlib import Path

from omega.core.exceptions import FileSearchError
from omega.files.results import FileSearchMatch, ResolvedLocation


class FileSearchService:
    """Search exact names or one safe extension without following directory links."""

    def __init__(self, maximum_depth: int, maximum_results: int) -> None:
        self.maximum_depth = maximum_depth
        self.maximum_results = maximum_results

    def search(
        self,
        location: ResolvedLocation,
        *,
        filename: str | None = None,
        extension: str | None = None,
    ) -> tuple[tuple[FileSearchMatch, ...], bool]:
        """Return bounded relative matches and whether additional matches existed."""
        if (filename is None) == (extension is None):
            raise FileSearchError("Search requires one exact name or one extension.")
        if filename is not None and any(
            character in filename for character in "*?[]\\/"
        ):
            raise FileSearchError("Wildcard and path search is not supported.")
        normalized_extension = None
        if extension is not None:
            normalized_extension = extension.casefold()
            if not normalized_extension.startswith("."):
                normalized_extension = "." + normalized_extension
            if not normalized_extension[1:].isalnum():
                raise FileSearchError("That extension search is not supported.")
        results: list[FileSearchMatch] = []
        truncated = self._walk(
            location,
            location.root,
            0,
            filename.casefold() if filename else None,
            normalized_extension,
            results,
        )
        return tuple(results), truncated

    def _walk(
        self,
        location: ResolvedLocation,
        directory: Path,
        depth: int,
        filename: str | None,
        extension: str | None,
        results: list[FileSearchMatch],
    ) -> bool:
        try:
            entries = sorted(directory.iterdir(), key=lambda item: item.name.casefold())
        except (OSError, PermissionError):
            return False
        for entry in entries:
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir():
                    if depth < self.maximum_depth and not self._protected_name(
                        entry.name
                    ):
                        if self._walk(
                            location,
                            entry,
                            depth + 1,
                            filename,
                            extension,
                            results,
                        ):
                            return True
                    continue
                if not entry.is_file():
                    continue
            except (OSError, PermissionError):
                continue
            matched = (filename is not None and entry.name.casefold() == filename) or (
                extension is not None and entry.suffix.casefold() == extension
            )
            if matched:
                if len(results) >= self.maximum_results:
                    return True
                relative = entry.relative_to(location.root).as_posix()
                results.append(
                    FileSearchMatch(entry.name, location.logical_name, relative)
                )
        return False

    @staticmethod
    def _protected_name(name: str) -> bool:
        return name.casefold() in {
            ".git",
            "$recycle.bin",
            "system volume information",
            "logs",
            "action_backups",
        }
