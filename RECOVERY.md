# Recovery, rollback and removal

Stop the owned dashboard first when appropriate:

```bash
genesis-sentinel-dashboard stop
```

Remove opt-in managed guidance/launcher integration before uninstalling the wheel:

```bash
genesis-sentinel unintegrate
/path/to/venv/bin/python -m pip uninstall genesis-arch-sentinel
```

Rollback checks ownership records and preserves user modifications. Package uninstall removes package code/console scripts while retaining external state and scientific evidence. It does not remove Python, Codex, environments, registered projects or research. Do not delete a shared environment to remove Sentinel.

## Interrupted snapshots

1. Inspect `status`, runtime error/dirty markers and the committed `current` generation.
2. Keep failed/uncommitted generation directories for diagnosis.
3. Select a complete existing generation under your state directory's `generations/`.
4. Run `genesis-sentinel recover GENERATION_ID`; recovery validates reports and takes the writer lock before repointing `current`.
5. Refresh metadata afterward and explicitly reverify stale operations.

Never hand-edit individual public report symlinks to different generations. The atomic pointer is the commit authority; CHANGES.jsonl is a retained audit stream and may lag a commit interrupted immediately before its audit append. Atomic rename protects readers from mixed generations under the implemented process-interruption model. This is not a tested guarantee against storage-controller failures or arbitrary power loss.

## Local operational backups

Back up your state directory separately with restrictive permissions. Configurations, inventories, reports and project paths are operational data, not public source. Exclude active login secrets/session stores from ordinary archives; reconstruct them through the owned access helpers after restoration. Stop restored services from trusting stale PID/process identity records. Test restoration into an empty separate directory rather than overwriting a running installation.

The original MOBILE-4 deployment was preserved separately during extraction. Its private recovery archive and exact location are in the operator's private handoff, never in this repository or its release assets. That archive is access restricted, not advertised as encrypted. It excludes active authentication stores and installed venv packages; external applications/research need their own backups. The portable package does not silently import the private deployment.
