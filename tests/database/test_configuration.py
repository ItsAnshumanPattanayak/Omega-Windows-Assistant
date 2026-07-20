from pathlib import Path

import pytest

from omega.core.exceptions import (
    DatabaseConfigurationError,
)
from omega.database import (
    DatabaseConfiguration,
)


def test_database_configuration_defaults_are_safe() -> None:
    configuration = DatabaseConfiguration.from_mapping({})

    assert configuration.enabled
    assert configuration.filename == "omega.db"
    assert configuration.busy_timeout_ms == 5_000
    assert configuration.journal_mode == "WAL"
    assert configuration.synchronous == "NORMAL"
    assert configuration.foreign_keys


def test_database_path_resolution_has_no_side_effect(
    tmp_path: Path,
) -> None:
    database_directory = tmp_path / "database"
    configuration = DatabaseConfiguration()

    resolved = configuration.resolve_path(database_directory)

    assert resolved == (database_directory / "omega.db")
    assert not database_directory.exists()
    assert not resolved.exists()


@pytest.mark.parametrize(
    "values",
    [
        {
            "unknown": True,
        },
        {
            "enabled": "yes",
        },
        {
            "filename": "",
        },
        {
            "filename": "../omega.db",
        },
        {
            "filename": r"C:\omega.db",
        },
        {
            "filename": "omega.txt",
        },
        {
            "busy_timeout_ms": 99,
        },
        {
            "busy_timeout_ms": 60_001,
        },
        {
            "journal_mode": "INVALID",
        },
        {
            "synchronous": "INVALID",
        },
        {
            "foreign_keys": False,
        },
    ],
)
def test_invalid_database_configuration_is_rejected(
    values: dict[str, object],
) -> None:
    with pytest.raises(DatabaseConfigurationError):
        DatabaseConfiguration.from_mapping(values)
