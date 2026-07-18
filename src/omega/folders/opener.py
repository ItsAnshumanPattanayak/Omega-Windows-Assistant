"""Isolated Windows File Explorer opening for validated directories."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable

from omega.core.exceptions import FolderOpenError
from omega.folders.results import ValidatedFolderPath
from omega.folders.validator import is_link_or_reparse


class WindowsFolderOpener:
    """Submit one validated real directory to the Windows opening API."""

    def __init__(self, startfile: Callable[[str], object] | None = None) -> None:
        self._startfile = startfile or getattr(os, "startfile", None)

    def open(self, target: ValidatedFolderPath) -> None:
        if (
            not target.path.exists()
            or not target.path.is_dir()
            or is_link_or_reparse(target.path)
        ):
            raise FolderOpenError("The requested folder was not found.")
        if sys.platform != "win32":
            raise FolderOpenError("Opening folders is supported only on Windows.")
        if self._startfile is None:
            raise FolderOpenError("The Windows folder-opening API is unavailable.")
        try:
            self._startfile(str(target.path.resolve()))
        except OSError as error:
            raise FolderOpenError("The folder could not be opened.") from error
