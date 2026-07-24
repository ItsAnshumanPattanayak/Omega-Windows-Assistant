# Local knowledge base

Phase 17 adds a private, offline document index. Omega imports only a file the
user explicitly names and only when it resides under an approved local root.
It does not scan folders, watch the filesystem, upload content, use telemetry,
or download a model.

## Supported formats and extraction

- PDF (`.pdf`): text extraction with `pypdf`; page numbers are retained.
  Encrypted, malformed, empty, and image-only files fail safely. OCR,
  attachments, links, forms, and embedded JavaScript are not processed.
- DOCX (`.docx`): bounded ZIP/XML paragraph and table-cell text. Macro-enabled
  containers and embedded objects are not executed or unpacked.
- TXT (`.txt`): bounded UTF-8 text with normalized line endings. Binary text is
  rejected.
- Markdown (`.md`, `.markdown`): stored as inert plain text with headings as
  section metadata. HTML, links, and fenced code are never rendered or run.

Validation requires a regular non-symlink file under an approved current,
Desktop, Documents, Downloads, or knowledge-import root. It rejects hidden,
network, device, protected runtime/configuration/database, executable,
oversized, malformed, and recognizable credential/private-key files.

## Collections, indexing, and search

Collections and documents have UUIDs, aware UTC timestamps, metadata, and
optimistic revisions. Migration 8 stores collections, document metadata,
deterministic chunks, and optional numeric semantic-vector metadata. Foreign
keys and indexes cover collection/status, fingerprint, source type, updated
time, chunk order/hash, and semantic model identity.

Chunking prefers paragraph or word boundaries, validates overlap, preserves
page/section metadata, assigns stable UUID5 chunk IDs, and enforces character
and count limits. Imports and re-index replacement use explicit transactions.
Changed source files retain the previous index until extraction and chunking
succeed.

Keyword search is always enabled. It uses escaped parameterized SQL to select a
bounded candidate set, then deterministic phrase/token/title ranking. Results
exclude archived collections and removed documents and include document ID,
title, collection, chunk sequence, page or section when available, and a
bounded preview.

Semantic search is disabled by default. Enabling it requires an explicit local
model name, existing local path, and vector dimension. Phase 17 defines the
adapter protocol but installs no model backend and never downloads a model.
Keyword fallback remains available and is reported clearly.

## Grounded answers and prompt-injection safety

The minimum answer implementation is extractive: it returns only relevant
bounded passages and their source references. When evidence is insufficient,
Omega says so. It does not claim generative RAG.

Text such as “ignore previous instructions,” “run this command,” “delete
files,” URLs, shell snippets, macros, and code blocks remains document content.
Retrieved text cannot call tools, alter policy, enter the parser, become a
voice command, or trigger an action.

## Removal, export, and interfaces

Document removal requires a session/action/document/revision/fingerprint-scoped
confirmation. It removes local chunks and index metadata but preserves the
original source file. Non-empty collection deletion is separately confirmed
and also preserves source files.

JSON and Markdown exports contain bounded collection/document metadata,
optional result previews, and grounded answers. They omit full source paths,
vectors, raw SQLite data, and source-document bodies. Destinations are confined
to the knowledge export directory and are not overwritten or opened
automatically.

Terminal and offline voice requests use `OmegaSession`. GUI shortcuts and the
normal command box use `GuiController` and its bounded background runner, so
widgets never access repositories or extract files directly. All operations
reach `SafeExecutionGateway` through `KnowledgeActionDispatcher`.

## Configuration and troubleshooting

The `knowledge` YAML section controls supported extensions and all file, text,
page, chunk, search, context, timeout, worker, duplicate, and semantic limits.
Unknown keys and unsafe values fail closed. No runtime preference may enable a
new file type, cloud upload, path bypass, executable content, automatic scan,
or model download.

If PDF support is unavailable, install the project dependencies so the pinned
`pypdf` range is present. Image-only PDFs require a future explicit OCR feature.
If semantic search is unavailable, use keyword search; this is the supported
default.

Run focused tests with:

```powershell
python -m pytest -p no:cacheprovider tests/knowledge -v
```
