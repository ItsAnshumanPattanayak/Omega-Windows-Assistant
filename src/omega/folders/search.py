"""Exact-name bounded folder search within one approved logical root."""

from __future__ import annotations

import os
from pathlib import Path

from omega.core.exceptions import FolderSearchError
from omega.files.results import ResolvedLocation
from omega.folders.results import FolderSearchMatch
from omega.folders.validator import (
    FolderPathValidator,
    WindowsFolderNameValidator,
    is_link_or_reparse,
)


class FolderSearch:
    """Search exact names without regex, globbing, drive scans, or links."""

    def __init__(self, validator: FolderPathValidator) -> None:
        self.validator = validator

    def search(
        self,
        location: ResolvedLocation,
        name: str,
        *,
        maximum_depth: int,
        maximum_results: int,
    ) -> tuple[tuple[FolderSearchMatch, ...], bool]:
        WindowsFolderNameValidator.validate_component(name)
        if not isinstance(maximum_results, int) or maximum_results <= 0:
            raise FolderSearchError("The folder-search result limit is invalid.")
        results: list[FolderSearchMatch] = []
        truncated = False
        stack: list[tuple[Path, int]] = [(location.root, 0)]
        while stack:
            directory, depth = stack.pop()
            try:
                with os.scandir(directory) as stream:
                    entries = sorted(
                        stream,
                        key=lambda entry: entry.name.casefold(),
                        reverse=True,
                    )
            except OSError:
                continue
            for entry in entries:
                path = Path(entry.path)
                try:
                    if is_link_or_reparse(path) or self.validator.is_protected_path(
                        path
                    ):
                        continue
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                except OSError:
                    continue
                child_depth = depth + 1
                if child_depth > maximum_depth:
                    continue
                if entry.name.casefold() == name.casefold():
                    if len(results) >= maximum_results:
                        truncated = True
                        stack.clear()
                        break
                    results.append(
                        FolderSearchMatch(
                            entry.name,
                            location.logical_name,
                            path.relative_to(location.root).as_posix(),
                        )
                    )
                if child_depth < maximum_depth:
                    stack.append((path, child_depth))
        results.sort(key=lambda match: match.relative_path.casefold())
        return tuple(results), truncated
