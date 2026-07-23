from pathlib import Path

import pytest

from omega.database import (
    DatabaseConfiguration,
    DatabaseConnectionFactory,
    MigrationRunner,
)
from omega.productivity import ProductivityConfiguration
from omega.productivity.repositories import ProductivityRepository
from omega.productivity.service import ProductivityService


@pytest.fixture
def productivity(tmp_path: Path) -> tuple[ProductivityService, ProductivityRepository]:
    factory = DatabaseConnectionFactory(
        DatabaseConfiguration(), database_path=tmp_path / "omega.db"
    )
    MigrationRunner(factory).migrate()
    repository = ProductivityRepository(factory)
    return ProductivityService(ProductivityConfiguration(), repository), repository
