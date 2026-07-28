# Omega threat model

This practical threat model describes the security boundary of the local Omega
process after Phase 26. It supports design and testing; it is not a certification or
formal penetration test.

## Protected assets

Protected assets are user files and folders; email and calendar state; clipboard and
screenshot content; notes, tasks, knowledge documents, and command history; local
SQLite databases; credentials and tokens; plugin data and workflow definitions;
local-AI context; configuration; and live application state.

## Threat actors and untrusted sources

Omega accounts for accidental user error and hostile content in documents, email,
clipboard, filenames, paths, archives, plugins, workflows, profiles, language packs,
provider responses, database rows, and local-AI inputs or outputs. Prompt-injection
text is treated as data. A local unprivileged malicious process is also relevant,
although Omega cannot isolate data from malware already running as the same user.

## Trust boundaries

```text
terminal / GUI / voice / imported files
        -> parser and typed model boundary
        -> dispatcher
        -> security invariants
        -> central safety gateway and exact confirmation
        -> filesystem / SQLite / Windows API / provider adapter

plugin runtime / workflow executor / local-AI provider
        -> bounded schemas and capability checks
        -> same central safety and domain-service boundaries
```

Crossing a boundary does not grant authority. User text, provider content, plugin
output, workflow variables, and model output cannot approve a command. Filesystem
paths are revalidated at the domain boundary. Provider identifiers and durable
operation receipts are opaque and bounded. The GUI and voice layers use the same
command lifecycle as the terminal.

## Security goals

- Prevent unauthorized side effects and confirmation bypass.
- Prevent path traversal, link escape, archive ambiguity, and unsafe replacement.
- Prevent arbitrary shell or dynamic-code execution.
- Prevent secrets and private bodies from leaking through normal logs and receipts.
- Bound input, import, provider, concurrency, and output work.
- Minimize persisted sensitive data and retain privacy-safe auditability.
- Fail closed on validation, policy, persistence, timeout, and provider ambiguity.
- Preserve deterministic, testable behavior without remote security dependencies.

## Representative threats and controls

| Threat | Primary controls | Residual risk |
| --- | --- | --- |
| Command or shell injection | Typed parsing, allowlisted intents, no shell, gateway invariants | A domain-parser bug may still require correction |
| Path or link escape | Logical roots, canonical containment, revalidation, reparse rejection | OS-level race resistance depends on supported APIs |
| Confirmation replay or target swap | Session/action binding, expiry, single use, fingerprints | User may still confirm a misunderstood but accurately displayed action |
| Malicious JSON/archive import | Byte/depth/item limits, duplicate-key rejection, per-member ZIP checks | Same-process reviewed plugin code is not a sandbox |
| SQL injection or corrupt rows | Parameter binding, schema constraints, typed decoding, migrations | A compromised database can cause safe failure or data loss |
| Provider replay or ambiguity | Bounded adapters, opaque IDs, idempotency receipts, no blind timeout retry | External provider state may require user reconciliation |
| Prompt injection | Untrusted-data delimiters, proposal-only AI, output schemas, gateway authority | Prompt injection cannot be eliminated perfectly |
| Secret leakage | Minimal persistence, structured redaction, bounded safe errors | Best-effort secret detection cannot identify every secret shape |
| Resource exhaustion | Size/count/depth/rate/concurrency/timeout limits | Same-user processes can still exhaust host resources |

## Non-goals and limitations

Same-process plugins and optional local-AI runtimes are not fully sandboxed. Local
malware running with the user's privileges may read or change user data. Local models
may return inaccurate or unsafe text. Prompt injection and secret detection are not
perfect. Windows protection ultimately depends on account controls, ACLs, updates,
and host integrity. Phase 26 does not provide forensic resistance, kernel isolation,
remote attestation, vulnerability certification, or protection from an administrator
who intentionally changes the installation.

## Review triggers

Revisit this model when adding an execution capability, network provider, new import
format, credential store, plugin capability, workflow step, AI tool, database
migration, background monitor, or privilege boundary. Any new side effect must have a
typed proposal, domain validator, safety policy, exact confirmation where required,
bounded persistence, and adversarial tests before release.
