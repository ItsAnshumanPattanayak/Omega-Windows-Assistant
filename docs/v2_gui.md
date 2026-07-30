# Omega V2 GUI foundation

Omega V2 Phase 1 adds an isolated, animated presentation foundation while preserving
the existing terminal and Version 1 GUI. It does not add microphone capture, speech
recognition, text-to-speech, screen awareness, permission requests, or new automation.

## Development environment

Use the dedicated Python 3.11 environment from the repository root:

```powershell
.\.venv-v2\Scripts\Activate.ps1
python --version
python -m omega --v2-gui-check
python -m omega --v2-gui
```

The `v2` optional dependency group contains Pillow and
`opencv-python-headless`. Recreate the environment, if needed, with:

```powershell
py -3.11 -m venv .venv-v2
.\.venv-v2\Scripts\python.exe -m pip install -e ".[dev,v2]"
```

The existing `.venv` environment is not modified by this workflow.

## Architecture

`OmegaV2GuiApplication` is the explicit composition root. It creates the Tk window,
`GuiStateManager`, view model, and `SilentLoopingVideoController` only when the V2 GUI
entry point runs. Importing the modules does not create a window or start playback.

The public V2 states are sleeping, idle, listening, understanding, planning, waiting
for confirmation, executing, speaking, completed, error, permission required, and
emergency stopped. State metadata supplies accessible labels, descriptions, and a
bounded visual-intensity hint. The emergency state clears the local demo display and
must be reset through sleeping or idle before normal states resume.

The animation asset is:

`assets\videos\omega_core_loop.mp4`

Resource lookup works from source and packaged applications and does not depend on
the current working directory. OpenCV decodes visual frames only; no audio stream is
opened, decoded, or sent to an output device. The controller is structurally muted,
loops at end-of-file, runs through Tk's non-blocking event scheduler, and falls back to
a static Omega panel if the asset or multimedia backend is unavailable.

The buttons in this phase demonstrate presentation states only. “Start listening
demo” does not access a microphone, and none of the controls executes a Windows
action. The existing `python -m omega`, `--gui`, and other entry points remain intact.

## Verification

```powershell
python -m pytest -p no:cacheprovider tests\gui_v2 -v
python -m black --check .
python -m ruff check .
python -m mypy src
python -m pytest -p no:cacheprovider
```

For a decoder problem, confirm the file exists at the path above and reinstall the
`v2` extra in `.venv-v2`. Omega will show static visual mode instead of crashing when
video playback cannot start. `python -m omega --v2-gui-check` provides a bounded
toolkit, media-dependency, and asset check without opening the main V2 window.
