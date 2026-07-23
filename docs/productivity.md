# Local productivity

Phase 16 adds local notes, task lists, and tasks. Notes support bounded title
and body text, pinning, archive/restore, tags, search, revision-safe editing,
and confirmed deletion. Tasks support pending, in-progress, completed, and
cancelled states; separate archive state; none/low/medium/high/urgent priority;
aware UTC deadlines; list moves; tags; bounded due and overdue views; reopening;
and confirmed deletion.

## Persistence and reminders

Migration 7 creates `notes`, `task_lists`, `tasks`, `tags`, `note_tags`,
`task_tags`, and `task_reminder_links`. Repository construction has no schema or
filesystem side effects. Connections follow Omega's existing foreign-key,
timeout, journal, and transaction policy.

Reminder links reference Phase 15 `scheduled_items` UUIDs. The linked schedule
must exist and be a reminder; cancelled reminders cannot be newly linked.
Completing a task preserves reminder history. Task text never becomes a
scheduled command, and automatic deadline reminder creation remains disabled.

## Import and export

Version 1 JSON import accepts only bounded UTF-8 objects under the approved
productivity import directory. It validates item counts and text before a
single transaction. Conflicts roll back the bundle. Pickle, Python, scripts,
database dumps, arbitrary YAML, Markdown import, absolute paths, traversal, and
arbitrary object deserialization are unsupported.

JSON and Markdown exports are deterministic, UTF-8, bounded, and confined to
the approved export directory. Existing files are not replaced unless an
explicit caller uses the safe overwrite option. Markdown uses plain text/code
fences, emits no raw database dump, and is never rendered as executable HTML.

## Interfaces and safety

Terminal and offline voice commands use `OmegaSession`; GUI shortcuts use
`GuiController`. All reach the same parser and `ProductivityActionDispatcher`,
which submits through `SafeExecutionGateway`. Destructive mutations require an
exact session/action/item/revision-scoped confirmation. A stale revision
invalidates the operation.

Omega does not execute note bodies, task descriptions, code blocks, links,
HTML, scripts, macros, or reminder text. It does not synchronize to cloud
services, collaborate with other accounts, store attachments, or trigger
arbitrary automation when a task becomes due.
