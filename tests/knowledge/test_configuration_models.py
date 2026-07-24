from dataclasses import replace
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from omega.core.exceptions import ModelValidationError
from omega.knowledge import (
    KnowledgeChunk,
    KnowledgeCollection,
    KnowledgeConfiguration,
    KnowledgeSearchQuery,
)
from omega.knowledge.exceptions import KnowledgeConfigurationError


def test_configuration_defaults_are_local_and_strict() -> None:
    value = KnowledgeConfiguration.from_mapping({})
    assert value.keyword_search_enabled
    assert not value.semantic_search_enabled
    assert value.supported_extensions == (".docx", ".markdown", ".md", ".pdf", ".txt")
    with pytest.raises(KnowledgeConfigurationError):
        KnowledgeConfiguration.from_mapping({"unknown": True})
    with pytest.raises(KnowledgeConfigurationError):
        KnowledgeConfiguration.from_mapping({"maximum_file_bytes": True})
    with pytest.raises(KnowledgeConfigurationError):
        KnowledgeConfiguration.from_mapping(
            {"chunk_size_characters": 100, "chunk_overlap_characters": 100}
        )
    with pytest.raises(KnowledgeConfigurationError):
        KnowledgeConfiguration.from_mapping({"supported_extensions": [".exe"]})


def test_semantic_search_requires_an_explicit_local_model() -> None:
    with pytest.raises(KnowledgeConfigurationError):
        KnowledgeConfiguration.from_mapping({"semantic_search_enabled": True})
    value = KnowledgeConfiguration.from_mapping(
        {
            "semantic_search_enabled": True,
            "semantic_model_name": "local-test",
            "semantic_model_path": str(Path("local-model")),
            "semantic_vector_dimension": 3,
        }
    )
    assert value.semantic_search_enabled


def test_models_validate_utc_revision_offsets_and_query_bounds() -> None:
    collection = KnowledgeCollection("College Notes")
    assert collection.to_dict()["revision"] == 1
    with pytest.raises(ModelValidationError):
        replace(collection, created_at=datetime.now())
    with pytest.raises(ModelValidationError):
        KnowledgeSearchQuery("")
    with pytest.raises(ModelValidationError):
        KnowledgeSearchQuery("query", limit=101)
    with pytest.raises(ModelValidationError):
        KnowledgeChunk(
            uuid4(),
            0,
            "text",
            "0" * 64,
            10,
            5,
        )
