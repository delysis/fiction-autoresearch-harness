"""Three reproducible local fiction-generation pipelines.

The functions in this module make no assumptions about the CLI.  They accept
the stable schema records, an OpenAI-compatible client, and a run directory;
all model calls and candidates are append-only and resumable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from difflib import SequenceMatcher
import json
from pathlib import Path
import random
import re
from statistics import mean
from typing import Any, Iterable, Mapping, Protocol, Sequence

from .authorship import proof_carrying_model_authorship
from .craft import render_craft_prompt
from .model_client import Completion
from .runtime import (
    TraceStore,
    canonical_json,
    model_runtime_provenance,
    sha256_text,
    stable_prompt,
    utc_now,
)
from .schemas import Candidate, PersonaPacket, RunConfig, SceneSpec


PROMPT_DIR = Path(__file__).with_name("prompts")
DEFAULT_SAMPLING = {"temperature": 0.9, "top_p": 0.95, "min_p": 0.03}
DIRECT_PIPELINE = "direct"
VERBALIZED_PIPELINE = "verbalized_sampling"
ACTOR_NOVELIST_PIPELINE = "actor_novelist"


class CompletionClient(Protocol):
    model: str

    def complete(self, **kwargs: Any) -> Completion:
        ...


def _plain(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict"):
        return dict(value.to_dict())
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError(f"Expected record or mapping, got {type(value).__name__}")


def _prompt(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def load_shared_prefix(compiled_dir: Path) -> str:
    """Load compiler output verbatim after the invariant fiction instruction."""

    compiled = Path(compiled_dir) / "stable_prefix.txt"
    if not compiled.is_file():
        raise FileNotFoundError(
            f"Compiled stable prefix not found: {compiled}. Run compile first."
        )
    system = _prompt("system_static.txt")
    # No strip/normalization: cache identity depends on preserving these bytes.
    return (
        system
        + "\n"
        + render_craft_prompt(mode="generation")
        + "\n<COMPILED_PROJECT_DOSSIER>\n"
        + compiled.read_text(encoding="utf-8")
    )


def _scene_bounds(scene: SceneSpec) -> dict[str, int]:
    return {
        "target_min": scene.target_words_min,
        "target_max": scene.target_words_max,
    }


def _source_ids(
    scene: SceneSpec, personas: Sequence[PersonaPacket]
) -> tuple[str, ...]:
    ordered = list(scene.source_ids)
    for persona in personas:
        ordered.extend(persona.source_ids)
    return tuple(dict.fromkeys(ordered))


def _sampling(config: RunConfig) -> dict[str, float]:
    values = dict(DEFAULT_SAMPLING)
    for key in values:
        if key in config.sampling:
            values[key] = float(config.sampling[key])
    return values


def _call(
    client: CompletionClient,
    store: TraceStore,
    *,
    call_id: str,
    role: str,
    prompt: str,
    seed: int,
    max_tokens: int,
    temperature: float,
    top_p: float,
    min_p: float,
) -> dict[str, Any]:
    prompt_hash = sha256_text(prompt)
    prompt_dir = store.run_dir / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = prompt_dir / f"{call_id}.txt"
    if prompt_path.is_file():
        if sha256_text(prompt_path.read_text(encoding="utf-8")) != prompt_hash:
            raise ValueError(f"Refusing prompt-byte drift for {call_id}")
    else:
        temporary = prompt_path.with_suffix(".txt.tmp")
        temporary.write_text(prompt, encoding="utf-8")
        temporary.replace(prompt_path)
    prior = store.completed_call(call_id)
    if prior:
        prior_hash = str(prior.get("prompt_hash", ""))
        if prior_hash and prior_hash != prompt_hash:
            raise ValueError(
                f"Refusing to resume {call_id}: prompt hash changed "
                f"({prior_hash} != {prompt_hash})"
            )
        result = prior.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("content"), str):
            raise ValueError(f"Completed call {call_id} is missing its result")
        return result

    parameters = {
        "seed": seed,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "min_p": min_p,
    }
    base = {
        "call_id": call_id,
        "role": role,
        "model": getattr(client, "model", "unknown"),
        "runtime": model_runtime_provenance(
            str(getattr(client, "model", "unknown"))
        ),
        "prompt_hash": prompt_hash,
        "prompt_path": str(prompt_path.resolve()),
        "transport": "chat_completion",
        "parameters": parameters,
    }
    store.append_call({**base, "status": "started", "started_at": utc_now()})
    try:
        completion = client.complete(prompt=prompt, **parameters)
    except Exception as exc:
        store.append_call(
            {
                **base,
                "status": "failed",
                "finished_at": utc_now(),
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        raise
    if isinstance(completion, Completion):
        result = completion.to_dict()
        # The raw object duplicates the response and can be very large.
        result.pop("raw", None)
    elif isinstance(completion, Mapping):
        result = dict(completion)
    elif isinstance(completion, str):
        result = {"content": completion}
    else:
        raise TypeError(f"Unexpected completion type: {type(completion).__name__}")
    if not isinstance(result.get("content"), str):
        raise ValueError(f"Call {call_id} returned no textual content")
    store.append_call(
        {
            **base,
            "status": "completed",
            "finished_at": utc_now(),
            "result": result,
        }
    )
    return result


def _repair_prompt(
    shared_prefix: str,
    original_dynamic: str,
    *,
    prior_output: str,
    error_message: str,
) -> str:
    """Create a bounded, deterministic format-repair request."""

    repair = (
        original_dynamic
        + "\n\n<FORMAT_REPAIR>\n"
        + "The previous response failed validation. Correct its structure and return "
        + "the complete requested JSON only.\n"
        + f"VALIDATION ERROR: {error_message}\n"
        + "PREVIOUS RESPONSE:\n"
        + prior_output[-16_000:]
        + "\n</FORMAT_REPAIR>"
    )
    return stable_prompt(shared_prefix, repair)


def _candidate_from_record(
    record: Mapping[str, Any], config: RunConfig | None = None
) -> Candidate:
    payload = dict(record)
    payload.pop("status", None)
    payload.pop("finished_at", None)
    candidate = Candidate.from_dict(payload)
    if config is not None and (
        candidate.resolved_profile_hash != config.resolved_profile_hash
        or candidate.ontology_version != config.ontology_version
        or candidate.story_profile_id != config.story_profile_id
        or candidate.scene_profile_id != config.scene_profile_id
    ):
        raise ValueError(
            f"Refusing to resume {candidate.candidate_id}: creative profile "
            "provenance differs from the active run configuration"
        )
    return candidate


def _save_candidate(store: TraceStore, candidate: Candidate) -> None:
    store.append_candidate(
        {
            **candidate.to_dict(),
            "status": "completed",
            "finished_at": utc_now(),
        }
    )


def _candidate(
    *,
    config: RunConfig,
    pipeline: str,
    candidate_id: str,
    seed: int,
    text: str,
    parent_trace: Mapping[str, Any],
    evidence_ids: tuple[str, ...],
    result: Mapping[str, Any],
    prompt_hash: str,
    lineage: tuple[str, ...],
    store: TraceStore,
) -> Candidate:
    telemetry = {
        key: result.get(key)
        for key in (
            "model",
            "finish_reason",
            "usage",
            "timings",
            "cache",
            "elapsed_seconds",
        )
        if result.get(key) is not None
    }
    normalized_text = text.strip()
    call_id = next(
        (
            item.removeprefix("call:")
            for item in reversed(lineage)
            if item.startswith("call:")
        ),
        f"{candidate_id}-generation",
    )
    completed_call = store.completed_call(call_id)
    if not completed_call:
        raise ValueError(f"candidate cannot resolve completed call {call_id}")
    authorship = proof_carrying_model_authorship(
        artifact_id=candidate_id,
        text=normalized_text,
        model_id=str(completed_call.get("model", config.model_role)),
        call_id=call_id,
        prompt_hash=prompt_hash,
        seed=seed,
        call_ledger_path=store.calls_path,
        derivation={"operation": "strip"},
        created_at=utc_now(),
    )
    return Candidate(
        candidate_id=candidate_id,
        run_id=config.run_id,
        pipeline=pipeline,
        scene_id=config.scene_id,
        seed=seed,
        text=normalized_text,
        parent_trace=dict(parent_trace),
        evidence_ids=evidence_ids,
        telemetry=telemetry,
        lineage=lineage,
        prompt_hash=prompt_hash,
        completed=True,
        ontology_version=config.ontology_version,
        story_profile_id=config.story_profile_id,
        scene_profile_id=config.scene_profile_id,
        resolved_profile_hash=config.resolved_profile_hash,
        artifact_authorship=authorship,
    )


def run_direct(
    *,
    client: CompletionClient,
    config: RunConfig,
    scene: SceneSpec,
    personas: Sequence[PersonaPacket],
    shared_prefix: str,
    run_dir: Path,
    count: int = 8,
) -> list[Candidate]:
    """Pipeline A: eight native stochastic samples with an identical prompt."""

    if len(config.seeds) < count:
        raise ValueError(f"Direct pipeline requires at least {count} seeds")
    dynamic = _prompt("direct_scene.txt").format(**_scene_bounds(scene))
    prompt = stable_prompt(shared_prefix, dynamic)
    sampling = _sampling(config)
    store = TraceStore(run_dir)
    evidence_ids = _source_ids(scene, personas)
    candidates: list[Candidate] = []
    for index, seed in enumerate(config.seeds[:count], 1):
        candidate_id = f"{config.run_id}-direct-{index:02d}"
        prior = store.completed_candidate(candidate_id)
        if prior:
            candidates.append(_candidate_from_record(prior, config))
            continue
        result = _call(
            client,
            store,
            call_id=f"{candidate_id}-generate",
            role="generator",
            prompt=prompt,
            seed=seed,
            max_tokens=config.output_tokens,
            **sampling,
        )
        candidate = _candidate(
            config=config,
            pipeline=DIRECT_PIPELINE,
            candidate_id=candidate_id,
            seed=seed,
            text=result["content"],
            parent_trace={},
            evidence_ids=evidence_ids,
            result=result,
            prompt_hash=sha256_text(prompt),
            lineage=(f"call:{candidate_id}-generate",),
            store=store,
        )
        _save_candidate(store, candidate)
        candidates.append(candidate)
    return candidates


@dataclass(frozen=True, slots=True)
class VerbalizedStrategy:
    strategy_id: str
    probability: float
    payload: dict[str, Any]
    source_call: str

    @property
    def text(self) -> str:
        return canonical_json(
            {
                key: value
                for key, value in self.payload.items()
                if key not in {"id", "strategy_id", "probability"}
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "probability": self.probability,
            "payload": self.payload,
            "source_call": self.source_call,
        }


def _extract_json(text: str) -> Any:
    stripped = text.strip()
    fenced = re.search(
        r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.IGNORECASE | re.DOTALL
    )
    if fenced:
        stripped = fenced.group(1).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        starts = [index for index in (stripped.find("{"), stripped.find("[")) if index >= 0]
        if not starts:
            raise ValueError("No JSON object or array found")
        start = min(starts)
        decoder = json.JSONDecoder()
        try:
            value, _ = decoder.raw_decode(stripped[start:])
        except json.JSONDecodeError as exc:
            raise ValueError("Could not parse JSON response") from exc
        return value


def parse_verbalized_strategies(
    text: str, *, source_call: str, require_profile_coordinates: bool = False
) -> list[VerbalizedStrategy]:
    """Parse the published Verbalized Sampling shape with strict tail weights."""

    value = _extract_json(text)
    items = value.get("strategies") if isinstance(value, dict) else value
    if not isinstance(items, list):
        raise ValueError("Verbalized response must contain a strategies array")
    strategies: list[VerbalizedStrategy] = []
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            raise ValueError(f"Strategy {index} is not an object")
        probability = item.get("probability")
        if isinstance(probability, str):
            probability_text = probability.strip()
            had_percent = probability_text.endswith("%")
            probability = probability_text.rstrip("%")
            try:
                probability = float(probability)
            except ValueError as exc:
                raise ValueError(f"Strategy {index} has invalid probability") from exc
            if had_percent:
                probability = float(probability) / 100
        if not isinstance(probability, (float, int)) or isinstance(probability, bool):
            raise ValueError(f"Strategy {index} has no numeric probability")
        probability = float(probability)
        if not 0 < probability < 0.10:
            raise ValueError(
                f"Strategy {index} probability must be > 0 and < 0.10, got {probability}"
            )
        raw_strategy_id = str(
            item.get("id") or item.get("strategy_id") or f"{source_call}-{index}"
        )
        strategy_id = f"{source_call}:{raw_strategy_id}"
        payload = dict(item)
        payload["probability"] = probability
        realized = payload.get("realized_coordinates")
        if require_profile_coordinates and (
            not isinstance(realized, Mapping)
            or not realized
            or any(
                not isinstance(key, str) or not str(value).strip()
                for key, value in realized.items()
            )
        ):
            raise ValueError(
                f"Strategy {index} must contain a non-empty "
                "realized_coordinates object"
            )
        strategies.append(
            VerbalizedStrategy(
                strategy_id=strategy_id,
                probability=probability,
                payload=payload,
                source_call=source_call,
            )
        )
    if not strategies:
        raise ValueError("Verbalized response contains no strategies")
    return strategies


_WORD_RE = re.compile(r"[a-z0-9']+")


def _tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.casefold()))


def _jaccard(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    if not a and not b:
        return 1.0
    return len(a & b) / max(1, len(a | b))


def deduplicate_strategies(
    strategies: Iterable[VerbalizedStrategy], *, similarity_threshold: float = 0.88
) -> list[VerbalizedStrategy]:
    """Remove semantic-near duplicates while retaining the higher tail weight."""

    def label(item: VerbalizedStrategy) -> str:
        return " ".join(
            str(item.payload.get(key, ""))
            for key in ("title", "premise", "romantic_engine", "epistemic_turn")
        )

    def duplicates(left: VerbalizedStrategy, right: VerbalizedStrategy) -> bool:
        left_label, right_label = label(left), label(right)
        return (
            SequenceMatcher(None, left_label, right_label).ratio()
            >= similarity_threshold
            and _jaccard(left_label, right_label) >= similarity_threshold
            and SequenceMatcher(None, left.text, right.text).ratio()
            >= similarity_threshold
            and _jaccard(left.text, right.text) >= similarity_threshold
        )

    kept: list[VerbalizedStrategy] = []
    for strategy in sorted(
        strategies, key=lambda item: (-item.probability, item.source_call, item.strategy_id)
    ):
        duplicate = any(duplicates(strategy, other) for other in kept)
        if not duplicate:
            kept.append(strategy)
    return kept


def weighted_sample_without_replacement(
    strategies: Sequence[VerbalizedStrategy],
    *,
    count: int,
    seed: int,
) -> list[VerbalizedStrategy]:
    if len(strategies) < count:
        raise ValueError(
            f"Need {count} distinct strategies after deduplication; got {len(strategies)}"
        )
    rng = random.Random(seed)
    pool = list(strategies)
    selected: list[VerbalizedStrategy] = []
    while len(selected) < count:
        total = sum(item.probability for item in pool)
        threshold = rng.random() * total
        running = 0.0
        chosen = len(pool) - 1
        for index, item in enumerate(pool):
            running += item.probability
            if threshold <= running:
                chosen = index
                break
        selected.append(pool.pop(chosen))
    return selected


def verbalized_diversity_report(
    strategies: Sequence[VerbalizedStrategy],
) -> dict[str, Any]:
    by_call: dict[str, list[VerbalizedStrategy]] = {}
    for item in strategies:
        by_call.setdefault(item.source_call, []).append(item)

    def pairwise_distance(items: Sequence[VerbalizedStrategy]) -> float:
        distances = [
            1 - _jaccard(left.text, right.text)
            for index, left in enumerate(items)
            for right in items[index + 1 :]
        ]
        return mean(distances) if distances else 0.0

    across = [
        1 - _jaccard(left.text, right.text)
        for index, left in enumerate(strategies)
        for right in strategies[index + 1 :]
        if left.source_call != right.source_call
    ]
    return {
        "strategy_count": len(strategies),
        "within_call_mean_jaccard_distance": {
            call: pairwise_distance(items) for call, items in sorted(by_call.items())
        },
        "across_call_mean_jaccard_distance": mean(across) if across else 0.0,
    }


def run_verbalized_sampling(
    *,
    client: CompletionClient,
    config: RunConfig,
    scene: SceneSpec,
    personas: Sequence[PersonaPacket],
    shared_prefix: str,
    run_dir: Path,
    count: int = 8,
) -> list[Candidate]:
    """Pipeline B: verbalize a tail distribution, then realize sampled plans."""

    if len(config.seeds) < count:
        raise ValueError(f"Verbalized pipeline requires at least {count} seeds")
    store = TraceStore(run_dir)
    sampling = _sampling(config)
    strategy_dynamic = _prompt("verbalized_sampling.txt").format()
    strategy_prompt = stable_prompt(shared_prefix, strategy_dynamic)
    pool: list[VerbalizedStrategy] = []
    for call_number in (1, 2):
        base_call_id = f"{config.run_id}-vs-distribution-{call_number}"
        active_prompt = strategy_prompt
        parse_error: Exception | None = None
        parsed: list[VerbalizedStrategy] = []
        for attempt in range(3):
            call_id = (
                base_call_id if attempt == 0 else f"{base_call_id}-repair-{attempt}"
            )
            result = _call(
                client,
                store,
                call_id=call_id,
                role="planner",
                prompt=active_prompt,
                seed=(
                    config.seeds[(call_number - 1) % len(config.seeds)]
                    ^ (call_number * 0x271)
                    ^ (attempt * 0x5A17)
                ),
                max_tokens=min(config.output_tokens, 8_192),
                **sampling,
            )
            try:
                parsed = parse_verbalized_strategies(
                    result["content"],
                    source_call=call_id,
                    require_profile_coordinates=bool(
                        config.resolved_profile_hash
                    ),
                )
                if len(parsed) != 8:
                    raise ValueError(
                        f"{call_id} must return exactly eight strategies; "
                        f"got {len(parsed)}"
                    )
                distinct = deduplicate_strategies(parsed)
                if len(distinct) != 8:
                    raise ValueError(
                        f"{call_id} contains only {len(distinct)} distinct strategies"
                    )
                parse_error = None
                break
            except ValueError as exc:
                parse_error = exc
                active_prompt = _repair_prompt(
                    shared_prefix,
                    strategy_dynamic,
                    prior_output=result["content"],
                    error_message=str(exc),
                )
        if parse_error is not None:
            raise ValueError(
                f"{base_call_id} remained invalid after two repair attempts"
            ) from parse_error
        pool.extend(parsed)

    unique = deduplicate_strategies(pool)
    selection_seed = config.seeds[-1] ^ 0x5653
    selected = weighted_sample_without_replacement(
        unique, count=count, seed=selection_seed
    )
    report = {
        **verbalized_diversity_report(pool),
        "unique_after_deduplication": len(unique),
        "selection_seed": selection_seed,
        "selected_ids": [item.strategy_id for item in selected],
    }
    (Path(run_dir) / "verbalized_diversity.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    evidence_ids = _source_ids(scene, personas)
    candidates: list[Candidate] = []
    template = _prompt("realize_strategy.txt")
    for index, (strategy, seed) in enumerate(
        zip(selected, config.seeds[:count]), 1
    ):
        candidate_id = f"{config.run_id}-verbalized-{index:02d}"
        prior = store.completed_candidate(candidate_id)
        if prior:
            candidates.append(_candidate_from_record(prior, config))
            continue
        plan_record = {
            "plan_id": f"{config.run_id}-plan-{index:02d}",
            "candidate_id": candidate_id,
            "pipeline": VERBALIZED_PIPELINE,
            "status": "selected",
            **strategy.to_dict(),
        }
        store.append_plan(plan_record)
        dynamic = template.format(
            **_scene_bounds(scene),
            strategy_json=json.dumps(
                strategy.payload, ensure_ascii=False, sort_keys=True, indent=2
            ),
        )
        prompt = stable_prompt(shared_prefix, dynamic)
        call_id = f"{candidate_id}-realize"
        result = _call(
            client,
            store,
            call_id=call_id,
            role="generator",
            prompt=prompt,
            seed=seed,
            max_tokens=config.output_tokens,
            **sampling,
        )
        candidate = _candidate(
            config=config,
            pipeline=VERBALIZED_PIPELINE,
            candidate_id=candidate_id,
            seed=seed,
            text=result["content"],
            parent_trace=plan_record,
            evidence_ids=evidence_ids,
            result=result,
            prompt_hash=sha256_text(prompt),
            lineage=(
                f"call:{strategy.source_call}",
                f"plan:{plan_record['plan_id']}",
                f"call:{call_id}",
            ),
            store=store,
        )
        _save_candidate(store, candidate)
        candidates.append(candidate)
    return candidates


ACTOR_REQUIRED_FIELDS = (
    "id",
    "what_mara_notices",
    "competing_interpretations",
    "desire",
    "concealed_vulnerability",
    "livia_strategy",
    "jonah_restraint",
    "dialogue_act_sequence",
    "erotic_escalation",
    "intimacy_mode",
    "emotional_transaction",
    "mara_attraction_filter",
    "sensory_triad",
    "atmospheric_pressure",
    "body_language_counterpoint",
    "distance_plan",
    "relationship_delta",
    "experimental_control",
    "residual_mystery",
    "event_sequence",
)


def parse_actor_traces(
    text: str, *, require_profile_coordinates: bool = False
) -> list[dict[str, Any]]:
    value = _extract_json(text)
    items = value.get("traces") if isinstance(value, dict) else value
    if not isinstance(items, list):
        raise ValueError("Actor response must contain a traces array")
    traces: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            continue
        trace = dict(item)
        trace.setdefault("id", f"trace-{index}")
        trace_id = str(trace["id"])
        if trace_id in seen:
            continue
        required_fields = (
            (*ACTOR_REQUIRED_FIELDS, "realized_coordinates")
            if require_profile_coordinates
            else ACTOR_REQUIRED_FIELDS
        )
        if all(
            field in trace and trace[field] not in ("", [], None)
            for field in required_fields
        ):
            if require_profile_coordinates and not isinstance(
                trace["realized_coordinates"], Mapping
            ):
                continue
            trace["id"] = trace_id
            traces.append(trace)
            seen.add(trace_id)
    return traces


def deduplicate_actor_traces(
    traces: Sequence[dict[str, Any]], *, similarity_threshold: float = 0.995
) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for trace in traces:
        text = canonical_json(
            {key: value for key, value in trace.items() if key != "id"}
        )
        if any(
            SequenceMatcher(
                None,
                text,
                canonical_json(
                    {key: value for key, value in other.items() if key != "id"}
                ),
            ).ratio()
            >= similarity_threshold
            and _jaccard(
                text,
                canonical_json(
                    {key: value for key, value in other.items() if key != "id"}
                ),
            )
            >= similarity_threshold
            for other in kept
        ):
            continue
        kept.append(trace)
    return kept


def parse_trace_validation(text: str) -> dict[str, Any]:
    value = _extract_json(text)
    if not isinstance(value, dict):
        raise ValueError("Trace validation must be a JSON object")
    valid_ids = value.get("valid_ids", [])
    clusters = value.get("clusters", [])
    if not isinstance(valid_ids, list) or not all(
        isinstance(item, str) for item in valid_ids
    ):
        raise ValueError("Trace validation valid_ids must be a string array")
    if not isinstance(clusters, list):
        raise ValueError("Trace validation clusters must be an array")
    return {
        "valid_ids": valid_ids,
        "clusters": [item for item in clusters if isinstance(item, dict)],
        "defects": value.get("defects", {}),
    }


def select_actor_traces(
    traces: Sequence[dict[str, Any]],
    validation: Mapping[str, Any],
    *,
    count: int = 8,
) -> list[dict[str, Any]]:
    """Round-robin clusters, then greedily maximize lexical distance."""

    by_id = {str(trace["id"]): trace for trace in traces}
    valid_ids = [item for item in validation.get("valid_ids", []) if item in by_id]
    if len(valid_ids) < count:
        raise ValueError(f"Fast validation left {len(valid_ids)} valid traces; need {count}")

    clusters: list[list[str]] = []
    assigned: set[str] = set()
    for cluster in validation.get("clusters", []):
        ids = [
            item
            for item in cluster.get("trace_ids", [])
            if item in by_id and item in valid_ids and item not in assigned
        ]
        if ids:
            clusters.append(ids)
            assigned.update(ids)
    for trace_id in valid_ids:
        if trace_id not in assigned:
            clusters.append([trace_id])

    selected_ids: list[str] = []
    while clusters and len(selected_ids) < count:
        remaining_clusters: list[list[str]] = []
        for cluster in clusters:
            if len(selected_ids) >= count:
                break
            candidates = [item for item in cluster if item not in selected_ids]
            if not candidates:
                continue
            if not selected_ids:
                chosen = candidates[0]
            else:
                chosen = max(
                    candidates,
                    key=lambda item: min(
                        1
                        - _jaccard(
                            canonical_json(by_id[item]),
                            canonical_json(by_id[other]),
                        )
                        for other in selected_ids
                    ),
                )
            selected_ids.append(chosen)
            leftovers = [item for item in candidates if item != chosen]
            if leftovers:
                remaining_clusters.append(leftovers)
        clusters = remaining_clusters
    if len(selected_ids) < count:
        raise ValueError(f"Could select only {len(selected_ids)} diverse traces")
    return [by_id[item] for item in selected_ids]


def run_actor_novelist(
    *,
    generator_client: CompletionClient,
    fast_client: CompletionClient,
    config: RunConfig,
    scene: SceneSpec,
    personas: Sequence[PersonaPacket],
    shared_prefix: str,
    run_dir: Path,
    count: int = 8,
) -> list[Candidate]:
    """Pipeline C: behavioral simulation, fast validation, prose realization."""

    if len(config.seeds) < count:
        raise ValueError(f"Actor–Novelist pipeline requires at least {count} seeds")
    store = TraceStore(run_dir)
    sampling = _sampling(config)
    actor_dynamic = _prompt("actor_trace.txt").format()
    actor_prompt = stable_prompt(shared_prefix, actor_dynamic)
    actor_call_id = f"{config.run_id}-actor-traces"
    active_actor_prompt = actor_prompt
    actor_error: Exception | None = None
    traces: list[dict[str, Any]] = []
    for attempt in range(3):
        active_call_id = (
            actor_call_id if attempt == 0 else f"{actor_call_id}-repair-{attempt}"
        )
        actor_result = _call(
            generator_client,
            store,
            call_id=active_call_id,
            role="actor",
            prompt=active_actor_prompt,
            seed=(config.seeds[0] ^ 0xAC70) ^ (attempt * 0x5A17),
            max_tokens=min(config.output_tokens, 10_240),
            **sampling,
        )
        try:
            traces = parse_actor_traces(
                actor_result["content"],
                require_profile_coordinates=bool(config.resolved_profile_hash),
            )
            if len(traces) != 12:
                raise ValueError(
                    "Actor must return twelve valid structured traces; "
                    f"got {len(traces)}"
                )
            distinct_traces = deduplicate_actor_traces(traces)
            if len(distinct_traces) != 12:
                raise ValueError(
                    "Actor returned only "
                    f"{len(distinct_traces)} behaviorally distinct traces"
                )
            actor_error = None
            actor_call_id = active_call_id
            break
        except ValueError as exc:
            actor_error = exc
            active_actor_prompt = _repair_prompt(
                shared_prefix,
                actor_dynamic,
                prior_output=actor_result["content"],
                error_message=str(exc),
            )
    if actor_error is not None:
        raise ValueError(
            "Actor traces remained invalid after two repair attempts"
        ) from actor_error

    validation_dynamic_base = (
        _prompt("validate_actor_traces.txt").format()
        + "\n\nACTOR TRACES\n"
        + json.dumps({"traces": traces}, ensure_ascii=False, sort_keys=True, indent=2)
    )
    validation_prompt = stable_prompt(shared_prefix, validation_dynamic_base)
    validation_call_id = f"{config.run_id}-validate-traces"
    active_validation_prompt = validation_prompt
    validation_error: Exception | None = None
    validation: dict[str, Any] = {}
    selected: list[dict[str, Any]] = []
    for attempt in range(3):
        active_validation_call_id = (
            validation_call_id
            if attempt == 0
            else f"{validation_call_id}-repair-{attempt}"
        )
        validation_result = _call(
            fast_client,
            store,
            call_id=active_validation_call_id,
            role="fast_judge",
            prompt=active_validation_prompt,
            seed=(config.seeds[0] ^ 0xE4B) ^ (attempt * 0x5A17),
            max_tokens=4_096,
            temperature=0.2,
            top_p=0.9,
            min_p=0.0,
        )
        try:
            validation = parse_trace_validation(validation_result["content"])
            selected = select_actor_traces(traces, validation, count=count)
            validation_error = None
            validation_call_id = active_validation_call_id
            break
        except ValueError as exc:
            validation_error = exc
            active_validation_prompt = _repair_prompt(
                shared_prefix,
                validation_dynamic_base,
                prior_output=validation_result["content"],
                error_message=str(exc),
            )
    if validation_error is not None:
        raise ValueError(
            "Trace validation remained invalid after two repair attempts"
        ) from validation_error
    selected_ids = {str(item["id"]) for item in selected}
    recorded_trace_ids = {
        str(item.get("trace_id"))
        for item in TraceStore.read(store.actor_traces_path)
        if item.get("pipeline") == ACTOR_NOVELIST_PIPELINE
    }
    for trace in traces:
        if str(trace["id"]) in recorded_trace_ids:
            continue
        store.append_actor_trace(
            {
                "trace_id": trace["id"],
                "pipeline": ACTOR_NOVELIST_PIPELINE,
                "status": "selected" if trace["id"] in selected_ids else "not_selected",
                "trace": trace,
                "validation_defects": validation.get("defects", {}).get(
                    trace["id"], []
                )
                if isinstance(validation.get("defects"), dict)
                else [],
            }
        )

    evidence_ids = _source_ids(scene, personas)
    template = _prompt("novelist.txt")
    candidates: list[Candidate] = []
    for index, (trace, seed) in enumerate(zip(selected, config.seeds[:count]), 1):
        candidate_id = f"{config.run_id}-actor-novelist-{index:02d}"
        prior = store.completed_candidate(candidate_id)
        if prior:
            candidates.append(_candidate_from_record(prior, config))
            continue
        dynamic = template.format(
            **_scene_bounds(scene),
            trace_json=json.dumps(trace, ensure_ascii=False, sort_keys=True, indent=2),
        )
        prompt = stable_prompt(shared_prefix, dynamic)
        call_id = f"{candidate_id}-novelist"
        result = _call(
            generator_client,
            store,
            call_id=call_id,
            role="novelist",
            prompt=prompt,
            seed=seed,
            max_tokens=config.output_tokens,
            **sampling,
        )
        candidate = _candidate(
            config=config,
            pipeline=ACTOR_NOVELIST_PIPELINE,
            candidate_id=candidate_id,
            seed=seed,
            text=result["content"],
            parent_trace=trace,
            evidence_ids=evidence_ids,
            result=result,
            prompt_hash=sha256_text(prompt),
            lineage=(
                f"call:{actor_call_id}",
                f"trace:{trace['id']}",
                f"call:{validation_call_id}",
                f"call:{call_id}",
            ),
            store=store,
        )
        _save_candidate(store, candidate)
        candidates.append(candidate)
    return candidates


def run_pipeline(
    pipeline: str,
    *,
    generator_client: CompletionClient,
    config: RunConfig,
    scene: SceneSpec,
    personas: Sequence[PersonaPacket],
    shared_prefix: str,
    run_dir: Path,
    fast_client: CompletionClient | None = None,
    count: int = 8,
) -> list[Candidate]:
    """Dispatch a configured run without importing the CLI."""

    normalized = pipeline.casefold().replace("-", "_")
    if normalized in {"direct", "best_of_n"}:
        return run_direct(
            client=generator_client,
            config=config,
            scene=scene,
            personas=personas,
            shared_prefix=shared_prefix,
            run_dir=run_dir,
            count=count,
        )
    if normalized in {"verbalized", "verbalized_sampling", "vs"}:
        return run_verbalized_sampling(
            client=generator_client,
            config=config,
            scene=scene,
            personas=personas,
            shared_prefix=shared_prefix,
            run_dir=run_dir,
            count=count,
        )
    if normalized in {"actor_novelist", "actor"}:
        if fast_client is None:
            raise ValueError("Actor–Novelist requires a fast validation client")
        return run_actor_novelist(
            generator_client=generator_client,
            fast_client=fast_client,
            config=config,
            scene=scene,
            personas=personas,
            shared_prefix=shared_prefix,
            run_dir=run_dir,
            count=count,
        )
    raise ValueError(f"Unknown pipeline: {pipeline}")
