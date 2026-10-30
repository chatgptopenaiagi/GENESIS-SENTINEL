# Engineering decisions and their observable rationale

These decisions are reconstructed from implemented boundaries and tests. They are an engineering explanation, not a transcript of hidden model reasoning.

| Decision | Problem addressed | Implementation and cost |
| --- | --- | --- |
| Keep inventory outside conversations | Session-local context can disappear or become stale | Persist generation-tagged views and a concise session brief; later clients must actually read them |
| Keep prefixes separate | Shared Python binaries do not imply shared packages | Derive environment identities from prefixes; duplicate package observations across environments are intentional |
| Inspect metadata before importing packages | Scientific imports can be expensive or have side effects | Run bounded metadata collection under each trusted interpreter; verify only fixed named operations explicitly |
| Distinguish installed, importable and verified | A distribution record does not prove useful behavior | Store states and evidence scope rather than one working/not-working Boolean |
| Separate observation and verification clocks | Refreshing metadata must not invent a new scientific test | Preserve original verification timestamps and expire them by age/signature |
| Register roots rather than scan everything | Mobile filesystems can be large and include private projects | Inspect conventional immediate environments and selected manifests under explicit roots; unregistered locations can be missed |
| Cache metadata signatures | Repeated full inspection wastes startup time | Reuse unchanged inventories; unusual metadata-preserving edits may need explicit full refresh |
| Use immutable generations and one pointer | Readers need a consistent last good snapshot | Write a complete generation, then replace `current`; retained snapshots consume disk over time |
| Use advisory single-writer locks | Concurrent refresh/verification can corrupt state | Finite lock acquisition serializes cooperating writers; it cannot police direct manual edits |
| Record dirty notifications cheaply | Package-manager hooks should not block on an inventory | Mark state and reconcile later; no universal watcher is claimed |
| Preserve failed evidence | A later pass must not erase earlier limitations | Keep verification attempts and source-backed timelines; human summaries can become larger |
| Use fixed probe code | Browser/model-supplied code should not become an execution API | Dispatch known operation identifiers; adding new probes requires source review and focused tests |
| Keep management on loopback | A phone control center manages a privileged local workspace | Authenticated local server with Origin/CSRF checks; a hostile local account is outside the isolation boundary |
| Make release integration opt-in | Installing a library should not modify an existing CLI or global configuration | Generate a chosen guidance block/launcher, record ownership, rollback only owned changes |
| Use a distinct public command | The original installation must remain operational | Public entry point `genesis-sentinel` does not replace the operator's existing `sentinel` or Codex command |
| Keep public source separate from deployment data | Operational inventory, tokens and research are not release examples | Publish synthetic fixtures and configuration templates; protect local recovery archives separately |

## Established techniques and project-specific composition

Metadata inspection through Python's distribution API, normalized package names, checksums, advisory `flock`, temporary files, atomic rename, versioned snapshots, process groups, managed text blocks and graph-shaped JSON are established techniques. Sentinel does not claim to invent them.

The project-specific design joins these techniques into a capability-aware engineering handoff: it connects a task-sized operation to an absolute environment, a bounded test, a signature and a timestamp, then presents that record to both a human and a later cooperating session. The mobile deployment also supplied concrete constraints—separate scientific distributions, restricted Android/proot behavior and preservation of an existing CLI—that informed the boundaries.

This is not a claim of priority, mathematical novelty or general AI memory. It is a reusable software design whose behavior can be tested independently.

## Why the public release does not reproduce the phone wholesale

The original dashboard had specialized controls for an existing scientific laboratory, a particular Joomla deployment and an owned Jupyter workbench. Those integrations depended on private configuration files, process records and application-specific busy checks. Copying those paths into a supposedly portable installer would be misleading and could expose unrelated operational data.

The portable dashboard therefore inventories the same general records and defaults to explicitly configured local service observations. Fixed Science/Joomla adapters are preserved as optional source with explicitly configured compatible roots and are disabled by default. An optional terminal Jupyter helper selects an existing interpreter and keeps its state private. External application start/stop controls are not generalized into an arbitrary command endpoint. The complete original specialized implementation is also retained in the protected deployment recovery archive. Source preservation, fixture coverage and live verification on a compatible deployment remain distinct claims.
