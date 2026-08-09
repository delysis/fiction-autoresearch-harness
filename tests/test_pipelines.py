from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


LAB_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB_ROOT))

from fiction_harness.pipelines import (  # noqa: E402
    VerbalizedStrategy,
    deduplicate_actor_traces,
    deduplicate_strategies,
    parse_actor_traces,
    parse_verbalized_strategies,
    run_actor_novelist,
    run_direct,
    run_verbalized_sampling,
    weighted_sample_without_replacement,
)
from fiction_harness.schemas import PersonaPacket, RunConfig, SceneSpec  # noqa: E402


class FakeClient:
    def __init__(self, responses: list[str], model: str = "fake"):
        self.responses = list(responses)
        self.model = model
        self.calls: list[dict] = []

    def complete(self, **kwargs):
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("Unexpected model call")
        return {"content": self.responses.pop(0), "model": self.model}


def make_scene() -> SceneSpec:
    return SceneSpec(
        scene_id="S01",
        title="The Calibration Game",
        function="Entrance and romantic recognition.",
        pov="Mara",
        target_words_min=2800,
        target_words_max=3600,
        opening_image="Mara arrives.",
        desire="Understand the game without surrendering judgment.",
        obstacle="Livia turns perception into authority.",
        pressure_ladder=("arrival", "reading", "contact", "control"),
        turn="Mara changes the cue channel.",
        aftermath="Jonah recognizes her method.",
        teaching_payload="Desire sharpens free attention.",
        source_ids=("MPC-01", "LEV-01"),
        beat_map=tuple(f"Beat {index}" for index in range(1, 9)),
        continuity_facts=("All principals are adults.",),
        heat_ceiling="No consummation.",
    )


def make_personas() -> tuple[PersonaPacket, ...]:
    return (
        PersonaPacket(
            persona_id="mara",
            name="Mara",
            version="1",
            role="protagonist",
            age=22,
            invariants=("Methodical under pressure.",),
            false_beliefs=("Uncertainty forfeits authority.",),
            attention_habits=("Notices pauses.",),
            relationship_variants={"jonah": ("Trusts costly restraint.",)},
            source_ids=("MPC-01",),
        ),
    )


def make_config(run_id: str, pipeline: str, seeds=(101, 202)) -> RunConfig:
    digest = "a" * 64
    return RunConfig(
        run_id=run_id,
        scene_id="S01",
        pipeline=pipeline,
        model_role="generator",
        prompt_hash=digest,
        source_hashes={"stable_prefix": digest},
        seeds=tuple(seeds),
        sampling={"temperature": 0.9, "top_p": 0.95, "min_p": 0.03},
        output_words_min=2800,
        output_words_max=3600,
        output_tokens=6000,
        persona_ids=("mara",),
    )


def strategy_payload(prefix: str) -> str:
    strategies = []
    for index in range(8):
        unique = f"{prefix}_lexeme_{index}"
        strategies.append(
            {
                "id": f"{prefix}-{index}",
                "title": unique,
                "probability": 0.01 + index * 0.005,
                "premise": f"{unique} " * 4,
                "beat_strategy": [f"{unique}_beat_{beat}" for beat in range(8)],
                "dialogue_moves": [f"{unique}_speech"],
                "event_sequence": [f"{unique}_event"],
                "romantic_engine": f"{unique}_romance",
                "epistemic_turn": f"{unique}_control",
            }
        )
    return json.dumps({"strategies": strategies})


def actor_payload() -> str:
    traces = []
    for index in range(12):
        unique = f"route_{index}"
        traces.append(
            {
                "id": f"trace-{index}",
                "what_mara_notices": [f"{unique} cue"],
                "competing_interpretations": [f"{unique} ordinary", "uncanny"],
                "desire": f"{unique} desire",
                "concealed_vulnerability": f"{unique} fear",
                "livia_strategy": f"{unique} probe",
                "jonah_restraint": f"{unique} refusal",
                "dialogue_act_sequence": [f"{unique} tease", "question"],
                "erotic_escalation": [f"{unique} attention"],
                "intimacy_mode": "non-sex sex scene",
                "emotional_transaction": {
                    "opening_offer": f"{unique} curiosity",
                    "counteroffer": f"{unique} recognition",
                    "ending_state": f"{unique} freer desire",
                },
                "mara_attraction_filter": [f"{unique} costly restraint"],
                "sensory_triad": ["touch", "sound", f"{unique} cedar"],
                "atmospheric_pressure": f"{unique} watching room",
                "body_language_counterpoint": [f"{unique} withdrawal"],
                "distance_plan": {
                    "close_on": f"{unique} wrist",
                    "widen_or_omit": f"{unique} unperformed kiss",
                },
                "relationship_delta": f"{unique} strangers -> recognized allies",
                "experimental_control": f"{unique} cue mask",
                "residual_mystery": f"{unique} remainder",
                "event_sequence": [f"{unique} event {beat}" for beat in range(8)],
            }
        )
    return json.dumps({"traces": traces})


class PipelineTests(unittest.TestCase):
    def test_verbalized_parser_fences_percent_and_probability_constraint(self) -> None:
        body = strategy_payload("a")
        parsed = parse_verbalized_strategies(f"```json\n{body}\n```", source_call="x")
        self.assertEqual(len(parsed), 8)
        percent = json.dumps(
            {"strategies": [{"probability": "0.07%", "title": "rare"}]}
        )
        self.assertAlmostEqual(
            parse_verbalized_strategies(percent, source_call="pct")[0].probability,
            0.0007,
        )
        bad = json.dumps({"strategies": [{"probability": 0.1, "title": "bad"}]})
        with self.assertRaisesRegex(ValueError, "must be"):
            parse_verbalized_strategies(bad, source_call="bad")

    def test_weighted_sampling_is_reproducible_and_dedupe_is_stable(self) -> None:
        original = VerbalizedStrategy("a", 0.03, {"title": "one"}, "x")
        duplicate = VerbalizedStrategy("b", 0.02, {"title": "one"}, "y")
        distinct = [
            VerbalizedStrategy(
                f"d{index}",
                0.01 + index / 1000,
                {"title": f"utterly distinct route {index}"},
                "x",
            )
            for index in range(8)
        ]
        unique = deduplicate_strategies([duplicate, original, *distinct])
        self.assertIn("a", [item.strategy_id for item in unique])
        self.assertNotIn("b", [item.strategy_id for item in unique])
        first = weighted_sample_without_replacement(unique, count=4, seed=17)
        second = weighted_sample_without_replacement(unique, count=4, seed=17)
        self.assertEqual(
            [item.strategy_id for item in first],
            [item.strategy_id for item in second],
        )

    def test_direct_keeps_prompt_identical_and_resumes(self) -> None:
        client = FakeClient(["scene one", "scene two"])
        with tempfile.TemporaryDirectory() as directory:
            kwargs = dict(
                client=client,
                config=make_config("r-direct", "direct"),
                scene=make_scene(),
                personas=make_personas(),
                shared_prefix="stable prefix bytes",
                run_dir=Path(directory),
                count=2,
            )
            candidates = run_direct(**kwargs)
            self.assertEqual(len(candidates), 2)
            self.assertEqual(client.calls[0]["prompt"], client.calls[1]["prompt"])
            self.assertTrue(
                all(
                    item.artifact_authorship["creation_kind"]
                    == "model_generation"
                    for item in candidates
                )
            )
            self.assertTrue(
                all(
                    item.artifact_authorship["model_call"]["call_record_hash"]
                    for item in candidates
                )
            )
            resumed = run_direct(**kwargs)
            self.assertEqual([item.text for item in resumed], ["scene one", "scene two"])
            self.assertEqual(len(client.calls), 2)

    def test_verbalized_pipeline_makes_two_distributions_and_realizes(self) -> None:
        client = FakeClient(
            [strategy_payload("alpha"), strategy_payload("beta"), "scene A", "scene B"]
        )
        with tempfile.TemporaryDirectory() as directory:
            candidates = run_verbalized_sampling(
                client=client,
                config=make_config("r-vs", "verbalized_sampling"),
                scene=make_scene(),
                personas=make_personas(),
                shared_prefix="stable prefix bytes",
                run_dir=Path(directory),
                count=2,
            )
            self.assertEqual(len(candidates), 2)
            self.assertTrue((Path(directory) / "verbalized_diversity.json").is_file())
            self.assertEqual(len(client.calls), 4)

    def test_verbalized_pipeline_repairs_invalid_distribution(self) -> None:
        client = FakeClient(
            [
                "not json",
                strategy_payload("repaired"),
                strategy_payload("second"),
                "scene",
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            candidates = run_verbalized_sampling(
                client=client,
                config=make_config("r-vs-repair", "verbalized_sampling", seeds=(101,)),
                scene=make_scene(),
                personas=make_personas(),
                shared_prefix="stable prefix bytes",
                run_dir=Path(directory),
                count=1,
            )
            self.assertEqual(len(candidates), 1)
            call_records = [
                json.loads(line)
                for line in (Path(directory) / "calls.jsonl").read_text().splitlines()
            ]
            self.assertTrue(
                any(
                    item["call_id"] == "r-vs-repair-vs-distribution-1-repair-1"
                    and item["status"] == "completed"
                    and item["runtime"]["model_alias"] == "fake"
                    for item in call_records
                )
            )

    def test_actor_novelist_validates_clusters_and_realizes(self) -> None:
        generator = FakeClient([actor_payload(), "actor scene A", "actor scene B"])
        validation = {
            "valid_ids": [f"trace-{index}" for index in range(12)],
            "clusters": [
                {
                    "cluster_id": f"c{index}",
                    "trace_ids": [f"trace-{index}"],
                    "shared_strategy": f"route {index}",
                }
                for index in range(12)
            ],
            "defects": {},
        }
        fast = FakeClient([json.dumps(validation)], model="fake-e4b")
        with tempfile.TemporaryDirectory() as directory:
            candidates = run_actor_novelist(
                generator_client=generator,
                fast_client=fast,
                config=make_config("r-actor", "actor_novelist"),
                scene=make_scene(),
                personas=make_personas(),
                shared_prefix="stable prefix bytes",
                run_dir=Path(directory),
                count=2,
            )
            self.assertEqual(len(candidates), 2)
            self.assertEqual(len(generator.calls), 3)
            self.assertEqual(len(fast.calls), 1)
            traces = [
                json.loads(line)
                for line in (Path(directory) / "actor_traces.jsonl")
                .read_text()
                .splitlines()
            ]
            self.assertEqual(len(traces), 12)
            self.assertEqual(
                sum(item["status"] == "selected" for item in traces),
                2,
            )
            self.assertEqual(len(parse_actor_traces(actor_payload())), 12)
            resumed = run_actor_novelist(
                generator_client=generator,
                fast_client=fast,
                config=make_config("r-actor", "actor_novelist"),
                scene=make_scene(),
                personas=make_personas(),
                shared_prefix="stable prefix bytes",
                run_dir=Path(directory),
                count=2,
            )
            self.assertEqual(len(resumed), 2)
            self.assertEqual(
                len(
                    (Path(directory) / "actor_traces.jsonl")
                    .read_text()
                    .splitlines()
                ),
                12,
            )

    def test_actor_novelist_repairs_actor_and_validation_json(self) -> None:
        generator = FakeClient(
            ["bad actor json", actor_payload(), "repaired actor scene"]
        )
        validation = {
            "valid_ids": [f"trace-{index}" for index in range(12)],
            "clusters": [
                {"cluster_id": "all", "trace_ids": [f"trace-{i}" for i in range(12)]}
            ],
            "defects": {},
        }
        fast = FakeClient(["bad validation json", json.dumps(validation)])
        with tempfile.TemporaryDirectory() as directory:
            candidates = run_actor_novelist(
                generator_client=generator,
                fast_client=fast,
                config=make_config("r-actor-repair", "actor_novelist", seeds=(303,)),
                scene=make_scene(),
                personas=make_personas(),
                shared_prefix="stable prefix bytes",
                run_dir=Path(directory),
                count=1,
            )
            self.assertEqual(candidates[0].text, "repaired actor scene")
            self.assertEqual(len(generator.calls), 3)
            self.assertEqual(len(fast.calls), 2)

    def test_actor_trace_deduplication_ignores_changed_ids(self) -> None:
        traces = parse_actor_traces(actor_payload())
        duplicate = dict(traces[0])
        duplicate["id"] = "different-id"
        self.assertEqual(
            len(deduplicate_actor_traces([traces[0], duplicate, traces[1]])),
            2,
        )


if __name__ == "__main__":
    unittest.main()
