from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from fiction_harness.anti_copy import AntiCopyIndex

from fiction_harness.long_context import (
    LongContextArm,
    S03_OPENING_FRAGMENT,
    compile_experiment,
    compile_long_context,
    self_repetition_report,
    run_experiment,
)
from fiction_harness.model_client import Completion
from fiction_harness.shared_endpoint import SharedEndpointAdmission


class LongContextTests(unittest.TestCase):
    def test_prompt_is_deterministic_and_ends_as_manuscript(self) -> None:
        arm = LongContextArm("fixture", 4_000, "distilled", "evidence-first", "full")
        arguments = {
            "manuscript": "Mara watched the redwoods. " * 1800,
            "guide_text": "Craft evidence about dialogue and action.\n\n" * 1800,
            "craft_distillation": "Character before mechanics.\n\n" * 200,
        }
        first = compile_long_context(arm, **arguments)
        second = compile_long_context(arm, **arguments)
        self.assertEqual(first.prompt_hash, second.prompt_hash)
        self.assertTrue(first.prompt.rstrip().endswith(S03_OPENING_FRAGMENT))
        self.assertIn("===== FICTION PREPARATION NOTEBOOK =====", first.prompt)
        self.assertIn("===== END FICTION PREPARATION NOTEBOOK =====", first.prompt)
        self.assertNotIn("<fiction-preparation>", first.prompt)
        self.assertNotIn("</fiction-preparation>", first.prompt)
        self.assertNotIn("<manuscript>", first.prompt)
        self.assertNotIn("</manuscript>", first.prompt)
        self.assertLess(
            first.prompt.index("===== END FICTION PREPARATION NOTEBOOK ====="),
            first.prompt.index("Mara watched the redwoods."),
        )
        self.assertNotIn("<fiction_program", first.prompt)

    def test_context_dose_is_monotonic(self) -> None:
        arguments = {
            "manuscript": "Accepted prose. " * 1800,
            "guide_text": "Long craft archive paragraph.\n\n" * 20_000,
            "craft_distillation": "Distilled craft.\n\n" * 400,
        }
        small = compile_long_context(
            LongContextArm("small", 4_000, "none", "contract-first", "full"),
            **arguments,
        )
        large = compile_long_context(
            LongContextArm("large", 24_000, "distilled", "evidence-first", "full"),
            **arguments,
        )
        self.assertGreater(large.prompt_words, small.prompt_words)
        self.assertGreater(large.component_words["evidence"], 0)

    def test_experiment_records_identical_program_and_manuscript_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manuscript = root / "manuscript.md"
            guide = root / "guide.md"
            craft = root / "craft.md"
            manuscript.write_text("Mara continued. " * 2000, encoding="utf-8")
            guide.write_text("Evidence.\n\n" * 20_000, encoding="utf-8")
            craft.write_text("Craft.\n\n" * 1000, encoding="utf-8")
            payload = compile_experiment(
                run_root=root / "run",
                manuscript_path=manuscript,
                guide_path=guide,
                craft_distillation_path=craft,
                arms=(
                    LongContextArm("a", 4_000, "none", "contract-first", "full"),
                    LongContextArm("b", 8_000, "distilled", "evidence-first", "organic"),
                ),
            )
            self.assertEqual(len(payload["arms"]), 2)
            self.assertEqual(
                {item["program_hash"] for item in payload["arms"]},
                {payload["story_program_hash"]},
            )
            self.assertEqual(
                {item["manuscript_hash"] for item in payload["arms"]},
                {payload["manuscript_hash"]},
            )

    def test_arm_identity_is_part_of_prompt_hash(self) -> None:
        common = {
            "manuscript": "Accepted prose. " * 2200,
            "guide_text": "Evidence.\n\n" * 10_000,
            "craft_distillation": "Craft.\n\n" * 100,
        }
        early = compile_long_context(
            LongContextArm("early", 8_000, "distilled", "evidence-first", "full"),
            **common,
        )
        late = compile_long_context(
            LongContextArm("late", 8_000, "distilled", "contract-first", "full"),
            **common,
        )
        self.assertNotEqual(early.prompt_hash, late.prompt_hash)

    def test_self_repetition_rejects_long_loop_but_not_short_motif(self) -> None:
        long_block = " ".join(f"word{index}" for index in range(70))
        looped = f"Opening paragraph.\n\n{long_block}\n\nBridge.\n\n{long_block}"
        self.assertTrue(self_repetition_report(looped)["hard_fail"])
        motif = "The clock ticked.\n\n" * 12 + "A wholly new scene followed."
        self.assertFalse(self_repetition_report(motif)["hard_fail"])

    def test_run_acquires_and_releases_shared_endpoint_lease(self) -> None:
        class FakeClient:
            model = "gemma-4-31b-base"

            def __init__(self) -> None:
                self.tokenized = 0
                self.generated = 0

            def token_count(self, text: str) -> int:
                self.tokenized += 1
                return 400

            def stream_raw(self, **_: object) -> Completion:
                self.generated += 1
                prose = " ".join(f"distinctword{index}" for index in range(700)) + "."
                return Completion(
                    content=prose,
                    model=self.model,
                    finish_reason="stop",
                    usage={"prompt_tokens": 400, "completion_tokens": 700},
                    timings={"prompt_n": 400, "predicted_n": 700},
                    cache={"prompt_n": 400},
                    elapsed_seconds=1.0,
                    raw={},
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manuscript = root / "manuscript.md"
            guide = root / "guide.md"
            craft = root / "craft.md"
            manuscript.write_text("Approved scene. " * 2000, encoding="utf-8")
            guide.write_text("Guide evidence.\n\n" * 5000, encoding="utf-8")
            craft.write_text("Craft evidence.\n\n" * 100, encoding="utf-8")
            run_root = root / "run"
            compile_experiment(
                run_root=run_root,
                manuscript_path=manuscript,
                guide_path=guide,
                craft_distillation_path=craft,
                arms=(LongContextArm("fixture", 4_000, "none", "contract-first", "full"),),
            )
            state = root / "admission.json"
            admission = SharedEndpointAdmission(
                state, parallel_slots=1, context_budget_tokens=2_000
            )
            client = FakeClient()
            records = run_experiment(
                client=client,  # type: ignore[arg-type]
                run_root=run_root,
                seeds=(17,),
                anti_copy_index=AntiCopyIndex({"source": "unrelated source text"}),
                max_tokens=800,
                max_retries=0,
                admission=admission,
            )
            self.assertEqual(len(records), 1)
            self.assertEqual(client.tokenized, 1)
            self.assertEqual(client.generated, 1)
            self.assertEqual(__import__("json").loads(state.read_text())["leases"], [])


if __name__ == "__main__":
    unittest.main()
