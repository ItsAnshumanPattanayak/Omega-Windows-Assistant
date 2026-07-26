"""SQLite persistence for plugin metadata and fingerprint-bound approvals."""

from __future__ import annotations

from datetime import UTC, datetime

from omega.database.connection import DatabaseConnectionFactory
from omega.plugins.models import PluginMetadata, PluginPermission, PluginStatus


class PluginRepository:
    def __init__(self, factory: DatabaseConnectionFactory) -> None:
        self.factory = factory

    def save(self, metadata: PluginMetadata) -> None:
        manifest = metadata.manifest
        with self.factory.connect() as connection:
            connection.execute(
                """INSERT INTO plugin_installations
                   (plugin_id,version,fingerprint,display_name,status,source_path,updated_at)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(plugin_id) DO UPDATE SET
                   version=excluded.version,fingerprint=excluded.fingerprint,
                   display_name=excluded.display_name,status=excluded.status,
                   source_path=excluded.source_path,updated_at=excluded.updated_at""",
                (
                    manifest.plugin_id,
                    str(manifest.version),
                    metadata.fingerprint,
                    manifest.display_name,
                    metadata.status.value,
                    metadata.source_path,
                    datetime.now(UTC).isoformat(),
                ),
            )

    def set_status(self, plugin_id: str, status: PluginStatus) -> None:
        with self.factory.connect() as connection:
            cursor = connection.execute(
                "UPDATE plugin_installations SET status=?,updated_at=? "
                "WHERE plugin_id=?",
                (status.value, datetime.now(UTC).isoformat(), plugin_id),
            )
            if cursor.rowcount != 1:
                raise LookupError("Plugin is not installed.")

    def status(self, plugin_id: str) -> PluginStatus | None:
        with self.factory.connect() as connection:
            row = connection.execute(
                "SELECT status FROM plugin_installations WHERE plugin_id=?",
                (plugin_id,),
            ).fetchone()
        return None if row is None else PluginStatus(str(row[0]))

    def grant_permission(
        self,
        plugin_id: str,
        version: str,
        fingerprint: str,
        permission: PluginPermission,
    ) -> None:
        with self.factory.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO plugin_permissions
                   (plugin_id,version,fingerprint,permission,approved_at)
                   VALUES (?,?,?,?,?)""",
                (
                    plugin_id,
                    version,
                    fingerprint,
                    permission.value,
                    datetime.now(UTC).isoformat(),
                ),
            )

    def revoke_permission(self, plugin_id: str, permission: PluginPermission) -> None:
        with self.factory.connect() as connection:
            connection.execute(
                "DELETE FROM plugin_permissions WHERE plugin_id=? AND permission=?",
                (plugin_id, permission.value),
            )

    def list_permissions(
        self, plugin_id: str, version: str, fingerprint: str
    ) -> tuple[PluginPermission, ...]:
        with self.factory.connect() as connection:
            rows = connection.execute(
                """SELECT permission FROM plugin_permissions
                   WHERE plugin_id=? AND version=? AND fingerprint=?
                   ORDER BY permission""",
                (plugin_id, version, fingerprint),
            ).fetchall()
        return tuple(PluginPermission(str(row[0])) for row in rows)

    def record_failure(self, plugin_id: str, category: str) -> None:
        with self.factory.connect() as connection:
            connection.execute(
                "INSERT INTO plugin_failures(plugin_id,category,occurred_at) "
                "VALUES (?,?,?)",
                (plugin_id, category[:80], datetime.now(UTC).isoformat()),
            )
