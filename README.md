# Omega

Omega is a safety-first Windows desktop assistant project. **Current phase: Phase 6 — Controlled Folder Management System.**

## Current status

Omega is a locally controlled assistant that understands narrowly approved Windows tasks while enforcing clear safety boundaries. It starts inactive, accepts `Hello Omega` as a standalone activation phrase, greets Anshuman based on the current time, accepts commands without repeating its name, and uses `Shut down Omega` for safe termination.

Phase 6 adds controlled folder operations inside the same approved logical locations used by Phase 5: Desktop, Documents, Downloads, Pictures, Music, Videos, Home, and the startup working directory. An active session can create one folder beneath an existing parent, check existence, list immediate contents, inspect bounded metadata, open a validated folder, rename folders, copy bounded trees, perform atomic same-volume moves, and run bounded exact-name searches. Folder merging, destination replacement, link traversal, and cross-volume destructive moves are blocked.

Omega still cannot permanently delete files or folders, use the Recycle Bin, undo actions, merge directory trees, replace existing destination folders, perform destructive cross-drive folder moves, access arbitrary absolute/system paths, process voice input, provide a GUI, automate browser pages, or execute AI-generated actions.

## Technology

- Python 3.11+
- PyYAML for safe YAML configuration
- psutil for controlled process inspection and termination
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
| Move tree | Same volume only | No | Same bounds as copy | Atomic rename-style move; cross-volume removal is blocked |
| Search by folder name | Yes | No | Depth 6 and 50 results by default | Exact case-insensitive name; one approved root only |
| Delete | No | Not applicable | Deferred to Phase 8 | No permanent folder-deletion path exists |

## Registered applications

Availability depends on the applications installed on the current Windows computer. Status matching uses exact registered process names.

| Application | Open | Status | Graceful close | Force close | Restrictions |
|---|---:|---:|---:|---:|---|
| Google Chrome | Yes | Yes | Confirmation | No | May contain tabs or unsaved form data |
| Microsoft Edge | Yes | Yes | Confirmation | No | May contain tabs or unsaved form data |
| Notepad | Yes | Yes | Confirmation | No | May contain unsaved text |
| Calculator | Yes | Yes | Yes | No | Uses an allowlisted Windows URI |
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

Omega never passes user text to a shell or executable argument list. Application targets come only from the validated project registry. File and folder targets are built from registered logical roots, validated Windows path components, and resolved containment checks; arbitrary absolute paths and permanent deletion are disabled. Recursive folder scans are bounded and never follow symbolic links or junctions. Administrator operations and force close remain disabled by default. Logs must not contain file contents or other sensitive information. Read the full [safety policy](docs/safety_policy.md).

## Roadmap

Phase 0 establishes the base. The planned sequence then introduces command models, text interaction, rule-based understanding, Windows application and file/folder management, safety confirmations, undo/history, GUI, and voice interaction. Details are in [development_roadmap.md](docs/development_roadmap.md).

## License

Omega is licensed under the [MIT License](LICENSE).
