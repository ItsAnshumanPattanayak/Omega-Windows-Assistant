# Privacy-first desktop utilities

Phase 20 adds explicit, bounded clipboard, screenshot, display, and window
operations. These features use the normal `UserCommand` → parser → dispatcher →
`SafeExecutionGateway` → service lifecycle for terminal, GUI, and offline voice
input. Persisted commands are redacted before clipboard text, search terms, or
window titles can reach command history.

Clipboard support is plain-text only. Omega can copy, read, clear, search, save
through the existing safe file manager, or create an inert note through the
existing productivity service. Reads are bounded for display and clearing
requires exact scoped confirmation. Clipboard history and background monitoring
are disabled; clipboard content is neither polled nor persisted automatically.

Screenshots occur only after an explicit command. The optional Pillow adapter is
loaded lazily and fails clearly when unavailable. Captures use generated names
inside Omega's runtime screenshot directory, with configured dimension and pixel
limits. Recent records and selection are process-local. Deletion requires exact
confirmation and uses the existing Windows Recycle Bin recovery mechanism.

Display information and visible-window metadata are bounded. Window titles are
sanitized and truncated; Omega does not inspect window content. Bringing a
window forward requires a previously selected exact window identifier and does
not inject input or automate that window.

No database migration is needed. There is no OCR, keylogging, clipboard polling,
continuous capture, remote upload, arbitrary shell scheduling, hidden capture,
or automatic execution of clipboard content. Automated tests use injected fake
adapters and perform zero real desktop or network operations.
