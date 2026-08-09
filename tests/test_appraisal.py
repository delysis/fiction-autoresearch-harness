from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from fiction_harness.appraisal import (
    blind_label_map,
    build_appraisal,
    build_internal_report,
    verify_blind_package,
)
from fiction_harness.authorship import text_sha256
from tests.test_authorship import evidence_fixture


def finalists() -> list[dict]:
    records = [
        {
            "candidate_id": "direct-secret-id",
            "pipeline": "native_best_of_n",
            "model_role": "generator_26b",
            "ontology_version": "rgo.v1",
            "story_profile_id": "fulcrum-pilot.v1",
            "scene_profile_id": "fulcrum-s01.v1",
            "resolved_profile_hash": "a" * 64,
            "author_profile_id": "jane-austen.control.v1",
            "author_profile_hash": "b" * 64,
            "corpus_manifest_hash": "c" * 64,
            "transformation_map_hash": "d" * 64,
            "conditioning_variant": "anonymous-profile",
            "prompt_encoding": "xml",
            "control_density": "medium",
            "story_program_id": "story-program-secret",
            "anti_copy_policy_version": "anti-copy.v1",
            "anti_copy_index_hash": "e" * 64,
            "frontier_adapter": "local-31b",
            "approved_prefix_id": "approved-s01-secret",
            "approved_prefix_hash": "f" * 64,
            "feedback_brief_hash": "1" * 64,
            "generation_mode": "raw_organic",
            "text": "Mara arrived beneath the redwoods.\n\nShe chose to stay.",
        },
        {
            "candidate_id": "verbalized-secret-id",
            "pipeline": "verbalized_sampling",
            "model_role": "generator_26b",
            "ontology_version": "rgo.v1",
            "story_profile_id": "fulcrum-pilot.v1",
            "scene_profile_id": "fulcrum-s01.v1",
            "resolved_profile_hash": "a" * 64,
            "author_profile_id": "jane-austen.control.v1",
            "author_profile_hash": "b" * 64,
            "corpus_manifest_hash": "c" * 64,
            "transformation_map_hash": "d" * 64,
            "conditioning_variant": "named-profile",
            "prompt_encoding": "markdown",
            "control_density": "light",
            "story_program_id": "story-program-secret-2",
            "anti_copy_policy_version": "anti-copy.v1",
            "anti_copy_index_hash": "e" * 64,
            "frontier_adapter": "frontier-secret",
            "approved_prefix_id": "approved-s01-secret",
            "approved_prefix_hash": "f" * 64,
            "feedback_brief_hash": "1" * 64,
            "generation_mode": "hybrid_base_program",
            "text": "The bakery box tilted as Mara crossed the porch.\n\nJonah waited.",
        },
        {
            "candidate_id": "actor-secret-id",
            "pipeline": "actor_novelist",
            "model_role": "editor_31b",
            "ontology_version": "rgo.v1",
            "story_profile_id": "fulcrum-pilot.v1",
            "scene_profile_id": "fulcrum-s01.v1",
            "resolved_profile_hash": "a" * 64,
            "author_profile_id": "jane-austen.control.v1",
            "author_profile_hash": "b" * 64,
            "corpus_manifest_hash": "c" * 64,
            "transformation_map_hash": "d" * 64,
            "conditioning_variant": "profile-sparse-exemplars",
            "prompt_encoding": "json",
            "control_density": "dense",
            "story_program_id": "story-program-secret-3",
            "anti_copy_policy_version": "anti-copy.v1",
            "anti_copy_index_hash": "e" * 64,
            "frontier_adapter": "local-31b",
            "approved_prefix_id": "approved-s01-secret",
            "approved_prefix_hash": "f" * 64,
            "feedback_brief_hash": "1" * 64,
            "generation_mode": "chat_direct",
            "text": "At sunset the compound looked staged for enchantment.\n\nMara changed the signal.",
        },
    ]
    for seed, record in enumerate(records, start=1):
        record["artifact_authorship"] = {
            "record_type": "ArtifactAuthorship",
            "schema_version": "artifact-authorship.v1",
            "artifact_id": record["candidate_id"],
            "creation_kind": "model_generation",
            "creator_id": "fixture-model-runtime",
            "creator_kind": "model_runtime",
            "created_at": "2026-08-03T00:00:00Z",
            "text_sha256": text_sha256(record["text"]),
            "parents": [],
            "model_pipeline_eligible": True,
            "model_call": {
                "model_id": "fixture-model",
                "call_id": f"fixture-call-{seed}",
                "prompt_hash": f"{seed}" * 64,
                "call_record_hash": "9" * 64,
                "seed": seed,
            },
        }
        record["review_attestations"] = []
    return records


def proofed_finalists(root: Path) -> list[dict]:
    records = finalists()
    for seed, record in enumerate(records, start=1):
        record["artifact_authorship"] = evidence_fixture(
            root,
            text=record["text"],
            artifact_id=record["candidate_id"],
            call_id=f"appraisal-call-{seed}",
            seed=seed,
        )
    return records


class AppraisalTests(unittest.TestCase):
    def test_blind_labels_are_reproducible(self) -> None:
        first = blind_label_map(finalists(), "seed")
        second = blind_label_map(finalists(), "seed")
        self.assertEqual(
            {label: value["candidate_id"] for label, value in first.items()},
            {label: value["candidate_id"] for label, value in second.items()},
        )
        self.assertEqual(set(first), {"A", "B", "C"})

    def test_requires_exactly_three_unique_finalists(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly three"):
            blind_label_map(finalists()[:2], "seed")
        duplicate = finalists()
        duplicate[-1]["candidate_id"] = duplicate[0]["candidate_id"]
        with self.assertRaisesRegex(ValueError, "distinct"):
            blind_label_map(duplicate, "seed")

    def test_builds_blind_html_markdown_and_separate_key(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            out_dir = Path(temporary) / "appraisal"
            manifest = build_appraisal(
                proofed_finalists(Path(temporary)), out_dir, "blind-seed"
            )
            html_path = Path(manifest["reader_html"])
            markdown_path = Path(manifest["reader_markdown"])
            reveal_path = Path(manifest["reveal_key"])
            self.assertTrue(html_path.is_file())
            self.assertTrue(markdown_path.is_file())
            self.assertTrue(reveal_path.is_file())
            self.assertEqual(reveal_path.parent.name, "internal")
            self.assertNotEqual(reveal_path.parent, html_path.parent)
            html = html_path.read_text(encoding="utf-8")
            markdown = markdown_path.read_text(encoding="utf-8")
            reveal = json.loads(reveal_path.read_text(encoding="utf-8"))
            self.assertIn("localStorage", html)
            self.assertIn("Export responses", html)
            self.assertIn("Responses exported", html)
            self.assertIn("Clear responses", html)
            self.assertIn("Pairwise choices", markdown)
            self.assertNotIn("direct-secret-id", html + markdown)
            self.assertNotIn("native_best_of_n", html + markdown)
            self.assertNotIn("fulcrum-pilot.v1", html + markdown)
            self.assertNotIn("fulcrum-s01.v1", html + markdown)
            self.assertNotIn("rgo.v1", html + markdown)
            self.assertNotIn("a" * 64, html + markdown)
            self.assertNotIn("jane-austen.control.v1", html + markdown)
            self.assertNotIn("anonymous-profile", html + markdown)
            self.assertNotIn("story-program-secret", html + markdown)
            self.assertNotIn("anti-copy.v1", html + markdown)
            self.assertNotIn("approved-s01-secret", html + markdown)
            self.assertNotIn("raw_organic", html + markdown)
            self.assertIn("Resemblance to the declared craft target", markdown)
            self.assertIn("Suspicion of source copying", markdown)
            self.assertEqual(set(reveal["labels"]), {"A", "B", "C"})
            self.assertTrue(
                all(
                    item["artifact_authorship"]["model_pipeline_eligible"]
                    for item in reveal["labels"].values()
                )
            )
            self.assertTrue(manifest["blind_check"]["passed"])

    def test_appraisal_rejects_missing_authorship(self) -> None:
        records = finalists()
        records[0].pop("artifact_authorship")
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "artifact_authorship"):
                build_appraisal(records, Path(temporary) / "appraisal", "seed")

    def test_appraisal_rejects_manual_edit_as_model_finalist(self) -> None:
        records = finalists()
        record = records[0]
        record["artifact_authorship"] = {
            "record_type": "ArtifactAuthorship",
            "schema_version": "artifact-authorship.v1",
            "artifact_id": record["candidate_id"],
            "creation_kind": "codex_manual_edit",
            "creator_id": "codex-task-fixture",
            "creator_kind": "codex_task",
            "created_at": "2026-08-03T00:00:00Z",
            "text_sha256": text_sha256(record["text"]),
            "parents": [{"artifact_id": "parent", "text_sha256": "8" * 64}],
            "model_pipeline_eligible": False,
        }
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "historical-only"):
                build_appraisal(records, Path(temporary) / "appraisal", "seed")

    def test_blind_verifier_detects_identity_leak(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "reader.md"
            path.write_text("Hidden id: actor-secret-id", encoding="utf-8")
            label_map = blind_label_map(finalists(), "seed")
            result = verify_blind_package([path], label_map)
            self.assertFalse(result["passed"])
            self.assertEqual(result["leaks"][0]["token"], "actor-secret-id")

    def test_blind_verifier_allows_direct_as_ordinary_prose(self) -> None:
        records = finalists()
        records[0]["pipeline"] = "direct"
        label_map = blind_label_map(records, "seed")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "reader.md"
            path.write_text(
                "Mara met his direct gaze and asked a direct question.",
                encoding="utf-8",
            )
            result = verify_blind_package([path], label_map)
            self.assertTrue(result["passed"])

    def test_blind_verifier_still_rejects_namespaced_pipeline_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "reader.md"
            path.write_text("Generated by actor_novelist.", encoding="utf-8")
            label_map = blind_label_map(finalists(), "seed")
            result = verify_blind_package([path], label_map)
            self.assertFalse(result["passed"])
            self.assertEqual(result["leaks"][0]["token"], "actor_novelist")

    def test_internal_report_keeps_unblinded_comparison_separate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = build_internal_report(
                finalists(),
                Path(temporary) / "internal",
                scorecards=[
                    {
                        "candidate_id": "actor-secret-id",
                        "rubric_scores": {"narrative_force": 18},
                        "total_score": 88,
                        "eligible": True,
                        "defects": ["scene_capture"],
                    }
                ],
                diversity_reports={"actor_novelist": {"mean_self_bleu_proxy": 0.2}},
                generation_summary={"sampled_tokens": 12000},
            )
            markdown = Path(paths["markdown"]).read_text(encoding="utf-8")
            payload = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
            self.assertIn("actor-secret-id", markdown)
            self.assertIn("sampled_tokens", markdown)
            self.assertEqual(payload["finalists"][2]["mean_score"], 88)


if __name__ == "__main__":
    unittest.main()
