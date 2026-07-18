from collections.abc import Callable, Mapping
from pathlib import Path

from omega.execution import FolderActionDispatcher
from omega.files import FileLocationResolver
from omega.folders import (
    FolderCreator,
    FolderInspector,
    FolderManager,
    FolderOperations,
    FolderOperationSettings,
    FolderPathValidator,
    FolderSearch,
    WindowsFolderOpener,
)


def build_folder_dispatcher(
    roots: Mapping[str, Path],
    *,
    settings: FolderOperationSettings | None = None,
    startfile: Callable[[str], object] = lambda path: None,
) -> FolderActionDispatcher:
    selected = settings or FolderOperationSettings()
    locations = FileLocationResolver(roots)
    validator = FolderPathValidator(protected_paths=())
    inspector = FolderInspector(validator)
    manager = FolderManager(
        locations,
        validator,
        FolderCreator(),
        inspector,
        FolderOperations(inspector, validator),
        FolderSearch(validator),
        WindowsFolderOpener(startfile),
        settings=selected,
    )
    return FolderActionDispatcher(manager)
