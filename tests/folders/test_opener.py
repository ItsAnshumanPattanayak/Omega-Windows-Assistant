import sys
from pathlib import Path
from uuid import uuid4

from omega.folders import WindowsFolderOpener
from tests.folder_support import build_folder_dispatcher


def test_only_validated_existing_folder_is_passed_to_opener(
    logical_roots: dict[str, Path], monkeypatch
) -> None:
    opened: list[str] = []
    (logical_roots["desktop"] / "Projects").mkdir()
    dispatcher = build_folder_dispatcher(logical_roots, startfile=opened.append)
    result = dispatcher.manager.open_folder("Projects", "desktop", uuid4())
    assert result.success
    assert opened == [str((logical_roots["desktop"] / "Projects").resolve())]
    missing = dispatcher.manager.open_folder("Missing", "desktop", uuid4())
    assert not missing.success and len(opened) == 1


def test_non_windows_without_api_returns_safe_failure(
    logical_roots: dict[str, Path], monkeypatch
) -> None:
    (logical_roots["desktop"] / "Projects").mkdir()
    monkeypatch.setattr(sys, "platform", "linux")
    dispatcher = build_folder_dispatcher(logical_roots)
    dispatcher.manager.opener = WindowsFolderOpener(None)
    result = dispatcher.manager.open_folder("Projects", "desktop", uuid4())
    assert not result.success


def test_windows_opening_api_failure_is_structured(
    logical_roots: dict[str, Path],
) -> None:
    (logical_roots["desktop"] / "Projects").mkdir()

    def fail(path: str) -> object:
        raise OSError("simulated")

    dispatcher = build_folder_dispatcher(logical_roots, startfile=fail)
    result = dispatcher.manager.open_folder("Projects", "desktop", uuid4())
    assert not result.success and result.error is not None
    assert result.error.code == "FOLDER_OPEN_FAILED"
