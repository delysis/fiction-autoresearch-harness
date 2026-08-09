from __future__ import annotations

import unittest

from fiction_harness.program_diversity import (
    CausalSignature,
    SemanticRole,
    analyze_batch_convergence,
    compare_signatures,
    extract_causal_signature,
    extract_signatures,
    pairwise_similarities,
    select_diverse_programs,
)


def _mentor_rescue_program(program_id: str = "mentor-rescue") -> dict[str, object]:
    return {
        "program_id": program_id,
        "event_sequence": [
            "Mara enters the late Fulcrum seminar.",
            "Livia accurately notices that Mara craves belonging.",
            "Livia treats Mara's uncertainty as consent to more interpretation.",
            "Miriam opens the door and ends the session.",
            "Jonah refuses an immediate kiss and is mocked by the group.",
            "Fulcrum leadership reframes the failure as Mara's resistance.",
        ],
        "causal_roles": {
            "antagonist_truth": "Livia is right that Mara longs to belong.",
            "protagonist_error": "Mara believes her no requires proof.",
            "exit_agency": "The senior mentor Miriam interrupts and opens the door.",
            "lover_cost": "Jonah defers the kiss and loses social status.",
            "institutional_consequence": "The academy reinterprets the failure as resistance.",
            "uncanny_remainder": "A bodily chill lingers after every cue channel is blocked.",
        },
        "aftermath": "A residual chill remains as Mara and Jonah leave together.",
    }


def _self_exit_program(program_id: str = "self-exit") -> dict[str, object]:
    return {
        "program_id": program_id,
        "events": [
            "Mara arrives for the midnight exercise.",
            "Livia correctly sees Mara's attraction to Jonah.",
            "Mara mistakes attraction for a command she must suppress.",
            "Mara names her desire, opens the door herself, and walks out.",
            "Jonah publicly contradicts Livia and risks his scholarship.",
            "The students split into factions and demand an investigation.",
        ],
        "antagonist_truth": "The facilitator accurately perceives the protagonist's intimacy hunger.",
        "protagonist_error": "The protagonist confuses attraction with an order.",
        "exit_agency": "The protagonist leaves under her own power.",
        "lover_cost": "The lover risks funding and his place at school.",
        "institutional_consequence": "The institution splits and begins an investigation.",
        "uncanny_remainder": "Livia knows a hidden childhood fact Mara never told anyone.",
        "ending": "Mara departs alone while the impossible knowledge remains unexplained.",
    }


class SignatureExtractionTests(unittest.TestCase):
    def test_structured_program_extracts_six_roles_events_and_endpoint(self) -> None:
        signature = extract_causal_signature(_mentor_rescue_program())
        self.assertIsInstance(signature, CausalSignature)
        self.assertEqual(signature.program_id, "mentor-rescue")
        self.assertEqual(len(signature.events), 6)
        self.assertEqual(signature.events[0].actor, "protagonist")
        self.assertIn(
            "c:mentor_rescue",
            signature.roles.get(SemanticRole.EXIT_AGENCY),
        )
        self.assertIn(
            "c:institution_reinterprets",
            signature.roles.institutional_consequence,
        )
        self.assertTrue(signature.endpoint)

    def test_freeform_headings_normalize_to_same_causal_decisions(self) -> None:
        freeform = """
        Antagonist is right about: The facilitator truly sees the heroine's hunger for community.
        Protagonist is wrong about: The heroine assumes a refusal has to be justified with evidence.
        Who enables the exit: An older woman interrupts the exercise and opens the door.
        What the lover risks: Her beloved waits instead of claiming a kiss and sacrifices his standing.
        Institutional response: Fulcrum explains away the failed reading as the subject's resistance.
        Residual mystery: A chill lingers after posture and vocal cues have been controlled.

        Events:
        - The heroine comes to the institution's night meeting.
        - The facilitator correctly recognizes her need for acceptance.
        - The facilitator claims uncertainty means permission to continue.
        - The older woman stops the meeting and opens the door.
        - The beloved waits rather than kiss her and loses status.
        - Leadership spins the failed test as resistance.

        Ending: The unexplained bodily sensation remains when the pair leave.
        """
        structured = extract_causal_signature(_mentor_rescue_program())
        paraphrase = extract_causal_signature(freeform, program_id="paraphrase")
        similarity = compare_signatures(structured, paraphrase)
        self.assertGreater(similarity.role_similarity, 0.66)
        self.assertGreater(similarity.event_similarity, 0.50)
        self.assertGreater(similarity.overall_similarity, 0.58)
        self.assertGreaterEqual(len(similarity.matching_roles), 4)

    def test_unheaded_freeform_still_extracts_events_and_roles(self) -> None:
        text = (
            "Livia is right that Mara wants approval. "
            "Mara wrongly assumes she must justify no. "
            "Mara opens the door herself and leaves. "
            "Jonah risks his reputation by refusing to cooperate. "
            "The academy retaliates against both of them. "
            "One impossible prediction remains unexplained."
        )
        signature = extract_causal_signature(text, program_id="plain")
        self.assertEqual(len(signature.events), 6)
        self.assertTrue(signature.roles.antagonist_truth)
        self.assertTrue(signature.roles.protagonist_error)
        self.assertIn("c:self_authored_exit", signature.roles.exit_agency)
        self.assertTrue(signature.roles.lover_cost)
        self.assertTrue(signature.roles.institutional_consequence)
        self.assertTrue(signature.roles.uncanny_remainder)

    def test_extraction_is_deterministic_and_ids_are_checked(self) -> None:
        program = _self_exit_program()
        self.assertEqual(
            extract_causal_signature(program),
            extract_causal_signature(program),
        )
        with self.assertRaisesRegex(ValueError, "duplicate program_id"):
            extract_signatures((program, program))

    def test_project_native_dimension_names_are_understood(self) -> None:
        signature = extract_causal_signature(
            {
                "id": "native-fields",
                "event_chain": ["Mara refuses.", "She opens the door."],
                "difficult truth Livia sees": "Mara wants to be chosen.",
                "Mara's error": "She thinks no needs evidence.",
                "Mara's exit-causing action": "Mara opens the door herself.",
                "Jonah's cost or needed repair": "Jonah loses status.",
                "consequence for Fulcrum": "The institution splits.",
                "concrete unexplained observation": "A prediction remains impossible.",
            }
        )
        self.assertEqual(len(signature.events), 2)
        for role in SemanticRole:
            self.assertTrue(signature.roles.get(role), role)


class SemanticComparisonTests(unittest.TestCase):
    def test_role_changes_matter_even_when_event_wording_is_reused(self) -> None:
        original = _mentor_rescue_program("original")
        changed = _mentor_rescue_program("changed")
        changed["causal_roles"] = {
            "antagonist_truth": "Livia is wrong about Mara's motives and observes nothing accurately.",
            "protagonist_error": "Mara makes no error and understands every signal.",
            "exit_agency": "Mara opens the door herself and walks out.",
            "lover_cost": "Jonah risks his scholarship and career.",
            "institutional_consequence": "The academy apologizes and reforms its policy.",
            "uncanny_remainder": "Nothing mysterious or unexplained remains.",
        }
        same_events = compare_signatures(
            extract_causal_signature(original),
            extract_causal_signature(changed),
        )
        self.assertGreater(same_events.event_similarity, 0.95)
        self.assertLess(same_events.role_similarity, 0.45)
        self.assertLess(same_events.overall_similarity, 0.65)

    def test_pairwise_comparison_is_symmetric(self) -> None:
        left, right = extract_signatures(
            (_mentor_rescue_program(), _self_exit_program())
        )
        forward = compare_signatures(left, right)
        reverse = compare_signatures(right, left)
        self.assertEqual(forward.event_similarity, reverse.event_similarity)
        self.assertEqual(forward.role_similarity, reverse.role_similarity)
        self.assertEqual(forward.endpoint_similarity, reverse.endpoint_similarity)
        self.assertEqual(forward.overall_similarity, reverse.overall_similarity)

    def test_missing_roles_do_not_count_as_matches(self) -> None:
        left = extract_causal_signature(
            {"id": "left", "events": ["Mara leaves."]}
        )
        right = extract_causal_signature(
            {"id": "right", "events": ["Mara leaves."]}
        )
        comparison = compare_signatures(left, right)
        self.assertEqual(comparison.role_similarity, 0.0)
        self.assertEqual(comparison.matching_roles, ())


class BatchDiversityTests(unittest.TestCase):
    def test_near_duplicate_paraphrase_is_rejected_but_causal_variant_survives(self) -> None:
        duplicate = _mentor_rescue_program("duplicate")
        duplicate["event_sequence"] = [
            "The protagonist enters Fulcrum after dark.",
            "The antagonist rightly sees her hunger for community.",
            "The antagonist treats doubt as permission to diagnose her.",
            "The mentor interrupts and opens the exit.",
            "The lover waits to kiss and loses standing.",
            "The institution reframes failure as resistance.",
        ]
        result = select_diverse_programs(
            (
                _mentor_rescue_program(),
                duplicate,
                _self_exit_program(),
            ),
            near_duplicate_threshold=0.58,
            role_threshold=0.68,
        )
        self.assertEqual(result.selected_ids, ("mentor-rescue", "self-exit"))
        self.assertEqual(len(result.rejected), 1)
        self.assertEqual(result.rejected[0].candidate_id, "duplicate")
        self.assertEqual(result.rejected[0].matched_id, "mentor-rescue")
        self.assertTrue(result.rejected[0].reasons)

    def test_limit_uses_input_as_deterministic_priority_order(self) -> None:
        first = _mentor_rescue_program("first")
        second = _self_exit_program("second")
        result = select_diverse_programs((first, second), limit=1)
        self.assertEqual(result.selected_ids, ("first",))

    def test_overconverged_batch_reports_collapsed_semantic_roles(self) -> None:
        programs: list[dict[str, object]] = []
        for index in range(4):
            program = _mentor_rescue_program(f"copy-{index}")
            program["premise"] = f"Lexically decorative variant {index}."
            programs.append(program)
        report = analyze_batch_convergence(programs)
        self.assertTrue(report.overconverged)
        self.assertEqual(len(report.near_duplicate_pairs), 6)
        self.assertGreaterEqual(len(report.collapsed_roles), 5)
        self.assertGreater(report.near_duplicate_fraction, 0.9)
        self.assertTrue(report.reasons)

    def test_causally_varied_batch_is_not_falsely_collapsed(self) -> None:
        third = {
            "id": "collective-exit",
            "events": [
                "The students test Livia's reading.",
                "A peer calls a vote and the group ends the exercise together.",
                "Jonah stays inside and loses Mara's trust.",
                "The academy adopts a stop policy.",
            ],
            "antagonist_truth": "Livia accurately notices Mara is attracted to power.",
            "protagonist_error": "Mara trusts the institution to know best.",
            "exit_agency": "The group negotiates a collective end.",
            "lover_cost": "Jonah risks and loses Mara's trust.",
            "institutional_consequence": "The school reforms its stop policy.",
            "uncanny_remainder": "The final result is only coincidence.",
            "ending": "The group leaves separately after changing the rule.",
        }
        report = analyze_batch_convergence(
            (
                _mentor_rescue_program(),
                _self_exit_program(),
                third,
            ),
            near_duplicate_threshold=0.72,
            mean_similarity_threshold=0.55,
        )
        self.assertFalse(report.overconverged, report.reasons)
        self.assertLess(report.near_duplicate_fraction, 0.40)

    def test_pair_count_is_n_choose_two(self) -> None:
        signatures = extract_signatures(
            (
                _mentor_rescue_program(),
                _self_exit_program(),
                {"id": "small", "events": ["Mara refuses.", "She leaves."]},
            )
        )
        self.assertEqual(len(pairwise_similarities(signatures)), 3)

    def test_preextracted_and_raw_programs_can_be_mixed(self) -> None:
        signature = extract_causal_signature(
            _mentor_rescue_program("already-extracted")
        )
        result = select_diverse_programs(
            (signature, _self_exit_program("raw"))
        )
        self.assertEqual(result.selected_ids, ("already-extracted", "raw"))

    def test_invalid_thresholds_and_limit_fail_loudly(self) -> None:
        with self.assertRaises(ValueError):
            select_diverse_programs((_mentor_rescue_program(),), limit=0)
        with self.assertRaises(ValueError):
            analyze_batch_convergence(
                (_mentor_rescue_program(),),
                near_duplicate_threshold=1.1,
            )


if __name__ == "__main__":
    unittest.main()
