import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fiction_harness.composed_realization import (
    COMPOSED_OPENING_RUNWAY,
    SEGMENT_RUNWAYS,
    SEGMENTS,
    build_segment_prompt,
    build_segment_anti_copy_index,
    extract_gated_segment,
    load_promoted_segments,
    segment_gate,
)
from fiction_harness.evaluation import word_count
from fiction_harness.meta_prompting import Demonstration


class ComposedRealizationTests(unittest.TestCase):
    def setUp(self):
        self.target = {
            "character_invariants": {"Mara": "observant"},
            "occurrences": [
                {
                    "atom_id": atom_id,
                    "setup": "setup",
                    "move": "move",
                    "response": "response",
                    "constraint_change": "change",
                    "participants": ["Mara"],
                }
                for spec in SEGMENTS
                for atom_id in spec.atom_ids
            ],
        }

    def test_endpoint_bands_leave_final_assembly_inside_reachable_range(self):
        runway_words = word_count(COMPOSED_OPENING_RUNWAY)
        minimum = runway_words + sum(item.minimum_words for item in SEGMENTS)
        maximum = runway_words + sum(item.maximum_words for item in SEGMENTS)
        self.assertLess(minimum, 875)
        self.assertGreaterEqual(maximum, 875)
        self.assertLessEqual(maximum, 1100)
        self.assertEqual(
            [(item.minimum_words, item.maximum_words) for item in SEGMENTS],
            [(260, 350), (200, 270), (150, 220)],
        )

    def test_gift_runway_supplies_pending_access_without_acceptance(self):
        runway = SEGMENT_RUNWAYS["gift-and-complicity"]
        diagnostics = segment_gate("gift-and-complicity", runway)
        self.assertFalse(diagnostics["required_atoms"])
        self.assertFalse(diagnostics["premature_later_atom"])
        self.assertIn("RAW TELEMETRY", runway)
        self.assertIn("PENDING", runway)
        self.assertIn("MARA VALE", runway)
        self.assertNotIn("MARA VOSS", runway)

    def test_segment_prompt_ends_on_existing_manuscript(self):
        demo = Demonstration.create("d", "ledger", "prose", {"path": "x"})
        prompt = build_segment_prompt(
            target=self.target,
            spec=SEGMENTS[0],
            demonstrations=[demo],
            manuscript_so_far="Existing manuscript runway.",
        )
        self.assertIn("CASE 2: EDITORIAL EVENT LEDGER", prompt)
        self.assertIn("CASE 2: FINISHED MANUSCRIPT", prompt)
        self.assertNotIn("</fiction-preparation>", prompt)
        self.assertTrue(prompt.endswith("Existing manuscript runway."))

    def test_segment_prompt_preserves_supplied_stable_prefix_byte_for_byte(self):
        demo = Demonstration.create("d", "ledger", "prose", {"path": "x"})
        stable = "<fiction-preparation>\nFICTION REFERENCE LIBRARY\n\nCACHE ME"
        prompt = build_segment_prompt(
            target=self.target,
            spec=SEGMENTS[0],
            demonstrations=[demo],
            manuscript_so_far="Existing manuscript runway.",
            stable_reference_prefix=stable,
        )
        self.assertTrue(
            prompt.startswith(stable + "\n\nCASE 2: EDITORIAL EVENT LEDGER")
        )
        self.assertNotIn("EDITORIAL APPRENTICESHIP ARCHIVE", prompt)

    def test_pressure_gate_detects_raw_stream_taken_home_as_premature_access(self):
        text = (
            'During the lab session Livia poured tea. "One," Mara said. '
            '"Two," Jonah said. "Three," Livia said. She named Mara\'s fear '
            'of being merely competent, then said Mara could take the raw stream home.'
        )
        gate = segment_gate("pressure", text)
        self.assertTrue(gate["premature_later_atom"])
        self.assertFalse(gate["eligible"])

    def test_pressure_gate_detects_telemetry_key_as_premature_access(self):
        text = (
            'Livia poured tea. "You fear being merely competent," she said. '
            '"That is efficient," Mara said. "And true," Jonah said. '
            'During their late work she offered Mara a telemetry key.'
        )
        gate = segment_gate("pressure", text)
        self.assertTrue(gate["premature_later_atom"])
        self.assertFalse(gate["eligible"])

    def test_gated_extractor_stops_before_premature_next_movement(self):
        prefix = (
            'Livia poured tea into Mara\'s cup. "You fear being merely competent, not exceptional," '
            'she said. "That is an admirably economical diagnosis," Mara said. "And?" Jonah asked. '
            '"And accurate," Livia said. '
        )
        filler = " ".join(["Mara held the warm cup while the silence pressed back."] * 24)
        raw = prefix + "\n\n" + filler + "\n\nLivia offered her a telemetry key."
        segment, gate = extract_gated_segment(raw, SEGMENTS[0])
        self.assertTrue(gate["eligible"])
        self.assertNotIn("telemetry key", segment)

    def test_pressure_gate_rejects_premature_access(self):
        text = (
            'Livia poured tea into a cup. "You fear being exceptional because '
            'it costs too much," she said. Then she offered raw access to the '
            'data tablet.'
        )
        gate = segment_gate("pressure", text)
        self.assertFalse(gate["eligible"])
        self.assertTrue(gate["premature_later_atom"])

    def test_pressure_gate_rejects_outdoor_scene_reset(self):
        text = (
            'Mara stood outside on the deck. Livia poured tea into a cup. '
            '"One," Mara said. "Two," Jonah said. "Three," Livia said. '
            'Livia named her fear that she was competent but not exceptional.'
        )
        gate = segment_gate("pressure", text)
        self.assertTrue(gate["continuity_violation"])
        self.assertFalse(gate["eligible"])

    def test_final_segment_gate_accepts_choice_and_continuation(self):
        text = (
            '"Ready?" Jonah asked. "Ready," Mara said. Livia said, "Then '
            'choose." Mara touched ACCEPT on the raw-access tablet. The next '
            "sequence loaded and the session continued around her."
        )
        self.assertTrue(segment_gate("choice-and-trap", text)["eligible"])

    def test_final_segment_accepts_nondialogue_resumption_endpoint(self):
        text = (
            "The permission line remained PENDING. Mara tapped ACCEPT. "
            "Livia turned back to the primary monitor. "
            "Jonah returned to the data traces. The room resumed its ordinary "
            "motion around Mara while her tea cooled."
        )
        gate = segment_gate("choice-and-trap", text)
        self.assertEqual(SEGMENTS[-1].required_dialogue_turns, 0)
        self.assertTrue(gate["required_atoms"])
        self.assertTrue(gate["eligible"])

    def test_choice_extractor_stops_before_next_morning_time_jump(self):
        runway = SEGMENT_RUNWAYS["choice-and-trap"]
        pressure = " ".join(
            ["Refusal could be read as lack of commitment."] * 15
        )
        raw = (
            pressure
            + "\n\nMara tapped ACCEPT.\n\n"
            + "Livia turned back to the primary monitor without celebrating. "
            + "Jonah returned to the data traces. The room resumed its ordinary "
            + "motion around Mara. Her tea was cooling."
            + "\n\nIt was the next morning before she saw Jonah again."
        )
        selected, gate = extract_gated_segment(
            runway + "\n\n" + raw, SEGMENTS[-1]
        )
        self.assertTrue(gate["eligible"])
        self.assertNotIn("next morning", selected)

    def test_runway_is_not_mistaken_for_a_protected_source(self):
        source = "twelve protected source words must never be copied into a generated manuscript at all today"
        index = build_segment_anti_copy_index(
            {"demo": source}, {"demo": "project-demonstration"}
        )
        self.assertFalse(index.exact_matches(COMPOSED_OPENING_RUNWAY))
        self.assertTrue(index.exact_matches(source))

    def test_segment_gate_rejects_prompt_packet_leakage(self):
        text = (
            'NEW PROJECT PREPARATION. Livia poured tea. "One," Mara said. '
            '"Two," Jonah said. "Three," Livia said. She named Mara\'s fear '
            'that she was competent but unexceptional during the lab session.'
        )
        gate = segment_gate("pressure", text)
        self.assertIn("NEW PROJECT PREPARATION", gate["packet_leakage_markers"])
        self.assertFalse(gate["eligible"])

    def test_segment_gate_rejects_case_end_marker(self):
        text = (
            'During the lab session Livia poured tea. "One," Mara said. '
            '"Two," Jonah said. "Three," Livia said. She named Mara\'s fear '
            "that she was competent but unexceptional.\n\nEND CASE 2"
        )
        gate = segment_gate("pressure", text)
        self.assertTrue(gate["heading_or_end_marker"])
        self.assertFalse(gate["eligible"])

    def test_promoted_segment_verifies_selected_and_raw_hashes(self):
        from fiction_harness.core import canonical_json_text, sha256_text

        prefix = (
            'Livia poured tea into Mara\'s cup. "You fear being merely competent, not exceptional," '
            'she said. "That is an admirably economical diagnosis," Mara said. "And?" Jonah asked. '
            '"And accurate," Livia said. '
        )
        filler = " ".join(["Mara held the warm cup while the silence pressed back."] * 24)
        raw = prefix + "\n\n" + filler + "\n\nLivia offered her a telemetry key."
        selected, _ = extract_gated_segment(raw, SEGMENTS[0])
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            selected_path = root / "selected.md"
            raw_path = root / "raw.txt"
            manifest_path = root / "promotion.json"
            selected_path.write_text(selected, encoding="utf-8")
            raw_path.write_text(raw, encoding="utf-8")
            manifest = {
                "record_type": "ComposedSegmentPromotion",
                "version": "composed-segment-promotion.v1",
                "segments": {
                    "pressure": {
                        "selected_path": "selected.md",
                        "selected_sha256": sha256_text(selected),
                        "selected_words": word_count(selected),
                        "source_raw_path": "raw.txt",
                        "source_raw_sha256": sha256_text(raw),
                    }
                },
            }
            manifest_path.write_text(canonical_json_text(manifest), encoding="utf-8")
            promoted, provenance = load_promoted_segments(root, manifest_path)
            self.assertEqual(promoted["pressure"], selected)
            self.assertEqual(provenance["segments"], manifest["segments"])


if __name__ == "__main__":
    unittest.main()
