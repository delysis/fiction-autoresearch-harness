#!/usr/bin/env python3
"""Admit, validate, and render evidence-linked fiction research notes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fiction_harness.research_journal import (  # noqa: E402
    ResearchNote,
    append_note,
    evidence_from_paths,
    read_journal,
    render_journal,
    utc_now,
)


DEFAULT_DIRECTORY = ROOT / "04_review_governance/research_notes"
DEFAULT_JOURNAL = DEFAULT_DIRECTORY / "fiction_research_journal.v1.jsonl"
DEFAULT_RENDER = DEFAULT_DIRECTORY / "fiction_research_journal.v1.md"


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--journal", type=Path, default=DEFAULT_JOURNAL)
    subcommands = value.add_subparsers(dest="command", required=True)

    admit = subcommands.add_parser("admit")
    admit.add_argument("--note-id", required=True)
    admit.add_argument("--status", choices=("observation", "inference", "decision"), required=True)
    admit.add_argument("--claim", required=True)
    admit.add_argument("--evidence", action="append", type=Path, required=True)
    admit.add_argument("--arm")
    admit.add_argument("--seed", type=int)
    admit.add_argument("--limitation", action="append", default=[])
    admit.add_argument("--next-test", required=True)
    admit.add_argument("--created-at")
    admit.add_argument("--project-root", type=Path, default=ROOT)
    admit.add_argument("--render", type=Path, default=DEFAULT_RENDER)

    render = subcommands.add_parser("render")
    render.add_argument("--output", type=Path, default=DEFAULT_RENDER)

    subcommands.add_parser("validate")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "admit":
        note = ResearchNote(
            note_id=args.note_id,
            created_at=args.created_at or utc_now(),
            status=args.status,
            claim=args.claim,
            evidence=evidence_from_paths(
                args.evidence, project_root=args.project_root
            ),
            arm=args.arm,
            seed=args.seed,
            limitations=tuple(args.limitation),
            next_test=args.next_test,
        )
        record = append_note(args.journal, note)
        render_journal(args.journal, args.render)
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 0
    if args.command == "render":
        rendered = render_journal(args.journal, args.output)
        print(json.dumps({"entries": len(read_journal(args.journal)), "output": str(args.output), "bytes": len(rendered.encode("utf-8"))}, indent=2))
        return 0
    notes = read_journal(args.journal)
    print(json.dumps({"valid": True, "entries": len(notes), "journal": str(args.journal)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
