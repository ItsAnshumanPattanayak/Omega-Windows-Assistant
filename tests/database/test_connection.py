from pathlib import Path

import pytest

from omega.core.exceptions import (
    DatabaseConnectionError,
)
from omega.database import (
    DatabaseConfiguration,
    DatabaseConnectionFactory,
)


def test_connection_factory_creates_and_configures_database(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "database" / "omega.db"
    configuration = DatabaseConfiguration()
    factory = DatabaseConnectionFactory(
        configuration,
        database_path=database_path,
    )

    connection = factory.connect()

    try:
        assert database_path.exists()
        assert connection.row_factory is not None

        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()

        busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()

        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()

        assert foreign_keys is not None
        assert int(foreign_keys[0]) == 1

        assert busy_timeout is not None
        assert int(busy_timeout[0]) == 5_000

        assert journal_mode is not None
        assert str(journal_mode[0]).upper() == "WAL"
    finally:
        connection.close()


def test_connection_factory_rejects_disabled_database(
    tmp_path: Path,
) -> None:
    configuration = DatabaseConfiguration(enabled=False)
    factory = DatabaseConnectionFactory(
        configuration,
        database_path=tmp_path / "omega.db",
    )

    with pytest.raises(
        DatabaseConnectionError,
        match="disabled",
    ):
        factory.connect()


def test_constructing_factory_does_not_create_database(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "database" / "omega.db"

    DatabaseConnectionFactory(
        DatabaseConfiguration(),
        database_path=database_path,
    )

    assert not database_path.exists()
    assert not database_path.parent.exists()
