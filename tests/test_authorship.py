from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from fiction_harness.authorship import (
    canonical_record_hash,
    proof_carrying_model_authorship,
    text_sha256,
    validate_artifact_authorship,
    validate_review_attestations,
)


TEXT = "Mara kept her hand on the warm cup."


def evidence_fixture(
    root: Path,
    *,
    text: str = TEXT,
    artifact_id: str = "candidate-1",
    call_id: str = "call-1",
    seed: int = 17,
) -> dict:
    prompt = "Write one sentence."
    prompt_path = root / f"{call_id}.prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    call = {
        "call_id": call_id,
        "status": "completed",
        "model": "gemma-fixture",
        "runtime": {
            "model_alias": "gemma-fixture",
            "model_blob": "/fixture/model.gguf",
            "model_size_bytes": 123,
            "model_blob_sha256": "c" * 64,
            "model_blob_sample_sha256": "a" * 64,
            "llama_server": "/fixture/llama-server",
            "llama_server_sha256": "b" * 64,
            "llama_version": "fixture-v1",
        },
        "prompt_hash": text_sha256(prompt),
        "prompt_path": str(prompt_path),
        "transport": "raw_completion",
        "parameters": {
            "seed": seed,
            "max_tokens": 32,
            "temperature": 0.9,
            "top_p": 0.95,
            "min_p": 0.02,
        },
        "result": {"content": text},
    }
    calls = root / f"{call_id}.calls.jsonl"
    calls.write_text(json.dumps(call, sort_keys=True) + "\n", encoding="utf-8")
    record = proof_carrying_model_authorship(
        artifact_id=artifact_id,
        text=text,
        model_id="gemma-fixture",
        call_id=call_id,
        prompt_hash=text_sha256(prompt),
        seed=seed,
        call_ledger_path=calls,
        derivation={"operation": "identity"},
        created_at="2026-08-03T00:00:00Z",
    )
    body = {
        "record_type": "ModelReplayWitness",
        "schema_version": "model-replay-witness.v1",
        "call_id": call_id,
        "original_call_record_hash": canonical_record_hash(call),
        "prompt_hash": text_sha256(prompt),
        "model_id": "gemma-fixture",
        "seed": seed,
        "raw_response_sha256": text_sha256(text),
        "expected_raw_response_sha256": text_sha256(text),
        "matches_original": True,
        "runtime": call["runtime"],
        "replayed_at": "2026-08-03T01:00:00Z",
    }
    witness = {**body, "witness_hash": canonical_record_hash(body)}
    replay_path = calls.with_name("replays.jsonl")
    with replay_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(witness, sort_keys=True) + "\n")
    return record


class AuthorshipTests(unittest.TestCase):
    def test_proof_carrying_generation_is_pipeline_eligible(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            record = evidence_fixture(Path(temporary))
            result = validate_artifact_authorship(
                record,
                text=TEXT,
                artifact_id="candidate-1",
                require_model_pipeline=True,
            )
            self.assertTrue(result["model_pipeline_eligible"])
            self.assertIn("verified_replay", result)

    def test_legacy_self_attestation_is_historical_only(self) -> None:
        record = {
            "record_type": "ArtifactAuthorship",
            "schema_version": "artifact-authorship.v1",
            "artifact_id": "candidate-1",
            "creation_kind": "model_generation",
            "creator_id": "runtime-1",
            "creator_kind": "model_runtime",
            "created_at": "2026-08-03T00:00:00Z",
            "text_sha256": text_sha256(TEXT),
            "parents": [],
            "model_pipeline_eligible": True,
            "model_call": {
                "model_id": "gemma-fixture",
                "call_id": "call-1",
                "prompt_hash": "1" * 64,
                "call_record_hash": "2" * 64,
                "seed": 17,
            },
        }
        validate_artifact_authorship(record, text=TEXT)
        with self.assertRaisesRegex(ValueError, "historical-only"):
            validate_artifact_authorship(
                record, text=TEXT, require_model_pipeline=True
            )

    def test_candidate_must_derive_from_raw_call(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            record = evidence_fixture(Path(temporary))
            forged = TEXT + " Fraud."
            record["text_sha256"] = text_sha256(forged)
            with self.assertRaisesRegex(ValueError, "reconstructed"):
                validate_artifact_authorship(record, text=forged)

    def test_missing_replay_fails_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            record = evidence_fixture(root)
            (root / "replays.jsonl").unlink()
            validate_artifact_authorship(
                record, text=TEXT, require_model_pipeline=True, require_replay=False
            )
            with self.assertRaisesRegex(ValueError, "replay witness"):
                validate_artifact_authorship(
                    record, text=TEXT, require_model_pipeline=True
                )

    def test_forged_call_hash_does_not_resolve(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            record = evidence_fixture(Path(temporary))
            record["model_call"]["call_record_hash"] = "f" * 64
            with self.assertRaisesRegex(ValueError, "resolve uniquely"):
                validate_artifact_authorship(record, text=TEXT)

    def test_manual_codex_edit_is_control_only(self) -> None:
        record = {
            "record_type": "ArtifactAuthorship",
            "schema_version": "artifact-authorship.v1",
            "artifact_id": "candidate-1",
            "creation_kind": "codex_manual_edit",
            "creator_id": "task-1",
            "creator_kind": "codex_task",
            "created_at": "2026-08-03T00:00:00Z",
            "text_sha256": text_sha256(TEXT),
            "parents": [{"artifact_id": "base", "text_sha256": "3" * 64}],
            "model_pipeline_eligible": False,
        }
        validate_artifact_authorship(record, text=TEXT)
        with self.assertRaisesRegex(ValueError, "historical-only"):
            validate_artifact_authorship(
                record, text=TEXT, require_model_pipeline=True
            )

    def test_review_independence_requires_blind_distinct_reviewer(self) -> None:
        result = validate_review_attestations(
            [
                {
                    "reviewer_id": "task-2",
                    "exposure": "blind_manuscript",
                    "review_hash": "4" * 64,
                    "independent": True,
                }
            ],
            creator_id="task-1",
            minimum_independent=1,
        )
        self.assertEqual(result["independent_blind_review_count"], 1)
        with self.assertRaisesRegex(ValueError, "conflicts"):
            validate_review_attestations(
                [
                    {
                        "reviewer_id": "task-1",
                        "exposure": "blind_manuscript",
                        "review_hash": "4" * 64,
                        "independent": True,
                    }
                ],
                creator_id="task-1",
            )


if __name__ == "__main__":
    unittest.main()
