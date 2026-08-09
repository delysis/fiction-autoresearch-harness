from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path
import json
import tempfile
import unittest

from fiction_harness.autoloom import (
    MODE_FIELDS,
    PROGRAM_FIELDS,
    LoomProgram,
    TransactionProgram,
    init_campaign,
    import_locked_program_set,
    loom_recipes,
    parse_mode_engines,
    parse_program_proposals,
    parse_transaction_programs,
    program_compatible,
    render_draft_prompt,
    render_program_prompt,
    render_stage_prompt,
    select_programs,
    SCENE_SENTINEL,
    calibration_gate,
    _complete_stage_prefix,
    _seeded_diverse_stage_selection,
    _stage_diagnostics,
    _terminal_call_ids,
    target_runway,
)
from fiction_harness.autoresearch import (
    DEFAULT_SOURCE,
    _graph_for,
    default_benchmarks,
    extract_gabaldon_examples,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRIDGES = PROJECT_ROOT / "fixtures" / "autoresearch" / "bridges"


def _program(index: int, cell_id: str = "charged-restraint") -> LoomProgram:
    motifs = (
        "copper orchard", "salt telescope", "violet engine", "paper cathedral",
        "winter radio", "glass beehive", "linen compass", "cedar clock",
        "ink lantern", "stone violin", "silver ladder", "moss archive",
    )
    motif = motifs[index % len(motifs)]
    return LoomProgram(
        program_id=f"p{index}",
        cell_id=cell_id,
        pressure_engine=f"The {motif} creates an irreversible deadline",
        offer=f"An unrepeatable bargain involving {motif}",
        counteroffer=f"A refusal transposes {motif} into evidence",
        embodied_engine=f"The body registers {motif} through a specific action",
        mode_engine="They ask, choose, undress, and proceed into consensual sexual union",
        reversal=f"The apparent repair exposes {motif}",
        image_system=motif,
        ending_motion=f"They leave {motif} deliberately unfinished",
        raw_proposal_hash=f"h{index}",
        proposal_seed=100 + index,
    )


class ProgramTests(unittest.TestCase):
    def test_program_prompt_ends_where_base_should_continue(self) -> None:
        prompt = render_program_prompt(default_benchmarks()[0])
        self.assertTrue(prompt.endswith("PROPOSAL 1\n"))
        self.assertIn("STORY LOOM ARCHIVE", prompt)
        self.assertIn("microdot", prompt)

    def test_light_parser_recovers_multiple_programs(self) -> None:
        chunks = []
        for number in range(1, 5):
            chunks.append(
                f"PROPOSAL {number}\n"
                + "\n".join(f"{field}: distinct {field.lower()} {number}" for field in PROGRAM_FIELDS)
                + "\nEND PROPOSAL"
            )
        parsed = parse_program_proposals(
            "\n\n".join(chunks), default_benchmarks()[0], 123
        )
        self.assertEqual(len(parsed), 4)
        self.assertEqual(parsed[2].proposal_seed, 123)

    def test_parser_recovers_prompt_prefilled_first_proposal(self) -> None:
        first = "\n".join(
            f"{field}: distinct {field.lower()} first" for field in PROGRAM_FIELDS
        ) + "\nEND PROPOSAL"
        second = (
            "PROPOSAL 2\n"
            + "\n".join(
                f"{field}: distinct {field.lower()} second" for field in PROGRAM_FIELDS
            )
            + "\nEND PROPOSAL"
        )
        parsed = parse_program_proposals(
            first + "\n\n" + second, default_benchmarks()[0], 123
        )
        self.assertEqual([item.program_id.rsplit(".", 1)[-1] for item in parsed], ["1", "2"])

    def test_selection_has_seeded_entropy_and_is_reproducible(self) -> None:
        programs = tuple(_program(index) for index in range(12))
        first = select_programs(programs, count=4, seed=77)
        replay = select_programs(programs, count=4, seed=77)
        other = select_programs(programs, count=4, seed=78)
        self.assertEqual([item.program_id for item in first], [item.program_id for item in replay])
        self.assertNotEqual([item.program_id for item in first], [item.program_id for item in other])

    def test_nonsexual_program_rejects_erotic_leakage(self) -> None:
        control = default_benchmarks()[3]
        program = _program(1, control.cell_id)
        leaking = replace(program, embodied_engine="They kiss with erotic heat")
        self.assertFalse(program_compatible(leaking, control))

    def test_explicit_program_must_retain_target_anchors(self) -> None:
        cell = default_benchmarks()[2]
        unanchored = _program(1, cell.cell_id)
        self.assertFalse(program_compatible(unanchored, cell))
        anchored = replace(
            unanchored,
            pressure_engine="Esther asks Simon why the recovered drive seal is broken",
        )
        self.assertTrue(program_compatible(anchored, cell))

    def test_mode_parser_accepts_reordered_fields(self) -> None:
        cell = default_benchmarks()[2]
        order = (
            "PLOT COUPLING", "ATTENTION OFFER", "PHYSICAL SEQUENCE",
            "IMAGE ANCHOR", "CONSENT SEQUENCE", "AFTERMATH",
        )
        raw = "ENGINE 1\n" + "\n".join(
            f"{field}: concrete {field.casefold()} value" for field in order
        ) + "\nEND ENGINE 1"
        parsed = parse_mode_engines(raw, cell, 991)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].plot_coupling, "concrete plot coupling value")
        for field in MODE_FIELDS:
            self.assertNotIn(field + ":", parsed[0].plot_coupling)

    def test_mode_parser_recovers_prefilled_first_engine(self) -> None:
        cell = default_benchmarks()[2]
        raw = "\n".join(
            f"{field}: first {field.casefold()}" for field in reversed(MODE_FIELDS)
        ) + "\nEND ENGINE"
        parsed = parse_mode_engines(raw, cell, 992)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].attention_offer, "first attention offer")


class DraftPromptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.passages = extract_gabaldon_examples(DEFAULT_SOURCE)
        cls.graphs = {item.passage_id: _graph_for(item) for item in cls.passages}

    def test_prompt_teaches_end_marker_and_ends_on_prose(self) -> None:
        cell = default_benchmarks()[2]
        recipe = next(item for item in loom_recipes() if item.recipe_id == "loom-paired-doc")
        prompt, source_ids = render_draft_prompt(
            recipe=recipe,
            cell=cell,
            program=_program(1, cell.cell_id),
            passages=self.passages,
            graphs=self.graphs,
            bridge_dir=BRIDGES,
        )
        self.assertGreaterEqual(prompt.count(SCENE_SENTINEL), 2)
        self.assertTrue(prompt.endswith(cell.opening_fragment))
        self.assertTrue(source_ids)

    def test_control_uses_nonsexual_bridge(self) -> None:
        cell = default_benchmarks()[3]
        recipe = loom_recipes()[0]
        prompt, source_ids = render_draft_prompt(
            recipe=recipe,
            cell=cell,
            program=_program(1, cell.cell_id),
            passages=self.passages,
            graphs=self.graphs,
            bridge_dir=BRIDGES,
        )
        self.assertIn("bridge.institutional-pressure", source_ids)
        self.assertIn("white, the card for insufficient evidence", prompt)

    def test_full_apprenticeship_ends_on_activated_prose_runway(self) -> None:
        cell = default_benchmarks()[2]
        recipe = next(
            item for item in loom_recipes()
            if item.recipe_id == "loom-activated-doc"
        )
        program = replace(
            _program(1, cell.cell_id),
            pressure_engine="Esther asks Simon why the recovered drive seal is broken",
        )
        prompt, source_ids = render_draft_prompt(
            recipe=recipe, cell=cell, program=program,
            passages=self.passages, graphs=self.graphs, bridge_dir=BRIDGES,
        )
        self.assertTrue(prompt.endswith("put those same fingers against his mouth."))
        self.assertLess(prompt.rfind("TARGET-NEAR MODE ACTIVATION"), prompt.rfind("MANUSCRIPT\n"))
        self.assertIn("gabaldon.example-02", source_ids)
        self.assertNotIn("gabaldon.example-04", source_ids)

    def test_naturalistic_runway_is_compact_and_in_scene(self) -> None:
        cell = default_benchmarks()[2]
        recipe = next(item for item in loom_recipes() if item.recipe_id == "loom-runway-doc")
        program = replace(
            _program(1, cell.cell_id),
            pressure_engine="Esther asks Simon why the recovered drive seal is broken",
        )
        prompt, _ = render_draft_prompt(
            recipe=recipe, cell=cell, program=program,
            passages=self.passages, graphs=self.graphs, bridge_dir=BRIDGES,
        )
        self.assertTrue(prompt.endswith('"Who did you leave inside?"'))
        self.assertNotIn("TARGET-NEAR MODE ACTIVATION", prompt)
        self.assertIn("MANUSCRIPT APPRENTICESHIP ARCHIVE", prompt)

    def test_stored_runway_equals_prompt_runway(self) -> None:
        cell = default_benchmarks()[2]
        recipe = next(item for item in loom_recipes() if item.recipe_id == "loom-runway-doc")
        prompt, _ = render_draft_prompt(
            recipe=recipe, cell=cell,
            program=replace(
                _program(1, cell.cell_id),
                pressure_engine="Esther asks Simon why the recovered drive seal is broken",
            ),
            passages=self.passages, graphs=self.graphs, bridge_dir=BRIDGES,
        )
        self.assertTrue(prompt.endswith(target_runway(recipe, cell)))

    def test_source_nearest_recipe_places_author_prose_after_bridge(self) -> None:
        cell = default_benchmarks()[2]
        recipe = next(item for item in loom_recipes() if item.recipe_id == "loom-source-nearest-doc")
        prompt, source_ids = render_draft_prompt(
            recipe=recipe, cell=cell, program=_program(1, cell.cell_id),
            passages=self.passages, graphs=self.graphs, bridge_dir=BRIDGES,
        )
        self.assertGreater(prompt.rfind("anonymous-mode-apprenticeship"), prompt.rfind("project-married-explicit"))
        self.assertTrue(prompt.endswith(target_runway(recipe, cell)))
        self.assertIn("gabaldon.example-03", source_ids)

    def test_retrieved_archive_precedes_target_near_material_and_live_runway(self) -> None:
        cell = default_benchmarks()[2]
        recipe = next(item for item in loom_recipes() if item.recipe_id == "loom-source-nearest-doc")
        archive = "RETRIEVED LITERARY APPRENTICESHIP\nA complete old scene."
        prompt, _ = render_stage_prompt(
            stage="transaction", recipe=recipe, cell=cell,
            program=_program(1, cell.cell_id), passages=self.passages,
            graphs=self.graphs, bridge_dir=BRIDGES,
            transaction=TransactionProgram(
                transaction_id="tx.test", parent_id="approach.test",
                offer="She asks for a concrete answer",
                counteroffer="He gives her the pace",
                consent_turn="She says wait and he waits",
                body_logic="Her hand guides his hand",
                sensory_asymmetry="Her skin warms while his voice stays level",
                disclosure="She names the hidden witness",
                plot_payment="The drive changes tomorrow's plan",
                ending_state="They choose one witnessed action",
                raw_proposal_hash="raw-test", proposal_seed=777,
            ),
            apprenticeship_archive=archive,
        )
        self.assertTrue(prompt.startswith(archive))
        self.assertLess(prompt.find(archive), prompt.rfind("anonymous-mode-apprenticeship"))
        self.assertTrue(prompt.endswith(target_runway(recipe, cell)))

    def test_campaign_requires_apprenticeship_pair(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "supplied together"):
                init_campaign(
                    campaign_dir=Path(directory) / "campaign",
                    corpus_source=DEFAULT_SOURCE, bridge_dir=BRIDGES,
                    apprenticeship_index=Path(directory) / "index.json",
                )

    def test_stage_gate_rejects_paratext_leakage(self) -> None:
        report = _stage_diagnostics(
            "transaction",
            "Esther touched Simon.\n\nWRITERS' ROOM NOTES:\n1. revision notes",
            "drive seal Esther Simon " + "touch kiss hand evidence choose " * 20,
        )
        self.assertTrue(report["packet_leakage"])
        self.assertFalse(report["eligible"])


class StagedLoomTests(unittest.TestCase):
    def test_program_import_rehashes_lineage_without_changing_programs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            campaign_dir = root / "campaign"
            source = root / "programs.json"
            program = _program(3, "married-explicit")
            source.write_text(json.dumps({
                "record_type": "AutoloomLockedProgramSet",
                "campaign_hash": "prior-campaign",
                "programs": {
                    "married-explicit": [
                        asdict(program) | {"program_hash": program.program_hash}
                    ]
                },
            }), encoding="utf-8")
            init_campaign(
                campaign_dir=campaign_dir, corpus_source=DEFAULT_SOURCE,
                bridge_dir=BRIDGES,
            )
            result = import_locked_program_set(
                campaign_dir=campaign_dir, source_program_set=source,
            )
            imported = json.loads((
                campaign_dir / "programs" / "locked_program_set.v1.json"
            ).read_text(encoding="utf-8"))
            self.assertEqual(result["cells"], {"married-explicit": 1})
            self.assertEqual(imported["source_campaign_hash"], "prior-campaign")
            self.assertEqual(
                imported["programs"]["married-explicit"][0]["program_hash"],
                program.program_hash,
            )

    def test_transaction_parser_requires_causal_and_consent_fields(self) -> None:
        fields = {
            "OFFER": "Esther turns his confession into a specific invitation",
            "COUNTEROFFER": "Simon asks her to set the pace and terms",
            "CONSENT TURN": "She asks him to wait; he agrees and confirms",
            "BODY LOGIC": "Her hand guides his mouth before they turn toward the bed",
            "SENSORY ASYMMETRY": "His voice stays controlled while her skin warms visibly",
            "DISCLOSURE": "She names the witness she concealed during the rescue",
            "PLOT PAYMENT": "The drive evidence changes their plan for tomorrow's meeting",
            "ENDING STATE": "They remain divided but choose one jointly witnessed action",
        }
        raw = "CARD 1\n" + "\n".join(f"{key}: {value}" for key, value in fields.items()) + "\nEND CARD 1"
        parsed = parse_transaction_programs(raw, parent_id="approach.1", seed=77)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].proposal_seed, 77)

    def test_transaction_parser_accepts_base_model_surface_variants(self) -> None:
        raw = """CARD 1
OFFER: Simon places the drive on the bed before touching Esther.
COUNTEROFFER: Esther redirects his hand and asks for the missing name.
CONSENT TURN: request -> explicit consent -> revocable continuation
BODY LOGIC: Her hand guides his mouth before they turn toward the bed.
SENSORY ASYMMETRIZATION: cold glass contradicts the heat of her skin.
DISCLOSURE: She names the witness whose survival changed her choice.
PLOT PAYMENT: The drive evidence changes their plan for tomorrow's meeting.
ENDING STATE: They remain divided but choose one jointly witnessed action.
CARD 1 COMPLETE"""
        parsed = parse_transaction_programs(raw, parent_id="approach.2", seed=78)
        self.assertEqual(len(parsed), 1)
        self.assertIn("cold glass", parsed[0].sensory_asymmetry)

    def test_transaction_stage_prompt_ends_on_exact_accumulated_prose(self) -> None:
        passages = extract_gabaldon_examples(DEFAULT_SOURCE)
        graphs = {item.passage_id: _graph_for(item) for item in passages}
        cell = default_benchmarks()[2]
        recipe = next(item for item in loom_recipes() if item.recipe_id == "loom-runway-doc")
        transaction = TransactionProgram(
            transaction_id="t1", parent_id="a1",
            offer="Esther converts accusation into a concrete intimate offer",
            counteroffer="Simon asks her to choose pace and evidence",
            consent_turn="She asks him to wait; he agrees before touch",
            body_logic="Her hand guides his mouth and then turns him toward the bed",
            sensory_asymmetry="His voice stays level while her skin warms",
            disclosure="She names the witness she previously concealed",
            plot_payment="The drive evidence changes tomorrow's joint plan",
            ending_state="They choose one action without erasing disagreement",
            raw_proposal_hash="raw", proposal_seed=3,
        )
        prior = '"Who did you leave inside?"\n\n"Marta," he said.'
        prompt, _ = render_stage_prompt(
            stage="transaction", recipe=recipe, cell=cell,
            program=_program(1, cell.cell_id), passages=passages,
            graphs=graphs, bridge_dir=BRIDGES,
            prior_completion=prior, transaction=transaction,
        )
        self.assertTrue(prompt.endswith(target_runway(recipe, cell) + "\n\n" + prior))
        self.assertLess(prompt.rfind("LOCAL MOVEMENT"), prompt.rfind("MANUSCRIPT\n"))
        self.assertNotIn(SCENE_SENTINEL, prompt)

    def test_source_nearest_transaction_binds_all_sampled_latent_fields(self) -> None:
        passages = extract_gabaldon_examples(DEFAULT_SOURCE)
        graphs = {item.passage_id: _graph_for(item) for item in passages}
        cell = default_benchmarks()[2]
        recipe = next(
            item for item in loom_recipes()
            if item.recipe_id == "loom-source-nearest-doc"
        )
        transaction = TransactionProgram(
            transaction_id="t-review", parent_id="a-review",
            offer="Esther turns the accusation into a concrete invitation",
            counteroffer="Simon asks her to choose both pace and evidence",
            consent_turn="She asks him to wait and he confirms before touch",
            body_logic="She turns toward the table and guides his hand to her hip",
            sensory_asymmetry="The drive clicks while his breathing remains deliberately quiet",
            disclosure="The polling signal reveals a nearby observer",
            plot_payment="The drive evidence forces a joint departure plan",
            ending_state="They dress and leave with a decision made together",
            raw_proposal_hash="raw-review", proposal_seed=4,
        )
        prompt, _ = render_stage_prompt(
            stage="transaction", recipe=recipe, cell=cell,
            program=_program(1, cell.cell_id), passages=passages,
            graphs=graphs, bridge_dir=BRIDGES,
            prior_completion='"Who did you leave inside?"',
            transaction=transaction,
        )
        for expected in (
            transaction.body_logic,
            transaction.sensory_asymmetry,
            transaction.ending_state,
            "Keep positions and every change of initiative physically legible",
            "render the mutually responsive completion",
        ):
            self.assertIn(expected, prompt)
        self.assertNotIn("You chose which of us was allowed to be frightened", prompt)
        self.assertTrue(prompt.endswith(
            target_runway(recipe, cell) + '\n\n"Who did you leave inside?"'
        ))

    def test_complete_stage_prefix_stops_on_paragraph_boundary(self) -> None:
        paragraph = " ".join(["word"] * 95) + "."
        raw = paragraph + "\n\n" + paragraph + "\n\nunfinished tail"
        selected = _complete_stage_prefix(raw, minimum_words=180, maximum_words=210)
        self.assertTrue(selected.endswith("."))
        self.assertNotIn("unfinished", selected)

    def test_approach_rejects_premature_explicit_action(self) -> None:
        text = (
            'Esther touched the drive seal. "Tell me," she said. '
            'Simon put his hand over hers. "Yes," he said. '
            'Then he penetrated her.'
        )
        report = _stage_diagnostics("approach", text, text)
        self.assertFalse(report["eligible"])
        self.assertGreater(report["explicit_signal"], 0)

    def test_approach_detects_euphemistic_entry(self) -> None:
        text = (
            'Esther touched the drive seal. "Tell me," she said. '
            'Simon put his hand over hers. "Yes," he said. '
            'She registered the slide of him inside.'
        )
        report = _stage_diagnostics("approach", text, text)
        self.assertFalse(report["eligible"])
        self.assertGreater(report["explicit_signal"], 0)

    def test_explicit_words_without_transaction_are_rejected(self) -> None:
        text = (
            'Esther watched Simon. "Do you want me?" she asked. "Yes." '
            'He penetrated her. Their bodies moved together until climax. '
            'The drive and its broken seal remained on the table.'
        )
        report = _stage_diagnostics("transaction", text, text)
        self.assertFalse(report["eligible"])
        self.assertTrue(report["cliche_hits"])

    def test_ordinary_came_does_not_fake_intimacy_completion(self) -> None:
        text = (
            'Esther touched the drive seal. "May I?" she asked. "Yes," Simon said. '
            'His hand came up to meet hers while they discussed the security plan.'
        )
        report = _stage_diagnostics("transaction", text, text)
        self.assertEqual(report["completed_intimacy_signal"], 0)
        self.assertEqual(report["completed_intimacy_evidence"], [])

    def test_released_hand_and_came_back_do_not_fake_completion(self) -> None:
        text = (
            'Esther released his thigh. "Did you hear it?" she asked. '
            'They came back together to inspect the drive seal.'
        )
        report = _stage_diagnostics("transaction", text, text)
        self.assertEqual(report["completed_intimacy_signal"], 0)
        self.assertEqual(report["completed_intimacy_evidence"], [])

    def test_seed_and_shared_release_count_as_completion(self) -> None:
        text = (
            'Esther asked Simon to wait, and he waited. She guided his hand, kissed him, '
            'and chose the pace as he entered her. His seed burst inside her; their release '
            'left them breathing together. The compromised house, courier, drive, broken '
            'seal, private papers, and tonight\'s removal plan changed their decision.'
        )
        report = _stage_diagnostics("transaction", text, text)
        self.assertGreaterEqual(report["completed_intimacy_signal"], 2)
        self.assertGreaterEqual(report["plot_payment_signal"], 6)

    def test_terminal_ledger_does_not_retry_failed_fixed_seed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calls.jsonl"
            records = (
                {"call_id": "a", "status": "started"},
                {"call_id": "a", "status": "failed"},
                {"call_id": "b", "status": "completed"},
                {"call_id": "c", "status": "started"},
            )
            path.write_text("".join(json.dumps(item) + "\n" for item in records))
            self.assertEqual(_terminal_call_ids(path, "call_id"), {"a", "b"})

    def test_seeded_stage_selection_is_reproducible_and_not_top_k(self) -> None:
        items = []
        for index in range(6):
            items.append({
                "stage_candidate_id": f"c{index}",
                "segment": f"distinct motif {index} " * (index + 1),
                "diagnostics": {"eligible": True, "quality_signal": 10 + index},
            })
        first = _seeded_diverse_stage_selection(items, count=3, seed=123)
        replay = _seeded_diverse_stage_selection(items, count=3, seed=123)
        self.assertEqual(
            [item["stage_candidate_id"] for item in first],
            [item["stage_candidate_id"] for item in replay],
        )
        self.assertNotEqual(
            [item["stage_candidate_id"] for item in first],
            ["c5", "c4", "c3"],
        )

    def test_campaign_manifest_hash_locks_bridge_set(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            campaign = init_campaign(
                campaign_dir=directory,
                corpus_source=DEFAULT_SOURCE,
                bridge_dir=BRIDGES,
            )
            replay = init_campaign(
                campaign_dir=directory,
                corpus_source=DEFAULT_SOURCE,
                bridge_dir=BRIDGES,
            )
            self.assertEqual(campaign["campaign_hash"], replay["campaign_hash"])

    def test_explicit_calibration_requires_a_heat_floor(self) -> None:
        cell = default_benchmarks()[2]
        generic = {
            "passed": True,
            "gates": {"word_band": True, "natural_stop": True},
            "diagnostics": {
                "erotic_charge_signal": 12,
                "anatomical_specificity_signal": 0,
                "completed_intimacy_action_signal": 0,
                "consent_language_signal": 4,
            },
        }
        checked = calibration_gate(cell, generic)
        self.assertFalse(checked["passed"])
        self.assertFalse(checked["gates"]["heat_target_floor"])


if __name__ == "__main__":
    unittest.main()
