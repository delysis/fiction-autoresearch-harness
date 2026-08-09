"""End-to-end resumable base-ideator/base-writer author workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .anti_copy import AntiCopyIndex
from .author import ResolvedAuthorContext, render_base_writer_prompt
from .author_schemas import StoryProgram
from .core import sha256_text, write_json
from .model_client import LlamaClient
from .runtime import TraceStore, utc_now
from .schemas import Candidate, RunConfig, SceneSpec
from .story_program import (
    PROSE_SAMPLING,
    compile_story_program,
    generate_base_candidate,
    sample_story_proposals,
    select_story_programs,
)


DEFAULT_IDEA_SEEDS = tuple(51_001 + index * 977 for index in range(32))
DEFAULT_PROSE_SEEDS = tuple(71_001 + index * 1_229 for index in range(8))


@dataclass(frozen=True, slots=True)
class AuthorRunResult:
    run_id: str
    proposal_count: int
    program_count: int
    selected_program_ids: tuple[str, ...]
    candidate_ids: tuple[str, ...]
    resolved_profile_hash: str
    author_profile_hash: str
    anti_copy_index_hash: str
    run_dir: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_type": "AuthorRunResult",
            "run_id": self.run_id,
            "proposal_count": self.proposal_count,
            "program_count": self.program_count,
            "selected_program_ids": list(self.selected_program_ids),
            "candidate_ids": list(self.candidate_ids),
            "resolved_profile_hash": self.resolved_profile_hash,
            "author_profile_hash": self.author_profile_hash,
            "anti_copy_index_hash": self.anti_copy_index_hash,
            "run_dir": self.run_dir,
        }


def _completed_programs(store: TraceStore) -> dict[str, StoryProgram]:
    latest: dict[str, StoryProgram] = {}
    for record in TraceStore.read(store.plans_path):
        if record.get("record_type") != StoryProgram.record_type:
            continue
        payload = dict(record)
        payload.pop("validation_errors", None)
        payload.pop("created_at", None)
        try:
            program = StoryProgram.from_dict(payload)
        except (TypeError, ValueError):
            continue
        latest[program.story_program_id] = program
    return latest


def _completed_candidate(
    store: TraceStore, candidate_id: str
) -> Candidate | None:
    record = store.completed_candidate(candidate_id)
    if not record:
        return None
    payload = dict(record)
    for key in ("status", "created_at", "finished_at"):
        payload.pop(key, None)
    return Candidate.from_dict(payload)


def build_author_run_config(
    *,
    run_id: str,
    scene: SceneSpec,
    program: StoryProgram,
    prefix_hash: str,
    source_hashes: Mapping[str, str],
    resolved_creative_profile: Mapping[str, Any],
    author_context: ResolvedAuthorContext,
    anti_copy_index: AntiCopyIndex,
    seed: int,
    output_tokens: int,
    frontier_adapter: str,
) -> RunConfig:
    return RunConfig(
        run_id=run_id,
        scene_id=scene.scene_id,
        pipeline="author-base-writer",
        model_role="base_writer",
        prompt_hash=prefix_hash,
        source_hashes=dict(source_hashes),
        seeds=(seed,),
        sampling=dict(PROSE_SAMPLING),
        output_words_min=scene.target_words_min,
        output_words_max=scene.target_words_max,
        output_tokens=output_tokens,
        created_at=utc_now(),
        ontology_version=str(resolved_creative_profile["ontology_version"]),
        story_profile_id=str(resolved_creative_profile["story_profile_id"]),
        scene_profile_id=str(resolved_creative_profile["scene_profile_id"]),
        resolved_profile_hash=str(resolved_creative_profile["profile_hash"]),
        author_profile_id=author_context.author_profile_id,
        author_profile_hash=author_context.author_profile_hash,
        corpus_manifest_hash=author_context.corpus_manifest_hash,
        transformation_map_hash=author_context.transformation_map_hash,
        conditioning_variant=author_context.conditioning_variant,
        prompt_encoding=author_context.prompt_encoding,
        control_density=author_context.control_density,
        story_program_id=program.story_program_id,
        anti_copy_policy_version=anti_copy_index.policy.version,
        anti_copy_index_hash=anti_copy_index.index_hash,
        frontier_adapter=frontier_adapter,
    )


def run_author_base_pipeline(
    *,
    ideator: LlamaClient,
    compiler: LlamaClient,
    writer: LlamaClient,
    scene: SceneSpec,
    resolved_creative_profile: Mapping[str, Any],
    gabaldon_profile: Mapping[str, Any],
    author_context: ResolvedAuthorContext,
    story_canon: Mapping[str, Any],
    source_hashes: Mapping[str, str],
    anti_copy_index: AntiCopyIndex,
    run_dir: str | Path,
    run_id: str,
    idea_seeds: Sequence[int] = DEFAULT_IDEA_SEEDS,
    prose_seeds: Sequence[int] = DEFAULT_PROSE_SEEDS,
    candidate_count: int = 8,
    output_tokens: int = 6_144,
    frontier_adapter: str = "none-local",
) -> AuthorRunResult:
    """Run the approved base → compiler → base workflow with safe resume."""

    if candidate_count > len(prose_seeds):
        raise ValueError("not enough declared prose seeds")
    if len(idea_seeds) < candidate_count:
        raise ValueError("idea count must be at least candidate count")
    store = TraceStore(Path(run_dir))
    proposals = sample_story_proposals(
        ideator,
        scene,
        author_context,
        seeds=idea_seeds,
        trace_store=store,
    )
    allowed_coordinates = tuple(
        str(item)
        for item in resolved_creative_profile.get("selected_coordinates", ())
    )
    completed = _completed_programs(store)
    programs: list[StoryProgram] = []
    for proposal in proposals:
        program_id = str(proposal["proposal_id"]).replace(
            "story-idea", "story-program"
        )
        prior = completed.get(program_id)
        if prior:
            if (
                prior.author_profile_hash != author_context.author_profile_hash
                or prior.resolved_profile_hash
                != str(resolved_creative_profile["profile_hash"])
            ):
                raise ValueError(
                    f"refusing to resume {program_id}: profile hash changed"
                )
            programs.append(prior)
            continue
        programs.append(
            compile_story_program(
                compiler,
                scene=scene,
                proposal=proposal,
                author_profile_hash=author_context.author_profile_hash,
                resolved_profile_hash=str(
                    resolved_creative_profile["profile_hash"]
                ),
                allowed_coordinates=allowed_coordinates,
                trace_store=store,
            )
        )
    selected = select_story_programs(programs, count=candidate_count)
    dummy_input = {
        "scene": scene.to_dict(),
        "story_program": {},
        "instruction": "Write finished fiction.",
    }
    prefix, _ = render_base_writer_prompt(
        creative_profile=resolved_creative_profile,
        gabaldon_profile=gabaldon_profile,
        author_context=author_context,
        story_canon=story_canon,
        scene_input=dummy_input,
    )
    prefix_hash = sha256_text(prefix)
    candidates: list[Candidate] = []
    configs: list[dict[str, Any]] = []
    for index, (program, seed) in enumerate(
        zip(selected, prose_seeds), 1
    ):
        candidate_id = f"{run_id}.candidate-{index:02d}"
        config = build_author_run_config(
            run_id=run_id,
            scene=scene,
            program=program,
            prefix_hash=prefix_hash,
            source_hashes=source_hashes,
            resolved_creative_profile=resolved_creative_profile,
            author_context=author_context,
            anti_copy_index=anti_copy_index,
            seed=int(seed),
            output_tokens=output_tokens,
            frontier_adapter=frontier_adapter,
        )
        configs.append(config.to_dict())
        prior_candidate = _completed_candidate(store, candidate_id)
        if prior_candidate:
            expected = (
                author_context.author_profile_hash,
                str(resolved_creative_profile["profile_hash"]),
                anti_copy_index.index_hash,
                program.story_program_id,
            )
            observed = (
                prior_candidate.author_profile_hash,
                prior_candidate.resolved_profile_hash,
                prior_candidate.anti_copy_index_hash,
                prior_candidate.story_program_id,
            )
            if observed != expected:
                raise ValueError(
                    f"refusing to resume {candidate_id}: lineage changed"
                )
            candidates.append(prior_candidate)
            continue
        candidates.append(
            generate_base_candidate(
                writer,
                config=config,
                scene=scene,
                program=program,
                author_context=author_context,
                creative_profile=resolved_creative_profile,
                gabaldon_profile=gabaldon_profile,
                story_canon=story_canon,
                anti_copy_index=anti_copy_index,
                trace_store=store,
                seed=int(seed),
                candidate_id=candidate_id,
            )
        )
    write_json(
        Path(run_dir) / "author_run_manifest.json",
        {
            "record_type": "AuthorRunManifest",
            "run_id": run_id,
            "author_context": author_context.to_dict(),
            "anti_copy_index": anti_copy_index.manifest(),
            "selected_story_programs": [
                program.to_dict() for program in selected
            ],
            "run_configs": configs,
            "candidate_ids": [item.candidate_id for item in candidates],
            "created_at": utc_now(),
        },
    )
    result = AuthorRunResult(
        run_id=run_id,
        proposal_count=len(proposals),
        program_count=len(programs),
        selected_program_ids=tuple(
            item.story_program_id for item in selected
        ),
        candidate_ids=tuple(item.candidate_id for item in candidates),
        resolved_profile_hash=str(
            resolved_creative_profile["profile_hash"]
        ),
        author_profile_hash=author_context.author_profile_hash,
        anti_copy_index_hash=anti_copy_index.index_hash,
        run_dir=str(Path(run_dir)),
    )
    write_json(Path(run_dir) / "author_run_result.json", result.to_dict())
    return result
