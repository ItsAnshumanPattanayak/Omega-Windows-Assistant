# Safe Windows system controls

Phase 14 adds one optional system domain beneath Omega's existing command
lifecycle. It does not add a parser, permission engine, shell, administrator
path, service manager, registry editor, or generic process killer.

## Supported information

Omega can return bounded CPU, memory, fixed-disk, battery, network-interface,
and process summaries. Desktop computers may report battery unavailable.
Process results include only PID, name, CPU percentage, memory percentage,
status, and a protected-process indicator. Command lines, environments,
handles, open files, modules, memory, Wi-Fi credentials, product keys, and
security tokens are never queried or persisted.

## Controls and Settings

Volume and brightness requests accept whole percentages. Increments are capped,
volume remains within configured limits, and brightness retains a safe lower
bound. Production adapters are optional and unsupported hardware returns one
safe failure without retry. Tests use in-memory fakes.

Windows Settings supports only System, Display, Sound, Notifications, Power and
battery, Storage, Bluetooth and devices, Network and internet, Windows Update,
Apps, and Privacy. User-supplied URIs and other protocols are rejected.

## Power safety

Lock, sleep, hibernate, sign out, restart, and computer shutdown require an
exact displayed phrase. Examples include `confirm restart computer` and
`confirm shut down computer`. Generic “yes”, partial recognition, silence,
wrong-session phrases, expiry, cancellation, and replay do not approve.
Shutdown and restart use a short configured countdown that can be cancelled.
No forced-close flag, arbitrary argument, elevation, or automatic retry exists.

`Shut down Omega` terminates only the assistant. `Shut down the computer`
creates a separate critical proposal and cannot execute before confirmation.

## Configuration and limitations

The `system` YAML section controls feature availability, bounded result counts,
percentage ranges, increments, countdowns, and supported power operations.
Unknown keys and unsafe values fail closed. Generic process termination is
permanently disabled. Configuration cannot enable administrator actions,
security-control changes, arbitrary commands, or credential access.

System information uses the existing `psutil` dependency. Windows Settings and
power adapters use only local operating-system interfaces. Audio and brightness
hardware support varies, and Omega does not install drivers or packages.

Normal tests never mutate the real host. Real lock, sleep, hibernate, sign-out,
restart, and shutdown operations must never be automated in CI or opt-in smoke
tests. Run the fake-based suite with:

```powershell
python -m pytest tests/system -p no:cacheprovider -v
```
