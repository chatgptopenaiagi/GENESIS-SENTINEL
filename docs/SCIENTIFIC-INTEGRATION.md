# Scientific integration without merging environments

Sentinel inventories and verifies existing scientific software; it does not install scientific engines as runtime dependencies of the package. A laboratory, Anaconda environment, Miniforge environment and project virtual environment can coexist. Register each interpreter separately and use the exact interpreter on a capability record.

The examples below are synthetic. Replace paths with your own existing locations; no `/opt/example-*` directory is required by the installer.

## Register an existing scientific interpreter

```bash
genesis-sentinel register-python /opt/example-lab/.venv/bin/python
genesis-sentinel register-root /opt/example-lab
genesis-sentinel refresh --full
genesis-sentinel status
```

Find the actual capability identifier in `CAPABILITY-GRAPH.json`; environment identifiers are derived from local prefixes and must not be copied from another machine. Run `genesis-sentinel verify CAPABILITY_ID` for a supported fixed operation. A package without a supported operation remains metadata-only until an appropriate check is implemented.

## What a bounded scientific check establishes

| Check | What is established | What is not established |
| --- | --- | --- |
| Small NumPy matrix result | That named array operation works under the recorded interpreter | Performance, every BLAS operation or all numerical conditioning cases |
| SciPy integral compared with its analytic value | One integration path meets its tolerance | Arbitrary scientific-model correctness |
| Symbolic derivative | One symbolic operation yields the required expression | Safe parsing of arbitrary user expressions |
| Molecular descriptor and rendering | One molecule can be parsed, described and rendered | Experimental measurement or pharmacological validity |
| CPU tensor result | CPU tensor arithmetic works | GPU acceleration |
| CUDA availability and optional GPU result | The separately reported CUDA/GPU facts | Compatibility with every accelerator workload |
| Import-only Jupyter check | The module imports | Authenticated browser service, a running kernel or successful notebook computation |

Sentinel's subprocess limits reduce runaway work. They do not turn the scientific interpreter into an untrusted-code sandbox. Only register executables and environments you trust.

## Optional existing evidence

A scientific project may already have a registry containing engine versions, operation scopes, verification timestamps and evidence paths. Such data remains external evidence with its original time and provenance. It must be explicitly configured rather than discovered by crawling private research directories. A changed package version or environment signature can invalidate its applicability.

Do not manually rewrite old verification timestamps to make a capability appear fresh. Run a new supported check and retain its result. Domain-specific saved computations, units, precision, source hashes and experimental provenance remain the laboratory's responsibility; the inventory is not a replacement for a scientific result store.

## Existing browser applications

A local JupyterLab, laboratory or Joomla service can be shown by an explicitly configured loopback endpoint. A response from that endpoint is a service observation only. Default service observation does not load another application's private credentials or expose generic program execution. The optional Jupyter helper manages its own loopback workbench under the selected state directory, with an explicitly chosen or registered existing interpreter; its authenticated Open handoff is limited to its owned process. Its lifecycle remains a terminal operation, and the helper does not install Jupyter or scientific kernels.

The original mobile deployment's fixed Science/Joomla lifecycle guards are preserved in optional `adapters.py` and in the private recovery material. Enable them only for compatible explicitly configured roots after reviewing process ownership, authentication, busy-state checks and data-preservation rules. Their fixed ports and launcher contracts are deployment-specific, not a generic scientific application management API.
