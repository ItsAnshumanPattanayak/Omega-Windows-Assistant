"""SQLite persistence for typed Omega commands."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from omega.core.exceptions import DatabaseError
from omega.database.connection import DatabaseConnectionFactory
from omega.models import UserCommand

_INSERT_COMMAND = """
INSERT INTO commands (
    command_id,
    original_text,
    normalized_text,
    intent,
    entities_json,
    confidence,
    received_at,
    source,
    session_id,
    metadata_json,
    created_at
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_SELECT_COMMAND = """
SELECT
    command_id,
    original_text,
    normalized_text,
    intent,
    entities_json,
    confidence,
    received_at,
    source,
    session_id,
    metadata_json
FROM commands
WHERE command_id = ?
"""

_SELECT_RECENT_COMMANDS = """
SELECT
    command_id,
    original_text,
    normalized_text,
    intent,
    entities_json,
    confidence,
    received_at,
    source,
    session_id,
    metadata_json
FROM commands
ORDER BY received_at DESC, command_id DESC
LIMIT ?
"""

_SELECT_SESSION_COMMANDS = """
SELECT
    command_id,
    original_text,
    normalized_text,
    intent,
    entities_json,
    confidence,
    received_at,
    source,
    session_id,
    metadata_json
FROM commands
WHERE session_id = ?
ORDER BY received_at ASC, command_id ASC
LIMIT ?
"""


class CommandRepository:
    """Store and retrieve immutable command-history records."""

    def __init__(
        self,
        connection_factory: DatabaseConnectionFactory,
    ) -> None:
        self.connection_factory = connection_factory

    def add(
        self,
        command: UserCommand,
    ) -> None:
        """Persist one command without replacing existing history."""

        serialized = command.to_dict()

        try:
            entities_json = json.dumps(
                serialized["entities"],
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            metadata_json = json.dumps(
                serialized["metadata"],
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )

            connection = self.connection_factory.connect()

            try:
                with connection:
                    connection.execute(
                        _INSERT_COMMAND,
                        (
                            serialized["command_id"],
                            serialized["original_text"],
                            serialized["normalized_text"],
                            serialized["intent"],
                            entities_json,
                            serialized["confidence"],
                            serialized["received_at"],
                            serialized["source"],
                            serialized["session_id"],
                            metadata_json,
                            serialized["received_at"],
                        ),
                    )
            finally:
                connection.close()
        except sqlite3.IntegrityError as error:
            raise DatabaseError(
                "The command is already present in command history."
            ) from error
        except (sqlite3.Error, TypeError, ValueError) as error:
            raise DatabaseError(
                "Omega could not save the command history record."
            ) from error

    def get(
        self,
        command_id: UUID,
    ) -> UserCommand | None:
        """Return one command by ID."""

        connection = self.connection_factory.connect()

        try:
            row = connection.execute(
                _SELECT_COMMAND,
                (str(command_id),),
            ).fetchone()
        except sqlite3.Error as error:
            raise DatabaseError(
                "Omega could not read the command history record."
            ) from error
        finally:
            connection.close()

        if row is None:
            return None

        return self._deserialize(row)

    def list_recent(
        self,
        *,
        limit: int = 20,
    ) -> list[UserCommand]:
        """Return the newest commands in descending time order."""

        validated_limit = self._validate_limit(limit)
        connection = self.connection_factory.connect()

        try:
            rows = connection.execute(
                _SELECT_RECENT_COMMANDS,
                (validated_limit,),
            ).fetchall()
        except sqlite3.Error as error:
            raise DatabaseError(
                "Omega could not read recent command history."
            ) from error
        finally:
            connection.close()

        return [self._deserialize(row) for row in rows]

    def list_for_session(
        self,
        session_id: UUID,
        *,
        limit: int = 100,
    ) -> list[UserCommand]:
        """Return commands belonging to one session."""

        validated_limit = self._validate_limit(limit)
        connection = self.connection_factory.connect()

        try:
            rows = connection.execute(
                _SELECT_SESSION_COMMANDS,
                (
                    str(session_id),
                    validated_limit,
                ),
            ).fetchall()
        except sqlite3.Error as error:
            raise DatabaseError(
                "Omega could not read session command history."
            ) from error
        finally:
            connection.close()

        return [self._deserialize(row) for row in rows]

    def count(self) -> int:
        """Return the number of stored commands."""

        connection = self.connection_factory.connect()

        try:
            row = connection.execute("SELECT COUNT(*) FROM commands").fetchone()
        except sqlite3.Error as error:
            raise DatabaseError(
                "Omega could not count command-history records."
            ) from error
        finally:
            connection.close()

        if row is None:
            return 0

        return int(row[0])

    @staticmethod
    def _validate_limit(
        limit: int,
    ) -> int:
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 1_000
        ):
            raise ValueError("Command-history limit must be between 1 and 1000.")

        return limit

    @staticmethod
    def _deserialize(
        row: Mapping[str, Any],
    ) -> UserCommand:
        try:
            entities = json.loads(str(row["entities_json"]))
            metadata = json.loads(str(row["metadata_json"]))

            if not isinstance(entities, list):
                raise ValueError("Stored command entities are invalid.")

            if not isinstance(metadata, dict):
                raise ValueError("Stored command metadata is invalid.")

            return UserCommand.from_dict(
                {
                    "command_id": row["command_id"],
                    "original_text": row["original_text"],
                    "normalized_text": row["normalized_text"],
                    "intent": row["intent"],
                    "entities": entities,
                    "confidence": row["confidence"],
                    "received_at": row["received_at"],
                    "source": row["source"],
                    "session_id": row["session_id"],
                    "metadata": metadata,
                }
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            raise DatabaseError(
                "A stored command-history record is invalid."
            ) from error
