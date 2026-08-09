from pathlib import Path
import unittest

from fiction_harness.heterogeneous_demonstrations import (
    SPECS,
    load_heterogeneous_demonstrations,
)


ROOT = Path(__file__).resolve().parents[1]


class HeterogeneousDemonstrationTests(unittest.TestCase):
    def test_sources_and_excerpts_are_hash_locked(self) -> None:
        demos = load_heterogeneous_demonstrations(ROOT)
        self.assertEqual(len(demos), 3)
        self.assertEqual(len({item.demonstration_id for item in demos}), 3)
        self.assertEqual(len({item.provenance["source_path"] for item in demos}), 3)
        self.assertEqual(
            {item.provenance["excerpt_words"] for item in demos},
            {1055, 1315, 770},
        )

    def test_ledgers_are_content_neutral_and_causally_explicit(self) -> None:
        demos = load_heterogeneous_demonstrations(ROOT)
        for demo in demos:
            self.assertIn("What changes:", demo.ledger)
            self.assertIn("Local stopping state:", demo.ledger)
            self.assertNotIn("Mara", demo.ledger)
            self.assertNotIn("Livia", demo.ledger)
            self.assertNotIn("Fulcrum", demo.ledger)

    def test_specs_span_distinct_story_functions(self) -> None:
        identifiers = {item.demonstration_id for item in SPECS}
        self.assertEqual(
            identifiers,
            {
                "austen-confidence-as-leverage",
                "austen-object-confession",
                "austen-teasing-to-commitment",
            },
        )


if __name__ == "__main__":
    unittest.main()
