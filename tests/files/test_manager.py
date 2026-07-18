from collections.abc import Callable, Mapping
from pathlib import Path
from uuid import uuid4

from omega.files import FileManager, FileOperationSettings


def _call_ids() -> tuple:  # type: ignore[type-arg]
    return uuid4(), uuid4()


def test_create_exists_metadata_and_existing_conflict(
    manager_factory: Callable[..., FileManager], logical_roots: Mapping[str, Path]
) -> None:
    manager = manager_factory()
    action_id, command_id = _call_ids()
    created = manager.create_file("author", "desktop", action_id, command_id)
    exists = manager.file_exists("author.txt", "desktop", *_call_ids())
    info = manager.get_file_information("author.txt", "desktop", *_call_ids())
    conflict = manager.create_file("author.txt", "desktop", *_call_ids())

    assert created.success and (logical_roots["desktop"] / "author.txt").exists()
    assert exists.success and exists.data["exists"] is True  # type: ignore[index]
    assert info.success and info.data["relative_path"] == "author.txt"  # type: ignore[index]
    assert not conflict.success and conflict.error.code == "FILE_ALREADY_EXISTS"  # type: ignore[union-attr]


def test_read_write_confirmation_cancel_expiry_and_changed_target(
    manager_factory: Callable[..., FileManager], logical_roots: Mapping[str, Path]
) -> None:
    current = [0.0]
    manager = manager_factory(clock=lambda: current[0])
    path = logical_roots["desktop"] / "notes.txt"
    path.write_text("", encoding="utf-8")
    written = manager.write_text_file("notes.txt", "desktop", "first", *_call_ids())
    pending = manager.write_text_file("notes.txt", "desktop", "second", *_call_ids())
    wrong = manager.confirm_overwrite("other.txt", "desktop", *_call_ids())
    confirmed = manager.confirm_overwrite("notes.txt", "desktop", *_call_ids())

    assert written.success and path.read_text(encoding="utf-8") == "second"
    assert not pending.success and "confirm overwrite" in pending.user_message
    assert not wrong.success
    assert confirmed.success

    manager.write_text_file("notes.txt", "desktop", "third", *_call_ids())
    cancelled = manager.cancel_overwrite("notes.txt", "desktop", *_call_ids())
    assert cancelled.success and path.read_text(encoding="utf-8") == "second"

    manager.write_text_file("notes.txt", "desktop", "third", *_call_ids())
    current[0] = 31
    expired = manager.confirm_overwrite("notes.txt", "desktop", *_call_ids())
    assert not expired.success and expired.error.code.endswith("EXPIRED")  # type: ignore[union-attr]

    current[0] = 0
    manager.write_text_file("notes.txt", "desktop", "third", *_call_ids())
    path.write_text("external change", encoding="utf-8")
    changed = manager.confirm_overwrite("notes.txt", "desktop", *_call_ids())
    assert not changed.success and path.read_text(encoding="utf-8") == "external change"


def test_append_read_rename_copy_move_search_and_open(
    manager_factory: Callable[..., FileManager], logical_roots: Mapping[str, Path]
) -> None:
    opened: list[str] = []
    manager = manager_factory(startfile=lambda path: opened.append(path))
    desktop = logical_roots["desktop"]
    (desktop / "notes.txt").write_text("first", encoding="utf-8")
    assert manager.append_text_file(
        "notes.txt", "desktop", "second", *_call_ids()
    ).success
    read = manager.read_text_file("notes.txt", "desktop", *_call_ids())
    assert read.user_message == "firstsecond"
    assert manager.rename_file(
        "notes.txt", "writer.txt", "desktop", *_call_ids()
    ).success
    assert manager.copy_file("writer.txt", "desktop", "documents", *_call_ids()).success
    assert manager.move_file(
        "writer.txt", "documents", "downloads", *_call_ids()
    ).success
    found = manager.search_files("writer.txt", "downloads", *_call_ids())
    assert found.success and "writer.txt" in found.user_message
    assert manager.open_file("writer.txt", "downloads", *_call_ids()).success
    assert opened and opened[0].endswith("writer.txt")


def test_limits_conflicts_blocked_paths_and_confirmation_clear(
    manager_factory: Callable[..., FileManager], logical_roots: Mapping[str, Path]
) -> None:
    settings = FileOperationSettings(
        maximum_read_size_bytes=3,
        maximum_display_characters=2,
        maximum_write_size_bytes=3,
        maximum_resulting_file_size_bytes=4,
    )
    manager = manager_factory(settings=settings)
    desktop = logical_roots["desktop"]
    documents = logical_roots["documents"]
    (desktop / "large.txt").write_text("large", encoding="utf-8")
    (documents / "large.txt").write_text("existing", encoding="utf-8")
    assert not manager.read_text_file("large.txt", "desktop", *_call_ids()).success
    assert not manager.append_text_file(
        "large.txt", "desktop", "x", *_call_ids()
    ).success
    assert not manager.copy_file(
        "large.txt", "desktop", "documents", *_call_ids()
    ).success
    assert not manager.create_file("bad.exe", "desktop", *_call_ids()).success
    manager.write_text_file("large.txt", "desktop", "new", *_call_ids())
    manager.clear_pending_confirmations()
    assert not manager.confirm_overwrite("large.txt", "desktop", *_call_ids()).success
