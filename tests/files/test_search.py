import os
from pathlib import Path

import pytest

from omega.core.exceptions import FileSearchError
from omega.files import FileLocationResolver, FileSearchService


def test_exact_extension_depth_and_result_limits(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    deep = nested / "deep"
    deep.mkdir(parents=True)
    (tmp_path / "Resume.PDF").write_text("", encoding="utf-8")
    (nested / "one.py").write_text("", encoding="utf-8")
    (deep / "two.py").write_text("", encoding="utf-8")
    location = FileLocationResolver({"documents": tmp_path}).resolve("documents")
    search = FileSearchService(1, 1)

    exact, exact_truncated = search.search(location, filename="resume.pdf")
    extensions, extension_truncated = search.search(location, extension="py")

    assert exact[0].relative_path == "Resume.PDF" and not exact_truncated
    assert extensions[0].relative_path == "nested/one.py"
    assert not extension_truncated
    limited, truncated = FileSearchService(5, 1).search(location, extension="py")
    assert len(limited) == 1 and truncated


def test_search_rejects_wildcards_and_skips_symlink_directories(tmp_path: Path) -> None:
    location = FileLocationResolver({"documents": tmp_path}).resolve("documents")
    with pytest.raises(FileSearchError, match="Wildcard"):
        FileSearchService(5, 10).search(location, filename="**")
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir(exist_ok=True)
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    try:
        os.symlink(outside, tmp_path / "linked", target_is_directory=True)
    except OSError:
        pytest.skip("Creating a directory symlink is not permitted on this host.")
    matches, _ = FileSearchService(5, 10).search(location, filename="secret.txt")
    assert matches == ()
