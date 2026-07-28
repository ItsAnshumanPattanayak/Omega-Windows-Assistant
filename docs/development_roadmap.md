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
9. **Phase 8 — Recycle Bin and Undo — Completed:** recoverable file/folder recycling, bounded recovery records, restore orchestration, and undo services.
10. **Phase 9 — SQLite History — Completed:** database foundation plus typed command, action, and result repositories.
11. **Phase 10 — Persistent History Integration — Completed:** persistent recovery and settings, history service, transactional cleanup, JSON export, startup composition, gateway lifecycle persistence, and history commands.
12. **Phase 11 — Desktop GUI — Completed:** optional tkinter/ttk interface, headless controller, bounded workers, exact confirmations, persistent activity, undo visibility, history operations, and safe mutable preferences.
13. **Phase 12 — Voice Interaction and Wake-Word Support — Completed:** optional offline microphone capture, Vosk transcription, exact wake activation, active voice sessions, strict confirmation handling, local SAPI responses, GUI controls, explicit CLI startup, privacy boundaries, and fake-based tests.

14. **Phase 13 — Safe Web Browser Automation — Completed:** optional lazy Playwright adapter, isolated Omega-controlled sessions, centralized HTTPS and network-boundary validation, bounded tabs/page information, allowlisted search, process-local bookmarks, gateway-only dispatch, GUI controls, shared voice/text parsing, privacy-safe results, and fake-backend tests.

15. **Phase 14 — Safe Windows System Controls and Device Information — Completed:** bounded system/process information, allowlisted Settings pages, optional audio and brightness adapters, exact-confirmed power actions, shared parser/voice/GUI/CLI routing, and gateway lifecycle persistence.

16. **Phase 15 — Reminders, Timers, Alarms, and Scheduled Tasks — Completed:** persistent SQLite schedules, atomic occurrence claims and finalization, bounded recurrence, stale-claim/restart recovery, timer lifecycle controls, local GUI/terminal/optional speech notifications, shared text/GUI/voice routing, and explicit scheduler startup/shutdown.

17. **Phase 16 — Notes, To-Do Lists, and Personal Productivity — Completed:**
    revisioned local notes, task lists, tasks, priorities, deadlines, tags,
    bounded search, archive/restore, Phase 15 reminder links, safe JSON import,
    JSON/Markdown export, and shared terminal/GUI/voice gateway routing.

18. **Phase 17 — Local Knowledge Base and Document Search — Completed:**
    explicit approved PDF/DOCX/TXT/Markdown and bounded directory import, safe extraction,
    deterministic chunking, SQLite collections and indexes, bounded keyword
    retrieval, optional local semantic fallback, extractive grounded answers
    with sources, transactional re-indexing, source-preserving removal, safe
    export, and shared terminal/GUI/voice gateway routing.

19. **Phase 18 — Privacy-First Email Assistance — Completed:** bounded
    provider-independent message listing/search/reading, deterministic local
    summaries, reviewable drafts and replies, exact-confirmed send/archive,
    metadata-only attachment handling, SQLite idempotency receipts, and shared
    terminal/GUI/voice safety routing backed by zero-network fake-provider tests.

20. **Phase 19 — Privacy-First Calendar Integration — Completed:** bounded
    provider-independent calendar listing/search/reading, deterministic local
    agenda and availability, timezone-aware event proposals, bounded recurrence
    and reminders, exact-confirmed create/update/delete/invitation responses,
    metadata-only SQLite idempotency receipts, and shared terminal/GUI/voice
    safety routing backed by a zero-network fake provider.

21. **Phase 20 — Privacy-First Clipboard, Screenshot, and Desktop Utilities — Completed:**
    explicit bounded plain-text clipboard operations, opt-in screenshot capture,
    process-local screenshot selection, display metadata, and visible-window
    metadata through shared terminal, GUI, and voice safety routing. Clipboard
    history, background monitoring, OCR, cloud upload, and permanent deletion
    remain unavailable.

22. **Phase 21 — Safe Workflow Automation — Completed:** typed code-free workflow
    definitions, deterministic validation and preview, bounded variables and
    conditions, sequential execution, cancellation and pause state, SQLite
    definition/version and redacted run persistence, shared command/GUI/voice
    routing, and per-step safety boundaries.

23. **Phase 22 — Secure Plugin Architecture — Completed:** bounded JSON manifests,
    manifest-only discovery, safe local ZIP validation and disabled installation,
    fingerprint-bound permissions, versioned compatibility, lazy reviewed loading,
    namespaced extension registration, isolated local storage, lifecycle containment,
    SQLite metadata, and shared command/GUI safety routing.

24. **Phase 23 — Privacy-First Local AI Integration — Completed:** optional
    disabled-by-default local generation and embeddings protocols, explicit model
    registry, lazy bounded resource management, cancellation, structured prompt and
    output validation, citation-checked grounded answers, proposal-only domain
    adapters, fingerprint-bound plugin permission enforcement, shared
    command/GUI/voice routing, privacy-minimized receipts, and deterministic fallback.

25. **Phase 24 — Privacy-First Personalization — Completed:** explicit local
    profiles, allowlisted validated preferences, session overrides, deterministic
    safety-dominant precedence, SQLite migration 14, bounded JSON export/import,
    registered application and folder aliases, narrow workflow/plugin/AI access,
    shared command/GUI/voice routing, and no telemetry, cloud sync, behavioral
    inference, or hidden profiling.

26. **Phase 25 — Accessibility and Multilingual Support — Completed:** bounded
    accessibility preferences, keyboard and focus behavior, textual status output,
    high contrast and font scaling, offline validated translation catalogs, complete
    English fallback, partial Hindi preview, deterministic localized aliases,
    Unicode command defenses, locale-aware formatting, and explicit plugin/AI/voice
    boundaries.

27. **Phase 26 — Comprehensive Security Hardening — Completed:** centralized
    fail-closed invariants, bounded command and JSON validation, credential-safe
    diagnostics and logging, rate limiting, hardened archive inspection, static
    execution-primitive checks, adversarial tests, and cross-domain threat-model
    documentation without adding a new execution path.

28. **Phase 27 — Next:** to be defined after Phase 26 review.

Later phases may cover additional Windows integrations, packaging,
installer support, and release hardening. AI-assisted intent fallback remains disabled
unless a future reviewed phase enables it under strict schema and confirmation rules.
