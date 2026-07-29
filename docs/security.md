# Phase 26 security hardening

Omega applies defense in depth around the existing mandatory safety gateway. Phase
26 does not add a second execution path, weaken confirmation, collect telemetry, or
introduce remote security services. Security failures are explicit and fail closed.

## Threat model and trust boundaries

Untrusted data includes terminal, GUI, and voice text; paths and filenames; imported
JSON, documents, archives, email and calendar bodies; clipboard content; plugin and
workflow definitions and results; local-AI prompts and outputs; provider errors; and
configuration supplied outside compiled defaults. None of these inputs is authority.

The primary threats are command and shell injection, traversal and link escape,
archive bombs and path collisions, confused-deputy execution, confirmation replay,
secret disclosure, unsafe deserialization, SQL injection, malicious providers or
plugins, prompt injection, resource exhaustion, and unsafe defaults. Physical device
compromise, operating-system compromise, and forensic resistance are outside the
application boundary.

```text
untrusted input -> bounded validation -> typed command/action
                -> universal security invariants
                -> mandatory safety policy and exact confirmation
                -> allowlisted domain service -> bounded result
```

## Enforced invariants

- Unknown intent, model-authorized action, safety-bypass metadata, user-derived
  shell execution, and mismatched command/action identity cannot dispatch.
- Subprocesses use argument lists with `shell=False`; arbitrary executable paths and
  executable scheduling remain unavailable.
- Existing path validators remain authoritative. Imports additionally reject
  duplicate JSON keys, excessive size, nesting, and item counts.
- Plugin ZIPs are inspected member by member. Traversal, links and special files,
  reserved or ambiguous Windows names, case collisions, nested archives, executable
  content, excessive expansion, and excessive compression ratios are rejected.
- Confirmations remain short-lived, exact-action scoped, single-use, state-bound,
  auditable, and revalidated immediately before execution.
- Provider, plugin, workflow, local-AI, and desktop content stays untrusted data and
  cannot become code, policy, or authorization.
- Logs and serializable diagnostic errors apply bounded credential, bearer-token,
  private-key, and optional path redaction. Sensitive domain bodies remain omitted
  from durable receipts.
- SQLite access remains parameterized and migration-controlled. No pickle, `eval`,
  `exec`, YAML object construction, import-time schema creation, or archive
  `extractall` path is permitted.

## Resource and concurrency controls

Commands have configurable character and token limits plus a thread-safe sliding
window rate limit. JSON imports, archives, provider results, workflows, plugins,
knowledge search, AI operations, clipboard and screenshot operations retain their
domain-specific size, count, timeout, queue, and concurrency bounds. Locks guard
mutable process state; durable claim and idempotency mechanisms remain authoritative
across restart.

Phase 27 caches only bounded immutable metadata or inert plans. It does not cache
credentials, provider bodies, clipboard/screenshot data, AI prompts or responses,
confirmation tokens, authorization decisions, full private documents, or filesystem
approvals. Cache keys avoid retaining command text, and cached workflow plans cannot
grant confirmation or permission. See [performance.md](performance.md).

## Configuration and diagnostics

The `security` configuration is typed, immutable, bounded, and rejects unknown keys.
Options representing shell execution, dynamic code, confirmation bypass, automatic
email/calendar mutation, remote plugin/model acquisition, external translation,
background clipboard/screenshot capture, telemetry, or cloud sync are mandatory
false and cannot be enabled by configuration.

Run the local read-only diagnostic with:

```powershell
python -m omega --security-check
```

It validates critical fail-closed settings and scans Python syntax for prohibited
high-impact primitives without importing source, touching providers, opening the
network, changing the database, or exposing secrets. It is a developer diagnostic,
not a guarantee that the host operating system is uncompromised.

## Reporting security issues

Do not include credentials, private content, database copies, or personal paths in a
report. Provide the Omega version, affected feature, minimal sanitized reproduction,
expected safety boundary, and observed behavior through the repository's private
security-reporting channel when available. Avoid publishing exploitable details until
a fix has been reviewed.

## Incident-response basics

If unsafe behavior or possible disclosure is observed, stop Omega, preserve only
sanitized diagnostic timestamps and operation IDs, revoke affected provider tokens,
and review local provider/account activity. Do not rerun a destructive reproduction
against real data. Report the smallest safe reproduction privately, then update Omega
and rotate credentials after a reviewed fix. The detailed asset, actor, boundary, and
residual-risk analysis is in [threat_model.md](threat_model.md).
