from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from fiction_harness.core import sha256_text
from fiction_harness.feedback import (
    HumanFeedbackBrief,
    build_pairwise_feedback_packets,
    summarize_feedback,
    validate_feedback_response,
)


def _finalists() -> list[dict[str, str]]:
    return [
        {
            "candidate_id": f"secret-{label}",
            "pipeline": f"pipeline-{label}",
            "text": f"Finalist {label} prose. " * 20,
        }
        for label in ("one", "two", "three")
    ]


def _reveal(finalists: list[dict[str, str]]) -> dict:
    return {
        "package_id": "package-123",
        "labels": {
            label: {
                "candidate_id": item["candidate_id"],
                "pipeline": item["pipeline"],
                "model_role": "writer",
                "text_sha256": sha256_text(item["text"]),
            }
            for label, item in zip(("A", "B", "C"), finalists)
        },
    }


def _response(
    reviewer: str,
    labels: tuple[str, ...],
    winners: dict[str, str],
    *,
    desire: dict[str, int] | None = None,
) -> dict:
    responses: dict[str, str] = {}
    desire = desire or {}
    for label in labels:
        for dimension in (
            "romantic_pull",
            "heat",
            "character_fascination",
            "trust",
            "prose_freshness",
            "desire_to_continue",
            "preachiness",
        ):
            responses[f"{label}_{dimension}"] = str(
                desire.get(label, 5)
                if dimension == "desire_to_continue"
                else 5
            )
        responses[f"{label}_hottest"] = f"strength {label} from {reviewer}"
        responses[f"{label}_false"] = f"defect {label} from {reviewer}"
        responses[f"{label}_next"] = f"next {label} from {reviewer}"
    responses.update(winners)
    return {
        "schema_version": "human-feedback.v1",
        "package_id": "package-123",
        "packet_id": "test",
        "reviewer_code": reviewer,
        "labels": list(labels),
        "saved_at": "2026-01-01T00:00:00Z",
        "responses": responses,
    }


class FeedbackPacketTests(unittest.TestCase):
    def test_builds_three_pairs_and_all_three_without_identity_leaks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            finalists = _finalists()
            reveal_path = root / "reveal.json"
            reveal_path.write_text(json.dumps(_reveal(finalists)))
            manifest = build_pairwise_feedback_packets(
                finalists=finalists,
                reveal_key_path=reveal_path,
                out_dir=root / "feedback",
            )
            self.assertEqual(len(manifest["packets"]), 4)
            self.assertTrue(manifest["blind_check"]["passed"])
            public = "\n".join(
                path.read_text()
                for path in (root / "feedback" / "reader").glob("*")
            )
            self.assertNotIn("secret-one", public)
            self.assertNotIn("pipeline-one", public)
            self.assertIn("Reviewer code", public)

    def test_response_validation_rejects_invalid_rating(self) -> None:
        raw = _response(
            "reader-1",
            ("A", "B"),
            {"pair_A_B": "A"},
        )
        raw["responses"]["A_heat"] = "8"
        with self.assertRaisesRegex(ValueError, "A_heat"):
            validate_feedback_response(raw)


class FeedbackAggregationTests(unittest.TestCase):
    def test_condorcet_winner_and_tiebreak_are_deterministic(self) -> None:
        responses = (
            _response("reader-1", ("A", "B"), {"pair_A_B": "B"}),
            _response("reader-2", ("A", "C"), {"pair_A_C": "A"}),
            _response("reader-3", ("B", "C"), {"pair_B_C": "B"}),
        )
        with tempfile.TemporaryDirectory() as temporary:
            paths = []
            for index, response in enumerate(responses):
                path = Path(temporary) / f"{index}.json"
                path.write_text(json.dumps(response))
                paths.append(path)
            first = summarize_feedback(paths)
            second = summarize_feedback(paths)
            self.assertEqual(first.winner_label, "B")
            self.assertEqual(first.pairwise, second.pairwise)
            self.assertNotEqual(
                first.feedback_brief_hash,
                "",
            )
            restored = HumanFeedbackBrief.from_dict(first.to_dict())
            self.assertEqual(restored.feedback_brief_hash, first.feedback_brief_hash)

    def test_duplicate_reviewer_is_rejected(self) -> None:
        responses = (
            _response("same-reader", ("A", "B"), {"pair_A_B": "A"}),
            _response("same-reader", ("A", "C"), {"pair_A_C": "A"}),
        )
        with tempfile.TemporaryDirectory() as temporary:
            paths = []
            for index, response in enumerate(responses):
                path = Path(temporary) / f"{index}.json"
                path.write_text(json.dumps(response))
                paths.append(path)
            with self.assertRaisesRegex(ValueError, "duplicate reviewer_code"):
                summarize_feedback(paths)

    def test_all_weak_candidates_trigger_fail_fast(self) -> None:
        responses = (
            _response(
                "reader-1",
                ("A", "B", "C"),
                {
                    "pair_A_B": "A",
                    "pair_A_C": "A",
                    "pair_B_C": "B",
                },
                desire={"A": 3, "B": 2, "C": 1},
            ),
        )
        responses[0]["responses"]["A_trust"] = "3"
        responses[0]["responses"]["B_trust"] = "3"
        responses[0]["responses"]["C_trust"] = "3"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "response.json"
            path.write_text(json.dumps(responses[0]))
            brief = summarize_feedback((path,))
            self.assertTrue(brief.fail_fast)


if __name__ == "__main__":
    unittest.main()
