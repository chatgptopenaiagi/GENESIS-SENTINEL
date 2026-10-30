# Installation

Linux with Python 3.10+ is required. `venv` and pip must be available in the Python you select. Runtime code uses only Python's standard library. Reuse an existing Python; do not install another distribution just for Sentinel. No root permission is needed for a user-owned prefix. See TEST-RESULTS.json for actual platform/version verification; untested platforms remain unqualified.

## Verify a release

Download the assets from the tagged GitHub prerelease, then run from their directory:

```bash
sha256sum --check SHA256SUMS
```

The checksum list covers the uploaded payloads; it cannot authenticate itself. Obtain it from the intended repository/release. No detached signing key is configured for v0.1.0.

## Wheel

```bash
python3 -m venv "$HOME/.local/share/genesis-sentinel/venv"
"$HOME/.local/share/genesis-sentinel/venv/bin/python" -m pip install --no-index --no-deps ./genesis_arch_sentinel-0.1.0-py3-none-any.whl
"$HOME/.local/share/genesis-sentinel/venv/bin/genesis-sentinel" --help
"$HOME/.local/share/genesis-sentinel/venv/bin/genesis-sentinel" init
"$HOME/.local/share/genesis-sentinel/venv/bin/genesis-sentinel" refresh --quick
```

State/configuration defaults to the current user's state directory, not a development checkout. To isolate it explicitly:

```bash
/path/to/venv/bin/genesis-sentinel --state-dir /absolute/private/state init
/path/to/venv/bin/genesis-sentinel --state-dir /absolute/private/state register-python /absolute/science/python
/path/to/venv/bin/genesis-sentinel --state-dir /absolute/private/state refresh --full
```

Dashboard and Jupyter helpers use `GENESIS_SENTINEL_HOME` to select that same state directory:

```bash
export GENESIS_SENTINEL_HOME=/absolute/private/state
/path/to/venv/bin/genesis-sentinel-dashboard start
/path/to/venv/bin/genesis-sentinel-dashboard access
```

The dashboard prints its actual local URL; the helper requires a terminal to display credentials. Keep a mobile Linux environment active while using its browser. Do not assume Android will keep background processes alive.

## Source distribution

Unpack the sdist and build with a Python environment already containing `build`, `setuptools` and `wheel`:

```bash
python3 -m build --no-isolation
```

Install the resulting wheel into a clean venv as above. Offline installation from an sdist requires preexisting build tools; no claim is made that a minimal Python alone can build a wheel without them.

## Linux installation archive

Extract the archive into an empty directory and inspect INSTALL.md and install.sh. Run:

```bash
./install.sh --python /absolute/path/to/python3 --prefix /absolute/new/user-owned/venv
```

The installer creates a new venv, installs the bundled wheel without network access or runtime dependencies, and prints commands. It refuses to overwrite an existing prefix. It does not modify shell startup, Codex files, global configuration, service definitions, package-manager databases or unrelated projects. The launchers are Python console-script wrappers, not native standalone binaries. Architecture-named archives identify the tested installation target; they do not contain compiled ARM/x86 code.

## Configuration and optional integrations

Start from `genesis-sentinel init`, then edit that state's config.json or use the registration commands. Example templates use synthetic paths and data and are not a copy of the development machine. No Science Lab, Joomla, Conda or Jupyter installation is mandatory. Optional Jupyter uses an existing registered environment containing JupyterLab and never installs it automatically.

Pacman post-transaction notification is optional. The example hook is a template only; installation never writes `/etc` automatically. Edit absolute executable/state paths and install it only through your normal administrator procedure. Notifications mark dirty; refresh performs bounded metadata reconciliation. pip/Conda/manual changes are detected when metadata is refreshed, not by a universal resident watcher.
