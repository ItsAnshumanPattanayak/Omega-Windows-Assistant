# Omega architecture

## Present foundation

Phase 0 implements application startup, configuration, paths, logging, exception types, and tests. Phase 1 adds `omega.models`: data-only models with standard-library validation, UUID identifiers, timezone-aware UTC timestamps, and JSON-compatible serialization. The `src/omega` package uses a `src` layout to keep imports explicit and package installation reliable. YAML configuration is read safely from the project-level `config` directory. Runtime logs belong under `data/logs`.

## Commands, actions, and results

`UserCommand` preserves future user input exactly, with an initially unknown intent and any future-extracted `CommandEntity` records. An `Action` is a separate proposal to perform an operation: it records parameters, risk, permission, confirmation, dependencies, and lifecycle state, but contains no executor or platform object. A future executor will return `ActionResult` data.

Python exceptions remain control-flow errors and derive from `OmegaError`; `OmegaErrorDetails` is a safe serializable record for reporting a failure to later layers or persistence. Risk and permission are represented as typed data (`RiskLevel`, `PermissionDecision`, and `PermissionEvaluation`), not by a Phase 1 policy engine. Action lifecycle states are represented by `ActionStatus` and validated for timestamp and confirmation consistency.

Models accept only JSON-compatible payloads. Serialization converts enums to stable values, UUIDs to strings, UTC datetimes to ISO-8601 strings, and nested models recursively. Commands, entities, permission evaluations, results, and error records are treated as immutable records; `Action` remains mutable because later phases will need controlled state transitions.

```text
User input
  ↓
UserCommand
  ↓
Future intent detection
  ↓
Action proposal
  ↓
Future permission evaluation
  ↓
Future executor
  ↓
ActionResult
```

Creating any Phase 1 model cannot execute an operation. Execution is deliberately deferred to later, safety-reviewed phases.

## Text session lifecycle

Phase 2 keeps terminal I/O in `TerminalInterface` and state management in `OmegaSession`. The terminal adapter collects text and displays responses; the session validates transitions, captures active commands as `UserCommand` records, and uses a monotonic timeout clock. Later dispatchers may act only on complete commands while Omega is active; shutdown, interruption, and timeout clear pending confirmations.

```text
Process starts → Omega inactive → “Hello Omega” → time-based greeting → Omega active
→ commands captured as UserCommand models → “Shut down Omega” → safe termination
```

## Deterministic understanding pipeline

```text
Active-session text input
  ↓
Command normalization
  ↓
Built-in command priority check
  ↓
Single-action validation
  ↓
Rule-based intent detection
  ↓
Entity extraction
  ↓
Confidence and completeness checks
  ↓
CommandParseResult
  ↓
Safe user response
```

Phase 3 uses explicitly ordered, typed regular-expression rules because deterministic behavior is auditable and fails closed. `ApplicationAliasRegistry` safely loads stable canonical names from JSON, rejects duplicate aliases, and resolves only whole-word matches. Missing parameters and ambiguous targets are represented in `CommandParseResult` and produce clarification without retaining conversational execution state. Unsupported and dangerous text remains `UNKNOWN`.

The parser only mutates the in-memory `UserCommand` representation; it imports no shell, subprocess, filesystem mutation, or Windows automation APIs. Phase 4 consumes complete application commands through a separately reviewed executor boundary, but Phase 3 itself still cannot launch anything.

## Controlled application execution

```text
Parsed application command
  -> ApplicationActionDispatcher
  -> ApplicationRegistry
  -> WindowsApplicationDiscovery
  -> ApplicationManager
  -> WindowsApplicationLauncher or ApplicationProcessService
  -> ActionResult
  -> OmegaSession response
```

`ApplicationActionDispatcher` accepts only `OPEN_APPLICATION`, `CLOSE_APPLICATION`, and `CHECK_APPLICATION_STATUS`. It rejects unknown, ambiguous, incomplete, multi-action, and non-application commands without calling the manager. It builds a separate `Action` proposal with the original command ID, a new action ID, the canonical application ID, and a provisional risk level.

`ApplicationRegistry` loads immutable `ApplicationDefinition` records from `config/application_aliases.json`. This is also the canonical alias source for Phase 3, so parsing and execution cannot drift between two registries. Definitions validate stable IDs, unique aliases, exact executable and process filenames, controlled candidate paths, allowlisted URIs, enablement, duplicate-instance policy, and close policy. Natural-language text can provide only an alias that resolves to a canonical ID; it can never supply an executable path, URI, PID, or argument.

`WindowsApplicationDiscovery` expands registered environment-based paths, checks explicitly registered filenames, uses `shutil.which` only for registered executables, rejects symbolic links and temporary-directory targets, and supports only the `calculator:` and `ms-settings:` URI allowlist. It caches successful discoveries for the process and never scans drives, user documents, or Downloads.

`WindowsApplicationLauncher` receives a validated discovered target. Filesystem launches call `subprocess.Popen` with a one-item argument sequence and `shell=False`; URI launches use the Windows URI association API only for an allowlisted registered value. User command text never reaches either call. No administrator elevation, PowerShell wrapper, Command Prompt wrapper, or arbitrary argument path exists.

`ApplicationProcessService` exposes data-only `ApplicationProcess` snapshots rather than live psutil objects. It matches case-insensitive executable names exactly, so a name such as `my-chrome.exe` cannot match `chrome.exe`. Definitions may additionally require the running executable to match the discovered trusted path; this is enabled only for applications whose Windows launch target reliably remains the running binary, because modern packaged applications such as Notepad may redirect to a different trusted installation path. Before mutation the service rechecks the PID's exact name and creation time to defend against PID reuse. Access-denied and disappearing processes are handled as structured partial visibility or operation outcomes.

The critical process denylist includes `System`, `Registry`, `smss.exe`, `csrss.exe`, `wininit.exe`, `services.exe`, `lsass.exe`, `svchost.exe`, `winlogon.exe`, `dwm.exe`, and `explorer.exe`. File Explorer can be opened and inspected, but Omega will not terminate `explorer.exe` because it may be the Windows desktop shell. Settings, Task Manager, Command Prompt, and PowerShell are also blocked from closing in Phase 4 because Omega cannot yet uniquely prove ownership of every matching process.

Every graceful application close now requires an exact application-specific confirmation through the central `ConfirmationManager`. The request is held only in memory, expires after the configured timeout, is cleared on session timeout/shutdown/interruption, and cannot authorize a different application. `yes` is never sufficient. File Explorer, Settings, Task Manager, Command Prompt, and PowerShell remain blocked from closing. Force close is denied globally in Phase 7 even if a domain definition is accidentally loosened.

When a normal executable launch yields a PID, `ApplicationManager` records the canonical ID, PID creation time, and action ID in memory. It verifies PID identity before preferring an Omega-owned process for close and drops stale records. URI applications and applications that detach may not expose a reliable launch PID; status can still use exact registered process names, but ownership claims remain conservative.

## Controlled file execution

```text
Parsed file command
  -> FileActionDispatcher
  -> FileLocationResolver
  -> FilePathValidator
  -> FileManager
  -> Reader / Writer / Operations / Search / Opener
  -> post-operation verification
  -> ActionResult
  -> OmegaSession response
```

`FileActionDispatcher` accepts only complete, unambiguous Phase 5 file intents. It extracts canonical entities, creates an `Action` with the original command ID and a provisional risk level, then calls `FileManager`. The parser never imports or calls a file mutation service. Folder intents are ignored, and `DELETE_FILE` returns the Phase 8 Recycle Bin/undo deferral without touching the target.

`FileLocationResolver` maps aliases to approved logical roots: Desktop, Documents, Downloads, Pictures, Music, Videos, Home, and the working directory captured at Omega startup. User-supplied absolute, drive-qualified, UNC, device, alternate-stream, tilde-expansion, and environment-expansion paths are rejected. Desktop is the configured default, and missing parent directories are never created automatically.

`FilePathValidator` parses Windows path components and resolves the candidate and its existing parents before checking containment with path-aware common-path comparison. A string-prefix check is unsafe because sibling paths such as `Documents-old` share characters with `Documents`; resolved path components also expose symbolic-link or junction escapes. Protected Windows locations, repository `.git`, configuration, logs, and action-backup data are independently blocked.

The writer supports UTF-8 text/data extensions with configured content and resulting-size limits. Non-empty replacement is submitted to the central gateway, which keeps pending content only in a private in-memory execution closure and binds confirmation to the exact target fingerprint. Exact confirmation re-resolves and revalidates the target, rejects changed files, and uses a temporary file on the same filesystem plus `os.replace` for atomic replacement. Pending text is never serialized, logged, or persisted and is cleared on cancellation, timeout, shutdown, interruption, or restart. Append writes exactly the quoted content and does not insert a newline.

Rename, copy, and move refuse destination conflicts because Phase 5 has no recovery/undo layer for replacing a different file. Regular-file and symlink checks occur before mutation; copy and move verify sizes and SHA-256 content. Executable/script opening is blocked. `WindowsFileOpener` isolates the `os.startfile` boundary and receives only a validated absolute document path, never arguments or a command string.

Filename search is limited to one logical root, exact case-insensitive names or internally selected extensions, configured recursion depth, and configured result count. It skips inaccessible and linked directories, never searches file contents or whole drives, and returns relative paths. Bounded reads, display truncation, write limits, and search limits prevent uncontrolled memory or terminal use. File contents and pending write text stay out of logs.

## Controlled folder execution

```text
Parsed folder command
  -> FolderActionDispatcher
  -> FileLocationResolver
  -> FolderPathValidator
  -> bounded preflight inspection
  -> FolderManager
  -> Creator / Inspector / Operations / Search / Opener
  -> post-operation verification
  -> ActionResult
  -> OmegaSession response
```

Phase 6 deliberately reuses Phase 5's `FileLocationResolver` and `ResolvedLocation` record. A single canonical mapping for Desktop, Documents, Downloads, Pictures, Music, Videos, Home, and the captured startup directory prevents file and folder operations from disagreeing about an approved root. Folder-specific validation remains separate because directory trees require component-by-component validation, reparse-point checks, bounded traversal, and different conflict semantics.

`FolderPathValidator` accepts only Windows-safe relative components beneath a resolved logical root. It rejects empty or reserved names, traversal, drive-qualified, UNC, device, alternate-stream, environment-expanded, and tilde-expanded paths. Containment uses resolved path components rather than string prefixes. Actual protected Windows and Omega runtime paths are blocked by resolved location, so an unrelated user directory merely named `config` is not rejected.

Creation uses a non-recursive `mkdir`: the immediate parent must already exist and be a real directory. This prevents a short command from silently creating an entire hierarchy. Listing is immediate and deterministically sorted. Metadata and recursive size calculations use configured depth, item, and byte limits and label partial results rather than claiming complete totals.

Recursive copy and move start with a read-only tree preflight. It measures regular files, directories, bytes, maximum depth, root modification time, and immediate item count; rejects inaccessible entries, protected paths, symbolic links, junctions, destination conflicts, self-nesting, and resource-limit violations; then rechecks the source immediately before mutation. Links and junctions are rejected for the entire operation because copying or traversing their targets would undermine logical-root containment.

Copy builds a private operation-created staging tree inside the validated destination parent, verifies regular-file counts, folder counts, and total bytes, and only then renames it to the final non-existing destination. Failure cleanup is confined to that private temporary directory and is not exposed through `DELETE_FOLDER`. Existing destinations are never cleaned, merged, replaced, or automatically renamed.

Same-volume moves use a rename-style operation and verify both endpoints and the bounded tree measurements. Cross-volume destructive movement is refused: Omega offers no source removal until Phase 8 provides recovery and undo. Folder deletion likewise returns the Phase 8 deferral without resolving or mutating the target. Exact-name search stays inside one approved logical root, uses bounded recursion, skips protected/inaccessible entries, and never follows links or scans a whole drive.

`FolderActionDispatcher` accepts only complete, unambiguous folder parse results, preserves command and action IDs, assigns provisional risk data, and submits the action to `SafeExecutionGateway`. Same-volume folder movement requires central exact confirmation before `FolderManager` is called. The parser and session contain no direct directory operation. Inactive sessions cannot reach the dispatcher, and `Shut down Omega` remains a built-in priority command.

## Central safety and permission pipeline

```text
Parsed command
  -> Action proposal
  -> SafeExecutionGateway
  -> RiskClassifier
  -> ProtectedResourceEvaluator
  -> PermissionPolicyEngine
  -> ALLOW / REQUIRE_CONFIRMATION / DENY
  -> immediate resource revalidation
  -> Application / File / Folder dispatcher
  -> domain manager and service
  -> ActionResult
```

Phase 7 makes `SafeExecutionGateway` the single production authority between an active session and all operational dispatchers. Dispatchers still validate domain parameters and build `Action` proposals, but their provisional risk values are not permission. The classifier may increase risk and never silently lowers a more conservative proposal. Every policy has a stable ID and explicit priority; `DENY` overrides `REQUIRE_CONFIRMATION`, which overrides `ALLOW`. If no explicit allow policy applies, the result is deny.

`SafetyContext` combines a command and its action with only the target information needed for evaluation. Resolved absolute paths may exist in memory for canonical containment checks, but serialization retains only logical target descriptions. `SafetyEvaluation` records the authoritative risk, decision, stable reason code, matched policies, and a safe user message. Configuration may disable an action or require more confirmation, but immutable hard boundaries prevent permanent deletion, arbitrary shell/script execution, protected-path modification, critical-process termination, administrator elevation, and destination replacement.

`ConfirmationManager` owns one pending high-risk action per active session. Its commands are exact and scoped, for example `confirm close Chrome`, `confirm overwrite notes.txt on Desktop`, `confirm move notes.txt from Documents to Downloads`, and `confirm move folder Projects from Desktop to Documents`. Comparison is case-insensitive and ignores surrounding whitespace, but generic `yes`, partial targets, added text, different sessions, expired requests, and replay are rejected. A new pending action in the same session cancels the older request. Pending content and executor callbacks remain in private process memory and are never serialized or logged.

Before an approved or confirmed action reaches a manager, the gateway reevaluates policy and compares a bounded resource fingerprint. Files use resolved identity, size, nanosecond modification time, and a bounded hash; folders add immediate item count; applications use the registered application and process identity snapshot. A change, new destination conflict, vanished source, inserted link, or reused process identity cancels execution. The confirmation is consumed before dispatch and the action ID is recorded, preventing duplicate execution.

`SafetyAuditRecord` captures only stable IDs, intent, risk, decision, policy IDs, confirmation state, time, and a redacted logical target. It excludes file contents, replacement text, confirmation secrets, private paths, environment values, process command lines, and stack traces. Phase 7 keeps this audit in memory; durable history remains Phase 9.

## Phase 10 persistence composition

Repository reconciliation verified Phases 0–9 in source and tests. Phase 9C was already committed and migrations 1–3 remain contiguous and unchanged: foundation, command persistence, then action/result persistence. Migration 4 adds `recovery_records`; migration 5 adds `runtime_settings`.

```text
Explicit OmegaApplication initialization
  -> validated YAML and immutable safety settings
  -> one DatabaseConnectionFactory
  -> MigrationRunner (versions 1–5)
  -> CommandRepository / ActionRepository
  -> SQLite recovery store / runtime settings repository
  -> HistoryService
  -> ExecutionPersistence injected into SafeExecutionGateway
  -> session and domain dispatchers
```

Imports and configuration construction create no database. Only explicit application initialization connects and migrates. Failure to initialize required persistence raises `InitializationError`; Omega does not silently continue without its audit boundary.

For every operational proposal, the gateway persists the command and action before execution. It stores the running state immediately before calling a domain executor and stores the final action/result afterward. Pre-execution persistence failure blocks execution. Post-execution persistence failure is reported without retrying the operating-system action.

`HistoryService` composes the existing repositories rather than duplicating their serialization. Reads and combined activity use bounded deterministic limits. Cleanup is one database transaction, preserves active undo records by default, leaves settings and migration records intact, and relies only on foreign-key cascades inside history tables. It never touches user files, folders, the Recycle Bin, or the database file.

History export serializes a versioned, timestamped, redacted UTF-8 JSON document. It is size bounded, uses a single safe `.json` filename beneath Omega's runtime export directory, and refuses overwrite. Runtime settings accept JSON-compatible values only and reject all safety, database-integrity, and destructive-policy names.

## Phase 11 desktop presentation

Phase 11 adds `omega.gui` as an optional presentation layer. Terminal mode remains the default and continues to use the same `OmegaApplication` composition. `omega --gui` explicitly creates one Tk root and one `OmegaMainWindow`; importing GUI modules creates no root, worker, database, directory, or main loop.

```text
Tk widgets
  -> GuiController
  -> OmegaSession.handle_input (exact original text)
  -> parser / dispatchers / SafeExecutionGateway
  -> domain services and persistent lifecycle
  -> safe user response
  -> Tk scheduler callback
```

`OmegaMainWindow` owns only layout, text rendering, dialogs, and widget state. Immutable display models contain no widget references. `GuiController` validates the UI input bound, prevents a second submission while busy, sends each command once through `OmegaSession`, and refreshes bounded activity through `HistoryService`. Toolbar activation, shutdown, history, undo, export, and cleanup are ordinary existing session commands rather than direct service execution.

`GuiTaskRunner` uses a two-worker `ThreadPoolExecutor`. Workers never touch widgets; terminal callbacks are scheduled onto Tk with `after`. Closing the window interrupts the existing session, clears pending confirmations through its normal lifecycle, cancels queued work, and closes the executor without retrying an operation.

Confirmation dialogs display the existing prompt, target, exact confirmation phrase, and cancellation path. Confirm and Cancel submit those exact phrases through the session. Escape, window close, and dismissal never approve. Undo availability comes from active `HistoryService` recovery records; the widget never calls a restore backend. History cleanup and export continue through the Phase 10 dispatcher and gateway.

`GuiPreferencesService` persists only validated `ui.*` JSON values through `RuntimeSettingsRepository`: theme, font size, history limit, auto-scroll, notification preference, and bounded window geometry. Malformed UI preferences fall back independently. Safety, database, path, deletion, administrator, replacement, merge, and confirmation policies remain immutable and are not exposed as mutable controls.

The desktop uses standard-library tkinter/ttk with system, light, and dark styles, keyboard navigation, visible text labels, resizable panes, selectable conversation text, and no external assets. Headless tests cover controller, task runner, formatting, preferences, import safety, and explicit bootstrap without opening a visible window.

## Implemented layered flow

Omega currently composes these reviewed layers:

- **Input layer:** terminal text, tkinter GUI commands, and optional offline voice transcripts.
- **Command-processing layer:** converts supported user intent into typed commands and entities.
- **Safety layer:** implemented in Phase 7; checks permissions, protected paths, confirmations, and action policies before execution.
- **Executor layer:** performs allowlisted application, validated file/folder, history, recovery, and controlled browser operations through separate domain dispatchers.

Command understanding remains separate from execution. An interpreter may recognize a request, but only the implemented safety layer may authorize it and only an approved dispatcher may call a manager. This separation makes behavior testable and prevents a parser or future AI suggestion from becoming an action automatically.

Arbitrary shell execution will be prohibited because it would allow ambiguous natural-language input to become unrestricted operating-system access.

## Session lifecycle

```text
Inactive
  ↓
“Hello Omega”
  ↓
Time-based greeting for Anshuman
  ↓
Active command session
  ↓
Normal commands without repeating “Omega”
  ↓
“Shut down Omega”
  ↓
Safe session termination
```

This lifecycle is implemented for text and optional voice input.

## Phase 12 voice adapter

Voice is an optional input/output adapter, not a command engine. Importing
`omega.voice` creates no device, model, speech engine, database, file, or thread.
Only explicit CLI or GUI actions build the adapters.

```text
sounddevice microphone
        ↓ bounded PCM queue
local Vosk recognizer
        ↓ final typed TranscriptionResult
strict wake/confirmation validation
        ↓ CommandSource.VOICE
OmegaSession.handle_input
        ↓
existing parser → persistence → dispatchers → SafeExecutionGateway
        ↓
safe text response
        ├─ terminal/GUI display
        └─ optional bounded Windows SAPI queue
```

`VoiceService` owns one listener thread, a stop event, a bounded set of recently
processed transcription identifiers, and a typed `VoiceStateMachine`. It accepts
each final recognizer callback at most once. `OmegaSession` serializes all typed
and voice input with one re-entrant lock, so adapters cannot overlap command
processing. Voice components never call a dispatcher, manager, executor, or
confirmation callback directly.

Passive listening recognizes only the configured activation phrase with strict
case/spacing/boundary-punctuation normalization and a minimum confidence. An
optional command remainder is accepted only after an exact wake prefix. Active
transcripts use the normal session lifecycle. The configured voice timeout
deactivates the session and either returns to passive listening or stops,
according to validated configuration.

When the central gateway has a pending confirmation, the voice adapter fails
closed: only a final, exact expected confirmation or cancellation phrase at the
higher confirmation threshold is forwarded. The central manager still owns
session/action/target/fingerprint/expiry validation and single-use consumption.

Microphone buffers are memory-only and bounded. Raw audio is never logged,
written to a file, inserted into SQLite, or uploaded. Vosk model loading,
sounddevice discovery, and SAPI initialization occur only after explicit voice
startup. GUI worker events enter `GuiTaskRunner`’s callback queue before any Tk
widget update. Speaker output uses a single bounded sequential queue and cannot
cause command retry if synthesis fails.

See [voice.md](voice.md) for configuration, dependencies, privacy, and operations.

## Phase 13 browser adapter

Browser automation is an optional execution domain over the existing lifecycle.
It does not parse commands, authorize itself, or expose Playwright objects to
models:

```text
terminal / GUI / voice
        ↓ UserCommand
existing CommandParser
        ↓ typed browser intent and bounded entities
BrowserActionDispatcher
        ↓ Action + SafetyContext
SafeExecutionGateway
        ↓ allow or exact scoped confirmation
BrowserManager
        ↓ validated, lock-serialized request
BrowserBackend protocol
        ├─ PlaywrightBrowserBackend (explicit real session)
        └─ FakeBrowserBackend (offline deterministic tests)
        ↓
ActionResult → existing SQLite lifecycle persistence
```

`BrowserConfiguration` rejects unknown keys, loose types, unsupported browsers
or search engines, unsafe ranges, dangerous schemes, and attempts to enable
credentials, files, scripts, downloads, forms, sensitive input, or private
mode. HTTPS is the default. HTTP, localhost, and private networks are disabled
unless trusted YAML explicitly permits the first two configurable boundaries;
permanent prohibitions cannot be loosened through settings.

`UrlValidator` uses standard URL and IP parsing, IDNA host canonicalization,
strict host labels, length/control/backslash checks, and explicit local,
loopback, private, link-local, unspecified, reserved, multicast, and metadata
endpoint rejection. It returns a canonical navigation URL plus a query- and
fragment-free audit URL. The Playwright adapter validates every routed request
before continuing it; the manager validates the reported final URL again so an
unsafe redirect fails closed.

`BrowserManager` owns a single bounded state machine and serializes operations
with a re-entrant lock. Stable UUID tab IDs replace backend references.
Maximum tabs, timeouts, title length, visible-text length, query length, and
bookmark names are bounded. It performs no automatic retry. A crash,
disconnect, timeout, missing backend, externally closed tab, or invalid URL
returns one safe structured failure. Shutdown closes only Omega's context and
browser instance, never unrelated Edge, Chrome, or Firefox processes.

Playwright is imported only inside explicit backend startup and creates one
isolated non-persistent context with downloads and service workers disabled.
Importing `omega.browser`, loading settings, or constructing the application
does not start Playwright, a process, worker, network request, profile, or
download. The optional package and browser binary have separate explicit
installation steps.

Browser intents share the Phase 3 parser for text, GUI, and voice. Navigation,
search, tabs, history movement, page information, visible-text matching, and
Omega-managed bookmarks become ordinary actions. Closing the browser and
saving a bookmark require exact confirmation scoped to the command, action,
session, browser target, expiry, and fingerprint. The gateway remains the only
production execution path and persists each proposal/result once.

Page records contain only validated/redacted URLs, bounded visible text, bounded
titles, load state, tab ID, and match count. They contain no raw HTML, cookies,
storage, headers, password values, or backend objects. Search result persistence
omits titles and page text because they commonly repeat the query. Action
parameters store query/text lengths rather than content. Bookmarks are
process-local Omega data in Phase 13 and never read or modify native browser
profiles or bookmark databases.

GUI controls submit ordinary commands through `GuiController`; browser work
uses the existing bounded worker and Tk callbacks remain on the Tk thread.
Voice preserves `CommandSource.VOICE` and cannot create a browser-specific
parser, permission path, or confirmation shortcut.

Passwords, logins, forms, uploads, downloads, payments, banking, legal
acceptance, CAPTCHA/authentication/security bypass, arbitrary JavaScript,
DevTools commands, extensions, native profile access, authenticated scraping,
and high-volume crawling are unsupported or denied.

See [browser.md](browser.md) for setup, commands, privacy, testing, and known
limitations.

## Phase 14 system domain

System commands remain ordinary `UserCommand` records:

```text
terminal / GUI / voice
        ↓
existing CommandParser
        ↓ typed system intent and bounded entities
SystemActionDispatcher
        ↓ Action + SafetyContext
SafeExecutionGateway
        ↓ policy, persistence, exact confirmation, execute-once
SystemManager
        ↓ injected information/control protocol
ActionResult → existing lifecycle persistence
```

`SystemConfiguration` is created without hardware access and rejects unknown
keys, loose booleans, unsafe ranges, and generic process termination. The
manager contains bounds and adapter orchestration but no parser, UI, or
permission logic. Domain records contain primitive values only, never native
handles, COM objects, processes, or credentials.

The psutil provider queries CPU, memory, fixed-volume usage, battery, bounded
interface counters, and bounded process summaries only when requested. Process
command lines, environments, files, modules, and memory are excluded. Settings
pages use a constant URI allowlist. Audio and brightness are optional adapters
and return safe unavailable results when unsupported.

Power operations use operation-specific, single-use confirmation phrases scoped
to session, command, action, expiry, and target. The Windows adapter accepts a
typed `PowerActionRequest`, uses fixed arguments with `shell=False`, never
forces applications closed, and does not retry. “Shut down Omega” remains the
assistant lifecycle intent; “Shut down the computer” is a separate critical
action.

## Phase 15 scheduler

Scheduling input uses the existing parser and session.
`SchedulingActionDispatcher` submits typed actions through
`SafeExecutionGateway`; `SchedulingService` validates lifecycle changes and
uses `ScheduleRepository`. Migration 6 stores schedules and unique delivery
claims. `SchedulerEngine` starts only when an application mode runs, recovers
abandoned claims as missed, claims a bounded batch, notifies at most once,
advances recurring schedules directly to a future occurrence, and stops with
the application.
Models contain no threads, locks, connections, widgets, callbacks, or executable
objects.

The repository finalizes a delivery row and its exact schedule revision in one
SQLite transaction. A unique `(schedule_id, occurrence_at_utc)` constraint
prevents two workers or restarts from claiming the same occurrence. A crash
after claiming cannot replay a notification: the stale claim is marked missed.
Notification failure is terminal for that occurrence and never triggers an
automatic retry.

Local wall times are interpreted with the configured system/IANA zone and
persisted as aware UTC timestamps. Ambiguous and nonexistent direct inputs are
rejected. Calendar recurrences preserve local wall time and skip DST
gaps/folds; interval recurrence represents elapsed time.

The scheduler publishes inert `ScheduleNotification` records to a bounded
thread-safe `NotificationCenter`. Terminal mode drains them around input, and
the GUI drains them on Tk's main-thread polling loop. Voice command creation and
mutations use the same session and parser. Optional spoken notifications use
only an already initialized local speech adapter and do not affect delivery
success.

## Phase 16 productivity workspace

Productivity commands remain ordinary command-lifecycle data:

```text
terminal / GUI / voice
        ↓
existing CommandParser
        ↓ typed note/task intent and inert entities
ProductivityActionDispatcher
        ↓ Action + revision-scoped SafetyContext
SafeExecutionGateway
        ↓ policy, persistence, exact confirmation, execute-once
ProductivityService
        ↓ parameterized repository / existing ScheduleRepository
ActionResult → existing lifecycle persistence
```

Migration 7 adds notes, task lists, tasks, normalized tags and associations,
plus stable task/reminder links. Foreign keys are enabled by the existing
connection factory. Multi-record imports and tag changes use explicit
transactions; mutations use optimistic revisions so stale editors or
confirmations fail closed.

Productivity models contain only UUIDs, aware UTC timestamps, enums, bounded
text, and JSON-compatible metadata. They never contain repository connections,
widgets, open files, scheduler objects, callbacks, or executable content.
Markdown is stored or exported as plain text, with no HTML renderer, link
launcher, macro facility, or command interpretation.

The productivity repository never creates schema. Search uses parameterized
SQL, escaped LIKE values, deterministic ordering, and bounded results. Task
deadline reminders reuse Phase 15 schedule IDs and services; no second
scheduler exists and due tasks are informational unless explicitly linked to a
notification.
