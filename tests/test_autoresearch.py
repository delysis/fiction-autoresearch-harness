from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest

from fiction_harness.autoresearch import (
    DEFAULT_SOURCE,
    PromptRecipe,
    _candidate_gate,
    _claim_prompt_view,
    _write_next_round_recipes,
    _graph_for,
    build_recipe_blocks,
    compile_benchmarks,
    compile_corpus,
    default_benchmarks,
    extract_gabaldon_examples,
    extract_manuscript,
    extract_prompt_eligible_craft,
    render_prompt,
    round1_recipes,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRIDGES = PROJECT_ROOT / "fixtures" / "autoresearch" / "bridges"


class CorpusTests(unittest.TestCase):
    def test_recovers_numbered_examples_and_book_partitions(self) -> None:
        passages = extract_gabaldon_examples(DEFAULT_SOURCE)
        self.assertEqual([item.example_number for item in passages], list(range(1, 14)))
        by_number = {item.example_number: item for item in passages}
        self.assertEqual(by_number[2].source_work, "The Scottish Prisoner")
        self.assertEqual(by_number[3].source_work, "Voyager")
        self.assertEqual(by_number[8].partition, "calibration")
        self.assertEqual(by_number[13].partition, "holdout")
        self.assertFalse(by_number[10].prompt_eligible)

    def test_public_manifest_contains_no_source_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            public = compile_corpus(DEFAULT_SOURCE, directory)
            self.assertTrue(public["passages"])
            self.assertTrue(all("text" not in item for item in public["passages"]))
            private = json.loads(
                (Path(directory) / "corpus.private.v1.json").read_text()
            )
            self.assertTrue(all("text" in item for item in private["passages"]))

    def test_long_craft_context_excludes_reserved_works(self) -> None:
        craft = extract_prompt_eligible_craft(DEFAULT_SOURCE)
        self.assertGreater(len(craft.split()), 12_000)
        self.assertNotIn("A Breath of Snow and Ashes", craft)
        self.assertNotIn("Drums of Autumn", craft)

    def test_backtranslations_are_scene_specific(self) -> None:
        passages = extract_gabaldon_examples(DEFAULT_SOURCE)
        graphs = [_graph_for(item) for item in passages]
        self.assertEqual(len({item.emotional_offer for item in graphs}), 13)
        self.assertIn("months of separation", graphs[0].emotional_offer)
        self.assertIn("coercive", graphs[5].intimacy_mode)


class PromptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.passages = extract_gabaldon_examples(DEFAULT_SOURCE)
        self.graphs = {item.passage_id: _graph_for(item) for item in self.passages}
        self.cell = default_benchmarks()[2]

    def _blocks(self, recipe: PromptRecipe):
        return build_recipe_blocks(
            recipe=recipe,
            cell=self.cell,
            passages=self.passages,
            graphs=self.graphs,
            project_root=PROJECT_ROOT,
            bridge_dir=BRIDGES,
        )

    def test_holdout_and_calibration_never_enter_generation_blocks(self) -> None:
        recipe = next(item for item in round1_recipes() if item.topology == "curated-long")
        blocks = self._blocks(recipe)
        used = {source for block in blocks for source in block.source_ids}
        forbidden = {
            item.passage_id
            for item in self.passages
            if item.partition in {"holdout", "calibration"}
        }
        self.assertFalse(used & forbidden)

    def test_all_encodings_end_on_plain_manuscript_runway(self) -> None:
        recipe = next(item for item in round1_recipes() if item.topology == "paired")
        blocks = self._blocks(recipe)
        for encoding in ("headings", "xml", "labeled-prose"):
            prompt = render_prompt(blocks, encoding)
            self.assertTrue(prompt.endswith(self.cell.opening_fragment))
            self.assertFalse(prompt.endswith("</fiction_program>"))

    def test_named_recipe_is_a_single_declared_topology_change(self) -> None:
        recipes = {item.topology: item for item in round1_recipes()}
        anonymous = recipes["paired"]
        named = recipes["paired-named"]
        self.assertFalse(anonymous.named_author)
        self.assertTrue(named.named_author)
        self.assertEqual(anonymous.encoding, named.encoding)
        self.assertEqual(anonymous.token_target, named.token_target)

    def test_benchmark_heat_pair_shares_opening_and_causal_program(self) -> None:
        cells = {item.cell_id: item for item in default_benchmarks()}
        open_door = cells["married-open-door"]
        explicit = cells["married-explicit"]
        self.assertEqual(open_door.opening_fragment, explicit.opening_fragment)
        self.assertEqual(open_door.story_program[:3], explicit.story_program[:3])
        self.assertNotEqual(open_door.heat_band, explicit.heat_band)

    def test_curated_long_prompt_is_materially_longer_than_paired(self) -> None:
        craft = extract_prompt_eligible_craft(DEFAULT_SOURCE)
        recipes = {item.topology: item for item in round1_recipes()}
        paired = render_prompt(self._blocks(recipes["paired"]), "headings")
        long_blocks = build_recipe_blocks(
            recipe=recipes["curated-long"],
            cell=self.cell,
            passages=self.passages,
            graphs=self.graphs,
            project_root=PROJECT_ROOT,
            bridge_dir=BRIDGES,
            craft_text=craft,
        )
        long_prompt = render_prompt(long_blocks, "headings")
        self.assertGreater(len(long_prompt.split()), len(paired.split()) * 5)

    def test_unverified_project_bridge_is_rejected(self) -> None:
        recipe = PromptRecipe(
            "bridge-fixture",
            1,
            "paired",
            "headings",
            16000,
            False,
            True,
            (),
            control_density="fixture",
        )
        with self.assertRaisesRegex(ValueError, "clean-room"):
            self._blocks(recipe)

    def test_control_suffix_is_preserved_but_not_scored_as_manuscript(self) -> None:
        manuscript, report = extract_manuscript(
            "A complete final paragraph.\n\nANALYSIS\n{\"score\": 9}"
        )
        self.assertEqual(manuscript, "A complete final paragraph.")
        self.assertTrue(report["suffix_removed"])
        self.assertEqual(report["stop_marker"], "ANALYSIS")

    def test_base_invented_end_label_is_not_manuscript(self) -> None:
        manuscript, report = extract_manuscript(
            "A complete final paragraph.\n\nEND TARGET\nIgnored material"
        )
        self.assertEqual(manuscript, "A complete final paragraph.")
        self.assertTrue(report["suffix_removed"])
        self.assertEqual(report["stop_marker"], "END TARGET")

    def test_heat_diagnostics_separate_charge_anatomy_and_action(self) -> None:
        cell = default_benchmarks()[2]
        prose = (
            "They were married adults. She kissed him, took off her bra, and "
            "pressed her bare breast to his chest. She asked, ‘Still yes?’ "
            "He said yes. They chose each other and trusted tomorrow. "
        ) * 90
        result = _candidate_gate(
            cell,
            prose,
            {"hard_fail": False, "unresolved_flags": False},
            "stop",
        )
        diagnostics = result["diagnostics"]
        self.assertGreater(diagnostics["erotic_charge_signal"], 0)
        self.assertGreater(diagnostics["anatomical_specificity_signal"], 0)
        self.assertEqual(diagnostics["completed_intimacy_action_signal"], 0)

    def test_repetition_loop_is_a_hard_gate(self) -> None:
        cell = default_benchmarks()[0]
        prose = "A complete opening. " + ("You're still the same. " * 220)
        result = _candidate_gate(
            cell,
            prose,
            {"hard_fail": False, "unresolved_flags": False},
            "stop",
        )
        self.assertFalse(result["gates"]["no_repetition_loop"])
        self.assertGreaterEqual(
            result["diagnostics"]["max_fourgram_repetitions"], 5
        )

    def test_consent_vocabulary_cannot_mask_coercive_action(self) -> None:
        cell = default_benchmarks()[0]
        prose = (
            "He pinned her in place and said she was not going home. "
            "She pushed away and he asked whether she wanted him to stop. "
            "‘I don't know,’ she said. He kissed her again. "
            "He told himself he was waiting for consent. "
        )
        result = _candidate_gate(
            cell,
            prose,
            {"hard_fail": False, "unresolved_flags": False},
            "stop",
        )
        self.assertFalse(result["gates"]["consent_invariant"])
        self.assertFalse(result["gates"]["endpoint_realized"])
        self.assertGreater(result["diagnostics"]["consent_language_signal"], 0)
        self.assertGreater(result["diagnostics"]["coercive_action_signal"], 0)
        self.assertGreater(
            result["diagnostics"]["uncertainty_escalation_signal"], 0
        )

    def test_prompt_claim_detects_cross_process_equivalent_recipe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertIsNone(
                _claim_prompt_view(
                    root,
                    prompt_hash="abc",
                    recipe_id="r3.24k",
                    cell_id="charged-restraint",
                )
            )
            self.assertIsNone(
                _claim_prompt_view(
                    root,
                    prompt_hash="abc",
                    recipe_id="r3.24k",
                    cell_id="charged-restraint",
                )
            )
            self.assertEqual(
                _claim_prompt_view(
                    root,
                    prompt_hash="abc",
                    recipe_id="r3.48k",
                    cell_id="charged-restraint",
                ),
                "r3.24k",
            )


class CampaignMutationTests(unittest.TestCase):
    def test_round_two_changes_only_encoding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recipes = round1_recipes()
            (root / "campaign_manifest.v1.json").write_text(
                json.dumps(
                    {
                        "recipes": [
                            asdict(item) | {"recipe_hash": item.recipe_hash}
                            for item in recipes
                        ]
                    }
                )
            )
            promoted = ["r1-paired-named", "r1-paired"]
            path = _write_next_round_recipes(root, 1, promoted)
            payload = json.loads(Path(path or "").read_text())
            self.assertEqual(len(payload["recipes"]), 6)
            self.assertEqual(
                {item["mutated_axis"] for item in payload["recipes"]},
                {"encoding"},
            )
            self.assertEqual(
                {item["encoding"] for item in payload["recipes"]},
                {"headings", "xml", "labeled-prose"},
            )


if __name__ == "__main__":
    unittest.main()
