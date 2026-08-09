from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from fiction_harness.continuation_evaluation import (
    _editorial_overrides,
    _literary_editor_defects,
    _pairwise_one,
    accept_editor_revisions,
    aggregate_proof_scores,
    tournament_top_two,
)
from fiction_harness.schemas import Candidate


def _candidate(identifier: str, mode: str = "raw_organic") -> Candidate:
    return Candidate(
        candidate_id=identifier,
        run_id="run",
        pipeline=mode,
        scene_id="S02",
        seed=1,
        text="Prefix.\n\nContinuation.",
        continuation_text="Continuation.",
        parent_trace={},
        evidence_ids=("MPC-02",),
        telemetry={},
        lineage=("call:x",),
        prompt_hash="a" * 64,
        approved_prefix_id="prefix",
        approved_prefix_hash="b" * 64,
        feedback_brief_hash="c" * 64,
        generation_mode=mode,
    )


def _score(candidate_id: str, scope: str, total: float, eligible: bool = True):
    axes = {
        "narrative_force": total / 5,
        "character_truth": total / 5,
        "heat_with_agency": total / 5,
        "prose_and_voice": total / 5,
    }
    return {
        "candidate_id": candidate_id,
        "scope": scope,
        "total_score": total,
        "eligible": eligible,
        "rubric_scores": axes,
        "defects": [],
    }


class ProofScoreTests(unittest.TestCase):
    def test_pairwise_allows_second_bounded_json_repair(self) -> None:
        calls: list[str] = []

        def fake_completion(**kwargs):
            calls.append(kwargs["call_id"])
            return {"content": kwargs["call_id"]}

        class Client:
            model = "judge"

        with patch(
            "fiction_harness.continuation_evaluation._resumable_completion",
            side_effect=fake_completion,
        ), patch(
            "fiction_harness.continuation_evaluation._pairwise_payload_with_exact_evidence",
            side_effect=[ValueError("bad json"), ValueError("bad evidence"), ({"winner": "A"}, [])],
        ), patch(
            "fiction_harness.continuation_evaluation.parse_pairwise_payload",
            return_value={"winner_id": "left"},
        ), patch(
            "fiction_harness.continuation_evaluation.pairwise_prompt",
            return_value="pair",
        ), patch(
            "fiction_harness.continuation_evaluation._pairwise_prefix",
            return_value="prefix",
        ):
            result = _pairwise_one(
                client=Client(),
                store=object(),
                left=_candidate("left"),
                right=_candidate("right"),
                call_id="match",
                seed=7,
                rubric={},
                reversed_order=False,
            )

        self.assertEqual(calls, ["match", "match-repair", "match-repair-2"])
        self.assertEqual(result["winner_id"], "left")

    def test_four_survivor_bracket_includes_diversity_wildcard(self) -> None:
        candidates = tuple(
            _candidate(f"c{index}") for index in range(1, 6)
        )
        rows = [
            {
                "candidate_id": f"c{index}",
                "eligible": True,
                "combined_score": 100 - index,
            }
            for index in range(1, 6)
        ]
        aggregate = {
            "by_mode": {"instruction_raw": rows},
            "generation_diagnostics": {
                "instruction_raw": {
                    "diversity": {
                        "per_candidate": {
                            "c4": {"diversity_contribution": 0.1},
                            "c5": {"diversity_contribution": 0.9},
                        }
                    }
                }
            },
        }

        def fake_pairwise(**kwargs):
            left = kwargs["left"].candidate_id
            right = kwargs["right"].candidate_id
            return {
                "candidate_a_id": left,
                "candidate_b_id": right,
                "winner_id": min(left, right),
            }

        with tempfile.TemporaryDirectory() as directory, patch(
            "fiction_harness.continuation_evaluation._pairwise_one",
            side_effect=fake_pairwise,
        ):
            result = tournament_top_two(
                candidates=candidates,
                score_aggregate=aggregate,
                compiled_dir="03_scene_lab/compiled/s02-v1-ontology",
                evaluation_dir=directory,
                client=object(),
                rubric_path=(
                    "fiction_harness/rubrics/s01_romance_v2_gabaldon.json"
                ),
            )
        mode = result["modes"]["instruction_raw"]
        self.assertEqual(mode["selected"], ["c1", "c2", "c3", "c5"])
        self.assertEqual(len(mode["semifinals"]), 2)
        self.assertEqual(mode["final_text_scope"], "complete_proof_story")

    def test_editorial_overrides_require_exact_candidate_passages(self) -> None:
        candidate = replace(
            _candidate("winner"),
            continuation_text="A precise sentence appears here. Then another.",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "editorial_overrides.json"
            path.write_text(
                json.dumps(
                    {
                        "candidate_defects": {
                            "winner": [
                                {
                                    "axis": "prose_and_voice",
                                    "passage": "A precise sentence appears here.",
                                    "named_defects": ["over-explains the action"],
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            defects = _editorial_overrides(directory, candidate, limit=1)
            self.assertEqual(defects[0]["scope"], "human_close_read")

            path.write_text(
                json.dumps(
                    {
                        "candidate_defects": {
                            "winner": [
                                {
                                    "passage": "A paraphrase does not count.",
                                    "named_defects": ["stale note"],
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "must occur exactly"):
                _editorial_overrides(directory, candidate, limit=1)

    def test_aggregate_keeps_scope_scores_and_prioritizes_eligibility(self) -> None:
        first = _candidate("first")
        second = _candidate("second")
        scores = [
            _score("first", "continuation", 80),
            _score("first", "merged_story", 82),
            _score("second", "continuation", 95, False),
            _score("second", "merged_story", 96, False),
        ]
        aggregate = aggregate_proof_scores((first, second), scores)
        self.assertEqual(aggregate["rows"][0]["candidate_id"], "first")
        self.assertEqual(aggregate["rows"][0]["combined_score"], 81)
        self.assertFalse(aggregate["rows"][1]["eligible"])
        diagnostics = aggregate["generation_diagnostics"]["instruction_raw"]
        self.assertEqual(diagnostics["candidate_count"], 2)
        self.assertIn("diversity", diagnostics)
        self.assertIn("literary_style", diagnostics)
        self.assertEqual(diagnostics["artifact_mode_labels"], ["raw_organic"])

    def test_repairable_gate_miss_remains_in_quality_competition(self) -> None:
        passing = _candidate("passing")
        repairable = _candidate("repairable")
        scores = [
            _score("passing", "continuation", 80),
            _score("passing", "merged_story", 82),
            _score("repairable", "continuation", 95, False),
            _score("repairable", "merged_story", 96, False),
        ]
        for score in scores[2:]:
            score["hard_gates"] = {"local_hfn": False, "anti_copy": True}
        aggregate = aggregate_proof_scores((passing, repairable), scores)
        self.assertEqual(aggregate["rows"][0]["candidate_id"], "repairable")
        self.assertTrue(aggregate["rows"][0]["editor_repairable"])
        self.assertEqual(aggregate["rows"][0]["failed_gates"], ["local_hfn"])

    def test_literary_preflight_promotes_repeated_cadence_to_edit_lead(self) -> None:
        score = _score("winner", "continuation", 80)
        score["literary_diagnostics"] = {
            "cadence_families": {
                "total_family_hits": 15,
                "hits_per_1000_words": 5.2,
                "families": {
                    "not_x_but_y": {
                        "count": 7,
                        "evidence": [{"match": "not fear but attention"}],
                    }
                },
            },
            "explanatory_gloss": {
                "possible_explanatory_glosses": 0,
                "evidence": [],
            },
        }
        defects = _literary_editor_defects("winner", [score])
        self.assertEqual(defects[0]["axis"], "prose_and_voice")
        self.assertIn("repeats 7 times", defects[0]["named_defects"][0])

    def test_editor_acceptance_requires_total_and_all_human_axes(self) -> None:
        raw = _candidate("raw")
        revision = replace(
            raw,
            candidate_id="raw-polished",
            parent_trace={"raw_winner": "raw"},
        )
        raw_scores = [
            _score("raw", "continuation", 80),
            _score("raw", "merged_story", 80),
        ]
        revision_scores = [
            _score("raw-polished", "continuation", 82),
            _score("raw-polished", "merged_story", 82),
        ]
        with tempfile.TemporaryDirectory() as directory:
            accepted = accept_editor_revisions(
                raw_candidates=(raw,),
                revisions=(revision,),
                raw_scores=raw_scores,
                revision_scores=revision_scores,
                output_path=Path(directory) / "decisions.json",
            )
            self.assertEqual(accepted[0].candidate_id, "raw-polished")

            worse_axis = [dict(item) for item in revision_scores]
            for item in worse_axis:
                item["rubric_scores"] = dict(item["rubric_scores"])
                item["rubric_scores"]["heat_with_agency"] = 0
            rejected = accept_editor_revisions(
                raw_candidates=(raw,),
                revisions=(revision,),
                raw_scores=raw_scores,
                revision_scores=worse_axis,
                output_path=Path(directory) / "rejected.json",
            )
            self.assertEqual(rejected[0].candidate_id, "raw")


if __name__ == "__main__":
    unittest.main()
