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

18. **Phase 17 — Next:** to be defined after Phase 16 review.

Later phases may cover local AI-assisted intent suggestions, additional Windows integrations, accessibility, packaging, installer support, and release hardening.
