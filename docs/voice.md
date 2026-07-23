# Omega offline voice

Phase 12 provides optional, explicitly started voice interaction over Omega’s
existing session and safety architecture. It is not a background Windows
service, biometric identity system, far-field wake engine, or cloud assistant.

## Technology and licenses

- **Vosk 0.3.45** — offline speech-to-text, Apache-2.0.
- **sounddevice 0.5.5** — local PortAudio microphone binding, MIT.
- **comtypes 1.4.16** — Windows COM binding used for installed SAPI voices, MIT.

These packages are in the optional `voice` dependency extra. Text-only and GUI
modes do not require them:

```powershell
python -m pip install -e ".[voice]"
```

Recognition needs no account, API key, paid API, or network request. Omega does
not silently download a speech model.

## Model setup

1. Download a compatible English Vosk model from the official Vosk model page.
2. Extract it under `data/voice_models/`, for example:
   `data/voice_models/vosk-model-small-en-us-0.15/`.
3. Configure only the relative directory:

```yaml
voice:
  enabled: true
  model_path: vosk-model-small-en-us-0.15
```

Absolute paths and `..` traversal are rejected. The entire model root is ignored
by Git. Model validity is checked only during explicit voice initialization.

## Configuration

The `voice` section in `config/app_config.yaml` controls:

- enablement and offline-recognition enablement;
- relative model path and optional microphone index/name;
- bounded sample rate, block size, listening/session timeouts, and transcript
  size;
- ordinary and stricter confirmation confidence thresholds;
- local speech enablement, rate, volume, and optional installed voice name;
- whether a timed-out active session returns to passive wake listening.

Unknown keys, loose boolean values, booleans used as numbers, unsafe paths,
out-of-range values, identical activation/shutdown phrases, and a confirmation
threshold below the ordinary threshold are rejected. Voice preferences can
disable speech output but cannot modify safety or confirmation policy.

The wake and shutdown phrases come from validated assistant settings rather than
being duplicated in voice configuration.

## Starting and stopping

Terminal voice mode is explicit:

```powershell
omega --voice
python -m omega --voice
omega --list-audio-devices
```

Ordinary `omega`, `python -m omega`, `omega --gui`, and `omega --gui-check`
retain their existing behavior. Conflicting startup modes return exit code 2.
Unavailable dependencies, devices, or models produce a concise actionable
message without a normal-use traceback. Ctrl+C stops and releases the adapters.

In the desktop interface, select **Start voice** to initialize one listener and
**Stop voice** to release it. The status area shows microphone/listening state
and the latest bounded transcription preview. Voice events are marshalled to the
Tk thread; background workers never manipulate widgets. Closing the GUI stops
voice first. Typed commands continue to work when voice is disabled or
unavailable.

## Wake and active sessions

The default `Hello Omega` phrase is case-insensitive, whitespace-normalized, and
tolerant only of harmless boundary punctuation. Partial words, unrelated
prefixes, fuzzy matches, and low-confidence results do not activate Omega.

Wake alone activates the existing session and uses its existing time-based
greeting. `Hello Omega, open Chrome` is supported only when the wake prefix can
be separated exactly; the remainder then travels through the same command
handler. Once active, commands do not repeat Omega’s name.

Every accepted transcript creates the canonical Phase 1 command with
`CommandSource.VOICE`, preserves the session ID, and travels through the same
normalizer, parser, persistence, dispatchers, safety gateway, result
persistence, recovery, and history paths as typed input. Recognition callbacks
carry unique IDs and a bounded recent-ID set prevents duplicate execution
without suppressing legitimate later repetitions.

`Shut down Omega` is sent through the existing session shutdown path. Stopping
voice listening alone does not close the GUI. Closing the GUI stops voice and
then closes the application.

## Confirmation security

Speech never changes confirmation semantics. If the central gateway has a
pending action, only its exact displayed confirmation or cancellation phrase is
eligible, and only when recognition is final and meets the stricter configured
confidence. Omega does not translate “yes” into approval.

Silence, partial recognition, low confidence, ambiguity, timeout, cancellation,
wrong session/action/target, expired state, changed resource fingerprint, or a
duplicate callback cannot approve. The voice layer forwards an eligible phrase
to the existing session; the central confirmation manager still performs
scoping, expiry, fingerprint revalidation, and single-use enforcement.

## Speech output

Safe assistant responses can be queued to the local Windows SAPI engine. The
queue is bounded, sequential, cancellable, and limits spoken text to 500
characters. An unavailable output engine, missing requested voice, full queue,
or synthesis failure never retries or reverses a completed command. Full safe
text remains visible in terminal/GUI output; internal diagnostics and stack
traces are not spoken.

## Privacy

- No microphone opens before explicit voice start.
- No raw audio is persisted, logged, uploaded, or stored in SQLite.
- No temporary WAV or microphone-test files are created.
- No telemetry, cloud service, account, or API key is used.
- In-memory PCM buffering is bounded and cleared on stop.
- Transcripts use only Omega’s existing command/history persistence policy.
- The GUI visibly reports voice and listening state.
- Stopping voice, terminal exit, GUI close, disconnect, or worker failure
  releases microphone and speech resources.

## Troubleshooting

- **Voice disabled:** set `voice.enabled: true`.
- **Model missing/invalid:** verify the relative directory below
  `data/voice_models/`; Omega never downloads it.
- **Dependency unavailable:** reinstall with
  `python -m pip install -e ".[voice]"`.
- **Microphone unavailable:** run `omega --list-audio-devices`, then configure a
  valid input index or exact device name.
- **No spoken response:** verify Windows has an installed SAPI voice and that
  both YAML and the GUI preference allow speech. The command itself is not
  retried.
- **Recognition rejected:** speak the wake phrase or command again clearly.
  Confirmation intentionally uses a higher threshold.

Recognition accuracy depends on the chosen local model, microphone, noise, and
speaker. Phase 12 does not claim perfect, multilingual, or far-field accuracy.

## Tests

Normal CI uses fake microphones, recognizers, speakers, clocks, sessions, and GUI
views. It requires neither optional packages nor audio hardware:

```powershell
python -m pytest -p no:cacheprovider tests/voice -v
```

For a manual hardware smoke test, install the extra, configure a local model,
enable voice, run `omega --voice`, say `Hello Omega`, request `status`, and then
say `Shut down Omega`. Confirm that the microphone is released. This is opt-in
and is not run automatically.
