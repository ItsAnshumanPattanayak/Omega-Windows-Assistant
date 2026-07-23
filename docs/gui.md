# Omega desktop interface

Phase 11 provides an optional Windows desktop interface using Python's standard-library tkinter and ttk. It is a presentation layer over the existing `OmegaApplication`; it does not contain a second parser, executor, safety engine, confirmation store, history repository, or recovery implementation.

## Launch

Terminal mode remains the default:

```powershell
omega
python -m omega
```

The desktop starts only when explicitly requested:

```powershell
omega --gui
python -m omega --gui
```

`omega --gui-check` checks tkinter import availability without creating a Tk root, starting a main loop, creating a database, or initializing runtime directories.

## Main window

The resizable main window contains:

- assistant name, version, and active/inactive state;
- selectable chronological conversation text;
- multiline command input, Enter to send, and Shift+Enter for a newline;
- bounded recent command/action activity with status and timestamps;
- Ready, Processing, Awaiting Confirmation, Error, and Closed status;
- Activate, Shutdown, Show History, Refresh, Undo, Export, Clear History, Settings, and Help controls;
- system, light, and dark ttk themes with configurable safe font sizes;
- in-application success, warning, error, confirmation, and refresh notifications.

Input is limited to 10,000 characters. Whitespace-only input is rejected. While one operation is processing, command-producing controls are disabled so a callback or repeated click cannot execute it twice.

## Safety integration

Every command and toolbar action is submitted once through `OmegaSession.handle_input`. This preserves activation, shutdown, parsing, intent/entity extraction, dispatch, safety classification, policy evaluation, command/action/result persistence, and recovery behavior.

When the existing gateway creates a pending confirmation, the dialog displays its exact prompt, safe target, confirmation phrase, and cancellation phrase. Confirm and Cancel route those phrases through the same session. Enter never approves a destructive operation. Escape or closing the dialog cancels it.

History rows come from bounded `HistoryService.latest_activity` queries. Undo is enabled only while an active recovery record exists and is still unconsumed and unexpired. Export and clear-history controls use their existing history commands. Cleanup remains confirmation-gated, preserves active undo records and runtime settings, and never deletes user files, the database, migration records, or Recycle Bin contents.

## Threading and shutdown

Potentially blocking session, database, history, export, recovery, and operating-system work runs in a bounded `ThreadPoolExecutor` with two workers. Workers return immutable view data. Tk widget updates are scheduled on the main thread with `after`.

The controller permits only one command at a time. Worker failures produce a safe message and are never automatically retried. Closing the window interrupts the existing session, clears pending confirmations, prevents new work, cancels queued tasks, and releases the executor.

## Mutable preferences

Only these validated JSON-compatible `ui.*` settings are mutable:

- system, light, or dark theme;
- font size from 9 through 24;
- history display limit from 1 through 100;
- conversation auto-scroll;
- in-application notifications;
- bounded window width, height, and maximized state.

Malformed UI preferences fall back to safe defaults. Administrator operations, shell execution, permanent deletion, absolute/network/device paths, destination replacement, folder merge, destructive cross-volume movement, default permission decisions, foreign keys, and confirmation policy are not mutable from the GUI.

## Tests and limitations

Headless tests exercise imports, bootstrap, controller behavior, duplicate prevention, confirmation routing, history formatting, undo state, settings, task marshalling, and CLI mode selection. A real Tk smoke session depends on an interactive Windows desktop.

Phase 13 adds toolbar commands for opening the controlled browser, listing tabs, navigating backward/forward, and refreshing. These buttons submit ordinary text commands through `GuiController`; they never call the browser backend directly. The existing busy state prevents duplicate clicks, browser work runs on the bounded GUI task runner, and Tk updates remain on the Tk thread. The GUI remains usable when the optional Playwright package or browser channel is unavailable.

Automatic login, form submission, downloads, embedded browsing, browser-native bookmarks, unrestricted clicking, and native restoration are not available. The current undo interface remains fail-closed when the Phase 8 native restore backend is unavailable.

Phase 14 system commands use the same command box and bounded worker as every
other domain. Read-only status, allowlisted Settings pages, and optional device
controls therefore never call an OS adapter from a widget. Power commands use
the existing exact-confirmation dialog; closing it cancels. Unsupported audio
or brightness hardware appears as a safe unavailable response.
