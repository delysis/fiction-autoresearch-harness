import json
from pathlib import Path
import tempfile
import unittest

from fiction_harness.meta_prompting import (
    Demonstration,
    _append_jsonl,
    _target_atom_diagnostics,
    build_prompt,
    extract_complete_checkpoint,
    load_anti_copy_sources,
    render_occurrence_ledger,
)
from fiction_harness.core import sha256_text


class MetaPromptingTests(unittest.TestCase):
    def setUp(self):
        self.target = {
            "character_invariants": {"Mara": "observant"},
            "sequence": {"sequence_id": "seq", "endpoint": "remain inside"},
            "occurrences": [
                {
                    "setup": "Mara is tired.",
                    "move": "Livia offers tea.",
                    "response": "Mara accepts.",
                    "constraint_change": "Leaving becomes harder.",
                    "participants": ["Livia", "Mara"],
                }
            ],
        }

    def test_ledger_contains_action_and_consequence(self):
        value = render_occurrence_ledger(self.target)
        self.assertIn("Action (Livia, Mara): Livia offers tea.", value)
        self.assertIn("What changes: Leaving becomes harder.", value)
        self.assertIn("Local stopping state: remain inside", value)

    def test_paired_prompt_ends_on_manuscript_runway(self):
        demo = Demonstration.create("d1", "ledger", "prose", {"path": "x"})
        value = build_prompt(
            family="paired-icl",
            target=self.target,
            canonical_s01="Prior chapter.",
            demonstrations=[demo],
            library=[],
        )
        self.assertIn("CASE 1: EDITORIAL EVENT LEDGER", value)
        self.assertIn("CASE 1: FINISHED MANUSCRIPT", value)
        self.assertIn("</fiction-preparation>", value)
        self.assertNotIn("<manuscript>", value)
        self.assertTrue(value.endswith("promised end."))

    def test_raw_library_does_not_claim_pairing(self):
        value = build_prompt(
            family="raw-prose-library",
            target=self.target,
            canonical_s01="Prior chapter.",
            demonstrations=[],
            library=[("source", "A reference scene.")],
        )
        self.assertIn("REFERENCE SCENE 1", value)
        self.assertNotIn("FINISHED MANUSCRIPT", value)

    def test_anti_copy_loads_demo_and_library_with_hash_checks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            library_path = root / "source.txt"
            library_path.write_text("Library source prose.", encoding="utf-8")
            manifest = {
                "canonical_s01": {
                    "path": "canonical.md",
                    "sha256": sha256_text("Canonical prefix prose."),
                },
                "demonstrations": [
                    {
                        "demonstration_id": "d1",
                        "prose": "Project demonstration prose.",
                        "prose_hash": sha256_text("Project demonstration prose."),
                    }
                ],
                "library_sources": [
                    {
                        "source_id": "book.chapter-1",
                        "path": "source.txt",
                        "text_hash": sha256_text("Library source prose."),
                        "category": "public-domain-reference",
                    }
                ],
            }
            (root / "canonical.md").write_text(
                "Canonical prefix prose.", encoding="utf-8"
            )
            documents, categories = load_anti_copy_sources(root, manifest)
            self.assertEqual(
                set(documents),
                {"canonical:s01", "demo:d1", "library:book.chapter-1"},
            )
            self.assertEqual(
                categories["library:book.chapter-1"], "public-domain-reference"
            )

    def test_atom_screen_does_not_credit_incidental_words(self):
        value = _target_atom_diagnostics(
            "The session ended. Jonah was already beside Mara in an ordinary sweater."
        )
        self.assertFalse(value["checks"]["unexceptional_fear"])
        self.assertFalse(value["checks"]["jonah_complicity"])
        self.assertFalse(value["checks"]["session_continues"])

    def test_atom_screen_credits_semantic_raw_access_realization(self):
        value = _target_atom_diagnostics(
            "Livia said Mara wanted to be exceptional but feared it would be "
            "too expensive. She offered raw access. The tablet showed trace "
            "permissions; Mara touched ACCEPT. The session continued."
        )
        self.assertTrue(value["checks"]["unexceptional_fear"])
        self.assertTrue(value["checks"]["telemetry_access"])
        self.assertTrue(value["checks"]["mara_accepts"])

    def test_atom_screen_credits_contracted_exceptionality_fear(self):
        for contraction in ("aren't", "aren’t"):
            value = _target_atom_diagnostics(
                f'Livia said Mara was scared to ask for help in case it proved '
                f'you {contraction} exceptional enough.'
            )
            self.assertTrue(value["checks"]["unexceptional_fear"])

    def test_checkpoint_extraction_uses_complete_paragraph_boundary(self):
        paragraphs = [
            " ".join([f"word{index}"] * 100) + "." for index in range(10)
        ]
        value = extract_complete_checkpoint(
            "\n\n".join(paragraphs) + "\n\nunfinished tail",
            minimum_words=875,
            maximum_words=950,
        )
        self.assertEqual(len(value.split()), 900)
        self.assertTrue(value.endswith("."))

    def test_jsonl_append_is_complete_and_resumable(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "calls.jsonl"
            _append_jsonl(path, {"call_id": "a", "status": "started"})
            _append_jsonl(path, {"call_id": "a", "status": "completed"})
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual([item["status"] for item in rows], ["started", "completed"])


if __name__ == "__main__":
    unittest.main()
