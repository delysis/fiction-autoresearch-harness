"""Base-model story-program sampling, compilation, selection, and drafting."""

from __future__ import annotations

from dataclasses import replace
import json
import re
from typing import Any, Mapping, Sequence

from .anti_copy import AntiCopyIndex, SourceOverlapError, StreamingNgramGuard
from .author import ResolvedAuthorContext, draft_lead, render_base_writer_prompt
from .author_schemas import StoryProgram
from .authorship import proof_carrying_model_authorship, text_sha256
from .core import canonical_json_text, hash_json, sha256_text
from .model_client import LlamaClient
from .runtime import TraceStore, model_runtime_provenance, utc_now
from .schemas import Candidate, RunConfig, SceneSpec


METADATA_SAMPLING = {
    "temperature": 1.1,
    "top_p": 0.98,
    "min_p": 0.01,
    "xtc_probability": 0.10,
}
PROSE_SAMPLING = {
    "temperature": 0.9,
    "top_p": 0.95,
    "min_p": 0.02,
    "xtc_probability": 0.05,
}
PROGRAM_FIELDS = (
    "premise",
    "event_sequence",
    "relationship_delta",
    "realized_coordinates",
    "dialogue_strategy",
    "intimacy_strategy",
    "continuity_facts",
)


def _json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fenced = re.search(
        r"```(?:json)?\s*(\{.*\})\s*```",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if fenced:
        cleaned = fenced.group(1)
    else:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start : end + 1]
    value = json.loads(cleaned)
    if not isinstance(value, dict):
        raise ValueError("story-program compiler must return a JSON object")
    return value


def story_idea_prompt(
    scene: SceneSpec,
    author_context: ResolvedAuthorContext,
    *,
    sample_number: int,
) -> str:
    """Return a light continuation-style prompt for the genuine base model."""

    return (
        "<story_idea_collection>\n"
        "<purpose>Discover a surprising but canon-compatible way to realize "
        "the scene. Prefer specific causal choices over generic prestige, "
        "occupations, names, or settings.</purpose>\n"
        f"<scene_id>{scene.scene_id}</scene_id>\n"
        f"<desire>{scene.desire}</desire>\n"
        f"<obstacle>{scene.obstacle}</obstacle>\n"
        f"<turn>{scene.turn}</turn>\n"
        f"<aftermath>{scene.aftermath}</aftermath>\n"
        "<author_context_hash>"
        f"{author_context.context_hash}"
        "</author_context_hash>\n"
        f"<sample_number>{sample_number}</sample_number>\n"
        "<idea>\n"
    )


def sample_story_proposals(
    client: LlamaClient,
    scene: SceneSpec,
    author_context: ResolvedAuthorContext,
    *,
    seeds: Sequence[int],
    trace_store: TraceStore | None = None,
    max_tokens: int = 768,
) -> tuple[dict[str, Any], ...]:
    """Sample unstructured proposals from the base model."""

    proposals: list[dict[str, Any]] = []
    for index, seed in enumerate(seeds, 1):
        call_id = f"story-idea-{scene.scene_id}-{index:02d}-{seed}"
        if trace_store:
            prior = trace_store.completed_call(call_id)
            if prior:
                result = prior.get("result", {})
                proposals.append(
                    {
                        "proposal_id": call_id,
                        "seed": seed,
                        "text": str(result.get("content", "")),
                        "prompt_hash": str(prior.get("prompt_hash", "")),
                        "resumed": True,
                    }
                )
                continue
        prompt = story_idea_prompt(
            scene, author_context, sample_number=index
        )
        if trace_store:
            trace_store.append_call(
                {
                    "call_id": call_id,
                    "stage": "base_story_ideation",
                    "status": "started",
                    "seed": seed,
                    "prompt_hash": sha256_text(prompt),
                    "created_at": utc_now(),
                }
            )
        completion = client.complete_raw(
            prompt=prompt,
            seed=seed,
            max_tokens=max_tokens,
            **METADATA_SAMPLING,
        )
        record = {
            "proposal_id": call_id,
            "seed": seed,
            "text": completion.content.strip(),
            "prompt_hash": sha256_text(prompt),
            "telemetry": completion.to_dict(),
            "resumed": False,
        }
        proposals.append(record)
        if trace_store:
            trace_store.append_call(
                {
                    "call_id": call_id,
                    "stage": "base_story_ideation",
                    "status": "completed",
                    "seed": seed,
                    "prompt_hash": record["prompt_hash"],
                    "result": completion.to_dict(),
                    "created_at": utc_now(),
                }
            )
    return tuple(proposals)


def story_program_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "premise": {"type": "string"},
            "event_sequence": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 4,
            },
            "relationship_delta": {"type": "string"},
            "realized_coordinates": {
                "type": "array",
                "items": {"type": "string"},
            },
            "dialogue_strategy": {"type": "string"},
            "intimacy_strategy": {"type": "string"},
            "continuity_facts": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": list(PROGRAM_FIELDS),
        "additionalProperties": False,
    }


def validate_compiled_program(
    value: Mapping[str, Any],
    *,
    allowed_coordinates: Sequence[str],
) -> tuple[str, ...]:
    errors: list[str] = []
    for field in PROGRAM_FIELDS:
        if field not in value:
            errors.append(f"missing {field}")
    for field in (
        "premise",
        "relationship_delta",
        "dialogue_strategy",
        "intimacy_strategy",
    ):
        if not isinstance(value.get(field), str) or not str(value.get(field)).strip():
            errors.append(f"{field} must be a non-empty string")
    events = value.get("event_sequence")
    if not isinstance(events, list) or len(events) < 4:
        errors.append("event_sequence must contain at least four beats")
    for field in ("realized_coordinates", "continuity_facts"):
        if not isinstance(value.get(field), list) or any(
            not isinstance(item, str) for item in value.get(field, [])
        ):
            errors.append(f"{field} must be a string list")
    allowed = set(allowed_coordinates)
    unknown = sorted(set(value.get("realized_coordinates", ())) - allowed)
    if unknown:
        errors.append(f"unknown realized coordinates: {unknown}")
    return tuple(dict.fromkeys(errors))


def _compiler_prompt(
    *,
    scene: SceneSpec,
    proposal: str,
    allowed_coordinates: Sequence[str],
    repair_errors: Sequence[str] = (),
) -> str:
    repair = (
        "\nREPAIR ONLY THESE ERRORS:\n- " + "\n- ".join(repair_errors)
        if repair_errors
        else ""
    )
    return (
        "Compile the base model's proposal into the supplied StoryProgram "
        "schema. Preserve unusual choices and wording as data; do not add new "
        "events, occupations, names, or twists. Coordinates must be chosen "
        "only from ALLOWED_COORDINATES. Return JSON only."
        f"{repair}\n\n"
        f"SCENE:\n{canonical_json_text(scene.to_dict())}\n"
        f"ALLOWED_COORDINATES:\n{canonical_json_text(list(allowed_coordinates))}\n"
        f"RAW_PROPOSAL:\n{proposal}"
    )


def compile_story_program(
    compiler: LlamaClient,
    *,
    scene: SceneSpec,
    proposal: Mapping[str, Any],
    author_profile_hash: str,
    resolved_profile_hash: str,
    allowed_coordinates: Sequence[str],
    trace_store: TraceStore | None = None,
    max_tokens: int = 1_536,
) -> StoryProgram:
    proposal_id = str(proposal["proposal_id"])
    prompt = _compiler_prompt(
        scene=scene,
        proposal=str(proposal["text"]),
        allowed_coordinates=allowed_coordinates,
    )
    response = compiler.complete(
        prompt=prompt,
        seed=int(proposal["seed"]) + 10_000,
        max_tokens=max_tokens,
        temperature=0.1,
        top_p=0.95,
        min_p=0.01,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "story_program",
                "schema": story_program_schema(),
            },
        },
    )
    repairs: list[Mapping[str, Any]] = []
    try:
        compiled = _json_object(response.content)
        errors = validate_compiled_program(
            compiled, allowed_coordinates=allowed_coordinates
        )
    except (ValueError, json.JSONDecodeError) as exc:
        compiled = {}
        errors = (str(exc),)
    if errors:
        repair_prompt = _compiler_prompt(
            scene=scene,
            proposal=str(proposal["text"]),
            allowed_coordinates=allowed_coordinates,
            repair_errors=errors,
        )
        repaired = compiler.complete(
            prompt=repair_prompt,
            seed=int(proposal["seed"]) + 20_000,
            max_tokens=max_tokens,
            temperature=0.0,
            top_p=1.0,
            min_p=0.0,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "story_program",
                    "schema": story_program_schema(),
                },
            },
        )
        compiled = _json_object(repaired.content)
        repairs.append(
            {
                "errors": list(errors),
                "prompt_hash": sha256_text(repair_prompt),
                "model": repaired.model,
            }
        )
        errors = validate_compiled_program(
            compiled, allowed_coordinates=allowed_coordinates
        )
    program = StoryProgram(
        story_program_id=proposal_id.replace("story-idea", "story-program"),
        scene_id=scene.scene_id,
        raw_proposal=str(proposal["text"]),
        compiled_program=compiled,
        repairs=tuple(repairs),
        selected_coordinates=tuple(
            str(item) for item in compiled.get("realized_coordinates", ())
        ),
        lineage=(proposal_id, sha256_text(prompt)),
        author_profile_hash=author_profile_hash,
        resolved_profile_hash=resolved_profile_hash,
        valid=not errors,
    )
    if trace_store:
        trace_store.append_plan(
            {
                **program.to_dict(),
                "validation_errors": list(errors),
                "created_at": utc_now(),
            }
        )
    return program


def _program_tokens(program: StoryProgram) -> set[str]:
    return {
        token
        for token in re.findall(
            r"\b[\w'-]+\b",
            canonical_json_text(program.compiled_program).casefold(),
        )
        if len(token) > 2
    }


def select_story_programs(
    programs: Sequence[StoryProgram],
    *,
    count: int = 8,
) -> tuple[StoryProgram, ...]:
    """Greedy quality-diversity selection over valid structured programs."""

    valid = [program for program in programs if program.valid]
    if len(valid) < count:
        raise ValueError(
            f"only {len(valid)} valid story programs; {count} required"
        )
    selected: list[StoryProgram] = []
    remaining = sorted(valid, key=lambda item: item.story_program_id)
    while remaining and len(selected) < count:
        best: tuple[float, StoryProgram] | None = None
        for program in remaining:
            data = program.compiled_program
            completeness = sum(bool(data.get(field)) for field in PROGRAM_FIELDS)
            coordinates = len(set(program.selected_coordinates))
            novelty = 1.0
            if selected:
                tokens = _program_tokens(program)
                similarities = []
                for prior in selected:
                    prior_tokens = _program_tokens(prior)
                    union = tokens | prior_tokens
                    similarities.append(
                        len(tokens & prior_tokens) / len(union) if union else 1.0
                    )
                novelty = 1.0 - max(similarities)
            score = completeness + min(coordinates, 4) * 0.2 + novelty * 2
            candidate = (score, program)
            if best is None or candidate[0] > best[0] or (
                candidate[0] == best[0]
                and program.story_program_id < best[1].story_program_id
            ):
                best = candidate
        assert best is not None
        selected.append(best[1])
        remaining.remove(best[1])
    return tuple(selected)


def author_lineage(
    config: RunConfig,
) -> dict[str, str]:
    return {
        key: str(getattr(config, key))
        for key in (
            "author_profile_id",
            "author_profile_hash",
            "corpus_manifest_hash",
            "transformation_map_hash",
            "conditioning_variant",
            "prompt_encoding",
            "control_density",
            "story_program_id",
            "anti_copy_policy_version",
            "anti_copy_index_hash",
            "frontier_adapter",
        )
    }


def generate_base_candidate(
    client: LlamaClient,
    *,
    config: RunConfig,
    scene: SceneSpec,
    program: StoryProgram,
    author_context: ResolvedAuthorContext,
    creative_profile: Mapping[str, Any],
    gabaldon_profile: Mapping[str, Any],
    story_canon: Mapping[str, Any],
    anti_copy_index: AntiCopyIndex,
    trace_store: TraceStore,
    seed: int,
    candidate_id: str,
    max_retries: int = 2,
) -> Candidate:
    if config.story_program_id != program.story_program_id:
        raise ValueError("run config and story program IDs differ")
    if config.author_profile_hash != program.author_profile_hash:
        raise ValueError("run config and story program author hashes differ")
    scene_input = {
        "scene": scene.to_dict(),
        "story_program": program.compiled_program,
        "output_words": {
            "minimum": config.output_words_min,
            "maximum": config.output_words_max,
        },
        "instruction": (
            "Continue with finished fiction only. Preserve the program's causal "
            "choices without naming controls, profiles, ontologies, or authors."
        ),
    }
    prefix, dynamic = render_base_writer_prompt(
        creative_profile=creative_profile,
        gabaldon_profile=gabaldon_profile,
        author_context=author_context,
        story_canon=story_canon,
        scene_input=scene_input,
    )
    prompt = prefix + "\n" + dynamic
    lead = draft_lead(scene_input)
    if config.prompt_hash != sha256_text(prefix):
        raise ValueError("run config stable-prefix hash differs from prompt")
    attempts: list[Mapping[str, Any]] = []
    for retry in range(max_retries + 1):
        attempt_seed = seed + retry * 100_000
        call_id = f"{candidate_id}-attempt-{retry + 1}"
        prompt_dir = trace_store.run_dir / "prompts"
        prompt_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = prompt_dir / f"{call_id}.txt"
        if prompt_path.is_file():
            if sha256_text(prompt_path.read_text(encoding="utf-8")) != sha256_text(prompt):
                raise ValueError(f"refusing prompt-byte drift for {call_id}")
        else:
            prompt_path.write_text(prompt, encoding="utf-8")
        parameters = {
            "seed": attempt_seed,
            "max_tokens": config.output_tokens,
            **PROSE_SAMPLING,
        }
        call_base = {
            "call_id": call_id,
            "stage": "base_prose_generation",
            "model": str(getattr(client, "model", "local-model")),
            "runtime": model_runtime_provenance(
                str(getattr(client, "model", "local-model"))
            ),
            "prompt_hash": sha256_text(prompt),
            "prompt_path": str(prompt_path.resolve()),
            "transport": "raw_completion",
            "parameters": parameters,
            "author_lineage": author_lineage(config),
        }
        prior = trace_store.completed_call(call_id)
        if prior:
            result = prior.get("result", {})
            raw_text = str(result.get("content", ""))
            text = lead + raw_text
            completion_data = dict(result)
        else:
            trace_store.append_call(
                {
                    **call_base,
                    "status": "started",
                    "created_at": utc_now(),
                }
            )
            guard = StreamingNgramGuard(anti_copy_index)
            try:
                completion = client.stream_raw(
                    prompt=prompt,
                    seed=attempt_seed,
                    max_tokens=config.output_tokens,
                    on_delta=guard.feed,
                    **PROSE_SAMPLING,
                )
            except SourceOverlapError as exc:
                attempt = {
                    "call_id": call_id,
                    "status": "rejected_source_overlap",
                    "seed": attempt_seed,
                    "match": exc.match,
                }
                attempts.append(attempt)
                trace_store.append_call(
                    {
                        **call_base,
                        **attempt,
                        "created_at": utc_now(),
                    }
                )
                continue
            text = lead + completion.content
            completion_data = completion.to_dict()
            trace_store.append_call(
                {
                    **call_base,
                    "status": "completed",
                    "result": completion_data,
                    "created_at": utc_now(),
                }
            )
        overlap = anti_copy_index.check(candidate_id, text)
        if overlap.hard_fail or overlap.unresolved_flags:
            attempts.append(
                {
                    "call_id": call_id,
                    "status": "rejected_postflight_overlap",
                    "seed": attempt_seed,
                    "overlap": overlap.to_dict(),
                }
            )
            continue
        candidate_prompt_hash = sha256_text(prompt)
        candidate_created_at = utc_now()
        candidate = Candidate(
            candidate_id=candidate_id,
            run_id=config.run_id,
            pipeline=config.pipeline,
            scene_id=scene.scene_id,
            seed=attempt_seed,
            text=text,
            parent_trace={
                "story_program": program.to_dict(),
                "attempts": attempts,
                "overlap_report": overlap.to_dict(),
            },
            evidence_ids=(),
            telemetry=completion_data,
            lineage=(
                program.story_program_id,
                program.program_hash,
                author_context.context_hash,
            ),
            prompt_hash=candidate_prompt_hash,
            ontology_version=config.ontology_version,
            story_profile_id=config.story_profile_id,
            scene_profile_id=config.scene_profile_id,
            resolved_profile_hash=config.resolved_profile_hash,
            artifact_authorship=proof_carrying_model_authorship(
                artifact_id=candidate_id,
                text=text,
                model_id=str(getattr(client, "model", "local-model")),
                call_id=call_id,
                prompt_hash=candidate_prompt_hash,
                seed=attempt_seed,
                call_ledger_path=trace_store.calls_path,
                derivation={
                    "operation": "literal_prefix_plus_raw",
                    "literal_prefix": lead,
                    "literal_prefix_origin": "locked_canon_fragment",
                    "literal_prefix_sha256": text_sha256(lead),
                },
                created_at=candidate_created_at,
            ),
            **author_lineage(config),
        )
        trace_store.append_candidate(
            {
                **candidate.to_dict(),
                "status": "completed",
                "created_at": candidate_created_at,
            }
        )
        return candidate
    raise RuntimeError(
        f"{candidate_id} exhausted {max_retries + 1} anti-copy attempts"
    )


def with_story_program(config: RunConfig, program: StoryProgram) -> RunConfig:
    """Return an author run config bound to one immutable story program."""

    return replace(config, story_program_id=program.story_program_id)
