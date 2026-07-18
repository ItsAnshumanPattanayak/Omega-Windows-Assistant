# Omega safety policy

Omega is founded on least-privilege behavior and explicit user control.

- User-provided shell commands must never be executed without strict, purpose-built authorization; unrestricted shell execution is prohibited.
- Administrator-level operations are disabled by default.
- Permanent deletion is disabled by default.
- Future path checks must protect system locations such as Windows, Program Files, Program Files (x86), and ProgramData.
- Future destructive operations must obtain clear confirmation before proceeding.
- Future deletion features should use the Recycle Bin rather than permanently removing files whenever possible.
- Future action history and undo support must make completed operations reviewable and reversible where practical.
- Local AI may propose actions, but it may never execute an action directly; only a validated executor may act after policy checks.
- Logs must not contain secrets, credentials, personal content, or other sensitive information.

Phase 0 enforces the initial configuration flags and deliberately contains no command executor.

## Phase 4 application controls

- Only canonical applications in `config/application_aliases.json` may be opened, inspected, or considered for closing.
- User input can resolve an alias only; it cannot supply an executable path, URI, PID, process argument, shell expression, or process definition.
- Executable and process fields accept exact `.exe` filenames without paths, arguments, traversal, shell metacharacters, pipelines, or redirections.
- Filesystem launches use an argument sequence and `shell=False`. Omega does not use `os.system`, PowerShell wrappers, Command Prompt wrappers, `taskkill`, `wmic`, `eval`, or `exec`.
- URI launches are limited to explicit registered allowlist values. Administrator elevation and UAC bypass are prohibited.
- Process matching is exact and case-insensitive. Every mutation revalidates process name and creation time to reduce PID-reuse risk.
- Essential Windows processes are protected. In particular, Omega never terminates `explorer.exe`, so File Explorer close commands are refused.
- Chrome, Edge, Notepad, and Paint require exact short-lived confirmation before close because unsaved work may be lost. A confirmation is scoped to one application and is never persisted.
- Force close is disabled globally and per application by default. It is never an automatic fallback and would require a prior graceful failure plus a separate exact confirmation.
- Automated tests mock process mutation. Opt-in Windows integration tests may clean up only a harmless process that the test can prove it launched; they skip rather than target any pre-existing process.

## Phase 5 file controls

- User commands may address only Desktop, Documents, Downloads, Pictures, Music, Videos, Home, or Omega's captured startup directory. Desktop is the configured default.
- Arbitrary absolute, drive-qualified, UNC, device, alternate-stream, environment-expanded, and tilde-expanded paths are rejected. Resolved containment checks, not string prefixes, prevent traversal and link escapes.
- Windows reserved names, control characters, invalid filename characters, trailing spaces/periods, and overlong components are rejected deterministically.
- Windows, System32, Program Files, Program Files (x86), ProgramData, boot/recovery data, system-volume data, Recycle Bin internals, repository `.git`, configuration, logs, and action backups are protected.
- Creation, reading, and writing are restricted to approved text/data extensions. Executable and script types are blocked; `.py` and `.js` may be stored as text but are not opened.
- Reads, displayed characters, writes, resulting file sizes, search depth, and search results have positive configured bounds. Search never scans drives or file contents and never follows directory links.
- Existing files are never replaced during create, rename, copy, or move. Destination conflicts are refused until recovery-aware policy exists.
- Replacing non-empty text requires an exact, expiring confirmation bound to the target's size, modification time, and content hash. Replacement uses a same-filesystem temporary file and atomic `os.replace`.
- Pending text exists only in memory and is cleared on cancellation, timeout, shutdown, interruption, or process restart. File contents and pending text are never logged.
- `DELETE_FILE` performs no deletion in Phase 5. Recycle Bin deletion and undo are deferred to Phase 8.
- Automated file tests use pytest-managed temporary logical roots. Real Windows workflow tests are opt-in and may affect only their isolated temporary directory.
