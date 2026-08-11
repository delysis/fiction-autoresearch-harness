# Fiction Autoresearch Harness — Archived

**Status: archived quarantine; diagnostic-only; not promotion-eligible.**

This repository was dispositioned on 2026-08-11 from audited base
`67b6222347e8ddc675f2bfde68ea260bc78764a4`. It is excluded from the active
release train. The former generation, appraisal, replay, and promotion commands
are disabled as public entrypoints and must not be used for production or
release decisions.

See [ARCHIVE.md](ARCHIVE.md) for the evidence-backed disposition, safe
historical export, one-way Loom diagnostic import, and the remote steward
actions that remain intentionally unperformed. Machine consumers must inspect
[ARCHIVE_STATUS.json](ARCHIVE_STATUS.json) and [RELEASE_TRAIN.json](RELEASE_TRAIN.json)
and fail closed unless both continue to deny promotion.

```bash
python3 -m fiction_harness status
python3 -m fiction_harness export --output /path/outside/the/repository
python3 -m fiction_harness loom-import \
  --export /path/to/export --output /path/to/loom-diagnostic-import.json
```

Historical source, storyworld, scene-lab, governance, apprenticeship, and
trusted-read data remain byte-preserved in this repository and may be exported
only through the content-verified diagnostic interface above.
