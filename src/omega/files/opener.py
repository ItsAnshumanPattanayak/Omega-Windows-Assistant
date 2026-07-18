"""Isolated default-application opening for validated safe documents."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable

from omega.core.exceptions import FileOpenError
from omega.files.results import ValidatedFilePath
from omega.files.validator import WindowsFilenameValidator


class WindowsFileOpener:
    """Open one validated document using Windows' registered default application."""

    def __init__(self, startfile: Callable[[str], object] | None = None) -> None:
        self._startfile = startfile or getattr(os, "startfile", None)

    def open(self, target: ValidatedFilePath) -> None:
        """Send a validated absolute path to the isolated Windows API."""
        WindowsFilenameValidator.validate_open_filename(target.path.name)
        if (
            not target.path.exists()
            or target.path.is_symlink()
            or not target.path.is_file()
        ):
            raise FileOpenError("The requested document was not found.")
        if sys.platform != "win32" and self._startfile is None:
            raise FileOpenError("Opening files is supported only on Windows.")
        if self._startfile is None:
            raise FileOpenError("The Windows file-opening API is unavailable.")
        try:
            self._startfile(str(target.path.resolve()))
        except OSError as error:
            raise FileOpenError("The document could not be opened.") from error
