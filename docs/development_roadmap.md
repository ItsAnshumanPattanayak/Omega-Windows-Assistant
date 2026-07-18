# Omega development roadmap

The approved roadmap is intentionally incremental. Each phase should be designed, tested, and reviewed before the next phase is implemented.

1. **Phase 0 — Project Foundation and Environment Setup — Completed:** package structure, configuration, logging, documentation, and tests.
2. **Phase 1 — Core Command Models — Completed:** typed, serializable command, action, safety, result, and error records.
3. **Phase 2 — Text Command Interface — Completed:** text sessions, greetings, command capture, timeout, and safe shutdown.
4. **Phase 3 — Rule-Based Command Understanding — Completed:** deterministic normalization, intents, entities, aliases, and clarification.
5. **Phase 4 — Windows Application Manager — Completed:** allowlisted discovery, launching, exact process status, guarded close, and structured results.
6. **Phase 5 — Safe File Management System — Completed:** approved logical roots, validated paths, bounded text I/O, conflict-safe file operations, opening, metadata, search, and overwrite confirmation.
7. **Phase 6 — Folder Management System — Completed:** validated folder creation, bounded inspection and search, safe opening, conflict-free rename/copy, and same-volume move.
8. **Phase 7 — Safety, Permissions, and Confirmations — Completed:** centralized risk classification, protected-resource enforcement, default-deny policy evaluation, exact confirmation, replay protection, revalidation, audit records, and the safe execution gateway.
9. **Phase 8 — Recycle Bin and Undo — Next:** support recoverable deletion and action reversal.
10. **Phase 9 — History and SQLite:** persist safe action history and audit data.
11. **Phase 10 — Desktop GUI:** provide a transparent local desktop interface.
12. **Phase 11 — Voice Input and Response:** add wake-word handling, time-based greetings, and spoken interaction.

Later phases may cover local AI-assisted intent suggestions, additional Windows integrations, accessibility, packaging, installer support, and release hardening. None of those capabilities are implemented in Phase 7.
