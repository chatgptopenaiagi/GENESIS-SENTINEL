# GENESIS Sentinel architecture

GENESIS Sentinel is a standard-library Python application for Linux software inventory, scoped capability verification, engineering handoff and an authenticated local human interface. Public v0.1.0 separates installed package code from private machine state. It does not replace a scientific engine, a package manager, an AI model or an existing Codex installation.

## Components

| Component | Responsibility |
| --- | --- |
| `config.py` | Resolve the state directory; construct and validate explicit discovery configuration |
| `core.py` | Metadata signatures, bounded probes, environment inspection, graph construction, diffs, immutable generations and recovery |
| `cli.py` / `__main__.py` | `genesis-sentinel` command dispatch and explicit state-directory selection |
| `integration.py` | Opt-in managed guidance and a launcher around an explicitly chosen existing executable |
| `launch.py` | Bounded refresh preparation, stale fallback and final `exec` preserving argument boundaries |
| `control_model.py` | Pin a generation and translate inventory/evidence into human-readable dashboard records |
| `control_server.py` | Authenticated loopback HTTP, report access and fixed management dispatch |
| `control_services.py` | Configured local endpoint observations and the default inventory-refresh action |
| `control_lifecycle.py` | Start, status, access, stop and restart of only the owned dashboard process |
| `adapters.py` | Optional source-preserved deployment adapters, disabled by default and requiring compatible explicit roots |
| `web-control/` | Nine-page responsive browser interface, search/filtering and source links |

The original deployment's notebook generators, scientific result examples, local package/kernel changes and operator reports are not dependencies of the public package. Their preservation boundary is documented in [SOURCE-PROVENANCE.md](docs/SOURCE-PROVENANCE.md).

## Private state location

The selected state directory is, in priority order, the CLI's `--state-dir`, `GENESIS_SENTINEL_HOME`, or `$XDG_STATE_HOME/genesis-sentinel`. Without `XDG_STATE_HOME`, the conventional fallback is `~/.local/state/genesis-sentinel`.

The runtime state directory is private. It contains configuration, generations, runtime locks/markers, verification evidence and dashboard credentials. It is not placed inside the package installation directory or assumed to be the release checkout. Installing the package does not adopt or migrate an existing mobile deployment automatically.

Configuration lists explicit interpreters, optional Conda roots/registry files, registered project/tool roots, tool basenames, configured local service ports and optional external scientific registries. Defaults include the running Python interpreter and only existing conventional Conda locations under the current home or active Conda prefix. There is no required laboratory, Joomla or Conda path.

## Inventory pipeline

```text
registered interpreters and roots
       |
       v
filesystem metadata signatures ------> unchanged interpreter cache
       |                                      |
       v                                      |
bounded per-interpreter metadata inspection <--+
       |
       +--> optional Conda native records
       +--> optional pacman installed records and owning-package version mapping
       +--> configured loopback observations
       +--> selected project manifest fingerprints
       |
       v
normalized snapshot + differences + capability-provider graph
       |
       v
complete generation + SHA-256 generation manifest
       |
       v
validate, then atomically replace current pointer
       |
       +--> human dashboard
       +--> session brief / explicit integration
       +--> retained audit history
```

Metadata collection runs sequentially under each selected interpreter with isolated Python flags and finite subprocess limits. Inventory does not execute arbitrary tool version commands or project setup scripts. Scientific probes are separate, explicit commands selected from a fixed registry.

The environment identifier hashes the canonical prefix directory, retaining separate environments even when their Python executable symlinks resolve to one binary. Python package names are normalized for stable keys. Conda and native-package records retain separate namespaces so they are not accidentally equated with Python distributions.

When pacman is absent or disabled, Python and Conda discovery continue. Public v0.1.0 does not implement a complete dpkg/rpm native-package inventory adapter. Native tool version mappings may therefore remain unknown on a non-Arch system.

## Capability records and freshness

The operation registry maps known package names to bounded operations. A capability records its provider environment, absolute interpreter, version, location, state, observation time, verification time, evidence path and limitations. Graph edges associate an environment with each capability it provides.

A package record starts as installed. A matching explicit verification record can establish importability or a named functional result. An environment-signature mismatch, expired timestamp, future/invalid timestamp or failed environment observation prevents a misleading current functional pass. External scientific registry records are stored as historical context and do not independently create a green Sentinel verification label.

Metadata freshness and operation freshness are separate. `status` reports dirty/error markers and snapshot age; re-reading a snapshot does not rerun scientific tests. The dashboard also ages functional labels at read time so a cached generation cannot remain green indefinitely.

## Transactions and recovery

A finite-wait advisory writer lock serializes cooperating refresh, verification, recovery and configuration operations. Dirty notifications use a separate short lock and unique event identifiers. A long refresh captures the initial marker and clears it only under the short lock when it still matches, preserving later notifications.

A generation contains the six public views plus `GENERATION-MANIFEST.json`, whose digest map covers all six files. Publication validates file presence, hashes and JSON generation identity before switching the pointer. Existing unmanaged report files or symlinks are not overwritten as a shortcut.

Individual writes synchronize the temporary file and parent directory before/after replacement as implemented by the atomic writer. Generation and pointer directories are synchronized. These measures strengthen durability; they do not replace testing on a particular filesystem or prove behavior under every device power-loss mode.

The `current` symlink is the commit authority. Readers resolve it once for a multi-file view. A partial new generation does not replace an old committed one. Recovery validates a named retained generation under the writer lock, repoints `current`, records recovery and marks state dirty to require present-day reconciliation. Old generations and failed checks are retained.

`CHANGES.jsonl` and runtime event records preserve observed transitions. They are audit streams rather than a distributed transaction log. A process can stop between pointer commit and audit append; records must be interpreted accordingly. There is no automatic snapshot garbage collection.

## Optional integration

`integrate` receives an explicit guidance-file destination. An optional launcher also requires an explicit existing original executable and a new, unoccupied destination. Managed block text and wrapper hashes are recorded for rollback. `unintegrate` removes only the exact owned block and an unchanged owned wrapper, preserving unrelated edits and changed files for review.

The launcher invokes Python, performs bounded quick-refresh preparation and then uses `exec` on the selected existing program. It is not a native compiled CLI replacement. The release does not modify Codex binaries, authentication, global configuration or shell profiles merely by installation.

The generated brief provides external knowledge to cooperating sessions. No mechanism modifies model weights or silently refreshes an already running conversation.

## Human interface and control boundary

The dashboard exposes Home, My software, My projects, Scientific laboratory, AI engines, Anaconda, Engineering history, Software changes and System status. The model reads a pinned generation, catalogs explicit reports and returns understandable records. It does not crawl unrelated project histories or invent achievements.

Default external service configuration provides local observations and Open links. A response is labelled as an endpoint observation rather than process identity or scientific qualification. Inventory refresh is a fixed authenticated action. Optional deployment adapters preserve specialized original checks but are disabled by default; their requirements and verification scope are distinct from the portable default.

The HTTP service binds to loopback, validates Host and mutation Origin, requires authentication and CSRF, limits request bodies, and serves reports by opaque catalog identifiers rather than user-supplied filesystem paths. Credentials, session storage and logs remain private. Dashboard process stop/restart checks owned command and kernel start identity before signalling. These are local administrative safeguards, not protection against a hostile process with the same account's filesystem access.

See [SECURITY.md](docs/SECURITY.md) for the complete trust boundary and [PORTABILITY.md](docs/PORTABILITY.md) for platform limits.
