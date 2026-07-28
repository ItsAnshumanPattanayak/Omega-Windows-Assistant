# Accessibility

Phase 25 provides practical, privacy-first accessibility improvements while preserving
Omega's safety rules. It does not claim WCAG, Section 508, screen-reader, or assistive
technology certification.

## Supported behavior

- Keyboard navigation follows tkinter's normal Tab and Shift+Tab traversal. Ctrl+L
  focuses command input, F1 opens help, Enter submits from the command editor, and
  Escape cancels safe dialogs. No shortcut confirms a sensitive action.
- Destructive confirmations name the action and target, retain all consequences and
  exact choices, expire within a bounded extension, and focus Cancel by default.
- Font scale is bounded from 0.8 to 2.0 by default. High contrast uses a black/white/
  yellow palette with textual Success, Warning, Error, Enabled, and Disabled states.
- Reduced motion is stored and resolved even though the current GUI has no essential
  animation. Screen-reader mode reduces decorative terminal output and uses direct
  textual labels. ANSI color and Unicode symbols remain optional.
- GUI controls use visible text labels and the status area describes state in text.
  Dialog focus is placed deliberately and headless adapters verify focus restoration.
- Speech rate, volume, response length, recognition language, installed voice, and
  listening timeout remain bounded. A missing voice or mismatched Vosk model produces
  a warning and preserves text mode. Models are never downloaded automatically.

Preferences use Phase 24 precedence: mandatory safety policy, session override,
active profile, persisted preference, application configuration, then built-in
default. Accessibility can extend confirmation time but cannot remove confirmation,
auto-select Yes, reuse an expired approval, or lower voice confidence requirements.

## Terminal output

Plain text is always complete. Essential meaning is not encoded only with color or
symbols. Screen-reader-friendly mode avoids animations and decorative separators;
compact and spoken-response preferences control verbosity without shortening safety
warnings.

## Limitations and testing

Automated tests use headless controllers and fake focus, catalog, event, and voice
state. No real screen reader, switch device, magnifier, microphone, SAPI language
voice, or physical keyboard layout was tested in Phase 25. tkinter's native
accessibility exposure differs by Windows and installed assistive technology. Users
should keep text mode available if a voice model or installed voice is incompatible.

Run focused tests with:

```powershell
python -m pytest tests/accessibility -p no:cacheprovider
```
