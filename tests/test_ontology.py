from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


LAB_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB_ROOT))

from fiction_harness.compiler import compile_trusted_sources  # noqa: E402
from fiction_harness.evaluation import evaluate_candidate, load_rubric, rubric_prompt  # noqa: E402
from fiction_harness.ontology import (  # noqa: E402
    DEFAULT_ONTOLOGY_PATH,
    DEFAULT_SCENE_PROFILE_PATH,
    DEFAULT_STORY_PROFILE_PATH,
    PROFILE_DEFECTS,
    SceneCreativeProfile,
    StoryProfile,
    load_ontology,
    load_scene_profile,
    load_story_profile,
    profile_aware_rubric,
    profile_prompt_text,
    resolve_profile_files,
    resolve_profiles,
)
from fiction_harness.schemas import Candidate, RunConfig  # noqa: E402
from fiction_harness.pipelines import (  # noqa: E402
    parse_actor_traces,
    parse_verbalized_strategies,
    run_direct,
)
from fiction_harness.workflow import load_compiled, load_resolved_profile, make_run_config  # noqa: E402


class OntologyCatalogTests(unittest.TestCase):
    def test_catalog_is_broad_versioned_and_polyhierarchy_capable(self) -> None:
        catalog = load_ontology()
        self.assertEqual(catalog.version, "rgo.v1")
        self.assertGreaterEqual(len(catalog.nodes), 100)
        self.assertEqual(
            catalog.node("trope.forced-proximity").parents,
            ("trope.proximity",),
        )
        self.assertIn("consent", catalog.namespaces)
        self.assertIn("heat", catalog.namespaces)
        self.assertIn("darkness", catalog.namespaces)

    def test_catalog_rejects_parent_cycles(self) -> None:
        data = json.loads(DEFAULT_ONTOLOGY_PATH.read_text(encoding="utf-8"))
        by_id = {node["id"]: node for node in data["nodes"]}
        by_id["trope.proximity"]["parents"] = ["trope.forced-proximity"]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "cycle.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "parent cycle"):
                load_ontology(path)


class ProfileResolutionTests(unittest.TestCase):
    def test_juicy_chastity_s01_resolves_without_warnings(self) -> None:
        catalog, profile = resolve_profile_files()
        self.assertFalse(profile.warnings)
        self.assertEqual(profile.ontology_hash, catalog.ontology_hash)
        self.assertEqual(profile.story_profile_id, "fulcrum-pilot.v1")
        self.assertEqual(profile.scene_profile_id, "fulcrum-s01.v1")
        self.assertEqual(profile.heat_target, "heat.scene.high-tension")
        self.assertIn("consent.explicit-revocable", profile.selected_coordinates)
        self.assertIn(
            "world.supernatural.ambiguous", profile.selected_coordinates
        )
        self.assertNotIn("genre.romance.dark", profile.selected_coordinates)
        self.assertNotIn("genre.romance.erotic", profile.selected_coordinates)

    def test_resolution_and_prompt_hash_are_deterministic(self) -> None:
        _, first = resolve_profile_files()
        _, second = resolve_profile_files()
        self.assertEqual(first.profile_hash, second.profile_hash)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(profile_prompt_text(first), profile_prompt_text(second))

    def test_prompt_contains_selected_semantics_not_retail_codes(self) -> None:
        _, profile = resolve_profile_files()
        prompt = profile_prompt_text(profile)
        self.assertIn("heat.scene.high-tension", prompt)
        self.assertIn("world.supernatural.ambiguous", prompt)
        self.assertNotIn("BISAC", prompt)
        self.assertNotIn("Thema", prompt)
        self.assertNotIn("genre.romance.dark", prompt)
        self.assertNotIn("genre.romance.erotic", prompt)

    def test_external_mappings_are_versioned_and_project_relevant(self) -> None:
        _, profile = resolve_profile_files()
        mappings = list(profile.external_mappings)
        self.assertTrue(mappings)
        self.assertTrue(
            all(mapping.get("version") for mapping in mappings)
        )
        codes = {mapping["code"] for mapping in mappings}
        self.assertIn("FRM", codes)
        self.assertIn("FRD", codes)
        self.assertIn("FW", codes)
        self.assertIn("5PGM", codes)
        self.assertIn("5LKE", codes)
        self.assertIn("FIC042120", codes)
        self.assertNotIn("FRF", codes)
        self.assertNotIn("FRT", codes)

    def test_scene_cannot_remove_protected_coordinate(self) -> None:
        catalog = load_ontology()
        layers = load_story_profile(DEFAULT_STORY_PROFILE_PATH)
        scene = load_scene_profile(DEFAULT_SCENE_PROFILE_PATH)
        invalid = replace(
            scene, remove_coordinates=("consent.explicit-revocable",)
        )
        with self.assertRaisesRegex(ValueError, "may not remove protected"):
            resolve_profiles(catalog, layers, invalid)

    def test_scene_heat_target_cannot_exceed_story_ceiling(self) -> None:
        catalog = load_ontology()
        story = StoryProfile(
            profile_id="low-heat",
            ontology_version=catalog.version,
            primary_genre="genre.romance.contemporary",
            contract="contract.romance-hea",
            coordinates=(
                "relationship.pair.monogamous",
                "consent.explicit-revocable",
                "heat.book.sensual",
                "narration.close-third-single",
            ),
            heat_ceiling="heat.ceiling.closed-door",
            relationship_trajectory="relationship.trajectory.marriage-oriented",
        )
        scene = SceneCreativeProfile(
            scene_profile_id="too-hot",
            story_profile_id=story.profile_id,
            ontology_version=catalog.version,
            scene_id="S99",
            coordinates=("heat.scene.high-tension",),
            heat_target="heat.scene.high-tension",
        )
        with self.assertRaisesRegex(ValueError, "exceeds"):
            resolve_profiles(catalog, (story,), scene)

    def test_redundant_ancestor_and_descendant_are_rejected(self) -> None:
        catalog = load_ontology()
        story = StoryProfile(
            profile_id="redundant",
            ontology_version=catalog.version,
            primary_genre="genre.romance.contemporary",
            contract="contract.romance-hea",
            coordinates=(
                "genre.romance",
                "relationship.pair.monogamous",
                "consent.explicit-revocable",
                "heat.book.sensual",
                "narration.close-third-single",
            ),
            heat_ceiling="heat.ceiling.closed-door",
            relationship_trajectory="relationship.trajectory.marriage-oriented",
        )
        with self.assertRaisesRegex(ValueError, "redundant ancestor"):
            resolve_profiles(catalog, (story,))


class OntologyHarnessIntegrationTests(unittest.TestCase):
    def test_ontology_compile_is_reproducible_and_legacy_remains_profile_free(self) -> None:
        with TemporaryDirectory() as first_dir, TemporaryDirectory() as second_dir:
            first = compile_trusted_sources(
                LAB_ROOT,
                first_dir,
                ontology_path=DEFAULT_ONTOLOGY_PATH,
                story_profile_path=DEFAULT_STORY_PROFILE_PATH,
                scene_profile_path=DEFAULT_SCENE_PROFILE_PATH,
            )
            second = compile_trusted_sources(
                LAB_ROOT,
                second_dir,
                ontology_path=DEFAULT_ONTOLOGY_PATH,
                story_profile_path=DEFAULT_STORY_PROFILE_PATH,
                scene_profile_path=DEFAULT_SCENE_PROFILE_PATH,
            )
            self.assertEqual(first.manifest_hash, second.manifest_hash)
            self.assertEqual(first.stable_prefix_hash, second.stable_prefix_hash)
            self.assertIsNotNone(first.resolved_profile_path)
            prefix = first.stable_prefix_path.read_text(encoding="utf-8")
            self.assertLess(
                prefix.index("@@SECTION resolved_creative_profile"),
                prefix.index("@@SECTION project_brief"),
            )
            self.assertNotIn("BISAC", prefix)
            self.assertNotIn("Thema", prefix)

        scene, personas, _, _ = load_compiled(
            LAB_ROOT / "03_scene_lab/compiled/s01-v1"
        )
        self.assertEqual(scene.scene_id, "S01")
        self.assertTrue(personas)
        self.assertIsNone(
            load_resolved_profile(LAB_ROOT / "03_scene_lab/compiled/s01-v1")
        )

    def test_run_config_and_candidate_carry_profile_provenance(self) -> None:
        _, profile = resolve_profile_files()
        legacy_scene, personas, _, sources = load_compiled(
            LAB_ROOT / "03_scene_lab/compiled/s01-v1"
        )
        config = make_run_config(
            run_id="ontology-test",
            pipeline="direct",
            scene=legacy_scene,
            prompt_hash="a" * 64,
            source_hashes=sources,
            count=1,
            persona_ids=tuple(persona.persona_id for persona in personas),
            resolved_profile=profile,
        )
        self.assertEqual(config.resolved_profile_hash, profile.profile_hash)
        candidate = Candidate(
            candidate_id="ontology-candidate",
            run_id=config.run_id,
            pipeline=config.pipeline,
            scene_id=config.scene_id,
            seed=config.seeds[0],
            text="Mara watched and chose.",
            parent_trace={},
            evidence_ids=(),
            telemetry={},
            lineage=(),
            prompt_hash="b" * 64,
            ontology_version=config.ontology_version,
            story_profile_id=config.story_profile_id,
            scene_profile_id=config.scene_profile_id,
            resolved_profile_hash=config.resolved_profile_hash,
        )
        self.assertEqual(
            Candidate.from_dict(candidate.to_dict()).resolved_profile_hash,
            profile.profile_hash,
        )

    def test_profile_aware_evaluation_requires_matching_provenance(self) -> None:
        _, profile = resolve_profile_files()
        scene, _, _, _ = load_compiled(
            LAB_ROOT / "03_scene_lab/compiled/s01-v1"
        )
        candidate = {
            "candidate_id": "wrong-profile",
            "text": "Mara arrived.",
            "resolved_profile_hash": "0" * 64,
        }
        score = evaluate_candidate(
            candidate, scene, (), load_rubric(), resolved_profile=profile
        )
        self.assertFalse(score["hard_gates"]["profile_provenance"])
        self.assertEqual(score["resolved_profile_hash"], profile.profile_hash)

    def test_profile_rubric_adds_diagnostics_and_defects_without_reweighting(self) -> None:
        _, profile = resolve_profile_files()
        base = load_rubric()
        active = profile_aware_rubric(base, profile)
        self.assertEqual(
            sum(float(axis["weight"]) for axis in active["axes"].values()), 100
        )
        self.assertTrue(set(PROFILE_DEFECTS) <= set(active["defect_taxonomy"]))
        prompt = rubric_prompt(active)
        self.assertIn("Resolved creative-profile diagnostic overlay", prompt)
        self.assertIn("heat_consent_darkness", prompt)

    def test_profiled_planners_require_realized_coordinate_maps(self) -> None:
        strategies = {
            "strategies": [
                {
                    "id": f"s-{index}",
                    "probability": 0.01,
                    "title": f"route-{index}",
                }
                for index in range(8)
            ]
        }
        with self.assertRaisesRegex(ValueError, "realized_coordinates"):
            parse_verbalized_strategies(
                json.dumps(strategies),
                source_call="profiled",
                require_profile_coordinates=True,
            )
        for strategy in strategies["strategies"]:
            strategy["realized_coordinates"] = {
                "trope.charged-restraint": "Jonah declines the status reward"
            }
        self.assertEqual(
            len(
                parse_verbalized_strategies(
                    json.dumps(strategies),
                    source_call="profiled",
                    require_profile_coordinates=True,
                )
            ),
            8,
        )

        trace = {
            "id": "trace-1",
            "what_mara_notices": ["pause"],
            "competing_interpretations": ["care", "control"],
            "desire": "know",
            "concealed_vulnerability": "wanting",
            "livia_strategy": "probe",
            "jonah_restraint": "declines",
            "dialogue_act_sequence": ["test"],
            "erotic_escalation": ["attention"],
            "intimacy_mode": "non-sex",
            "emotional_transaction": {"ending": "recognition"},
            "mara_attraction_filter": ["restraint"],
            "sensory_triad": ["touch", "sound", "sight"],
            "atmospheric_pressure": "witnesses",
            "body_language_counterpoint": ["withdrawal"],
            "distance_plan": {"close": "wrist"},
            "relationship_delta": "strangers -> allies",
            "experimental_control": "mask cue",
            "residual_mystery": "one result",
            "event_sequence": ["one"],
        }
        self.assertEqual(
            parse_actor_traces(
                json.dumps({"traces": [trace]}),
                require_profile_coordinates=True,
            ),
            [],
        )
        trace["realized_coordinates"] = {
            "trope.charged-restraint": "Jonah declines"
        }
        self.assertEqual(
            len(
                parse_actor_traces(
                    json.dumps({"traces": [trace]}),
                    require_profile_coordinates=True,
                )
            ),
            1,
        )

    def test_resume_refuses_different_profile_hash(self) -> None:
        scene, personas, _, sources = load_compiled(
            LAB_ROOT / "03_scene_lab/compiled/s01-v1"
        )
        _, profile = resolve_profile_files()
        first_config = make_run_config(
            run_id="resume-profile-test",
            pipeline="direct",
            scene=scene,
            prompt_hash="a" * 64,
            source_hashes=sources,
            count=1,
            persona_ids=tuple(persona.persona_id for persona in personas),
            resolved_profile=profile,
        )
        second_config = replace(
            first_config, resolved_profile_hash="b" * 64
        )

        class Client:
            model = "fake"

            def complete(self, **kwargs):
                return {"content": "A scene.", "model": self.model}

        with TemporaryDirectory() as directory:
            run_direct(
                client=Client(),
                config=first_config,
                scene=scene,
                personas=personas,
                shared_prefix="stable",
                run_dir=Path(directory),
                count=1,
            )
            with self.assertRaisesRegex(ValueError, "profile provenance"):
                run_direct(
                    client=Client(),
                    config=second_config,
                    scene=scene,
                    personas=personas,
                    shared_prefix="stable",
                    run_dir=Path(directory),
                    count=1,
                )


if __name__ == "__main__":
    unittest.main()
