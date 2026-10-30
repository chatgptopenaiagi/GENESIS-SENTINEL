# GENESIS Sentinel

An evidence-backed software inventory and human control center for Linux scientific workstations, including mobile ARM64 Linux. Sentinel records separate Python environments, checks named capabilities on demand, preserves engineering evidence and gives a new assistant session a concise view of what the machine can actually do.

This is the portable **v0.1.0 prerelease**, extracted from the functioning GENESIS MOBILE-4 deployment. It does not modify or bundle Codex, Anaconda, Miniforge, scientific applications, databases or research data. No OpenAI API or account is required. Runtime dependencies: Python 3.10+ and its standard library on Linux. Platform verification is recorded in `TEST-RESULTS.json`; a pure-Python wheel tag is not a claim of Windows/macOS support.

## Install and start

Use an existing Python installation with venv/pip support. Download the wheel and checksum manifest from [GitHub Releases](https://github.com/chatgptopenaiagi/GENESIS-SENTINEL/releases), verify checksums, then:

```bash
python3 -m venv "$HOME/.local/share/genesis-sentinel/venv"
"$HOME/.local/share/genesis-sentinel/venv/bin/python" -m pip install --no-deps ./genesis_arch_sentinel-0.1.0-py3-none-any.whl
"$HOME/.local/share/genesis-sentinel/venv/bin/genesis-sentinel" init
"$HOME/.local/share/genesis-sentinel/venv/bin/genesis-sentinel" refresh --quick
"$HOME/.local/share/genesis-sentinel/venv/bin/genesis-sentinel-dashboard" start
"$HOME/.local/share/genesis-sentinel/venv/bin/genesis-sentinel-dashboard" access
```

Open the URL printed by dashboard startup on the same device. The access helper displays login credentials only in an operator terminal. The dashboard binds to `127.0.0.1`; there is no publication, tunnel or background boot service. The Linux installation archive supplies an offline `install.sh` wrapper around these Python commands. It is not a native standalone ELF executable.

See [INSTALL.md](INSTALL.md) for full commands and [RECOVERY.md](RECOVERY.md) before changing state or removing integration.

## Know what works

```bash
genesis-sentinel register-python /absolute/path/to/science-env/bin/python
genesis-sentinel register-root /absolute/path/to/project
genesis-sentinel refresh --full
genesis-sentinel status
genesis-sentinel report
genesis-sentinel brief
```

The commands above assume the venv `bin` directory is on your PATH; its explicit absolute path also works. Sentinel defaults to `$GENESIS_SENTINEL_HOME`, or `$XDG_STATE_HOME/genesis-sentinel`, or `~/.local/state/genesis-sentinel`. `--state-dir /absolute/path` overrides that state directory. Package source is read-only at runtime; private local inventories stay in your chosen state directory.

Inventory checks metadata through each registered interpreter separately; it never combines binary packages from different environments. Optional Conda roots/current-user registries and conventional venvs under registered projects are discovered without a whole-device crawl. No arbitrary installed package is imported during inventory.

Inspect `CAPABILITY-GRAPH.json` for a capability ID, then run:

```bash
genesis-sentinel verify CAPABILITY_ID
```

An installed distribution establishes presence. An import establishes importability. Only a successful fixed bounded probe establishes its named operation. CPU and GPU evidence remain separate; a stopped web service is not a broken installation. Verification expires and is invalidated by metadata changes. A new metadata snapshot does not silently renew scientific verification.

## Human control center

Home, My software, My projects, Scientific laboratory, AI engines, Anaconda, Engineering history, Software changes and System status offer readable cards, filters, source-linked reports and local availability observations. With no configured external applications, empty pages explain what to register rather than fabricate results. Default browser management is inventory refresh only. Optional Jupyter and deployment adapters have their own documented configuration and verification boundaries; see [scientific integration](docs/SCIENTIFIC-INTEGRATION.md).

## Persistent session guidance

```bash
genesis-sentinel integrate --guidance /absolute/project/AGENTS.md
genesis-sentinel unintegrate
```

Integration is opt-in and writes an owned managed section, not model memory. An optional explicit launcher can refresh metadata and execute a chosen existing assistant CLI while preserving arguments. It does not replace installed Codex binaries, change authentication, enable unsafe approval flags, or universally intercept all launch routes. Existing conversations need to reread changed evidence themselves. Consult [THEORY.md](THEORY.md) for the distinction between external knowledge and model weights.

## Engineering and validation

```bash
python -m build --no-isolation
python -m unittest discover -s tests -v
python tools/release_acceptance.py --wheel dist/genesis_arch_sentinel-0.1.0-py3-none-any.whl --output acceptance.json
```

Build tools are development requirements, not runtime dependencies. Acceptance creates disposable environments, installs the real wheel, tests synthetic package install/upgrade/removal, failed-probe evidence, concurrency, generation recovery, fresh-process guidance and rollback, then uninstalls the package while retaining state. It does not launch an AI model or overwrite the operator's live installation.

- [THEORY.md](THEORY.md): implemented algorithms, established techniques and project-specific decisions.
- [ARCHITECTURE.md](ARCHITECTURE.md): components, contracts and failure boundaries.
- [Security](docs/SECURITY.md), [portability](docs/PORTABILITY.md), [provenance](docs/SOURCE-PROVENANCE.md).
- [Release report](FINAL-RELEASE-REPORT.md), [test evidence](TEST-RESULTS.json), [release manifest](RELEASE-MANIFEST.json).

MIT licensed. This prerelease is an engineering tool with explicit evidence limits, not a universal certification of installed scientific software.
