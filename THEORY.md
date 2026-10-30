# The theory and implemented algorithms of GENESIS Sentinel

GENESIS Sentinel maintains inspectable knowledge about a Linux software environment outside an AI conversation. Its central object is a timestamped capability record: a named operation, the interpreter or executable that can provide it, the evidence supporting its state, and the conditions under which that evidence becomes stale.

This document explains the implemented engineering model. It does not claim access to hidden model reasoning, a change to model weights, a new theory of machine intelligence, or priority over established inventory and transaction techniques. The design decisions described here are recoverable from source, tests and observable behavior. See [architecture](ARCHITECTURE.md), [engineering decisions](docs/ENGINEERING-DECISIONS.md) and [source provenance](docs/SOURCE-PROVENANCE.md).

## 1. Persistent software capability awareness

A conversation can refer to a tool that no longer exists, confuse two environments, or repeatedly install a dependency already available elsewhere. Sentinel addresses the external-state part of that problem by persisting six coordinated views:

| View | Purpose |
| --- | --- |
| `SOFTWARE-INVENTORY.json` | Observed environments, distributions, command-line tools and configured service endpoints |
| `ENVIRONMENTS.json` | Separate interpreter prefixes and their package metadata |
| `CAPABILITY-GRAPH.json` | Named operation records with environment-provider edges |
| `PROJECT-MAP.json` | Registered project roots, availability and selected manifest fingerprints |
| `CURRENT-STATUS.md` | Human-readable snapshot summary |
| `SESSION-BRIEF.md` | Concise bootstrap context for a later engineering session |

A `GENERATION-MANIFEST.json` digest map covers the six views for validation and recovery. These files are external records. A new session must actually read them, check their generation and timestamps, and interpret their evidence. Merely writing a file does not make a model remember it. Installing the Python package also does not automatically edit another application's global instructions.

## 2. Discovery across multiple Python environments

Discovery starts with registered interpreters and roots, not a recursive scan of the machine. Conda roots and environment registry files can contribute prefixes. Registered projects contribute conventional immediate environment paths such as `.venv/bin/python`, `venv/bin/python` and `env/bin/python`. The portable configuration does not require a particular account name, a laboratory directory or a particular Conda installation prefix.

Environment identity derives from the environment directory rather than the final executable symlink. This distinction matters because two virtual environments often use the same underlying Python binary. Canonicalizing only the binary would incorrectly merge their package sets. Aliases of one environment directory can be deduplicated while distinct prefixes remain separate.

For an interpreter requiring observation, a bounded subprocess runs that interpreter with `-I` and reads installed-distribution metadata through `importlib.metadata`. It returns the interpreter version, prefixes, module search paths and distribution names, versions and locations. Sentinel does not invoke project setup scripts or import every discovered scientific package during inventory. The registered interpreter remains a trusted executable: Python startup and installed `.pth` behavior are not a security sandbox.

Conda native-package metadata is read separately from `conda-meta`. It can describe libraries with no Python distribution record. Conda package presence and Python importability are therefore distinct observations, even when their names resemble one another.

## 3. Installed software and verified operations

Sentinel uses explicit states rather than interpreting every detected package as working:

| State | Meaning |
| --- | --- |
| `DISCOVERED` | A root, endpoint or other item was observed within the discovery scope |
| `INSTALLED` | Metadata or an executable establishes presence |
| `IMPORTABLE` | A fixed import check succeeded; this is still narrower than useful operation correctness |
| `FUNCTIONALLY_VERIFIED` | A named bounded operation produced its required result |
| `STALE` | Prior verification no longer meets its signature or age conditions |
| `FAILED_CHECK` | A performed check failed; retained evidence explains that attempt |
| `UNAVAILABLE` | A required observed resource, such as a registered interpreter, is absent |
| `UNKNOWN` | Evidence does not establish a stronger conclusion |
| `STOPPED` | A configured service connection was refused; this does not prove a broken installation |

The core has a finite operation registry and fixed probe programs. Examples include an exact small matrix result, a quadrature comparison with an analytic value, a symbolic derivative, a PNG signature, and a known molecular descriptor calculation. A successful check verifies its stated scope, not every operation in a package. An import-only notebook check must remain labelled importable.

CPU tensors, installed accelerator packages, CUDA build metadata, runtime CUDA availability and a successful GPU computation are separate facts. Sentinel must not infer GPU computation from package names, a device node or a passed CPU calculation.

## 4. Historical knowledge and current machine state

A retained report establishes what a check found at its recorded time. A live HTTP response establishes that an endpoint responded now. Neither substitutes for the other. A completed project milestone is also not proof that its service is currently running.

Sentinel preserves both metadata observation time and functional verification time. A metadata refresh can reuse prior operation evidence without pretending that the operation ran again. Failed checks are retained instead of being overwritten by a success narrative. The dashboard translates evidence into understandable labels and source links; its chronology is a view over records, not an inferred account of unrecorded achievements.

The portable release contains synthetic examples rather than the original operator's engineering history. Operators may explicitly register local reports. A report's modification time is not an exact achievement time and should be labelled as such when used as a fallback.

## 5. Detecting installation, removal and change

Each inventory can be flattened into stable record keys:

- Environment records use a prefix-derived environment identifier.
- Python distribution records combine that identifier with a normalized distribution name.
- Conda package records use a separate namespace under the environment.
- Native package and command-line tool records retain their own namespaces.
- Configured service observations retain their endpoint identity.

The difference algorithm compares the union of old and new keys. A new key is `ADDED`, a missing key is `REMOVED`, and an unequal value under the same key is `CHANGED`. Compared fields include versions, locations, signatures and recorded states where relevant. The human view can distinguish version changes and executable relocations from generic state changes.

The first inventory is a baseline. An `ADDED` record in that first observation is not proof that the software was installed at observation time. Likewise, removal from a configured discovery scope can mean the configuration changed; the audit must be interpreted with its source and scope.

Optional package-manager hooks are notifications. They mark inventory dirty rather than running an expensive inventory inside the package manager transaction. Pip, Conda and manual changes are reconciled when metadata is next inspected. There is no universal resident installation watcher.

## 6. Incremental inventory refresh

For each interpreter, the signature algorithm hashes a deterministic collection of filesystem metadata. This includes executable and virtual-environment configuration metadata, relevant site-package entries and distribution metadata files, and Conda metadata/history. A virtual environment inheriting system packages must also account for the inherited base environment.

A quick refresh reuses an installed environment's saved metadata when its signature is unchanged. It updates observation bookkeeping and marks the environment as cached. A full refresh bypasses this metadata cache and reinspects registered interpreters. Full refresh remains targeted; it does not mean a whole-device crawl or an automatic scientific correctness audit.

Signatures are invalidation hints. File size, inode and nanosecond modification time are not a cryptographic integrity proof of all package code. An unusual in-place edit preserving the observed metadata can escape quick detection. Selected project manifests have content hashes, but Sentinel does not hash every installed binary by default.

## 7. Capability graph construction

The capability graph is deliberately small and inspectable. It is JSON containing capability nodes and environment-provider edges, not a graph database or learned representation.

The construction algorithm joins normalized installed package names with the finite operation registry. A matching package creates a capability with its environment identifier, absolute interpreter, version, installation location and supported operation description. Explicit verification records can elevate that capability's state when their signature matches the current environment and their timestamp remains within the configured verification lifetime.

A changed environment signature invalidates matching prior evidence. Verification age can expire even when no software changed. Unavailable or failed environment observation must not be hidden behind a historical green badge. Optional external scientific registries remain evidence sources with their own provenance; configuration alone is not proof of success. Re-verification through Sentinel's own named probe is the most direct route to a current local result.

For discovered CLI tools, presence and a package-manager version association can be recorded without executing arbitrary `--version` commands. A tool without a supported fixed probe remains installed or unknown in operation scope.

## 8. Evidence-based tool selection

The intended selection procedure is explicit:

1. Read a consistent generation and check its freshness and error markers.
2. Find a capability matching the required operation.
3. Inspect its absolute interpreter or executable, version, environment and limitations.
4. If operation evidence is stale or absent, run a supported explicit probe or retain the weaker state.
5. Use the recorded environment without mixing binary libraries from another distribution.
6. Preserve new scientific outputs and their domain-specific provenance separately from inventory metadata.

This is decision support for an engineer or a cooperating agent. Sentinel does not automatically solve every dependency choice, claim that the first match is optimal, or execute arbitrary programs suggested by a model.

## 9. Concurrency and single-writer protection

Cooperating inventory writers use an advisory `flock` lock in the state directory. Lock acquisition has a finite wait. A competing writer times out with an explicit error instead of interleaving two commits. Verification also uses the writer boundary when updating the latest verification index.

Advisory locks coordinate code that honors them. They do not stop the operator, another program or a broken filesystem from modifying files directly. Dirty notifications use a separate short `dirty.lock` boundary and unique event identifiers because they should not wait for a complete inventory. A refresh captures its initial marker, then compares and clears under that short lock, preserving notifications arriving after its initial observation.

The dashboard additionally serializes management jobs so that two browser actions do not launch overlapping refreshes. Authentication does not replace the writer lock: the two mechanisms protect different boundaries.

## 10. Atomic inventory updates

A refresh produces a unique generation directory. It writes all six reader-facing views there before changing the active generation. JSON views embed the generation identifier; the Markdown views state it for inspection.

Stable report paths point through one `current` symlink. Replacing that symlink with `os.replace` commits the complete generation in one namespace operation. Readers who need a consistent multi-file analysis resolve `current` once and read all files from that immutable directory. Independently following six symlinks while a commit occurs can straddle two generations; the pointer mechanism does not remove the need to pin a read transaction.

Individual files are written through temporary files, flushed, synchronized, renamed, and followed by parent-directory synchronization. The generation manifest and relevant generation/pointer directories are also synchronized. Process-interruption safety and full power-loss durability are different claims: the host filesystem and hardware still determine their guarantees, and a passed interrupted-write fixture is not a power-failure experiment.

## 11. Recovery from interrupted writes

The active pointer is the commit authority. A refresh interrupted before pointer replacement leaves the prior complete generation active. Partially written, uncommitted generation directories can remain for diagnosis. The append-only change stream is an audit, not the authority to choose a snapshot: an interruption can occur after commit but before an audit append completes.

Errors are recorded outside the last good generation so a failed refresh can mark the old snapshot stale without destroying it. Recovery selects a retained complete generation, validates its manifest, all six file hashes and embedded JSON generation identities, and repoints `current` under the writer lock. It records the recovery and marks state dirty because an old generation still needs reconciliation with current software. It does not delete research, reinstall applications or blindly replay project scripts.

A corrupted or missing configuration must not silently replace registered roots with default guesses. Restore configuration from a protected backup or repair the explicit error, then perform a fresh targeted refresh. Old snapshots remain historical evidence after recovery.

## 12. Discovery by a fresh Codex session

The original deployment used managed instruction text and a wrapper around the already installed CLI. The wrapper performed bounded refresh preparation, then executed the original program with preserved argument boundaries. A failed preparation left a stale marker and allowed the original CLI to proceed; it did not require an upgrade or an authentication rewrite.

The portable release makes integration opt-in. An operator chooses the guidance file or launcher destination and the original executable. The installed entry point is a Python wrapper, not a newly compiled Codex binary. Its source and tests establish its own behavior; they do not establish universal instruction-file discovery across all CLI versions, graphical clients, other accounts or existing conversations.

The integration bootstrap directs a cooperating session to the current brief, capability graph and markers. A fresh process can demonstrate that the generated information is independently readable. This is a reproducibility test of external awareness, not evidence that a model retained previous hidden state.

## 13. Persistent engineering handoff

A useful handoff identifies the active generation, the scope of completed work, evidence paths, test outcomes, preserved failures, actual startup commands and unfinished limitations. The brief is short enough to bootstrap a session; detailed data remains in inspectable files rather than being copied wholesale into a prompt.

Engineering history remains source-backed. A later successful test may establish that an earlier failure was repaired, but it does not establish the exact edit time unless an edit record exists. A handoff should distinguish completed implementation, observed verification, active work, failed attempts and unknown scope.

Public release handoffs must also distinguish repository source state, locally built artifacts, published assets and downloaded artifact verification. A local build is not proof that a remote release exists.

## 14. Resource-aware operation on mobile ARM64

The source deployment motivated sequential environment inspection, metadata caching, explicit rather than automatic scientific imports, bounded subprocess output, finite wall/CPU/address-space limits and native thread counts set to one. There is no requirement to run a resident watcher, a graph database, containers or a second Python distribution.

A bounded subprocess is still real work on the operator's account. Address-space caps are not exact resident-memory budgets; native allocators, libraries and kernel behavior affect outcomes. Parent-death/process-group cleanup is platform-dependent and should be tested on the actual Linux environment. A proot environment can deny hardware or kernel interfaces even when normal file and loopback HTTP operations work.

ARM64 and x86_64 use the same pure-Python inventory algorithms, but that fact alone does not verify every platform. Scientific packages, packaging tools, Linux facilities and the Python build can differ. Release metadata must state actual tested platforms and leave untested ones unclaimed.

## 15. External software knowledge and model memory

Sentinel changes the information available to a future session. It does not change model weights, guarantee attention to every instruction, or prove prevention of arbitrary future engineering mistakes. Its records can themselves be stale, incomplete or wrong, so their freshness and evidence are part of the model.

The reusable contribution is the composition: separate environment identities, metadata-first inventory, named-operation evidence, explicit stale states, atomic snapshot publication, retained history and a concise fresh-session bootstrap, with a human interface over the same records. The mechanisms underneath—content/metadata hashing, graph records, advisory locking, atomic rename, immutable generations, bounded subprocesses and managed configuration blocks—are established engineering techniques.

The project-specific value should be evaluated through reproducible behavior and scoped acceptance tests. Claims about general AI memory, intelligence, causal error prevention or scientific validity require separate evidence and are not established by an inventory system.
