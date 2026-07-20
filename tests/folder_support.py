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
from tests.recovery_support import build_test_recovery


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
    common_root = next(iter(roots.values())).parent
    recycle_bin_service, recovery_registry = build_test_recovery(common_root)
    manager = FolderManager(
        locations,
        validator,
        FolderCreator(),
        inspector,
        FolderOperations(inspector, validator),
        FolderSearch(validator),
        WindowsFolderOpener(startfile),
        settings=selected,
        recycle_bin_service=recycle_bin_service,
        recovery_registry=recovery_registry,
    )
    return FolderActionDispatcher(manager)
