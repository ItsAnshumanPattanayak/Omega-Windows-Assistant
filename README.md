<div align="center">

# Ω OMEGA

### A Local, Safety-First Windows Desktop Assistant

**Control applications, manage files, browse safely, use voice commands, monitor your system, create reminders, and organize notes and tasks—all from one assistant.**

<br>

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows&logoColor=white)](#system-requirements)
[![Interface](https://img.shields.io/badge/Interface-CLI%20%7C%20GUI%20%7C%20Voice-8A2BE2)](#interaction-modes)
[![Database](https://img.shields.io/badge/Database-SQLite-003B57?logo=sqlite&logoColor=white)](#local-persistence)
[![Privacy](https://img.shields.io/badge/Privacy-Local--First-success)](#privacy)
[![Status](https://img.shields.io/badge/Status-Active%20Development-orange)](#development-status)
[![License](https://img.shields.io/badge/License-Add%20License-lightgrey)](#license)

<br>

[Features](#features) •
[Installation](#installation) •
[Run Omega](#running-omega) •
[Examples](#example-commands) •
[Safety](#safety-architecture) •
[Testing](#testing) •
[Roadmap](#development-status)

</div>

---

## About Omega

**Omega** is a modular Windows assistant designed to help users interact with their computer through text, a desktop graphical interface, and optional offline voice commands.

Unlike a basic command launcher, Omega uses a structured application architecture with:

- Typed commands and actions
- Intent recognition and entity extraction
- Centralized safety evaluation
- Permission policies
- Scoped confirmations
- Persistent command and action history
- Recovery and undo support
- Local SQLite storage
- Modular feature dispatchers
- GUI, terminal, and voice integration

Omega is designed around one core principle:

> **Convenience must never bypass safety.**

All supported operations pass through the same command-processing and safety lifecycle, regardless of whether the command originated from the terminal, desktop GUI, or voice interface.

---

## Current capabilities

Omega currently includes functionality completed through **Phase 16**:

| Area | Status |
|---|---|
| Command understanding | ✅ Implemented |
| Terminal interface | ✅ Implemented |
| Desktop GUI | ✅ Implemented |
| Optional voice interaction | ✅ Implemented |
| Application management | ✅ Implemented |
| Safe file management | ✅ Implemented |
| Safe folder management | ✅ Implemented |
| Confirmation system | ✅ Implemented |
| Recycle Bin and undo | ✅ Implemented |
| Persistent history | ✅ Implemented |
| Runtime settings | ✅ Implemented |
| Safe browser automation | ✅ Implemented |
| Windows system information | ✅ Implemented |
| Volume and brightness controls | ✅ Implemented |
| Windows Settings launcher | ✅ Implemented |
| Confirmed power actions | ✅ Implemented |
| Reminders and recurring reminders | ✅ Implemented |
| Alarms and timers | ✅ Implemented |
| Notes and task management | ✅ Implemented |
| Knowledge-base document search | ⏸️ Planned / paused |

---

# Features

## 1. Multi-interface interaction

Omega supports three interaction modes.

### Terminal interface

Use Omega directly from PowerShell or the VS Code terminal.

```text
Hello Omega
Open Notepad
Show my reminders
Shut down Omega
```

### Desktop graphical interface

The desktop application provides:

- Conversation display
- Command input
- Assistant responses
- Activity status
- Persistent history
- Confirmation dialogs
- Settings controls
- Undo and recovery controls
- Browser controls
- System-information panels
- Reminder and timer views
- Notes and task-management views

Long-running operations are processed outside the GUI thread so the desktop interface remains responsive.

### Optional voice interaction

Omega supports optional local voice interaction with:

- Microphone input
- Configurable wake phrase
- Speech-to-text
- Active listening sessions
- Local text-to-speech
- Voice-state indicators
- Strict confirmation handling
- Text-only fallback when voice components are unavailable

Default wake phrase:

```text
Hello Omega
```

Assistant-session shutdown phrase:

```text
Shut down Omega
```

Voice commands are processed through the same parser and safety gateway as typed commands.

---

## 2. Application management

Omega can safely interact with registered Windows applications.

Supported operations include:

- Open an approved application
- Close an approved application
- Check whether an application is running
- Resolve configured aliases
- Discover registered applications
- Prevent broad or unrelated process termination

Example commands:

```text
Open Chrome
Open Notepad
Open Visual Studio Code
Is Notepad running?
Close Notepad
```

Omega does not expose unrestricted process termination through arbitrary process IDs.

---

## 3. Safe file management

Omega provides controlled file operations inside approved locations.

Supported capabilities include:

- Create a file
- Read supported text files
- Write text to a file
- Append text
- Open a file
- Rename or move supported files
- Search for files
- Delete through a recoverable workflow
- Restore supported deleted files
- Validate source and destination paths

Example commands:

```text
Create a file called notes.txt
Write Hello from Omega in notes.txt
Open notes.txt
Find report.pdf
Delete test.txt
Undo the last action
```

Safety protections include:

- Protected-path checks
- Approved-root validation
- Path normalization
- Traversal prevention
- Confirmation for destructive actions
- Recovery records
- Duplicate-execution protection

---

## 4. Safe folder management

Omega can manage folders through the same safety infrastructure.

Supported operations include:

- Create folders
- Open folders
- Search for folders
- Rename folders
- Move folders
- Inspect folder information
- Delete folders through a safe workflow
- Restore supported folder operations

Example commands:

```text
Create a folder called Project Notes
Open the Downloads folder
Find my Resume Analyzer folder
Rename Drafts to Completed Drafts
```

Omega prevents unsafe operations involving protected Windows locations or ambiguous destination paths.

---

## 5. Central safety gateway

Every supported state-changing operation is evaluated by Omega’s safety system.

The safety architecture includes:

- Risk classification
- Permission decisions
- Resource validation
- Protected-target detection
- Confirmation requirements
- Confirmation expiration
- Action fingerprinting
- Duplicate-execution prevention
- Structured denial responses
- Persistent audit records

Conceptual risk categories include:

| Risk | Example |
|---|---|
| Low | Reading system information |
| Medium | Changing volume or brightness |
| High | Removing stored data or locking the computer |
| Critical | Restarting or shutting down Windows |
| Denied | Arbitrary shell execution or security bypass |

The GUI, voice interface, browser controller, scheduling system, and other components cannot bypass the central execution gateway.

---

## 6. Scoped confirmations

Risky operations require deliberate confirmation.

A confirmation may be linked to:

- Session ID
- Command ID
- Action ID
- Target resource
- Requested operation
- Resource fingerprint
- Current revision
- Expiration time

This prevents:

- Reusing confirmation for another action
- Approving an action after the target changed
- Approving an expired operation
- Executing the same confirmed action twice
- Treating silence or dialog closure as approval
- Using low-confidence voice input for critical actions

---

## 7. Recycle Bin, recovery, and undo

Omega supports recoverable destructive operations where possible.

Capabilities include:

- Recycle Bin integration
- Persistent recovery records
- Undoable action registration
- Restore supported deleted items
- Prevent reuse of completed recovery records
- Preserve recovery state across application restarts
- Validate restored destinations

Example:

```text
Delete E:\Omega-Test-Workspace\test.txt
Undo the last action
```

Omega does not empty the Windows Recycle Bin or perform unrestricted permanent deletion.

---

## 8. Persistent command and action history

Omega stores command activity locally in SQLite.

History may include:

- User commands
- Command source
- Session identifiers
- Generated actions
- Risk level
- Permission decision
- Confirmation state
- Action results
- Error category
- Execution timestamps
- Recovery information

Example commands:

```text
Show my history
Show recent commands
Show failed actions
Show recent activity
```

History queries are bounded and ordered to prevent unbounded database output.

---

## 9. History export and cleanup

Omega can safely manage its own application history.

Supported operations include:

- Export history as JSON
- View recent command history
- View failed actions
- Clear eligible historical records
- Preserve active recovery information
- Preserve database schema information
- Return a cleanup summary

Clearing Omega history does not delete personal files or empty the Windows Recycle Bin.

---

## 10. Runtime preferences

Omega stores safe mutable preferences locally.

Preferences may include:

- Theme
- Font size
- History display limits
- Window state
- Notification preferences
- Voice preferences
- Speech rate
- Browser preferences
- Productivity display settings

Runtime preferences cannot override hard safety restrictions.

---

## 11. Safe browser automation

Omega can operate a controlled browser session.

Supported operations include:

- Open the browser
- Close the Omega-controlled browser
- Open a validated website
- Search the web
- Open a new tab
- Close a tab
- Switch tabs
- List tabs
- Refresh the current page
- Go backward
- Go forward
- Show page information
- Find text on a page
- Use Omega-managed bookmarks

Example commands:

```text
Open the browser
Open https://example.com
Search the web for Python decorators
Open a new tab
List tabs
Go back
Refresh the page
Find the word Example on this page
```

### Browser restrictions

Omega does not provide:

- Password entry
- Payment automation
- Banking automation
- CAPTCHA bypass
- Arbitrary JavaScript execution
- Browser-security bypass
- Unrestricted form submission
- Executable downloads
- Cookie or token extraction
- Hidden authenticated scraping
- Broad termination of user browser processes

Dangerous URL schemes and unsafe local-network targets are rejected by default.

---

## 12. Windows system information

Omega can retrieve bounded read-only system information.

Supported information may include:

- Operating-system summary
- CPU usage
- Processor counts
- Memory usage
- Available memory
- Disk usage
- Free disk space
- Battery percentage
- Charging status
- Network status
- Bounded process summaries

Example commands:

```text
Show system information
What is my CPU usage?
Show memory usage
Show disk space
What is my battery percentage?
Show network status
List running processes
```

Omega does not expose:

- Wi-Fi passwords
- Product keys
- Access tokens
- Process environment variables
- Process memory
- Complete sensitive command lines
- Credential stores

---

## 13. Volume controls

Supported audio controls include:

- Get current volume
- Set volume
- Increase volume
- Decrease volume
- Mute
- Unmute

Example commands:

```text
Show volume
Set volume to 40 percent
Increase volume by 10 percent
Mute the sound
Unmute the sound
```

Volume values are validated and bounded.

---

## 14. Brightness controls

On supported hardware, Omega can:

- Show brightness
- Set brightness
- Increase brightness
- Decrease brightness

Example commands:

```text
Show brightness
Set brightness to 60 percent
Decrease brightness by 10 percent
```

Unsupported external displays or hardware return a safe unavailable response instead of crashing Omega.

---

## 15. Approved Windows Settings pages

Omega can open allowlisted Windows Settings pages.

Examples include:

- Display
- Sound
- Notifications
- Power and battery
- Storage
- Bluetooth and devices
- Network and internet
- Windows Update
- Apps
- Privacy

Example commands:

```text
Open display settings
Open sound settings
Open Bluetooth settings
Open storage settings
```

Omega does not accept arbitrary system protocols or unrestricted Settings URIs.

---

## 16. Power and session controls

Omega supports carefully restricted power operations:

- Lock computer
- Sleep
- Hibernate when enabled and available
- Sign out
- Restart
- Shut down
- Cancel a pending power countdown where supported

Example commands:

```text
Lock the computer
Restart the computer
Shut down the computer
```

High-risk and critical actions require scoped, operation-specific confirmation.

Omega distinguishes between:

```text
Shut down Omega
```

and:

```text
Shut down the computer
```

The first ends the assistant session. The second requests a critical Windows power action.

---

## 17. Reminders

Omega provides persistent local reminders.

Supported features include:

- One-time reminders
- Relative reminders
- Daily reminders
- Weekly reminders
- Selected-weekday reminders
- Recurring reminders
- Reminder editing
- Reminder cancellation
- Reminder completion
- Snoozing
- Restart recovery
- Overdue handling

Example commands:

```text
Remind me in 30 minutes to review my code
Remind me tomorrow at 7 PM to study DSA
Remind me every Monday at 10 AM to check assignments
List my reminders
Cancel the study reminder
Snooze this reminder for 10 minutes
```

---

## 18. Alarms

Omega supports persistent local alarms.

Capabilities include:

- One-time alarms
- Recurring alarms
- Daily alarms
- Weekday alarms
- Dismissal
- Snoozing
- Cancellation
- Restart restoration
- Bounded notification repetition

Example commands:

```text
Set an alarm for 6:30 AM
Set an alarm every weekday at 7 AM
List my alarms
Snooze this alarm for five minutes
Cancel my 7 AM alarm
```

---

## 19. Timers

Omega supports multiple countdown timers.

Capabilities include:

- Start timer
- Pause timer
- Resume timer
- Cancel timer
- View remaining time
- List active timers
- Restore active or paused timers after restart
- Deliver one completion notification

Example commands:

```text
Start a timer for 20 minutes called Study Timer
List my timers
Pause the Study Timer
Resume the Study Timer
Cancel the Study Timer
```

---

## 20. Persistent scheduler

Omega includes a local scheduling engine with:

- Explicit startup and shutdown
- SQLite persistence
- Atomic due-item claiming
- Duplicate-delivery prevention
- Stale-claim recovery
- Timezone-aware scheduling
- UTC persistence
- Restart restoration
- Bounded overdue processing
- Deterministic recurrence
- GUI notifications
- Terminal notifications
- Optional spoken notifications

The scheduler does not require:

- A cloud service
- A cloud account
- Windows Task Scheduler
- A permanently installed Windows service

Destructive scheduled commands remain disabled or restricted by current safety policy.

---

## 21. Notes

Omega provides local note management.

Supported operations include:

- Create a note
- View notes
- Edit a note
- Append content
- Search notes
- Pin and unpin notes
- Archive notes
- Restore archived notes
- Delete notes with confirmation
- Add and remove tags
- Export notes

Example commands:

```text
Create a note called Project Ideas
Add Use SQLite to the Project Ideas note
Show the Project Ideas note
Search my notes for machine learning
Pin the Project Ideas note
Archive the Shopping note
```

Note content is always treated as data.

Omega does not execute:

- Code blocks
- Markdown commands
- HTML
- JavaScript
- Links
- Shell commands written inside notes

---

## 22. Task lists and to-do management

Omega supports local productivity management.

Capabilities include:

- Create task lists
- Create tasks
- Update task details
- Complete tasks
- Reopen tasks
- Cancel tasks
- Archive tasks
- Restore tasks
- Delete tasks with confirmation
- Move tasks between lists
- Set priorities
- Set deadlines
- Remove deadlines
- Add and remove tags
- Search and filter tasks

Example commands:

```text
Create a task list called Omega QA
Add a task to Omega QA called Test voice mode
Set the task priority to high
Set the deadline to tomorrow at 7 PM
Show tasks due today
Show overdue tasks
Mark Test voice mode complete
```

Supported task views may include:

- Pending
- In progress
- Due today
- Overdue
- Upcoming
- Completed
- Cancelled
- Archived

Task text is never executed as an Omega command.

---

## 23. Task and reminder integration

Tasks can be linked to the Phase 15 scheduling system.

Supported behavior includes:

- Link an existing reminder to a task
- Create a reminder for a task deadline
- Show linked reminder status
- Unlink reminders
- Cancel a linked reminder explicitly
- Prevent duplicate reminder links
- Preserve reminder history after task completion

Example:

```text
Remind me about the Test voice mode task tomorrow at 6 PM
```

Completing a task does not silently execute or remove unrelated actions.

---

## 24. Productivity import and export

Omega supports safe productivity data handling.

Supported formats may include:

- JSON import
- JSON export
- Markdown export

Safety restrictions include:

- No Pickle import
- No Python file import
- No script execution
- No raw SQLite database import
- No executable Markdown
- No automatic link opening
- No unsafe export path
- No silent overwrite
- Bounded import and export sizes

---

# Architecture

Omega follows a layered and modular architecture.

```text
┌─────────────────────────────────────────────┐
│              User Interfaces                │
│       Terminal │ Desktop GUI │ Voice        │
└─────────────────────┬───────────────────────┘
                      │
┌─────────────────────▼───────────────────────┐
│         Command and Session Handling        │
│  Activation │ Normalization │ Clarification │
└─────────────────────┬───────────────────────┘
                      │
┌─────────────────────▼───────────────────────┐
│          Natural-Language Understanding     │
│      Intent Detection │ Entity Extraction   │
└─────────────────────┬───────────────────────┘
                      │
┌─────────────────────▼───────────────────────┐
│             Feature Dispatchers             │
│ Apps │ Files │ Folders │ Browser │ System   │
│ Scheduling │ Productivity │ History          │
└─────────────────────┬───────────────────────┘
                      │
┌─────────────────────▼───────────────────────┐
│              Safety Architecture            │
│ Risk │ Permission │ Confirmation │ Gateway  │
└─────────────────────┬───────────────────────┘
                      │
┌─────────────────────▼───────────────────────┐
│             Services and Adapters           │
│ Windows APIs │ Browser │ Audio │ SQLite     │
└─────────────────────┬───────────────────────┘
                      │
┌─────────────────────▼───────────────────────┐
│             Persistent Local Data           │
│ History │ Actions │ Recovery │ Schedules    │
│ Settings │ Notes │ Tasks                     │
└─────────────────────────────────────────────┘
```

---

# Project structure

The exact structure may evolve, but the project follows a layout similar to:

```text
Omega-Windows-Assistant/
│
├── config/
│   └── app_config.yaml
│
├── data/
│   ├── database/
│   ├── logs/
│   └── exports/
│
├── docs/
│
├── src/
│   └── omega/
│       ├── applications/
│       ├── browser/
│       ├── database/
│       ├── files/
│       ├── folders/
│       ├── gui/
│       ├── history/
│       ├── productivity/
│       ├── recovery/
│       ├── safety/
│       ├── scheduling/
│       ├── system/
│       ├── understanding/
│       ├── voice/
│       ├── app.py
│       └── __main__.py
│
├── tests/
│
├── .gitignore
├── pyproject.toml
└── README.md
```

> The actual repository is the source of truth. Some package names may differ depending on the implemented architecture.

---

# System requirements

- Windows 10 or Windows 11
- Python 3.11 or a compatible version declared in `pyproject.toml`
- PowerShell
- Git
- Optional microphone for voice mode
- Optional supported audio and brightness hardware
- Optional supported browser automation dependencies

---

# Installation

## 1. Clone the repository

```powershell
git clone https://github.com/ItsAnshumanPattanayak/Omega-Windows-Assistant.git
cd Omega-Windows-Assistant
```

For the existing local project:

```powershell
cd "E:\project Omega"
```

## 2. Create a virtual environment

```powershell
python -m venv .venv
```

## 3. Activate it

```powershell
.\.venv\Scripts\Activate.ps1
```

When PowerShell blocks script activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 4. Upgrade pip

```powershell
python -m pip install --upgrade pip
```

## 5. Install Omega

```powershell
python -m pip install -e .
```

When a development dependency group exists:

```powershell
python -m pip install -e ".[dev]"
```

Check `pyproject.toml` before installing optional groups.

---

# Running Omega

Always activate the virtual environment first:

```powershell
cd "E:\project Omega"
.\.venv\Scripts\Activate.ps1
```

## View available launch options

```powershell
python -m omega --help
```

This command is the source of truth for the currently implemented launch flags.

## Terminal mode

```powershell
python -m omega
```

When a project script is registered, this may also work:

```powershell
omega
```

## Desktop GUI

Use the GUI option shown by:

```powershell
python -m omega --help
```

The expected command is commonly:

```powershell
python -m omega --gui
```

## Voice mode

Use the voice option shown by the help command.

Expected examples may include:

```powershell
python -m omega --voice
```

or:

```powershell
python -m omega --gui --voice
```

Voice mode may require additional local dependencies or an offline speech model. Consult the project’s voice documentation and configuration.

---

# First safe test

Create an isolated workspace before testing file operations:

```powershell
New-Item -ItemType Directory -Path "E:\Omega-Test-Workspace" -Force
```

Start Omega and test:

```text
Hello Omega
Open Notepad
Show system information
Create a folder called Notes inside E:\Omega-Test-Workspace
Create a file called test.txt inside E:\Omega-Test-Workspace
Write Hello from Omega in test.txt
Open test.txt
Start a timer for one minute called Test Timer
Create a note called Omega Testing
Shut down Omega
```

Avoid testing shutdown, restart, sign-out, sleep, hibernate, or deletion of important files during the first test session.

---

# Example commands

## Applications

```text
Open Chrome
Open Notepad
Is Visual Studio Code running?
Close Notepad
```

## Files and folders

```text
Create a folder called Study Notes
Create a file called topics.txt
Write Arrays and Sorting in topics.txt
Open topics.txt
Find report.pdf
Undo the last action
```

## Browser

```text
Open the browser
Open https://example.com
Search the web for Python binary search
Open a new tab
List tabs
Refresh the page
```

## System

```text
Show system information
Show CPU usage
Show memory usage
Show disk space
Show battery status
List running processes
```

## Audio and brightness

```text
Show volume
Set volume to 30 percent
Mute the sound
Set brightness to 60 percent
```

## Settings

```text
Open display settings
Open sound settings
Open Bluetooth settings
Open storage settings
```

## Scheduling

```text
Remind me in ten minutes to drink water
Remind me tomorrow at 7 PM to practice DSA
Set an alarm for 6:30 AM
Start a timer for 25 minutes called Study Session
Pause the Study Session timer
Resume the Study Session timer
List my reminders
```

## Notes

```text
Create a note called Project Ideas
Add Build a local assistant to the Project Ideas note
Show my notes
Search my notes for assistant
Pin the Project Ideas note
```

## Tasks

```text
Create a task list called Placement Preparation
Add a task called Practice sorting problems
Set its priority to high
Set its deadline to tomorrow at 9 PM
Show tasks due today
Show overdue tasks
Mark Practice sorting problems complete
```

## History

```text
Show my history
Show recent commands
Show failed actions
Export my history
```

---

# Configuration

Omega uses trusted application configuration, expected under:

```text
config/app_config.yaml
```

Configuration may control:

- Wake phrase
- Shutdown phrase
- Approved paths
- Application registry
- Safety policies
- Database paths
- History limits
- Voice settings
- Browser restrictions
- System-control limits
- Scheduler behavior
- Notification preferences
- Productivity limits

Do not use runtime preferences to weaken safety rules.

Before changing configuration:

1. Create a backup.
2. Change only documented keys.
3. Preserve valid YAML indentation.
4. Run tests after the change.
5. Never store secrets directly in committed configuration.

---

# Local persistence

Omega uses SQLite for local persistence.

Stored information may include:

- Commands
- Actions
- Results
- Confirmation status
- Recovery records
- Runtime preferences
- History
- Reminders
- Alarms
- Timers
- Notes
- Task lists
- Tasks
- Tags
- Reminder links

Database migrations run during explicit application startup rather than during package import.

Runtime database files should remain excluded from Git.

---

# Privacy

Omega is designed as a local-first project.

Default privacy principles include:

- Local command processing
- Local database storage
- No required cloud account
- No hidden telemetry
- No automatic document upload
- No raw audio persistence by default
- No continuous clipboard monitoring
- No hidden screenshot capture
- No password collection
- No credential storage
- No browser-cookie extraction
- No automatic filesystem scanning
- No cloud scheduler requirement

Optional components must fail safely without breaking core text-based functionality.

---

# Security restrictions

Omega intentionally does not provide:

- Arbitrary CMD execution
- Arbitrary PowerShell execution
- Arbitrary shell execution
- `eval` or `exec`
- Unsafe Pickle deserialization
- Automatic administrator elevation
- Registry modification
- Windows Defender disabling
- Firewall disabling
- UAC bypass
- BitLocker modification
- Generic process killing
- Wi-Fi password retrieval
- Product-key extraction
- Event-log clearing
- CAPTCHA bypass
- Payment automation
- Banking automation
- Password entry automation
- Executable download automation
- Automatic execution of note or task content
- Destructive scheduled commands without current safety evaluation

---

# Testing

Activate the virtual environment and run:

```powershell
python -m ruff check .
python -m black --check .
python -m mypy src
python -m pytest -p no:cacheprovider
```

Do not use:

```powershell
pytest --basetemp
```

The project uses:

```powershell
python -m mypy src
```

as its production type-checking boundary.

## Manual testing recommendations

Use:

```text
E:\Omega-Test-Workspace
```

for file and folder tests.

Start with:

1. Terminal startup
2. GUI startup
3. Application opening
4. Read-only system information
5. Safe test-file creation
6. Browser navigation to a harmless page
7. Short timer
8. Short reminder
9. Note creation
10. Task creation
11. Voice mode
12. Recovery and undo

Save all work before testing power operations.

---

# Development status

Omega is currently paused for manual testing and stabilization after completing the major implementation through Phase 16.

## Completed

```text
Phase 0  — Foundation and environment
Phase 1  — Core command models
Phase 2  — Text session lifecycle
Phase 3  — Rule-based command understanding
Phase 4  — Safe application management
Phase 5  — Safe file management
Phase 6  — Safe folder management
Phase 7  — Centralized safety and permissions
Phase 8  — Recovery, Recycle Bin, and undo
Phase 9  — SQLite persistence foundation
Phase 10 — History, recovery, settings, and composition
Phase 11 — Desktop graphical interface
Phase 12 — Offline-first voice interaction
Phase 13 — Safe browser automation
Phase 14 — Windows system controls
Phase 15 — Reminders, alarms, timers, and scheduling
Phase 16 — Notes, tasks, and productivity
```

## Paused / planned

```text
Phase 17 — Local knowledge base and document search
Phase 18 — Email assistance
Phase 19 — Calendar and meeting management
Phase 20 — Clipboard, screenshots, and desktop utilities
Phase 21 — Workflow automation
Phase 22 — Plugin and skill architecture
Phase 23 — Local AI and advanced language intelligence
Phase 24 — User profiles and personalization
Phase 25 — Accessibility and multilingual support
Phase 26 — Security hardening and privacy controls
Phase 27 — Performance and reliability optimization
Phase 28 — Packaging and Windows installer
Phase 29 — Automated releases and CI/CD
Phase 30 — Final QA, documentation, and v1.0 release
```

Current priority:

> Run Omega manually, test completed capabilities, document bugs, and stabilize the existing system before adding more phases.

---

# Contributing

Contributions should preserve Omega’s safety-first architecture.

Before submitting a change:

```powershell
python -m ruff check .
python -m black --check .
python -m mypy src
python -m pytest -p no:cacheprovider
```

Contribution expectations:

- Do not bypass the safety gateway.
- Do not add arbitrary command execution.
- Do not weaken confirmations.
- Add tests for new behavior.
- Preserve terminal, GUI, and voice compatibility.
- Avoid import-time side effects.
- Keep optional dependencies optional.
- Do not commit runtime databases, logs, personal files, models, or secrets.

---

# Troubleshooting

## PowerShell blocks virtual-environment activation

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Omega module is not found

Install the project in editable mode:

```powershell
python -m pip install -e .
```

## Development tools are missing

When the `dev` optional group exists:

```powershell
python -m pip install -e ".[dev]"
```

## GUI does not start

Check available options:

```powershell
python -m omega --help
```

Then inspect the traceback and project logs.

## Voice mode is unavailable

Check:

- Microphone permissions
- Optional voice dependencies
- Configured speech-model path
- Audio input device
- Voice configuration
- Project voice documentation

Text and GUI modes should continue working when voice is unavailable.

## Brightness control is unavailable

Brightness control may not work with every external monitor or graphics configuration. Omega should return an unsupported-device response safely.

## Browser mode is unavailable

Check:

- Optional browser dependency
- Supported browser installation
- Browser backend setup
- Project browser documentation

Non-browser features should remain operational.

## Tests fail with Windows temporary-folder permission errors

Do not use `pytest --basetemp`.

Run:

```powershell
python -m pytest -p no:cacheprovider
```

---

# Known limitations

- Omega currently targets Windows.
- Voice accuracy depends on microphone quality and the configured local model.
- Voice dependencies may require separate installation.
- Brightness control may not support every display.
- Browser automation depends on the configured browser backend.
- Omega does not operate as an always-running Windows service.
- Notifications cannot be delivered while the computer is powered off.
- Scheduled tasks require Omega to start again for restart recovery.
- Natural-language parsing does not understand every possible sentence.
- Ambiguous commands may require clarification.
- Cloud synchronization is not currently included.
- Local document knowledge search is planned but paused.
- A packaged Windows installer is not yet available.

---

# Author

<div align="center">

### Anshuman Pattanayak

B.Tech Computer Science and Engineering  
AI/ML and Software Development Enthusiast

[![GitHub](https://img.shields.io/badge/GitHub-ItsAnshumanPattanayak-181717?logo=github)](https://github.com/ItsAnshumanPattanayak)

</div>

---

# License

No license should be claimed until a license file has been added to the repository.

Recommended options include:

- MIT License
- Apache License 2.0
- A proprietary “all rights reserved” notice

After selecting a license:

1. Add a `LICENSE` file.
2. Replace the license badge at the top.
3. Update this section with the chosen license.

---

<div align="center">

## Ω Omega

### Your computer. Your commands. Your control.

Built as a local, modular, and safety-first Windows assistant.

⭐ Star the repository if you find the project useful.

</div>
