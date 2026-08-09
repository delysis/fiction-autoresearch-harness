from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from fiction_harness.research_journal import (
    EvidenceArtifact,
    ResearchNote,
    append_note,
    evidence_from_paths,
    read_journal,
    render_markdown,
)


HASH = "a" * 64


def note(note_id: str = "rn-fixture-001") -> ResearchNote:
    return ResearchNote(
        note_id=note_id,
        created_at="2026-08-01T00:00:00+00:00",
        status="observation",
        claim="The arm stopped below its target length.",
        evidence=(EvidenceArtifact("runs/calls.jsonl", HASH),),
        arm="short-control",
        seed=17,
        limitations=("One seed only.",),
        next_test="Repeat with three held-out seeds.",
    )


class ResearchJournalTests(unittest.TestCase):
    def test_note_hash_round_trip(self) -> None:
        original = note()
        self.assertEqual(ResearchNote.from_dict(original.to_dict()), original)

    def test_tamper_is_rejected(self) -> None:
        payload = note().to_dict()
        payload["claim"] = "Rewritten after the fact."
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            ResearchNote.from_dict(payload)

    def test_append_is_ordered_and_duplicate_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            journal = Path(directory) / "journal.jsonl"
            append_note(journal, note("rn-fixture-001"))
            append_note(journal, note("rn-fixture-002"))
            self.assertEqual(
                [item.note_id for item in read_journal(journal)],
                ["rn-fixture-001", "rn-fixture-002"],
            )
            with self.assertRaisesRegex(ValueError, "duplicate"):
                append_note(journal, note("rn-fixture-001"))

    def test_evidence_paths_are_hashed_and_relativized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "runs" / "calls.jsonl"
            artifact.parent.mkdir()
            artifact.write_text("evidence\n", encoding="utf-8")
            result = evidence_from_paths((artifact,), project_root=root)
            self.assertEqual(result[0].artifact, "runs/calls.jsonl")
            self.assertEqual(len(result[0].sha256), 64)

    def test_renderer_preserves_claim_evidence_and_next_test(self) -> None:
        rendered = render_markdown((note(),))
        self.assertIn("The arm stopped below its target length.", rendered)
        self.assertIn("runs/calls.jsonl", rendered)
        self.assertIn("One seed only.", rendered)
        self.assertIn("Repeat with three held-out seeds.", rendered)

    def test_invalid_json_line_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            journal = Path(directory) / "journal.jsonl"
            journal.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "JSON object"):
                read_journal(journal)


if __name__ == "__main__":
    unittest.main()
