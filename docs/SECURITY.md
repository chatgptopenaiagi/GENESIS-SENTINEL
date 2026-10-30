# Security and privacy boundaries

GENESIS Sentinel is local administrative software. The operator trusts the selected state directory, registered interpreters, package-manager executables and explicitly configured deployment roots. Its safeguards reduce accidental execution, browser-origin misuse and exposure of operational data; they do not isolate Sentinel from a hostile process running as the same Linux account.

## Public source and private deployment data

The public repository and distributions contain reusable code, technical documentation, synthetic configuration/data examples and tests. They must not include a machine's runtime state directory, raw inventory snapshots, unrelated project reports, scientific result directories, notebook outputs, local logs or recovery archive.

Credentials are operational data. Codex authentication, API keys, Jupyter tokens, database credentials, SSH/WireGuard private keys and private environment variables are excluded from publication. A `.gitignore` file is useful but insufficient: publication also requires explicit source selection and inspection of the built wheel, source archive, installation archive and Git-tracked tree. Checksums establish byte integrity, not an automatic guarantee that content is appropriate to publish.

Private recovery material is kept outside the public checkout with restrictive filesystem permissions. Excluding authentication means restoration requires the operator to restore or regenerate credentials separately. Never upload the private archive as a release asset.

## Inventory execution model

Normal refresh reads metadata rather than importing every discovered scientific package. Registered interpreters are still executable programs. Python startup, installed startup hooks and metadata parsers operate under the operator account. Register only trusted interpreters and directories.

The fixed verification registry has bounded programs for specific operations. The browser and CLI do not accept arbitrary probe source code. Subprocesses have finite time/output/resource limits, separate process groups and native thread limits. These guards are not a security sandbox and do not make malicious native extensions safe.

The public core does not automatically update packages, execute unknown project installers or merge library search paths across Python distributions. Conda channel records redact common embedded credential/token URL forms, but raw operational inventory is still private: path names, package choices and metadata can be sensitive even without an obvious token.

## Dashboard authentication

The dashboard binds to `127.0.0.1` and serves local HTTP. It is not designed for public hosting, direct LAN exposure or a reverse proxy that drops its origin assumptions.

Its local login uses a generated password. The private credential file retains the information needed for the operator access helper and is protected by filesystem permissions; it is not a hardware-backed secret store. Sessions use random tokens, private server-side storage and HttpOnly/SameSite cookies. State-changing requests require an authenticated session or supported private authentication together with a valid CSRF value and allowed local Origin. Host validation rejects unexpected names.

The server caps request bodies, uses finite socket waits and limits concurrent handler slots. Its headers disable caching, framing and common content-type ambiguity. Login throttling is a local abuse guard, not a distributed authentication service. Plain HTTP loopback does not provide network TLS; the design relies on local binding and the Linux/browser boundary.

The access helper intentionally requires an operator terminal before displaying credentials. Passwords and tokens must not be copied into general test logs or published reports. Generic request logging does not print token-bearing URLs.

## Reports and service controls

Reports are explicitly cataloged local files with constrained types and size bounds. The endpoint receives an opaque report identifier, not a path. Private credential directories, traversal and symlink redirection are rejected. Configuring a report is a deliberate disclosure to authenticated dashboard users; Sentinel cannot determine whether every paragraph of an operator-selected report is confidential.

Default service entries are loopback observations. Endpoint response, process identity, application correctness and scientific verification remain distinct. Default management dispatch is limited to fixed inventory refresh.

Optional deployment adapters must be enabled explicitly and point to a compatible trusted installation. Their fixed launchers and original loopback ports are not a generic browser shell. Identity and known busy-state checks are required before destructive lifecycle actions; uncertainty disables control. A local operator who can edit trusted configuration already has authority to select executable application roots. The configuration file is therefore within the trust boundary.

The dashboard's own process lifecycle compares command and kernel start identity before sending signals. A reused PID alone is not sufficient ownership evidence. Stopping the dashboard while a management job is active is refused through its normal controls.

## Persistence and recovery limits

Advisory locks protect cooperating writers, not arbitrary programs editing the files. Immutable generation hashes detect changed snapshot content when validation runs; they do not authenticate the origin of every package on the computer. Atomic replacement and directory synchronization reduce interruption risk but cannot promise behavior for every filesystem, hardware fault or power event.

The audit stream is retained evidence, not a tamper-proof ledger. The operator account can alter it. Recovery should select a complete validated generation and then reconcile current software; restoring an old snapshot must not be presented as a fresh inventory.

## Reporting an issue

Avoid posting credentials, real inventory dumps or unpublished research in a public issue. A useful report includes the Sentinel version, tested platform, a synthetic configuration, the command that failed and a redacted error. Reproduce with a disposable state directory when practical. No private vulnerability-reporting channel or response-time commitment is implied by this prerelease.
