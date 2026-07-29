# Phase 27 performance and resource efficiency

Phase 27 optimizes measured local bottlenecks without removing validation, safety,
confirmation, privacy, accessibility, or provider boundaries. Measurements are
developer observations from one Windows host, not universal performance guarantees.

## Baseline methodology

The baseline and comparison used the same Python environment and repository, seven
fresh processes for startup operations, 25 warm in-process runs for configuration and
parser initialization, nine repeated command/workflow batches, deterministic command
sets, temporary SQLite databases, and fake adapters. Minimum, median, maximum, run
count, connection count, and peak traced allocation were recorded where stable.

```powershell
python -m omega.performance.benchmark
python -m omega --performance-check
python -m pytest -p no:cacheprovider tests/performance -v
```

Ordinary tests assert bounds, reuse, invalidation, operation counts, and cleanup; they
do not fail on fragile machine-specific millisecond thresholds.

## Representative measurements

| Operation | Before median | After median | Observation |
| --- | ---: | ---: | --- |
| Fresh CLI help, 7 runs | 1,011.29 ms | 195.69 ms | Application graph is not imported for help |
| Fresh GUI availability check, 7 runs | 851.91 ms | 722.06 ms | Lower, but still dominated by imports |
| Fresh application init and shutdown, 7 runs | 1,189.01 ms | 1,118.69 ms | Import graph remains dominant |
| Profiled `OmegaApplication.__init__` | 307 ms | 184 ms | Batched reads and fewer persistent pragmas |
| SQLite connections during initialization | 17 | 5 | One profile/value batch replaces repeated reads |
| Parse 900 representative commands, 9 runs | 111.82 ms | 102.87 ms | Hash-keyed bounded intent reuse |
| Plan an unchanged 50-step workflow 100 times | 22.29 ms | 0.034 ms | Exact immutable-object plan reuse |
| Configuration load, 25 warm runs | 20.47 ms | 20.50 ms | No material change |

Traced peak allocation for the parser batch remained effectively flat (921,410 bytes
before and 921,860 bytes after). No memory improvement is claimed.

## Startup and lazy behavior

`omega.__main__` parses help, GUI checks, security diagnostics, and performance
diagnostics before importing the full composition root. Normal application startup
still builds the existing typed service graph. Vosk and SAPI adapters remain lazy to
explicit voice startup; local-AI models load only on request; providers do not connect
at import; disabled plugins are not imported; the scheduler starts only when an
application mode runs.

## Database and knowledge behavior

Each SQLite connection still enables foreign keys, busy timeout, and synchronous
policy. Persistent journal mode is set once per factory under a lock. Startup
preferences are fetched in one bounded batch. Repositories retain parameterized SQL,
bounded results, pagination, existing indexes, short transactions, migration
protection, and explicit connection cleanup. No migration was needed.

Knowledge indexing and search were reviewed and left unchanged because they already
use bounded validation, deterministic chunks, transactional reindexing, indexed
source lookup, bounded results, and no automatic directory watching. Entire private
documents are not added to a cache.

## Cache policy

All Phase 27 caches are process-local, bounded, locked, and explicitly clearable.

| Cache | Key | Value | Bound and invalidation | Privacy |
| --- | --- | --- | --- | --- |
| Parser intent | SHA-256 of normalized text | Intent ID and rule name | Configured LRU; eviction/disposal | No command text retained as key |
| Workflow plan | Exact immutable object identity | Definition and inert plan | Configured LRU; new object/eviction/clear | Never authorization or confirmation |
| Plugin manifest | SHA-256 of validated payload | Immutable manifest metadata | Configured LRU; payload change/eviction | No plugin code or credentials |

Credentials, email bodies, calendar descriptions, clipboard content, screenshot
pixels, AI prompts/responses, full knowledge documents, confirmation tokens,
authorization decisions, and filesystem approvals are never cached by Phase 27.
`enable_sensitive_content_caching` is mandatory false.

## Concurrency, GUI, voice, and shutdown

Cache and metric stores use small locks and fixed capacity. SQLite journal setup is
single-flight per factory. Existing GUI task-runner bounds, duplicate-task prevention,
voice queue limits, AI queue/single-flight behavior, workflow concurrency, provider
idempotency, plugin activation guards, and scheduler idle waits remain intact.

Application shutdown is now explicitly idempotent and records only an allowlisted
timing label when local metrics are enabled. Timing metrics are disabled by default,
bounded when enabled, contain no command text, and never leave the machine.

## Diagnostics and limitations

`python -m omega --performance-check` performs bounded local configuration/parser
measurements and read-only database metadata inspection. It reports only counts,
sizes, migration version, safe labels, and timing distributions. It does not start
Omega, migrate the database, load models, connect providers, import plugins, access
clipboard/screenshots, or upload telemetry.

The application composition module still has a noticeable cold-import cost; splitting
it safely requires a later measured architectural phase. Shared SQLite connections
were not introduced because repositories use short scoped connections for isolation.
Report regressions with the command, run count, fixture size, min/median/max values,
and sanitized environment details—never private content or credentials.
