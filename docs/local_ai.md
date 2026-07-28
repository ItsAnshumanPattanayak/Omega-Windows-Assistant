# Privacy-first local AI

Phase 23 provides an optional local language-model boundary. It does not bundle a
model, inference runtime, cloud account, or heavyweight ML dependency. Omega starts
and all deterministic features work when local AI is disabled or unavailable.

## Security and privacy boundary

- Local AI is disabled by default.
- Models and packages are never downloaded or installed automatically.
- Remote endpoints, telemetry, cloud upload, credentials, and hidden prompt logging
  are prohibited.
- An optional HTTP adapter accepts only a configured loopback URL. The same-machine
  runtime is a separate trusted component and receives no credentials from Omega.
- Models receive text through `AiService`; they never receive shell, filesystem,
  email-send, calendar-mutation, workflow-execution, safety, or credential services.
- Generated text is an unverified proposal, never authorization. It is not parsed as
  code, redispatched as a command, saved as a workflow, or applied automatically.
- Persistent action receipts omit prompts, responses, private source bodies, and
  conversation content.

Prompt injection cannot be eliminated completely. Omega uses defense in depth:
trusted instructions and untrusted sources are separated, every source is labeled,
credentials are rejected or redacted, prompts and context are bounded, structured
outputs are schema-checked, citations are validated, and every eventual domain action
must pass its normal validation, permission, safety, and confirmation path.

## Providers and models

The provider protocol supports generation and embeddings. Automated tests use the
deterministic `FakeAiProvider`, which performs no network, filesystem, email,
calendar, clipboard, screenshot, or workflow work. `LoopbackHttpAiProvider` is an
optional standard-library JSON adapter for an explicitly configured runtime on
`localhost`, `127.0.0.1`, or `::1`. It applies request timeouts and response byte
limits and validates response shapes.

Model descriptors are registered explicitly. Omega does not scan the filesystem.
Optional model files must be inside the approved model directory, may not escape by
symlink, and are fingerprinted. A model is reported ready only after provider
validation and explicit loading succeeds.

Example conservative configuration:

```yaml
local_ai:
  enabled: false
  provider: null
  default_generation_model: null
  default_embedding_model: null
  approved_model_directory: null
  automatically_download_models: false
  allow_remote_endpoints: false
  allow_only_loopback_endpoints: true
  endpoint: null
  maximum_prompt_characters: 50000
  maximum_response_characters: 10000
  maximum_context_turns: 10
  maximum_context_characters: 30000
  maximum_concurrent_requests: 1
  maximum_queued_requests: 5
  generation_timeout_seconds: 120
  model_load_timeout_seconds: 180
  enable_ai_command_fallback: false
  enable_conversation_persistence: false
  log_prompts: false
  log_responses: false
```

No private model path, user identity, credential, token, or email address belongs in
tracked configuration. Model directories and runtime data must remain outside Git.

## Commands and interfaces

The terminal, tkinter GUI command worker, and offline voice pipeline share the normal
command lifecycle. Supported typed forms include:

```text
Show local AI status
List local AI models
Load model <configured-id>
Unload the model
Ask local AI <question>
Summarize text: <text>
Cancel AI generation
Show AI context status
Clear AI conversation
Start a new AI conversation
```

Voice cannot load a model. Long output is displayed as bounded text; generated actions
still require normal typed or explicit confirmation and are never executed directly.
GUI controls submit the same commands through the existing background task runner, so
generation does not run on the tkinter UI thread and duplicate submissions remain
disabled while a request is active.

## Grounding, embeddings, and fallbacks

Grounded answers retrieve bounded Phase 17 knowledge chunks first, keep chunk IDs and
locations authoritative, and accept only citations that refer to supplied chunks.
When evidence is absent, Omega says so or returns the existing extractive answer.
Source excerpts are bounded; entire private documents are not added automatically.

The embedding interface is local, dimension-checked, fingerprint-aware, bounded, and
cancellable. No mandatory vector database was added. Existing SQLite keyword search
remains authoritative and available when embeddings are not configured.

Deterministic fallbacks remain available for knowledge search and answers, email
summaries, calendar behavior, notes and tasks, workflows, and command parsing. AI
command fallback remains disabled by default.

## Draft-only integrations

AI may rewrite an email draft, suggest calendar description text, rewrite a note,
propose tasks, or return a schema-validated workflow draft. These adapters do not
receive mutation-capable services. They cannot send mail, add recipients, create or
change events, overwrite notes, create tasks, save workflows, or execute workflow
steps. The user must review the output and start a separate normal Omega operation.

Plugins require the explicit `use_local_ai_generation` or
`use_local_ai_embeddings` permission. Permission is tied to plugin identity, version,
and fingerprint, is rechecked for every request, and is combined with a per-session
quota. Plugin context is always untrusted and plugins cannot supply system prompts,
provider URLs, model paths, hidden prompts, or tool instructions.

## Resource lifecycle and troubleshooting

Models load lazily and explicitly. The resource manager prevents simultaneous load
races, limits concurrent and queued requests, supports cooperative cancellation,
enforces generation and load timeouts, and owns shutdown. Cancellation cannot safely
kill an uncooperative provider thread; a provider must honor its cancellation token,
and Omega never terminates unrelated processes.

If status says AI is disabled or unconfigured, leave the deterministic fallback in
use or configure a reviewed local runtime and model explicitly. Omega does not claim
that a real model has been verified merely because the provider interface or fake
tests pass. Model output may be inaccurate, biased, incomplete, or vulnerable to
adversarial source content and must be reviewed.

Run the standard zero-network test suite with:

```powershell
python -m pytest -p no:cacheprovider tests/ai
```

Real-model testing is opt-in and was not part of standard Phase 23 verification.
