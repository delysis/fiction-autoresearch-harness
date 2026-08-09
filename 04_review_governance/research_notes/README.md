# Fiction research notes

`fiction_research_journal.v1.jsonl` is the append-only source of truth. Each
record contains a claim, status, experiment coordinate, evidence artifact and
SHA-256, limitations, next test, and a hash over the complete record.

`fiction_research_journal.v1.md` is a deterministic human-readable rendering.
It may be regenerated at any time:

```text
python3 scripts/research_journal.py render
```

Add a note with `scripts/research_journal.py admit`. Existing note IDs and
tampered records are rejected; later conclusions supersede rather than edit
earlier observations.
