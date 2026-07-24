"""Parameterized SQLite persistence for collections, documents, and chunks."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from omega.database import DatabaseConnectionFactory
from omega.knowledge.enums import (
    ExtractionStatus,
    KnowledgeDocumentStatus,
    KnowledgeIndexStatus,
    KnowledgeSourceType,
)
from omega.knowledge.exceptions import (
    DocumentNotFoundError,
    KnowledgeCollectionNotFoundError,
    KnowledgeConflictError,
    KnowledgeError,
    StaleKnowledgeRevisionError,
)
from omega.knowledge.models import (
    KnowledgeChunk,
    KnowledgeCollection,
    KnowledgeDocument,
)

_SEARCH_STOPWORDS = frozenset(
    {
        "and",
        "are",
        "for",
        "from",
        "how",
        "into",
        "is",
        "of",
        "or",
        "that",
        "the",
        "this",
        "to",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "with",
    }
)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _timestamp(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value).astimezone(UTC) if value else None


def _like(value: str) -> str:
    return (
        "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    )


class KnowledgeRepository:
    """Persist knowledge records without implicit schema or filesystem creation."""

    def __init__(self, factory: DatabaseConnectionFactory) -> None:
        self.factory = factory

    def add_collection(self, item: KnowledgeCollection) -> KnowledgeCollection:
        self._execute(
            """
            INSERT INTO knowledge_collections (
              collection_id,name,description,is_archived,created_at,updated_at,
              archived_at,metadata_json,revision
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            self._collection_values(item),
        )
        return item

    def get_collection(self, collection_id: UUID) -> KnowledgeCollection | None:
        row = self._one(
            "SELECT * FROM knowledge_collections WHERE collection_id=?",
            (str(collection_id),),
        )
        return self._collection(row) if row else None

    def resolve_collection(
        self, reference: str, *, include_archived: bool = False
    ) -> KnowledgeCollection:
        clauses = ["(collection_id=? OR lower(name)=lower(?))"]
        if not include_archived:
            clauses.append("is_archived=0")
        rows = self._all(
            "SELECT * FROM knowledge_collections WHERE "
            + " AND ".join(clauses)
            + " ORDER BY lower(name),collection_id",
            (reference.strip(), reference.strip()),
        )
        if len(rows) != 1:
            raise KnowledgeCollectionNotFoundError(
                "No collection matched that reference."
                if not rows
                else "More than one collection matched that reference."
            )
        return self._collection(rows[0])

    def list_collections(
        self, *, include_archived: bool = False
    ) -> tuple[KnowledgeCollection, ...]:
        rows = self._all(
            "SELECT * FROM knowledge_collections "
            + ("" if include_archived else "WHERE is_archived=0 ")
            + "ORDER BY lower(name),collection_id"
        )
        return tuple(self._collection(row) for row in rows)

    def update_collection(
        self, item: KnowledgeCollection, expected_revision: int
    ) -> KnowledgeCollection:
        values = self._collection_values(item)
        count = self._execute(
            """
            UPDATE knowledge_collections SET name=?,description=?,is_archived=?,
              created_at=?,updated_at=?,archived_at=?,metadata_json=?,revision=?
            WHERE collection_id=? AND revision=?
            """,
            (*values[1:], values[0], expected_revision),
        )
        if count != 1:
            raise StaleKnowledgeRevisionError(
                "The collection changed before this update."
            )
        return item

    def delete_collection(
        self, collection_id: UUID, expected_revision: int, *, include_documents: bool
    ) -> int:
        connection = self.factory.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM knowledge_documents "
                    "WHERE collection_id=? AND status!='removed'",
                    (str(collection_id),),
                ).fetchone()[0]
            )
            if count and not include_documents:
                raise KnowledgeConflictError("The collection is not empty.")
            if count:
                connection.execute(
                    "DELETE FROM knowledge_chunks WHERE document_id IN "
                    "(SELECT document_id FROM knowledge_documents "
                    "WHERE collection_id=?)",
                    (str(collection_id),),
                )
                connection.execute(
                    "DELETE FROM knowledge_documents WHERE collection_id=?",
                    (str(collection_id),),
                )
            cursor = connection.execute(
                "DELETE FROM knowledge_collections "
                "WHERE collection_id=? AND revision=?",
                (str(collection_id), expected_revision),
            )
            if cursor.rowcount != 1:
                raise StaleKnowledgeRevisionError(
                    "The collection changed before deletion."
                )
            connection.commit()
            return count
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    def add_document_with_chunks(
        self, document: KnowledgeDocument, chunks: tuple[KnowledgeChunk, ...]
    ) -> KnowledgeDocument:
        if any(chunk.document_id != document.document_id for chunk in chunks):
            raise KnowledgeError("Every chunk must belong to the imported document.")
        if [chunk.sequence_number for chunk in chunks] != list(range(len(chunks))):
            raise KnowledgeError("Chunk sequence must be contiguous.")
        connection = self.factory.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO knowledge_documents (
                  document_id,collection_id,title,original_filename,source_path,
                  source_type,file_size_bytes,content_fingerprint,status,
                  extraction_status,index_status,character_count,page_count,
                  imported_at,updated_at,last_indexed_at,removed_at,metadata_json,revision
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                self._document_values(document),
            )
            connection.executemany(
                """
                INSERT INTO knowledge_chunks (
                  chunk_id,document_id,sequence_number,text,text_hash,character_start,
                  character_end,page_number,section_title,token_estimate,created_at,
                  metadata_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                [self._chunk_values(chunk) for chunk in chunks],
            )
            connection.commit()
            return document
        except sqlite3.IntegrityError as error:
            if connection.in_transaction:
                connection.rollback()
            raise KnowledgeConflictError(
                "The document conflicts with existing knowledge data."
            ) from error
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    def get_document(
        self, document_id: UUID, *, include_removed: bool = False
    ) -> KnowledgeDocument | None:
        row = self._one(
            "SELECT * FROM knowledge_documents WHERE document_id=?"
            + ("" if include_removed else " AND status!='removed'"),
            (str(document_id),),
        )
        return self._document(row) if row else None

    def resolve_document(
        self, reference: str, *, include_removed: bool = False
    ) -> KnowledgeDocument:
        rows = self._all(
            "SELECT * FROM knowledge_documents WHERE "
            "(document_id=? OR lower(title)=lower(?) OR "
            "lower(original_filename)=lower(?))"
            + ("" if include_removed else " AND status!='removed'")
            + " ORDER BY updated_at DESC,document_id",
            (reference.strip(), reference.strip(), reference.strip()),
        )
        if len(rows) != 1:
            raise DocumentNotFoundError(
                "No document matched that reference."
                if not rows
                else "More than one document matched; use its exact ID."
            )
        return self._document(rows[0])

    def find_by_fingerprint(self, fingerprint: str) -> KnowledgeDocument | None:
        row = self._one(
            "SELECT * FROM knowledge_documents "
            "WHERE content_fingerprint=? AND status!='removed' "
            "ORDER BY imported_at,document_id LIMIT 1",
            (fingerprint,),
        )
        return self._document(row) if row else None

    def list_documents(
        self,
        *,
        collection_id: UUID | None = None,
        include_archived: bool = False,
        limit: int = 100,
    ) -> tuple[KnowledgeDocument, ...]:
        clauses = ["status!='removed'"]
        values: list[object] = []
        if not include_archived:
            clauses.append("status='active'")
        if collection_id is not None:
            clauses.append("collection_id=?")
            values.append(str(collection_id))
        values.append(limit)
        rows = self._all(
            "SELECT * FROM knowledge_documents WHERE "
            + " AND ".join(clauses)
            + " ORDER BY lower(title),document_id LIMIT ?",
            tuple(values),
        )
        return tuple(self._document(row) for row in rows)

    def update_document(
        self, item: KnowledgeDocument, expected_revision: int
    ) -> KnowledgeDocument:
        values = self._document_values(item)
        count = self._execute(
            """
            UPDATE knowledge_documents SET collection_id=?,title=?,original_filename=?,
              source_path=?,source_type=?,file_size_bytes=?,content_fingerprint=?,
              status=?,extraction_status=?,index_status=?,character_count=?,page_count=?,
              imported_at=?,updated_at=?,last_indexed_at=?,removed_at=?,metadata_json=?,
              revision=? WHERE document_id=? AND revision=?
            """,
            (*values[1:], values[0], expected_revision),
        )
        if count != 1:
            raise StaleKnowledgeRevisionError(
                "The document changed before this update."
            )
        return item

    def replace_document_and_chunks(
        self,
        item: KnowledgeDocument,
        expected_revision: int,
        chunks: tuple[KnowledgeChunk, ...],
    ) -> KnowledgeDocument:
        connection = self.factory.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            values = self._document_values(item)
            cursor = connection.execute(
                """
                UPDATE knowledge_documents SET collection_id=?,title=?,
                  original_filename=?,source_path=?,source_type=?,file_size_bytes=?,
                  content_fingerprint=?,status=?,extraction_status=?,index_status=?,
                  character_count=?,page_count=?,imported_at=?,updated_at=?,
                  last_indexed_at=?,removed_at=?,metadata_json=?,revision=?
                WHERE document_id=? AND revision=?
                """,
                (*values[1:], values[0], expected_revision),
            )
            if cursor.rowcount != 1:
                raise StaleKnowledgeRevisionError(
                    "The document changed before re-indexing."
                )
            connection.execute(
                "DELETE FROM knowledge_chunks WHERE document_id=?",
                (str(item.document_id),),
            )
            connection.executemany(
                """
                INSERT INTO knowledge_chunks (
                  chunk_id,document_id,sequence_number,text,text_hash,character_start,
                  character_end,page_number,section_title,token_estimate,created_at,
                  metadata_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                [self._chunk_values(chunk) for chunk in chunks],
            )
            connection.commit()
            return item
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    def chunks_for_document(self, document_id: UUID) -> tuple[KnowledgeChunk, ...]:
        rows = self._all(
            "SELECT * FROM knowledge_chunks WHERE document_id=? "
            "ORDER BY sequence_number",
            (str(document_id),),
        )
        return tuple(self._chunk(row) for row in rows)

    def remove_document(self, item: KnowledgeDocument, expected_revision: int) -> int:
        connection = self.factory.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM knowledge_chunks WHERE document_id=?",
                    (str(item.document_id),),
                ).fetchone()[0]
            )
            cursor = connection.execute(
                """
                UPDATE knowledge_documents SET status='removed',removed_at=?,
                  updated_at=?,index_status='failed',revision=?
                WHERE document_id=? AND revision=? AND status!='removed'
                """,
                (
                    item.removed_at.isoformat() if item.removed_at else None,
                    item.updated_at.isoformat(),
                    item.revision,
                    str(item.document_id),
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise StaleKnowledgeRevisionError(
                    "The document changed before removal."
                )
            connection.execute(
                "DELETE FROM knowledge_chunks WHERE document_id=?",
                (str(item.document_id),),
            )
            connection.commit()
            return count
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    def keyword_candidates(
        self,
        text: str,
        *,
        collection_id: UUID | None,
        document_id: UUID | None,
        source_type: KnowledgeSourceType | None,
        limit: int,
    ) -> list[sqlite3.Row]:
        clauses = ["d.status='active'", "c.is_archived=0"]
        values: list[object] = []
        tokens = tuple(
            dict.fromkeys(
                token.casefold()
                for token in re.findall(r"[\w'-]+", text, re.UNICODE)
                if len(token) > 2 and token.casefold() not in _SEARCH_STOPWORDS
            )
        )[:12]
        terms = (text.strip(), *tokens)
        match_clauses: list[str] = []
        for term in terms:
            pattern = _like(term)
            match_clauses.append(
                "(k.text LIKE ? ESCAPE '\\' OR d.title LIKE ? ESCAPE '\\' "
                "OR d.original_filename LIKE ? ESCAPE '\\')"
            )
            values.extend((pattern, pattern, pattern))
        clauses.append("(" + " OR ".join(match_clauses) + ")")
        if collection_id is not None:
            clauses.append("d.collection_id=?")
            values.append(str(collection_id))
        if document_id is not None:
            clauses.append("d.document_id=?")
            values.append(str(document_id))
        if source_type is not None:
            clauses.append("d.source_type=?")
            values.append(source_type.value)
        values.append(limit)
        return self._all(
            """
            SELECT k.*,d.title AS document_title,d.original_filename,
                   c.name AS collection_name
            FROM knowledge_chunks k
            JOIN knowledge_documents d ON d.document_id=k.document_id
            JOIN knowledge_collections c ON c.collection_id=d.collection_id
            WHERE """
            + " AND ".join(clauses)
            + " ORDER BY d.title,k.sequence_number,k.chunk_id LIMIT ?",
            tuple(values),
        )

    def document_count(self) -> int:
        row = self._one(
            "SELECT COUNT(*) AS count FROM knowledge_documents WHERE status!='removed'",
            (),
        )
        return int(row["count"]) if row else 0

    def collection_count(self) -> int:
        row = self._one("SELECT COUNT(*) AS count FROM knowledge_collections", ())
        return int(row["count"]) if row else 0

    def _one(self, sql: str, values: tuple[object, ...]) -> sqlite3.Row | None:
        connection = self.factory.connect()
        try:
            return cast(sqlite3.Row | None, connection.execute(sql, values).fetchone())
        finally:
            connection.close()

    def _all(self, sql: str, values: tuple[object, ...] = ()) -> list[sqlite3.Row]:
        connection = self.factory.connect()
        try:
            return list(connection.execute(sql, values).fetchall())
        finally:
            connection.close()

    def _execute(self, sql: str, values: tuple[object, ...]) -> int:
        connection = self.factory.connect()
        try:
            cursor = connection.execute(sql, values)
            connection.commit()
            return cursor.rowcount
        except sqlite3.IntegrityError as error:
            connection.rollback()
            raise KnowledgeConflictError(
                "That knowledge record conflicts with existing data."
            ) from error
        finally:
            connection.close()

    @staticmethod
    def _collection_values(item: KnowledgeCollection) -> tuple[object, ...]:
        return (
            str(item.collection_id),
            item.name,
            item.description,
            int(item.is_archived),
            item.created_at.isoformat(),
            item.updated_at.isoformat(),
            item.archived_at.isoformat() if item.archived_at else None,
            _json(item.metadata),
            item.revision,
        )

    @staticmethod
    def _document_values(item: KnowledgeDocument) -> tuple[object, ...]:
        return (
            str(item.document_id),
            str(item.collection_id),
            item.title,
            item.original_filename,
            item.source_path,
            item.source_type.value,
            item.file_size_bytes,
            item.content_fingerprint,
            item.status.value,
            item.extraction_status.value,
            item.index_status.value,
            item.character_count,
            item.page_count,
            item.imported_at.isoformat(),
            item.updated_at.isoformat(),
            item.last_indexed_at.isoformat() if item.last_indexed_at else None,
            item.removed_at.isoformat() if item.removed_at else None,
            _json(item.metadata),
            item.revision,
        )

    @staticmethod
    def _chunk_values(item: KnowledgeChunk) -> tuple[object, ...]:
        return (
            str(item.chunk_id),
            str(item.document_id),
            item.sequence_number,
            item.text,
            item.text_hash,
            item.character_start,
            item.character_end,
            item.page_number,
            item.section_title,
            item.token_estimate,
            item.created_at.isoformat(),
            _json(item.metadata),
        )

    @staticmethod
    def _collection(row: sqlite3.Row) -> KnowledgeCollection:
        return KnowledgeCollection(
            row["name"],
            row["description"],
            UUID(row["collection_id"]),
            bool(row["is_archived"]),
            _timestamp(row["created_at"]) or datetime.now(UTC),
            _timestamp(row["updated_at"]) or datetime.now(UTC),
            _timestamp(row["archived_at"]),
            json.loads(row["metadata_json"]),
            int(row["revision"]),
        )

    @staticmethod
    def _document(row: sqlite3.Row) -> KnowledgeDocument:
        return KnowledgeDocument(
            UUID(row["collection_id"]),
            row["title"],
            row["original_filename"],
            row["source_path"],
            KnowledgeSourceType(row["source_type"]),
            int(row["file_size_bytes"]),
            row["content_fingerprint"],
            int(row["character_count"]),
            UUID(row["document_id"]),
            KnowledgeDocumentStatus(row["status"]),
            ExtractionStatus(row["extraction_status"]),
            KnowledgeIndexStatus(row["index_status"]),
            int(row["page_count"]) if row["page_count"] is not None else None,
            _timestamp(row["imported_at"]) or datetime.now(UTC),
            _timestamp(row["updated_at"]) or datetime.now(UTC),
            _timestamp(row["last_indexed_at"]),
            _timestamp(row["removed_at"]),
            json.loads(row["metadata_json"]),
            int(row["revision"]),
        )

    @staticmethod
    def _chunk(row: sqlite3.Row) -> KnowledgeChunk:
        return KnowledgeChunk(
            UUID(row["document_id"]),
            int(row["sequence_number"]),
            row["text"],
            row["text_hash"],
            int(row["character_start"]),
            int(row["character_end"]),
            UUID(row["chunk_id"]),
            int(row["page_number"]) if row["page_number"] is not None else None,
            row["section_title"],
            int(row["token_estimate"]),
            _timestamp(row["created_at"]) or datetime.now(UTC),
            json.loads(row["metadata_json"]),
        )
