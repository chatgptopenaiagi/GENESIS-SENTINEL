# Portability and platform claims

The installable package is pure Python and uses the standard library at runtime. Its supported implementation target is Linux, including the Linux facilities used for advisory locking, resource limits, process groups, symlinks and process identity. The wheel's `py3-none-any` tag describes its lack of compiled extension payload; it is not evidence that every operating system or Python build has been tested.

## State and dependency separation

- Package code is installed into the selected Python environment; private state is in the selected state directory.
- The default interpreter is the Python running Sentinel. Additional interpreters are explicit registrations or bounded conventional Conda discoveries.
- Anaconda, Miniforge, a scientific laboratory, Joomla, JupyterLab and Codex are optional existing software. None is required to import the package or create its first inventory.
- The command is `genesis-sentinel`, keeping an existing `sentinel` command and its state separate.
- Optional integration names its guidance destination and existing executable. Installation does not edit Codex binaries, authentication, global settings or shell profiles.
- The package does not supply a scientific Python distribution or reinstall applications.

## Native package inventory

Arch's pacman adapter reads installed-package records when pacman is available and collection is enabled. Its database location can be configured. Without pacman, Python/Conda discovery and registered projects still work; complete dpkg/rpm package inventory is not implemented in v0.1.0. Command-line tool versions without an owning-package mapping can remain unknown because Sentinel does not execute arbitrary tools merely to ask their versions.

## Platform verification

Actual platform/interpreter test outcomes belong in `TEST-RESULTS.json` and the release report. A successful ARM64 installation does not verify x86_64. A CI workflow file is not a passed CI run. An x86_64 installation archive or compatibility claim must be accompanied by actual evidence from that platform.

Linux ARM64 is the source deployment's native platform. Android/proot may deny `/proc` or hardware interfaces and may kill background services. A working loopback service does not establish reboot survival, touchscreen interaction or GPU acceleration. If a required process-identity facility is unavailable, lifecycle controls should retain uncertainty rather than signal an unrelated process.

Python packaging metadata declares the intended minimum version. The exact interpreter versions exercised by release tests must be reported separately; source syntax compatibility is not a substitute for running all supported interpreter versions.

## Optional deployment adapters

Source-preserved Science/Joomla adapters are not application installers. They assume compatible launcher names, private credential structures, process records, loopback ports and application-specific busy checks, but take their roots from explicit configuration. They are disabled by default and are not required for inventory, packaging or the dashboard's default read-only service observations.

A mock or fixture test of an adapter establishes only that dispatch and guards behave under that fixture. It does not verify a different real laboratory or Joomla deployment. Existing operator installations must retain their own source, data and authentication rules.

## Unimplemented scope

Windows-native execution, macOS guarantees, universal package-manager hooks, remote inventory fleets, automatic application installation, model-memory modification, automatic public hosting and transparent integration into every Codex launch path are outside this prerelease's verified scope. Running the package in a container or emulator can be useful, but is not equivalent to testing every host facility or scientific engine.

## v0.1.0 completed evidence

The published release was tested locally on Linux aarch64/Python 3.14.6 and by completed hosted Linux x86_64 jobs on Python 3.10.22, 3.12.15 and 3.14.9. Hosted offline installer execution also passed. See [run 41142709084](https://github.com/chatgptopenaiagi/GENESIS-SENTINEL/actions/runs/41142709084) and the final test report. This records actual runs without extending claims to untested interpreters or operating systems.
