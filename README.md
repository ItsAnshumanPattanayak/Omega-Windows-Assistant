<div align="center"> 

Ω OMEGA WINDOWS ASSISTANT

A privacy-first, local Windows automation assistant built with Python

<p>
  <strong>Control apps · Manage files · Organize tasks · Use offline voice · Build workflows · Stay in control</strong>
</p>

<p>
  <a href="https://github.com/ItsAnshumanPattanayak/Omega-Windows-Assistant">
    <img src="https://img.shields.io/badge/Version-2.0.0%20Unreleased-7c3aed?style=for-the-badge&logo=windows11&logoColor=white" alt="Version">
  </a>
  <img src="https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D4?style=for-the-badge&logo=windows11&logoColor=white" alt="Platform">
  <img src="https://img.shields.io/badge/Python-Local--First-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Privacy-By%20Default-16a34a?style=for-the-badge&logo=shield&logoColor=white" alt="Privacy">
</p>

<p>
  <a href="https://github.com/ItsAnshumanPattanayak/Omega-Windows-Assistant/actions">
    <img src="https://img.shields.io/github/actions/workflow/status/ItsAnshumanPattanayak/Omega-Windows-Assistant/ci.yml?branch=main&style=flat-square&label=CI" alt="CI">
  </a>
  <a href="https://github.com/ItsAnshumanPattanayak/Omega-Windows-Assistant/issues">
    <img src="https://img.shields.io/github/issues/ItsAnshumanPattanayak/Omega-Windows-Assistant?style=flat-square" alt="Issues">
  </a>
  <a href="https://github.com/ItsAnshumanPattanayak/Omega-Windows-Assistant/stargazers">
    <img src="https://img.shields.io/github/stars/ItsAnshumanPattanayak/Omega-Windows-Assistant?style=flat-square" alt="Stars">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/github/license/ItsAnshumanPattanayak/Omega-Windows-Assistant?style=flat-square" alt="License">
  </a>
</p>

Omega helps you operate Windows through natural language without surrendering control of your files, data, or decisions.

## Omega V2 Phase 1 GUI foundation

The V2 development branch now includes an isolated animated GUI foundation built for
Python 3.11. Activate `.venv-v2`, then run `python -m omega --v2-gui`; the existing
terminal and Version 1 GUI remain available. The animation is always muted, and the
Phase 1 controls only demonstrate typed UI states—they do not access a microphone or
add new automation. See [the V2 GUI guide](docs/v2_gui.md) for setup, architecture,
limitations, and troubleshooting.

Features •Quick Start •GUI •Voice •Safety •Commands •Build •Documentation

</div>

✨ What is Omega?

Omega Windows Assistant is a privacy-first desktop assistant for Windows 10 and Windows 11. It combines safe local automation, structured confirmations, offline voice recognition, productivity tools, workflows, personalization, accessibility options, and optional local AI in one extensible Python application.

Omega can:

open and close registered Windows applications;

create, read, update, move, rename, and delete files safely;

manage folders, notes, tasks, reminders, and scheduled actions;

search locally indexed documents;

create privacy-safe email drafts and calendar proposals;

use clipboard and screenshot utilities;

run reviewed multi-step workflows;

support optional plugins and local AI;

operate through terminal, chat-style GUI, or offline voice mode.

Sensitive, destructive, or external actions remain behind explicit confirmation.

🚦 Project Status

Item

Status

Current source version

2.0.0

Release status

Unreleased source implementation

Stable source baseline

1.0.0

Supported platform

Windows 10 and Windows 11

Source execution

✅ Available

Terminal mode

✅ Available

GUI mode

✅ Available

Offline voice architecture

✅ Available

Official v2 installer

⏳ Not yet published

Official v2 portable package

⏳ Not yet published

Version 2.0.0 has not yet been tagged or published. Installer and portable downloads become available only after verified artifacts are attached to an official GitHub Release.

## Future Windows installer download

The verified installer filename will be
`Omega-Windows-Assistant-Setup-v2.0.0.exe`. It installs **Omega Windows Assistant**
for the current Windows user under `%LOCALAPPDATA%\Programs\Omega`, creates a Start
Menu shortcut, and offers an optional Desktop shortcut. Python, the source repository,
and the development virtual environment are not required after installation.

No public installer release exists yet. When an installer is attached to an official
[Omega release](https://github.com/ItsAnshumanPattanayak/Omega-Windows-Assistant/releases),
verify its published SHA-256 checksum before running it. Current local builds are
unsigned and may trigger Windows SmartScreen; bypassing Windows security is not
recommended. User data under `%LOCALAPPDATA%\Omega` is preserved during upgrades and
uninstall. The large optional Vosk speech model is not bundled.

## Developer

**Anshuman Pattanayak**

GitHub: https://github.com/ItsAnshumanPattanayak

🌟 Feature Highlights

<table>
<tr>
<td width="50%" valign="top">

🖥️ Windows Control

Open and close registered applications

App-name-only interaction

Approved aliases

Website and browser actions

Terminal and graphical operation

</td>
<td width="50%" valign="top">

📁 Safe File Management

Create, read, write, move, and rename files

Create and manage folders

Search files and directories

Confirm deletion and overwriting

Restrict operations to approved locations

</td>
</tr>
<tr>
<td width="50%" valign="top">

✅ Personal Productivity

Notes and tasks

Reminders and schedules

Local knowledge search

Clipboard and screenshots

Personalization and preferences

</td>
<td width="50%" valign="top">

🔗 Extensible Workflows

Multi-step workflows

Step-level safety checks

Reviewed local plugins

Optional email and calendar providers

Optional local AI runtime

</td>
</tr>
<tr>
<td width="50%" valign="top">

🎙️ Offline Voice

Vosk-based speech recognition

Windows SAPI speech output

Local voice-model configuration

Microphone diagnostics

Confidence and error-state reporting

</td>
<td width="50%" valign="top">

♿ Accessible Experience

Keyboard-friendly navigation

Font scaling

High contrast

Reduced motion

Screen-reader-aware terminal output

Locale and language architecture

</td>
</tr>
</table>

🆕 Version 2 Experience

Version 2 preserves Omega’s Version 1 safety and persistence architecture while improving the interaction layer.

Natural app-name prompts

Typing or saying an exact registered application name or approved alias creates a temporary prompt:

You: Notepad
Omega: Do you want to open Notepad?
You: Yes please.
Omega: Notepad opened successfully.

Contextual responses such as:

yes please
open it
no
never mind

apply only to the active prompt. They cannot approve an unrelated sensitive action.

Redesigned conversation interface

The conversation occupies most of the window.

Omega messages and user messages are visually separated.

Recent activity can be collapsed.

Secondary actions are grouped instead of permanently filling the interface.

More Activities

More Activities groups existing actions into eight keyboard-accessible categories, reducing top-level button clutter while keeping capabilities easy to reach.

Improved offline voice diagnostics

Voice mode reports:

selected model;

microphone device;

sample rate;

readiness;

transcript;

low-confidence state;

recognition errors.

The selected development model is:

vosk-model-en-us-0.22-lgraph

The model is not distributed through Git, the installer, or Omega itself. Recognition quality still requires physical microphone testing.

🧭 How Omega Works

flowchart LR
    U[User] --> I{Interface}
    I --> T[Terminal]
    I --> G[GUI]
    I --> V[Offline Voice]

    T --> N[Command Understanding]
    G --> N
    V --> N

    N --> C{Confirmation Required?}
    C -- No --> E[Safe Execution Layer]
    C -- Yes --> P[Scoped Confirmation Prompt]
    P -- Approved --> E
    P -- Rejected / Expired --> X[Cancel Safely]

    E --> A[Applications]
    E --> F[Files & Folders]
    E --> R[Reminders & Tasks]
    E --> W[Workflows]
    E --> O[Optional Providers]
    E --> L[Optional Local AI]

    A --> Z[Local Result]
    F --> Z
    R --> Z
    W --> Z
    O --> Z
    L --> Z

🔐 Safety and Privacy

Omega follows a local-first, confirmation-controlled design.

Omega does not

automatically send emails;

automatically modify calendar events;

execute arbitrary shell or PowerShell commands;

automatically download AI models;

automatically download voice models;

upload personal files by default;

enable telemetry by default;

synchronize personal data to the cloud by default;

continuously monitor the clipboard;

capture screenshots secretly;

enable plugins automatically after installation.

Confirmation-protected actions

Actions such as the following require review and confirmation:

deletion;

overwriting;

external communication;

email sending;

calendar mutation;

plugin installation;

other sensitive or destructive operations.

[!WARNING]Approved Python plugins run as trusted same-process code and are not perfectly sandboxed. Install plugins only from sources you trust.

⚙️ System Requirements

Required

Requirement

Details

Operating system

Windows 10 or Windows 11

Python

A version supported by the project

Shell

PowerShell

Version control

Git

Internet

Required for initial dependency installation

Optional

microphone for voice mode;

compatible Vosk model;

installed Windows SAPI voice;

local AI runtime and compatible model;

email-provider credentials;

calendar-provider credentials;

Inno Setup for installer builds;

PyInstaller for application bundles.

🚀 Quick Start

Clone and install

git clone https://github.com/ItsAnshumanPattanayak/Omega-Windows-Assistant.git
cd Omega-Windows-Assistant

python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e .

For development tools:

python -m pip install -e ".[dev]"

Verify the installation

python -m omega --version
python -m omega --help
python -m omega --gui-check

Expected version:

omega-windows-assistant 2.0.0

Additional diagnostics:

python -m omega --security-check
python -m omega --performance-check

[!IMPORTANT]Do not commit the .venv/ directory.

💻 Terminal Mode

.\.venv\Scripts\Activate.ps1
python -m omega

Example session:

You: Hello Omega

Omega: Good evening, Anshuman. How can I help you?

You: Open Chrome

Omega: Chrome opened successfully.

You: Create a folder named College Notes

Omega: The folder proposal is ready.

You: Show my tasks

Omega: Here are your current tasks.

You: Shut down Omega

Omega: Shutting down safely.

After activation, commands generally do not need the word Omega before every instruction.

The greeting can depend on:

current time;

active user profile;

display-name preference;

greeting preference;

response-style preference.

🪟 Graphical Interface

Start GUI mode:

python -m omega --gui

Check GUI availability:

python -m omega --gui-check

The GUI can be used to:

enter commands and read responses;

approve or cancel confirmations;

manage notes, tasks, and reminders;

search local knowledge;

manage workflows and plugins;

configure personalization and accessibility;

review local AI status;

review email drafts and calendar proposals.

Close the GUI through its normal close control or Omega’s safe shutdown option.

🎙️ Offline Voice Mode

Omega uses Vosk for offline speech recognition and Windows SAPI for speech output.

Install voice dependencies

.\.venv\Scripts\Activate.ps1
python -m pip install vosk sounddevice comtypes

Add a voice model

Download a compatible model manually and extract it to:

data/voice_models/vosk-model-en-us-0.22-lgraph

Example configuration:

voice:
  model_path: vosk-model-en-us-0.22-lgraph

Voice models are:

not included in the repository;

not downloaded automatically;

not committed to GitHub;

selected and managed locally.

Check microphone devices

python -m omega --list-audio-devices

Start voice mode

python -m omega --voice

Voice limitations

A microphone is required.

Accuracy depends on the microphone and environment.

The Vosk model must match the spoken language.

Available voices depend on installed Windows SAPI voices.

Terminal and GUI modes remain available without voice configuration.

🧪 First-Time Setup

After launching Omega:

Set your display name.

Select your time zone.

Select your preferred browser.

Select your preferred code editor.

Configure safe workspace folders.

Configure voice only when needed.

Configure local AI only when needed.

Connect email and calendar only when needed.

Review plugin permissions before enabling plugins.

Review privacy and retention preferences.

Test with a harmless command.

Example:

Hello Omega
Show my preferences
Call me Anshuman
Set my time zone to Asia/Kolkata
Set my preferred browser to Chrome
Set my default editor to Visual Studio Code
Use concise responses
Use 24-hour time
Show my tasks
Shut down Omega

💬 Example Commands

<details>
<summary><strong>🖥️ Applications</strong></summary>

Open Chrome
Close Chrome
Open Visual Studio Code
Open Notepad
Show registered applications

</details>

<details>
<summary><strong>📄 Files</strong></summary>

Create a file named notes.txt
Open notes.txt
Read notes.txt
Write Hello Omega to notes.txt
Search for notes.txt
Show file information
Rename notes.txt
Move notes.txt
Delete notes.txt

Deletion, replacement, and overwrite operations require confirmation.

</details>

<details>
<summary><strong>📁 Folders</strong></summary>

Create a folder named College Notes
Open my Projects folder
List my Documents folder
Search for a folder named Assignments
Rename a folder
Move a folder
Delete a folder

</details>

<details>
<summary><strong>📝 Notes and Tasks</strong></summary>

Create a note
Show my notes
Open the latest note
Create a task
Show my tasks
Show today's tasks
Mark this task completed

</details>

<details>
<summary><strong>⏰ Reminders and Scheduling</strong></summary>

Create a reminder
Show my reminders
Remind me to study at 7 PM
Show scheduled actions
Cancel this reminder

</details>

<details>
<summary><strong>🔎 Local Knowledge</strong></summary>

Show knowledge sources
Add this document to my knowledge base
Search my knowledge base for authentication
Explain this knowledge result
Remove this knowledge source

User documents remain local unless another provider is explicitly configured.

</details>

<details>
<summary><strong>✉️ Email Assistance</strong></summary>

Show recent emails
Search emails from Rahul
Summarize this email
Create an email draft
Improve this draft
Show this draft
Send this draft

Sending requires explicit confirmation.

</details>

<details>
<summary><strong>📅 Calendar Assistance</strong></summary>

Show today's calendar
Show this week's calendar
Check my availability
Create a calendar proposal
Update this event proposal
Create this calendar event
Delete this event

Calendar creation, updates, deletion, and invitation responses require confirmation.

</details>

<details>
<summary><strong>📋 Clipboard and Screenshots</strong></summary>

Copy this text to the clipboard
Show clipboard text
Clear the clipboard
Take a screenshot
Show display information
Show screenshots
Delete this screenshot

Omega does not continuously monitor the clipboard or screen.

</details>

<details>
<summary><strong>🔁 Workflows</strong></summary>

List my workflows
Show Morning Setup
Preview Morning Setup
Validate Morning Setup
Run Morning Setup
Pause this workflow
Resume this workflow
Cancel this workflow
Show workflow history

Workflow approval never bypasses step-level safety checks.

</details>

<details>
<summary><strong>🧩 Plugins</strong></summary>

List plugins
Show plugin details
Validate this plugin
Install plugin from this path
Show plugin permissions
Enable this plugin
Disable this plugin
Remove this plugin

New plugins remain disabled until reviewed and approved.

</details>

<details>
<summary><strong>🧠 Local AI</strong></summary>

Show local AI status
Show available local AI models
Summarize this note
Explain this document
Improve this email draft
Suggest tasks from this note
Suggest a workflow
Cancel AI generation

Local AI output is treated as a proposal—not authorization.

</details>

<details>
<summary><strong>🎨 Personalization and Accessibility</strong></summary>

Call me Anshuman
Use concise responses
Use detailed responses
Use 24-hour time
Set my time zone to Asia/Kolkata
Set my preferred browser to Chrome
Enable quiet hours
Enable high contrast
Increase text size
Enable screen-reader mode
Disable terminal colors
Speak more slowly
Show keyboard shortcuts

</details>

🧩 Optional Components

Component

Requirement

Safety model

Voice

Vosk, microphone, model, SAPI

Local and optional

Local AI

Approved runtime and model

Output remains a proposal

Email

User-owned provider configuration

Draft → review → confirm → send

Calendar

User-owned provider configuration

Search → proposal → review → confirm

Knowledge base

Local documents

Local indexing by default

Plugins

Trusted reviewed plugin

Validate → review → approve → enable

Workflows

Supported Omega actions

Step-level confirmations remain active

Omega workflows are not an unrestricted scripting engine. They do not support arbitrary PowerShell, shell execution, Python execution, SQL execution, network commands, or infinite loops.

📦 Installation Options

1. Run from source

Recommended for developers, contributors, and testers.

git clone https://github.com/ItsAnshumanPattanayak/Omega-Windows-Assistant.git
cd Omega-Windows-Assistant
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m omega

2. Windows installer

When an official installer is published:

Open the repository’s Releases page.

Download the installer and SHA256SUMS.txt.

Verify the SHA-256 checksum.

Run the installer.

Open Omega from the Start Menu.

Example checksum command:

Get-FileHash ".\Omega-Windows-Assistant-Setup-1.0.0.exe" -Algorithm SHA256

[!CAUTION]Omega binaries may be unsigned. Continue through SmartScreen only when the file came from the official repository, the version is correct, and the checksum matches. Do not disable Windows security globally.

3. Portable build

When published:

Download portable ZIP
→ Verify checksum
→ Extract to a user-writable directory
→ Start Omega

Do not extract a portable build into:

C:\Windows
C:\Program Files
C:\Program Files (x86)

🛠️ Build and Package

Install packaging dependencies

.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[packaging]"

Or:

python -m pip install pyinstaller

Build the Windows application

powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\build_windows.ps1

Verify the package

powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\verify_package.ps1

Inspect output

Get-ChildItem .\dist -Recurse

Example executable checks:

.\dist\Omega\Omega.exe --version
.\dist\Omega\Omega.exe --help
.\dist\Omega\Omega.exe --gui-check

Build the installer

Install Inno Setup, then verify:

Get-Command ISCC.exe

Build:

powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\build_installer.ps1

Check output:

Get-ChildItem .\installer\output -Recurse

Test the installer manually on a clean Windows computer or virtual machine.

🧹 Files Excluded from Releases

Never include personal or generated runtime data:

.venv/
.env
data/*.db
build/
dist/
installer/output/
*.log
credentials
tokens
voice models
AI models
screenshots
clipboard history
private plugins
plugin runtime storage
personal profiles
workflow exports
private knowledge documents
__pycache__/
.pytest_cache/
machine-specific configuration

✅ Development Verification

.\.venv\Scripts\Activate.ps1

python -m black --check .
python -m ruff check .
python -m mypy src
python -m pytest -p no:cacheprovider

python -m omega --help
python -m omega --version
python -m omega --gui-check
python -m omega --security-check
python -m omega --performance-check

Do not use:

pytest --basetemp

The project has previously encountered Windows access-control issues with that option.

Final v1.0.0 source verification

Collected: 1,730
Passed:    1,720
Failed:    0
Skipped:   10
Xfailed:   0

This confirms the source release-preparation state. It does not replace clean-machine installer testing, packaged-executable testing, live provider tests, microphone testing, local-model testing, or accessibility certification.

🔄 Update Omega

cd Omega-Windows-Assistant
git status
git fetch origin
git pull --ff-only origin main

.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m omega --version

Do not pull blindly when unresolved local modifications exist.

🗑️ Uninstall

For an installer-based installation:

Windows Settings
→ Apps
→ Installed apps
→ Omega Windows Assistant
→ Uninstall

Application removal should preserve user data by default. Back up important local data before manually deleting an Omega data directory.

🧯 Troubleshooting

<details>
<summary><strong>PowerShell cannot activate the environment</strong></summary>

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1

</details>

<details>
<summary><strong>Python is not found</strong></summary>

Install a supported Python version, enable Add Python to PATH, and reopen PowerShell.

</details>

<details>
<summary><strong>No module named omega</strong></summary>

.\.venv\Scripts\Activate.ps1
python -m pip install -e .

</details>

<details>
<summary><strong>GUI does not start</strong></summary>

python -m omega --gui-check

Inspect the displayed diagnostic.

</details>

<details>
<summary><strong>Voice model is missing</strong></summary>

Download a compatible Vosk model manually and configure its local path.

</details>

<details>
<summary><strong>Microphone is not detected</strong></summary>

python -m omega --list-audio-devices

Also check Windows microphone privacy permissions.

</details>

<details>
<summary><strong>Local AI, email, or calendar is unavailable</strong></summary>

Configure the relevant optional provider or runtime. Omega’s deterministic local features remain usable without them.

</details>

<details>
<summary><strong>SmartScreen blocks the installer</strong></summary>

Continue only after confirming the official source, version, and checksum. Never disable Windows security globally.

</details>

<details>
<summary><strong>Internet connection is lost</strong></summary>

Configured local features should continue working. Provider-dependent email, calendar, Git, and remote services may fail gracefully.

</details>

⚠️ Known Limitations

Windows-focused application;

installer binaries may be unsigned;

voice requires a separately downloaded model;

local AI requires a separately configured runtime and model;

email and calendar require provider configuration;

approved same-process Python plugins are not perfectly sandboxed;

prompt injection cannot be eliminated completely;

accessibility behavior partly depends on tkinter and Windows;

additional-language coverage may be partial;

no cloud synchronization by default;

no automatic AI-model download;

no automatic voice-model download;

no OCR;

no continuous screen understanding;

no background surveillance;

no automatic email sending;

no automatic calendar mutation.

See Known limitations.

📚 Documentation

Area

Document

Architecture

docs/architecture.md

Development roadmap

docs/development_roadmap.md

Installation

docs/installation.md

Packaging

docs/packaging.md

CI/CD

docs/ci_cd.md

Releasing

docs/releasing.md

Release checklist

docs/release_checklist.md

Release readiness

docs/release_readiness.md

Version 1 release notes

docs/releases/v1.0.0.md

Version 2 upgrade notes

docs/releases/v2.0.0.md

Command reference

docs/command_reference.md

Version history

docs/version_history.md

Security

docs/security.md

Threat model

docs/threat_model.md

Performance

docs/performance.md

Accessibility

docs/accessibility.md

Localization

docs/localization.md

Personalization

docs/personalization.md

Local AI

docs/local_ai.md

Plugins

docs/plugins.md

Plugin development

docs/plugin_development.md

Workflows

docs/workflows.md

🔒 Security Reporting

Please do not publicly disclose sensitive vulnerabilities before giving the project owner a reasonable opportunity to investigate.

Read:

Security policy

Security documentation

Threat model

🗺️ Release Flow

flowchart TD
    A[Clean working tree] --> B[Run formatting, linting, typing, and tests]
    B --> C[Run security and performance checks]
    C --> D[Push approved commit]
    D --> E[Confirm GitHub Actions]
    E --> F[Build Windows application]
    F --> G[Verify package]
    G --> H[Build installer and portable artifact]
    H --> I[Generate SHA-256 checksums]
    I --> J[Test on clean Windows system]
    J --> K[Create and push release tag]
    K --> L[Publish verified GitHub Release]

🤝 Contributing

Contributions should preserve Omega’s core principles:

Local-first behavior

Explicit user control

Scoped confirmations

Safe defaults

No hidden monitoring

Clear failure handling

Tested Windows behavior

Before submitting changes:

python -m black --check .
python -m ruff check .
python -m mypy src
python -m pytest -p no:cacheprovider

👨‍💻 Author

<div align="center">

Anshuman Pattanayak



</div>

📄 License

This project is distributed under the license included in the repository.

See LICENSE.

<div align="center">

Ω Your Windows. Your Commands. Your Control.

Built for local productivity without sacrificing privacy.

⬆ Back to top

</div>
