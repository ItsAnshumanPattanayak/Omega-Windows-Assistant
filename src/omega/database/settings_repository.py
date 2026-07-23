"""Typed JSON-only mutable runtime settings repository."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from omega.core.exceptions import ModelValidationError, SettingsRepositoryError
from omega.database.connection import DatabaseConnectionFactory
from omega.database.schema import utc_timestamp
from omega.models._serialization import (
    JsonValue,
    parse_utc_timestamp,
    validate_json_value,
)

_NAME = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_RESERVED = frozenset(
    {
        "safety.default_decision",
        "safety.allow_administrator_operations",
        "safety.allow_arbitrary_shell_commands",
        "safety.permanent_deletion_enabled",
        "safety.allow_absolute_paths",
        "safety.allow_network_paths",
        "safety.allow_device_paths",
        "safety.allow_destination_replace",
        "safety.allow_folder_merge",
        "safety.allow_cross_volume_destructive_move",
        "database.foreign_keys",
        "recovery.allow_permanent_deletion",
    }
)


@dataclass(frozen=True)
class RuntimeSetting:
    name: str
    value: JsonValue
    created_at: datetime
    updated_at: datetime


class RuntimeSettingsRepository:
    """Store only explicitly mutable JSON-compatible settings."""

    def __init__(self, connection_factory: DatabaseConnectionFactory) -> None:
        self.connection_factory = connection_factory

    def upsert(self, name: str, value: JsonValue) -> RuntimeSetting:
        normalized = self._validate_name(name)
        try:
            validated = validate_json_value(value, "value")
        except ModelValidationError as error:
            raise SettingsRepositoryError(
                "Runtime setting value must be JSON compatible."
            ) from error
        encoded = json.dumps(
            validated, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        now = utc_timestamp()
        connection = self.connection_factory.connect()
        try:
            with connection:
                connection.execute(
                    """
                    INSERT INTO runtime_settings(name,value_json,created_at,updated_at)
                    VALUES (?,?,?,?)
                    ON CONFLICT(name) DO UPDATE SET
                        value_json=excluded.value_json,
                        updated_at=excluded.updated_at
                    """,
                    (normalized, encoded, now, now),
                )
        except sqlite3.Error as error:
            raise SettingsRepositoryError(
                "Omega could not save the runtime setting."
            ) from error
        finally:
            connection.close()
        result = self.get(normalized)
        if result is None:
            raise SettingsRepositoryError("The runtime setting was not saved.")
        return result

    def get(self, name: str) -> RuntimeSetting | None:
        normalized = self._validate_name(name)
        connection = self.connection_factory.connect()
        try:
            row = connection.execute(
                """
                SELECT name,value_json,created_at,updated_at
                FROM runtime_settings WHERE name=?
                """,
                (normalized,),
            ).fetchone()
        except sqlite3.Error as error:
            raise SettingsRepositoryError(
                "Omega could not read the runtime setting."
            ) from error
        finally:
            connection.close()
        return None if row is None else self._deserialize(row)

    def list_all(self) -> tuple[RuntimeSetting, ...]:
        connection = self.connection_factory.connect()
        try:
            rows = connection.execute(
                """
                SELECT name,value_json,created_at,updated_at
                FROM runtime_settings ORDER BY name ASC
                """
            ).fetchall()
        except sqlite3.Error as error:
            raise SettingsRepositoryError(
                "Omega could not list runtime settings."
            ) from error
        finally:
            connection.close()
        return tuple(self._deserialize(row) for row in rows)

    def delete(self, name: str) -> bool:
        normalized = self._validate_name(name)
        connection = self.connection_factory.connect()
        try:
            with connection:
                cursor = connection.execute(
                    "DELETE FROM runtime_settings WHERE name=?", (normalized,)
                )
                return cursor.rowcount == 1
        finally:
            connection.close()

    def clear(self) -> int:
        connection = self.connection_factory.connect()
        try:
            with connection:
                cursor = connection.execute("DELETE FROM runtime_settings")
                return cursor.rowcount
        finally:
            connection.close()

    @staticmethod
    def _validate_name(name: str) -> str:
        if not isinstance(name, str) or _NAME.fullmatch(name) is None:
            raise SettingsRepositoryError("Runtime setting name is invalid.")
        normalized = name.casefold()
        if normalized in _RESERVED or normalized.startswith(
            ("safety.", "database.", "files.allow_", "folders.allow_")
        ):
            raise SettingsRepositoryError(
                "That setting is an immutable safety boundary."
            )
        return normalized

    @staticmethod
    def _deserialize(row: sqlite3.Row) -> RuntimeSetting:
        try:
            value = validate_json_value(json.loads(str(row["value_json"])), "value")
            return RuntimeSetting(
                str(row["name"]),
                value,
                parse_utc_timestamp(row["created_at"], "created_at"),
                parse_utc_timestamp(row["updated_at"], "updated_at"),
            )
        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
            ModelValidationError,
        ) as error:
            raise SettingsRepositoryError(
                "A stored runtime setting is invalid."
            ) from error
