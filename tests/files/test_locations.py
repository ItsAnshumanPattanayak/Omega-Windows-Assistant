from pathlib import Path

import pytest

from omega.core.exceptions import FileLocationError
from omega.files import FileLocationResolver


def test_injected_locations_resolve_aliases_without_creating_directories(
    tmp_path: Path,
) -> None:
    desktop = tmp_path / "Desktop"
    documents = tmp_path / "Documents"
    desktop.mkdir()
    documents.mkdir()
    resolver = FileLocationResolver(
        {"desktop": desktop, "documents": documents, "home": tmp_path}
    )

    assert resolver.resolve("my Desktop").root == desktop.resolve()
    assert resolver.resolve("DOCUMENTS").logical_name == "documents"
    assert resolver.resolve("home folder").root == tmp_path.resolve()
    assert resolver.registered_locations == ("desktop", "documents", "home")


def test_current_directory_is_captured_and_unknown_or_missing_locations_fail(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing"
    resolver = FileLocationResolver(
        {"current_directory": tmp_path, "downloads": missing}
    )
    assert resolver.resolve("project directory").root == tmp_path.resolve()
    assert not missing.exists()
    with pytest.raises(FileLocationError, match="unavailable"):
        resolver.resolve("downloads")
    with pytest.raises(FileLocationError, match="not approved"):
        resolver.resolve("system32")


def test_default_resolver_uses_profile_independent_paths(tmp_path: Path) -> None:
    resolver = FileLocationResolver(startup_directory=tmp_path)
    assert resolver.resolve("current directory").root == tmp_path.resolve()
    assert "Anshuman" not in str(resolver._roots)  # noqa: SLF001
