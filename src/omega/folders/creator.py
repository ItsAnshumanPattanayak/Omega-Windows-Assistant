"""Non-recursive creation of one validated final directory."""

from __future__ import annotations

from omega.core.exceptions import FolderConflictError, FolderCreationError
from omega.folders.results import ValidatedFolderPath
from omega.folders.validator import is_link_or_reparse


class FolderCreator:
    """Create exactly one directory when its real parent already exists."""

    def create(self, target: ValidatedFolderPath) -> None:
        parent = target.path.parent
        if not parent.exists() or not parent.is_dir() or is_link_or_reparse(parent):
            raise FolderCreationError(
                "I could not create that folder because its parent does not exist."
            )
        if target.path.exists():
            if target.path.is_dir() and not is_link_or_reparse(target.path):
                raise FolderConflictError("That folder already exists.")
            raise FolderConflictError("A file with that name already exists.")
        try:
            target.path.mkdir(parents=False, exist_ok=False)
        except FileExistsError as error:
            raise FolderConflictError("That folder already exists.") from error
        except OSError as error:
            raise FolderCreationError(
                "The folder could not be created safely."
            ) from error
        if not target.path.is_dir() or is_link_or_reparse(target.path):
            raise FolderCreationError("The new folder could not be verified.")
