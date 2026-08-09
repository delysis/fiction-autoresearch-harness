from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from fiction_harness.anti_copy import (
    AntiCopyIndex,
    SourceOverlapError,
    StreamingNgramGuard,
    build_anti_copy_index,
)
from fiction_harness.author import (
    compile_source_segments,
    draft_lead,
    render_base_writer_prompt,
    resolve_author_context,
    validate_corpus_files,
    validate_profile_against_manifest,
    validate_transformation_map,
)
from fiction_harness.author_evaluation import (
    AUTHOR_EVALUATION_AXES,
    distribution_diagnostics,
    pareto_frontier,
    parse_author_judgment,
    surface_style_metrics,
)
from fiction_harness.author_experiments import (
    calibration_design,
    full_s01_design,
    verify_shared_story_programs,
)
from fiction_harness.author_schemas import (
    AuthorAffordance,
    AuthorBook,
    AuthorCorpusManifest,
    AuthorProfile,
    StoryProgram,
    TransformationMap,
    partition_plan,
)
from fiction_harness.author_workflow import build_author_run_config
from fiction_harness.core import hash_file, hash_json
from fiction_harness.runtime import (
    MODEL_PROFILES,
    build_base_conversion_command,
    build_server_command,
)
from fiction_harness.story_program import select_story_programs
from fiction_harness.schemas import SceneSpec


DIGEST = "a" * 64


def _affordance(
    identifier: str,
    axis: str,
    *,
    books: tuple[str, ...] = ("book-a", "book-b"),
) -> AuthorAffordance:
    return AuthorAffordance(
        affordance_id=identifier,
        axis=axis,
        claim="The scene routes judgment through social observation.",
        activation_conditions=("A character risks social embarrassment.",),
        prevalence=0.7,
        strength=0.8,
        distribution={"mean": 1.0},
        evidence_refs=(f"{books[0]}.segment-0001", f"{books[-1]}.segment-0001"),
        evidence_book_ids=books,
        counterevidence_refs=(f"{books[0]}.segment-0002",),
        rgo_coordinates=("tone.comic",),
        prompt_semantics=("Make social inference alter the next choice.",),
        evaluator_semantics=("Identify the inference and changed choice.",),
        confidence=0.85,
        scope="author-signature" if len(set(books)) >= 2 else "local-tendency",
    )


def _profile(manifest: AuthorCorpusManifest) -> AuthorProfile:
    affordances = (
        _affordance("author.social-inference", "scene_causality"),
        _affordance("author.dialogue-deflection", "dialogue"),
        _affordance("author.rhythmic-qualification", "syntax_lexis"),
    )
    return AuthorProfile(
        profile_id="author.test.v1",
        author_id=manifest.author_id,
        author_name="Test Author",
        version="1.0",
        corpus_manifest_hash=manifest.corpus_hash,
        affordances=affordances,
        author_subgenre_delta=("Indirect inference carries causal weight.",),
        distributions={
            "mean_sentence_words": {"mean": 8.0, "tolerance": 4.0}
        },
        negative_space=("Avoid omniscient motive declarations.",),
    )


def _transformation(profile: AuthorProfile) -> TransformationMap:
    return TransformationMap(
        map_id="author.test.juicy.v1",
        author_profile_id=profile.profile_id,
        version="1.0",
        rules={item.affordance_id: "preserve" for item in profile.affordances},
        target_semantics={},
        target_profile_hash=DIGEST,
    )


class AuthorCorpusTests(unittest.TestCase):
    def test_partition_policy(self) -> None:
        self.assertEqual(
            partition_plan(3),
            {"profiling": 2, "calibration": 0, "holdout": 1},
        )
        self.assertEqual(
            partition_plan(5),
            {"profiling": 3, "calibration": 1, "holdout": 1},
        )

    def test_holdout_is_existence_checked_but_not_read_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            paths = {}
            for name in ("a", "b", "h"):
                path = root / f"{name}.txt"
                path.write_text(f"Chapter I\n\n{name} text " * 30, encoding="utf-8")
                paths[name] = path
            books = (
                AuthorBook(
                    "book-a", "A", "profiling", "a.txt", hash_file(paths["a"])
                ),
                AuthorBook(
                    "book-b", "B", "profiling", "b.txt", hash_file(paths["b"])
                ),
                AuthorBook("book-h", "H", "holdout", "h.txt", "0" * 64),
            )
            manifest = AuthorCorpusManifest(
                "test.v1", "test-author", "Test Author", "1.0", books
            )
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(manifest.to_dict()), encoding="utf-8"
            )
            default = validate_corpus_files(manifest_path)
            audited = validate_corpus_files(
                manifest_path, permit_holdout_read=True
            )
            self.assertTrue(default.valid)
            self.assertFalse(audited.valid)
            segments = compile_source_segments(manifest_path)
            self.assertTrue(segments)
            self.assertNotIn("book-h", {item.book_id for item, _ in segments})

    def test_profile_rejects_holdout_evidence(self) -> None:
        books = (
            AuthorBook("book-a", "A", "profiling", "a", DIGEST),
            AuthorBook("book-b", "B", "profiling", "b", DIGEST),
            AuthorBook("book-h", "H", "holdout", "h", DIGEST),
        )
        manifest = AuthorCorpusManifest(
            "test.v1", "test-author", "Test Author", "1", books
        )
        profile = _profile(manifest)
        bad = replace(
            profile,
            affordances=(
                _affordance(
                    "author.holdout-leak",
                    "dialogue",
                    books=("book-a", "book-h"),
                ),
            ),
        )
        with self.assertRaisesRegex(ValueError, "holdout leakage"):
            validate_profile_against_manifest(bad, manifest)


class PromptAndExperimentTests(unittest.TestCase):
    def setUp(self) -> None:
        books = (
            AuthorBook("book-a", "A", "profiling", "a", DIGEST),
            AuthorBook("book-b", "B", "profiling", "b", DIGEST),
            AuthorBook("book-h", "H", "holdout", "h", DIGEST),
        )
        self.manifest = AuthorCorpusManifest(
            "test.v1", "test-author", "Test Author", "1", books
        )
        self.profile = _profile(self.manifest)
        self.transformation = _transformation(self.profile)

    def test_three_prompt_views_are_deterministic_and_xml_escaped(self) -> None:
        contexts = {}
        for encoding in ("xml", "markdown", "json"):
            first = resolve_author_context(
                self.profile,
                self.transformation,
                corpus_manifest_hash=self.manifest.corpus_hash,
                prompt_encoding=encoding,
                control_density="light",
            )
            second = resolve_author_context(
                self.profile,
                self.transformation,
                corpus_manifest_hash=self.manifest.corpus_hash,
                prompt_encoding=encoding,
                control_density="light",
            )
            self.assertEqual(first.context_hash, second.context_hash)
            contexts[encoding] = first
        xml_context = contexts["xml"]
        prefix, dynamic = render_base_writer_prompt(
            creative_profile={"genre": "romance & suspense"},
            gabaldon_profile={"rule": "character < mechanics"},
            author_context=xml_context,
            story_canon={"locked": True},
            scene_input={"turn": "A > B"},
        )
        self.assertIn("&amp;", prefix)
        self.assertIn("&lt;", prefix)
        self.assertTrue(dynamic.endswith('metadata="forbidden">\n'))
        self.assertNotIn("book-a", prefix)

    def test_transformation_map_can_be_locked_to_project_profile(self) -> None:
        validate_transformation_map(
            self.profile,
            self.transformation,
            target_profile_hash=DIGEST,
        )
        with self.assertRaisesRegex(ValueError, "different creative profile"):
            validate_transformation_map(
                self.profile,
                self.transformation,
                target_profile_hash="f" * 64,
            )

    def test_canon_prose_lead_stays_below_exact_copy_threshold(self) -> None:
        lead = draft_lead(
            {
                "scene": {
                    "opening_image": (
                        "At sunset, Mara arrives at Fulcrum’s redwood compound "
                        "carrying one hard-sided suitcase and a bakery box from "
                        "her church."
                    )
                }
            }
        )
        self.assertEqual(
            lead,
            "At sunset, Mara arrived at Fulcrum’s redwood compound.\n\n",
        )
        self.assertLess(len(lead.split()), 12)

    def test_source_exposure_variants_require_explicit_bounded_material(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires explicit"):
            resolve_author_context(
                self.profile,
                self.transformation,
                corpus_manifest_hash=self.manifest.corpus_hash,
                conditioning_variant="profile-sparse-exemplars",
            )
        context = resolve_author_context(
            self.profile,
            self.transformation,
            corpus_manifest_hash=self.manifest.corpus_hash,
            conditioning_variant="profile-sparse-exemplars",
            conditioning_material=(
                {
                    "source_id": "book-a.segment-1",
                    "text": "A bounded public-domain excerpt.",
                },
            ),
        )
        self.assertEqual(
            context.prompt_payload["conditioning_material"][0]["source_id"],
            "book-a.segment-1",
        )

    def test_calibration_and_full_design_share_story_programs(self) -> None:
        arms = calibration_design(
            graph_ids=("g1", "g2"), seeds=(1, 2, 3, 4)
        )
        self.assertEqual(len(arms), 120)
        self.assertTrue(
            verify_shared_story_programs([arm.to_dict() for arm in arms])[
                "passed"
            ]
        )
        full = full_s01_design(
            winning_encoding="xml",
            winning_variants=("anonymous-profile", "named-profile"),
            story_program_ids=tuple(f"p{i}" for i in range(8)),
            seeds=tuple(range(8)),
        )
        self.assertEqual(len(full), 32)

    def test_base_server_has_no_chat_template_and_conversion_is_exact(self) -> None:
        profile = MODEL_PROFILES["base_writer"]
        command = build_server_command(profile, port=9999)
        self.assertNotIn("--jinja", command)
        self.assertNotIn("--reasoning", command)
        convert = build_base_conversion_command(
            "base_writer", python_path=Path("/tmp/python")
        )
        self.assertEqual(convert[-2:], ["--outtype", "q8_0"])


class AntiCopyTests(unittest.TestCase):
    def test_exact_twelve_word_match_hard_fails_and_stream_aborts(self) -> None:
        source = (
            "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu "
            "nu xi omicron"
        )
        index = AntiCopyIndex({"book-a.s1": source})
        report = index.check("candidate", source)
        self.assertTrue(report.hard_fail)
        guard = StreamingNgramGuard(index)
        with self.assertRaises(SourceOverlapError):
            for word in source.split():
                guard.feed(word + " ")

    def test_whitelist_and_cross_candidate_detection_are_separate(self) -> None:
        phrase = "one two three four five six seven eight nine ten eleven twelve"
        index = AntiCopyIndex({"source": phrase + " thirteen"}, whitelist=(phrase,))
        candidate_phrase = (
            "amber birch cedar dogwood elm fir gingko hazel ironwood juniper "
            "kapok larch maple nutmeg oak pine"
        )
        report = index.check(
            "c2",
            candidate_phrase,
            prior_candidates={"c1": candidate_phrase},
        )
        self.assertFalse(report.exact_matches)
        self.assertTrue(report.cross_candidate_matches)

    def test_prompt_exemplars_are_independently_indexed(self) -> None:
        exemplar = (
            "violet willow xenia yarrow zephyr amber bronze copper dahlia "
            "ember flint garnet"
        )
        index = build_anti_copy_index(
            author_documents={"author": "one two three four"},
            prompt_exemplars={"example": exemplar},
            project_sources={"canon": "five six seven eight"},
        )
        report = index.check("candidate", exemplar)
        self.assertTrue(report.hard_fail)
        self.assertEqual(
            report.exact_matches[0]["source_ids"],
            ["example"],
        )
        categories = {
            source["source_id"]: source["category"]
            for source in index.manifest()["sources"]
        }
        self.assertEqual(categories["example"], "prompt-exemplar")


class AuthorEvaluationTests(unittest.TestCase):
    def test_surface_metrics_and_distribution_are_transparent(self) -> None:
        books = (
            AuthorBook("book-a", "A", "profiling", "a", DIGEST),
            AuthorBook("book-b", "B", "profiling", "b", DIGEST),
            AuthorBook("book-h", "H", "holdout", "h", DIGEST),
        )
        manifest = AuthorCorpusManifest(
            "test.v1", "test-author", "Test Author", "1", books
        )
        profile = _profile(manifest)
        text = '“Come here,” Mara said. She waited; he did not move.'
        metrics = surface_style_metrics(text)
        diagnostic = distribution_diagnostics(text, profile)
        self.assertGreater(metrics["dialogue_word_ratio"], 0)
        self.assertIn("mean_sentence_words", diagnostic["comparisons"])

    def test_judge_requires_exact_passage_evidence_on_every_axis(self) -> None:
        text = "Mara noticed the pause and chose to ask a smaller question."
        payload = {
            "candidate_id": "c1",
            "scores": {axis: 7 for axis in AUTHOR_EVALUATION_AXES},
            "evidence": {
                axis: ["Mara noticed the pause"] for axis in AUTHOR_EVALUATION_AXES
            },
            "defects": [],
            "copy_suspicion": False,
            "notes": "Mechanism fidelity without surface mimicry.",
        }
        result = parse_author_judgment(
            payload,
            candidate_id="c1",
            candidate_text=text,
            judge_id="judge",
        )
        self.assertEqual(result.mean_score, 7)
        payload["evidence"]["novelty"] = ["unsupported paraphrase"]
        with self.assertRaisesRegex(ValueError, "unsupported"):
            parse_author_judgment(
                payload,
                candidate_id="c1",
                candidate_text=text,
                judge_id="judge",
            )

    def test_quality_diversity_copy_frontier_does_not_average_tradeoffs(self) -> None:
        records = (
            {"candidate_id": "a", "quality": 9, "diversity": 4, "copy": 0},
            {"candidate_id": "b", "quality": 7, "diversity": 9, "copy": 0},
            {"candidate_id": "c", "quality": 6, "diversity": 3, "copy": 1},
        )
        result = pareto_frontier(
            records, maximize=("quality", "diversity"), minimize=("copy",)
        )
        self.assertEqual({item["candidate_id"] for item in result}, {"a", "b"})


class StoryProgramTests(unittest.TestCase):
    def test_quality_diversity_selection_requires_valid_programs(self) -> None:
        programs = []
        for index in range(10):
            programs.append(
                StoryProgram(
                    story_program_id=f"p{index}",
                    scene_id="s01",
                    raw_proposal=f"proposal {index}",
                    compiled_program={
                        "premise": f"premise {index}",
                        "event_sequence": [f"event {index}", "b", "c", "d"],
                        "relationship_delta": f"delta {index}",
                        "realized_coordinates": [f"trope.{index}"],
                        "dialogue_strategy": f"dialogue {index}",
                        "intimacy_strategy": f"intimacy {index}",
                        "continuity_facts": ["adult"],
                    },
                    repairs=(),
                    selected_coordinates=(f"trope.{index}",),
                    lineage=(f"raw-{index}",),
                    author_profile_hash=DIGEST,
                    resolved_profile_hash="b" * 64,
                )
            )
        selected = select_story_programs(programs)
        self.assertEqual(len(selected), 8)
        self.assertEqual(len({item.story_program_id for item in selected}), 8)

    def test_author_run_config_carries_complete_profile_lineage(self) -> None:
        scene = SceneSpec.from_dict(
            json.loads(
                Path(
                    "03_scene_lab/compiled/s01-v2-ontology/"
                    "scene_specs/s01.v1.json"
                ).read_text(encoding="utf-8")
            )
        )
        books = (
            AuthorBook("book-a", "A", "profiling", "a", DIGEST),
            AuthorBook("book-b", "B", "profiling", "b", DIGEST),
            AuthorBook("book-h", "H", "holdout", "h", DIGEST),
        )
        manifest = AuthorCorpusManifest(
            "test.v1", "test-author", "Test Author", "1", books
        )
        profile = _profile(manifest)
        transformation = _transformation(profile)
        context = resolve_author_context(
            profile,
            transformation,
            corpus_manifest_hash=manifest.corpus_hash,
        )
        program = StoryProgram(
            story_program_id="p1",
            scene_id="S01",
            raw_proposal="proposal",
            compiled_program={
                "premise": "p",
                "event_sequence": ["a", "b", "c", "d"],
                "relationship_delta": "delta",
                "realized_coordinates": [],
                "dialogue_strategy": "probe",
                "intimacy_strategy": "restraint",
                "continuity_facts": ["adult"],
            },
            repairs=(),
            selected_coordinates=(),
            lineage=("raw",),
            author_profile_hash=profile.profile_hash,
            resolved_profile_hash="f" * 64,
        )
        index = AntiCopyIndex({"source": "unrelated source words"})
        config = build_author_run_config(
            run_id="run",
            scene=scene,
            program=program,
            prefix_hash="1" * 64,
            source_hashes={"canon": "2" * 64},
            resolved_creative_profile={
                "ontology_version": "rgo.v1",
                "story_profile_id": "story",
                "scene_profile_id": "scene",
                "profile_hash": "f" * 64,
            },
            author_context=context,
            anti_copy_index=index,
            seed=7,
            output_tokens=100,
            frontier_adapter="none-local",
        )
        self.assertEqual(config.author_profile_hash, profile.profile_hash)
        self.assertEqual(config.story_program_id, "p1")
        self.assertEqual(config.anti_copy_index_hash, index.index_hash)


if __name__ == "__main__":
    unittest.main()
