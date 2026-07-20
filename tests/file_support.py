from collections.abc import Callable, Mapping
from pathlib import Path

from omega.execution import FileActionDispatcher
from omega.files import (
    FileLocationResolver,
    FileManager,
    FileOperationSettings,
    FileOperationsService,
    FilePathValidator,
    FileSearchService,
    SafeFilePathResolver,
    TextFileReader,
    TextFileWriter,
    WindowsFileOpener,
)
from tests.recovery_support import build_test_recovery


def build_file_dispatcher(
    roots: Mapping[str, Path],
    *,
    clock: Callable[[], float] = lambda: 0.0,
    startfile: Callable[[str], object] = lambda path: None,
) -> FileActionDispatcher:
    settings = FileOperationSettings()
    locations = FileLocationResolver(roots)
    common_root = next(iter(roots.values())).parent
    recycle_bin_service, recovery_registry = build_test_recovery(common_root)
    manager = FileManager(
        locations,
        SafeFilePathResolver(locations, FilePathValidator(protected_paths=())),
        TextFileReader(
            settings.maximum_read_size_bytes,
            settings.maximum_display_characters,
        ),
        TextFileWriter(
            settings.maximum_write_size_bytes,
            settings.maximum_resulting_file_size_bytes,
        ),
        FileOperationsService(),
        FileSearchService(settings.search_max_depth, settings.search_max_results),
        WindowsFileOpener(startfile),
        settings=settings,
        recycle_bin_service=recycle_bin_service,
        recovery_registry=recovery_registry,
        monotonic_clock=clock,
    )
    return FileActionDispatcher(manager)
