# Omega 1.0 known limitations

- Omega is Windows-focused. Pure domain code may import elsewhere, but Windows
  integration and packaging are authoritative only on supported Windows systems.
- Release binaries are unsigned and may trigger Windows unknown-publisher warnings.
  Checksums establish file integrity, not publisher identity.
- A clean Windows build and installer run must still pass before publishing binary
  artifacts; the release-preparation environment lacks PyInstaller and Inno Setup.
- Optional voice requires a compatible local Vosk model, microphone/audio backend,
  and installed Windows SAPI voice. Hindi UI translation is partial, and multilingual
  speech recognition is not claimed.
- Email and calendar depend on explicit provider configuration. Automated tests use
  zero-network fake providers; no live account behavior is certified by this release.
- Local AI never downloads models automatically. Quality, speed, language coverage,
  and memory use depend on the explicitly configured local runtime and model. Prompt
  injection risk can be reduced but not eliminated; generated actions remain
  proposals and are never executed automatically.
- Approved same-process Python plugins are trusted code after fingerprint-bound
  permission review. Omega does not claim a perfect plugin sandbox.
- Browser automation requires the optional Playwright package and a compatible local
  browser installation. It is limited to Omega-controlled sessions.
- tkinter accessibility depends on Windows and assistive-technology behavior. Omega
  includes keyboard, text-status, contrast, and scaling support but is not formally
  screen-reader or WCAG certified.
- Omega has no cloud synchronization, mobile client, automatic updater, OCR, real-time
  screen understanding, background clipboard collection, background screenshot
  surveillance, or automatic plugin/model download.
