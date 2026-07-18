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

Chrome, Edge, Notepad, and Paint require an exact application-specific confirmation before graceful close. The pending confirmation is held only in memory, expires after the configured timeout, is cleared on session timeout/shutdown/interruption, and cannot authorize a different application. `yes` is never sufficient. Calculator is documented as the initial low-risk close target. Force close is never an automatic fallback: it requires a failed graceful close, a separate request and confirmation, the global switch, and application-level permission. Both switches default to disabled for the initial registry.

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

The writer supports UTF-8 text/data extensions with configured content and resulting-size limits. Non-empty replacement creates an in-memory pending record containing the exact target, content, expiry, size, nanosecond modification time, and content hash. Exact confirmation re-resolves and revalidates the target, rejects changed files, and uses a temporary file on the same filesystem plus `os.replace` for atomic replacement. Pending text is never logged or persisted and is cleared on cancellation, timeout, shutdown, interruption, or restart. Append writes exactly the quoted content and does not insert a newline.

Rename, copy, and move refuse destination conflicts because Phase 5 has no recovery/undo layer for replacing a different file. Regular-file and symlink checks occur before mutation; copy and move verify sizes and SHA-256 content. Executable/script opening is blocked. `WindowsFileOpener` isolates the `os.startfile` boundary and receives only a validated absolute document path, never arguments or a command string.

Filename search is limited to one logical root, exact case-insensitive names or internally selected extensions, configured recursion depth, and configured result count. It skips inaccessible and linked directories, never searches file contents or whole drives, and returns relative paths. Bounded reads, display truncation, write limits, and search limits prevent uncontrolled memory or terminal use. File contents and pending write text stay out of logs.

## Planned layers

The following components are planned, not implemented:

- **Input layer:** text and, later, voice input. Voice activation will use `Hello Omega`.
- **Command-processing layer:** converts approved user intent into structured commands.
- **Safety layer:** checks permissions, protected paths, confirmations, and action policies before execution.
- **Executor layer:** performs allowlisted Phase 4 application operations and validated Phase 5 file operations through separate domain dispatchers. Future domains require separate review.

Command understanding must remain separate from execution. An interpreter may recognize a request, but only the safety layer may authorize it and only the executor may perform it. This separation makes future behavior testable and prevents an AI suggestion from becoming an action automatically.

Arbitrary shell execution will be prohibited because it would allow ambiguous natural-language input to become unrestricted operating-system access.

## Planned session lifecycle

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

This lifecycle is implemented for text input. Voice activation remains deferred.
