from pathlib import Path

import pytest

from omega.database import (
    DatabaseConfiguration,
    DatabaseConnectionFactory,
    MigrationRunner,
)
from omega.plugins import (
    PluginConfiguration,
    PluginLocalStorage,
    PluginMetadata,
    PluginPermission,
    PluginPermissionService,
    PluginRepository,
    PluginStatus,
    PluginValidator,
)
from omega.plugins.exceptions import PluginPermissionError, PluginStorageError


def repository(tmp_path: Path) -> tuple[PluginRepository, DatabaseConnectionFactory]:
    factory = DatabaseConnectionFactory(
        DatabaseConfiguration(), database_path=tmp_path / "omega.db"
    )
    assert MigrationRunner(factory).migrate() == 14
    return PluginRepository(factory), factory


def metadata(plugin_directory: Path) -> PluginMetadata:
    validator = PluginValidator(PluginConfiguration())
    root = plugin_directory / "example.readonly"
    return PluginMetadata(
        validator.parse_file(root / "plugin.json"),
        str(root),
        validator.fingerprint(root),
        PluginStatus.DISABLED,
    )


def test_plugin_schema_and_permission_persistence(
    tmp_path: Path, plugin_directory: Path
) -> None:
    repo, factory = repository(tmp_path)
    item = metadata(plugin_directory)
    repo.save(item)
    permissions = PluginPermissionService(repo)
    permissions.grant(
        item.manifest, item.fingerprint, PluginPermission.REGISTER_READ_ONLY_COMMAND
    )
    assert permissions.approved(
        item.manifest.plugin_id, str(item.manifest.version), item.fingerprint
    ) == {PluginPermission.REGISTER_READ_ONLY_COMMAND}
    connection = factory.connect()
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {
            "plugin_installations",
            "plugin_permissions",
            "plugin_failures",
        } <= tables
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        connection.close()


def test_permission_is_declared_revocable_and_fingerprint_bound(
    tmp_path: Path, plugin_directory: Path
) -> None:
    repo, _ = repository(tmp_path)
    item = metadata(plugin_directory)
    repo.save(item)
    service = PluginPermissionService(repo)
    with pytest.raises(PluginPermissionError):
        service.grant(item.manifest, item.fingerprint, PluginPermission.CREATE_NOTE)
    service.grant(
        item.manifest, item.fingerprint, PluginPermission.REGISTER_READ_ONLY_COMMAND
    )
    assert not service.approved(
        item.manifest.plugin_id, str(item.manifest.version), "0" * 64
    )
    service.revoke(item.manifest.plugin_id, PluginPermission.REGISTER_READ_ONLY_COMMAND)
    with pytest.raises(PluginPermissionError):
        service.require(
            item.manifest.plugin_id,
            str(item.manifest.version),
            item.fingerprint,
            PluginPermission.REGISTER_READ_ONLY_COMMAND,
        )


def test_storage_is_json_bounded_and_namespaced(tmp_path: Path) -> None:
    first = PluginLocalStorage(tmp_path, "one", 100)
    second = PluginLocalStorage(tmp_path, "two", 100)
    first.write("state", {"value": 1})
    second.write("state", {"value": 2})
    assert first.read("state") == {"value": 1}
    assert second.read("state") == {"value": 2}
    with pytest.raises(PluginStorageError):
        PluginLocalStorage(tmp_path, "../escape", 100)
    with pytest.raises(PluginStorageError):
        first.write("large", "x" * 200)
