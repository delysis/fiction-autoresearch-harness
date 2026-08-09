from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from fiction_harness.runtime import TraceStore
from fiction_harness.schemas import Candidate
from fiction_harness.workflow import (
    _nearest_exact_evidence,
    _pairwise_payload_with_exact_evidence,
    _pairwise_prefix,
    _repair_evidence_payload,
    load_candidates,
)


class EvidenceProjectionTests(unittest.TestCase):
    def test_projects_exact_normalized_three_word_diagnostic(self) -> None:
        text = "Jonah smiled. ‘A high-resolution boundary,’ he murmured."
        result = _nearest_exact_evidence("a high-resolution boundary", text)
        self.assertEqual(result, ("A high-resolution boundary", 1.0))

    def test_projects_near_quote_to_exact_contiguous_span(self) -> None:
        text = (
            "Livia wasn't reading souls; she was reading the way people "
            "adjusted their breathing when they felt judged."
        )
        result = _nearest_exact_evidence(
            "Livia wasn't reading souls; she was reading the reaction", text
        )
        self.assertIsNotNone(result)
        excerpt, similarity = result or ("", 0)
        self.assertIn(excerpt, text)
        self.assertGreaterEqual(similarity, 0.72)

    def test_repaired_payload_retains_audit_record(self) -> None:
        candidate = (
            "Mara decided to decouple her tactile response from her visual "
            "and postural cues."
        )
        payload = {
            "passage_evidence": {
                "instructional_fidelity": [
                    "She decided to decouple her tactile response from her visual cues"
                ]
            }
        }
        repaired, audit = _repair_evidence_payload(
            json.dumps(payload), candidate
        )
        quote = repaired["passage_evidence"]["instructional_fidelity"][0]
        self.assertIn(quote, candidate)
        self.assertEqual(audit[0]["method"], "nearest_contiguous_source_span")

    def test_repaired_payload_projects_diagnostic_evidence(self) -> None:
        candidate = (
            "Jonah stepped back, and the cost of his restraint made Mara trust him."
        )
        payload = {
            "passage_evidence": {"heat_with_agency": [candidate]},
            "romance_diagnostics": {
                "productive_restraint": {
                    "passed": True,
                    "evidence": "the cost of restraint made Mara trust him",
                }
            },
        }
        repaired, audit = _repair_evidence_payload(json.dumps(payload), candidate)
        quote = repaired["romance_diagnostics"]["productive_restraint"]["evidence"]
        self.assertIn(quote, candidate)
        self.assertEqual(audit[-1]["diagnostic"], "productive_restraint")

    def test_pairwise_evidence_is_projected_per_candidate(self) -> None:
        left = "Mara changed the cue channel and watched the accuracy fall."
        right = "Jonah refused to narrate her for the waiting room."
        payload = {
            "winner": "A",
            "confidence": 0.8,
            "axis_winners": {},
            "evidence": {
                "A": ["She changed the cue channel and watched accuracy fall"],
                "B": ["Jonah refused to narrate her for the room"],
            },
            "defects": {"A": [], "B": []},
            "reason": "A changes what can be known.",
        }
        repaired, audit = _pairwise_payload_with_exact_evidence(
            json.dumps(payload), left, right
        )
        self.assertIn(repaired["evidence"]["A"][0], left)
        self.assertIn(repaired["evidence"]["B"][0], right)
        self.assertEqual(len(audit), 2)

    def test_pairwise_fallback_extracts_from_correct_candidate(self) -> None:
        left = (
            "Mara let the expected signal collapse. The room became quiet while "
            "she watched Livia revise the story."
        )
        right = (
            "Jonah refused the performance and protected Mara's freedom without "
            "asking to be praised for it."
        )
        payload = {
            "winner": "B",
            "confidence": 0.9,
            "axis_winners": {},
            "evidence": {
                "A": ["words that appear in neither candidate"],
                "B": ["words that appear in neither candidate"],
            },
            "defects": {"A": ["passive collapse"], "B": []},
            "reason": "A has a passive collapse; B makes Jonah's refusal causal.",
        }
        repaired, audit = _pairwise_payload_with_exact_evidence(
            json.dumps(payload),
            left,
            right,
            allow_lexical_fallback=True,
        )
        self.assertIn(repaired["evidence"]["A"][0], left)
        self.assertIn(repaired["evidence"]["B"][0], right)
        self.assertEqual(
            {item["method"] for item in audit},
            {"lexical_support_span_fallback"},
        )

    def test_pairwise_prefix_contains_no_story_dossier(self) -> None:
        prefix = _pairwise_prefix(
            {
                "axes": {"narrative_force": {"weight": 20}},
                "pairwise_priorities": ["Prefer causal action."],
            }
        )
        self.assertIn("narrative_force", prefix)
        self.assertIn("Prefer causal action.", prefix)
        self.assertNotIn("Mara", prefix)
        self.assertNotIn("Livia", prefix)
        self.assertNotIn("Jonah", prefix)

    def test_candidate_loader_strips_editor_envelope_fields(self) -> None:
        candidate = Candidate(
            candidate_id="edited-01",
            run_id="run-01",
            pipeline="direct",
            scene_id="S02",
            seed=1,
            text="Complete proof story.",
            parent_trace={},
            evidence_ids=(),
            telemetry={},
            lineage=(),
            prompt_hash="0" * 64,
        )
        with tempfile.TemporaryDirectory() as directory:
            store = TraceStore(Path(directory) / "editor")
            store.append_candidate(
                {
                    **candidate.to_dict(),
                    "status": "completed",
                    "editor_gate_eligible": True,
                    "legacy_gate_carry_forward": {"basis": "test"},
                }
            )
            loaded = load_candidates(directory)
        self.assertEqual([item.candidate_id for item in loaded], ["edited-01"])


if __name__ == "__main__":
    unittest.main()
