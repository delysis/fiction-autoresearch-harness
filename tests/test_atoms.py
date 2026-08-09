from __future__ import annotations

import unittest

from fiction_harness.atoms import (
    AtomRealization,
    AtomRealizationReport,
    AtomBundle,
    DramaticAtom,
    atom_role_distance,
    render_novelist_packet,
    render_scene_novelist_packet,
    select_atoms_weighted_without_replacement,
    validate_atom_realization_report,
)
from fiction_harness.core import sha256_text


def atom(atom_id: str, probability: float = 0.05) -> DramaticAtom:
    return DramaticAtom(
        atom_id=atom_id,
        scene_id="S02",
        sequence_id="s02-seq-1-trap",
        kind="social_move",
        participants=("Mara", "Livia"),
        setup_fact="Mara has not eaten since the briefing.",
        observable_move="Livia places salted almonds beside Mara's water.",
        observable_response="Mara eats one before answering.",
        local_constraint_change="Refusing Livia's next request now risks seeming ungrateful.",
        required_entities=("salted almonds",),
        source_call_id="call-1",
        source_text_hash=sha256_text("donor"),
        source_span="Livia placed salted almonds beside the water.",
        proposed_probability=probability,
    )


class DramaticAtomTests(unittest.TestCase):
    def test_atom_round_trip_is_strict(self) -> None:
        original = atom("a1")
        self.assertEqual(DramaticAtom.from_dict(original.to_dict()), original)
        invalid = original.to_dict()
        invalid["theme"] = "care"
        with self.assertRaisesRegex(ValueError, "unknown"):
            DramaticAtom.from_dict(invalid)

    def test_atom_rejects_control_language_and_invalid_probability(self) -> None:
        value = atom("a1").to_dict()
        value["observable_move"] = "The rubric demands a reversal."
        with self.assertRaisesRegex(ValueError, "evaluator"):
            DramaticAtom.from_dict(value)
        value = atom("a1").to_dict()
        value["proposed_probability"] = 0.10
        with self.assertRaisesRegex(ValueError, "below 0.10"):
            DramaticAtom.from_dict(value)

    def test_bundle_hash_and_weighted_selection_are_reproducible(self) -> None:
        pool = tuple(atom(f"a{i}", 0.01 + i / 1000) for i in range(1, 7))
        left = select_atoms_weighted_without_replacement(pool, count=4, seed=17)
        right = select_atoms_weighted_without_replacement(pool, count=4, seed=17)
        self.assertEqual([x.atom_id for x in left], [x.atom_id for x in right])
        bundle = AtomBundle(
            bundle_id="b1",
            scene_id="S02",
            sequence_id="s02-seq-1-trap",
            ordered_atom_ids=("a1", "a2"),
            required_atom_ids=("a1",),
            optional_atom_ids=("a2",),
            source_pool_hash="pool-hash",
            selection_policy_hash="policy-hash",
            editorial_overlay="Keep the access change administrative.",
            editorial_overlay_hash=sha256_text(
                "Keep the access change administrative."
            ),
        )
        self.assertEqual(AtomBundle.from_dict(bundle.to_dict()), bundle)

    def test_novelist_packet_omits_donor_provenance_and_probabilities(self) -> None:
        selected = atom("a1")
        bundle = AtomBundle(
            bundle_id="b1",
            scene_id="S02",
            sequence_id="s02-seq-1-trap",
            ordered_atom_ids=("a1",),
            required_atom_ids=("a1",),
            optional_atom_ids=(),
            source_pool_hash="pool-hash",
            selection_policy_hash="policy-hash",
            editorial_overlay="",
            editorial_overlay_hash="",
        )
        packet = render_novelist_packet(
            manuscript_tail="Mara looked at the monitor.",
            current_state={"location": "alignment lab"},
            character_invariants={"Mara": "sheltered and technically competent"},
            word_range=(875, 1100),
            endpoint="Mara remains inside with one fewer practical option.",
            bundle=bundle,
            atoms={"a1": selected},
        )
        rendered = str(packet)
        self.assertNotIn("source_call_id", rendered)
        self.assertNotIn("source_span", rendered)
        self.assertNotIn("proposed_probability", rendered)
        self.assertNotIn("selection_policy_hash", rendered)
        self.assertIn("salted almonds", rendered)

    def test_realization_requires_separate_exact_action_and_consequence(self) -> None:
        selected = atom("a1")
        bundle = AtomBundle(
            bundle_id="b1",
            scene_id="S02",
            sequence_id="s02-seq-1-trap",
            ordered_atom_ids=("a1",),
            required_atom_ids=("a1",),
            optional_atom_ids=(),
            source_pool_hash="pool-hash",
            selection_policy_hash="policy-hash",
            editorial_overlay="",
            editorial_overlay_hash="",
        )
        text = "Livia set down the almonds. Mara ate one before answering."
        report = AtomRealizationReport(
            candidate_id="c1",
            bundle_hash=bundle.bundle_hash,
            per_atom=(
                AtomRealization(
                    atom_id="a1",
                    status="realized",
                    action_evidence="Livia set down the almonds.",
                    consequence_evidence="Mara ate one before answering.",
                ),
            ),
            endpoint_status="pass",
            invented_conflicts=(),
            judge_id="human-1",
        )
        validate_atom_realization_report(
            candidate_text=text, bundle=bundle, report=report
        )
        invalid = AtomRealizationReport(
            candidate_id="c1",
            bundle_hash=bundle.bundle_hash,
            per_atom=(
                AtomRealization(
                    atom_id="a1",
                    status="partial",
                    action_evidence="Livia set down the almonds.",
                    consequence_evidence="",
                    explanation_only=True,
                ),
            ),
            endpoint_status="pass",
            invented_conflicts=(),
            judge_id="human-1",
        )
        with self.assertRaisesRegex(ValueError, "required atoms"):
            validate_atom_realization_report(
                candidate_text=text, bundle=bundle, report=invalid
            )

    def test_scene_packet_projects_ordered_phases_without_donor_metadata(self) -> None:
        first = atom("a1")
        second_value = atom("a2").to_dict()
        second_value["sequence_id"] = "s02-seq-2-choice"
        second = DramaticAtom.from_dict(second_value)

        def bundle(atom_id: str, sequence_id: str) -> AtomBundle:
            return AtomBundle(
                bundle_id=f"bundle-{atom_id}",
                scene_id="S02",
                sequence_id=sequence_id,
                ordered_atom_ids=(atom_id,),
                required_atom_ids=(atom_id,),
                optional_atom_ids=(),
                source_pool_hash="pool-hash",
                selection_policy_hash="policy-hash",
                editorial_overlay="",
                editorial_overlay_hash="",
            )

        packet = render_scene_novelist_packet(
            opening_runway="Rain moved through the redwoods.",
            current_state={"location": "alignment lab"},
            character_invariants={"Mara": "technically competent"},
            scene_contract={"pov": "close third Mara"},
            word_range=(2800, 3300),
            endpoint="Mara freely chooses the next step.",
            phase_bundles=(
                bundle("a1", "s02-seq-1-trap"),
                bundle("a2", "s02-seq-2-choice"),
            ),
            atoms={"a1": first, "a2": second},
        )
        self.assertEqual(
            [phase["phase_id"] for phase in packet["phases"]],
            ["s02-seq-1-trap", "s02-seq-2-choice"],
        )
        rendered = str(packet)
        for forbidden in (
            "source_call_id",
            "source_span",
            "proposed_probability",
            "selection_policy_hash",
            "model",
            "score",
            "judge",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_event_role_distance_detects_structural_difference(self) -> None:
        first = atom("a1")
        second_value = atom("a2").to_dict()
        second_value.update(
            {
                "kind": "mystery_observation",
                "participants": ["Mara", "Jonah"],
                "required_entities": ["access log"],
            }
        )
        second = DramaticAtom.from_dict(second_value)
        bundle_a = AtomBundle(
            bundle_id="ba",
            scene_id="S02",
            sequence_id="s02-seq-1-trap",
            ordered_atom_ids=("a1",),
            required_atom_ids=("a1",),
            optional_atom_ids=(),
            source_pool_hash="pool",
            selection_policy_hash="policy",
            editorial_overlay="",
            editorial_overlay_hash="",
        )
        bundle_b = AtomBundle(
            bundle_id="bb",
            scene_id="S02",
            sequence_id="s02-seq-1-trap",
            ordered_atom_ids=("a2",),
            required_atom_ids=("a2",),
            optional_atom_ids=(),
            source_pool_hash="pool",
            selection_policy_hash="policy",
            editorial_overlay="",
            editorial_overlay_hash="",
        )
        self.assertEqual(
            atom_role_distance(bundle_a, bundle_b, atoms={"a1": first, "a2": second}),
            1.0,
        )


if __name__ == "__main__":
    unittest.main()
