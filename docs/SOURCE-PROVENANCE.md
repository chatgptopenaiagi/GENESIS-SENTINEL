# Source provenance and preservation boundary

Public v0.1.0 is an extraction of the functioning GENESIS MOBILE-4 Sentinel implementation. It retains the inventory and evidence model, refactors deployment constants into configuration, and packages the reusable human interface. It is not a replacement installation on the original phone and does not bundle the operator's machine state.

## Original acceptance is historical evidence

The accepted MOBILE-4 human control center recorded 78 passing assertions and no final assertion failures across model, backend, dashboard restart, application-control and browser groups. Physical touchscreen interaction remained untested. Earlier failed/interrupted attempts were retained by that deployment.

Those outcomes establish the source deployment's recorded acceptance scope. They are not release-package tests, not independent tests on another architecture and not proof that all original applications remain running. Public release acceptance is recorded separately in `TEST-RESULTS.json` and `FINAL-RELEASE-REPORT.md` after actual clean-install and artifact tests.

## Reused components

| Original component | Public extraction | What changed |
| --- | --- | --- |
| `sentinel_core.py` | `src/genesis_sentinel/core.py`, `config.py`, `cli.py` | Retains bounded metadata inspection, signatures, normalization, probes, capability records, diffs and generations; selects state/config dynamically instead of using deployment constants |
| `sentinel` and fixed root wrappers | `genesis-sentinel` console script and module entry point | Packaging generates an interpreter-backed launcher; the existing mobile `sentinel` command is not overwritten |
| `launch.py` | `src/genesis_sentinel/launch.py` | Preserves bounded preparation, stale fallback, argument arrays and final exec; original executable/state are explicit, with no automatic unsafe-mode flags |
| `install-integration.py`, `rollback-integration.py`, shell integration | `src/genesis_sentinel/integration.py` | Opt-in destination files, owned block/wrapper tracking and conservative rollback; no root-only global integration is installed by package installation |
| `pacman-event.sh` and hook | Optional hook example and `mark-dirty` command | Hooks notify only; users must deliberately install/configure an example for their account and state directory |
| `control_model.py` | Package `control_model.py` | Retains human semantics, categories, filters, report catalog and bounded history; removes the private project catalogue and machine-specific milestones |
| `control_server.py` | Package `control_server.py` | Retains authenticated loopback serving, CSRF/Origin/Host checks and fixed dispatch; reads packaged static assets and selected state |
| `control_services.py` | Package `control_services.py` plus `adapters.py` | Generic configured observations by default; original fixed Science/Joomla lifecycle guards preserved as optional explicitly rooted deployment adapters |
| `control_lifecycle.py` and shell helpers | Package lifecycle module and dashboard console command | Uses current interpreter/package imports; retains process command/start identity before signalling |
| `jupyter.py` and Jupyter shell helpers | Package `jupyter.py` and optional terminal console command | Selects an explicit or registered existing Jupyter interpreter; no mandatory Conda prefix or package installation; state/credentials remain private |
| `web-control/` | Packaged `web-control/` assets | Retains responsive nine-page interface, search/filtering, confirmations and source links; removes statements that imply the original phone's local achievements or environment paths apply everywhere |
| Original core/launcher/rollback/control tests | Public `tests/` and release acceptance tools | Reuses behavioral cases with disposable roots and synthetic fixtures; actual public-package tests are run independently |

The extraction strengthens generation validation with a six-file checksum manifest, synchronizes relevant directories, adds an explicit validated recovery command, and synchronizes dirty-marker clearing independently of a long refresh. External scientific registries are retained as historical context rather than automatically promoted to a current Sentinel functional pass.

This is a source refactoring and packaging provenance statement, not a claim that public modules are byte-for-byte identical to the mobile files. The release manifest identifies the actual public source/artifact bytes.

## Source and evidence retained privately

The protected recovery archive preserves the original Sentinel-owned implementation, configuration, launchers, integration ownership records and retained evidence needed to reconstruct that deployment's Sentinel arrangement, subject to its documented secret exclusions. It is kept outside the public release tree and is never a public asset.

The following material is not part of the public installable distribution:

- The original raw software inventories, environment package lists, project map and private engineering timeline.
- Existing scientific research results, notebook outputs and unrelated project source.
- Machine-specific benchmark and application-acceptance reports containing operational or research details.
- Codex configuration/authentication, active Jupyter credentials, database credentials, SSH/WireGuard keys or private environment variables.
- Installed Anaconda/Miniforge/Arch environments or Codex binaries.
- Source-deployment notebook generators, kernel-registration/install orchestration and full-machine preservation scripts whose operation assumes that deployment's private projects. Their Sentinel-owned source is retained privately rather than silently generalized into a public installer.

The public package offers synthetic examples and reusable scientific integration guidance instead of copying the original research demonstrations. Existing applications remain their own software with their own licenses, data and preservation requirements.

## Verification and release traceability

A complete release distinguishes:

1. The source commit and tag.
2. The locally built wheel, source distribution and installation archive.
3. Their SHA-256 manifest.
4. The actual remote repository/release metadata, when publication succeeds.
5. Downloaded artifact bytes and clean installation results.
6. Original-deployment preservation and private-archive integrity results.

Until the corresponding remote metadata and download verification exist, publication is pending. A URL in project metadata or a CI workflow file does not establish a published or tested release. The final report must state any remaining authentication, platform or infrastructure limitation directly.
