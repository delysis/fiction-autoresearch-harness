from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from fiction_harness.anti_copy import AntiCopyIndex, SourceOverlapError
from fiction_harness.continuation import (
    ApprovedPrefix,
    BASE_PROSE_SENTINEL,
    BASE_S02_OPENING_FRAGMENT,
    BASE31_PLAN_MODE,
    BASE_PROGRAM_MODE,
    CHAT_DIRECT_MODE,
    CHAT_PLANNED_MODE,
    GENERATION_MODES,
    NATIVE_BASE_MODE,
    NATIVE_BASE_PLANNED_MODE,
    S02_MACRO_SEQUENCES,
    VERBALIZED_MODE,
    adjudicate_verbalized_plan_set,
    base_story_program_proposal_prompt,
    base_generation_context,
    base_sequence_prompt,
    compact_story_packet,
    clean_generated_prose,
    context_manifest,
    continuation_gates,
    generation_story_packet,
    judge_and_lock_verbalized_plans,
    load_approved_prefix,
    packet_word_count,
    parse_story_proposals,
    parse_verbalized_plan_judgments,
    prepare_continuation_context,
    raw_sequence_prompt,
    realization_story_program,
    realization_story_program_for_sequence,
    render_compact_packet,
    render_generation_packet,
    literary_scene_spec,
    select_diverse_story_programs,
    _budgeted_macro_sequence,
    _base_continue_short_sequence_prompt,
    _canonical_realization_instruction,
    _compress_sequence_prompt,
    _model_call,
    _sentence_bounded_prefix,
    _sequence_endpoint_satisfied,
    _ordered_beat_findings,
    _prose_has_complete_ending,
    _repeated_signature_passages,
    _strategy_as_program,
    validate_story_program,
    require_packet_clean_prose,
    sequence_checkpoint_diagnostics,
    verbalized_story_program_messages,
    verbalized_plan_judge_messages,
    with_locked_s02_plan_contract,
    write_locked_plan_set,
)
from fiction_harness.cli import _context_prompt_exemplars, _load_story_programs
from fiction_harness.core import hash_json, sha256_text
from fiction_harness.feedback import HumanFeedbackBrief
from fiction_harness.pipelines import VerbalizedStrategy
from fiction_harness.runtime import TraceStore
from fiction_harness.schemas import Candidate, PersonaPacket, SceneSpec


ROOT = Path(__file__).resolve().parents[1]
S01_ROOT = ROOT / "03_scene_lab" / "runs" / "s01-comparison-v1"
S02_COMPILED = ROOT / "03_scene_lab" / "compiled" / "s02-v1-ontology"


def _feedback(winner: str = "B") -> HumanFeedbackBrief:
    return HumanFeedbackBrief(
        package_id="test-package",
        source_kind="human",
        response_ids=("friend-01",),
        coverage={"A": 1, "B": 1, "C": 0},
        pairwise={"wins": {"A": 0, "B": 1, "C": 0}},
        rating_medians={
            "A": {"desire_to_continue": 4, "romantic_pull": 4, "trust": 4},
            "B": {"desire_to_continue": 6, "romantic_pull": 6, "trust": 6},
            "C": {"desire_to_continue": 0, "romantic_pull": 0, "trust": 0},
        },
        winner_label=winner,
        strengths={"A": (), "B": ("Keep the charged restraint.",), "C": ()},
        defects={"A": (), "B": ("Avoid long abstract explanation.",), "C": ()},
        desired_next={"A": (), "B": ("Let Mara say a clean no.",), "C": ()},
        fail_fast=False,
        created_at="2026-07-28T00:00:00+00:00",
    )


def _scene() -> SceneSpec:
    return SceneSpec(
        scene_id="S02",
        title="The Doorway Rule",
        function="First boundary",
        pov="Mara",
        target_words_min=2_800,
        target_words_max=3_600,
        opening_image="The door closes.",
        desire="Mara wants truth and freedom.",
        obstacle="Concern becomes coercion.",
        pressure_ladder=("fatigue", "concern", "threat"),
        turn="Mara asks whether no is data or decision.",
        aftermath="Jonah walks her home.",
        teaching_payload="Authority protects refusal.",
        source_ids=("MPC-02",),
        beat_map=tuple(f"Beat {index}" for index in range(1, 10)),
        continuity_facts=("No consummation.",),
        heat_ceiling="No graphic anatomy.",
    )


def _personas() -> tuple[PersonaPacket, ...]:
    return (
        PersonaPacket(
            persona_id="mara_vale",
            name="Mara Vale",
            version="1",
            role="protagonist",
            age=22,
            invariants=("Sheltered and competent.",),
            false_beliefs=("Uncertainty forfeits authority.",),
            attention_habits=("Notices pace.",),
            relationship_variants={"jonah_reed": ("Trusts protected freedom.",)},
        ),
    )


def _v4_program(*, forbidden: str = "No consummation occurs.") -> str:
    return "\n".join(
        (
            "TITLE: The Cost of Leaving",
            "ANTAGONIST TRUTH: Livia accurately sees Mara's hunger to belong, but mistakes perception for jurisdiction.",
            "PROTAGONIST ERROR: Mara overexplains her uncertainty and gives the group more material with which to delay her.",
            "EXIT AGENCY: Mara refuses the next exercise and places her own chair beside the open door, changing the room's choices.",
            "PROTECTOR COST: Miriam protects Mara's exit and risks her board seat by naming the session's procedural breach.",
            "LOVER COST: Jonah walks Mara home and admits that his earlier silence protected his status at her expense.",
            "INSTITUTIONAL CONSEQUENCE: Fulcrum leadership freezes the cohort's access badges and opens a contested incident review.",
            "UNCANNY REMAINDER: A door-camera timestamp records Mara outside before the session's visible exit.",
            "SEQUENCE ONE: Livia offers precise care, names Mara's belonging hunger correctly, and turns that truth into a demand for disclosure. Mara's explanations deepen the trap.",
            "SEQUENCE TWO: Mara notices that the question assumes consent, refuses the exercise, moves her chair, and makes an exit possible before Miriam backs her.",
            "SEQUENCE THREE: Miriam accepts public cost. Jonah walks Mara home, confesses his failure, and asks rather than assumes. Mara chooses a kiss; they stop while desire remains and agree that either may say enough without penalty.",
            "RELATIONSHIP DELTA: Mara trusts Jonah more because his restraint includes confession and cost, while keeping judgment of him open.",
            f"HARD END STATES: Mara freely returns to investigate the timestamp. {forbidden}",
        )
    )


class ContinuationContextTests(unittest.TestCase):
    def test_conditioning_exemplar_keeps_declared_source_identity(self) -> None:
        payload = {
            "conditioning_material": [
                {"source_id": "book.scene-7", "text": "A bounded excerpt."}
            ]
        }
        self.assertEqual(
            _context_prompt_exemplars(payload),
            {"prompt-exemplar:book.scene-7": "A bounded excerpt."},
        )

    def test_final_sequence_instruction_ends_on_scene_not_interpretive_coda(self) -> None:
        instruction = _canonical_realization_instruction(S02_MACRO_SEQUENCES[-1])
        self.assertIn("action, dialogue, an object", instruction)
        self.assertIn("not Mara explaining what she realized", instruction)

    def test_real_context_is_bounded_and_uses_full_feedback_winner(self) -> None:
        values = prepare_continuation_context(
            compiled_dir=S02_COMPILED,
            finalists_path=S01_ROOT / "evaluation" / "finalists.json",
            reveal_key_path=S01_ROOT / "internal" / "reveal_key.json",
            feedback_path=(
                S01_ROOT
                / "appraisal"
                / "round1-feedback"
                / "bootstrap_feedback_brief.v1.json"
            ),
        )
        scene, _, profile, _, feedback, prefix, packet, rendered = values
        self.assertEqual(scene.scene_id, "S02")
        self.assertEqual(prefix.label, feedback.winner_label)
        self.assertEqual(prefix.label, "B")
        self.assertLessEqual(packet_word_count(packet), 6_000)
        self.assertEqual(packet["approved_prefix"]["full_text"], prefix.text)
        self.assertNotIn("BISAC", rendered)
        self.assertNotIn("https://", rendered)
        manifest = context_manifest(
            packet=packet,
            rendered=rendered,
            scene=scene,
            profile=profile,
            feedback=feedback,
            approved_prefix=prefix,
        )
        self.assertEqual(manifest["approved_prefix_hash"], prefix.text_hash)
        self.assertEqual(len(manifest["macro_sequences"]), 3)

    def test_prefix_hash_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            finalists = {
                "finalists": [
                    {"candidate_id": "x", "text": "immutable text"}
                ]
            }
            reveal = {
                "labels": {
                    "A": {"candidate_id": "x", "text_sha256": "0" * 64},
                    "B": {"candidate_id": "x", "text_sha256": "0" * 64},
                    "C": {"candidate_id": "x", "text_sha256": "0" * 64},
                }
            }
            (root / "finalists.json").write_text(json.dumps(finalists))
            (root / "reveal.json").write_text(json.dumps(reveal))
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                load_approved_prefix(
                    finalists_path=root / "finalists.json",
                    reveal_key_path=root / "reveal.json",
                    feedback_brief=_feedback("A"),
                )

    def test_prompt_hides_final_ending_until_sequence_three(self) -> None:
        program = (
            "ANTAGONIST TRUTH: Livia sees Mara's fear.\n"
            "PROTAGONIST ERROR: Mara answers too much.\n"
            "EXIT AGENCY: Mara opens the record.\n"
            "PROTECTOR COST: Miriam loses her office.\n"
            "LOVER COST: Jonah loses access.\n"
            "INSTITUTIONAL CONSEQUENCE: Fulcrum loses the room.\n"
            "UNCANNY REMAINDER: An offline camera has one extra frame.\n"
            "SEQUENCE ONE: Care makes silence expensive.\n"
            "SEQUENCE TWO: Mara opens the record.\n"
            "SEQUENCE THREE: They stop the doorway kiss.\n"
            "LOCKED END STATES: Mara authors the next meeting."
        )
        prompt = raw_sequence_prompt(
            compact_prefix="<context>stable</context>",
            scene=_scene(),
            sequence=S02_MACRO_SEQUENCES[0],
            completed_text="",
            program=program,
        )
        self.assertIn("Do not write, hint, summarize", prompt)
        self.assertNotIn("doorway kiss", prompt)
        self.assertNotIn("Jonah loses access", prompt)
        self.assertNotIn("locally intelligent", prompt)
        self.assertNotIn("remaining-beat-ledger", prompt)
        final_prompt = raw_sequence_prompt(
            compact_prefix="<context>stable</context>",
            scene=_scene(),
            sequence=S02_MACRO_SEQUENCES[2],
            completed_text="prior",
            program=program,
        )
        self.assertIn("doorway kiss", final_prompt)

    def test_native_base_prompt_has_no_chat_envelope(self) -> None:
        prefix = "Earlier paragraph.\n\nThe accepted scene ends in this voice."
        prompt = base_sequence_prompt(
            compact_prefix=(
                "<continuation-context><scene-state><beats>future kiss</beats>"
                "<continuity>future walk</continuity><desire>leave freely</desire>"
                "</scene-state><accepted-story-continuity><use>not prose</use>"
                "</accepted-story-continuity></continuation-context>"
            ),
            scene=_scene(),
            sequence=S02_MACRO_SEQUENCES[0],
            completed_text="",
            program=(
                "ANTAGONIST TRUTH: Livia sees Mara's fear of appearing ungrateful.\n"
                "PROTAGONIST ERROR: Mara answers a private question to preserve status.\n"
                "EXIT AGENCY: Mara places her recorder in the open.\n"
                "PROTECTOR COST: Miriam stakes her authority on the refusal.\n"
                "LOVER COST: Jonah names an earlier failure.\n"
                "INSTITUTIONAL CONSEQUENCE: the session record becomes contested.\n"
                "UNCANNY REMAINDER: a stopped clock advances once.\n"
                "SEQUENCE ONE: The offered water makes declining harder.\n"
                "SEQUENCE TWO: Mara makes the observation public.\n"
                "SEQUENCE THREE: Miriam opens the door.\n"
                "LOCKED END STATES: Mara chooses the next meeting."
            ),
            approved_prefix_text=prefix,
        )
        self.assertNotIn("<|turn>", prompt)
        self.assertTrue(prompt.endswith(BASE_S02_OPENING_FRAGMENT))
        self.assertIn(prefix, prompt)
        self.assertIn("The offered water makes declining harder.", prompt)
        self.assertNotIn("Miriam opens the door.", prompt)
        self.assertNotIn("future kiss", prompt)
        self.assertNotIn("not prose", prompt)
        self.assertNotIn("locally intelligent", prompt)
        self.assertNotIn("the trap", prompt.casefold())
        self.assertNotIn("s02-seq", prompt)
        self.assertNotIn("Care becomes a trap", prompt)

    def test_native_base_prompt_requires_real_manuscript_runway(self) -> None:
        with self.assertRaisesRegex(ValueError, "approved manuscript prefix"):
            base_sequence_prompt(
                compact_prefix="<continuation-context />",
                scene=_scene(),
                sequence=S02_MACRO_SEQUENCES[0],
                completed_text="",
            )

    def test_base_sequence_program_projection_hides_later_solutions(self) -> None:
        program = (
            "ANTAGONIST TRUTH: Livia sees Mara's fear.\n"
            "PROTAGONIST ERROR: Mara answers too much.\n"
            "EXIT AGENCY: Mara makes the record public.\n"
            "PROTECTOR COST: Miriam risks her office.\n"
            "LOVER COST: Jonah names his failure.\n"
            "INSTITUTIONAL CONSEQUENCE: the board intervenes.\n"
            "UNCANNY REMAINDER: the dead clock moves.\n"
            "SEQUENCE ONE: care narrows the choices.\n"
            "SEQUENCE TWO: Mara changes the room.\n"
            "SEQUENCE THREE: the doorway kiss stops.\n"
            "LOCKED END STATES: Mara authors the next meeting."
        )
        first = realization_story_program_for_sequence(
            program, S02_MACRO_SEQUENCES[0]
        )
        self.assertIn("care narrows the choices", first)
        self.assertNotIn("doorway kiss", first)
        self.assertNotIn("Miriam risks", first)
        final = realization_story_program_for_sequence(
            program, S02_MACRO_SEQUENCES[2]
        )
        self.assertIn("doorway kiss", final)
        self.assertIn("Jonah names his failure", final)

    def test_base_short_repair_ends_on_exact_manuscript_tail(self) -> None:
        prompt = _base_continue_short_sequence_prompt(
            compact_prefix="<continuation-context>must vanish</continuation-context>",
            sequence=S02_MACRO_SEQUENCES[0],
            prose="Mara set down the glass.",
            missing_words=200,
        )
        self.assertNotIn("must vanish", prompt)
        self.assertTrue(
            prompt.endswith("Mara set down the glass.\n" + BASE_PROSE_SENTINEL)
        )

    def test_packet_leakage_is_a_hard_failure(self) -> None:
        with self.assertRaisesRegex(ValueError, "prompt-packet material"):
            require_packet_clean_prose(
                "Good prose.\n## Locked story state\n<continuation-context>",
                call_id="test-call",
            )
        with self.assertRaisesRegex(ValueError, "prompt-packet material"):
            require_packet_clean_prose(
                "## Final words\nThe story has reached its conclusion. "
                "The syntax has become appropriately final.",
                call_id="editorial-meta",
            )
        self.assertEqual(
            require_packet_clean_prose("Mara kept the door open.", call_id="ok"),
            "Mara kept the door open.",
        )
        with self.assertRaisesRegex(ValueError, "SOURCE MATERIAL"):
            require_packet_clean_prose(
                "Finished prose.\n\n# SOURCE MATERIAL\nnotes",
                call_id="source-material-leak",
            )
        with self.assertRaisesRegex(ValueError, "serialized-control-xml"):
            require_packet_clean_prose(
                "<id>austen.error</id><strength>0.9</strength>"
                "<item>not fiction</item>",
                call_id="mid-packet-fragment",
            )

    def test_sequence_checkpoint_exposes_stock_and_control_language(self) -> None:
        prose = (
            "The air was thick with doubt. Livia's small practical kindness "
            "met a need Mara had concealed. And that was a start."
        )
        result = sequence_checkpoint_diagnostics(
            prose,
            program="",
            sequence=S02_MACRO_SEQUENCES[0],
        )
        self.assertIn("air_thick_with", result["stock_prose_hits"])
        self.assertIn("that_was_a_start", result["stock_prose_hits"])
        self.assertGreater(
            result["control_phrase_overlap"]["unique_match_count"], 0
        )

    def test_base_generation_context_removes_future_and_fake_bridge(self) -> None:
        compact = (
            "<continuation-context><author-conditioning>"
            "<author-profile-hash>secret-hash</author-profile-hash>"
            "<prompt-payload><affordances><item>"
            "<activation-conditions><item>metadata</item></activation-conditions>"
            "<creative-obligations><item>Use consequential detail.</item>"
            "</creative-obligations><id>author.secret</id><strength>0.9</strength>"
            "</item></affordances><conditioning-material><item>"
            "<source-id>author.book.scene</source-id><text>Sample prose.</text>"
            "</item></conditioning-material><negative-space><item>do not imitate</item>"
            "</negative-space></prompt-payload></author-conditioning>"
            "<scene-state><pressure-ladder><item>x</item>"
            "</pressure-ladder><beats><item>kiss</item></beats>"
            "<desire>freedom</desire></scene-state>"
            "<accepted-story-continuity><use>fake bridge</use>"
            "</accepted-story-continuity></continuation-context>"
        )
        projected = base_generation_context(compact)
        self.assertIn("freedom", projected)
        self.assertNotIn("kiss", projected)
        self.assertNotIn("fake bridge", projected)
        self.assertIn("Use consequential detail", projected)
        self.assertIn("fiction-craft", projected)
        self.assertNotIn("secret-hash", projected)
        self.assertNotIn("author.secret", projected)
        self.assertNotIn("author.book.scene", projected)
        self.assertIn("Sample prose", projected)
        self.assertNotIn("activation-conditions", projected)
        self.assertNotIn("do not imitate", projected)

    def test_base31_planner_uses_document_backtranslation_without_chat_tokens(
        self,
    ) -> None:
        prompt = base_story_program_proposal_prompt(
            compact_prefix="<context>full accepted scene</context>"
        )
        self.assertNotIn("<|turn>", prompt)
        self.assertNotIn("backtranslation", prompt.casefold())
        self.assertIn("not a style model", prompt)
        self.assertIn("ANTAGONIST TRUTH", prompt)
        self.assertIn("not a cost unless", prompt)
        self.assertIn("ordinary explanation", prompt)
        self.assertIn("must author the choice", prompt)

    def test_v2_modes_include_base_and_verbalized_arms(self) -> None:
        self.assertIn(BASE_PROGRAM_MODE, GENERATION_MODES)
        self.assertIn(BASE31_PLAN_MODE, GENERATION_MODES)
        self.assertIn(VERBALIZED_MODE, GENERATION_MODES)
        self.assertIn(NATIVE_BASE_MODE, GENERATION_MODES)
        self.assertIn(NATIVE_BASE_PLANNED_MODE, GENERATION_MODES)
        self.assertIn(CHAT_PLANNED_MODE, GENERATION_MODES)
        messages = verbalized_story_program_messages(
            compact_prefix="<context>stable</context>",
            call_number=1,
        )
        rendered = "\n".join(message["content"] for message in messages)
        self.assertIn("strictly below", rendered)
        self.assertIn('"probability"', rendered)
        self.assertIn("long-tail", rendered)

    def test_raw_transport_tokens_are_removed_without_rewriting_prose(self) -> None:
        prose = "<|channel>thought\n<channel|>Mara kept the door in sight.<turn|>"
        self.assertEqual(
            clean_generated_prose(prose), "Mara kept the door in sight."
        )

    def test_packet_determinism(self) -> None:
        prefix = ApprovedPrefix(
            label="B",
            candidate_id="b",
            text="Some approved prose.",
            text_hash=sha256_text("Some approved prose."),
        )
        profile = {
            "heat_target": "high",
            "heat_ceiling": "nongraphic",
            "atmosphere": "late",
            "pacing": [],
            "prompt_obligations": [],
            "prohibited": [],
        }
        source = {
            "cards": [
                {
                    "source_id": "MPC-02",
                    "evidence_or_dynamic": "space before choice",
                    "dramatic_use": "Mara pauses.",
                    "source": "must not leak",
                }
            ]
        }
        left = compact_story_packet(
            scene=_scene(),
            personas=_personas(),
            profile=profile,
            source_packet=source,
            feedback=_feedback(),
            approved_prefix=prefix,
        )
        right = compact_story_packet(
            scene=_scene(),
            personas=_personas(),
            profile=profile,
            source_packet=source,
            feedback=_feedback(),
            approved_prefix=prefix,
        )
        self.assertEqual(render_compact_packet(left), render_compact_packet(right))
        self.assertNotIn("must not leak", render_compact_packet(left))

    def test_generation_view_keeps_audit_prefix_but_omits_the_full_scene(self) -> None:
        prefix_text = " ".join(f"word-{index}" for index in range(900))
        prefix = ApprovedPrefix(
            label="B",
            candidate_id="b",
            text=prefix_text,
            text_hash=sha256_text(prefix_text),
        )
        packet = compact_story_packet(
            scene=_scene(),
            personas=_personas(),
            profile={"heat_ceiling": "nongraphic", "prohibited": []},
            source_packet={"cards": []},
            feedback=_feedback(),
            approved_prefix=prefix,
        )
        rendered = render_generation_packet(packet)
        self.assertEqual(packet["approved_prefix"]["full_text"], prefix_text)
        self.assertNotIn("word-1<", rendered)
        self.assertNotIn("word-899", rendered)
        self.assertIn(prefix.text_hash, rendered)
        self.assertIn("state-bridge", rendered)
        self.assertNotIn("reader-feedback", rendered)

    def test_generation_view_omits_author_surface_statistics(self) -> None:
        packet = {
            "author_conditioning": {
                "author_profile_hash": "a" * 64,
                "prompt_payload": {
                    "affordances": [{"id": "dialogue.indirect-action"}],
                    "negative_space": ["No milieu imitation."],
                    "distributions": {
                        "semicolon_per_1000": {"mean": 13.4}
                    },
                },
            },
            "approved_prefix": {"id": "p", "hash": "h", "full_text": "x"},
            "story_contract": {},
            "scene": {},
            "characters": [],
            "mechanisms": [],
            "selected_profile": {},
        }
        generation = generation_story_packet(packet)
        payload = generation["author_conditioning"]["prompt_payload"]
        self.assertIn("affordances", payload)
        self.assertNotIn("distributions", payload)

    def test_generation_view_routes_only_scene_active_mechanisms(self) -> None:
        packet = {
            "approved_prefix": {"id": "p", "hash": "h", "full_text": "x"},
            "story_contract": {},
            "scene": {},
            "characters": [],
            "mechanisms": [
                {"id": "MPC-04", "mechanism": "A pause restores choice."},
                {"id": "LEV-04", "mechanism": "Posture can become evidence."},
                {"id": "MPC-02", "mechanism": "A stream-and-banks abstraction."},
                {"id": "MPC-19", "mechanism": "A later-scene forgiveness rule."},
            ],
            "selected_profile": {},
        }
        ids = [
            item["id"]
            for item in generation_story_packet(packet)["observable_mechanisms"]
        ]
        self.assertEqual(ids, ["MPC-04", "LEV-04"])

    def test_literary_scene_spec_preserves_state_without_scripted_wording(self) -> None:
        scene = literary_scene_spec(_scene())
        joined = " ".join(scene.beat_map + scene.continuity_facts)
        self.assertIn("substantially true", joined)
        self.assertIn("Mara herself makes exit possible", joined)
        self.assertIn("Jonah's restraint", joined)
        self.assertNotIn("data or decision", joined)
        self.assertNotIn("At 1:17", joined)


class StoryProgramTests(unittest.TestCase):
    def test_loader_uses_highest_valid_locked_plan_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = TraceStore(root / VERBALIZED_MODE)
            write_locked_plan_set(
                store=store,
                generation_mode=VERBALIZED_MODE,
                programs={22011: "TITLE: v2 audit plan"},
                source="test-v2",
                lineage={},
                manifest_version=2,
            )
            write_locked_plan_set(
                store=store,
                generation_mode=VERBALIZED_MODE,
                programs={22011: "TITLE: v3 adjudicated plan"},
                source="test-v3",
                lineage={},
                manifest_version=3,
            )
            loaded = _load_story_programs(root, (22011,), VERBALIZED_MODE)
            self.assertEqual(loaded[22011], "TITLE: v3 adjudicated plan")

    def test_loader_can_reuse_external_immutable_plan_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source" / BASE31_PLAN_MODE
            store = TraceStore(source)
            write_locked_plan_set(
                store=store,
                generation_mode=BASE31_PLAN_MODE,
                programs={22011: "TITLE: frozen high-entropy plan"},
                source="paired-ablation",
                lineage={},
                manifest_version=1,
            )
            plan_path = source / "locked_plan_set.v1.json"
            loaded = _load_story_programs(
                root / "new-run",
                (22011,),
                BASE31_PLAN_MODE,
                locked_plan_set=plan_path,
            )
            self.assertEqual(loaded[22011], "TITLE: frozen high-entropy plan")

    def test_quality_ranker_writes_separate_v2_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = TraceStore(Path(tmp))
            flavors = (
                "orchid semaphore",
                "ferry ledger",
                "violin case",
                "greenhouse key",
                "weather balloon",
                "bakery invoice",
                "museum badge",
                "railway timetable",
                "amber bottle",
                "satellite map",
                "choir roster",
                "river gauge",
                "broken compass",
                "library stamp",
                "copper bracelet",
                "observatory card",
            )
            for call_number in (1, 2):
                strategies = []
                for index in range(1, 9):
                    marker = flavors[(call_number - 1) * 8 + index - 1]
                    strategies.append(
                        {
                            "id": f"tail-{index}",
                            "title": marker,
                            "probability": 0.09 - index * 0.005,
                            "premise": f"Livia uses care through {marker}.",
                            "antagonist_truth": f"Mara wants recognition through {marker}.",
                            "protagonist_error": f"Mara conceals evidence through {marker}.",
                            "exit_agency": f"Mara publishes timestamp {call_number}-{index} herself.",
                            "protector_cost": f"Miriam loses credential {call_number}-{index}.",
                            "lover_cost": f"Jonah surrenders key {call_number}-{index}.",
                            "institutional_consequence": f"Fulcrum loses room {call_number}-{index}.",
                            "uncanny_remainder": f"Camera frame {call_number}-{index} has an ordinary alternative.",
                            "sequence_one": f"Care narrows choice in {marker}.",
                            "sequence_two": f"Mara creates the exit in {marker}.",
                            "sequence_three": f"Costs follow in {marker}.",
                            "romantic_engine": f"Attraction meets distrust in {marker}.",
                            "epistemic_turn": f"One observation changes in {marker}.",
                            "distinctive_tactics": [f"key {index}", f"frame {call_number}"],
                            "relationship_delta": f"interest -> costly trust {marker}",
                        }
                    )
                store.append_call(
                    {
                        "call_id": f"s02-vs-compact-v2-distribution-{call_number}",
                        "status": "completed",
                        "result": {"content": json.dumps({"strategies": strategies})},
                    }
                )

            class Judge:
                model = "fake-plan-judge"

                def complete_raw(self, **_: object) -> str:
                    judgments = []
                    for index in range(1, 17):
                        judgments.append(
                            {
                                "label": f"P{index:02d}",
                                "dimensions": {
                                    "dramatic_causality": 12,
                                    "character_truth": 12,
                                    "costly_agency": 12,
                                    "romantic_voltage": 10,
                                    "epistemic_restraint": 10,
                                    "prose_affordance": 8,
                                },
                                "hard_reject": False,
                                "defects": [],
                                "best_affordance": "A concrete choice changes the room.",
                                "weakest_link": "One consequence needs sharper specificity.",
                                "verdict": "Usable causal material.",
                            }
                        )
                    return json.dumps({"judgments": judgments})

            prefix = ApprovedPrefix(
                label="B",
                candidate_id="accepted",
                text="Accepted prefix.",
                text_hash=sha256_text("Accepted prefix."),
            )
            result = judge_and_lock_verbalized_plans(
                judge=Judge(),
                store=store,
                compact_prefix="<context>stable</context>",
                seeds=(22011, 22023),
                approved_prefix=prefix,
                feedback=_feedback(),
                profile_hash="profile-hash",
            )
            self.assertTrue((Path(tmp) / "locked_plan_set.v2.json").is_file())
            self.assertEqual(len(result["manifest"]["entries"]), 2)
            self.assertIn("plan_quality_report_hash", result["manifest"])
            self.assertFalse((Path(tmp) / "locked_plan_set.v1.json").exists())

            selected_ids = set(result["report"]["selected_strategy_ids"])
            title_by_id = {
                f"s02-vs-compact-v2-distribution-{call_number}:tail-{index}":
                flavors[(call_number - 1) * 8 + index - 1]
                for call_number in (1, 2)
                for index in range(1, 9)
            }
            ranked = list(result["report"]["selected_strategy_ids"])
            policy = {
                "version": "verbalized-plan-adjudication-policy.v1",
                "source_quality_report_hash": hash_json(result["report"]),
                "source_locked_plan_set_hash": result["manifest"]["plan_set_hash"],
                "decisions": [
                    {
                        "strategy_id": strategy_id,
                        "title": title_by_id[strategy_id],
                        "action": "select" if strategy_id in selected_ids else "exclude",
                        **(
                            {
                                "rank": ranked.index(strategy_id) + 1,
                                "repair_overlay": "Keep the causal choice concrete.",
                            }
                            if strategy_id in selected_ids
                            else {}
                        ),
                        "rationale": "Explicit unit-test adjudication.",
                    }
                    for strategy_id in title_by_id
                ],
            }
            adjudicated = adjudicate_verbalized_plan_set(
                store=store,
                seeds=(22011, 22023),
                policy=policy,
            )
            v3_path = Path(tmp) / "locked_plan_set.v3.json"
            self.assertTrue(v3_path.is_file())
            self.assertEqual(len(adjudicated["manifest"]["entries"]), 2)
            self.assertTrue((Path(tmp) / "plan_adjudication.v1.json").is_file())
            self.assertIn(
                "CAUSAL REPAIR",
                adjudicated["manifest"]["entries"][0]["plan"],
            )
            self.assertEqual(
                adjudicated["manifest"]["entries"][0]["sampled_payload_hash"],
                hash_json(adjudicated["manifest"]["entries"][0]["sampled_payload"]),
            )

    def test_plan_judge_parser_recomputes_total_and_requires_every_label(self) -> None:
        dimensions = {
            "dramatic_causality": 16,
            "character_truth": 17,
            "costly_agency": 15,
            "romantic_voltage": 12,
            "epistemic_restraint": 13,
            "prose_affordance": 8,
        }
        raw = json.dumps(
            {
                "judgments": [
                    {
                        "label": "P01",
                        "dimensions": dimensions,
                        "hard_reject": False,
                        "defects": ["cost_needs_specificity"],
                        "best_affordance": "Mara publishes the timestamp.",
                        "weakest_link": "Jonah only apologizes.",
                        "verdict": "Promising after one causal repair.",
                    }
                ]
            }
        )
        parsed = parse_verbalized_plan_judgments(raw, expected_labels=("P01",))
        self.assertEqual(parsed["P01"]["total_score"], 81)
        with self.assertRaisesRegex(ValueError, "omitted labels"):
            parse_verbalized_plan_judgments(raw, expected_labels=("P01", "P02"))

    def test_plan_judge_parser_rejects_boolean_evidence_contradiction(self) -> None:
        raw = json.dumps(
            {
                "judgments": [
                    {
                        "label": "P01",
                        "dimensions": {
                            "dramatic_causality": 10,
                            "character_truth": 10,
                            "costly_agency": 10,
                            "romantic_voltage": 8,
                            "epistemic_restraint": 2,
                            "prose_affordance": 7,
                        },
                        "hard_reject": False,
                        "defects": [],
                        "best_affordance": "Prayer creates a vivid turn.",
                        "weakest_link": "The temperature drop confirms supernatural causation.",
                        "verdict": "This violates a hard canon boundary.",
                    }
                ]
            }
        )
        with self.assertRaisesRegex(ValueError, "contradicts hard_reject=false"):
            parse_verbalized_plan_judgments(raw, expected_labels=("P01",))

    def test_plan_judge_prompt_calibrates_quality_before_novelty(self) -> None:
        messages = verbalized_plan_judge_messages(
            compact_prefix="<context>stable</context>",
            labeled_strategies=({"label": "P01", "plan": {"exit_agency": "Mara leaves."}},),
        )
        rendered = "\n".join(item["content"] for item in messages)
        self.assertIn("75 is strong publishable planning", rendered)
        self.assertIn("novelty alone", rendered)
        self.assertIn("not a cost unless", rendered)

    def test_realization_brief_omits_abstract_planner_conclusions(self) -> None:
        program = (
            "TITLE: A schematic title\n"
            "PREMISE: A thematic summary.\n"
            "ANTAGONIST TRUTH: Livia accurately notices Mara wants recognition.\n"
            "PROTAGONIST ERROR: Mara conceals the failed control.\n"
            "EXIT AGENCY: Mara publishes the timestamp herself.\n"
            "PROTECTOR COST: Miriam loses her observer credential.\n"
            "LOVER COST: Jonah surrenders access to the lab.\n"
            "INSTITUTIONAL CONSEQUENCE: The trial loses its scheduled venue.\n"
            "UNCANNY REMAINDER: An offline camera contains one extra frame.\n"
            "SEQUENCE ONE: Livia's accurate care becomes leverage.\n"
            "SEQUENCE TWO: Mara publishes the timestamp and leaves.\n"
            "SEQUENCE THREE: Jonah walks Mara home and loses access.\n"
            "ROMANTIC ENGINE: Shared secrecy creates attraction.\n"
            "EPISTEMIC TURN: Accuracy is not authority.\n"
            "RELATIONSHIP DELTA: interest -> trust\n"
            "LOCKED END STATES: Their kiss stops at the doorway."
        )
        brief = realization_story_program(program)
        self.assertIn("Mara publishes the timestamp herself", brief)
        self.assertIn("Their kiss stops at the doorway", brief)
        self.assertNotIn("schematic title", brief)
        self.assertNotIn("Accuracy is not authority", brief)
        self.assertNotIn("interest -> trust", brief)

    def test_verbalized_program_adds_locked_end_states_without_mutating_payload(self) -> None:
        payload = {
            "title": "The Honest Log",
            "premise": "Livia's accurate reading tempts Mara to surrender judgment.",
            "antagonist_truth": "Mara wants recognition more than she admits.",
            "protagonist_error": "Mara conceals a bad control result.",
            "exit_agency": "Mara broadcasts the camera record and opens the door.",
            "protector_cost": "Miriam risks her post by protecting Mara's exit.",
            "lover_cost": "Jonah admits that he ignored an earlier warning.",
            "institutional_consequence": "Fulcrum suspends Livia's calibration session.",
            "uncanny_remainder": "An offline camera names an unseen witness.",
            "sequence_one": "Livia's care becomes a trap for Mara.",
            "sequence_two": "Mara's concealment fails and forces her decision.",
            "sequence_three": "Mara leaves under institutional pressure.",
            "romantic_engine": "Recognition competes with earned distrust.",
            "epistemic_turn": "Accurate perception does not confer authority.",
            "distinctive_tactics": ["camera record", "public refusal"],
            "relationship_delta": "wary attraction -> costly trust",
            "probability": 0.07,
        }
        original = json.loads(json.dumps(payload))
        strategy = VerbalizedStrategy("test:tail-1", 0.07, payload, "test")
        program = _strategy_as_program(strategy)
        self.assertEqual(payload, original)
        self.assertIn("LOCKED END STATES", program)
        self.assertTrue(validate_story_program(program)["passed"])

    def test_base_plan_contract_preserves_sampled_kernel_exactly(self) -> None:
        sampled = (
            "TITLE: A Strange Cost\n"
            "ANTAGONIST TRUTH: Livia notices Mara is waiting to be chosen.\n"
            "PROTAGONIST ERROR: Mara hides a failed control and worsens the test.\n"
            "EXIT AGENCY: Mara opens the recorded session to every participant.\n"
            "PROTECTOR COST: Miriam loses her observer credential protecting Mara's exit.\n"
            "LOVER COST: Jonah admits he buried the first camera warning.\n"
            "INSTITUTIONAL CONSEQUENCE: Fulcrum loses access to its calibration room.\n"
            "UNCANNY REMAINDER: An offline camera records a second voice.\n"
            "SEQUENCE ONE: Livia's care makes Mara stay too long.\n"
            "SEQUENCE TWO: Mara releases the record and leaves.\n"
            "SEQUENCE THREE: The institution fractures around her decision.\n"
            "RELATIONSHIP DELTA: suspicion becomes costly trust.\n"
            "HARD END STATES: Mara chooses continued investigation."
        )
        derived = with_locked_s02_plan_contract(sampled)
        self.assertEqual(derived.split("\nLOCKED END STATES:", 1)[0], sampled)
        self.assertEqual(sampled.count("LOCKED END STATES"), 0)
        self.assertTrue(validate_story_program(derived)["passed"])

    def test_parse_numbered_proposals(self) -> None:
        parsed = parse_story_proposals(
            "1. Tea as leverage. Mara notices the cup.\n\n"
            "2) A broken lock. The room cannot pretend the exit is open.\n\n"
            "3: Jonah jokes once and then pays a cost."
        )
        self.assertEqual(len(parsed), 3)

        headed = parse_story_proposals(
            "ALTERNATIVE 1: First plan.\nSEQUENCE ONE:\n1. Inner event.\n\n"
            "ALTERNATIVE 2: Second plan.\nSEQUENCE ONE:\n1. Other event."
        )
        self.assertEqual(len(headed), 2)
        self.assertIn("Inner event", headed[0])
        self.assertIn("broken lock", parsed[1])

    def test_selection_is_reproducible(self) -> None:
        superficial = tuple(
            f"Plan {index} uses object {index} and a different causal turn."
            for index in range(10)
        )
        with self.assertRaisesRegex(ValueError, "causally distinct"):
            select_diverse_story_programs(superficial, count=4, seed=7)
        proposals = (
            "ANTAGONIST TRUTH: grief hidden by competence\nPROTAGONIST ERROR: deletes evidence\nEXIT AGENCY: withdraws consent\nLOVER COST: loses fellowship\nINSTITUTIONAL CONSEQUENCE: donor withdraws funding\nUNCANNY REMAINDER: offline sensor predicts the exit\nSEQUENCE ONE: Mara deletes a message.\nSEQUENCE TWO: Mara withdraws consent.\nSEQUENCE THREE: Jonah confesses and the donor calls.",
            "ANTAGONIST TRUTH: fear of public failure\nPROTAGONIST ERROR: falsely accuses Livia\nEXIT AGENCY: calls the fire marshal\nLOVER COST: reveals his leaked complaint\nINSTITUTIONAL CONSEQUENCE: faculty splits into factions\nUNCANNY REMAINDER: unplugged recorder contains a voice\nSEQUENCE ONE: Livia displays a sealed recording.\nSEQUENCE TWO: Mara calls an inspector.\nSEQUENCE THREE: Jonah admits the leak and teachers divide.",
            "ANTAGONIST TRUTH: hunger for approval\nPROTAGONIST ERROR: signs a coercive waiver\nEXIT AGENCY: triggers the building alarm\nLOVER COST: sacrifices his housing\nINSTITUTIONAL CONSEQUENCE: police seize the lab\nUNCANNY REMAINDER: a badge logs an impossible arrival\nSEQUENCE ONE: Mara signs the waiver.\nSEQUENCE TWO: Smoke makes her pull the alarm.\nSEQUENCE THREE: Jonah surrenders his key while investigators arrive.",
            "ANTAGONIST TRUTH: attraction distorts Mara's judgment\nPROTAGONIST ERROR: conceals the control result\nEXIT AGENCY: broadcasts the experiment\nLOVER COST: ends his friendship with the founder\nINSTITUTIONAL CONSEQUENCE: students publish the protocol\nUNCANNY REMAINDER: a camera names an unseen witness\nSEQUENCE ONE: Mara hides the test result.\nSEQUENCE TWO: She starts a public stream.\nSEQUENCE THREE: Jonah confronts the founder while students publish.",
        )
        first = select_diverse_story_programs(proposals, count=3, seed=7)
        second = select_diverse_story_programs(proposals, count=3, seed=7)
        self.assertEqual(first, second)
        self.assertEqual(len(set(first)), 3)

    def test_program_validation_rejects_xml_drift_and_accepts_causal_plan(self) -> None:
        self.assertFalse(
            validate_story_program(
                "<teaching>A night of emotional intimacy.</teaching>"
            )["passed"]
        )
        valid = _v4_program()
        self.assertTrue(validate_story_program(valid)["passed"])

    def test_program_validation_distinguishes_prevention_from_event(self) -> None:
        prevented = _v4_program(
            forbidden="They prevent the kiss from becoming a leap into consummation."
        )
        scheduled = _v4_program(
            forbidden="They kiss and consummate the relationship."
        )
        self.assertTrue(validate_story_program(prevented)["passed"])
        self.assertTrue(validate_story_program(scheduled)["forbidden"])


class LengthControllerTests(unittest.TestCase):
    def test_overlap_retry_advances_and_records_sampler_seed(self) -> None:
        source = (
            "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu"
        )
        safe = "A fresh sentence that shares no protected source sequence."

        class Client:
            model = "test-model"

            def __init__(self) -> None:
                self.seeds: list[int] = []

            def complete(self, **kwargs: object) -> dict[str, object]:
                seed = int(kwargs["seed"])
                self.seeds.append(seed)
                return {"content": source if len(self.seeds) == 1 else safe}

        with tempfile.TemporaryDirectory() as directory:
            store = TraceStore(Path(directory))
            client = Client()
            arguments = {
                "client": client,
                "store": store,
                "call_id": "retry-seed",
                "mode": CHAT_DIRECT_MODE,
                "prompt": "stable prompt",
                "messages": ({"role": "user", "content": "write"},),
                "seed": 17,
                "max_tokens": 64,
                "anti_copy_index": AntiCopyIndex({"source": source}),
                "lineage": {"resolved_profile_hash": "profile"},
            }
            with self.assertRaises(SourceOverlapError):
                _model_call(**arguments)
            result = _model_call(**arguments)
            self.assertEqual(result["content"], safe)
            self.assertEqual(client.seeds, [17, 100_020])
            records = TraceStore.read(store.calls_path)
            self.assertEqual(records[-1]["attempt_index"], 2)
            self.assertEqual(records[-1]["parameters"]["seed"], 100_020)

    def test_final_sequence_budget_closes_overall_hard_range(self) -> None:
        sequence = _budgeted_macro_sequence(
            sequence=S02_MACRO_SEQUENCES[2],
            remaining=(),
            completed_words=2_174,
            scene=_scene(),
        )
        self.assertEqual(sequence.minimum_words, 1_100)
        self.assertEqual(sequence.maximum_words, 1_400)
        self.assertLessEqual(
            2_174 + sequence.maximum_words,
            _scene().target_words_max,
        )

    def test_early_sequence_budget_reserves_later_minimums(self) -> None:
        sequence = _budgeted_macro_sequence(
            sequence=S02_MACRO_SEQUENCES[0],
            remaining=S02_MACRO_SEQUENCES[1:],
            completed_words=0,
            scene=_scene(),
        )
        self.assertLessEqual(
            sequence.maximum_words
            + sum(item.minimum_words for item in S02_MACRO_SEQUENCES[1:]),
            _scene().target_words_max,
        )

    def test_strict_compression_retry_carries_deletion_ledger(self) -> None:
        prose = "word " * 1_500
        prompt = _compress_sequence_prompt(
            compact_prefix="<context>stable</context>",
            sequence=S02_MACRO_SEQUENCES[2],
            prose=prose,
            strict_retry=True,
        )
        self.assertIn("<failed-compression-word-count>1500", prompt)
        self.assertIn("<minimum-words-to-delete>100", prompt)
        self.assertIn("do not replay the prior draft", prompt)

    def test_length_compliant_but_cut_off_ending_fails_endpoint_gate(self) -> None:
        cut_off = (
            "Mara stated the doorway rule and told Jonah, “You may kiss me if "
            "we would both be glad to stop.” He understood. “"
        )
        self.assertFalse(
            _sequence_endpoint_satisfied(S02_MACRO_SEQUENCES[2], cut_off)
        )

    def test_complete_doorway_ending_passes_endpoint_gate(self) -> None:
        complete = (
            "Mara named the doorway rule. He kissed her; their lips met, and "
            "they stopped while both still wanted more. She chose to return "
            "tomorrow, although Fulcrum's larger mystery remained unresolved."
        )
        self.assertTrue(
            _sequence_endpoint_satisfied(S02_MACRO_SEQUENCES[2], complete)
        )
        false_choice = (
            "Mara was told that willingness to stay proved her health. Later he "
            "kissed her; their lips met, and they stopped while both wanted more. "
            "Jonah said they needed a rule."
        )
        self.assertFalse(
            _sequence_endpoint_satisfied(S02_MACRO_SEQUENCES[2], false_choice)
        )
        imposed_future = (
            "He kissed her; their lips met, and they stopped while both wanted "
            "more. Jonah said, ‘See you tomorrow. Next time we need a rule.’"
        )
        self.assertFalse(
            _sequence_endpoint_satisfied(S02_MACRO_SEQUENCES[2], imposed_future)
        )
        vague_future = (
            "He kissed her; their lips met, and they stopped while both still "
            "wanted more. They agreed on a doorway rule. She knew she would "
            "investigate Fulcrum tomorrow, but made no choice about staying."
        )
        self.assertFalse(
            _sequence_endpoint_satisfied(S02_MACRO_SEQUENCES[2], vague_future)
        )
        breakfast_future = (
            "She kissed him; their lips met, and they stopped while both still "
            "wanted more. "
            "They agreed that saying raw would stop them so the other could ask. "
            "‘Breakfast?’ she said. ‘Seven,’ Jonah answered."
        )
        self.assertTrue(
            _sequence_endpoint_satisfied(
                S02_MACRO_SEQUENCES[2], breakfast_future
            )
        )

    def test_early_sequences_cannot_spend_the_exit(self) -> None:
        trapped = (
            "Mara looked toward the door but sat again. The monitors restarted, "
            "and the session continued with one fewer choice available to her."
        )
        self.assertTrue(
            _sequence_endpoint_satisfied(S02_MACRO_SEQUENCES[0], trapped)
        )
        escaped = (
            "Mara reached the glass door. She stood alone in the corridor, "
            "the session finally behind her."
        )
        self.assertFalse(
            _sequence_endpoint_satisfied(S02_MACRO_SEQUENCES[0], escaped)
        )
        self.assertFalse(
            _sequence_endpoint_satisfied(S02_MACRO_SEQUENCES[1], escaped)
        )

    def test_tail_rescue_keeps_a_sentence_boundary(self) -> None:
        prose = "One complete sentence. " * 200
        kept = _sentence_bounded_prefix(prose, 120)
        self.assertLessEqual(len(kept.split()), 120)
        self.assertTrue(kept.endswith("."))


class ContinuationGateTests(unittest.TestCase):
    def test_internal_signature_replay_requires_a_long_separated_match(self) -> None:
        phrase = "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen"
        repeated = phrase + " intervening words " * 20 + phrase
        self.assertTrue(_repeated_signature_passages(repeated))
        self.assertFalse(_repeated_signature_passages(phrase + " once only"))

    def test_token_cut_ending_is_never_complete(self) -> None:
        self.assertFalse(
            _prose_has_complete_ending(
                "He understood the doorway rule and leaned closer.\n\n“"
            )
        )
        self.assertFalse(
            _prose_has_complete_ending(
                "“I choose this, Mara said, and the quotation never closed."
            )
        )
        self.assertFalse(
            _prose_has_complete_ending(
                'Jonah said, "If we do this, we need a rule.'
            )
        )
        self.assertTrue(
            _prose_has_complete_ending(
                "“I choose this,” Mara said. They stopped while still glad."
            )
        )

    def test_beat_gate_accepts_trap_before_care_is_named(self) -> None:
        text = (
            "Livia brought water as care. Livia said she had watched Mara correctly, "
            "but therefore Mara must stay. Mara tried to explain until every clarification "
            "made the trap worse and left her less sure. Her throat tightened; it could "
            "mean fear or anger. Mara paused in prayer until attention returned her choice. "
            "'Is my no a data point or a decision?' Miriam opened the door to protect the "
            "exit and risked her board position in public. Jonah walked her home and "
            "confessed that his earlier silence had failed her. At the doorway their lips "
            "met; the kiss stopped while they both wanted again. She would return tomorrow. "
            "An offline camera timestamp showed her outside before she had left."
        )
        ordered, findings = _ordered_beat_findings(text)
        self.assertTrue(ordered, findings)

    def test_prefix_is_exempt_but_continuation_is_checked(self) -> None:
        prefix_text = "Approved opening prose with a distinctive sentence."
        prefix = ApprovedPrefix(
            label="B",
            candidate_id="approved",
            text=prefix_text,
            text_hash=sha256_text(prefix_text),
        )
        continuation = (
            "Livia brought tea as care. Livia said she had read Mara correctly, but "
            "therefore Mara must stay. Mara tried to explain until each clarification "
            "made the trap worse and left her less sure. Her throat tightened; it might "
            "be fear or anger. She paused in prayer until attention restored her choice. "
            "“Is no data,” Mara asked, “or is it a decision?” "
            "Miriam opened the door to protect the exit and risked her board position. "
            "Jonah walked her home and admitted his silence had failed her. "
            "He asked, she said yes, and their lips met in a kiss; they stopped, both glad. "
            "Tomorrow she would return by choice. An offline sensor log showed her exit "
            "before the door had opened, an impossible timestamp no one could explain. "
        )
        continuation += " ordinary" * 2_700
        merged = prefix_text + "\n\n" + continuation
        candidate = Candidate(
            candidate_id="c",
            run_id="r",
            pipeline="raw_organic",
            scene_id="S02",
            seed=1,
            text=merged,
            continuation_text=continuation,
            parent_trace={},
            evidence_ids=("MPC-02",),
            telemetry={},
            lineage=("call:x",),
            prompt_hash="p",
            ontology_version="rgo.v1",
            story_profile_id="story",
            scene_profile_id="scene",
            resolved_profile_hash="1" * 64,
            approved_prefix_id=prefix.approved_prefix_id,
            approved_prefix_hash=prefix.text_hash,
            feedback_brief_hash="2" * 64,
            generation_mode="raw_organic",
        )
        index = AntiCopyIndex(
            {"source": "unrelated source language never used in this continuation"}
        )
        report = continuation_gates(
            candidate,
            scene=replace(_scene(), target_words_max=3_600),
            approved_prefix=prefix,
            anti_copy_index=index,
        )
        self.assertTrue(report["gates"]["immutable_prefix"]["passed"])
        self.assertTrue(report["gates"]["anti_copy"]["passed"])
        # This synthetic sample is intentionally too short as a merged story,
        # proving that prefix exemption does not bypass the other gates.
        self.assertFalse(report["eligible"])


if __name__ == "__main__":
    unittest.main()
