"""Tests for extracted entity records."""

import pytest

from omega.core.exceptions import ModelValidationError
from omega.models import CommandEntity, EntityType


def test_entity_validates_boundaries_and_round_trips() -> None:
    entity = CommandEntity(EntityType.APPLICATION, "chrome", confidence=0.0)
    assert entity.confidence == 0.0
    entity.confidence = 1.0
    entity.start_index, entity.end_index = 0, 6
    restored = CommandEntity.from_dict(entity.to_dict())
    assert restored.to_dict() == entity.to_dict()


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_entity_rejects_invalid_confidence(confidence: float) -> None:
    with pytest.raises(ModelValidationError):
        CommandEntity(EntityType.FILE, "report.txt", confidence=confidence)


def test_entity_validates_indexes_and_independent_metadata() -> None:
    with pytest.raises(ModelValidationError):
        CommandEntity(EntityType.FILE, "x", start_index=4, end_index=3)
    first = CommandEntity(EntityType.FILE, "one")
    second = CommandEntity(EntityType.FILE, "two")
    first.metadata["source"] = "test"
    assert second.metadata == {}
