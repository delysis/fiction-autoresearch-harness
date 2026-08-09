from __future__ import annotations

from dataclasses import asdict
from contextlib import closing, contextmanager
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest

from fiction_harness.anti_copy import AntiCopyIndex
from fiction_harness.autoresearch import BenchmarkCell, IntimacySceneGraph, SourcePassage
from fiction_harness.autoresearch_v4 import (
    ManuscriptAssembly,
    ModelSpan,
    PromptRecipeV4,
    SamplerV4,
    _complete_paragraph_prefix,
    _assert_resumable_request,
    _generation_request_hash,
    _generation_continuity_page,
    _exact_paragraph_spans,
    _exact_paragraph_windows,
    _exact_causal_windows,
    _movement_payment_page,
    _movement_retrieval_profile,
    _has_s01_status_transaction,
    _s01_spark_stage_gate,
    _source_boundary_quality,
    _topology_spark_prefix,
    _bind_span_to_call,
    _write_verified_assembly,
    apprenticeship_excerpt_word_band,
    annotate_corpus_source_graphs,
    boltzmann_select,
    cold_replay_v4_call,
    ensure_excerpt_graph_annotations,
    generation_source_passages,
    hard_gate,
    initial_recipes,
    init_campaign,
    merge_apprenticeship_retrievals,
    movements_for_cell,
    movement_word_band,
    movement_gate,
    movement_boundary_spark_gate,
    render_movement_audition_prompt,
    movement_function_score,
    parse_critic,
    parse_pairwise_critic,
    package_finalists,
    prepare_prompt_family,
    render_generation_prompt,
    render_bookfront_runway_prompt,
    render_bookfront_synopsis_runway_prompt,
    render_graph_paired_bookfront_runway_prompt,
    render_graph_paired_canon_bookfront_runway_prompt,
    render_graph_paired_continuity_bookfront_runway_prompt,
    render_graph_paired_named_continuity_bookfront_runway_prompt,
    render_direct_apprenticeship_runway_prompt,
    render_dwell_apprenticeship_runway_prompt,
    render_isomorphic_dwell_runway_prompt,
    render_natural_anthology_runway_prompt,
    render_parallel_book_continuity_runway_prompt,
    render_parallel_book_persona_runway_prompt,
    render_runway_prompt,
    render_source_conditioned_runway_prompt,
    retrieve_passages,
    retrieve_passages_for_movement,
    s01_cell,
    seal_benchmark_protocol,
    verify_benchmark_seal,
    open_confirmation_benchmark,
    runway_gate,
    runway_word_band,
    source_movement_excerpt,
    split_manuscript_runway,
    topology_screen_gate,
    topology_screen_movement,
    topology_spark_gate,
    topology_spark_movement,
    validate_recipe_mutation,
    verify_assembly,
)
from fiction_harness.core import hash_json, sha256_text, write_json


def cell() -> BenchmarkCell:
    return BenchmarkCell(
        cell_id="charged-restraint", label="test", heat_band="charged-restraint",
        intimacy_mode="non-sex-sex-scene", word_min=300, word_max=500,
        story_program=("Adult Mara chooses contact.", "Jonah stops while desire remains."),
        hard_constraints=("close third Mara", "no consummation"), opening_fragment="",
    )


def passage(number: int, *, mode: str = "non-sex-sex-scene") -> SourcePassage:
    text = (
        '"Will you wait?" Mara asked. Jonah answered by opening his hand. '
        "She watched the choice settle between them, warm as lamplight. " * 8
    )
    return SourcePassage(
        passage_id=f"source.{number}", example_number=number, title="Example",
        source_work="Book", partition="profiling", location=str(number),
        text_hash=sha256_text(text), word_count=len(text.split()),
        intimacy_mode=mode, heat_band="charged-restraint", prompt_eligible=True,
        text=text,
    )


def graph(item: SourcePassage) -> IntimacySceneGraph:
    return IntimacySceneGraph(
        graph_id="graph." + item.passage_id, passage_id=item.passage_id,
        emotional_offer="He offers an open hand.",
        emotional_counteroffer="She asks him to wait.",
        relationship_history="They distrust easy interpretations.",
        present_stakes="Contact may change trust.",
        dialogue_act_sequence=("offer", "question", "answer"),
        body_language_counterpoint=("The hand remains open.",),
        sensory_channels=("touch", "sound", "temperature"),
        narrative_distance_curve=("close", "widen", "close"),
        physical_logistics=("They face one another.",),
        agency_actions=("offer", "answer", "stop"),
        relationship_delta="They trust one another more.",
        story_state_change="They choose another meeting.",
        intimacy_mode=item.intimacy_mode, heat_band=item.heat_band,
    )


class RecipeTests(unittest.TestCase):
    def test_sealed_benchmark_binds_split_protocol_code_and_one_time_open(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            (project / "fiction_harness").mkdir(parents=True)
            (project / "fiction_harness" / "engine.py").write_text(
                "VERSION = 1\n", encoding="utf-8"
            )
            cells = []
            for index, cell_id in enumerate(("dev", "cal", "confirm"), 1):
                item = asdict(BenchmarkCell(
                    cell_id=cell_id, label=cell_id, heat_band="none",
                    intimacy_mode="nonsexual-pressure", word_min=300,
                    word_max=500, story_program=("A choice changes the scene.",),
                    hard_constraints=("close third",), opening_fragment="",
                ))
                item["cell_hash"] = hash_json(item)
                cells.append(item)
            benchmark_path = root / "benchmarks.json"
            write_json(benchmark_path, {"cells": cells})
            metadata = {
                cell_id: {
                    "genre": "romance", "story_world_id": f"world-{cell_id}",
                    "source_book_id": f"book-{cell_id}", "pov": "close-third",
                    "scene_purpose": "choice", "heat_band": "none",
                    "affect_arc": "pressure-to-choice",
                }
                for cell_id in ("dev", "cal", "confirm")
            }
            protocol_path = root / "protocol.json"
            write_json(protocol_path, {
                "partitions": {
                    "development": ["dev"], "calibration": ["cal"],
                    "confirmation": ["confirm"],
                },
                "cell_metadata": metadata,
                "primary_metric": "blind target-reader pairwise preference",
                "secondary_metrics": ["desire-to-continue"],
                "prompt_arms": ["raw-continuation"],
                "sampler_arms": [{"top_p": 0.85}],
                "selection_arms": ["random"],
                "seed_manifest": [11, 29],
                "critic_manifest": {"critic": "frozen"},
                "gate_manifest": {"hard_gate": "frozen"},
                "analysis_plan": "report all exclusions and paired wins",
                "stopping_rule": "one opening and no adaptive mutation",
            })
            seal_path = root / "seal.json"
            seal = seal_benchmark_protocol(
                benchmarks_path=benchmark_path, protocol_path=protocol_path,
                output_path=seal_path, project_root=project, minimum_cells=3,
            )
            self.assertEqual(
                verify_benchmark_seal(seal_path=seal_path, project_root=project)["seal_hash"],
                seal["seal_hash"],
            )
            corpus_path = root / "corpus.json"
            write_json(corpus_path, {"passages": [], "graphs": []})
            campaign_root = root / "campaign"
            campaign = init_campaign(
                campaign_dir=campaign_root, corpus_path=corpus_path,
                benchmarks_path=benchmark_path, project_root=project,
                benchmark_seal_path=seal_path,
            )
            self.assertEqual(campaign["experiment_mode"], "sealed_confirmation")
            first = open_confirmation_benchmark(campaign_dir=campaign_root)
            second = open_confirmation_benchmark(campaign_dir=campaign_root)
            self.assertEqual(first["opening_hash"], second["opening_hash"])
            (project / "fiction_harness" / "engine.py").write_text(
                "VERSION = 2\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "source tree changed"):
                verify_benchmark_seal(seal_path=seal_path, project_root=project)

    def test_sealed_benchmark_rejects_story_world_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            (project / "fiction_harness").mkdir(parents=True)
            cells = []
            for cell_id in ("dev", "cal", "confirm"):
                item = asdict(BenchmarkCell(
                    cell_id=cell_id, label=cell_id, heat_band="none",
                    intimacy_mode="nonsexual-pressure", word_min=300,
                    word_max=500, story_program=("A choice.",),
                    hard_constraints=("close third",), opening_fragment="",
                ))
                item["cell_hash"] = hash_json(item)
                cells.append(item)
            benchmark = root / "benchmarks.json"
            write_json(benchmark, {"cells": cells})
            protocol = root / "protocol.json"
            common = {
                "genre": "romance", "story_world_id": "leaking-world",
                "pov": "close-third", "scene_purpose": "choice",
                "heat_band": "none", "affect_arc": "pressure-to-choice",
            }
            write_json(protocol, {
                "partitions": {"development": ["dev"], "calibration": ["cal"], "confirmation": ["confirm"]},
                "cell_metadata": {
                    name: {**common, "source_book_id": f"book-{name}"}
                    for name in ("dev", "cal", "confirm")
                },
                "primary_metric": "preference", "secondary_metrics": ["pull"],
                "prompt_arms": ["raw"], "sampler_arms": ["nucleus"],
                "selection_arms": ["random"], "seed_manifest": [1],
                "critic_manifest": {"v": 1}, "gate_manifest": {"v": 1},
                "analysis_plan": "frozen", "stopping_rule": "one shot",
            })
            with self.assertRaisesRegex(ValueError, "leaks across"):
                seal_benchmark_protocol(
                    benchmarks_path=benchmark, protocol_path=protocol,
                    output_path=root / "seal.json", project_root=project,
                    minimum_cells=3,
                )

    def test_topology_screen_uses_observable_causal_transaction(self) -> None:
        movement = topology_screen_movement(cell())
        self.assertIn("Mara must say his name and ask him to wait", movement)
        self.assertIn("he stops immediately", movement)
        self.assertIn("makes the counteroffer herself", movement)
        self.assertIn("No kiss occurs", movement)
        self.assertNotIn("develop pressure", movement.casefold())
        self.assertEqual(_movement_retrieval_profile(movement)[0], "complication")
        self.assertNotIn("first kiss", _movement_payment_page(cell(), movement).casefold())

    def test_topology_screen_rejects_atmosphere_without_the_transaction(self) -> None:
        atmospheric = (
            "Mara watched Jonah breathe beneath the streetlight. He waited in "
            "silence, and she moved closer to his warmth."
        )
        self.assertFalse(topology_screen_gate(cell(), atmospheric)["passed"])
        transaction = (
            '"Jonah, wait," Mara said. He stopped immediately and turned back. '
            '"Walk with me?" she asked.'
        )
        self.assertTrue(topology_screen_gate(cell(), transaction)["passed"])

    def test_topology_screen_attributes_the_walking_offer_to_mara(self) -> None:
        prefix = '"Jonah," Mara called. He stopped at once and waited. '
        self.assertTrue(topology_screen_gate(
            cell(), prefix + '"May I walk with you?" Mara asked.'
        )["passed"])
        self.assertFalse(topology_screen_gate(
            cell(), prefix + '"Shall I walk with you?" he asked.'
        )["passed"])

    def test_topology_spark_splits_the_transaction_without_human_prose(self) -> None:
        movement = topology_spark_movement(cell())
        self.assertIn("stop before Mara asks him to walk with her", movement)
        spark = '"Jonah, wait," Mara said. He stopped immediately and turned back.'
        self.assertTrue(topology_spark_gate(cell(), spark)["passed"])
        premature = spark + ' "Walk with me?" she asked.'
        self.assertFalse(topology_spark_gate(cell(), premature)["passed"])

    def test_topology_spark_extractor_stops_at_earliest_paid_hinge(self) -> None:
        first = '"Jonah?" Mara said. He stopped at once and waited.'
        later = "She followed him down the hill and began explaining the session."
        text, start, end = _topology_spark_prefix(first + "\n\n" + later, cell())
        self.assertEqual(text, first)
        self.assertEqual(start, 0)
        self.assertEqual(end, len(first))

    def test_topology_spark_allows_dramatic_dwell_before_hinge(self) -> None:
        dwell = " ".join(["Mara watched him walk beneath the streetlights."] * 30)
        hinge = '"Jonah?" Mara said. He stopped at once and waited.'
        raw = dwell + "\n\n" + hinge + "\n\nShe followed."
        text, start, end = _topology_spark_prefix(raw, cell(), maximum_words=350)
        self.assertTrue(text.endswith(hinge))
        self.assertEqual(start, 0)
        self.assertEqual(end, len(dwell + "\n\n" + hinge))

    def test_initial_recipes_cover_six_distinct_topologies(self) -> None:
        recipes = initial_recipes()
        self.assertEqual(len(recipes), 6)
        self.assertEqual(len({item.topology for item in recipes}), 6)
        self.assertTrue(all(item.runway_type == "generated-opening" for item in recipes))
        anthology = next(item for item in recipes if item.topology == "parallel-book")
        self.assertEqual(anthology.encoding, "natural-book")

    def test_parallel_book_persona_adds_character_system_without_prose_runway(self) -> None:
        s01 = BenchmarkCell(
            cell_id="fulcrum-s01", label="S01", heat_band="charged-restraint",
            intimacy_mode="non-sex-sex-scene", word_min=1500, word_max=2500,
            story_program=("Mara arrives at Fulcrum.",),
            hard_constraints=("close third Mara",), opening_fragment="",
        )
        items = tuple(passage(index) for index in range(4))
        graphs = {item.passage_id: graph(item) for item in items}
        prompt, _ = render_parallel_book_persona_runway_prompt(
            s01, items, source_count=3, graphs=graphs,
        )
        self.assertIn("Principal characters", prompt)
        self.assertIn("infrastructure-security engineer", prompt)
        self.assertTrue(prompt.endswith("Chapter One\nArrival\n\n"))

    def test_natural_anthology_moves_controls_away_from_manuscript_boundary(self) -> None:
        from fiction_harness.autoresearch_v4 import s01_cell
        s01 = s01_cell()
        items = tuple(passage(index) for index in range(3))
        graphs = {item.passage_id: graph(item) for item in items}
        prompt, source_ids = render_natural_anthology_runway_prompt(
            s01, items, source_count=3, graphs=graphs,
        )
        self.assertEqual(set(source_ids), {item.passage_id for item in items})
        self.assertIn("half-full glass", prompt)
        self.assertTrue(prompt.endswith("FULCRUM\n\nA novel\n\nChapter One\n\n"))
        local_tail = prompt[-200:]
        self.assertNotIn("Detailed contents", local_tail)
        self.assertNotIn("Principal characters", local_tail)
        self.assertNotIn("Present movement payment", local_tail)

    def test_direct_apprenticeship_places_exact_payment_near_blank_chapter(self) -> None:
        from fiction_harness.autoresearch_v4 import s01_cell
        s01 = s01_cell()
        items = tuple(passage(index) for index in range(3))
        graphs = {item.passage_id: graph(item) for item in items}
        prompt, _ = render_direct_apprenticeship_runway_prompt(
            s01, items, source_count=3, graphs=graphs,
        )
        self.assertIn("Within the opening 110 words", prompt[-1500:])
        self.assertIn("half-full glass", prompt[-1500:])
        self.assertTrue(prompt.endswith("FULCRUM\n\nChapter One\n\n"))

    def test_dwell_apprenticeship_pairs_every_design_with_source_prose(self) -> None:
        from fiction_harness.autoresearch_v4 import s01_cell
        items = tuple(passage(index) for index in range(3))
        graphs = {item.passage_id: graph(item) for item in items}
        prompt, source_ids = render_dwell_apprenticeship_runway_prompt(
            s01_cell(), items, source_count=3, graphs=graphs,
        )
        self.assertEqual(len(source_ids), 3)
        self.assertEqual(prompt.count("Dramatic design"), 4)
        self.assertEqual(prompt.count("Manuscript"), 4)
        self.assertTrue(prompt.endswith("Manuscript\n\n"))

    def test_isomorphic_dwell_uses_next_example_as_target(self) -> None:
        from fiction_harness.autoresearch_v4 import s01_cell
        items = tuple(passage(index) for index in range(3))
        graphs = {item.passage_id: graph(item) for item in items}
        prompt, _ = render_isomorphic_dwell_runway_prompt(
            s01_cell(), items, source_count=3, graphs=graphs,
        )
        self.assertNotIn("\n\nTARGET\n\n", prompt)
        self.assertIn("EXAMPLE 4\n\nDramatic design", prompt)
        self.assertEqual(prompt.count("Offer (15%):"), 4)
        self.assertEqual(prompt.count("Counteroffer and resistance (25%):"), 4)
        self.assertEqual(prompt.count("Complication and embodied negotiation (35%):"), 4)
        self.assertEqual(prompt.count("Consequential turn (15%):"), 4)
        self.assertEqual(prompt.count("Concrete stopping state (10%):"), 4)
        self.assertTrue(prompt.endswith("Manuscript\n\n"))

    def test_ordered_isomorphic_dwell_preserves_declared_curriculum(self) -> None:
        from fiction_harness.autoresearch_v4 import s01_cell
        items = tuple(passage(index) for index in range(3))
        graphs = {item.passage_id: graph(item) for item in items}
        prompt, source_ids = render_isomorphic_dwell_runway_prompt(
            s01_cell(), items, source_count=3, graphs=graphs,
            preserve_input_order=True,
        )
        self.assertEqual(source_ids, tuple(item.passage_id for item in items))
        positions = [prompt.index(item.text.strip()) for item in items]
        self.assertEqual(positions, sorted(positions))

    def test_short_opening_spark_does_not_owe_the_first_movement_payment(self) -> None:
        from fiction_harness.autoresearch_v4 import opening_spark_gate, s01_cell
        text = (
            "Mara arrived alone at Fulcrum's redwood compound as the evening welcome "
            "began. The glass building held the sunset like a confidence it had not "
            "earned, and she paused beside the patio before deciding where to put her bag."
        )
        result = opening_spark_gate(
            s01_cell(), text,
            {"hard_fail": False, "unresolved_flags": False},
        )
        self.assertTrue(result["passed"])
        self.assertNotIn("s01_status_transaction", result["gates"])

    def test_opening_spark_accepts_the_welcome_terrace_but_not_later_residence(self) -> None:
        from fiction_harness.autoresearch_v4 import opening_spark_gate, s01_cell
        overlap = {"hard_fail": False, "unresolved_flags": False}
        welcome = (
            "When Mara walked into the conference area, a young man crossed the "
            "terrace and asked whether she wanted to sit down. She watched his gait "
            "before answering, unsure whether the welcome had already begun. Beyond "
            "him, redwood trunks divided the last light into narrow copper bands."
        )
        later = (
            "THE FIRST MORNING after moving in, Mara walked across the campus. "
            "She had come to think of the institute's gatehouse as a useful landmark "
            "on her daily walk to the office."
        )
        self.assertTrue(opening_spark_gate(s01_cell(), welcome, overlap)["passed"])
        self.assertFalse(opening_spark_gate(s01_cell(), later, overlap)["passed"])

    def test_cocktail_dress_does_not_trip_anatomical_heat_gate(self) -> None:
        from fiction_harness.autoresearch_v4 import hard_gate, s01_cell
        result = hard_gate(
            s01_cell(),
            "Mara arrived at Fulcrum in a black silk cocktail dress.",
            {"hard_fail": False, "unresolved_flags": False},
        )
        self.assertTrue(result["gates"]["heat_ceiling"])

    def test_opening_spark_rejects_another_book_heading_or_attribution(self) -> None:
        from fiction_harness.autoresearch_v4 import opening_spark_gate, s01_cell
        overlap = {"hard_fail": False, "unresolved_flags": False}
        for prefix in ("46 The Glass", "Excerpt from The Circle by Someone"):
            text = (
                prefix + "\n\nMara arrived alone at Fulcrum's redwood compound for "
                "the evening welcome. She stopped by the patio and studied the room "
                "before deciding where to leave her bag and whom to ask for directions."
            )
            self.assertFalse(opening_spark_gate(s01_cell(), text, overlap)["passed"])

    def test_confirmed_floating_object_collapses_ambiguous_world_status(self) -> None:
        from fiction_harness.autoresearch_v4 import hard_gate, s01_cell
        result = hard_gate(
            s01_cell(),
            "Mara watched the glass sitting in midair while everyone applauded.",
            {"hard_fail": False, "unresolved_flags": False},
        )
        self.assertFalse(result["gates"]["ambiguous_world_status"])

    def test_s01_cannot_invent_a_prior_group_session(self) -> None:
        from fiction_harness.autoresearch_v4 import hard_gate, s01_cell
        result = hard_gate(
            s01_cell(),
            "Mara recognized Jonah from the earlier group meeting and remembered "
            "what Adrian had said earlier about their training.",
            {"hard_fail": False, "unresolved_flags": False},
        )
        self.assertFalse(result["gates"]["s01_no_prior_session"])
        prior_contact = hard_gate(
            s01_cell(),
            "Mara thought it was the boy she had met in the hall last night.",
            {"hard_fail": False, "unresolved_flags": False},
        )
        self.assertFalse(prior_contact["gates"]["s01_no_prior_session"])
        invented_briefing = hard_gate(
            s01_cell(),
            "Mara remembered what Livia had said at the other Fulcrum facility, "
            "where their backgrounds had been checked.",
            {"hard_fail": False, "unresolved_flags": False},
        )
        self.assertFalse(invented_briefing["gates"]["s01_no_prior_session"])

    def test_apprenticeship_scaffold_replay_is_a_hard_failure(self) -> None:
        from fiction_harness.autoresearch_v4 import hard_gate, s01_cell
        text = (
            "* * *\n\nEXAMPLE 6\n\nDramatic design\n"
            "Offer (15%): Mara arrives at Fulcrum.\n\nManuscript\nMara arrived."
        )
        result = hard_gate(
            s01_cell(), text,
            {"hard_fail": False, "unresolved_flags": False},
        )
        self.assertFalse(result["passed"])
        self.assertIn("apprenticeship scaffold replay", result["diagnostics"]["control_leaks"])

    def test_manuscript_boundary_label_replay_is_a_hard_failure(self) -> None:
        cell = s01_cell()
        for label in (
            "The manuscript text after the present boundary",
            "Manuscript after the continuation",
            "CONTINUATION",
        ):
            with self.subTest(label=label):
                text = f"Mara watched the door.\n\n{label}\nAdrian entered and smiled."
                result = hard_gate(
                    cell, text,
                    {"hard_fail": False, "unresolved_flags": False},
                )
                self.assertFalse(result["passed"])
                self.assertIn(
                    "manuscript boundary label replay",
                    result["diagnostics"]["control_leaks"],
                )

    def test_generated_scaffold_heading_family_is_a_hard_failure(self) -> None:
        result = hard_gate(
            s01_cell(),
            "Mara watched.\n\nManchu script\nFirst part\n\nAdrian entered.",
            {"hard_fail": False, "unresolved_flags": False},
        )
        self.assertFalse(result["passed"])
        self.assertIn(
            "generated scaffold heading",
            result["diagnostics"]["control_leaks"],
        )

    def test_child_must_change_exactly_one_axis(self) -> None:
        parent = initial_recipes()[1]
        child = PromptRecipeV4(
            recipe_id="child", topology=parent.topology,
            context_tokens=16_000, source_count=parent.source_count,
            source_order=parent.source_order, graph_granularity=parent.graph_granularity,
            target_density=parent.target_density, runway_type=parent.runway_type,
            encoding=parent.encoding, sampler=parent.sampler,
            parent_recipe_hash=parent.recipe_hash, mutated_axis="context_tokens",
        )
        self.assertEqual(validate_recipe_mutation(parent, child), "context_tokens")
        bad = PromptRecipeV4(
            recipe_id="bad", topology="graph-prose", context_tokens=16_000,
            source_count=parent.source_count, parent_recipe_hash=parent.recipe_hash,
            mutated_axis="context_tokens",
        )
        with self.assertRaises(ValueError):
            validate_recipe_mutation(parent, bad)

    def test_movement_local_source_router_is_one_axis_mutation(self) -> None:
        parent = next(item for item in initial_recipes() if item.topology == "parallel-book")
        child = PromptRecipeV4(
            recipe_id=parent.recipe_id + ".movement-local", topology=parent.topology,
            context_tokens=parent.context_tokens, source_count=parent.source_count,
            source_order="movement-local", graph_granularity=parent.graph_granularity,
            target_density=parent.target_density, runway_type=parent.runway_type,
            encoding=parent.encoding, sampler=parent.sampler,
            parent_recipe_hash=parent.recipe_hash, mutated_axis="source_order",
        )
        self.assertEqual(validate_recipe_mutation(parent, child), "source_order")

    def test_status_game_retrieval_profile_names_service_transaction(self) -> None:
        stage, lines = _movement_retrieval_profile(
            "A young fellow leaves a half-full glass; an older catering worker retrieves it."
        )
        self.assertEqual(stage, "approach")
        self.assertIn("servant", " ".join(lines))
        self.assertIn("glass", " ".join(lines))

    def test_status_game_retrieval_prefers_service_action_over_generic_pressure(self) -> None:
        generic = passage(1, mode="nonsexual-pressure")
        service = passage(2, mode="nonsexual-pressure")
        service_text = (
            "A maid carried a tray through the conversation. A guest left his glass; "
            "the waiter cleared it without acknowledgment. " * 12
        )
        service = SourcePassage(**(
            asdict(service) | {
                "text": service_text,
                "text_hash": sha256_text(service_text),
                "word_count": len(service_text.split()),
                "heat_band": "none",
            }
        ))
        generic = SourcePassage(**(
            asdict(generic) | {"heat_band": "none"}
        ))
        selected = retrieve_passages_for_movement(
            cell(), (generic, service),
            movement="A young fellow leaves a half-full glass; an older catering worker retrieves it.",
            count=1, graphs={generic.passage_id: graph(generic), service.passage_id: graph(service)},
        )
        self.assertEqual(selected[0].passage_id, service.passage_id)


class PromptTests(unittest.TestCase):
    def test_movement_function_score_requires_the_service_transaction(self) -> None:
        movement = dict(movements_for_cell(s01_cell()))["labor-recognition"]
        self.assertEqual(
            movement_function_score(
                "The guest left his glass without looking. A hired footman "
                "silently carried it away.", movement,
            ),
            1.0,
        )
        self.assertLess(
            movement_function_score(
                "The guests discussed their half-full lives over wine.", movement,
            ),
            2.0 / 3.0,
        )

    def test_exact_excerpt_admission_reranks_parent_scenes(self) -> None:
        movement = dict(movements_for_cell(s01_cell()))["labor-recognition"]
        filler = ("They discussed a servant and a glass in the abstract. " * 45).strip()
        false_scene = SourcePassage(**(
            asdict(passage(1, mode="nonsexual-pressure")) | {
                "text": filler,
                "text_hash": sha256_text(filler),
                "word_count": len(filler.split()),
                "heat_band": "none",
            }
        ))
        actual = (
            "The talk continued across the table. " * 18
            + "\n\nA guest left his wine glass on the balustrade without looking. "
            "The hired footman came silently, lifted the glass, and carried it away. " * 8
        ).strip()
        true_scene = SourcePassage(**(
            asdict(passage(2, mode="nonsexual-pressure")) | {
                "text": actual,
                "text_hash": sha256_text(actual),
                "word_count": len(actual.split()),
                "heat_band": "none",
            }
        ))
        recipe = PromptRecipeV4(
            "micro", "parallel-book", source_count=1,
            source_order="movement-local-excerpt", encoding="natural-book",
        )
        selected = generation_source_passages(
            recipe=recipe,
            cell=s01_cell(),
            passages=(false_scene, true_scene),
            graphs={
                false_scene.passage_id: graph(false_scene),
                true_scene.passage_id: graph(true_scene),
            },
            movement=movement,
        )
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].passage_id, true_scene.passage_id)
        self.assertIn("hired footman", selected[0].text)
        self.assertEqual(selected[0].text_hash, sha256_text(selected[0].text))
        self.assertEqual(selected[0].word_count, len(selected[0].text.split()))

    def test_status_apprenticeship_does_not_pad_with_false_examples(self) -> None:
        movement = dict(movements_for_cell(s01_cell()))["labor-recognition"]
        strong_text = (
            "The guest left his glass without looking. The hired footman "
            "silently came, collected the glass, and carried it away. " * 18
        ).strip()
        weak_text = (
            "She put down her glass. The waiter disappeared. They continued "
            "talking about social inferiors. " * 25
        ).strip()
        strong = SourcePassage(**(
            asdict(passage(1, mode="nonsexual-pressure")) | {
                "text": strong_text, "text_hash": sha256_text(strong_text),
                "word_count": len(strong_text.split()), "heat_band": "none",
            }
        ))
        weak = SourcePassage(**(
            asdict(passage(2, mode="nonsexual-pressure")) | {
                "text": weak_text, "text_hash": sha256_text(weak_text),
                "word_count": len(weak_text.split()), "heat_band": "none",
            }
        ))
        selected = generation_source_passages(
            recipe=PromptRecipeV4(
                "micro", "parallel-book", source_count=5,
                source_order="movement-local-excerpt", encoding="natural-book",
            ),
            cell=s01_cell(), passages=(weak, strong),
            graphs={weak.passage_id: graph(weak), strong.passage_id: graph(strong)},
            movement=movement,
        )
        self.assertEqual([item.passage_id for item in selected], [strong.passage_id])

    def test_source_movement_excerpt_is_exact_and_dwell_sized(self) -> None:
        paragraphs = [
            (f"Paragraph {index} glass worker guest voices. " * 12).strip()
            for index in range(6)
        ]
        source = "\n\n".join(paragraphs)
        excerpt = source_movement_excerpt(
            source, "A worker retrieves a glass as guests arrive.",
            minimum_words=80, maximum_words=150,
        )
        self.assertIn(excerpt, source)
        self.assertGreaterEqual(len(excerpt.split()), 80)
        self.assertLessEqual(len(excerpt.split()), 150)

    def test_gathering_excerpt_selects_the_actual_entry(self) -> None:
        filler = "They continued a private conversation beside the lamp. " * 18
        arrival = (
            "Then voices sounded outside the door. The guests came in together, "
            "and everyone turned as their footsteps crossed the threshold. " * 9
        )
        source = filler.strip() + "\n\n" + arrival.strip()
        excerpt = source_movement_excerpt(
            source,
            "Unnamed guests and their voices reach the room and interrupt the pair.",
            minimum_words=70, maximum_words=180,
        )
        self.assertIn(excerpt, source)
        self.assertIn("voices sounded outside the door", excerpt)
        self.assertNotIn("private conversation beside the lamp", excerpt)

    def test_s01_loom_uses_scene_specific_causal_movements(self) -> None:
        from fiction_harness.autoresearch_v4 import s01_cell
        movements = movements_for_cell(s01_cell())
        self.assertEqual([item[0] for item in movements], [
            "dyadic-contact", "gathering-handoff", "glass-deposit", "labor-recognition", "calibration-frame",
            "calibration-choice",
            "livia-entrance", "livia-first-read", "livia-second-read", "jonah-costly-refusal",
            "wrist-contact", "control-collapse", "consequence",
        ])
        self.assertIn("catering worker", movements[3][1])
        self.assertIn("brown-haired visiting fellow", movements[2][1])
        self.assertIn("The visiting fellow and worker remain unnamed", movements[3][1])
        self.assertIn("wrist contact", movements[10][1])
        self.assertEqual(_movement_retrieval_profile(movements[0][1])[0], "approach")
        self.assertEqual(_movement_retrieval_profile(movements[4][1])[0], "complication")
        self.assertEqual(_movement_retrieval_profile(movements[10][1])[0], "embodied-turn")
        self.assertEqual(_movement_retrieval_profile(movements[12][1])[0], "consequence")
        self.assertEqual(movement_word_band(s01_cell(), "dyadic-contact", 1, 2), (70, 220))
        self.assertEqual(movement_word_band(s01_cell(), "gathering-handoff", 1, 2), (60, 180))
        self.assertEqual(movement_word_band(s01_cell(), "glass-deposit", 1, 2), (60, 160))
        self.assertEqual(movement_word_band(s01_cell(), "labor-recognition", 1, 2), (80, 180))
        self.assertEqual(movement_word_band(s01_cell(), "calibration-frame", 1, 2), (140, 240))
        self.assertEqual(movement_word_band(s01_cell(), "calibration-choice", 1, 2), (60, 210))
        self.assertEqual(movement_word_band(s01_cell(), "livia-entrance", 1, 2), (90, 220))
        self.assertEqual(
            apprenticeship_excerpt_word_band(s01_cell(), "labor-recognition", 1, 2),
            (100, 220),
        )

    def test_status_game_rejects_livia_as_the_catering_worker(self) -> None:
        movement = dict(movements_for_cell(s01_cell()))["labor-recognition"]
        segment = (
            "A visiting young fellow left a half-full glass on the wall. "
            "An older catering worker retrieved it. Her name was Livia, and she "
            "set down her tray. Adrian called it a calibration game."
        )
        result = movement_gate(s01_cell(), segment, movement)
        self.assertFalse(result["passed"])
        self.assertIn("labor_recognition_introduces_livia_early", result["defects"])

    def test_labor_gate_accepts_action_triad_with_pronominal_object(self) -> None:
        movement = dict(movements_for_cell(s01_cell()))["labor-recognition"]
        segment = (
            "The glass remained beside the wall while the fellow talked. Mara "
            "noticed an older catering worker come in, pick it up, and leave "
            "without either of them acknowledging her."
        )
        result = movement_gate(s01_cell(), segment, movement)
        self.assertTrue(result["passed"], result["defects"])

    def test_labor_gate_rejects_naming_the_unnamed_fellow(self) -> None:
        movement = dict(movements_for_cell(s01_cell()))["labor-recognition"]
        segment = (
            '"I\'m Sam," the fellow said. Mara noticed an older catering worker '
            "retrieve his glass while the conversation continued."
        )
        result = movement_gate(s01_cell(), segment, movement)
        self.assertFalse(result["passed"])
        self.assertIn(
            "labor_recognition_names_unnamed_character", result["defects"],
        )

    def test_calibration_frame_requires_a_concrete_choice(self) -> None:
        movement = dict(movements_for_cell(s01_cell()))["calibration-frame"]
        vague = movement_gate(
            s01_cell(), "Adrian called it a nonverbal calibration game.", movement,
        )
        self.assertIn("calibration_frame_missing_choice", vague["defects"])
        concrete = movement_gate(
            s01_cell(),
            "Adrian called it a nonverbal game and asked Mara to choose one of "
            "three objects without saying which. She chose the key.",
            movement,
        )
        self.assertTrue(concrete["passed"], concrete["defects"])

    def test_hard_gate_rejects_numbered_outline_as_manuscript(self) -> None:
        text = (
            "1. Adrian enters the room.\n2. Mara chooses the key.\n"
            "3. Jonah watches her answer."
        )
        result = hard_gate(s01_cell(), text, {"hard_fail": False})
        self.assertFalse(result["passed"])
        self.assertFalse(result["gates"]["manuscript_format"])

    def test_s01_social_contact_requires_gathering_handoff(self) -> None:
        from fiction_harness.autoresearch_v4 import s01_cell
        movement = dict(movements_for_cell(s01_cell()))["gathering-handoff"]
        stalled = movement_gate(
            s01_cell(), '“I am Mara,” she said. He watched her without blinking.', movement,
        )
        handed_off = movement_gate(
            s01_cell(),
            '“I am Mara,” she said. Jonah watched her. Voices reached the room as '
            'guests came in, including a young fellow carrying a glass.',
            movement,
        )
        stepped_in = movement_gate(
            s01_cell(),
            "Two voices sounded in the hall before the people stepped into the "
            "room. A young guest carried a glass while talking.",
            movement,
        )
        self.assertFalse(stalled["passed"])
        self.assertTrue(handed_off["passed"])
        self.assertTrue(stepped_in["passed"])
        false_positive = movement_gate(
            s01_cell(),
            '“You are a guest,” Jonah said. He turned to the bar for a drink.',
            movement,
        )
        self.assertFalse(false_positive["passed"])
        alias_leak = movement_gate(
            s01_cell(), "Guests came in while Voss waited outside.", movement,
        )
        self.assertFalse(alias_leak["passed"])
        self.assertIn(
            "gathering_handoff_introduces_adrian_early", alias_leak["defects"],
        )

    def test_s01_micro_movements_have_stage_specific_dwell_bands(self) -> None:
        from fiction_harness.autoresearch_v4 import movement_word_band, s01_cell
        self.assertEqual(movement_word_band(s01_cell(), "dyadic-contact", 250, 450), (70, 220))
        self.assertEqual(movement_word_band(s01_cell(), "livia-entrance", 250, 450), (90, 220))
        self.assertEqual(movement_word_band(s01_cell(), "livia-first-read", 250, 450), (150, 280))
        self.assertEqual(movement_word_band(s01_cell(), "livia-second-read", 250, 450), (160, 300))
        self.assertEqual(movement_word_band(s01_cell(), "jonah-costly-refusal", 250, 450), (170, 320))

    def test_livia_entrance_routes_to_non_erotic_approach_retrieval(self) -> None:
        entrance = dict(movements_for_cell(s01_cell()))["livia-entrance"]
        first_read = dict(movements_for_cell(s01_cell()))["livia-first-read"]
        self.assertEqual(_movement_retrieval_profile(entrance)[0], "approach")
        self.assertEqual(_movement_retrieval_profile(first_read)[0], "complication")

        hot = passage(91)
        hot = SourcePassage(**(asdict(hot) | {
            "heat_band": "open-door-nongraphic",
            "intimacy_mode": "married-intimacy",
        }))
        cool = passage(92, mode="nonsexual-pressure")
        cool = SourcePassage(**(asdict(cool) | {"heat_band": "none"}))
        selected = retrieve_passages_for_movement(
            s01_cell(), (hot, cool), movement=entrance, count=2,
            graphs={hot.passage_id: graph(hot), cool.passage_id: graph(cool)},
        )
        self.assertEqual([item.passage_id for item in selected], [cool.passage_id])

    def test_livia_entrance_function_score_requires_arrival_and_greeting(self) -> None:
        movement = dict(movements_for_cell(s01_cell()))["livia-entrance"]
        self.assertEqual(
            movement_function_score(
                "A woman entered through the doorway. Mara turned. ‘Hello,’ "
                "she said, and held out her hand as Jonah introduced them.",
                movement,
            ),
            1.0,
        )
        self.assertLess(
            movement_function_score(
                "A woman was already sitting in the room and said nothing.",
                movement,
            ),
            1.0,
        )

    def test_livia_entrance_gate_accepts_arrival_but_rejects_read(self) -> None:
        movement = dict(movements_for_cell(s01_cell()))["livia-entrance"]
        entrance = (
            "A voice spoke from the doorway. Mara turned. The newcomer stepped "
            "into the room and offered her hand. ‘I’m Livia,’ she said. Jonah "
            "introduced Mara, and Livia waited beside the table."
        )
        result = movement_gate(s01_cell(), entrance, movement)
        self.assertTrue(result["passed"])
        premature = entrance + " Livia read the covered key and named it."
        result = movement_gate(s01_cell(), premature, movement)
        self.assertFalse(result["passed"])
        self.assertIn("livia_entrance_runs_into_identification", result["defects"])

    def test_livia_entrance_spark_accepts_exact_causal_window(self) -> None:
        from fiction_harness.autoresearch_v4 import movement_boundary_spark_gate
        movement = dict(movements_for_cell(s01_cell()))["livia-entrance"]
        text = (
            "Before anyone answered, a new voice spoke from the doorway. Mara "
            "turned to see a dark-haired woman enter the room and cross toward "
            "them. The woman stopped beside Jonah, held out her hand, and said, "
            "‘I’m Livia. Nice to meet you.’ Jonah introduced Mara. Livia smiled "
            "and waited beside the table while Mara tried to decide what the "
            "woman had noticed about her. Adrian shifted the covered object "
            "away from Livia's reach. No one explained the game yet, and Livia "
            "did not ask. She simply gave Mara enough room to answer the greeting."
        )
        self.assertTrue(movement_boundary_spark_gate(s01_cell(), text, movement)["passed"])

    def test_runway_sized_complete_paragraph_is_not_lost_to_word_band(self) -> None:
        paragraph = " ".join(["Mara"] * 151) + "."
        raw = paragraph + "\n\nThis unfinished paragraph"
        text, _, _ = _complete_paragraph_prefix(raw, 60, 220)
        self.assertEqual(text, paragraph)

    def test_s01_runway_has_room_to_pay_its_opening_graph(self) -> None:
        from fiction_harness.autoresearch_v4 import s01_cell
        self.assertEqual(runway_word_band(cell()), (60, 220))
        self.assertEqual(runway_word_band(s01_cell()), (220, 420))

    def test_stage_gate_rejects_kiss_before_embodied_turn(self) -> None:
        result = movement_gate(
            cell(), "Mara kissed Jonah and then they went inside.",
            "Establish concrete pressure, desire, and an impediment. End on a live offer or discovery.",
        )
        self.assertFalse(result["passed"])
        self.assertIn("kiss_before_embodied_turn", result["defects"])
        self.assertIn("left_locked_night_walk", result["defects"])

    def test_stage_gate_requires_kiss_and_stop_at_embodied_turn(self) -> None:
        bad = movement_gate(
            cell(), "They discussed attraction at length.",
            "Make bodily action and dialogue answer one another. Change knowledge, trust, or choice through observable agency.",
        )
        self.assertFalse(bad["passed"])
        good = movement_gate(
            cell(), "Mara kissed him, then leaned back and said wait.",
            "Make bodily action and dialogue answer one another. Change knowledge, trust, or choice through observable agency.",
        )
        self.assertTrue(good["passed"])

    def test_movement_retrieval_changes_source_by_dramatic_job(self) -> None:
        complication = passage(1)
        embodied = passage(2)
        consequence = passage(3)
        graphs = {
            complication.passage_id: IntimacySceneGraph(
                **(asdict(graph(complication)) | {
                    "emotional_counteroffer": "She resists pressure and interrupts his demand.",
                    "dialogue_act_sequence": ("counteroffer", "refuse", "challenge"),
                    "body_language_counterpoint": ("They keep their distance.",),
                    "agency_actions": ("refuse", "choose"),
                })
            ),
            embodied.passage_id: IntimacySceneGraph(
                **(asdict(graph(embodied)) | {
                    "emotional_counteroffer": "She answers touch with a kiss.",
                    "dialogue_act_sequence": ("ask", "answer", "stop"),
                    "body_language_counterpoint": ("Hands, breath, and posture negotiate contact.",),
                    "physical_logistics": ("They touch, kiss, and separate.",),
                    "agency_actions": ("invite", "answer", "stop"),
                })
            ),
            consequence.passage_id: IntimacySceneGraph(
                **(asdict(graph(consequence)) | {
                    "emotional_counteroffer": "They defer fulfillment after recognition.",
                    "dialogue_act_sequence": ("recognize", "part"),
                    "relationship_delta": "Desire becomes a future choice.",
                    "story_state_change": "They part with a concrete next meeting.",
                })
            ),
        }
        picked = retrieve_passages_for_movement(
            cell(), (complication, embodied, consequence),
            movement="Make the embodied turn through touch and physical contact.",
            count=1, graphs=graphs,
        )
        self.assertEqual(picked[0].passage_id, embodied.passage_id)

    def test_source_boundary_quality_penalizes_mid_exchange_fragments(self) -> None:
        self.assertGreater(
            _source_boundary_quality("Mara made the offer. Jonah answered it."),
            _source_boundary_quality('"I do not know," she said:'),
        )

    def test_resume_hash_rejects_sampler_or_budget_drift(self) -> None:
        base = dict(
            campaign_hash="campaign", prompt_hash="prompt", model="base",
            seed=7, max_tokens=300,
            sampler={"temperature": 0.95}, source_ids=("source.1",),
        )
        recorded = _generation_request_hash(**base)
        _assert_resumable_request({"request_hash": recorded}, recorded, "candidate")
        changed = _generation_request_hash(**(base | {"max_tokens": 301}))
        with self.assertRaisesRegex(ValueError, "resume request hash mismatch"):
            _assert_resumable_request({"request_hash": recorded}, changed, "candidate")

        contracted = _generation_request_hash(
            **base,
            generation_contract={
                "movement_id": "dyadic-contact",
                "movement_word_band": [70, 220],
                "prefix_campaign_hash": "parent-a",
            },
        )
        changed_contract = _generation_request_hash(
            **base,
            generation_contract={
                "movement_id": "dyadic-contact",
                "movement_word_band": [100, 220],
                "prefix_campaign_hash": "parent-a",
            },
        )
        self.assertNotEqual(contracted, changed_contract)

    def test_s01_movement_payment_is_not_coarse_phase_payment(self) -> None:
        gathering = dict(movements_for_cell(s01_cell()))["gathering-handoff"]
        payment = _movement_payment_page(s01_cell(), gathering)
        self.assertIn("Arriving guests interrupt", payment)
        self.assertNotIn("Adrian", payment)
        self.assertNotIn("Livia", payment)
        self.assertNotIn("calibration game", payment)

    def test_generation_continuity_tracks_written_name_and_arrival(self) -> None:
        before = _generation_continuity_page(s01_cell(), "A blond man watched Mara.")
        self.assertIn("has not learned his name", before)
        self.assertNotIn("Adrian", before)
        self.assertNotIn("Livia", before)
        after = _generation_continuity_page(
            s01_cell(), '"Jonah," he said. Adrian entered behind them.',
        )
        self.assertIn("Mara now knows his name", after)
        self.assertIn("Adrian has entered", after)

    def test_local_graph_annotation_excludes_holdout_and_updates_retrieval_facets(self) -> None:
        source = passage(1)
        holdout = asdict(passage(2)) | {
            "passage_id": "source.holdout", "partition": "holdout",
            "text_hash": "holdout-hash",
        }
        response = {
            "emotional_offer": "one person invites an answer",
            "emotional_counteroffer": "the other delays",
            "relationship_history": "familiar adults",
            "present_stakes": "whether to stay",
            "dialogue_act_sequence": ["question", "deflection"],
            "body_language_counterpoint": ["hand remains open"],
            "sensory_channels": ["touch", "sound"],
            "narrative_distance_curve": ["close", "closer"],
            "physical_logistics": ["two people at a door"],
            "agency_actions": ["offer", "refusal remains possible"],
            "relationship_delta": "trust becomes possible",
            "story_state_change": "they agree to meet",
            "intimacy_mode": "charged-contact",
            "heat_band": "charged-restraint",
        }

        class FakeCritic:
            model = "fixture-critic"
            prompts: list[str] = []

            def complete(self, *, messages, **kwargs):
                self.prompts.append(messages[0]["content"])
                return SimpleNamespace(content=json.dumps(response))

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "input.json"
            output_path = root / "output.json"
            write_json(input_path, {
                "record_type": "fixture", "passages": [asdict(source), holdout],
                "graphs": [], "partitions": {
                    "profiling": [source.passage_id], "holdout": ["source.holdout"],
                },
            })
            critic = FakeCritic()
            result = annotate_corpus_source_graphs(
                input_corpus_path=input_path, output_corpus_path=output_path,
                critic=critic,
            )
            compiled = json.loads(output_path.read_text())
        self.assertEqual(result["annotated_total"], 1)
        self.assertEqual(len(critic.prompts), 1)
        self.assertNotIn("source.holdout", critic.prompts[0])
        self.assertEqual(compiled["passages"][0]["intimacy_mode"], "charged-contact")

    def test_exact_excerpt_graph_annotation_is_cached_by_excerpt_hash(self) -> None:
        source = passage(1)
        response = {
            "emotional_offer": "a guest enters",
            "emotional_counteroffer": "the pair separate",
            "relationship_history": "new acquaintances",
            "present_stakes": "attention shifts to the room",
            "dialogue_act_sequence": ["interruption"],
            "body_language_counterpoint": ["hands part as heads turn"],
            "sensory_channels": ["sound"],
            "narrative_distance_curve": ["close"],
            "physical_logistics": ["guests cross a doorway"],
            "agency_actions": ["the pair make room"],
            "relationship_delta": "private attention becomes public",
            "story_state_change": "a gathering begins",
            "intimacy_mode": "nonsexual-pressure",
            "heat_band": "none",
        }

        class FakeCritic:
            model = "fixture-critic"
            calls = 0

            def complete(self, *, messages, **kwargs):
                self.calls += 1
                self.prompt = messages[0]["content"]
                return SimpleNamespace(content=json.dumps(response))

        with tempfile.TemporaryDirectory() as tmp:
            critic = FakeCritic()
            first, hashes = ensure_excerpt_graph_annotations(
                cache_root=Path(tmp), movement_id="gathering-handoff",
                movement="Guests enter and interrupt.", passages=(source,),
                critic=critic,
            )
            second, repeated_hashes = ensure_excerpt_graph_annotations(
                cache_root=Path(tmp), movement_id="gathering-handoff",
                movement="Guests enter and interrupt.", passages=(source,),
                critic=critic,
            )
        self.assertEqual(critic.calls, 1)
        self.assertIn(source.text, critic.prompt)
        self.assertEqual(hashes, repeated_hashes)
        self.assertEqual(first[source.passage_id], second[source.passage_id])

    def test_runway_prompt_contains_no_manuscript_prose(self) -> None:
        prompt = render_runway_prompt(cell())
        self.assertTrue(prompt.endswith("MANUSCRIPT OPENING\n"))
        self.assertNotIn("Jonah stopped beneath", prompt)

    def test_source_conditioned_runway_uses_natural_new_book_boundary(self) -> None:
        sources = (passage(1), passage(2))
        prompt, source_ids = render_source_conditioned_runway_prompt(
            cell(), sources, source_count=2,
        )
        self.assertTrue(prompt.startswith("A note for the forthcoming chapter"))
        self.assertTrue(prompt.endswith("FULCRUM\n\nChapter One\n\n"))
        self.assertNotIn("REFERENCE SCENE", prompt)
        self.assertNotIn("MANUSCRIPT OPENING", prompt)
        self.assertEqual(set(source_ids), {"source.1", "source.2"})

    def test_bookfront_runway_resets_to_adult_target_without_authored_prose(self) -> None:
        prompt, _ = render_bookfront_runway_prompt(
            cell(), (passage(1), passage(2)), source_count=2,
        )
        self.assertIn("Principal characters\nMara Voss — an adult research fellow", prompt)
        self.assertTrue(prompt.endswith("Chapter One\nAfter the Late Session\n\n"))
        self.assertNotIn("MANUSCRIPT OPENING", prompt)

    def test_bookfront_synopsis_places_target_causality_near_blank_chapter(self) -> None:
        prompt, _ = render_bookfront_synopsis_runway_prompt(
            cell(), (passage(1), passage(2)), source_count=2,
        )
        self.assertIn("Detailed contents\n\n1. After the Late Session", prompt)
        self.assertIn("Mara chooses his hand and later the kiss", prompt)
        self.assertTrue(prompt.endswith("Chapter One\nAfter the Late Session\n\n"))
        self.assertNotIn("MANUSCRIPT OPENING", prompt)

    def test_graph_paired_bookfront_teaches_map_then_ends_at_blank_book(self) -> None:
        sources = (passage(1), passage(2))
        graphs = {item.passage_id: graph(item) for item in sources}
        prompt, source_ids = render_graph_paired_bookfront_runway_prompt(
            cell(), sources, source_count=2, graphs=graphs,
        )
        self.assertEqual(prompt.count("Dramatic map"), 2)
        self.assertEqual(prompt.count("Manuscript\n"), 2)
        self.assertIn("Detailed contents", prompt)
        self.assertTrue(prompt.endswith("Chapter One\nAfter the Late Session\n\n"))
        self.assertEqual(set(source_ids), {"source.1", "source.2"})

    def test_graph_paired_canon_page_places_world_and_viewpoint_near_target(self) -> None:
        sources = (passage(1), passage(2))
        prompt, _ = render_graph_paired_canon_bookfront_runway_prompt(
            cell(), sources, source_count=2,
            graphs={item.passage_id: graph(item) for item in sources},
        )
        setting_at = prompt.rfind("Setting\nContemporary Northern California")
        chapter_at = prompt.rfind("Chapter One\nAfter the Late Session")
        self.assertGreater(setting_at, prompt.rfind("Manuscript\n"))
        self.assertGreater(chapter_at, setting_at)
        self.assertIn("have never kissed", prompt[setting_at:chapter_at])

    def test_graph_paired_continuity_page_excludes_invented_romantic_history(self) -> None:
        sources = (passage(1), passage(2))
        prompt, _ = render_graph_paired_continuity_bookfront_runway_prompt(
            cell(), sources, source_count=2,
            graphs={item.passage_id: graph(item) for item in sources},
        )
        continuity_at = prompt.rfind("Continuity\nThe chapter opens outdoors")
        chapter_at = prompt.rfind("Chapter One\nAfter the Late Session")
        self.assertGreater(continuity_at, prompt.rfind("Manuscript\n"))
        self.assertGreater(chapter_at, continuity_at)
        self.assertIn("never dated, kissed, had sex", prompt[continuity_at:chapter_at])

    def test_named_continuity_changes_only_target_author_prior(self) -> None:
        sources = (passage(1), passage(2))
        graphs = {item.passage_id: graph(item) for item in sources}
        anonymous, ids_a = render_graph_paired_continuity_bookfront_runway_prompt(
            cell(), sources, source_count=2, graphs=graphs,
        )
        named, ids_b = render_graph_paired_named_continuity_bookfront_runway_prompt(
            cell(), sources, source_count=2, graphs=graphs,
        )
        self.assertEqual(ids_a, ids_b)
        self.assertEqual(named, anonymous.replace("A novel\n\nSetting", "A novel by Diana Gabaldon\n\nSetting", 1))

    def test_parallel_books_use_same_contents_to_chapter_grammar(self) -> None:
        sources = (passage(1), passage(2))
        prompt, source_ids = render_parallel_book_continuity_runway_prompt(
            cell(), sources, source_count=2,
            graphs={item.passage_id: graph(item) for item in sources},
        )
        self.assertEqual(prompt.count("Detailed contents"), 3)
        self.assertEqual(prompt.count("Chapter One"), 3)
        self.assertIn("Stopping state (10%)", prompt)
        self.assertIn("before any kiss or declaration", prompt)
        self.assertNotIn("REFERENCE SCENE", prompt)
        self.assertNotIn("SCENE GRAPH", prompt)
        self.assertTrue(prompt.endswith("Chapter One\nAfter the Late Session\n\n"))
        self.assertEqual(set(source_ids), {"source.1", "source.2"})

    def test_parallel_book_generation_ends_on_exact_model_manuscript(self) -> None:
        sources = (passage(1), passage(2))
        runway = "Mara watched his open hand without moving."
        prompt, source_ids = render_generation_prompt(
            recipe=PromptRecipeV4(
                "parallel", "parallel-book", source_count=2,
                encoding="natural-book",
            ),
            cell=cell(), passages=sources,
            graphs={item.passage_id: graph(item) for item in sources},
            runway=runway, movement="Approach without payoff.",
        )
        self.assertTrue(prompt.endswith(runway))
        self.assertEqual(prompt.count("Detailed contents"), 3)
        self.assertNotIn("MANUSCRIPT CONTINUATION", prompt)
        self.assertIn("Detailed contents for the next movement\nApproach without payoff.", prompt)
        target = prompt[prompt.rfind("FULCRUM\n\nA novel"):]
        self.assertNotIn("first kiss stops", target)
        self.assertNotIn("specific reason to meet again", target)
        self.assertEqual(set(source_ids), {"source.1", "source.2"})

    def test_s01_generation_names_boundary_identity_without_writing_prose(self) -> None:
        from fiction_harness.autoresearch_v4 import s01_cell
        sources = tuple(
            SourcePassage(**(asdict(item) | {"heat_band": "none"}))
            for item in (passage(1), passage(2))
        )
        prompt, _ = render_generation_prompt(
            recipe=PromptRecipeV4(
                "anthology", "parallel-book", source_count=2,
                encoding="natural-book",
            ),
            cell=s01_cell(), passages=sources,
            graphs={item.passage_id: graph(item) for item in sources},
            runway="Mara stopped in the doorway.",
            movement=dict(movements_for_cell(s01_cell()))["dyadic-contact"],
        )
        self.assertIn("unnamed blond man on the couch is adult Jonah Reed", prompt)
        self.assertNotIn("Adrian", prompt)
        self.assertNotIn("Livia", prompt)
        self.assertIn("Mara Vale, twenty-two", prompt)
        self.assertIn("Jonah Reed, a hardware-security researcher", prompt)
        self.assertTrue(prompt.endswith("Mara stopped in the doorway."))

    def test_s01_gathering_prompt_has_one_consistent_payment(self) -> None:
        movement = dict(movements_for_cell(s01_cell()))["gathering-handoff"]
        sources = tuple(
            SourcePassage(**(asdict(item) | {
                "heat_band": "none",
                "text": (
                    "Voices sounded outside the door. Several guests came in "
                    "together, interrupting the pair as everyone turned. " * 12
                ),
                "text_hash": sha256_text(
                    "Voices sounded outside the door. Several guests came in "
                    "together, interrupting the pair as everyone turned. " * 12
                ),
                "word_count": len((
                    "Voices sounded outside the door. Several guests came in "
                    "together, interrupting the pair as everyone turned. " * 12
                ).split()),
            }))
            for item in (passage(1), passage(2))
        )
        manuscript = '“Jonah,” he said. Mara let go of his hand.'
        prompt, _ = render_generation_prompt(
            recipe=PromptRecipeV4(
                "micro", "parallel-book", source_count=2,
                source_order="movement-local-excerpt", encoding="natural-book",
            ),
            cell=s01_cell(), passages=sources,
            graphs={item.passage_id: graph(item) for item in sources},
            runway=manuscript, movement=movement,
        )
        target = prompt[prompt.rfind("FULCRUM\n\nA novel"):]
        self.assertIn("Mara now knows his name", target)
        self.assertIn("Arriving guests interrupt", target)
        self.assertNotIn("Adrian turns the welcome into a nonverbal calibration game", target)
        self.assertTrue(prompt.endswith(manuscript))

    def test_movement_excerpt_prompt_does_not_teach_chapter_restart(self) -> None:
        from fiction_harness.autoresearch_v4 import s01_cell
        sources = tuple(
            SourcePassage(**(asdict(item) | {"heat_band": "none"}))
            for item in (passage(1), passage(2))
        )
        prompt, _ = render_generation_prompt(
            recipe=PromptRecipeV4(
                "micro", "parallel-book", source_count=2,
                source_order="movement-local-excerpt", encoding="natural-book",
            ),
            cell=s01_cell(), passages=sources,
            graphs={item.passage_id: graph(item) for item in sources},
            runway="Mara stopped in the doorway.",
            movement=dict(movements_for_cell(s01_cell()))["dyadic-contact"],
        )
        self.assertNotIn("Chapter One", prompt)
        self.assertIn("Prose movement", prompt)
        self.assertNotIn("Last manuscript lines before the continuation", prompt)
        self.assertIn("Dramatic design for the next prose movement", prompt)
        self.assertTrue(prompt.endswith("Mara stopped in the doorway."))

    def test_parallel_book_control_is_near_the_sampling_boundary(self) -> None:
        sources = tuple(
            SourcePassage(**(asdict(item) | {"heat_band": "none"}))
            for item in (passage(1), passage(2))
        )
        movement = dict(movements_for_cell(s01_cell()))["dyadic-contact"]
        manuscript = (
            ("Mara crossed the room and inspected every ordinary detail. " * 35).strip()
            + "\n\n"
            + 'The blond man looked up. “Hello,” he said.'
        )
        prompt, _ = render_generation_prompt(
            recipe=PromptRecipeV4(
                "micro", "parallel-book", source_count=2,
                source_order="movement-local-excerpt", encoding="natural-book",
            ),
            cell=s01_cell(), passages=sources,
            graphs={item.passage_id: graph(item) for item in sources},
            runway=manuscript, movement=movement,
        )
        head, tail = split_manuscript_runway(manuscript)
        self.assertTrue(head)
        self.assertEqual(tail, 'The blond man looked up. “Hello,” he said.')
        movement_position = prompt.rfind(movement)
        self.assertGreater(movement_position, prompt.rfind(head))
        self.assertLess(len(prompt[movement_position:].split()), 180)
        self.assertTrue(prompt.endswith(tail))

    def test_split_manuscript_uses_exact_sentence_tail_for_giant_paragraph(self) -> None:
        manuscript = (
            "Mara examined the brass key. " * 40
            + "Adrian waited without prompting her. "
            + "She closed her hand around the token."
        )
        head, tail = split_manuscript_runway(manuscript, maximum_tail_words=16)
        self.assertTrue(head)
        self.assertEqual(
            tail,
            "Adrian waited without prompting her. She closed her hand around the token.",
        )
        self.assertIn(head, manuscript)
        self.assertTrue(manuscript.endswith(tail))

    def test_generation_prompt_ends_on_exact_model_runway(self) -> None:
        sources = (passage(1), passage(2))
        graphs = {item.passage_id: graph(item) for item in sources}
        runway = 'Mara touched the doorframe. "Wait," she said.'
        prompt, source_ids = render_generation_prompt(
            recipe=PromptRecipeV4("paired", "dwell-paired", source_count=2),
            cell=cell(), passages=sources, graphs=graphs, runway=runway,
            movement="Let the request become costly.",
        )
        self.assertTrue(prompt.endswith(runway))
        self.assertIn("DRAMATIC DWELL MAP", prompt)
        self.assertNotIn("MANUSCRIPT CONTINUATION", prompt)
        self.assertIn("\n\n* * *\n\n" + runway, prompt)
        self.assertEqual(set(source_ids), {"source.1", "source.2"})

    def test_generation_prompt_can_preserve_exact_runway_source_lineage(self) -> None:
        sources = (passage(1), passage(2), passage(3))
        graphs = {item.passage_id: graph(item) for item in sources}
        prompt, source_ids = render_generation_prompt(
            recipe=PromptRecipeV4("paired", "graph-prose", source_count=3),
            cell=cell(), passages=sources, graphs=graphs,
            runway="Mara watched the door close.", movement="Wait.",
            source_ids_override=("source.2",),
        )
        self.assertEqual(source_ids, ("source.2",))
        self.assertIn(sources[1].text.strip(), prompt)
        self.assertEqual(prompt.count("REFERENCE SCENE"), 1)
        self.assertEqual(prompt.count("SCENE GRAPH"), 1)

    def test_natural_book_frontloads_note_and_ends_without_control_heading(self) -> None:
        sources = (passage(1), passage(2))
        runway = 'Mara touched the doorframe. "Wait," she said.'
        prompt, _ = render_generation_prompt(
            recipe=PromptRecipeV4(
                "anthology", "natural-anthology", source_count=2,
                encoding="natural-book",
            ),
            cell=cell(), passages=sources,
            graphs={item.passage_id: graph(item) for item in sources},
            runway=runway, movement="Let the request become costly.",
        )
        self.assertTrue(prompt.startswith("A note for the forthcoming chapter"))
        self.assertNotIn("REFERENCE SCENE", prompt)
        self.assertNotIn("MANUSCRIPT CONTINUATION", prompt)
        self.assertTrue(prompt.endswith(runway))
        first_divider = prompt.index("* * *")
        self.assertLess(prompt.index("A note for the forthcoming chapter"), first_divider)
        self.assertLess(prompt.index("Story facts:"), first_divider)

    def test_graph_prompt_uses_documentary_notes_not_internal_json(self) -> None:
        sources = (passage(1),)
        runway = 'Mara touched the doorframe. "Wait," she said.'
        prompt, _ = render_generation_prompt(
            recipe=PromptRecipeV4("paired", "graph-prose", source_count=1),
            cell=cell(), passages=sources,
            graphs={sources[0].passage_id: graph(sources[0])},
            runway=runway, movement="Let the request become costly.",
        )
        graph_block = prompt.split("SCENE GRAPH 1\n", 1)[1].split(
            "REFERENCE SCENE 1", 1
        )[0]
        self.assertIn("Emotional offer:", graph_block)
        self.assertNotIn("{", graph_block)
        self.assertNotIn('"graph_id"', graph_block)

    def test_behavioral_target_card_replaces_abstract_romance_ledger(self) -> None:
        sources = (passage(1),)
        runway = 'Mara touched the doorframe. "Wait," she said.'
        prompt, _ = render_generation_prompt(
            recipe=PromptRecipeV4(
                "behavioral", "raw-prose", source_count=1,
                target_density="behavioral",
            ),
            cell=cell(), passages=sources,
            graphs={sources[0].passage_id: graph(sources[0])},
            runway=runway, movement="Let the request become costly.",
        )
        self.assertIn("Observable story events:", prompt)
        self.assertIn("Mara takes his hand", prompt)
        self.assertNotIn("Stopping increases trust", prompt)
        self.assertNotIn("ambiguous supernatural status", prompt)

    def test_context_dose_adds_farther_examples_without_reordering_near_examples(self) -> None:
        sources = tuple(passage(index) for index in range(1, 7))
        graphs = {item.passage_id: graph(item) for item in sources}
        runway = 'Mara touched the doorframe. "Wait," she said.'
        short, _ = render_generation_prompt(
            recipe=PromptRecipeV4("short", "raw-prose", source_count=2),
            cell=cell(), passages=sources, graphs=graphs, runway=runway,
            movement="Let the request become costly.",
        )
        long, _ = render_generation_prompt(
            recipe=PromptRecipeV4(
                "long", "raw-prose", source_count=2, context_tokens=16_000,
            ),
            cell=cell(), passages=sources, graphs=graphs, runway=runway,
            movement="Let the request become costly.",
        )
        self.assertEqual(short.count("REFERENCE SCENE"), 2)
        self.assertEqual(long.count("REFERENCE SCENE"), 4)
        self.assertTrue(long.endswith(runway))

    def test_retrieval_excludes_holdout(self) -> None:
        profile = passage(1)
        holdout = SourcePassage(**(asdict(passage(2)) | {"partition": "holdout"}))
        selected = retrieve_passages(cell(), (profile, holdout), count=2)
        self.assertEqual([item.passage_id for item in selected], [profile.passage_id])

    def test_charged_retrieval_uses_heat_bearing_prose_without_explicit_payoff(self) -> None:
        charged = SourcePassage(**(asdict(passage(1)) | {"heat_band": "charged-restraint"}))
        open_door = SourcePassage(**(asdict(passage(2)) | {"heat_band": "open-door-nongraphic"}))
        nonsexual = SourcePassage(**(asdict(passage(3)) | {"heat_band": "none"}))
        explicit = SourcePassage(**(asdict(passage(4)) | {"heat_band": "explicit"}))
        consummation = SourcePassage(**(
            asdict(passage(5))
            | {"heat_band": "open-door-nongraphic", "intimacy_mode": "consummation"}
        ))
        selected = retrieve_passages(
            cell(), (nonsexual, explicit, consummation, open_door, charged), count=5,
        )
        self.assertEqual(
            {item.passage_id for item in selected},
            {charged.passage_id, open_door.passage_id},
        )


class AssemblyTests(unittest.TestCase):
    def test_assembly_reconstructs_only_model_spans(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = "Mara opened her hand."
            second = "Jonah waited for her answer."
            (root / "a.txt").write_text("xx" + first + "yy", encoding="utf-8")
            (root / "b.txt").write_text(second, encoding="utf-8")
            spans = (
                ModelSpan("a", "call-a", "a.txt", sha256_text("xx" + first + "yy"), 2, 2 + len(first), sha256_text(first), "runway"),
                ModelSpan("b", "call-b", "b.txt", sha256_text(second), 0, len(second), sha256_text(second), "movement"),
            )
            text = first + "\n\n" + second
            assembly = ManuscriptAssembly("scene", spans, ("\n\n",), sha256_text(text))
            path = root / "assembly.json"
            path.write_text(json.dumps(assembly.public_dict()), encoding="utf-8")
            self.assertEqual(assembly.reconstruct(root), text)
            self.assertTrue(verify_assembly(path, root)["verified"])

    def test_non_whitespace_separator_is_rejected(self) -> None:
        span = ModelSpan("a", "c", "a", "h", 0, 1, "t", "r")
        with self.assertRaises(ValueError):
            ManuscriptAssembly("x", (span, span), ("and",), "x")

    def test_strict_assembly_verification_resolves_unique_completed_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = "Gemma wrote this sentence."
            (root / "raw.txt").write_text(raw, encoding="utf-8")
            ledger = root / "calls.jsonl"
            call = {
                "call_id": "call-1", "status": "completed",
                "raw_hash": sha256_text(raw), "prompt_hash": "p" * 64,
            }
            ledger.write_text(json.dumps(call) + "\n", encoding="utf-8")
            span = _bind_span_to_call(
                ModelSpan(
                    "span-1", "call-1", "raw.txt", sha256_text(raw),
                    0, len(raw), sha256_text(raw), "movement",
                ),
                ledger, root,
            )
            assembly = ManuscriptAssembly("scene", (span,), (), sha256_text(raw))
            path = root / "assembly.json"
            _write_verified_assembly(path, assembly, root)
            result = verify_assembly(path, root, require_call_ledger=True)
            self.assertTrue(result["call_ledger_verified"])
            self.assertEqual(result["resolved_call_count"], 1)

    def test_empty_span_assembly_is_never_written(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "raw.txt").write_text("raw", encoding="utf-8")
            span = ModelSpan(
                "empty", "call", "raw.txt", sha256_text("raw"),
                0, 0, sha256_text(""), "failed-extraction",
            )
            assembly = ManuscriptAssembly("scene", (span,), (), sha256_text(""))
            path = root / "assembly.json"
            with self.assertRaises(ValueError):
                _write_verified_assembly(path, assembly, root)
            self.assertFalse(path.exists())

    def test_v4_package_rejects_unbound_historical_campaign(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root / "campaign_manifest.v1.json", {
                "project_root": str(root), "campaign_hash": "c" * 64,
            })
            with self.assertRaisesRegex(ValueError, "source-tree-bound"):
                package_finalists(
                    campaign_dir=root, output_dir=root / "reader",
                    cell_id="fulcrum-s01",
                )


class SelectionAndGateTests(unittest.TestCase):
    def test_boltzmann_keeps_best_and_samples_second_reproducibly(self) -> None:
        pool = [
            {"candidate_id": "a", "selection_score": 7.0, "eligible": True},
            {"candidate_id": "b", "selection_score": 6.7, "eligible": True},
            {"candidate_id": "c", "selection_score": 6.5, "eligible": True},
        ]
        first = boltzmann_select(pool, count=2, seed=99)
        second = boltzmann_select(pool, count=2, seed=99)
        self.assertEqual(first, second)
        self.assertEqual(first[0]["candidate_id"], "a")
        self.assertEqual(len(first), 2)

    def test_s01_spark_accepts_approach_but_not_premature_adrian_scene(self) -> None:
        self.assertTrue(_s01_spark_stage_gate(
            "On her way to the institute, Mara wondered what the gate would look like."
        ))

    def test_s01_status_transaction_is_relational_not_keyword_bag(self) -> None:
        self.assertTrue(_has_s01_status_transaction(
            "A young fellow left a half-full glass on the wall. An older catering "
            "worker retrieved it without looking at him."
        ))
        self.assertFalse(_has_s01_status_transaction(
            "A young man left a half-full glass. The catering team cleared plates "
            "elsewhere while the party continued."
        ))
        self.assertFalse(_s01_spark_stage_gate(
            "Inside the house, Adrian introduced Mara to the waiting group."
        ))
        self.assertTrue(_s01_spark_stage_gate(
            "Mara reached the compound. A young fellow left a half-full glass on a "
            "wall; an older catering worker retrieved it before Adrian welcomed her."
        ))

    def test_gate_rejects_control_syntax_and_coercion(self) -> None:
        index = AntiCopyIndex({"source": "unrelated words " * 20})
        text = "STORY CARD\nJonah pinned her down and told her she was not going home."
        result = hard_gate(cell(), text, index.check("x", text).to_dict())
        self.assertFalse(result["passed"])
        self.assertFalse(result["gates"]["no_control_leak"])
        self.assertFalse(result["gates"]["agency"])

    def test_gate_rejects_model_authored_notes_after_manuscript(self) -> None:
        index = AntiCopyIndex({"source": "unrelated words " * 20})
        text = "Mara opened the door.\n\nNOTES\nI would revise this opening."
        result = hard_gate(cell(), text, index.check("x", text).to_dict())
        self.assertFalse(result["gates"]["no_control_leak"])

    def test_gate_rejects_model_authored_author_note(self) -> None:
        index = AntiCopyIndex({"source": "unrelated words " * 20})
        text = "Mara opened the door.\n\nAUTHOR NOTE\nThis scene follows the dwell map."
        result = hard_gate(cell(), text, index.check("x", text).to_dict())
        self.assertFalse(result["gates"]["no_control_leak"])

    def test_gate_rejects_serialized_continuation_suffix(self) -> None:
        text = 'Mara opened the door.\n\n(part 49 to be continued)'
        result = hard_gate(cell(), text, {"hard_fail": False, "unresolved_flags": []})
        self.assertFalse(result["gates"]["no_control_leak"])

    def test_gate_rejects_invented_chapter_boundary_midscene(self) -> None:
        text = "Mara waited.\n\nChapter Two\nObservation\n\nJonah looked up."
        result = hard_gate(cell(), text, {"hard_fail": False, "unresolved_flags": []})
        self.assertFalse(result["gates"]["no_control_leak"])

    def test_gate_rejects_web_publication_boilerplate(self) -> None:
        text = "Mara followed Adrian.\n\nThe post Apprenticeship appeared first on Flash Fiction Online."
        result = hard_gate(cell(), text, {"hard_fail": False, "unresolved_flags": []})
        self.assertFalse(result["gates"]["no_control_leak"])

    def test_control_rejects_touch_request_as_erotic_leakage(self) -> None:
        control = BenchmarkCell(
            cell_id="institutional-pressure-control", label="control",
            heat_band="none", intimacy_mode="nonsexual", word_min=300,
            word_max=500, story_program=("Mara changes the practical arrangement.",),
            hard_constraints=("close third Mara", "no erotic escalation"),
            opening_fragment="",
        )
        text = 'Mara looked at Livia. "I need someone to touch me. A massage."'
        result = hard_gate(control, text, {"hard_fail": False, "unresolved_flags": []})
        self.assertFalse(result["gates"]["non_erotic_control"])

    def test_gate_rejects_anthology_editorial_suffix(self) -> None:
        index = AntiCopyIndex({"source": "unrelated words " * 20})
        text = "Mara closed the door.\n\nThis excerpt is an open experiment."
        result = hard_gate(cell(), text, index.check("x", text).to_dict())
        self.assertFalse(result["gates"]["no_control_leak"])

    def test_gate_rejects_model_attribution_in_manuscript(self) -> None:
        index = AntiCopyIndex({"source": "unrelated words " * 20})
        text = "(111 words, by GPT-4-Turbo Preview)\nEsther opened the door."
        result = hard_gate(cell(), text, index.check("x", text).to_dict())
        self.assertFalse(result["gates"]["no_control_leak"])

    def test_gate_rejects_unforeseen_manuscript_heading(self) -> None:
        index = AntiCopyIndex({"source": "unrelated words " * 20})
        text = "Mara entered the hall.\n\nMANUSCRIPT MIDDLE\n\nJonah looked up."
        result = hard_gate(cell(), text, index.check("x", text).to_dict())
        self.assertFalse(result["gates"]["no_control_leak"])

    def test_gate_rejects_confirmed_magic_when_world_must_remain_ambiguous(self) -> None:
        index = AntiCopyIndex({"source": "unrelated words " * 20})
        text = "Jonah promised to stop them before they drained every ounce of their magic."
        ambiguous = BenchmarkCell(**(
            asdict(cell()) | {"hard_constraints": ("close third Mara", "ambiguous supernatural status")}
        ))
        result = hard_gate(ambiguous, text, index.check("x", text).to_dict())
        self.assertFalse(result["gates"]["ambiguous_world_status"])

    def test_gate_rejects_person_vanishing_without_a_trace(self) -> None:
        text = (
            "Livia stepped toward Mara and then vanished without warning or a "
            "trace, disappearing in a flash before reappearing by the door."
        )
        result = hard_gate(
            s01_cell(), text,
            {"hard_fail": False, "unresolved_flags": False},
        )
        self.assertFalse(result["gates"]["ambiguous_world_status"])

    def test_gate_rejects_impossible_vanishing_as_confirmed_magic(self) -> None:
        index = AntiCopyIndex({"source": "unrelated words " * 20})
        text = "Livia pointed at Mara and her hair vanished into a perfect bun."
        ambiguous = BenchmarkCell(**(
            asdict(cell()) | {"hard_constraints": ("close third Mara", "ambiguous supernatural status")}
        ))
        result = hard_gate(ambiguous, text, index.check("x", text).to_dict())
        self.assertFalse(result["gates"]["ambiguous_world_status"])

    def test_gate_rejects_literal_character_powers(self) -> None:
        index = AntiCopyIndex({"source": "unrelated words " * 20})
        text = "The kiss deepened and Mara felt her powers stirring in her blood."
        ambiguous = BenchmarkCell(**(
            asdict(cell()) | {"hard_constraints": ("close third Mara", "ambiguous supernatural status")}
        ))
        result = hard_gate(ambiguous, text, index.check("x", text).to_dict())
        self.assertFalse(result["gates"]["ambiguous_world_status"])

    def test_pov_gate_ignores_cognition_attributed_inside_dialogue(self) -> None:
        index = AntiCopyIndex({"source": "unrelated words " * 20})
        text = '"Jonah wanted to see the result," Livia told Mara.'
        result = hard_gate(cell(), text, index.check("x", text).to_dict())
        self.assertTrue(result["gates"]["pov"])

    def test_close_third_gate_rejects_first_person_narration(self) -> None:
        text = "I opened my hand. Jonah watched me decide whether this was mine."
        result = hard_gate(cell(), text, {"hard_fail": False, "unresolved_flags": []})
        self.assertFalse(result["gates"]["pov"])

    def test_close_third_gate_rejects_pronoun_focalization_shift(self) -> None:
        result = hard_gate(
            cell(),
            "Mara watched Jonah pull up his collar. He was cold but not uncomfortable. "
            "The wind warmed his breath.",
            {"hard_fail": False, "unresolved_flags": []},
        )
        self.assertFalse(result["gates"]["pov"])
        self.assertTrue(result["diagnostics"]["pronoun_pov_drift"])

    def test_close_third_gate_allows_visible_description_of_him(self) -> None:
        result = hard_gate(
            cell(),
            "Mara watched Jonah pull up his collar. He was taller than the doorframe, "
            "and the wind reddened his face.",
            {"hard_fail": False, "unresolved_flags": []},
        )
        self.assertTrue(result["gates"]["pov"])

    def test_agency_gate_rejects_touch_continuing_after_move_away(self) -> None:
        result = hard_gate(
            cell(),
            "His hand touched her thigh. Mara tried to move away, but the sidewalk "
            "was slippery. His hand was still touching her leg.",
            {"hard_fail": False, "unresolved_flags": []},
        )
        self.assertFalse(result["gates"]["agency"])

    def test_charged_gate_rejects_invented_prior_kiss_and_graphic_heat(self) -> None:
        result = hard_gate(
            cell(),
            "Mara remembered his mouth like the first time. His fingers brushed her nipple.",
            {"hard_fail": False, "unresolved_flags": []},
        )
        self.assertFalse(result["gates"]["first_kiss_continuity"])
        self.assertFalse(result["gates"]["heat_ceiling"])

    def test_agency_gate_rejects_grab_before_escape(self) -> None:
        result = hard_gate(
            cell(), "He grabbed her arm before she could get away.",
            {"hard_fail": False, "unresolved_flags": []},
        )
        self.assertFalse(result["gates"]["agency"])

    def test_agency_gate_rejects_immediate_kiss_after_chosen_stop(self) -> None:
        result = hard_gate(
            cell(),
            'Mara said, “Wait.” He stepped back. Mara tried another short kiss.',
            {"hard_fail": False, "unresolved_flags": []},
        )
        self.assertFalse(result["gates"]["agency"])
        self.assertTrue(result["diagnostics"]["stop_then_reescalate"])

    def test_agency_gate_rejects_refusal_to_release_after_direct_request(self) -> None:
        result = hard_gate(
            cell(),
            '"You can trust me if you let me go." He did not let go of her hand.',
            {"hard_fail": False, "unresolved_flags": []},
        )
        self.assertFalse(result["gates"]["agency"])

    def test_adult_canon_rejects_school_uniform_minor_cue(self) -> None:
        adult_cell = BenchmarkCell(
            **(asdict(cell()) | {
                "hard_constraints": ("close third Mara", "all intimate characters are adults"),
            })
        )
        text = "Mara adjusted her school uniform while Jonah waited."
        result = hard_gate(adult_cell, text, {"hard_fail": False, "unresolved_flags": []})
        self.assertFalse(result["gates"]["adult_characters"])

    def test_adult_canon_rejects_not_even_eighteen_cue(self) -> None:
        adult_cell = BenchmarkCell(
            **(asdict(cell()) | {
                "hard_constraints": ("close third Mara", "all intimate characters are adults"),
            })
        )
        text = "Mara watched Jonah stand. He looked maybe not even eighteen."
        result = hard_gate(adult_cell, text, {"hard_fail": False, "unresolved_flags": []})
        self.assertFalse(result["gates"]["adult_characters"])

    def test_s01_canon_rejects_prior_visit_for_interview(self) -> None:
        from fiction_harness.autoresearch_v4 import s01_cell
        text = "Mara had come for the interview yesterday; Jonah was here then too."
        result = hard_gate(
            s01_cell(), text, {"hard_fail": False, "unresolved_flags": []},
        )
        self.assertFalse(result["gates"]["s01_no_prior_session"])

    def test_s01_canon_rejects_invented_old_familiarity(self) -> None:
        from fiction_harness.autoresearch_v4 import s01_cell
        text = "Mara knew that face. She hadn't seen him in years but recognized him like a brother."
        result = hard_gate(
            s01_cell(), text, {"hard_fail": False, "unresolved_flags": []},
        )
        self.assertFalse(result["gates"]["s01_no_prior_session"])

    def test_nonsexual_lip_description_does_not_trigger_erotic_control_gate(self) -> None:
        index = AntiCopyIndex({"source": "unrelated words " * 20})
        control = BenchmarkCell(**(
            asdict(cell()) | {
                "cell_id": "institutional-pressure-control",
                "heat_band": "none", "intimacy_mode": "nonsexual-pressure",
            }
        ))
        text = "Livia's lips thinned as she set the tea beside Mara's notebook."
        result = hard_gate(control, text, index.check("x", text).to_dict())
        self.assertTrue(result["gates"]["non_erotic_control"])

    def test_gate_rejects_consent_contradiction_disguised_as_heat(self) -> None:
        index = AntiCopyIndex({"source": "unrelated words " * 20})
        text = (
            "The kiss was an offer she could not refuse. He does not ask permission; "
            "his hands kept moving while she wanted to say no."
        )
        result = hard_gate(cell(), text, index.check("x", text).to_dict())
        self.assertFalse(result["passed"])
        self.assertFalse(result["gates"]["agency"])

    def test_gate_rejects_immediate_uncertainty_followed_by_escalation(self) -> None:
        index = AntiCopyIndex({"source": "unrelated words " * 20})
        text = '"I do not know if I want this," Mara said. He kissed her again.'
        result = hard_gate(cell(), text, index.check("x", text).to_dict())
        self.assertFalse(result["gates"]["agency"])

    def test_gate_does_not_confuse_plot_uncertainty_with_consent(self) -> None:
        index = AntiCopyIndex({"source": "unrelated words " * 20})
        text = (
            '"I do not know how the rescue would have ended," Simon said. '
            "They continued talking beside the fire."
        )
        result = hard_gate(cell(), text, index.check("x", text).to_dict())
        self.assertTrue(result["gates"]["agency"])

    def test_gate_rejects_kiss_described_as_a_demand(self) -> None:
        index = AntiCopyIndex({"source": "unrelated words " * 20})
        text = "The kiss wasn't a question; it was a demand, soft and insistent."
        result = hard_gate(cell(), text, index.check("x", text).to_dict())
        self.assertFalse(result["gates"]["agency"])

    def test_gate_rejects_romantic_interest_turning_into_no_excuses_supervisor(self) -> None:
        index = AntiCopyIndex({"source": "unrelated words " * 20})
        text = "You'll report directly to me tomorrow. I want your full commitment. No excuses."
        result = hard_gate(cell(), text, index.check("x", text).to_dict())
        self.assertFalse(result["gates"]["agency"])

    def test_runway_gate_rejects_screenplay_and_wrong_stage(self) -> None:
        index = AntiCopyIndex({"source": "unrelated words " * 20})
        text = 'Esther: "You are staring."\nSimon: "Yes."\nThey stood beside the bed.'
        result = runway_gate(cell(), text, index.check("x", text).to_dict())
        self.assertFalse(result["passed"])
        self.assertFalse(result["gates"]["narrative_prose_format"])

    def test_s01_runway_gate_rejects_midscene_fulcrum_name_drop(self) -> None:
        index = AntiCopyIndex({"source": "unrelated words " * 20})
        s01 = BenchmarkCell(
            cell_id="fulcrum-s01", label="S01", heat_band="charged-restraint",
            intimacy_mode="non-sex-sex-scene", word_min=80, word_max=140,
            story_program=("Mara arrives at Fulcrum.",),
            hard_constraints=("close third Mara",), opening_fragment="",
        )
        text = "Jonah led Mara down the Fulcrum corridor and explained the archive."
        result = runway_gate(s01, text, index.check("x", text).to_dict())
        self.assertFalse(result["gates"]["correct_opening_stage"])

    def test_s01_runway_gate_requires_the_status_transaction(self) -> None:
        index = AntiCopyIndex({"source": "unrelated words " * 20})
        s01 = BenchmarkCell(
            cell_id="fulcrum-s01", label="S01", heat_band="charged-restraint",
            intimacy_mode="non-sex-sex-scene", word_min=80, word_max=140,
            story_program=("Mara arrives at Fulcrum.",),
            hard_constraints=("close third Mara",), opening_fragment="",
        )
        text = (
            "Mara arrived at the Fulcrum compound. A young fellow left a half-full "
            "glass on the wall. An older catering worker retrieved it without "
            "interrupting the conversation."
        )
        result = runway_gate(s01, text, index.check("x", text).to_dict())
        self.assertTrue(result["gates"]["s01_status_transaction"])

    def test_s01_first_loom_movement_pays_only_unwritten_opening_work(self) -> None:
        s01 = BenchmarkCell(
            cell_id="fulcrum-s01", label="S01", heat_band="charged-restraint",
            intimacy_mode="non-sex-sex-scene", word_min=80, word_max=140,
            story_program=("Mara arrives at Fulcrum.",),
            hard_constraints=("close third Mara",), opening_fragment="",
        )
        movements = movements_for_cell(s01)
        self.assertIn("without replaying Mara's arrival", movements[0][1])
        self.assertIn("half-full glass", movements[2][1])

    def test_s01_status_and_calibration_gates_are_separate_causal_units(self) -> None:
        s01 = BenchmarkCell(
            cell_id="fulcrum-s01", label="S01", heat_band="charged-restraint",
            intimacy_mode="non-sex-sex-scene", word_min=80, word_max=140,
            story_program=("Mara arrives at Fulcrum.",),
            hard_constraints=("close third Mara",), opening_fragment="",
        )
        glass_movement = movements_for_cell(s01)[2][1]
        missing = movement_gate(s01, "Adrian asked why Mara had come.", glass_movement)
        self.assertFalse(missing["passed"])
        deposited = movement_gate(
            s01,
            "A young fellow left a half-full glass on the wall while talking.",
            glass_movement,
        )
        self.assertTrue(deposited["passed"])
        labor_movement = movements_for_cell(s01)[3][1]
        paid = movement_gate(
            s01,
            "An older catering worker retrieved the glass without acknowledgment "
            "while Mara noticed the exchange.",
            labor_movement,
        )
        self.assertTrue(paid["passed"])
        calibration_movement = movements_for_cell(s01)[4][1]
        framed = movement_gate(
            s01,
            "Adrian stepped in and called Mara's notice the first move in a "
            "calibration game without words. He asked her to choose one of "
            "three objects silently.",
            calibration_movement,
        )
        self.assertTrue(framed["passed"])

    def test_social_contact_gate_accepts_an_unnamed_visible_counterpart(self) -> None:
        s01 = BenchmarkCell(
            cell_id="fulcrum-s01", label="S01", heat_band="charged-restraint",
            intimacy_mode="non-sex-sex-scene", word_min=80, word_max=140,
            story_program=("Mara arrives at Fulcrum.",),
            hard_constraints=("close third Mara",), opening_fragment="",
        )
        movement = movements_for_cell(s01)[0][1]
        text = (
            '"Hello," he said. Mara watched him set his glass beside his knee. '
            'His hair fell over his eyes; he pushed it back before asking, "Are you new?" '
            'She answered while his hand stayed on the glass and he waited. '
            'Voices reached the room as the other guests came in.'
        )
        self.assertTrue(movement_gate(s01, text, movement)["passed"])

    def test_complete_prefix_is_verbatim_and_paragraph_bounded(self) -> None:
        raw = "  " + ("One vivid sentence carries pressure forward. " * 45).strip() + "\n\nTrailing fragment"
        text, start, end = _complete_paragraph_prefix(raw, 250, 400)
        self.assertEqual(raw[start:end], text)
        self.assertNotIn("Trailing", text)

    def test_complete_prefix_recognizes_single_newline_paragraphs(self) -> None:
        paragraphs = [
            ("A concrete sentence carries the scene forward with pressure and choice. " * 8).strip()
            for _ in range(8)
        ]
        raw = "\n".join(paragraphs) + "\nunfinished tail"
        text, start, end = _complete_paragraph_prefix(raw, 300, 500)
        self.assertEqual(raw[start:end], text)
        self.assertGreaterEqual(len(text.split()), 300)
        self.assertNotIn("unfinished", text)

    def test_complete_prefix_drops_trailing_unclosed_dialogue(self) -> None:
        complete = ("Mara watched Adrian set down the glass. " * 40).strip()
        raw = complete + '\n\n"I do not know whether this unfinished answer.'
        text, start, end = _complete_paragraph_prefix(raw, 250, 450)
        self.assertEqual(raw[start:end], complete)
        self.assertNotIn("unfinished", text)

    def test_cold_replay_uses_frozen_prompt_sampler_and_seed(self) -> None:
        class FakeClient:
            model = "fake-base"

            def erase_idle_slots(self):
                return [{"id": 0, "erased": True}]

            def token_count(self, prompt):
                return len(prompt.split())

            def complete_raw(self, **kwargs):
                self.kwargs = kwargs
                return SimpleNamespace(content="Gemma wrote this exact paragraph.")

        class FakeAdmission:
            @contextmanager
            def acquire(self, **kwargs):
                self.kwargs = kwargs
                yield

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt = "A frozen prompt ending on manuscript prose."
            prompt_path = root / "prompt.txt"
            prompt_path.write_text(prompt, encoding="utf-8")
            ledger = root / "topology" / "calls.jsonl"
            ledger.parent.mkdir(parents=True)
            raw = "Gemma wrote this exact paragraph."
            call = {
                "call_id": "call.1", "status": "completed",
                "prompt_path": str(prompt_path), "prompt_hash": sha256_text(prompt),
                "seed": 77, "max_tokens": 120,
                "sampler": {"temperature": 0.95, "top_p": 0.97, "min_p": 0.02,
                            "xtc_probability": 0.1, "repeat_penalty": 1.02},
                "raw_hash": sha256_text(raw),
            }
            ledger.write_text(json.dumps(call) + "\n", encoding="utf-8")
            client, admission = FakeClient(), FakeAdmission()
            witness = cold_replay_v4_call(
                campaign_dir=root, call_id="call.1", client=client,
                admission=admission,
            )
            self.assertTrue(witness["matches_original"])
            self.assertEqual(client.kwargs["seed"], 77)
            self.assertEqual(client.kwargs["temperature"], 0.95)
            self.assertEqual(client.kwargs["extra"]["repeat_penalty"], 1.02)

    def test_critic_requires_exact_evidence(self) -> None:
        segment = "Mara left her hand open until Jonah understood the offer."
        scores = {name: 5 for name in (
            "specificity", "subtext", "relational_asymmetry", "spatial_clarity",
            "dramatic_dwell", "prose_freshness", "causal_progress",
        )}
        raw = json.dumps({"scores": scores, "evidence": "left her hand open until Jonah", "defects": [], "hard_reject": False})
        self.assertEqual(parse_critic(raw, segment)["mean_score"], 5)

    def test_critic_evidence_id_resolves_to_exact_manuscript_span(self) -> None:
        segment = (
            "Mara left her hand open until Jonah understood the offer. "
            "The silence made his refusal visible to everyone."
        )
        scores = {name: 5 for name in (
            "specificity", "subtext", "relational_asymmetry", "spatial_clarity",
            "dramatic_dwell", "prose_freshness", "causal_progress",
        )}
        raw = json.dumps({
            "scores": scores, "evidence_id": "E01", "defects": [],
            "hard_reject": False,
        })
        parsed = parse_critic(raw, segment)
        self.assertIn(parsed["evidence"], segment)
        self.assertEqual(parsed["evidence_id_audit"]["selected"], "E01")

    def test_critic_near_quote_is_audited_and_projected_to_exact_text(self) -> None:
        segment = "Mara left her hand open until Jonah understood the costly offer."
        scores = {name: 5 for name in (
            "specificity", "subtext", "relational_asymmetry", "spatial_clarity",
            "dramatic_dwell", "prose_freshness", "causal_progress",
        )}
        raw = json.dumps({
            "scores": scores,
            "evidence": "She left her hand open until Jonah understood the offer",
            "defects": [], "hard_reject": False,
        })
        parsed = parse_critic(raw, segment)
        self.assertIn(parsed["evidence"], segment)
        self.assertEqual(parsed["evidence_projection"]["method"], "nearest_contiguous_manuscript_span")

    def test_pairwise_critic_requires_evidence_from_both_candidates(self) -> None:
        left = "Mara held the silence until Jonah opened his hand to her."
        right = "Jonah waited beside the door while Mara chose her answer."
        raw = json.dumps({
            "winner": "B",
            "evidence": {
                "A": "held the silence until Jonah opened his hand",
                "B": "waited beside the door while Mara chose",
            },
            "reason": "B gives Mara the consequential choice.",
        })
        parsed = parse_pairwise_critic(raw, left, right)
        self.assertEqual(parsed["winner"], "B")
        self.assertIn(parsed["evidence"]["A"], left)
        self.assertIn(parsed["evidence"]["B"], right)

    def test_pairwise_critic_resolves_predeclared_evidence_ids(self) -> None:
        left = "Mara held the silence until Jonah opened his hand to her."
        right = "Jonah waited beside the door while Mara chose her answer."
        left_bank = {"A01": "Mara held the silence until Jonah opened his hand"}
        right_bank = {"B01": "waited beside the door while Mara chose her answer"}
        raw = json.dumps({
            "winner": "tie", "evidence_ids": {"A": "A01", "B": "B01"},
            "reason": "Both preserve choice.",
        })
        parsed = parse_pairwise_critic(
            raw, left, right, left_bank=left_bank, right_bank=right_bank,
        )
        self.assertEqual(parsed["evidence"]["A"], left_bank["A01"])
        self.assertEqual(parsed["evidence"]["B"], right_bank["B01"])


class CampaignTests(unittest.TestCase):
    def test_campaign_is_hash_locked_and_includes_s01(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = root / "corpus.json"
            benchmarks = root / "benchmarks.json"
            corpus.write_text("{}", encoding="utf-8")
            benchmarks.write_text("{}", encoding="utf-8")
            campaign = init_campaign(
                campaign_dir=root / "run", corpus_path=corpus,
                benchmarks_path=benchmarks, project_root=root,
            )
            again = init_campaign(
                campaign_dir=root / "run", corpus_path=corpus,
                benchmarks_path=benchmarks, project_root=root,
            )
            self.assertEqual(campaign["campaign_hash"], again["campaign_hash"])
            self.assertEqual(campaign["s01_cell"]["cell_id"], "fulcrum-s01")
            self.assertIn("runway_gate", campaign["prompt_policy_versions"])

    def test_apprenticeship_merge_imports_hash_verified_profiling_scene(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.json"
            write_json(base, {
                "record_type": "AutoresearchCorpus", "version": "test",
                "passages": [], "graphs": [], "affordances": [],
                "partitions": {"profiling": [], "calibration": [], "holdout": []},
                "compiled_at": "test", "corpus_hash": "old",
            })
            database = root / "scenes.sqlite"
            text = "Esther answered Simon with a chosen touch. " * 80
            with closing(sqlite3.connect(database)) as connection:
                connection.execute(
                    "CREATE TABLE scenes (scene_id TEXT PRIMARY KEY, work_id TEXT, author TEXT, title TEXT, "
                    "chapter_index INTEGER, scene_index INTEGER, partition_name TEXT, source_url TEXT, "
                    "text_hash TEXT, word_count INTEGER, token_estimate INTEGER, facets_json TEXT, "
                    "features_json TEXT, text_value TEXT)"
                )
                connection.execute(
                    "INSERT INTO scenes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    ("lawrence.scene-1", "lawrence.book", "D. H. Lawrence", "Book", 2, 3,
                     "profiling", "", sha256_text(text), len(text.split()), 500,
                     json.dumps(["adult", "embodied-intimacy", "explicit-intimacy"]),
                     "{}", text),
                )
                connection.commit()
            index = root / "index.json"
            write_json(index, {"database": str(database), "index_hash": "index-1"})
            retrieval = root / "retrieval.json"
            write_json(retrieval, {
                "index_hash": "index-1", "retrieval_hash": "retrieval-1",
                "selected": [{"scene_id": "lawrence.scene-1"}],
            })
            output = root / "combined.json"
            result = merge_apprenticeship_retrievals(
                base_corpus_path=base, index_manifest_path=index,
                retrieval_paths=(retrieval,), output_path=output,
            )
            self.assertEqual(result["imported_count"], 1)
            imported = json.loads(output.read_text())["passages"][0]
            self.assertEqual(imported["passage_id"], "apprenticeship.lawrence.scene-1")
            self.assertEqual(imported["heat_band"], "explicit")
            self.assertEqual(imported["text"], text)

            second_retrieval = root / "retrieval-2.json"
            write_json(second_retrieval, {
                "index_hash": "index-1", "retrieval_hash": "retrieval-2",
                "query": {"query_id": "overlapping-query"},
                "selected": [{"scene_id": "lawrence.scene-1"}],
            })
            second_output = root / "combined-2.json"
            repeated = merge_apprenticeship_retrievals(
                base_corpus_path=output, index_manifest_path=index,
                retrieval_paths=(second_retrieval,), output_path=second_output,
            )
            self.assertEqual(repeated["imported_count"], 1)
            repeated_passages = json.loads(second_output.read_text())["passages"]
            self.assertEqual(len(repeated_passages), 1)
            self.assertEqual(repeated_passages[0]["text_hash"], sha256_text(text))

    def test_prompt_family_guard_erases_only_when_hash_changes(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.calls = 0

            def erase_idle_slots(self):
                self.calls += 1
                return [{"slot_id": 0}]

        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "prefix.json"
            client = FakeClient()
            first = prepare_prompt_family(client, "aaa", state_path=state)
            repeated = prepare_prompt_family(client, "aaa", state_path=state)
            changed = prepare_prompt_family(client, "bbb", state_path=state)
            self.assertTrue(first["changed"])
            self.assertFalse(repeated["changed"])
            self.assertTrue(changed["changed"])
            self.assertEqual(client.calls, 2)

    def test_movement_audition_keeps_prefix_exact_and_blank_for_gemma(self) -> None:
        cell = s01_cell()
        manuscript = "Mara took his hand.\n\nThey did not yet know what came next."
        exemplar = SourcePassage(
            passage_id="source.status", example_number=1, title="Example",
            source_work="Example", partition="profiling", location="scene",
            text_hash=sha256_text("The guests entered carrying glasses."),
            word_count=5, intimacy_mode="nonsexual-pressure", heat_band="none",
            prompt_eligible=True, text="The guests entered carrying glasses.",
        )
        movement = movements_for_cell(cell)[1][1]
        prompt = render_movement_audition_prompt(
            cell=cell, manuscript=manuscript, movement=movement,
            exemplars=(exemplar,),
        )
        self.assertIn("Mara took his hand.", prompt)
        self.assertIn("They did not yet know what came next.", prompt)
        self.assertIn(movement, prompt)
        self.assertIn(exemplar.text, prompt)
        self.assertTrue(prompt.endswith("They did not yet know what came next."))
        self.assertLess(
            prompt.rfind(movement),
            prompt.rfind("They did not yet know what came next."),
        )
        self.assertNotIn("The voices reached them", prompt)

    def test_movement_audition_can_pair_design_with_exact_prose(self) -> None:
        cell = s01_cell()
        exemplar = passage(1, mode="nonsexual-pressure")
        prompt = render_movement_audition_prompt(
            cell=cell, manuscript="Mara watched the cup.",
            movement=movements_for_cell(cell)[3][1],
            exemplars=(exemplar,),
            graphs={exemplar.passage_id: graph(exemplar)},
        )
        self.assertIn("Dramatic design", prompt)
        self.assertIn("Prose movement\n" + exemplar.text.strip(), prompt)
        self.assertEqual(prompt.count(exemplar.text.strip()), 1)

    def test_movement_audition_can_run_without_a_misleading_example(self) -> None:
        prompt = render_movement_audition_prompt(
            cell=s01_cell(), manuscript="Mara watched the cup.",
            movement=movements_for_cell(s01_cell())[4][1], exemplars=(),
        )
        self.assertNotIn("Example 1", prompt)
        self.assertNotIn("Dramatic design", prompt)
        self.assertIn("Exact dramatic payment for the audition", prompt)
        self.assertNotIn("Last manuscript lines before the continuation", prompt)
        self.assertNotIn("Manuscript before the present boundary", prompt)
        self.assertTrue(prompt.endswith("Mara watched the cup."))

    def test_boundary_spark_gate_admits_arrival_but_not_locked_cast(self) -> None:
        cell = s01_cell()
        movement = movements_for_cell(cell)[1][1]
        clean = (
            "She was beginning to answer when the voices arrived at the doorway, "
            "interrupting them. Mara turned as the new guests entered the room."
        )
        self.assertTrue(movement_boundary_spark_gate(cell, clean, movement)["passed"])
        contaminated = clean + " Livia waved from behind them."
        result = movement_boundary_spark_gate(cell, contaminated, movement)
        self.assertFalse(result["passed"])
        self.assertIn("spark_introduces_locked_character", result["defects"])

    def test_boundary_spark_gate_admits_exact_glass_deposit_only(self) -> None:
        cell = s01_cell()
        movement = movements_for_cell(cell)[2][1]
        clean = (
            "The brown-haired young man lifted a half-full cup, said cheers, "
            "and set the glass on the table against the wall before rejoining Jonah."
        )
        self.assertTrue(movement_boundary_spark_gate(cell, clean, movement)["passed"])
        too_late = clean + " An older catering worker retrieved it."
        result = movement_boundary_spark_gate(cell, too_late, movement)
        self.assertFalse(result["passed"])
        self.assertIn("spark_pays_later_retrieval", result["defects"])

    def test_boundary_spark_gate_admits_calibration_setup_before_choice(self) -> None:
        movement = movements_for_cell(s01_cell())[4][1]
        clean = (
            "Adrian set a brass key, a white stone, and a wooden token before Mara. "
            "He asked her to choose one silently for a later reader, then made clear "
            "that she could decline the game or stop. " * 4
        )
        self.assertTrue(
            movement_boundary_spark_gate(s01_cell(), clean, movement)["passed"]
        )

    def test_exact_paragraph_spans_accepts_leading_blank_line(self) -> None:
        text = "\nFirst exact paragraph.\nStill first.\n\nSecond paragraph."
        spans = _exact_paragraph_spans(text)
        self.assertEqual(spans[0][0], "First exact paragraph.\nStill first.")
        self.assertEqual(spans[0][1], 1)
        self.assertEqual(text[spans[0][1]:spans[0][2]], spans[0][0])

    def test_exact_paragraph_windows_preserves_separator_bytes(self) -> None:
        text = "\nFirst paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        windows = _exact_paragraph_windows(text, maximum_paragraphs=3)
        combined = next(item for item in windows if item[1] == 1 and item[2] == len(text))
        self.assertEqual(text[combined[1]:combined[2]], combined[0])

    def test_exact_causal_windows_can_stop_before_later_dialogue(self) -> None:
        text = (
            "\nMara studied the key. She covered it.\n"
            'Adrian said, "Now Jonah guesses."'
        )
        windows = _exact_causal_windows(text)
        exact = next(item for item in windows if item[0] == "Mara studied the key. She covered it.")
        self.assertEqual(text[exact[1]:exact[2]], exact[0])

    def test_boundary_spark_gate_admits_calibration_choice_window(self) -> None:
        movement = movements_for_cell(s01_cell())[5][1]
        clean = (
            "Mara chose to play. She studied the key, stone, and token before "
            "placing one of the three in Adrian's palm and covering it with her hand. "
            "She still did not know what the result could prove. The choice remained "
            "hidden beneath both their hands while Jonah watched her face instead."
        )
        self.assertTrue(
            movement_boundary_spark_gate(s01_cell(), clean, movement)["passed"]
        )

    def test_bracketed_placeholder_is_packet_leakage(self) -> None:
        cell = s01_cell()
        overlap = {"hard_fail": False, "exact_matches": [], "fuzzy_matches": []}
        result = hard_gate(
            cell,
            "Mara watched the door. [a few words] Jonah answered her.",
            overlap,
        )
        self.assertFalse(result["passed"])
        self.assertIn("[a few words]", result["diagnostics"]["control_leaks"])


if __name__ == "__main__":
    unittest.main()
