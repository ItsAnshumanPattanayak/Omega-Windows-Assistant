# Omega

Omega is a safety-first Windows desktop assistant project. This repository currently contains **Phase 0: Project Foundation and Environment Setup** only.

## Current status

The long-term vision is a locally controlled assistant that can understand approved Windows tasks while enforcing clear safety boundaries. Its planned activation phrase is `Hello Omega`; a future active session will use `Shut down Omega` to terminate safely. Once activated in a future phase, Omega is planned to greet Anshuman based on the current time and accept normal commands without repeating its name.

Phase 0 provides a professional Python package layout, configuration loading, structured logging, custom exceptions, safe setup guidance, documentation, and tests. It does **not** listen to a microphone, detect wake words, greet users, execute commands, open or close applications, manage files, call AI services, or display a GUI.

## Technology

- Python 3.11+
- PyYAML for safe YAML configuration
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

The final command works after installing the package (for example, with `python -m pip install -e .`). All commands currently initialize Phase 0, report success, and exit.

## Quality checks

```powershell
python -m pytest
python -m pytest --cov=omega --cov-report=term-missing
python -m ruff check .
python -m black --check .
python -m mypy src
```

## Safety principles

Omega will never permit unrestricted user-provided shell execution, administrator operations by default, or permanent deletion by default. Future destructive actions will require confirmation and prefer the Recycle Bin. Logs must not contain sensitive information. Read the full [safety policy](docs/safety_policy.md).

## Roadmap

Phase 0 establishes the base. The planned sequence then introduces command models, text interaction, rule-based understanding, Windows application and file/folder management, safety confirmations, undo/history, GUI, and voice interaction. Details are in [development_roadmap.md](docs/development_roadmap.md).

## License

Omega is licensed under the [MIT License](LICENSE).
