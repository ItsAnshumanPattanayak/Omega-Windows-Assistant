from __future__ import annotations

import pytest

from omega.personalization import (
    FakePreferenceRepository,
    PersonalizationConfiguration,
    PreferenceResolver,
    PreferenceService,
    PreferenceValidator,
)


@pytest.fixture
def configuration() -> PersonalizationConfiguration:
    return PersonalizationConfiguration()


@pytest.fixture
def repository() -> FakePreferenceRepository:
    return FakePreferenceRepository()


@pytest.fixture
def service(
    configuration: PersonalizationConfiguration,
    repository: FakePreferenceRepository,
) -> PreferenceService:
    resolver = PreferenceResolver(repository)
    validator = PreferenceValidator(
        configuration,
        application_aliases=("chrome", "visual studio code", "notepad"),
    )
    return PreferenceService(configuration, repository, validator, resolver)
