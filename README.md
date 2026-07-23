# Omega

Omega is a safety-first Windows desktop assistant project. **Current phase:
Phase 15 — Reminders, Timers, Alarms, and Scheduled Tasks (completed).**

## Current status

Omega is a locally controlled assistant that understands narrowly approved Windows tasks while enforcing clear safety boundaries. It starts inactive, accepts `Hello Omega` as a standalone activation phrase, greets Anshuman based on the current time, accepts commands without repeating its name, and uses `Shut down Omega` for safe termination.

Phases 8–13 add recovery, persistence, desktop, voice, and controlled browser support. Phase 14 adds bounded read-only CPU, memory, disk, battery, network, and process information; allowlisted Windows Settings pages; bounded audio/brightness control adapters; and exactly confirmed Windows power actions over the same command, safety, confirmation, and persistence lifecycle.

Omega still cannot permanently delete files or folders, run arbitrary shell commands, modify protected Windows paths, elevate to administrator, modify the Registry or security controls, kill arbitrary processes, retrieve credentials, install software or drivers, or execute AI-generated actions. Browser, voice, audio, and brightness support are optional and do not change these boundaries.

## Safe system controls

After activation, commands such as `Show system information`, `What is my CPU usage?`, `Show disk space`, `Show network status`, `List running processes`, `Set volume to 40 percent`, `Set brightness to 60 percent`, and `Open display settings` use the normal parser and central gateway. Process output is bounded and excludes command lines, environments, open files, and memory content.

Audio and brightness adapters fail safely when compatible local hardware support is unavailable. Brightness never falls below the configured safe minimum. Settings launching accepts only fixed `ms-settings:` entries.

`Lock the computer`, `Put the computer to sleep`, `Sign out`, `Restart the computer`, and `Shut down the computer` require exact, expiring, session-scoped confirmation. `Shut down Omega` only ends the assistant session and never powers off Windows. Generic “yes” is not accepted. Automated tests use fakes and never execute real power actions. See [system.md](docs/system.md).

## Local scheduling

Omega stores local reminders, alarms, and countdown timers in SQLite. Schedules
survive restarts, exact due occurrences are claimed and finalized atomically,
stale claims fail safely without replay, and timers support pause, resume,
cancellation, and one completion notification. Reminders and alarms support
rescheduling, snooze, cancellation, completion/dismissal, and bounded daily,
weekly, monthly, weekday, and interval recurrence. Times are stored in UTC and
interpreted/displayed using the configured local timezone.

Scheduled Omega command execution is disabled: reminder text remains inert data
and cannot become code, deletion, browser input, or a delayed power action.
Omega is not an always-on service, so notification delivery requires Omega to
be running. See [scheduling.md](docs/scheduling.md).

## Optional safe browser automation

Install the optional Playwright adapter:

```powershell
python -m pip install -e ".[browser]"
```

Omega defaults to the installed Microsoft Edge channel and does not download or launch a browser during installation, import, or normal startup. To use Playwright-managed Chromium instead, set `browser.preferred_browser: chromium` and explicitly install its binary:

```powershell
python -m playwright install chromium
```

Browser startup occurs only after an active session receives a browser command. Supported commands include `Open browser`, `Open example.com`, `Search the web for Python decorators`, `Open a new tab`, `List tabs`, `Switch to tab 2`, `Close tab 1`, `Refresh page`, `Go back`, `Go forward`, `Get page information`, `Find the word installation on this page`, `Open bookmark Docs`, and `Save this page as Docs`.

Navigation is HTTPS-only by default. Embedded credentials, dangerous/internal schemes, malformed URLs, localhost, private/link-local/reserved addresses, and cloud metadata endpoints are rejected. All initial requests, redirects, and subresources are checked. Downloads, uploads, form submission, sensitive input, payments, logins, CAPTCHAs, extensions, developer commands, cookies, storage export, and arbitrary JavaScript remain unavailable.

Browser actions use the same parser for text, GUI, and voice, then pass through `SafeExecutionGateway` once. Closing the controlled session and saving a bookmark require exact scoped confirmation. Omega closes only its own Playwright context/browser and never broadly terminates Chrome, Edge, or Firefox processes. Bookmarks are Omega-managed and process-local in Phase 13; browser-native bookmarks and profiles are never read or changed. See [browser.md](docs/browser.md).

## Optional offline voice

Voice is disabled by default and never opens a microphone during import, ordinary terminal startup, or GUI construction. Install the optional local adapters with:

```powershell
python -m pip install -e ".[voice]"
```

Download an English Vosk model manually, extract it beneath `data/voice_models/`, set its relative directory in `config/app_config.yaml`, and set `voice.enabled: true`. Omega never downloads a model during startup and model directories are ignored by Git.

Start terminal voice mode explicitly:

```powershell
omega --voice
python -m omega --voice
omega --list-audio-devices
```

The GUI has **Start voice** and **Stop voice** controls, microphone/listening state, a transcription preview, and a preference that can disable spoken responses. The microphone remains off until Start voice is selected.

While passively listening, an exact, case-insensitive and boundary-punctuation-tolerant `Hello Omega` activates the existing session. `Hello Omega, open Chrome` is split only when that prefix is exact. Active speech is sent once through `OmegaSession`, the existing parser, persistence, dispatchers, and `SafeExecutionGateway`, with `CommandSource.VOICE`. `Shut down Omega` uses the existing shutdown lifecycle and releases listening resources.

Voice confirmation remains strict: only a final transcription matching the pending action’s exact confirmation or cancellation phrase at the configured higher confidence threshold reaches the existing confirmation manager. Silence, partial text, low confidence, “yes”, expired confirmations, and duplicate callbacks cannot approve an action.

Recognition is local through Vosk; microphone capture uses sounddevice; spoken output uses Windows SAPI through comtypes. There is no cloud upload, API key, telemetry, raw-audio logging, audio-file creation, or audio storage in SQLite. Transcripts follow the same command/history policy as typed commands. See [voice.md](docs/voice.md) for setup, privacy, troubleshooting, and opt-in hardware verification.

## Desktop interface

The desktop interface is optional. Terminal mode remains the default:

```powershell
omega
python -m omega
```

Start the GUI explicitly:

```powershell
omega --gui
python -m omega --gui
```

Use `omega --gui-check` to verify that tkinter is available without creating a window or initializing Omega. The resizable ttk window provides conversation history, multiline command input, assistant state, bounded persistent activity, exact confirmation dialogs, safe Undo/Export/Clear History controls, mutable appearance preferences, and in-application notifications.

All commands—including toolbar operations—go through the existing `OmegaSession`, parser, dispatchers, and `SafeExecutionGateway`. Closing a confirmation dialog cancels rather than approves. Background operations use a bounded two-worker executor and marshal every widget update back to Tk's main thread. See [gui.md](docs/gui.md).

## Persistent history

- Migrations 1–3 retain the Phase 9 database, command, and action meanings.
- Migration 4 adds recovery records with command/action foreign keys.
- Migration 5 adds JSON-only mutable runtime settings.
- Commands, action proposals, lifecycle changes, and terminal results are saved once.
- A persistence failure before execution blocks the operation; a result-write failure after execution is surfaced and never causes automatic retry.
- `show history`, recent command/action views, failed actions, confirmed cleanup, export, and undo inspection all pass through the safety gateway.
- Cleanup never deletes user resources, the database, migration records, or runtime settings.
- Exports are bounded UTF-8 JSON under Omega's runtime export directory and never overwrite an existing file.

## Safety decisions

| Action category | Typical risk | Default decision | Confirmation | Restrictions |
|---|---|---|---|---|
| Status, bounded reads, metadata, search | Low | Allow after validation | No | Approved roots and safe types only |
| Registered application open, create, append, rename, copy | Medium | Allow after validation | No | No arbitrary targets, arguments, merge, or replacement |
| Application close, content overwrite, file/folder move | High | Require confirmation | Exact scoped command | Expires, is session-bound, and revalidates the target |
| Permanent deletion, protected paths, shell/script execution | Critical | Deny | Not available | Configuration cannot enable these boundaries |
| Lock, sleep, hibernate | High | Require confirmation | Exact operation phrase | No automatic retry or elevation |
| Sign out, restart, computer shutdown | Critical | Require confirmation | Exact operation phrase | Fixed Windows invocation; no force-close flag |

## Technology

- Python 3.11+
- PyYAML for safe YAML configuration
- psutil for controlled process inspection and termination
- tzdata for deterministic IANA timezone and DST handling on Windows
- tzlocal for resolving the Windows system timezone without hardcoding it
- optional Vosk, sounddevice, and comtypes for offline Windows voice interaction
- optional Playwright for isolated, controlled browser sessions
- pytest, Ruff, Black, and mypy for quality checks

## Architecture

The source package lives in `src/omega`. Configuration is kept in `config/`; generated runtime data belongs in `data/`; project decisions and future design are documented in `docs/`. See [architecture.md](docs/architecture.md).

## Installation (Windows PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pip install -e .
```

`scripts/setup_environment.py` can safely print this guidance and create the tracked runtime directories:

```powershell
python scripts/setup_environment.py
```

## Run Omega

```powershell
python main.py
python -m omega
omega
```

The final command works after installing the package (for example, with `python -m pip install -e .`). Omega starts inactive; say `Hello Omega` before entering a command, and use `Shut down Omega` to exit safely.

## Safe file support

All file commands resolve through a configured logical location. Desktop is the safe default when a command omits a location. Parent folders must already exist; Phase 5 does not create folder trees.

| Extension | Create | Read | Write | Open | Restrictions |
|---|---:|---:|---:|---:|---|
| `.txt`, `.md`, `.csv` | Yes | Yes | Yes | Yes | UTF-8 text and configured size limits |
| `.json`, `.yaml`, `.yml` | Yes | Yes | Yes | Yes | Written as text; Omega does not claim schema validity |
| `.html`, `.css` | Yes | Yes | Yes | Yes | Stored as text and never executed by Omega |
| `.py`, `.js` | Yes | Yes | Yes | No | Opening is blocked because the file association may execute a script |
| `.pdf`, `.doc`, `.docx` | No | No | No | Yes | Open-only through the registered default application |
| `.xls`, `.xlsx`, `.ppt`, `.pptx` | No | No | No | Yes | Open-only; contents are not inspected or modified |
| Executables and command scripts | No | No | No | No | Includes `.exe`, `.bat`, `.cmd`, `.ps1`, `.vbs`, `.msi`, and related types |

## Safe folder support

Folder commands reuse Phase 5's logical-location resolver and accept only validated relative paths. Creation makes only the requested final directory and requires its immediate parent to exist. Recursive work is preceded by a bounded, read-only scan that rejects symbolic links, junctions, protected paths, inaccessible trees, and configured item, byte, or depth overages.

| Operation | Supported | Confirmation | Limits | Important restrictions |
|---|---:|---:|---|---|
| Create | Yes | No | One final directory | Existing real parent required; no recursive parent creation |
| Existence check | Yes | No | One validated target | Files and links do not count as folders |
| List contents | Yes | No | First 100 items by default | Immediate children only; protected/linked entries omitted |
| Inspect metadata | Yes | No | Configured depth, item, and byte bounds | Incomplete scans are identified as truncated |
| Open in File Explorer | Yes on Windows | No | One validated target | Uses the Windows association API; never a shell command |
| Rename | Yes | No | Same parent only | No overwrite, merge, link, or protected target |
| Copy tree | Yes | No | 20 levels, 10,000 items, 5 GiB by default | Preflight and post-copy verification; no links or merge |
| Move tree | Same volume only | Yes, exact | Same bounds as copy | Atomic rename-style move; cross-volume removal is blocked |
| Search by folder name | Yes | No | Depth 6 and 50 results by default | Exact case-insensitive name; one approved root only |
| Delete | No | Not applicable | Deferred to Phase 8 | No permanent folder-deletion path exists |

## Registered applications

Availability depends on the applications installed on the current Windows computer. Status matching uses exact registered process names.

| Application | Open | Status | Graceful close | Force close | Restrictions |
|---|---:|---:|---:|---:|---|
| Google Chrome | Yes | Yes | Confirmation | No | May contain tabs or unsaved form data |
| Microsoft Edge | Yes | Yes | Confirmation | No | May contain tabs or unsaved form data |
| Notepad | Yes | Yes | Confirmation | No | May contain unsaved text |
| Calculator | Yes | Yes | Confirmation | No | Uses an allowlisted Windows URI |
| File Explorer | Yes | Yes | No | No | Closing is blocked to protect the desktop shell |
| Paint | Yes | Yes | Confirmation | No | May contain unsaved work |
| Settings | Yes | Yes | No | No | Uses an allowlisted Windows URI; close is blocked |
| Task Manager | Yes | Yes | No | No | Close is blocked |
| Command Prompt | Yes | Yes | No | No | No user arguments; close is blocked |
| PowerShell | Yes | Yes | No | No | No user arguments; close is blocked |

## Quality checks

```powershell
python -m pytest
python -m pytest --cov=omega --cov-report=term-missing
python -m ruff check .
python -m black --check .
python -m mypy src
```

## Safety principles

Omega never passes user text to a shell or executable argument list. Every session-originated operation passes through `SafeExecutionGateway`; domain risk values are provisional and cannot override its classifier. Denial overrides confirmation, confirmation overrides allow, and no matching allow policy means deny. File and folder targets use registered logical roots, resolved containment, protected-resource checks, and immediate revalidation. Confirmations are exact, short-lived, session-bound, and single-use. Logs and audit records exclude file contents, pending text, secrets, process command lines, and private absolute paths. Read the full [safety policy](docs/safety_policy.md).

## Roadmap

Phase 0 establishes the base. The completed sequence then introduces command models, text interaction, rule-based understanding, Windows application and file/folder management, safety confirmations, undo/history, GUI, voice interaction, and safe browser automation. Details are in [development_roadmap.md](docs/development_roadmap.md).

## License

Omega is licensed under the [MIT License](LICENSE).
