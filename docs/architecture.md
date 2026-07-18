# Omega architecture

## Present foundation

Phase 0 implements application startup, configuration, paths, logging, exception types, and tests. Phase 1 adds `omega.models`: data-only models with standard-library validation, UUID identifiers, timezone-aware UTC timestamps, and JSON-compatible serialization. The `src/omega` package uses a `src` layout to keep imports explicit and package installation reliable. YAML configuration is read safely from the project-level `config` directory. Runtime logs belong under `data/logs`.

## Commands, actions, and results

`UserCommand` preserves future user input exactly, with an initially unknown intent and any future-extracted `CommandEntity` records. An `Action` is a separate proposal to perform an operation: it records parameters, risk, permission, confirmation, dependencies, and lifecycle state, but contains no executor or platform object. A future executor will return `ActionResult` data.

Python exceptions remain control-flow errors and derive from `OmegaError`; `OmegaErrorDetails` is a safe serializable record for reporting a failure to later layers or persistence. Risk and permission are represented as typed data (`RiskLevel`, `PermissionDecision`, and `PermissionEvaluation`), not by a Phase 1 policy engine. Action lifecycle states are represented by `ActionStatus` and validated for timestamp and confirmation consistency.

Models accept only JSON-compatible payloads. Serialization converts enums to stable values, UUIDs to strings, UTC datetimes to ISO-8601 strings, and nested models recursively. Commands, entities, permission evaluations, results, and error records are treated as immutable records; `Action` remains mutable because later phases will need controlled state transitions.

```text
User input
  ↓
UserCommand
  ↓
Future intent detection
  ↓
Action proposal
  ↓
Future permission evaluation
  ↓
Future executor
  ↓
ActionResult
```

Creating any Phase 1 model cannot execute an operation. Execution is deliberately deferred to later, safety-reviewed phases.

## Text session lifecycle

Phase 2 keeps terminal I/O in `TerminalInterface` and state management in `OmegaSession`. The terminal adapter collects text and displays responses; the session validates transitions, captures active commands as `UserCommand` records, and uses a monotonic timeout clock. No terminal input can execute an action.

```text
Process starts → Omega inactive → “Hello Omega” → time-based greeting → Omega active
→ commands captured as UserCommand models → “Shut down Omega” → safe termination
```

## Deterministic understanding pipeline

```text
Active-session text input
  ↓
Command normalization
  ↓
Built-in command priority check
  ↓
Single-action validation
  ↓
Rule-based intent detection
  ↓
Entity extraction
  ↓
Confidence and completeness checks
  ↓
CommandParseResult
  ↓
Safe user response
```

Phase 3 uses explicitly ordered, typed regular-expression rules because deterministic behavior is auditable and fails closed. `ApplicationAliasRegistry` safely loads stable canonical names from JSON, rejects duplicate aliases, and resolves only whole-word matches. Missing parameters and ambiguous targets are represented in `CommandParseResult` and produce clarification without retaining conversational execution state. Unsupported and dangerous text remains `UNKNOWN`.

The parser only mutates the in-memory `UserCommand` representation; it imports no shell, subprocess, filesystem mutation, or Windows automation APIs. Phase 4 may consume recognized application commands through a separately reviewed executor boundary, but Phase 3 cannot launch anything.

## Planned layers

The following components are planned, not implemented:

- **Input layer:** text and, later, voice input. Voice activation will use `Hello Omega`.
- **Command-processing layer:** converts approved user intent into structured commands.
- **Safety layer:** checks permissions, protected paths, confirmations, and action policies before execution.
- **Executor layer:** performs only approved, validated operations through platform-aware Windows services.

Command understanding must remain separate from execution. An interpreter may recognize a request, but only the safety layer may authorize it and only the executor may perform it. This separation makes future behavior testable and prevents an AI suggestion from becoming an action automatically.

Arbitrary shell execution will be prohibited because it would allow ambiguous natural-language input to become unrestricted operating-system access.

## Planned session lifecycle

```text
Inactive
  ↓
“Hello Omega”
  ↓
Time-based greeting for Anshuman
  ↓
Active command session
  ↓
Normal commands without repeating “Omega”
  ↓
“Shut down Omega”
  ↓
Safe session termination
```

This lifecycle is a future design. Phase 0 starts, reports that the foundation is ready, and exits immediately.
