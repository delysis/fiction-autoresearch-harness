from __future__ import annotations

import unittest

from fiction_harness.craft import (
    load_craft_profile,
    render_craft_prompt,
    render_judge_overlay,
)
from fiction_harness.evaluation import (
    GABALDON_RUBRIC_PATH,
    S02_RUBRIC_PATH,
    intimacy_craft_diagnostics,
    load_rubric,
    parse_judge_payload,
    rubric_prompt,
)


class CraftProfileTests(unittest.TestCase):
    def test_profile_is_transformative_and_complete(self) -> None:
        profile = load_craft_profile()
        self.assertEqual(profile["profile_id"], "gabaldon-intimacy-v1")
        self.assertGreaterEqual(len(profile["principles"]), 10)
        self.assertNotIn("Excerpt", str(profile))
        self.assertIn("non-sex sex scene", str(profile["s01_application"]))

    def test_generation_planning_and_editorial_modules_are_distinct(self) -> None:
        generation = render_craft_prompt(mode="generation")
        planning = render_craft_prompt(mode="planning")
        editorial = render_craft_prompt(mode="editorial")
        self.assertIn("S01 APPLICATION", generation)
        self.assertIn("emotional transaction", planning.lower())
        self.assertIn("Repair mechanics-only", editorial)
        self.assertNotEqual(generation, editorial)
        self.assertIn("emotional_transaction", render_judge_overlay())

    def test_v2_rubric_retains_weights_and_exposes_overlay(self) -> None:
        rubric = load_rubric(GABALDON_RUBRIC_PATH)
        self.assertEqual(sum(axis["weight"] for axis in rubric["axes"].values()), 100)
        self.assertIn("productive_restraint", rubric["intimacy_diagnostics"])
        self.assertIn("lust_as_emotion", rubric["defect_taxonomy"])
        prompt = rubric_prompt(rubric)
        self.assertIn("emotional_transaction", prompt)
        self.assertIn("character-specific desire", prompt.lower())

    def test_s02_rubric_replaces_s01_mechanics_and_pacing(self) -> None:
        rubric = load_rubric(S02_RUBRIC_PATH)
        self.assertEqual(rubric["rubric_id"], "s02-proof-story-v1")
        rendered = rubric_prompt(rubric)
        self.assertIn("Mara herself changes the room's available choices", rendered)
        self.assertIn("interpretive codas", rendered)
        self.assertNotIn("wrist exercise remains physically intelligible", rendered)
        self.assertEqual(rubric["pacing_targets"][-1]["beat"], "mara_authors_next_and_hook")
        self.assertIn("miriam_deus_ex_machina", rubric["defect_taxonomy"])


class CraftDiagnosticTests(unittest.TestCase):
    def test_diagnostics_recognize_embodied_consequential_scene(self) -> None:
        text = (
            "The cedar room held the watching silence. Mara looked at Jonah. "
            "“You could have answered for me,” she said. He stepped back and "
            "lowered his hand. “That would have made the answer mine.” "
            "Livia touched Mara's wrist; warm pressure changed beneath her "
            "fingertips while rain ticked at the window. Mara altered the cue "
            "and watched Livia doubt her first reading. “Again?” Livia asked. "
            "Mara laughed, uncertain and curious. Jonah refused to take the "
            "opening, and that costly restraint made her trust him. She decided "
            "to stay for the fellowship tomorrow, wanting the next question."
        )
        diagnostics = intimacy_craft_diagnostics(
            text, load_rubric(GABALDON_RUBRIC_PATH)
        )
        self.assertTrue(diagnostics["emotional_transaction"]["passed"])
        self.assertTrue(diagnostics["consequential_contact"]["passed"])
        self.assertTrue(diagnostics["productive_restraint"]["passed"])
        self.assertTrue(diagnostics["atmospheric_participation"]["passed"])

    def test_judge_diagnostic_requires_known_id_and_exact_evidence(self) -> None:
        rubric = load_rubric(GABALDON_RUBRIC_PATH)
        text = "Mara trusted the cost of Jonah's restraint."
        payload = {
            "rubric_scores": {axis: 75 for axis in rubric["axes"]},
            "passage_evidence": {axis: [text] for axis in rubric["axes"]},
            "defects": [],
            "romance_diagnostics": {
                "productive_restraint": {
                    "passed": True,
                    "evidence": "the cost of Jonah's restraint",
                    "note": "The limit creates trust.",
                }
            },
        }
        parsed = parse_judge_payload(
            payload,
            "candidate",
            "judge",
            candidate_text=text,
            rubric=rubric,
        )
        self.assertTrue(
            parsed["romance_diagnostics"]["productive_restraint"]["passed"]
        )
        payload["romance_diagnostics"] = {
            "invented_diagnostic": {"passed": True, "evidence": text}
        }
        with self.assertRaisesRegex(ValueError, "Unknown romance/intimacy"):
            parse_judge_payload(
                payload,
                "candidate",
                "judge",
                candidate_text=text,
                rubric=rubric,
            )


if __name__ == "__main__":
    unittest.main()
