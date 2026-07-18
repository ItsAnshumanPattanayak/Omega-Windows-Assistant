from pathlib import Path

import pytest

from omega.execution import FolderActionDispatcher
from tests.folder_support import build_folder_dispatcher


@pytest.fixture
def logical_roots(tmp_path: Path) -> dict[str, Path]:
    roots = {name: tmp_path / name for name in ("desktop", "documents", "downloads")}
    for root in roots.values():
        root.mkdir()
    return roots


@pytest.fixture
def folder_dispatcher(logical_roots: dict[str, Path]) -> FolderActionDispatcher:
    return build_folder_dispatcher(logical_roots)
