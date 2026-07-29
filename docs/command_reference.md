# Command reference

This reference describes deterministic commands supported by the current source. It
does not imply that optional providers, applications, hardware, models, or browser
backends are available on a particular machine. Dynamic values are shown in angle
brackets.

## Session commands

| Purpose | Supported input | Notes |
| --- | --- | --- |
| Activate | `Hello Omega` | Standalone configured phrase; case-insensitive. |
| Stop Omega | `Shut down Omega` | Ends the assistant, not Windows. |
| Help | `help`, `show help` | Available while inactive or active. |
| State | `status` | Reports inactive, active, shutting down, or terminated. |
| History | `show history` | Uses current-session or persistent history service. |

## Application commands

| Purpose | Examples | Confirmation and availability |
| --- | --- | --- |
| Open | `Open <application>`, `Launch <application>` | Registered allowlist only; passes through the safety gateway. |
| Close | `Close <application>` | Exact central confirmation may be required because unsaved work can be lost. |
| Status | `Is <application> running?` | Read-only when the registered application can be inspected. |
| Name-only | `<application>` | Exact name/alias asks `Do you want to open <application>?`; never opens immediately. |

Current registered names/aliases include Google Chrome, Microsoft Edge, Notepad
(`note pad`), Calculator, File Explorer, Paint, Settings, Task Manager, Command
Prompt, PowerShell, and Visual Studio Code (`vs code`, `vscode`). Registration does
not guarantee that an executable is installed or discoverable.

For a current application-name clarification only, Omega accepts `yes`, `yes please`,
`open it`, `please open it`, or `confirm`; cancellation accepts `no`, `cancel`,
`do not open it`, or `never mind`. These phrases do not replace an exact sensitive
confirmation and are inert when no matching clarification exists.

## Other implemented categories

The deterministic parser also covers the Version 1 categories documented in the
[README](../README.md#command-examples): files and folders; history and recovery;
notes and tasks; reminders, alarms, timers, and schedules; browser operations; system
status and allowlisted settings; clipboard, screenshots, displays, and windows;
knowledge; email and calendar provider operations; workflows; plugins; local AI; and
personalization.

Commands with dynamic values require the exact entities described by their prompt,
for example `Create a file named <filename> on <location>`, `Remind me to <message> at
<time>`, or `Search knowledge for <query>`. Unsupported, ambiguous, multi-action, or
unsafe input is rejected or clarified rather than guessed.

## Input channels and safety

Terminal, GUI, and accepted voice transcripts use the same session and command
lifecycle. Optional dependencies can produce a safe unavailable response. Permission
denial, missing resources, expiry, changed targets, low voice confidence, or an exact
confirmation mismatch cannot be converted into success by another input channel.
