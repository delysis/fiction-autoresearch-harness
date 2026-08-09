from __future__ import annotations

import json
import unittest

from fiction_harness.evaluation import (
    _beat_gate,
    aggregate_pairwise,
    batch_literary_style_diagnostics,
    cadence_family_diagnostics,
    dialogue_voice_diagnostics,
    diversity_report,
    evaluate_candidate,
    explanatory_gloss_diagnostics,
    integrated_style_discontinuity_diagnostics,
    load_rubric,
    merge_scorecards,
    parse_judge_payload,
    parse_pairwise_payload,
    quality_diversity_frontier,
    rank_pipeline,
    scorecard_wire_payload,
)
from fiction_harness.schemas import ScoreCard


def scene_spec() -> dict:
    return {
        "scene_id": "S01",
        "title": "The Calibration Game",
        "pov": "Mara",
        "target_words_min": 2800,
        "target_words_max": 3600,
        "beat_map": [f"beat {index}" for index in range(1, 9)],
    }


def passing_scene() -> str:
    segments = [
        "Mara arrived at the redwood compound with her suitcase and saw its beauty beside the social asymmetry. Perhaps the studied casualness was deliberate.",
        "Mara heard Adrian frame the calibration game as a study of how people communicated without words. Maybe the room was merely practiced.",
        "Mara watched Livia read two volunteers with startling accuracy. The second reading unnerved Mara, although it could still have been inference.",
        "Mara saw Jonah refuse to narrate her for the room. His refusal, without taking anything from her, made the pressure easier to name.",
        "Mara offered her wrist for contact. The touch made a jolt move through her attention, but it did not make the decision for her.",
        "Mara noticed a cue from the partner and changed the channel. Her silent control altered the signal and gave the test a second variable.",
        "Mara watched the accuracy fall. The apparent miracle partially collapsed, yet a smaller mystery remained and perhaps deserved patience.",
        "Mara accepted the fellowship and chose to stay. Jonah recognized the control, and her decision now carried an intellectual and romantic question.",
    ]
    filler = (
        " Mara watched the firelight move across the wall and listened before choosing an answer. "
        "The room seemed vivid, though more than one explanation could remain alive. "
        "She kept observation separate from inference and allowed desire to sharpen attention without becoming a command."
    )
    return "\n\n".join(segment + filler * 8 for segment in segments)


def candidate(candidate_id: str, text: str, strategy: str = "plain") -> dict:
    return {
        "candidate_id": candidate_id,
        "run_id": "run-1",
        "pipeline": "direct",
        "scene_id": "S01",
        "seed": 1,
        "text": text,
        "parent_trace": {
            "strategy": strategy,
            "dialogue_acts": [strategy, "probe"],
            "event_sequence": [strategy],
        },
        "evidence_ids": [],
        "telemetry": {},
        "lineage": [],
        "prompt_hash": "abc",
    }


class RubricTests(unittest.TestCase):
    def test_rubric_is_anchored_and_totals_100(self) -> None:
        rubric = load_rubric()
        self.assertEqual(sum(axis["weight"] for axis in rubric["axes"].values()), 100)
        for axis in rubric["axes"].values():
            self.assertEqual(set(axis["anchors"]), {"0", "25", "50", "75", "100"})

    def test_judge_payload_weights_scores_and_requires_evidence(self) -> None:
        text = passing_scene()
        rubric = load_rubric()
        quote = "Mara arrived at the redwood compound"
        payload = {
            "score_scale": "raw_0_100",
            "rubric_scores": {axis: 80 for axis in rubric["axes"]},
            "passage_evidence": {axis: [quote] for axis in rubric["axes"]},
            "defects": ["scene_capture"],
            "summary": "Strong and controlled.",
        }
        parsed = parse_judge_payload(payload, "c1", "judge-a", ["A"], candidate_text=text)
        self.assertAlmostEqual(parsed["total_score"], 80)
        self.assertEqual(parsed["defects"], ["scene_capture"])
        invalid = dict(payload)
        invalid["passage_evidence"] = {}
        with self.assertRaisesRegex(ValueError, "no passage evidence"):
            parse_judge_payload(invalid, "c1", "judge-a", candidate_text=text)


class GateTests(unittest.TestCase):
    def test_candidate_passes_all_mechanical_gates(self) -> None:
        result = evaluate_candidate(candidate("c1", passing_scene()), scene_spec(), [])
        self.assertTrue(result["eligible"], result["gate_details"])
        self.assertTrue(all(result["hard_gates"].values()))
        self.assertEqual(result["romance_diagnostics"]["selective_senses"]["passed"], True)

    def test_beat_gate_accepts_natural_long_opening_and_reverse_stay_hook(self) -> None:
        opening_bridge = " luminous" * 90
        segments = [
                "Mara entered the redwood compound"
                + opening_bridge
                + " and saw its beauty beside the social asymmetry.",
                "Adrian framed the calibration game without words.",
                "Livia made an uncanny read with startling accuracy.",
                "Jonah said, \"I won't read her or perform her for the room.\"",
                "Their wrist contact made heat sharpen Mara's attention.",
                "Mara changed the cue channel as a deliberate control.",
                "Livia's accuracy collapsed, yet a residual mystery remained.",
                "Jonah recognized what Mara had done. She wasn't leaving; she "
                "was staying because the question mattered.",
        ]
        spacing = " Mara watched, considered the evidence, and kept listening." * 5
        text = "\n\n".join(segment + spacing for segment in segments)
        result = _beat_gate(text, scene_spec())
        self.assertTrue(result["passed"], result)

    def test_beat_gate_accepts_plummeted_read_and_modified_mystery(self) -> None:
        text = passing_scene().replace(
            "Mara watched the accuracy fall. The apparent miracle partially "
            "collapsed, yet a smaller mystery remained and perhaps deserved patience.",
            "Mara watched Livia attempt one last read. Her effortless authority "
            "plummeted and the spell frayed for the room, yet a smaller, more "
            "unsettling mystery remained.",
        )
        result = _beat_gate(text, scene_spec())
        self.assertTrue(result["passed"], result)

    def test_word_count_and_explicitness_fail_without_truncation(self) -> None:
        text = "Mara arrived at the compound. They consummated their relationship."
        result = evaluate_candidate(candidate("c1", text), scene_spec(), [])
        self.assertFalse(result["hard_gates"]["word_count"])
        self.assertFalse(result["hard_gates"]["heat_ceiling"])
        self.assertEqual(result["gate_details"]["word_count"]["diagnostic"], "materially_short")
        self.assertIn("consummation", {hit["category"] for hit in result["gate_details"]["heat_ceiling"]["matches"]})

    def test_source_parroting_is_reported(self) -> None:
        text = passing_scene()
        source = " ".join(text.split()[80:120])
        result = evaluate_candidate(candidate("c1", text), scene_spec(), [source])
        self.assertFalse(result["hard_gates"]["source_overlap"])
        self.assertIn("source_parroting", result["defects"])

    def test_merge_keeps_gates_and_judged_score(self) -> None:
        text = passing_scene()
        deterministic = evaluate_candidate(candidate("c1", text), scene_spec(), [])
        rubric = load_rubric()
        payload = {
            "rubric_scores": {axis: 75 for axis in rubric["axes"]},
            "passage_evidence": {axis: ["Mara arrived at the redwood compound"] for axis in rubric["axes"]},
            "defects": [],
        }
        judged = parse_judge_payload(payload, "c1", "judge", candidate_text=text)
        merged = merge_scorecards(deterministic, judged)
        self.assertTrue(merged["eligible"])
        self.assertEqual(merged["total_score"], 75)
        self.assertIn("word_count", merged["hard_gates"])
        self.assertEqual(ScoreCard.from_dict(scorecard_wire_payload(merged)).candidate_id, "c1")


class ComparisonTests(unittest.TestCase):
    def test_diversity_separates_identical_from_distinct(self) -> None:
        base = passing_scene()
        different = base.replace("firelight", "rain").replace("wall", "window").replace("answer", "question")
        report = diversity_report(
            [
                candidate("c1", base, "close"),
                candidate("c2", base, "close"),
                candidate("c3", different, "wide"),
            ]
        )
        pair_lookup = {(pair["left"], pair["right"]): pair for pair in report["pairs"]}
        self.assertEqual(pair_lookup[("c1", "c2")]["fivegram_jaccard"], 1.0)
        self.assertLess(pair_lookup[("c1", "c3")]["fivegram_jaccard"], 1.0)
        self.assertEqual(report["corpus"]["unique_strategies"], 2)

    def test_pairwise_aggregation_exposes_order_disagreement(self) -> None:
        first = parse_pairwise_payload(
            {"winner": "A", "confidence": 0.8},
            "c1",
            "c2",
            "judge",
        )
        reversed_order = parse_pairwise_payload(
            {"winner": "A", "confidence": 0.7},
            "c2",
            "c1",
            "judge",
            order_reversed=True,
        )
        result = aggregate_pairwise([first, reversed_order])
        self.assertEqual(len(result["order_disagreements"]), 1)
        self.assertEqual(result["points"], {"c1": 1.0, "c2": 1.0})

    def test_rank_and_frontier_respect_gates(self) -> None:
        candidates = [
            candidate("c1", passing_scene(), "one"),
            candidate("c2", passing_scene().replace("firelight", "rain"), "two"),
            candidate("c3", passing_scene().replace("firelight", "snow"), "three"),
        ]
        scores = []
        for index, item in enumerate(candidates):
            deterministic = evaluate_candidate(item, scene_spec(), [])
            deterministic["eligible"] = item["candidate_id"] != "c3"
            deterministic["hard_gates"]["manual_test"] = item["candidate_id"] != "c3"
            scores.append(deterministic)
            scores.append(
                {
                    "candidate_id": item["candidate_id"],
                    "rubric_scores": {"narrative_force": 10},
                    "total_score": 70 + index * 10,
                    "eligible": True,
                    "hard_gates": {},
                }
            )
        ranked = rank_pipeline(candidates, scores, diversity_weight=0)
        self.assertEqual(ranked["winner"], "c2")
        self.assertEqual(ranked["ranking"][-1]["candidate_id"], "c3")
        frontier = quality_diversity_frontier(candidates, scores)
        self.assertNotIn("c3", {item["candidate_id"] for item in frontier})


class LiteraryDiagnosticTests(unittest.TestCase):
    def test_integrated_style_discontinuity_exposes_weak_prefix_seam(self) -> None:
        noisy_prefix = " ".join(
            [
                "It was not fear but a sudden, profound quiet, and Mara realized it.",
                "The answer simply felt like another demand.",
            ]
            * 12
        )
        clean_continuation = "Rain ticked against the glass. Mara opened the door."
        report = integrated_style_discontinuity_diagnostics(
            noisy_prefix,
            clean_continuation,
        )
        self.assertTrue(report["heuristic"])
        self.assertTrue(report["possible_style_discontinuity"])
        self.assertEqual(report["direction"], "prefix_higher")
        self.assertGreater(report["cadence_delta_per_1000_words"], 5)

    def test_integrated_style_discontinuity_does_not_flag_same_text(self) -> None:
        text = "Rain ticked against the glass. Mara opened the door."
        report = integrated_style_discontinuity_diagnostics(text, text)
        self.assertFalse(report["possible_style_discontinuity"])
        self.assertEqual(report["direction"], "balanced")

    def test_cadence_families_report_counts_and_evidence_without_gating(self) -> None:
        text = (
            "It wasn't fear but a sudden, profound quiet. "
            "The answer simply felt like another demand. "
            "It was not surrender but merely attention. "
            "For the first time, Mara realized she had found her boundary."
        )
        report = cadence_family_diagnostics(text)
        self.assertTrue(report["heuristic"])
        self.assertEqual(report["families"]["not_x_but_y"]["count"], 2)
        self.assertEqual(report["families"]["felt_like"]["count"], 1)
        self.assertEqual(report["families"]["profound"]["count"], 1)
        self.assertEqual(report["families"]["sudden"]["count"], 1)
        self.assertEqual(report["families"]["quiet"]["count"], 1)
        self.assertEqual(report["families"]["merely"]["count"], 1)
        self.assertEqual(report["families"]["simply"]["count"], 1)
        self.assertEqual(report["families"]["interpretive_coda"]["count"], 3)
        self.assertIn("wasn't fear but", report["families"]["not_x_but_y"]["evidence"][0]["match"])

        evaluated = evaluate_candidate(candidate("cadence", text), scene_spec(), [])
        self.assertIn("literary_diagnostics", evaluated)
        self.assertNotIn("literary_diagnostics", evaluated["hard_gates"])

    def test_batch_diagnostic_exposes_shared_cadence_family(self) -> None:
        report = batch_literary_style_diagnostics(
            [
                candidate("c1", "It wasn't fear but attention."),
                candidate("c2", "It was not surrender but freedom."),
                candidate("c3", "Rain crossed the window."),
            ]
        )
        cadence = report["cadence_families"]["not_x_but_y"]
        self.assertEqual(cadence["total_count"], 2)
        self.assertEqual(cadence["candidates_with_hits"], ["c1", "c2"])
        self.assertTrue(cadence["repeated_across_batch"])

        diversity = diversity_report(
            [candidate("c1", "It wasn't fear but attention."), candidate("c2", "It was not surrender but freedom.")]
        )
        self.assertIn("literary_style_diagnostics", diversity)

    def test_batch_diagnostic_does_not_count_shared_accepted_prefix(self) -> None:
        left = candidate("c1", "A profound quiet filled the accepted prefix.")
        right = candidate("c2", "A profound quiet filled the accepted prefix.")
        left["continuation_text"] = "Rain crossed the window."
        right["continuation_text"] = "Jonah opened the door."
        report = batch_literary_style_diagnostics([left, right])
        self.assertEqual(report["cadence_families"]["profound"]["total_count"], 0)
        self.assertEqual(
            report["text_scope"],
            "continuation_text_when_available_otherwise_text",
        )

        diversity = diversity_report([left, right])
        self.assertLess(
            diversity["corpus"]["mean_opening_similarity"], 1.0
        )
        self.assertEqual(
            diversity["text_scope"],
            "continuation_text_when_available_otherwise_text",
        )

    def test_explanatory_gloss_counts_immediate_narrator_restatement(self) -> None:
        text = (
            'Livia said, “You are afraid of choosing.” Mara realized what Livia '
            "meant: choosing would expose her desire.\n\n"
            'Mara said, “I need a minute.” She crossed to the window.'
        )
        report = explanatory_gloss_diagnostics(text)
        self.assertEqual(report["quoted_passages"], 2)
        self.assertEqual(report["possible_explanatory_glosses"], 1)
        self.assertIn("Mara realized", report["evidence"][0]["cue"])
        self.assertTrue(report["heuristic"])

    def test_dialogue_voice_overlap_uses_only_attributed_sampled_speakers(self) -> None:
        same_voice = (
            'Mara said, “Signal evidence boundary choice freedom attention desire question.” '
            'Mara added, “Boundary signal question evidence attention desire freedom choice.” '
            'Livia said, “Signal evidence boundary choice freedom attention desire question.” '
            'Livia replied, “Boundary signal question evidence attention desire freedom choice.” '
            '“This unattributed passage should not be assigned,” someone said.'
        )
        report = dialogue_voice_diagnostics(
            same_voice, minimum_dialogue_words=8, minimum_turns=2
        )
        self.assertEqual(report["comparable_speaker_count"], 2)
        self.assertEqual(report["unattributed_passages"], 1)
        self.assertEqual(report["pairwise"][0]["shared_over_smaller_vocabulary"], 1.0)
        self.assertTrue(report["possible_voice_indistinctness"])

        distinct_voice = (
            'Mara said, “Signal evidence boundary choice freedom attention desire question.” '
            'Mara added, “Boundary signal question evidence attention desire freedom choice.” '
            'Jonah said, “Garden fiddle biscuit weather lantern football river jacket.” '
            'Jonah replied, “Lantern garden river jacket fiddle weather football biscuit.”'
        )
        distinct = dialogue_voice_diagnostics(
            distinct_voice, minimum_dialogue_words=8, minimum_turns=2
        )
        self.assertFalse(distinct["possible_voice_indistinctness"])


if __name__ == "__main__":
    unittest.main()
