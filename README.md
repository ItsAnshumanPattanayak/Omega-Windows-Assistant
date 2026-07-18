# Omega

Omega is a safety-first Windows desktop assistant project. **Current phase: Phase 4 — Controlled Windows Application Manager.**

## Current status

Omega is a locally controlled assistant that understands narrowly approved Windows tasks while enforcing clear safety boundaries. It starts inactive, accepts `Hello Omega` as a standalone activation phrase, greets Anshuman based on the current time, accepts commands without repeating its name, and uses `Shut down Omega` for safe termination.

Phase 4 connects complete Phase 3 application intents to an allowlisted Windows application manager. An active text session can open registered applications, report their running status, close selected applications gracefully, and require an exact short-lived confirmation before data-loss-risk closes. Operations return the existing structured `ActionResult` records. Unknown, disabled, ambiguous, incomplete, or unregistered targets are never executed.

Omega still cannot create or delete files or folders, execute arbitrary shell commands, install software, modify Windows settings, process voice input, provide a GUI, automate browser pages, or execute AI-generated actions.

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

The final command works after installing the package (for example, with `python -m pip install -e .`). Omega starts inactive; say `Hello Omega` before entering an application command, and use `Shut down Omega` to exit safely.

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

Omega never passes user text to a shell or executable argument list. Application IDs, paths, URIs, and exact process names come only from the validated project registry; launches use argument sequences with `shell=False`. Administrator operations and force close remain disabled by default. Logs must not contain sensitive information. Read the full [safety policy](docs/safety_policy.md).

## Roadmap

Phase 0 establishes the base. The planned sequence then introduces command models, text interaction, rule-based understanding, Windows application and file/folder management, safety confirmations, undo/history, GUI, and voice interaction. Details are in [development_roadmap.md](docs/development_roadmap.md).

## License

Omega is licensed under the [MIT License](LICENSE).
