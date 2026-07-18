from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

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


@pytest.fixture
def logical_roots(tmp_path: Path) -> dict[str, Path]:
    roots = {
        name: tmp_path / name
        for name in ("desktop", "documents", "downloads", "current_directory")
    }
    for root in roots.values():
        root.mkdir()
    return roots


@pytest.fixture
def manager_factory(
    logical_roots: Mapping[str, Path],
) -> Callable[..., FileManager]:
    def factory(
        *,
        clock: Callable[[], float] = lambda: 0.0,
        startfile: Callable[[str], object] = lambda path: None,
        settings: FileOperationSettings | None = None,
    ) -> FileManager:
        selected = settings or FileOperationSettings()
        locations = FileLocationResolver(logical_roots)
        paths = SafeFilePathResolver(locations, FilePathValidator(protected_paths=()))
        return FileManager(
            locations,
            paths,
            TextFileReader(
                selected.maximum_read_size_bytes,
                selected.maximum_display_characters,
            ),
            TextFileWriter(
                selected.maximum_write_size_bytes,
                selected.maximum_resulting_file_size_bytes,
            ),
            FileOperationsService(),
            FileSearchService(selected.search_max_depth, selected.search_max_results),
            WindowsFileOpener(startfile),
            settings=selected,
            monotonic_clock=clock,
        )

    return factory
