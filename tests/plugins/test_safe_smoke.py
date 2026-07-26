import json
import zipfile
from pathlib import Path

from omega.database import (
    DatabaseConfiguration,
    DatabaseConnectionFactory,
    MigrationRunner,
)
from omega.plugins import (
    PluginConfiguration,
    PluginDiscovery,
    PluginLifecycle,
    PluginLoader,
    PluginManager,
    PluginPackageInstaller,
    PluginPermission,
    PluginPermissionService,
    PluginRepository,
    PluginStatus,
    PluginValidator,
)


def test_complete_fake_plugin_lifecycle_has_no_external_side_effects(
    tmp_path: Path, manifest_data: dict[str, object]
) -> None:
    package = tmp_path / "reviewed.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("plugin.json", json.dumps(manifest_data))
        archive.writestr(
            "plugin.py",
            "class Plugin:\n"
            "    def __init__(self, context): self.context = context\n"
            "    def commands(self):\n"
            "        return {'hello': lambda value: {'message': value}}\n"
            "    def shutdown(self): return None\n"
            "def create_plugin(context): return Plugin(context)\n",
        )
    factory = DatabaseConnectionFactory(
        DatabaseConfiguration(), database_path=tmp_path / "omega.db"
    )
    MigrationRunner(factory).migrate()
    config = PluginConfiguration()
    validator = PluginValidator(config)
    installed_root = tmp_path / "installed"
    repository = PluginRepository(factory)
    permissions = PluginPermissionService(repository)
    manager = PluginManager(
        config,
        PluginDiscovery(config, validator, (installed_root,)),
        PluginPackageInstaller(config, validator, installed_root),
        validator,
        repository,
        permissions,
        PluginLifecycle(config, PluginLoader(config, validator)),
    )

    installed = manager.install(package)
    assert installed.status is PluginStatus.DISABLED
    assert (
        permissions.approved(
            installed.manifest.plugin_id,
            str(installed.manifest.version),
            installed.fingerprint,
        )
        == set()
    )
    manager.grant(PluginPermission.REGISTER_READ_ONLY_COMMAND)
    enabled = manager.enable()
    assert enabled.status is PluginStatus.ENABLED
    assert manager.activate().status is PluginStatus.ACTIVE

    assert manager.registry.invoke_command(
        "plugin.example.readonly.hello", "Omega"
    ) == {"message": "Omega"}

    manager.disable()
    manager.remove()
    assert not (installed_root / installed.manifest.plugin_id).exists()
    assert not any(tmp_path.glob("*.network"))
