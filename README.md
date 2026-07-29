# Omega Windows Assistant

Omega is a privacy-first Windows desktop assistant built with Python. It allows users to control applications, manage files and folders, create notes and tasks, schedule reminders, search local documents, use offline voice commands, create workflows, connect optional email and calendar providers, and use optional local AI features.

Omega is designed to work locally and safely. Sensitive, destructive, and external actions require confirmation before execution.

## Current Source Version

```text
Omega Windows Assistant v2.0.0
Status: Unreleased source implementation
Platform: Windows 10 and Windows 11
```

Omega can currently be used directly from its source code. Version 1.0.0 remains the
stable source baseline; Version 2.0.0 has not been tagged or published.

The Windows installer and portable package become available only after they are built and attached to an official GitHub Release.

## Main Features

- Open and close registered Windows applications
- Ask before opening an application entered by name or approved alias
- Create, read, update, move, rename, and delete files safely
- Create and manage folders
- Open websites and perform supported browser actions
- Create notes, tasks, and reminders
- Schedule supported actions
- Search locally indexed documents
- Create privacy-safe email drafts
- View calendars and create event proposals
- Use clipboard and screenshot utilities
- Build and run multi-step workflows
- Install reviewed local plugins
- Use optional local AI
- Use offline voice commands
- Personalize Omega’s responses and defaults
- Use accessibility and multilingual settings
- Use a chat-oriented graphical interface or terminal mode

## Version 2 Experience

Version 2 keeps the Version 1 safety and persistence architecture while improving
the desktop interaction layer:

- entering an exact registered application name or alias creates an expiring prompt
  such as `Do you want to open Notepad?`;
- contextual replies such as `yes please`, `open it`, `no`, or `never mind` apply
  only to that prompt and cannot approve an unrelated sensitive action;
- the GUI gives the conversation most of the window, aligns user and Omega messages
  distinctly, and lets the recent-activity pane collapse;
- **More Activities** groups all existing actions into eight keyboard-accessible
  categories instead of permanently displaying a large button grid;
- offline voice mode reports model, microphone, sample-rate, readiness, transcript,
  low-confidence, and error state information more clearly.

The selected development model is the official
`vosk-model-en-us-0.22-lgraph`. It is not distributed by Git, the installer, or
Omega itself. Recognition quality still requires real microphone testing.

## Safety and Privacy

Omega follows a local-first and confirmation-controlled design.

Omega does not:

- Automatically send emails
- Automatically modify calendar events
- Execute arbitrary shell or PowerShell commands
- Automatically download AI models
- Automatically download voice models
- Upload personal files by default
- Enable telemetry by default
- Synchronize personal data to the cloud by default
- Monitor the clipboard continuously
- Capture screenshots secretly
- Enable plugins automatically after installation

Sensitive operations such as deletion, overwriting, email sending, calendar modification, plugin installation, and other external actions require confirmation.

> Approved Python plugins run as trusted same-process code. They are not perfectly sandboxed. Install plugins only from sources you trust.

---

# System Requirements

## Required

- Windows 10 or Windows 11
- Python supported by the project
- PowerShell
- Git
- Internet access for initial package installation

## Optional

- Microphone for voice mode
- Compatible Vosk model for offline speech recognition
- Installed Windows SAPI voice for speech output
- Local AI runtime and model for AI features
- Provider credentials for optional email integration
- Provider credentials for optional calendar integration
- Inno Setup for building the Windows installer
- PyInstaller for building the Windows application bundle

---

# Quick Start for the Project Owner

The current local project is located at:

```text
E:\project Omega
```

Open PowerShell and run:

```powershell
cd "E:\project Omega"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m omega
```

Activate Omega by typing:

```text
Hello Omega
```

Stop Omega safely by typing:

```text
Shut down Omega
```

---

# Method 1 — Run Omega From Source

This method is suitable for developers, contributors, testers, and users who already have Python installed.

## Step 1: Clone the repository

```powershell
git clone https://github.com/ItsAnshumanPattanayak/Omega-Windows-Assistant.git
cd Omega-Windows-Assistant
```

## Step 2: Create a virtual environment

```powershell
python -m venv .venv
```

## Step 3: Activate the virtual environment

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

The execution-policy command affects only the current PowerShell window.

Whenever you reopen the project, activate the environment again:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Step 4: Upgrade pip

```powershell
python -m pip install --upgrade pip
```

## Step 5: Install Omega

```powershell
python -m pip install -e .
```

For development tools:

```powershell
python -m pip install -e ".[dev]"
```

Do not commit the following directory:

```text
.venv/
```

## Step 6: Verify the installation

```powershell
python -m omega --version
python -m omega --help
python -m omega --gui-check
```

Expected version:

```text
omega-windows-assistant 2.0.0
```

Additional diagnostic commands may include:

```powershell
python -m omega --security-check
python -m omega --performance-check
```

---

# Start Omega in Terminal Mode

Open PowerShell:

```powershell
cd "E:\project Omega"
.\.venv\Scripts\Activate.ps1
python -m omega
```

For another cloned copy:

```powershell
cd Omega-Windows-Assistant
.\.venv\Scripts\Activate.ps1
python -m omega
```

Example interaction:

```text
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
```

The greeting depends on:

- Current time
- Active user profile
- Display-name preference
- Greeting preference
- Response-style preference

After activation, commands generally do not need the word “Omega” before every instruction.

---

# Start Omega in GUI Mode

Run:

```powershell
cd "E:\project Omega"
.\.venv\Scripts\Activate.ps1
python -m omega --gui
```

Check whether the GUI is available:

```powershell
python -m omega --gui-check
```

The GUI can be used to:

- Enter commands
- Read Omega’s responses
- Approve or cancel confirmations
- Manage notes and tasks
- View reminders
- Search local knowledge
- Manage workflows
- Manage plugins
- Configure personalization
- Configure accessibility
- View local AI status
- Review email drafts
- Review calendar proposals

Close the GUI normally using its close button or Omega’s safe shutdown option.

---

# Start Omega in Voice Mode

Voice mode is optional.

Omega uses offline speech recognition through Vosk and Windows speech output through SAPI.

## Step 1: Install the voice dependencies

Activate the environment:

```powershell
cd "E:\project Omega"
.\.venv\Scripts\Activate.ps1
```

Install the required packages:

```powershell
python -m pip install vosk sounddevice comtypes
```

## Step 2: Download a Vosk model

Download a compatible Vosk speech-recognition model manually.

Example English model:

```text
vosk-model-en-us-0.22-lgraph
```

Extract it into:

```text
data/voice_models/vosk-model-en-us-0.22-lgraph
```

Voice models are:

- Not included in the repository
- Not downloaded automatically
- Not committed to GitHub
- Selected and managed locally by each user

## Step 3: Configure the model

Set the voice model path in the user configuration.

Example:

```yaml
voice:
  model_path: vosk-model-en-us-0.22-lgraph
```

Use a model that matches the configured recognition language.

## Step 4: Check microphone devices

```powershell
python -m omega --list-audio-devices
```

Select the correct input device in Omega’s configuration when required.

## Step 5: Start voice mode

```powershell
python -m omega --voice
```

Example:

```text
You: Hello Omega

Omega: Good morning. How can I help you?

You: Open Chrome

You: Show today's tasks

You: Create a note

You: Shut down Omega
```

After activation, you normally do not need to repeat “Omega” before every command.

## Voice limitations

- A microphone is required
- Recognition accuracy depends on the microphone and environment
- The configured Vosk model must match the spoken language
- Available text-to-speech voices depend on installed Windows SAPI voices
- Text and GUI modes remain available when voice is not configured

---

# Method 2 — Run Omega Using the Windows Installer

## When an official installer is available

Open the official GitHub Releases page:

```text
https://github.com/ItsAnshumanPattanayak/Omega-Windows-Assistant/releases
```

Download the installer for the required version.

Example expected filename:

```text
Omega-Windows-Assistant-Setup-1.0.0.exe
```

Also download:

```text
SHA256SUMS.txt
```

## Verify the installer checksum

Example PowerShell command:

```powershell
Get-FileHash ".\Omega-Windows-Assistant-Setup-1.0.0.exe" -Algorithm SHA256
```

Compare the displayed hash with the value inside:

```text
SHA256SUMS.txt
```

## Install Omega

1. Double-click the installer.
2. Review the publisher and version.
3. Continue only when it came from the official repository release.
4. Select the installation directory.
5. Choose whether to create a desktop shortcut.
6. Finish the installation.
7. Open Omega from:

```text
Start Menu → Omega Windows Assistant
```

You may also use the desktop shortcut when selected during installation.

## Windows SmartScreen warning

Omega binaries may be unsigned.

Windows SmartScreen may display a warning. Continue only when:

- You downloaded the installer from the official GitHub repository
- The version is correct
- The SHA-256 checksum matches
- You trust the release source

Do not disable Windows Defender or SmartScreen globally.

## When an installer is not available

Run Omega from the source code or build the installer locally using the instructions below.

---

# Method 3 — Portable Build

When a portable archive is attached to a GitHub Release:

1. Download the portable `.zip` file.
2. Verify its SHA-256 checksum.
3. Extract it into a normal user-writable folder.
4. Do not extract it into protected system folders.
5. Open the extracted Omega executable.

Example expected filename:

```text
Omega-Windows-Assistant-Portable-1.0.0.zip
```

Portable builds should not be placed inside:

```text
C:\Windows
C:\Program Files
C:\Program Files (x86)
```

Use a user-writable location such as:

```text
C:\Users\<username>\Applications\Omega
```

Portable availability depends on the published release artifacts.

---

# First-Time Setup

After starting Omega for the first time, configure only the features you need.

Recommended setup:

1. Set your display name.
2. Select your time zone.
3. Select your preferred browser.
4. Select your preferred code editor.
5. Configure safe workspace folders.
6. Configure voice only when needed.
7. Configure local AI only when needed.
8. Connect email only when needed.
9. Connect calendar only when needed.
10. Review plugin permissions before enabling plugins.
11. Review privacy and retention preferences.
12. Test Omega using a harmless command.

Example commands:

```text
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
```

---

# Example Commands

Command availability may depend on the installed version, active configuration, registered applications, and enabled optional features.

## Application Commands

```text
Open Chrome
Close Chrome
Open Visual Studio Code
Open Notepad
Show registered applications
```

## File Commands

```text
Create a file named notes.txt
Open notes.txt
Read notes.txt
Write Hello Omega to notes.txt
Search for notes.txt
Show file information
Rename notes.txt
Move notes.txt
Delete notes.txt
```

Deletion, replacement, and overwrite operations require confirmation.

## Folder Commands

```text
Create a folder named College Notes
Open my Projects folder
List my Documents folder
Search for a folder named Assignments
Rename a folder
Move a folder
Delete a folder
```

Destructive folder operations require confirmation.

## Notes and Tasks

```text
Create a note
Show my notes
Open the latest note
Create a task
Show my tasks
Show today's tasks
Mark this task completed
```

## Reminders and Scheduling

```text
Create a reminder
Show my reminders
Remind me to study at 7 PM
Show scheduled actions
Cancel this reminder
```

## Local Knowledge Base

```text
Show knowledge sources
Add this document to my knowledge base
Search my knowledge base for authentication
Explain this knowledge result
Remove this knowledge source
```

User documents remain local unless the user explicitly configures another provider.

## Email Assistance

```text
Show recent emails
Search emails from Rahul
Summarize this email
Create an email draft
Improve this draft
Show this draft
Send this draft
```

Sending email requires explicit confirmation.

Omega should not send an email automatically.

## Calendar Assistance

```text
Show today's calendar
Show this week's calendar
Check my availability
Create a calendar proposal
Update this event proposal
Create this calendar event
Delete this event
```

Calendar creation, updates, deletion, and invitation responses require confirmation.

## Clipboard and Screenshots

```text
Copy this text to the clipboard
Show clipboard text
Clear the clipboard
Take a screenshot
Show display information
Show screenshots
Delete this screenshot
```

Clearing clipboard content and deleting screenshots may require confirmation.

Omega does not continuously monitor the clipboard or screen.

## Workflows

```text
List my workflows
Show Morning Setup
Preview Morning Setup
Validate Morning Setup
Run Morning Setup
Pause this workflow
Resume this workflow
Cancel this workflow
Show workflow history
```

Sensitive workflow steps still require their own confirmation.

A workflow-level approval does not bypass step-level safety checks.

## Plugins

```text
List plugins
Show plugin details
Validate this plugin
Install plugin from this path
Show plugin permissions
Enable this plugin
Disable this plugin
Remove this plugin
```

New plugins remain disabled until reviewed and approved.

## Local AI

```text
Show local AI status
Show available local AI models
Summarize this note
Explain this document
Improve this email draft
Suggest tasks from this note
Suggest a workflow
Cancel AI generation
```

Local AI output is treated as a proposal, not authorization.

Generated actions are not executed automatically.

## Personalization

```text
Call me Anshuman
Use concise responses
Use detailed responses
Use 24-hour time
Set my time zone to Asia/Kolkata
Set my preferred browser to Chrome
Enable quiet hours
Show my preferences
Reset voice preferences
```

## Accessibility

```text
Enable high contrast
Increase text size
Decrease text size
Enable screen-reader mode
Disable terminal colors
Show keyboard shortcuts
Speak more slowly
Use concise spoken responses
```

---

# Optional Features

## Voice

Requires:

- Microphone
- Vosk package
- Compatible Vosk model
- Sounddevice
- Windows SAPI voice

Voice is local and optional.

## Local AI

Requires:

- Approved local AI runtime
- Compatible local model
- Sufficient system memory
- Explicit configuration

Omega does not automatically download AI models.

When AI is unavailable, deterministic Omega features remain usable.

## Email

Requires the user’s own provider configuration.

Email flow:

```text
Read or search → Create draft → Review → Confirm → Send
```

Omega does not automatically send email.

## Calendar

Requires the user’s own calendar-provider configuration.

Calendar flow:

```text
Search → Create proposal → Validate → Review → Confirm → Create or update
```

Omega does not automatically modify calendar data.

## Knowledge Base

Knowledge documents are indexed locally.

Users should never commit private knowledge documents or generated knowledge databases to GitHub.

## Plugins

Plugins must be:

1. Selected explicitly
2. Validated
3. Reviewed
4. Permission-approved
5. Enabled manually

Only install plugins from trusted sources.

## Workflows

Workflows combine supported Omega actions into ordered multi-step operations.

Omega workflows are not an unrestricted scripting engine.

They do not support arbitrary:

- PowerShell
- Shell execution
- Python execution
- SQL execution
- Network commands
- Infinite loops

## Accessibility and Languages

Omega includes accessibility and localization architecture.

Features may include:

- Keyboard navigation
- Font scaling
- High contrast
- Reduced motion
- Screen-reader-friendly terminal output
- Voice-rate configuration
- Locale-aware date and time formatting
- English interface
- Partial additional language support

Formal accessibility certification is not claimed.

---

# Build the Windows Application

Before building, commit or safely preserve important source changes.

Do not include personal runtime data in a build.

## Step 1: Activate the environment

```powershell
cd "E:\project Omega"
.\.venv\Scripts\Activate.ps1
```

## Step 2: Install packaging tools

When the project provides a packaging dependency group:

```powershell
python -m pip install -e ".[packaging]"
```

Otherwise install the required packaging tool manually:

```powershell
python -m pip install pyinstaller
```

Verify:

```powershell
python -m PyInstaller --version
```

## Step 3: Build the application

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\build_windows.ps1
```

## Step 4: Verify the package

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\verify_package.ps1
```

## Step 5: Inspect the output

```powershell
Get-ChildItem .\dist -Recurse
```

Generated files may appear under:

```text
build/
dist/
```

Do not commit generated build output.

Test the actual executable generated inside `dist`.

Example:

```powershell
.\dist\Omega\Omega.exe --version
.\dist\Omega\Omega.exe --help
.\dist\Omega\Omega.exe --gui-check
```

Use the actual executable path produced by the build.

---

# Build the Windows Installer

Omega’s installer is designed for Windows.

The installer may use Inno Setup.

## Step 1: Install Inno Setup

Install Inno Setup from its official source.

After installation, check:

```powershell
Get-Command ISCC.exe
```

When it is not available through `PATH`, check its default location:

```powershell
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /?
```

## Step 2: Build the application first

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\build_windows.ps1
```

## Step 3: Verify the application package

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\verify_package.ps1
```

## Step 4: Build the installer

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\build_installer.ps1
```

## Step 5: Check the output

```powershell
Get-ChildItem .\installer\output -Recurse
```

The expected result will be similar to:

```text
Omega-Windows-Assistant-Setup-1.0.0.exe
```

The exact filename depends on the installer configuration.

Do not automatically install the generated installer through the build script.

Test it manually on a clean Windows computer or virtual machine.

---

# Files That Must Not Be Included in a Release

Do not include:

```text
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
```

Generated release files should be verified before distribution.

---

# How Other People Can Use Omega

Other users have three options.

## Option 1: Install from source

Suitable for developers and Python users.

```powershell
git clone https://github.com/ItsAnshumanPattanayak/Omega-Windows-Assistant.git
cd Omega-Windows-Assistant
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m omega
```

## Option 2: Use the published installer

Suitable for ordinary Windows users.

```text
GitHub Releases
→ Download installer
→ Verify checksum
→ Run setup
→ Open Omega from the Start Menu
```

## Option 3: Use a portable release

Suitable for users who do not want a full installation.

```text
Download portable archive
→ Verify checksum
→ Extract it
→ Start Omega
```

Each user must configure their own:

- Display name
- Preferences
- Workspace folders
- Email provider
- Calendar provider
- Voice model
- AI model
- Plugins
- Knowledge documents

Never give another person your:

- `.env`
- Database
- Provider credentials
- Tokens
- Screenshots
- Clipboard data
- Personal configuration
- Private plugins
- Workflow exports
- Profile exports
- Knowledge documents

---

# Update Omega

## Source installation

Open the repository:

```powershell
cd Omega-Windows-Assistant
```

Check for local changes:

```powershell
git status
```

When the working tree is clean:

```powershell
git fetch origin
git pull --ff-only origin main
```

Activate the environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Refresh installation:

```powershell
python -m pip install -e .
```

Verify:

```powershell
python -m omega --version
```

Do not pull blindly when unresolved local modifications exist.

## Installer installation

Download the latest verified installer from the official GitHub Release.

Run the newer installer over the current version.

The installer is designed to preserve user data during upgrades, but important local data should still be backed up before major upgrades.

Omega does not currently claim automatic-update support.

---

# Uninstall Omega

Open:

```text
Windows Settings
→ Apps
→ Installed apps
→ Omega Windows Assistant
→ Uninstall
```

The installer is designed to remove application files while preserving local user data by default.

Removing user data should be a separate explicit action.

Back up important Omega data before manually deleting its local data directory.

Do not delete unrelated folders.

---

# Troubleshooting

## PowerShell cannot activate `.venv`

Run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Do not change execution policy globally unless you understand the security impact.

## Python is not found

Install a supported Python version.

During Python installation, enable:

```text
Add Python to PATH
```

Then reopen PowerShell.

## `No module named omega`

Activate the environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install Omega:

```powershell
python -m pip install -e .
```

## GUI does not start

Run:

```powershell
python -m omega --gui-check
```

Then inspect the displayed error.

## Voice model is missing

Download a compatible Vosk model manually and configure its path.

Voice models are not automatically downloaded.

## Microphone is not detected

Run:

```powershell
python -m omega --list-audio-devices
```

Check Windows microphone privacy permissions.

## Local AI is unavailable

Configure an approved local runtime and model.

Omega’s deterministic features continue working without local AI.

## Email is unavailable

Configure the email provider.

Omega remains usable without email integration.

## Calendar is unavailable

Configure the calendar provider.

Omega remains usable without calendar integration.

## SmartScreen blocks the installer

Continue only when:

- The installer came from the official repository
- The version is correct
- The checksum matches
- You trust the release

Do not disable Windows security globally.

## Database or configuration problem

Do not immediately delete the database or configuration.

Check:

- The documented user-data directory
- Application logs
- Configuration validation output
- Security diagnostics
- Release documentation

Back up files before attempting manual repair.

## Internet connection is lost

Local Omega features should continue working.

Internet-dependent features may fail gracefully, including:

- Git operations
- Provider-dependent email features
- Provider-dependent calendar features
- Optional remote services

Local files, notes, tasks, workflows, knowledge search, preferences, and other offline features remain available when configured locally.

---

# Development Verification

Activate the environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Run formatting verification:

```powershell
python -m black --check .
```

Run linting:

```powershell
python -m ruff check .
```

Run static type checking:

```powershell
python -m mypy src
```

Run the test suite:

```powershell
python -m pytest -p no:cacheprovider
```

Run application checks:

```powershell
python -m omega --help
python -m omega --version
python -m omega --gui-check
python -m omega --security-check
python -m omega --performance-check
```

Do not use:

```text
pytest --basetemp
```

because the project has previously encountered Windows access-control issues with that option.

## Final v1.0.0 Source Verification

```text
Collected: 1,730
Passed: 1,720
Failed: 0
Skipped: 10
Xfailed: 0
```

This confirms the source release-preparation state.

It does not replace:

- Clean-machine installer testing
- Real packaged-executable testing
- Live email-provider testing
- Live calendar-provider testing
- Physical microphone testing
- Real local-model testing
- Assistive-technology certification

---

# Release Process

Before creating a release:

1. Confirm the working tree is clean.
2. Confirm local `main` matches `origin/main`.
3. Confirm version is `1.0.0`.
4. Run all quality checks.
5. Run the release-readiness script.
6. Push the final approved commit.
7. Confirm GitHub Actions passes.
8. Build and verify application artifacts.
9. Generate SHA-256 checksums.
10. Confirm prohibited files are absent.
11. Test artifacts on a clean Windows system.
12. Create the version tag.
13. Push the tag.
14. Confirm the release workflow succeeds.

Suggested release tag:

```text
v1.0.0
```

Suggested tag command:

```powershell
git tag -a v1.0.0 -m "Omega Windows Assistant v1.0.0"
git push origin v1.0.0
```

Do not create the release tag until the final commit is pushed and required CI checks pass.

---

# Security Reporting

Do not publicly disclose sensitive vulnerabilities before giving the project owner a reasonable opportunity to review them.

See:

- [Security policy](SECURITY.md)
- [Security documentation](docs/security.md)
- [Threat model](docs/threat_model.md)

---

# Known Limitations

- Omega is Windows-focused
- Installer binaries may be unsigned
- Voice requires a separately downloaded model
- Local AI requires a separately configured local runtime and model
- Email and calendar integrations require provider configuration
- Same-process Python plugins are trusted after approval
- Plugins are not perfectly sandboxed
- Prompt injection cannot be eliminated completely
- Accessibility behavior depends partly on tkinter and Windows
- Additional-language coverage may be partial
- No cloud synchronization by default
- No automatic AI-model download
- No automatic voice-model download
- No OCR
- No continuous screen understanding
- No background surveillance
- No automatic email sending
- No automatic calendar mutation

See:

- [Known limitations](docs/known_limitations.md)

---

# Documentation

- [Architecture](docs/architecture.md)
- [Development roadmap](docs/development_roadmap.md)
- [Installation](docs/installation.md)
- [Packaging](docs/packaging.md)
- [CI/CD](docs/ci_cd.md)
- [Release instructions](docs/releasing.md)
- [Release checklist](docs/release_checklist.md)
- [Release-readiness report](docs/release_readiness.md)
- [v1.0.0 release notes](docs/releases/v1.0.0.md)
- [v2.0.0 upgrade notes](docs/releases/v2.0.0.md)
- [Command reference](docs/command_reference.md)
- [Version history](docs/version_history.md)
- [Security](docs/security.md)
- [Threat model](docs/threat_model.md)
- [Performance](docs/performance.md)
- [Accessibility](docs/accessibility.md)
- [Localization](docs/localization.md)
- [Personalization](docs/personalization.md)
- [Local AI](docs/local_ai.md)
- [Plugins](docs/plugins.md)
- [Plugin development](docs/plugin_development.md)
- [Workflows](docs/workflows.md)
- [Known limitations](docs/known_limitations.md)

---

# Repository

```text
https://github.com/ItsAnshumanPattanayak/Omega-Windows-Assistant
```

# Author

**Anshuman Pattanayak**

GitHub:

```text
https://github.com/ItsAnshumanPattanayak
```

# Version

```text
Omega Windows Assistant v2.0.0 (unreleased)
```

# License

This project is distributed under the license included in the repository.

See:

- [LICENSE](LICENSE)

---

## Final Reminder

For the current local project:

```powershell
cd "E:\project Omega"
.\.venv\Scripts\Activate.ps1
python -m omega
```

For another developer:

```powershell
git clone https://github.com/ItsAnshumanPattanayak/Omega-Windows-Assistant.git
cd Omega-Windows-Assistant
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m omega
```

For an ordinary user after the installer is published:

```text
Download installer
→ Verify checksum
→ Install Omega
→ Open Start Menu
→ Start Omega Windows Assistant
```
