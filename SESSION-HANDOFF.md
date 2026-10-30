# GENESIS Sentinel portable release handoff

This workspace contains the published, downloaded-artifact-verified public v0.1.0 prerelease. Original deployment code and operational data remain separate. Read THEORY.md, ARCHITECTURE.md, TEST-RESULTS.json, RELEASE-MANIFEST.json and FINAL-RELEASE-REPORT.md before continuation. Do not copy a deployment state directory, private recovery archive, credentials or unrelated research into this repository.

Runtime is Python 3.10+ on Linux, standard library only. Development builds need existing build/setuptools/wheel. Use genesis-sentinel CLI and GENESIS_SENTINEL_HOME or --state-dir for disposable testing. Never aim a package test at a live state directory. Explicit guidance integration changes only named destinations; installed Codex/authentication/global configuration are not automatically modified.

Source modules live under src/genesis_sentinel; web-control assets are package data. Unit tests are synthetic plus bounded real temporary subprocesses. tools/release_acceptance.py installs the actual wheel in a disposable venv, exercises install/version/remove, explicit SQLite query, deliberate failed scientific fixture, concurrency/recovery, fresh-process brief+graph, wrapper preparation, rollback and uninstall. No model/API invocation is required. Never present those synthetic fixtures as real scientific research.

The private deployment adapters are retained as configurable optional code; default external services are read-only and default browser management is inventory refresh. Optional Jupyter requires an existing known interpreter. Recheck real application identity/busy semantics before expanding adapters.

Build with python -m build --no-isolation. Build installer bundles with tools/build_release.py, audit all staged/artifact members, and verify published download hashes before claiming a release. Platform support is evidence, not an inference from a py3-none-any filename. Preserve failed attempts and previous generations. Do not mutate a versioned release asset silently; use a new version for runtime changes after release.

Publication completed: https://github.com/chatgptopenaiagi/GENESIS-SENTINEL/releases/tag/v0.1.0. Source tag v0.1.0 resolves to 60f38e2dfea987906d3c993d5c60db7ae44f550f. Hosted run 41142709084 verified x86_64 Python 3.10/3.12/3.14 and offline installers. All 12 published assets were downloaded and hashed; downloaded-wheel acceptance passed 13/13. The final report and TEST-RESULTS.json are the authoritative evidence. Private archive location remains only in the operator's private handoff.
