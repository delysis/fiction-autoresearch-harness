from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fiction_harness.model_client import Completion
from fiction_harness.frontier import revise_candidate
from fiction_harness.provenance import (
    assert_critic_only_frontier,
    audit_repository,
    replay_artifact,
    verify_candidate_record,
)
from tests.test_authorship import TEXT, evidence_fixture


class FakeReplayClient:
    model = "gemma-fixture"

    def complete_raw(self, **_: object) -> Completion:
        return Completion(TEXT, self.model, "stop", {}, {}, {}, 0.01, {})


class ProvenanceTests(unittest.TestCase):
    def test_frontier_rewrite_entrypoint_is_disabled(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "rewriting is disabled"):
            revise_candidate(
                None,
                candidate=None,
                critique={},
                author_context=None,
                creative_profile={},
                seed=1,
            )

    def test_frontier_critic_cannot_return_replacement_prose(self) -> None:
        assert_critic_only_frontier(
            {
                "defects": [],
                "evidence": [],
                "prompt_mutation": {},
                "prediction": "More tension",
                "falsifier": "No improvement",
            }
        )
        with self.assertRaisesRegex(ValueError, "non-critic fields"):
            assert_critic_only_frontier(
                {"defects": [], "revised_text": "Better prose."}
            )

    def test_replay_witness_is_appended_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            record = evidence_fixture(root)
            (root / "replays.jsonl").unlink()
            with patch(
                "fiction_harness.provenance.model_runtime_provenance",
                return_value=record["generation_evidence"]["runtime_identity"],
            ):
                witness = replay_artifact(
                    authorship=record, client=FakeReplayClient()
                )
            self.assertTrue(witness["matches_original"])
            verified = verify_candidate_record(
                {
                    "candidate_id": "candidate-1",
                    "text": TEXT,
                    "artifact_authorship": record,
                }
            )
            self.assertIn("verified_replay", verified)

    def test_audit_quarantines_codex_runway_and_frontier_prose(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "03_scene_lab" / "runs" / "fixture"
            (run / "frontier_editor").mkdir(parents=True)
            (run / "frontier_editor" / "scene.codex.v1.md").write_text(
                "Manual prose.", encoding="utf-8"
            )
            (run / "experiment_manifest.v1.json").write_text(
                '{"canonical_path":"selected/scene.codex.v1.md"}\n',
                encoding="utf-8",
            )
            report = audit_repository(root)
            categories = {item["category"] for item in report["findings"]}
            self.assertIn("frontier_or_codex_artifact", categories)
            self.assertIn("experiment_conditioned_on_frontier_prose", categories)


if __name__ == "__main__":
    unittest.main()
