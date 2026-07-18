"""Tests for project path resolution."""

from pathlib import Path
from tempfile import TemporaryDirectory

from omega.utils import paths


def test_project_paths_resolve_from_source_layout() -> None:
    root = paths.project_root()

    assert root.name == "project Omega"
    assert paths.source_root() == root / "src"
    assert paths.config_dir() == root / "config"
    assert paths.data_dir() == root / "data"
    assert paths.log_dir() == root / "data" / "logs"
    assert paths.docs_dir() == root / "docs"


def test_path_imports_do_not_create_unexpected_directories(monkeypatch) -> None:
    with TemporaryDirectory(dir=paths.data_dir()) as temporary_directory:
        temp_path = Path(temporary_directory)
        monkeypatch.setattr(paths, "data_dir", lambda: temp_path / "data")

        assert not (temp_path / "data").exists()
        assert paths.log_dir() == temp_path / "data" / "logs"
        assert not (temp_path / "data").exists()


def test_ensure_runtime_directories_creates_only_runtime_locations(monkeypatch) -> None:
    with TemporaryDirectory(dir=paths.data_dir()) as temporary_directory:
        temp_path = Path(temporary_directory)
        monkeypatch.setattr(paths, "data_dir", lambda: temp_path / "runtime")

        paths.ensure_runtime_directories()

        assert (temp_path / "runtime" / "action_backups").is_dir()
        assert (temp_path / "runtime" / "command_history").is_dir()
        assert (temp_path / "runtime" / "logs").is_dir()
