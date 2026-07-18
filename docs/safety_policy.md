# Omega safety policy

Omega is founded on least-privilege behavior and explicit user control.

- User-provided shell commands must never be executed without strict, purpose-built authorization; unrestricted shell execution is prohibited.
- Administrator-level operations are disabled by default.
- Permanent deletion is disabled by default.
- Future path checks must protect system locations such as Windows, Program Files, Program Files (x86), and ProgramData.
- Future destructive operations must obtain clear confirmation before proceeding.
- Future deletion features should use the Recycle Bin rather than permanently removing files whenever possible.
- Future action history and undo support must make completed operations reviewable and reversible where practical.
- Local AI may propose actions, but it may never execute an action directly; only a validated executor may act after policy checks.
- Logs must not contain secrets, credentials, personal content, or other sensitive information.

Phase 0 enforces the initial configuration flags and deliberately contains no command executor.
