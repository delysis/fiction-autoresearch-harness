from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


LAB_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB_ROOT))

from fiction_harness.core import canonical_json_text, hash_json, stable_prefix  # noqa: E402
from fiction_harness.schemas import (  # noqa: E402
    Candidate,
    PersonaPacket,
    RunConfig,
    SceneSpec,
    ScoreCard,
)


class SchemaTests(unittest.TestCase):
    def make_scene(self) -> SceneSpec:
        return SceneSpec(
            scene_id="S01",
            title="The Calibration Game",
            function="Entrance and enchantment",
            pov="Mara",
            target_words_min=2800,
            target_words_max=3600,
            opening_image="Mara arrives at sunset.",
            desire="Prove that goodness and competence can coexist.",
            obstacle="A glamorous status game converts perception into authority.",
            pressure_ladder=("flattery", "public task", "apparent telepathy"),
            turn="Mara changes the cue channel.",
            aftermath="Jonah recognizes what she did.",
            teaching_payload="Desire can sharpen attention without commanding action.",
            source_ids=("MPC-01", "LEV-01"),
            beat_map=("Arrival", "Calibration", "Control", "Recognition"),
            continuity_facts=("Mara is observant but uncertain.",),
            heat_ceiling="No consummation or graphic sex acts.",
        )

    def test_scene_round_trip_and_wire_type(self) -> None:
        scene = self.make_scene()
        encoded = scene.to_dict()
        self.assertEqual(encoded["record_type"], "SceneSpec")
        self.assertEqual(SceneSpec.from_dict(json.loads(canonical_json_text(encoded))), scene)

    def test_persona_round_trip_preserves_relationship_lists(self) -> None:
        persona = PersonaPacket(
            persona_id="mara",
            name="Mara",
            version="1",
            role="protagonist",
            age=22,
            invariants=("Observant.",),
            false_beliefs=("Uncertainty forfeits authority.",),
            attention_habits=("Notices changes in pace.",),
            relationship_variants={"jonah": ("Trusts restraint.",)},
        )
        restored = PersonaPacket.from_dict(persona.to_dict())
        self.assertEqual(restored, persona)
        self.assertEqual(restored.relationship_variants["jonah"], ("Trusts restraint.",))

    def test_run_candidate_and_scorecard_round_trip(self) -> None:
        digest = "a" * 64
        run = RunConfig(
            run_id="run-001",
            scene_id="S01",
            pipeline="direct",
            model_role="generator",
            prompt_hash=digest,
            source_hashes={"stable_prefix": digest},
            seeds=(101, 202),
            sampling={"temperature": 0.9, "top_p": 0.95},
            output_words_min=2800,
            output_words_max=3600,
            output_tokens=6000,
            persona_ids=("mara",),
        )
        candidate = Candidate(
            candidate_id="direct-101",
            run_id=run.run_id,
            pipeline=run.pipeline,
            scene_id=run.scene_id,
            seed=101,
            text="A complete scene.",
            parent_trace={},
            evidence_ids=("MPC-01",),
            telemetry={"tokens": 12},
            lineage=("direct",),
            prompt_hash=digest,
        )
        score = ScoreCard(
            candidate_id=candidate.candidate_id,
            judge_id="judge-e4b",
            label_order=("A",),
            hard_gates={"word_count": True},
            rubric_scores={"narrative_force": 15.0},
            passage_evidence={"narrative_force": ("A complete scene.",)},
            defects=("thin ending",),
            romance_diagnostics={"attraction_and_impediment": True},
            total_score=75.0,
            eligible=True,
        )
        self.assertEqual(RunConfig.from_dict(run.to_dict()), run)
        self.assertEqual(Candidate.from_dict(candidate.to_dict()), candidate)
        self.assertEqual(ScoreCard.from_dict(score.to_dict()), score)

    def test_validation_rejects_invalid_ranges_and_unknown_fields(self) -> None:
        data = self.make_scene().to_dict()
        data["target_words_min"] = 4000
        data["target_words_max"] = 3000
        with self.assertRaises(ValueError):
            SceneSpec.from_dict(data)
        data = self.make_scene().to_dict()
        data["invented"] = True
        with self.assertRaisesRegex(ValueError, "unknown SceneSpec fields"):
            SceneSpec.from_dict(data)

    def test_continuation_lineage_round_trip_and_partial_rejection(self) -> None:
        digest = "a" * 64
        candidate = Candidate(
            candidate_id="s02-raw-01",
            run_id="s02-run",
            pipeline="raw_organic",
            scene_id="S02",
            seed=101,
            text="Approved prefix.\n\nContinuation.",
            continuation_text="Continuation.",
            parent_trace={},
            evidence_ids=("MPC-02",),
            telemetry={},
            lineage=("call:s02",),
            prompt_hash=digest,
            approved_prefix_id="s01-finalist-B",
            approved_prefix_hash="b" * 64,
            feedback_brief_hash="c" * 64,
            generation_mode="raw_organic",
        )
        self.assertEqual(Candidate.from_dict(candidate.to_dict()), candidate)
        invalid = candidate.to_dict()
        invalid["feedback_brief_hash"] = ""
        with self.assertRaisesRegex(ValueError, "supplied together"):
            Candidate.from_dict(invalid)

    def test_hashes_and_prefixes_are_order_stable(self) -> None:
        self.assertEqual(hash_json({"b": 2, "a": 1}), hash_json({"a": 1, "b": 2}))
        first = stable_prefix({"canon": "law", "brief": "promise"})
        second = stable_prefix({"brief": "promise", "canon": "law"})
        self.assertEqual(first, second)
        self.assertIn("@@SECTION brief", first)


if __name__ == "__main__":
    unittest.main()
