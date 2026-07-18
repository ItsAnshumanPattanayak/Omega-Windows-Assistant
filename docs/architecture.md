# Omega architecture

## Present foundation

Phase 0 implements only application startup, configuration, paths, logging, exception types, and tests. The `src/omega` package uses a `src` layout to keep imports explicit and package installation reliable. YAML configuration is read safely from the project-level `config` directory. Runtime logs belong under `data/logs`.

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
