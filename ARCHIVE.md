# Archival quarantine

This repository is an immutable historical research record, not an active
generation or release system. Its audited base is
`67b6222347e8ddc675f2bfde68ea260bc78764a4`. No artifact from this repository
is promotion-eligible.

The 2026-08-11 architectural audit found that exact replay accepts
artifact-selected ledger and prompt paths, those paths are not confined to a
trusted root, append-only ledgers have neither a single-writer lease nor a hash
chain, runtime configuration contains host-specific absolute paths, and the
repository lacks a package manifest and model-free CI. Repair is valid only if
all of those boundaries are repaired together. A partial retrofit would create
false confidence, so this checkout takes the audit's archival branch.

## Allowed interface

The public module entrypoint is diagnostic-only:

```bash
python3 -m fiction_harness status
python3 -m fiction_harness export --output /path/outside/the/repository
python3 -m fiction_harness loom-import \
  --export /path/to/export --output /path/to/loom-diagnostic-import.json
```

Exports accept only the trusted dataset IDs in `ARCHIVE_STATUS.json`. They
reject symbolic links and out-of-root paths, copy the selected historical
bytes, and bind every relative file ID to its size and SHA-256 digest. The Loom
adapter verifies the export envelope and every copied byte before producing a
one-way manifest marked `diagnostic_only` and `promotion_eligible: false`.

The legacy direct scripts, promotion functions, runtime launch agents, and
historical implementation remain in this quarantined tree as evidence. The
public module CLI exposes only the diagnostic commands above; legacy generation
is unsupported and must not be executed as an active release path.

## Steward state and remaining remote actions

- The local annotated tag `archive/pre-quarantine-67b6222` now binds the exact
  audited pre-quarantine commit. It has not been pushed.
- Mark the GitHub repository archived/read-only.
- Confirm that every organization-level release manifest excludes this
  repository.

The remaining operations mutate remote organization state. Their pending state
is fail-closed and recorded in `ARCHIVE_STATUS.json`; `RELEASE_TRAIN.json`
removes this checkout from the local active release train.
