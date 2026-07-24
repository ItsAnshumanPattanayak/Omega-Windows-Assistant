"""Strict, local-only configuration for document knowledge."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from omega.knowledge.exceptions import KnowledgeConfigurationError

HARD_SUPPORTED_EXTENSIONS = frozenset({".pdf", ".docx", ".txt", ".md", ".markdown"})


@dataclass(frozen=True)
class KnowledgeConfiguration:
    """Validated limits that cannot enable cloud or executable behavior."""

    enabled: bool = True
    supported_extensions: tuple[str, ...] = tuple(sorted(HARD_SUPPORTED_EXTENSIONS))
    maximum_file_bytes: int = 26_214_400
    maximum_document_characters: int = 2_000_000
    maximum_documents: int = 5_000
    maximum_collections: int = 200
    maximum_collection_name_characters: int = 120
    maximum_document_title_characters: int = 300
    maximum_pages: int = 2_000
    chunk_size_characters: int = 1_500
    chunk_overlap_characters: int = 200
    maximum_chunks_per_document: int = 5_000
    default_search_limit: int = 10
    maximum_search_limit: int = 100
    maximum_query_characters: int = 1_000
    keyword_search_enabled: bool = True
    semantic_search_enabled: bool = False
    semantic_model_name: str | None = None
    semantic_model_path: Path | None = None
    semantic_vector_dimension: int | None = None
    minimum_semantic_score: float = 0.25
    answer_maximum_context_characters: int = 20_000
    extraction_timeout_seconds: int = 30
    indexing_worker_count: int = 2
    allow_duplicate_content: bool = False
    preserve_original_files: bool = True
    copy_documents_into_data_directory: bool = False
    auto_reindex_changed_documents: bool = False

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> KnowledgeConfiguration:
        allowed = set(cls.__dataclass_fields__)
        unknown = set(values).difference(allowed)
        if unknown:
            raise KnowledgeConfigurationError(
                "Unknown knowledge setting(s): " + ", ".join(sorted(unknown))
            )
        defaults = cls()
        merged = {name: values.get(name, getattr(defaults, name)) for name in allowed}
        booleans = {
            "enabled",
            "keyword_search_enabled",
            "semantic_search_enabled",
            "allow_duplicate_content",
            "preserve_original_files",
            "copy_documents_into_data_directory",
            "auto_reindex_changed_documents",
        }
        for name in booleans:
            if not isinstance(merged[name], bool):
                raise KnowledgeConfigurationError(f"knowledge.{name} must be boolean.")
        if not merged["keyword_search_enabled"]:
            raise KnowledgeConfigurationError("Keyword search must remain enabled.")
        integer_limits = {
            "maximum_file_bytes": (1, 100_000_000),
            "maximum_document_characters": (1, 10_000_000),
            "maximum_documents": (1, 100_000),
            "maximum_collections": (1, 10_000),
            "maximum_collection_name_characters": (1, 300),
            "maximum_document_title_characters": (1, 1_000),
            "maximum_pages": (1, 10_000),
            "chunk_size_characters": (100, 20_000),
            "chunk_overlap_characters": (0, 5_000),
            "maximum_chunks_per_document": (1, 20_000),
            "default_search_limit": (1, 100),
            "maximum_search_limit": (1, 1_000),
            "maximum_query_characters": (1, 5_000),
            "answer_maximum_context_characters": (100, 100_000),
            "extraction_timeout_seconds": (1, 300),
            "indexing_worker_count": (1, 8),
        }
        for name, bounds in integer_limits.items():
            value = merged[name]
            if isinstance(value, bool) or not isinstance(value, int):
                raise KnowledgeConfigurationError(f"knowledge.{name} must be integer.")
            if not bounds[0] <= value <= bounds[1]:
                raise KnowledgeConfigurationError(
                    f"knowledge.{name} is outside its safe range."
                )
        if merged["chunk_overlap_characters"] >= merged["chunk_size_characters"]:
            raise KnowledgeConfigurationError(
                "Chunk overlap must be smaller than size."
            )
        if merged["default_search_limit"] > merged["maximum_search_limit"]:
            raise KnowledgeConfigurationError(
                "Default search limit cannot exceed the maximum."
            )
        score = merged["minimum_semantic_score"]
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise KnowledgeConfigurationError(
                "knowledge.minimum_semantic_score must be numeric."
            )
        if not 0.0 <= float(score) <= 1.0:
            raise KnowledgeConfigurationError("Semantic score must be within 0 and 1.")
        merged["minimum_semantic_score"] = float(score)
        extensions = merged["supported_extensions"]
        if not isinstance(extensions, (list, tuple)) or not extensions:
            raise KnowledgeConfigurationError(
                "knowledge.supported_extensions must be a non-empty list."
            )
        normalized: list[str] = []
        for value in extensions:
            if not isinstance(value, str):
                raise KnowledgeConfigurationError("Extensions must be text.")
            item = value.casefold()
            if item not in HARD_SUPPORTED_EXTENSIONS:
                raise KnowledgeConfigurationError(
                    f"Unsupported knowledge extension: {value}."
                )
            if item not in normalized:
                normalized.append(item)
        merged["supported_extensions"] = tuple(normalized)
        for name in ("semantic_model_name", "semantic_model_path"):
            value = merged[name]
            if value is not None and not isinstance(value, (str, Path)):
                raise KnowledgeConfigurationError(f"knowledge.{name} must be text.")
        path = merged["semantic_model_path"]
        merged["semantic_model_path"] = Path(path) if path is not None else None
        dimension = merged["semantic_vector_dimension"]
        if dimension is not None and (
            isinstance(dimension, bool)
            or not isinstance(dimension, int)
            or not 1 <= dimension <= 16_384
        ):
            raise KnowledgeConfigurationError("Semantic vector dimension is invalid.")
        if merged["semantic_search_enabled"] and (
            not merged["semantic_model_name"]
            or merged["semantic_model_path"] is None
            or dimension is None
        ):
            raise KnowledgeConfigurationError(
                "Semantic search requires an explicit local model name, path, "
                "and dimension; Omega never downloads a model."
            )
        if merged["copy_documents_into_data_directory"]:
            raise KnowledgeConfigurationError(
                "Copying source documents is not enabled in Phase 17."
            )
        if merged["auto_reindex_changed_documents"]:
            raise KnowledgeConfigurationError(
                "Automatic filesystem monitoring is not enabled in Phase 17."
            )
        return cls(**merged)
