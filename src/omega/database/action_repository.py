"""SQLite persistence for Omega actions and action results."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from omega.core.exceptions import DatabaseError
from omega.database.connection import DatabaseConnectionFactory
from omega.database.schema import utc_timestamp
from omega.models import Action, ActionResult

_ACTION_COLUMNS = """
    action_id,
    command_id,
    intent,
    parameters_json,
    risk_level,
    status,
    permission_decision,
    confirmation_status,
    requires_confirmation,
    dependencies_json,
    created_at,
    started_at,
    completed_at,
    metadata_json
"""

_INSERT_ACTION = f"""
INSERT INTO actions (
    {_ACTION_COLUMNS},
    updated_at
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_UPDATE_ACTION = """
UPDATE actions
SET
    command_id = ?,
    intent = ?,
    parameters_json = ?,
    risk_level = ?,
    status = ?,
    permission_decision = ?,
    confirmation_status = ?,
    requires_confirmation = ?,
    dependencies_json = ?,
    created_at = ?,
    started_at = ?,
    completed_at = ?,
    metadata_json = ?,
    updated_at = ?
WHERE action_id = ?
"""

_SELECT_ACTION = f"""
SELECT
    {_ACTION_COLUMNS}
FROM actions
WHERE action_id = ?
"""

_SELECT_COMMAND_ACTIONS = f"""
SELECT
    {_ACTION_COLUMNS}
FROM actions
WHERE command_id = ?
ORDER BY created_at ASC, action_id ASC
LIMIT ?
"""

_SELECT_RECENT_ACTIONS = f"""
SELECT
    {_ACTION_COLUMNS}
FROM actions
ORDER BY created_at DESC, action_id DESC
LIMIT ?
"""

_INSERT_RESULT = """
INSERT INTO action_results (
    action_id,
    success,
    status,
    message,
    user_message,
    data_json,
    error_json,
    started_at,
    completed_at,
    duration_ms,
    metadata_json,
    created_at
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_SELECT_RESULT = """
SELECT
    action_id,
    success,
    status,
    message,
    user_message,
    data_json,
    error_json,
    started_at,
    completed_at,
    duration_ms,
    metadata_json
FROM action_results
WHERE action_id = ?
"""


class ActionRepository:
    """Store and retrieve typed actions and execution results."""

    def __init__(
        self,
        connection_factory: DatabaseConnectionFactory,
    ) -> None:
        self.connection_factory = connection_factory

    def add(
        self,
        action: Action,
    ) -> None:
        """Persist one action without replacing an existing record."""

        values = self._serialize_action(action)
        connection = self.connection_factory.connect()

        try:
            with connection:
                connection.execute(
                    _INSERT_ACTION,
                    (*values, utc_timestamp()),
                )
        except sqlite3.IntegrityError as error:
            raise DatabaseError(
                "The action already exists or its command is unavailable."
            ) from error
        except sqlite3.Error as error:
            raise DatabaseError(
                "Omega could not save the action-history record."
            ) from error
        finally:
            connection.close()

    def update(
        self,
        action: Action,
    ) -> None:
        """Replace the stored lifecycle state of an existing action."""

        values = self._serialize_action(action)
        connection = self.connection_factory.connect()

        try:
            with connection:
                cursor = connection.execute(
                    _UPDATE_ACTION,
                    (
                        values[1],
                        values[2],
                        values[3],
                        values[4],
                        values[5],
                        values[6],
                        values[7],
                        values[8],
                        values[9],
                        values[10],
                        values[11],
                        values[12],
                        values[13],
                        utc_timestamp(),
                        values[0],
                    ),
                )

                if cursor.rowcount != 1:
                    raise DatabaseError("The action-history record does not exist.")
        except sqlite3.IntegrityError as error:
            raise DatabaseError(
                "The updated action references an unavailable command."
            ) from error
        except sqlite3.Error as error:
            raise DatabaseError(
                "Omega could not update the action-history record."
            ) from error
        finally:
            connection.close()

    def get(
        self,
        action_id: UUID,
    ) -> Action | None:
        """Return one action by ID."""

        connection = self.connection_factory.connect()

        try:
            row = connection.execute(
                _SELECT_ACTION,
                (str(action_id),),
            ).fetchone()
        except sqlite3.Error as error:
            raise DatabaseError(
                "Omega could not read the action-history record."
            ) from error
        finally:
            connection.close()

        if row is None:
            return None

        return self._deserialize_action(row)

    def list_for_command(
        self,
        command_id: UUID,
        *,
        limit: int = 100,
    ) -> list[Action]:
        """Return actions belonging to one command."""

        validated_limit = self._validate_limit(limit)
        connection = self.connection_factory.connect()

        try:
            rows = connection.execute(
                _SELECT_COMMAND_ACTIONS,
                (
                    str(command_id),
                    validated_limit,
                ),
            ).fetchall()
        except sqlite3.Error as error:
            raise DatabaseError(
                "Omega could not read command action history."
            ) from error
        finally:
            connection.close()

        return [self._deserialize_action(row) for row in rows]

    def list_recent(
        self,
        *,
        limit: int = 20,
    ) -> list[Action]:
        """Return the newest actions first."""

        validated_limit = self._validate_limit(limit)
        connection = self.connection_factory.connect()

        try:
            rows = connection.execute(
                _SELECT_RECENT_ACTIONS,
                (validated_limit,),
            ).fetchall()
        except sqlite3.Error as error:
            raise DatabaseError(
                "Omega could not read recent action history."
            ) from error
        finally:
            connection.close()

        return [self._deserialize_action(row) for row in rows]

    def save_result(
        self,
        result: ActionResult,
    ) -> None:
        """Persist one immutable execution result for an action."""

        serialized = result.to_dict()

        try:
            data_json = self._encode_json(serialized["data"])
            error_value = serialized["error"]
            error_json = (
                self._encode_json(error_value) if error_value is not None else None
            )
            metadata_json = self._encode_json(serialized["metadata"])
        except (TypeError, ValueError) as error:
            raise DatabaseError("The action result could not be serialized.") from error

        connection = self.connection_factory.connect()

        try:
            with connection:
                connection.execute(
                    _INSERT_RESULT,
                    (
                        serialized["action_id"],
                        int(bool(serialized["success"])),
                        serialized["status"],
                        serialized["message"],
                        serialized["user_message"],
                        data_json,
                        error_json,
                        serialized["started_at"],
                        serialized["completed_at"],
                        serialized["duration_ms"],
                        metadata_json,
                        utc_timestamp(),
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise DatabaseError(
                "The result already exists or its action is unavailable."
            ) from error
        except sqlite3.Error as error:
            raise DatabaseError("Omega could not save the action result.") from error
        finally:
            connection.close()

    def get_result(
        self,
        action_id: UUID,
    ) -> ActionResult | None:
        """Return the stored execution result for an action."""

        connection = self.connection_factory.connect()

        try:
            row = connection.execute(
                _SELECT_RESULT,
                (str(action_id),),
            ).fetchone()
        except sqlite3.Error as error:
            raise DatabaseError("Omega could not read the action result.") from error
        finally:
            connection.close()

        if row is None:
            return None

        return self._deserialize_result(row)

    def count(self) -> int:
        """Return the number of stored actions."""

        connection = self.connection_factory.connect()

        try:
            row = connection.execute("SELECT COUNT(*) FROM actions").fetchone()
        except sqlite3.Error as error:
            raise DatabaseError(
                "Omega could not count action-history records."
            ) from error
        finally:
            connection.close()

        if row is None:
            return 0

        return int(row[0])

    @classmethod
    def _serialize_action(
        cls,
        action: Action,
    ) -> tuple[object, ...]:
        serialized = action.to_dict()

        try:
            return (
                serialized["action_id"],
                serialized["command_id"],
                serialized["intent"],
                cls._encode_json(serialized["parameters"]),
                serialized["risk_level"],
                serialized["status"],
                serialized["permission_decision"],
                serialized["confirmation_status"],
                int(bool(serialized["requires_confirmation"])),
                cls._encode_json(serialized["dependencies"]),
                serialized["created_at"],
                serialized["started_at"],
                serialized["completed_at"],
                cls._encode_json(serialized["metadata"]),
            )
        except (TypeError, ValueError) as error:
            raise DatabaseError("The action could not be serialized.") from error

    @staticmethod
    def _deserialize_action(
        row: Mapping[str, Any],
    ) -> Action:
        try:
            parameters = json.loads(str(row["parameters_json"]))
            dependencies = json.loads(str(row["dependencies_json"]))
            metadata = json.loads(str(row["metadata_json"]))

            if not isinstance(parameters, dict):
                raise ValueError("Stored action parameters are invalid.")

            if not isinstance(dependencies, list):
                raise ValueError("Stored action dependencies are invalid.")

            if not isinstance(metadata, dict):
                raise ValueError("Stored action metadata is invalid.")

            return Action.from_dict(
                {
                    "action_id": row["action_id"],
                    "command_id": row["command_id"],
                    "intent": row["intent"],
                    "parameters": parameters,
                    "risk_level": row["risk_level"],
                    "status": row["status"],
                    "permission_decision": row["permission_decision"],
                    "confirmation_status": row["confirmation_status"],
                    "requires_confirmation": bool(row["requires_confirmation"]),
                    "dependencies": dependencies,
                    "created_at": row["created_at"],
                    "started_at": row["started_at"],
                    "completed_at": row["completed_at"],
                    "metadata": metadata,
                }
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            raise DatabaseError("A stored action-history record is invalid.") from error

    @staticmethod
    def _deserialize_result(
        row: Mapping[str, Any],
    ) -> ActionResult:
        try:
            data = json.loads(str(row["data_json"]))
            metadata = json.loads(str(row["metadata_json"]))
            raw_error = row["error_json"]
            error_data = json.loads(str(raw_error)) if raw_error is not None else None

            if not isinstance(metadata, dict):
                raise ValueError("Stored result metadata is invalid.")

            if error_data is not None and not isinstance(error_data, dict):
                raise ValueError("Stored result error data is invalid.")

            return ActionResult.from_dict(
                {
                    "action_id": row["action_id"],
                    "success": bool(row["success"]),
                    "status": row["status"],
                    "message": row["message"],
                    "user_message": row["user_message"],
                    "data": data,
                    "error": error_data,
                    "started_at": row["started_at"],
                    "completed_at": row["completed_at"],
                    "duration_ms": row["duration_ms"],
                    "metadata": metadata,
                }
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            raise DatabaseError("A stored action-result record is invalid.") from error

    @staticmethod
    def _validate_limit(
        limit: int,
    ) -> int:
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 1_000
        ):
            raise ValueError("Action-history limit must be between 1 and 1000.")

        return limit

    @staticmethod
    def _encode_json(
        value: object,
    ) -> str:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
