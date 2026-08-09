"""Command-line interface for the local Gemma 4 fiction laboratory."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping, Sequence

from .anti_copy import AntiCopyIndex, build_anti_copy_index
from .apprenticeship import (
    compile_prompt as apprenticeship_compile_prompt,
    compile_scene_index as apprenticeship_compile_index,
    fetch_declared_sources as apprenticeship_fetch_sources,
    load_query as apprenticeship_load_query,
    retrieve_scenes as apprenticeship_retrieve_scenes,
)
from .appraisal import (
    build_appraisal as build_blind_appraisal,
    build_internal_report as build_appraisal_internal_report,
)
from .author import (
    compile_source_segments,
    load_author_profile,
    load_corpus_manifest,
    load_transformation_map,
    render_prompt_payload,
    resolve_author_context,
    validate_affordance_provenance,
    validate_corpus_files,
    validate_profile_against_manifest,
    validate_transformation_map,
)
from .author_experiments import (
    calibration_design,
    full_s01_design,
    verify_shared_story_programs,
)
from .author_evaluation import (
    author_judge_prompt,
    distribution_diagnostics,
    novelty_diagnostics,
    parse_author_judgment,
)
from .author_workflow import (
    DEFAULT_IDEA_SEEDS,
    DEFAULT_PROSE_SEEDS,
    run_author_base_pipeline,
)
from .autoresearch import (
    DEFAULT_SOURCE as DEFAULT_AUTORESEARCH_SOURCE,
    admit_research_review as autoresearch_admit_research_review,
    admit_reviews as autoresearch_admit_reviews,
    adjudicate_overlap_flags as autoresearch_adjudicate_overlap_flags,
    analyze_traces as autoresearch_analyze_traces,
    campaign_init as autoresearch_campaign_init,
    compile_benchmarks as autoresearch_compile_benchmarks,
    compile_corpus as autoresearch_compile_corpus,
    decide_round as autoresearch_decide_round,
    export_blind_review as autoresearch_export_review,
    package_human_finalists as autoresearch_package_human_finalists,
    render_report as autoresearch_render_report,
    run_round1 as autoresearch_run_round1,
)
from .autoresearch_v4 import (
    SamplerV4 as autoresearch_v4_SamplerV4,
    annotate_corpus_source_graphs as autoresearch_v4_annotate_corpus_source_graphs,
    admit_v4_research_review as autoresearch_v4_admit_research_review,
    analyze_v4_traces as autoresearch_v4_analyze_traces,
    audit_v4_assemblies as autoresearch_v4_audit_assemblies,
    cold_replay_v4_call as autoresearch_v4_cold_replay_call,
    freeze_behavioral_recipes as autoresearch_v4_freeze_behavioral_recipes,
    freeze_context_recipes as autoresearch_v4_freeze_context_recipes,
    freeze_sampler_recipes as autoresearch_v4_freeze_sampler_recipes,
    derive_verified_runway_prefix as autoresearch_v4_derive_verified_runway_prefix,
    inherit_verified_runways as autoresearch_v4_inherit_verified_runways,
    init_campaign as autoresearch_v4_init_campaign,
    merge_apprenticeship_retrievals as autoresearch_v4_merge_apprenticeship_retrievals,
    mine_movement_boundary_sparks as autoresearch_v4_mine_movement_boundary_sparks,
    judge_candidates as autoresearch_v4_judge_candidates,
    judge_pairwise_candidates as autoresearch_v4_judge_pairwise_candidates,
    package_finalists as autoresearch_v4_package_finalists,
    open_confirmation_benchmark as autoresearch_v4_open_confirmation_benchmark,
    promote_bootstrap as autoresearch_v4_promote_bootstrap,
    promote_behavioral as autoresearch_v4_promote_behavioral,
    promote_context as autoresearch_v4_promote_context,
    promote_runways as autoresearch_v4_promote_runways,
    promote_sampler as autoresearch_v4_promote_sampler,
    promote_topologies as autoresearch_v4_promote_topologies,
    reextract_phase_candidates as autoresearch_v4_reextract_phase_candidates,
    readmit_movement_audition as autoresearch_v4_readmit_movement_audition,
    revalidate_phase_candidates as autoresearch_v4_revalidate_phase_candidates,
    run_bootstrap as autoresearch_v4_run_bootstrap,
    run_behavioral_search as autoresearch_v4_run_behavioral_search,
    run_branch_loom as autoresearch_v4_run_branch_loom,
    sample_movement_auditions as autoresearch_v4_sample_movement_auditions,
    run_context_search as autoresearch_v4_run_context_search,
    run_sampler_search as autoresearch_v4_run_sampler_search,
    run_staged_topology_search as autoresearch_v4_run_staged_topology_search,
    run_topology_continuation_branches as autoresearch_v4_run_topology_continuation_branches,
    run_topology_search as autoresearch_v4_run_topology_search,
    sample_runways as autoresearch_v4_sample_runways,
    sample_staged_runways as autoresearch_v4_sample_staged_runways,
    sample_s01_trajectories as autoresearch_v4_sample_s01_trajectories,
    seal_benchmark_protocol as autoresearch_v4_seal_benchmark_protocol,
    verify_assembly as autoresearch_v4_verify_assembly,
)
from .autoloom import (
    draft as autoloom_draft,
    init_campaign as autoloom_init_campaign,
    import_approach_selection as autoloom_import_approach_selection,
    import_locked_program_set as autoloom_import_locked_program_set,
    propose_mode_engines as autoloom_propose_mode_engines,
    propose_programs as autoloom_propose_programs,
    propose_transaction_programs as autoloom_propose_transaction_programs,
    replay_causal_programs as autoloom_replay_causal_programs,
    replay_mode_engines as autoloom_replay_mode_engines,
    replay_transaction_candidates as autoloom_replay_transaction_candidates,
    replay_transaction_programs as autoloom_replay_transaction_programs,
    run_staged_autoloom as autoloom_run_staged,
    summarize as autoloom_summarize,
)
from .compiler import compile_trusted_sources
from .continuation import (
    BASE31_PLAN_MODE,
    BASE_PROGRAM_MODE,
    CHAT_DIRECT_MODE,
    CHAT_PLANNED_MODE,
    COMPARISON_VERSION as S02_COMPARISON_VERSION,
    DEFAULT_SEEDS as CONTINUATION_SEEDS,
    GENERATION_MODES,
    INSTRUCTION_PROGRAM_MODES,
    LEGACY_BASE_PROGRAM_MODE,
    NATIVE_BASE_MODE,
    NATIVE_BASE_PLANNED_MODE,
    PRIMARY_COMPARISON_MODES,
    VERBALIZED_MODE,
    adjudicate_verbalized_plan_set,
    canonical_generation_mode,
    compile_story_programs,
    context_manifest,
    continuation_gates,
    judge_and_lock_verbalized_plans,
    make_continuation_run_config,
    prepare_continuation_context,
    propose_story_programs,
    propose_verbalized_story_programs,
    run_continuation_arm,
)
from .continuation_evaluation import (
    accept_editor_revisions,
    aggregate_proof_scores,
    edit_mode_winners,
    judge_proof_candidates,
    tournament_top_two,
)
from .core import atomic_write_text, canonical_json_text, hash_file, hash_json, sha256_text, write_json
from .evaluation import (
    GABALDON_RUBRIC_PATH,
    RUBRIC_PATH,
    S02_RUBRIC_PATH,
    evaluate_candidate,
    load_rubric,
    word_count,
)
from .feedback import (
    bootstrap_feedback_brief,
    build_pairwise_feedback_packets,
    summarize_feedback,
)
from .model_client import LlamaClient
from .pipelines import (
    ACTOR_NOVELIST_PIPELINE,
    DIRECT_PIPELINE,
    VERBALIZED_PIPELINE,
    load_shared_prefix,
    run_pipeline,
)
from .provenance import replay_artifact, verify_candidate_record, write_audit
from .ontology import (
    DEFAULT_ONTOLOGY_PATH,
    DEFAULT_SCENE_PROFILE_PATH,
    DEFAULT_STORY_PROFILE_PATH,
    load_ontology,
    load_scene_profile,
    load_story_profile,
    profile_aware_rubric,
    resolve_profiles,
    write_resolved_profile,
)
from .runtime import (
    LLAMA_SERVER,
    MODEL_PROFILES,
    TraceStore,
    build_base_conversion_command,
    build_server_command,
    preflight,
)
from .shared_endpoint import SharedEndpointAdmission
from .schemas import Candidate
from .workflow import (
    PIPELINES,
    build_internal_report,
    judge_candidates,
    load_candidates,
    load_compiled,
    load_resolved_profile,
    load_source_texts,
    make_run_config,
    package_finalists,
    polish_winners,
    run_pairwise_tournaments,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_COMPILED = PROJECT_ROOT / "03_scene_lab" / "compiled" / "s01-v1"
DEFAULT_ONTOLOGY_COMPILED = (
    PROJECT_ROOT / "03_scene_lab" / "compiled" / "s01-v2-ontology"
)
DEFAULT_RUN_ROOT = PROJECT_ROOT / "03_scene_lab" / "runs" / "s01-comparison-v1"
DEFAULT_EVALUATION = DEFAULT_RUN_ROOT / "evaluation"
DEFAULT_FEEDBACK_ROOT = DEFAULT_RUN_ROOT / "appraisal" / "round1-feedback"
DEFAULT_S02_COMPILED = (
    PROJECT_ROOT / "03_scene_lab" / "compiled" / "s02-v1-ontology"
)
DEFAULT_S02_RUN_ROOT = (
    PROJECT_ROOT / "03_scene_lab" / "runs" / "s02-compute-v4.1-literary"
)
DEFAULT_S02_CONTEXT = DEFAULT_S02_RUN_ROOT / "context"
DEFAULT_S02_VERBALIZED_ADJUDICATION = (
    PROJECT_ROOT
    / "04_review_governance"
    / "s02_v4.1_verbalized_adjudication_policy.v1.json"
)
DEFAULT_PORTS = {
    "base_ideator": 8094,
    "base_writer": 8095,
    "generator": 8091,
    "planner": 8091,
    "editor": 8092,
    "raw_writer": 8096,
    "base_31b_writer": 8097,
    "base_31b_writer_full": 8097,
    "fast_judge": 8093,
}
DEFAULT_AUTHOR_ROOT = PROJECT_ROOT / "fixtures" / "author_control" / "jane_austen"
DEFAULT_AUTHOR_MANIFEST = DEFAULT_AUTHOR_ROOT / "corpus_manifest.v1.json"
DEFAULT_AUTHOR_PROFILE = DEFAULT_AUTHOR_ROOT / "author_profile.v1.json"
DEFAULT_TRANSFORMATION_MAP = (
    DEFAULT_AUTHOR_ROOT / "juicy_chastity_transformation.v1.json"
)
DEFAULT_S02_TRANSFORMATION_MAP = (
    DEFAULT_AUTHOR_ROOT / "juicy_chastity_s02_transformation.v1.json"
)
DEFAULT_AUTHOR_RUN_ROOT = (
    PROJECT_ROOT / "03_scene_lab" / "runs" / "s01-author-control-v1"
)
DEFAULT_AUTORESEARCH_ROOT = (
    PROJECT_ROOT / "03_scene_lab" / "runs" / "prompt-autoresearch-v14-cleanroom"
)
DEFAULT_AUTORESEARCH_COMPILED = (
    PROJECT_ROOT / "04_review_governance" / "prompt_autoresearch" / "compiled-v14-cleanroom"
)
DEFAULT_AUTORESEARCH_BRIDGES = PROJECT_ROOT / "fixtures" / "autoresearch" / "bridges"
DEFAULT_AUTORESEARCH_V4_ROOT = (
    PROJECT_ROOT / "03_scene_lab" / "runs" / "prompt-autoresearch-v15-branch-loom"
)
DEFAULT_AUTOLOOM_ROOT = (
    PROJECT_ROOT / "03_scene_lab" / "runs" / "base-autoloom-v22"
)
PIPELINE_ALIASES = {
    "direct": DIRECT_PIPELINE,
    "verbalized": VERBALIZED_PIPELINE,
    "verbalized_sampling": VERBALIZED_PIPELINE,
    "actor": ACTOR_NOVELIST_PIPELINE,
    "actor_novelist": ACTOR_NOVELIST_PIPELINE,
}


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def _command_preflight(args: argparse.Namespace) -> int:
    report = preflight(
        data_path=Path(args.data_path),
        minimum_free_gb=args.minimum_free_gb,
        full_duplicate_hash=args.full_hash,
    )
    _print_json(report.to_dict())
    return 0 if report.ok else 1


def _candidate_from_path(path: str | Path, candidate_id: str = "") -> dict[str, Any]:
    source = Path(path)
    if source.suffix == ".jsonl":
        values = TraceStore.read(source)
    else:
        value = json.loads(source.read_text(encoding="utf-8"))
        if isinstance(value, Mapping) and isinstance(value.get("finalists"), list):
            values = [item for item in value["finalists"] if isinstance(item, Mapping)]
        elif isinstance(value, Mapping):
            values = [dict(value)]
        else:
            raise ValueError("candidate source must contain an object or finalists list")
    completed = [
        dict(item)
        for item in values
        if isinstance(item, Mapping)
        and (not candidate_id or item.get("candidate_id") == candidate_id)
        and item.get("status", "completed") == "completed"
    ]
    if len(completed) != 1:
        raise ValueError("candidate source must resolve to exactly one completed candidate")
    return completed[0]


def _command_provenance_audit(args: argparse.Namespace) -> int:
    result = write_audit(args.project_root, args.output)
    _print_json(result)
    return 0


def _command_provenance_verify(args: argparse.Namespace) -> int:
    candidate = _candidate_from_path(args.candidate, args.candidate_id)
    verified = verify_candidate_record(candidate, require_replay=not args.without_replay)
    _print_json(
        {
            "candidate_id": candidate.get("candidate_id"),
            "text_sha256": verified["text_sha256"],
            "schema_version": verified["schema_version"],
            "replay_verified": "verified_replay" in verified,
        }
    )
    return 0


def _command_provenance_replay(args: argparse.Namespace) -> int:
    candidate = _candidate_from_path(args.candidate, args.candidate_id)
    authorship = candidate.get("artifact_authorship", {})
    model_id = str(authorship.get("model_call", {}).get("model_id", ""))
    client = LlamaClient(args.url, model=model_id, timeout=args.timeout)
    if not client.health():
        raise RuntimeError(f"Replay model is not healthy: {args.url}")
    witness = replay_artifact(authorship=authorship, client=client)
    _print_json(witness)
    return 0


def _command_compile(args: argparse.Namespace) -> int:
    output = Path(args.output) if args.output else (
        DEFAULT_ONTOLOGY_COMPILED if args.profile else DEFAULT_COMPILED
    )
    result = compile_trusted_sources(
        Path(args.project_root),
        output,
        config_path=Path(args.config) if args.config else None,
        ontology_path=Path(args.ontology) if args.profile else None,
        story_profile_path=Path(args.profile) if args.profile else None,
        scene_profile_path=(
            Path(args.scene_profile) if args.profile and args.scene_profile else None
        ),
    )
    _print_json(
        {
            "output_dir": str(result.output_dir),
            "manifest": str(result.manifest_path),
            "manifest_hash": result.manifest_hash,
            "stable_prefix": str(result.stable_prefix_path),
            "stable_prefix_hash": result.stable_prefix_hash,
            "resolved_profile": (
                str(result.resolved_profile_path)
                if result.resolved_profile_path
                else None
            ),
        }
    )
    return 0


def _command_serve(args: argparse.Namespace) -> int:
    profile = MODEL_PROFILES[args.role]
    command = build_server_command(
        profile,
        port=args.port or DEFAULT_PORTS[args.role],
        host=args.host,
    )
    if args.dry_run:
        _print_json({"command": command, "role": args.role})
        return 0
    os.execv(str(LLAMA_SERVER), command)
    return 0


def _selected_pipelines(value: str) -> tuple[str, ...]:
    if value == "all":
        return PIPELINES
    return (PIPELINE_ALIASES[value],)


def _command_run(args: argparse.Namespace) -> int:
    compiled = Path(args.compiled)
    run_root = Path(args.run_root)
    scene, personas, _, source_hashes = load_compiled(compiled)
    resolved_profile = load_resolved_profile(compiled)
    shared_prefix = load_shared_prefix(compiled)
    generator = LlamaClient(
        args.generator_url,
        model=MODEL_PROFILES["generator"].alias,
        timeout=args.timeout,
    )
    fast = (
        LlamaClient(
            args.fast_url,
            model=MODEL_PROFILES["fast_judge"].alias,
            timeout=args.timeout,
        )
        if args.fast_url
        else None
    )
    if not generator.health():
        raise RuntimeError(f"Generator is not healthy: {args.generator_url}")
    selected = _selected_pipelines(args.pipeline)
    if ACTOR_NOVELIST_PIPELINE in selected:
        if fast is None or not fast.health():
            raise RuntimeError("Actor–Novelist requires a healthy --fast-url server")
    summary: dict[str, Any] = {}
    for pipeline in selected:
        pipeline_dir = run_root / pipeline
        config = make_run_config(
            run_id=f"{args.run_id}-{pipeline}",
            pipeline=pipeline,
            scene=scene,
            prompt_hash=sha256_text(shared_prefix),
            source_hashes=source_hashes,
            count=args.count,
            output_tokens=args.output_tokens,
            persona_ids=tuple(persona.persona_id for persona in personas),
            resolved_profile=resolved_profile,
        )
        prior_config_path = pipeline_dir / "run_config.json"
        if prior_config_path.is_file():
            prior = json.loads(prior_config_path.read_text(encoding="utf-8"))
            for key in (
                "prompt_hash",
                "ontology_version",
                "story_profile_id",
                "scene_profile_id",
                "resolved_profile_hash",
            ):
                if str(prior.get(key, "")) != str(config.to_dict().get(key, "")):
                    raise ValueError(
                        f"Refusing to resume {pipeline}: {key} differs from "
                        "the existing run configuration"
                    )
        write_json(pipeline_dir / "run_config.json", config.to_dict())
        candidates = run_pipeline(
            pipeline,
            generator_client=generator,
            fast_client=fast,
            config=config,
            scene=scene,
            personas=personas,
            shared_prefix=shared_prefix,
            run_dir=pipeline_dir,
            count=args.count,
        )
        summary[pipeline] = {
            "candidate_count": len(candidates),
            "candidate_ids": [candidate.candidate_id for candidate in candidates],
            "run_dir": str(pipeline_dir),
        }
    write_json(run_root / "generation_summary.json", summary)
    _print_json(summary)
    return 0


def _continuation_author_context(args: argparse.Namespace):
    manifest = load_corpus_manifest(args.author_manifest)
    corpus_validation = validate_corpus_files(args.author_manifest)
    if not corpus_validation.valid:
        raise ValueError(
            "author corpus validation failed: "
            + "; ".join(corpus_validation.errors)
        )
    profile = load_author_profile(args.author_profile)
    transformation = load_transformation_map(args.author_transformation_map)
    validate_profile_against_manifest(profile, manifest)
    compiled_manifest = json.loads(
        (Path(args.compiled) / "manifest.v1.json").read_text(encoding="utf-8")
    )
    target_hash = str(
        compiled_manifest.get("creative_profile", {}).get(
            "resolved_profile_hash", ""
        )
    )
    validate_transformation_map(
        profile,
        transformation,
        target_profile_hash=target_hash,
    )
    return resolve_author_context(
        profile,
        transformation,
        corpus_manifest_hash=manifest.corpus_hash,
        conditioning_variant=getattr(
            args, "author_conditioning_variant", "anonymous-profile"
        ),
        prompt_encoding=getattr(args, "author_prompt_encoding", "xml"),
        control_density=getattr(args, "author_control_density", "light"),
        conditioning_material=_conditioning_material(args),
    )


def _continuation_inputs(args: argparse.Namespace):
    return prepare_continuation_context(
        compiled_dir=args.compiled,
        finalists_path=args.finalists,
        reveal_key_path=args.reveal_key,
        feedback_path=args.feedback_brief,
        author_context=_continuation_author_context(args),
    )


def _continuation_source_hashes(compiled: str | Path) -> dict[str, str]:
    root = Path(compiled)
    manifest = json.loads(
        (root / "manifest.v1.json").read_text(encoding="utf-8")
    )
    hashes = {
        str(item["key"]): str(item["raw_sha256"])
        for item in manifest.get("sources", ())
        if isinstance(item, Mapping)
    }
    profile = root / "profiles" / "resolved_profile.v1.json"
    if profile.is_file():
        hashes["resolved_creative_profile_file"] = hash_file(profile)
    return hashes


def _continuation_anti_copy_index(
    compiled: str | Path,
    *,
    approved_prefix_id: str,
    approved_prefix_text: str,
    prompt_exemplars: Mapping[str, str] | None = None,
) -> AntiCopyIndex:
    root = Path(compiled)
    project_sources: dict[str, str] = {}
    categories: dict[str, str] = {}
    for path in sorted((root / "corpus").glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, Mapping) and isinstance(value.get("text"), str):
            source_id = f"compiled:{path.stem}"
            project_sources[source_id] = str(value["text"])
            categories[source_id] = "project-source"
    project_sources[f"approved-prefix:{approved_prefix_id}"] = approved_prefix_text
    categories[f"approved-prefix:{approved_prefix_id}"] = "approved-prefix"
    for source_id, text in sorted((prompt_exemplars or {}).items()):
        if source_id in project_sources:
            raise ValueError(f"duplicate continuation anti-copy source ID: {source_id}")
        project_sources[source_id] = text
        categories[source_id] = "prompt-exemplar"
    if not project_sources:
        raise ValueError("S02 anti-copy index has no project sources")
    return AntiCopyIndex(project_sources, categories=categories)


def _command_continuation_prepare(args: argparse.Namespace) -> int:
    (
        scene,
        _,
        profile,
        _,
        feedback,
        approved,
        packet,
        rendered,
    ) = _continuation_inputs(args)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    manifest = context_manifest(
        packet=packet,
        rendered=rendered,
        scene=scene,
        profile=profile,
        feedback=feedback,
        approved_prefix=approved,
    )
    write_json(output / "compact_context.v1.json", packet)
    atomic_write_text(output / "compact_context.v1.xml", rendered + "\n")
    write_json(output / "context_manifest.v1.json", manifest)
    _print_json(
        {
            **manifest,
            "output": str(output),
            "provisional": feedback.source_kind != "human",
        }
    )
    return 0


def _command_continuation_propose(args: argparse.Namespace) -> int:
    (
        _,
        _,
        profile,
        _,
        feedback,
        approved,
        _,
        rendered,
    ) = _continuation_inputs(args)
    mode = args.mode
    role = "base_31b_writer" if mode == BASE31_PLAN_MODE else "base_ideator"
    ideator_url = args.ideator_url or (
        "http://127.0.0.1:8097"
        if mode == BASE31_PLAN_MODE
        else "http://127.0.0.1:8094"
    )
    client = LlamaClient(
        ideator_url,
        model=MODEL_PROFILES[role].alias,
        timeout=args.timeout,
    )
    if not client.health():
        raise RuntimeError(f"Base ideator is not healthy: {ideator_url}")
    store = TraceStore(Path(args.run_root) / mode)
    programs = propose_story_programs(
        ideator=client,
        store=store,
        compact_prefix=rendered,
        seeds=CONTINUATION_SEEDS[: args.count],
        approved_prefix=approved,
        feedback=feedback,
        profile_hash=str(profile["profile_hash"]),
        generation_mode=mode,
    )
    _print_json(
        {
            "program_count": len(programs),
            "generation_mode": mode,
            "program_ids": [f"s02-{mode}-{seed}" for seed in programs],
            "run_dir": str(store.run_dir),
        }
    )
    return 0


def _command_continuation_verbalize(args: argparse.Namespace) -> int:
    (
        _,
        _,
        profile,
        _,
        feedback,
        approved,
        _,
        rendered,
    ) = _continuation_inputs(args)
    client = LlamaClient(
        args.planner_url,
        model=MODEL_PROFILES["raw_writer"].alias,
        timeout=args.timeout,
    )
    if not client.health():
        raise RuntimeError(
            f"Verbalized Sampling planner is not healthy: {args.planner_url}"
        )
    store = TraceStore(Path(args.run_root) / VERBALIZED_MODE)
    programs = propose_verbalized_story_programs(
        planner=client,
        store=store,
        compact_prefix=rendered,
        seeds=CONTINUATION_SEEDS[: args.count],
        approved_prefix=approved,
        feedback=feedback,
        profile_hash=str(profile["profile_hash"]),
    )
    _print_json(
        {
            "generation_mode": VERBALIZED_MODE,
            "program_count": len(programs),
            "program_ids": [f"s02-vs-{seed}" for seed in programs],
            "run_dir": str(store.run_dir),
        }
    )
    return 0


def _command_continuation_rank_verbalized(args: argparse.Namespace) -> int:
    (
        _,
        _,
        profile,
        _,
        feedback,
        approved,
        _,
        rendered,
    ) = _continuation_inputs(args)
    client = LlamaClient(
        args.judge_url,
        model=MODEL_PROFILES["raw_writer"].alias,
        timeout=args.timeout,
    )
    if not client.health():
        raise RuntimeError(f"Plan judge is not healthy: {args.judge_url}")
    store = TraceStore(Path(args.run_root) / VERBALIZED_MODE)
    result = judge_and_lock_verbalized_plans(
        judge=client,
        store=store,
        compact_prefix=rendered,
        seeds=CONTINUATION_SEEDS[: args.count],
        approved_prefix=approved,
        feedback=feedback,
        profile_hash=str(profile["profile_hash"]),
    )
    manifest = result["manifest"]
    report = result["report"]
    _print_json(
        {
            "generation_mode": VERBALIZED_MODE,
            "selected_strategy_ids": report["selected_strategy_ids"],
            "plan_set_hash": manifest["plan_set_hash"],
            "plan_manifest": str(store.run_dir / "locked_plan_set.v2.json"),
            "quality_report": str(store.run_dir / "plan_quality.v1.json"),
        }
    )
    return 0


def _command_continuation_adjudicate_verbalized(args: argparse.Namespace) -> int:
    store = TraceStore(Path(args.run_root) / VERBALIZED_MODE)
    policy = json.loads(Path(args.policy).read_text(encoding="utf-8"))
    result = adjudicate_verbalized_plan_set(
        store=store,
        seeds=CONTINUATION_SEEDS[: args.count],
        policy=policy,
    )
    manifest = result["manifest"]
    adjudication = result["adjudication"]
    _print_json(
        {
            "generation_mode": VERBALIZED_MODE,
            "selected_strategy_ids": adjudication["selected_strategy_ids"],
            "plan_set_hash": manifest["plan_set_hash"],
            "plan_manifest": str(store.run_dir / "locked_plan_set.v3.json"),
            "adjudication_report": str(store.run_dir / "plan_adjudication.v1.json"),
        }
    )
    return 0


def _command_continuation_compile_programs(args: argparse.Namespace) -> int:
    (
        _,
        _,
        profile,
        _,
        feedback,
        approved,
        _,
        rendered,
    ) = _continuation_inputs(args)
    client = LlamaClient(
        args.compiler_url,
        model=MODEL_PROFILES["raw_writer"].alias,
        timeout=args.timeout,
    )
    if not client.health():
        raise RuntimeError(
            f"Raw 31B program compiler is not healthy: {args.compiler_url}"
        )
    mode = args.mode
    store = TraceStore(Path(args.run_root) / mode)
    programs = compile_story_programs(
        compiler=client,
        store=store,
        compact_prefix=rendered,
        seeds=CONTINUATION_SEEDS[: args.count],
        approved_prefix=approved,
        feedback=feedback,
        profile_hash=str(profile["profile_hash"]),
        generation_mode=mode,
        source_tag=(
            "verbalized-tail-proposal"
            if mode == VERBALIZED_MODE
            else "raw-base-proposal"
        ),
        source_description=(
            "verbalized tail proposal"
            if mode == VERBALIZED_MODE
            else "raw proposal"
        ),
    )
    _print_json(
        {
            "program_count": len(programs),
            "program_ids": [
                f"s02-{mode}-{seed}-compiled" for seed in programs
            ],
            "generation_mode": mode,
            "all_valid": True,
            "run_dir": str(store.run_dir),
        }
    )
    return 0


def _load_story_programs(
    run_root: Path,
    seeds: Sequence[int],
    mode: str,
    *,
    locked_plan_set: str | Path | None = None,
) -> dict[int, str]:
    if locked_plan_set is not None:
        locked_path = Path(locked_plan_set)
        if not re.fullmatch(r"locked_plan_set\.v\d+\.json", locked_path.name):
            raise ValueError(
                "external locked plan set must retain its versioned filename"
            )
    else:
        locked_candidates = sorted(
            (run_root / mode).glob("locked_plan_set.v*.json"),
            key=lambda path: int(
                re.fullmatch(r"locked_plan_set\.v(\d+)\.json", path.name).group(1)
            )
            if re.fullmatch(r"locked_plan_set\.v(\d+)\.json", path.name)
            else -1,
        )
        locked_path = locked_candidates[-1] if locked_candidates else None
    if locked_path is not None and locked_path.is_file():
        if mode == VERBALIZED_MODE and locked_path.name == "locked_plan_set.v1.json":
            raise ValueError(
                "verbalized_to_instruction requires quality-ranked "
                "locked_plan_set.v2.json; v1 is an audit artifact only"
            )
        manifest = json.loads(locked_path.read_text(encoding="utf-8"))
        version_match = re.fullmatch(
            r"locked_plan_set\.v(\d+)\.json", locked_path.name
        )
        expected_version = (
            f"locked-plan-set.v{version_match.group(1)}"
            if version_match
            else ""
        )
        if manifest.get("version") != expected_version:
            raise ValueError(f"{mode} locked plan-set filename/version mismatch")
        body = dict(manifest)
        observed_set_hash = str(body.pop("plan_set_hash", ""))
        if observed_set_hash != hash_json(body):
            raise ValueError(f"{mode} locked plan-set hash mismatch")
        if manifest.get("generation_mode") != mode:
            raise ValueError(f"{mode} locked plan set names a different mode")
        programs: dict[int, str] = {}
        for entry in manifest.get("entries", ()):
            if not isinstance(entry, Mapping):
                raise ValueError(f"{mode} locked plan entry is not an object")
            seed = entry.get("seed")
            plan = entry.get("plan")
            if not isinstance(seed, int) or not isinstance(plan, str):
                raise ValueError(f"{mode} locked plan entry is malformed")
            if seed in programs:
                raise ValueError(f"{mode} locked plan set duplicates seed {seed}")
            if entry.get("plan_hash") != sha256_text(plan):
                raise ValueError(f"{mode} locked plan hash mismatch for seed {seed}")
            if entry.get("immutable") is not True:
                raise ValueError(f"{mode} plan {seed} is not immutable")
            programs[seed] = plan
        missing = [seed for seed in seeds if seed not in programs]
        if missing:
            raise ValueError(
                f"{mode} locked plan set is missing seeds: "
                + ", ".join(str(seed) for seed in missing)
            )
        return {seed: programs[seed] for seed in seeds}

    if mode in {BASE31_PLAN_MODE, VERBALIZED_MODE}:
        raise ValueError(f"{mode} requires a locked_plan_set.vN.json manifest")
    records = TraceStore.read(
        run_root / mode / "plans.jsonl"
    )
    programs: dict[int, str] = {}
    for record in records:
        if (
            record.get("record_type") == "StoryProgram"
            and record.get("status") == "completed"
            and record.get("generation_mode") == mode
            and isinstance(record.get("seed"), int)
            and isinstance(record.get("program"), str)
        ):
            program = str(record["program"])
            if record.get("program_hash") != sha256_text(program):
                raise ValueError(f"{mode} plan record has a hash mismatch")
            seed = int(record["seed"])
            prior = programs.get(seed)
            if prior is not None and prior != program:
                raise ValueError(
                    f"{mode} contains conflicting completed plans for seed {seed}"
                )
            programs[seed] = program
    missing = [seed for seed in seeds if seed not in programs]
    if missing:
        raise ValueError(
            f"{mode} requires completed story proposals for seeds: "
            + ", ".join(str(seed) for seed in missing)
        )
    return {seed: programs[seed] for seed in seeds}


def _command_continuation_run(args: argparse.Namespace) -> int:
    (
        scene,
        _,
        profile,
        _,
        feedback,
        approved,
        _,
        rendered,
    ) = _continuation_inputs(args)
    mode = args.mode
    # A long-running comparison may span harness revisions.  Resume must use
    # the exact stable prefix recorded when the arm began, not a newly rendered
    # equivalent.  The saved context is eligible only when its bytes match the
    # existing RunConfig prompt hash; all other lineage checks still run below.
    run_root = Path(args.run_root)
    existing_config_path = run_root / mode / "run_config.json"
    saved_context_path = run_root / "context" / "compact_context.v1.xml"
    if existing_config_path.is_file() and saved_context_path.is_file():
        existing_config = json.loads(
            existing_config_path.read_text(encoding="utf-8")
        )
        saved_context = saved_context_path.read_text(encoding="utf-8").rstrip(
            "\n"
        )
        if sha256_text(saved_context) == existing_config.get("prompt_hash"):
            rendered = saved_context
    inferred_role = (
        "editor"
        if mode in {CHAT_DIRECT_MODE, CHAT_PLANNED_MODE}
        else "base_31b_writer"
        if mode in {NATIVE_BASE_MODE, NATIVE_BASE_PLANNED_MODE}
        else "raw_writer"
    )
    # Transport and checkpoint are independent experimental variables.  The
    # historical defaults preserve every existing arm, while an explicit role
    # makes writer-prior ablations honest in RunConfig and candidate telemetry.
    role = getattr(args, "writer_role", None) or inferred_role
    writer_url = args.writer_url or f"http://127.0.0.1:{DEFAULT_PORTS[role]}"
    client = LlamaClient(
        writer_url,
        model=MODEL_PROFILES[role].alias,
        timeout=args.timeout,
    )
    if not client.health():
        raise RuntimeError(f"Writer is not healthy: {writer_url}")
    author_context = _continuation_author_context(args)
    index = _continuation_anti_copy_index(
        args.compiled,
        approved_prefix_id=approved.approved_prefix_id,
        approved_prefix_text=approved.text,
        prompt_exemplars=_context_prompt_exemplars(
            author_context.prompt_payload
        ),
    )
    seeds = CONTINUATION_SEEDS[: args.count]
    programs = (
        _load_story_programs(
            run_root,
            seeds,
            BASE31_PLAN_MODE,
            locked_plan_set=args.locked_plan_set,
        )
        if mode in {NATIVE_BASE_PLANNED_MODE, CHAT_PLANNED_MODE}
        else _load_story_programs(run_root, seeds, mode)
        if mode in INSTRUCTION_PROGRAM_MODES
        else {}
    )
    config = make_continuation_run_config(
        run_id=f"{args.run_id}-{mode}",
        mode=mode,
        model_role=role,
        compact_prefix=rendered,
        scene=scene,
        source_hashes=_continuation_source_hashes(args.compiled),
        seeds=seeds,
        profile=profile,
        approved_prefix=approved,
        feedback=feedback,
        anti_copy_index=index,
        author_context=author_context,
    )
    candidates = run_continuation_arm(
        client=client,
        run_dir=run_root / mode,
        config=config,
        scene=scene,
        profile=profile,
        approved_prefix=approved,
        feedback=feedback,
        compact_prefix=rendered,
        anti_copy_index=index,
        story_programs=programs,
        max_new_candidates=args.max_new_candidates,
        stop_after_sequences=args.stop_after_sequences,
    )
    _print_json(
        {
            "mode": mode,
            "candidate_count": len(candidates),
            "candidate_ids": [item.candidate_id for item in candidates],
            "continuation_words": [
                word_count(item.continuation_text) for item in candidates
            ],
            "run_dir": str(run_root / mode),
        }
    )
    return 0


def _command_continuation_gate(args: argparse.Namespace) -> int:
    (
        scene,
        _,
        _,
        _,
        _,
        approved,
        _,
        _,
    ) = _continuation_inputs(args)
    author_context = _continuation_author_context(args)
    index = _continuation_anti_copy_index(
        args.compiled,
        approved_prefix_id=approved.approved_prefix_id,
        approved_prefix_text=approved.text,
        prompt_exemplars=_context_prompt_exemplars(
            author_context.prompt_payload
        ),
    )
    candidates = load_candidates(Path(args.run_root))
    reports = [
        continuation_gates(
            candidate,
            scene=scene,
            approved_prefix=approved,
            anti_copy_index=index,
        )
        for candidate in candidates
    ]
    output = Path(args.output)
    write_json(
        output,
        {
            "record_type": "S02GateReport",
            "candidate_count": len(reports),
            "eligible_count": sum(item["eligible"] for item in reports),
            "reports": reports,
        },
    )
    _print_json(
        {
            "candidate_count": len(reports),
            "eligible_count": sum(item["eligible"] for item in reports),
            "output": str(output),
        }
    )
    return 0 if reports and all(item["eligible"] for item in reports) else 1


def _read_jsonl_objects(path: Path) -> list[dict[str, Any]]:
    return TraceStore.read(path)


def _command_continuation_package(args: argparse.Namespace) -> int:
    evaluation_dir = Path(args.evaluation_dir)
    payload = json.loads(
        (evaluation_dir / "finalists.json").read_text(encoding="utf-8")
    )
    finalists = [
        Candidate.from_dict(item)
        for item in payload.get("finalists", ())
        if isinstance(item, Mapping)
    ]
    if len(finalists) < 3:
        raise ValueError("continuation appraisal requires at least three finalists")
    scores = [
        *_read_jsonl_objects(evaluation_dir / "scorecards.jsonl"),
        *_read_jsonl_objects(
            evaluation_dir / "revision_scores" / "scorecards.jsonl"
        ),
    ]
    score_map: dict[str, list[float]] = {}
    eligible_map: dict[str, list[bool]] = {}
    for score in scores:
        candidate_id = str(score.get("candidate_id", ""))
        if not candidate_id:
            continue
        score_map.setdefault(candidate_id, []).append(
            float(score.get("total_score", 0))
        )
        eligible_map.setdefault(candidate_id, []).append(
            bool(score.get("eligible", False))
        )
    ranking = sorted(
        finalists,
        key=lambda candidate: (
            not (
                eligible_map.get(candidate.candidate_id)
                and all(eligible_map[candidate.candidate_id])
            ),
            -(
                sum(score_map.get(candidate.candidate_id, ()))
                / max(1, len(score_map.get(candidate.candidate_id, ())))
            ),
            candidate.candidate_id,
        ),
    )
    primary_by_mode: dict[str, Candidate] = {}
    for candidate in ranking:
        canonical_mode = canonical_generation_mode(candidate.generation_mode)
        if canonical_mode in PRIMARY_COMPARISON_MODES:
            # ``ranking`` is best-first, so preserve the strongest accepted
            # representative if an evaluation directory contains retries or
            # both raw and polished records for the same primary mode.
            primary_by_mode.setdefault(canonical_mode, candidate)
    selected = (
        [primary_by_mode[mode] for mode in PRIMARY_COMPARISON_MODES]
        if all(mode in primary_by_mode for mode in PRIMARY_COMPARISON_MODES)
        else ranking[:3]
    )
    output = Path(args.output)
    manifest = build_blind_appraisal(
        selected,
        output,
        blind_seed=args.blind_seed,
    )
    pairwise_manifest = build_pairwise_feedback_packets(
        finalists=[candidate.to_dict() for candidate in selected],
        reveal_key_path=manifest["reveal_key"],
        out_dir=output / "balanced_pairs",
        title="The Calibration Game — Complete Proof Stories",
    )
    aggregate_path = evaluation_dir / "score_aggregate.json"
    aggregate = (
        json.loads(aggregate_path.read_text(encoding="utf-8"))
        if aggregate_path.is_file()
        else {}
    )
    internal = build_appraisal_internal_report(
        finalists,
        output.parent / "internal",
        scorecards=scores,
        diversity_reports=aggregate.get("generation_diagnostics", {}),
        generation_summary={
            "comparison_version": S02_COMPARISON_VERSION,
            "selected_for_blind_appraisal": [
                candidate.candidate_id for candidate in selected
            ],
            "excluded_after_internal_ranking": [
                candidate.candidate_id for candidate in ranking[3:]
            ],
            "selection_rule": (
                "one accepted winner from each declared primary pipeline "
                "(direct instruction, Verbalized Sampling, planned native base); "
                "fallback to top three only if a primary mode is absent; "
                "identities hidden from reader packet"
            ),
        },
    )
    _print_json(
        {
            "selected_candidate_ids": [
                candidate.candidate_id for candidate in selected
            ],
            "reader_html": manifest["reader_html"],
            "reader_markdown": manifest["reader_markdown"],
            "reveal_key": manifest["reveal_key"],
            "blind_check": manifest["blind_check"],
            "balanced_pair_packets": pairwise_manifest["packets"],
            "internal_report": internal,
        }
    )
    return 0


def _command_continuation_evaluate(args: argparse.Namespace) -> int:
    (
        scene,
        _,
        _,
        _,
        feedback,
        approved,
        _,
        rendered,
    ) = _continuation_inputs(args)
    run_root = Path(args.run_root)
    evaluation_dir = Path(args.evaluation_dir)
    candidates = load_candidates(run_root)
    if not candidates:
        raise RuntimeError(f"No proof-story candidates found under {run_root}")
    author_context = _continuation_author_context(args)
    index = _continuation_anti_copy_index(
        args.compiled,
        approved_prefix_id=approved.approved_prefix_id,
        approved_prefix_text=approved.text,
        prompt_exemplars=_context_prompt_exemplars(
            author_context.prompt_payload
        ),
    )
    if args.phase in {"tournament", "edit"} and args.judge_role != "editor":
        raise ValueError(
            f"continuation {args.phase} requires --judge-role editor"
        )
    client = None
    if args.phase != "finalize":
        client = LlamaClient(
            args.judge_url,
            model=MODEL_PROFILES[args.judge_role].alias,
            timeout=args.timeout,
        )
        if not client.health():
            raise RuntimeError(f"Judge/editor is not healthy: {args.judge_url}")
    rubric_path = _resolve_rubric(args.rubric)

    if args.phase in {"score", "all"}:
        _, scores = judge_proof_candidates(
            candidates=candidates,
            scene=scene,
            approved_prefix=approved,
            feedback=feedback,
            anti_copy_index=index,
            compiled_dir=args.compiled,
            evaluation_dir=evaluation_dir,
            client=client,
            rubric_path=rubric_path,
        )
    else:
        scores = _read_jsonl_objects(evaluation_dir / "scorecards.jsonl")
    if not scores:
        raise RuntimeError("No proof-story scorecards are available")
    aggregate = aggregate_proof_scores(candidates, scores)
    write_json(evaluation_dir / "score_aggregate.json", aggregate)
    if args.phase == "score":
        _print_json(
            {
                "candidate_count": len(candidates),
                "scorecard_count": len(scores),
                "evaluation_dir": str(evaluation_dir),
            }
        )
        return 0

    if args.phase in {"tournament", "all"}:
        tournament = tournament_top_two(
            candidates=candidates,
            score_aggregate=aggregate,
            compiled_dir=args.compiled,
            evaluation_dir=evaluation_dir,
            client=client,
            rubric_path=rubric_path,
        )
    else:
        tournament = json.loads(
            (evaluation_dir / "tournament.json").read_text(encoding="utf-8")
        )
    if args.phase == "tournament":
        _print_json(
            {
                "modes": list(tournament["modes"]),
                "evaluation_dir": str(evaluation_dir),
            }
        )
        return 0

    if args.phase in {"edit", "all"}:
        revisions = edit_mode_winners(
            candidates=candidates,
            scores=scores,
            tournament=tournament,
            compact_context=rendered,
            approved_prefix=approved,
            feedback=feedback,
            anti_copy_index=index,
            scene=scene,
            evaluation_dir=evaluation_dir,
            client=client,
        )
    else:
        revisions = load_candidates(evaluation_dir)
    if args.phase == "edit":
        _print_json(
            {
                "revision_count": len(revisions),
                "revision_ids": [item.candidate_id for item in revisions],
            }
        )
        return 0

    if args.phase in {"revision-score", "all"}:
        _, revision_scores = judge_proof_candidates(
            candidates=revisions,
            scene=scene,
            approved_prefix=approved,
            feedback=feedback,
            anti_copy_index=index,
            compiled_dir=args.compiled,
            evaluation_dir=evaluation_dir / "revision_scores",
            client=client,
            rubric_path=rubric_path,
        )
    else:
        revision_scores = _read_jsonl_objects(
            evaluation_dir / "revision_scores" / "scorecards.jsonl"
        )
    if args.phase == "revision-score":
        _print_json(
            {
                "revision_count": len(revisions),
                "scorecard_count": len(revision_scores),
            }
        )
        return 0

    finalists = accept_editor_revisions(
        raw_candidates=candidates,
        revisions=revisions,
        raw_scores=scores,
        revision_scores=revision_scores,
        output_path=evaluation_dir / "editor_decisions.json",
    )
    write_json(
        evaluation_dir / "finalists.json",
        {
            "record_type": "ProofStoryFinalists",
            "feedback_source_kind": feedback.source_kind,
            "feedback_brief_hash": feedback.feedback_brief_hash,
            "finalists": [item.to_dict() for item in finalists],
        },
    )
    _print_json(
        {
            "finalist_count": len(finalists),
            "finalist_ids": [item.candidate_id for item in finalists],
            "evaluation_dir": str(evaluation_dir),
        }
    )
    return 0


def _load_scorecards(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    records.append(value)
    return records


def _command_evaluate(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    evaluation_dir = Path(args.evaluation_dir)
    compiled = Path(args.compiled)
    candidates = load_candidates(run_root)
    if not candidates:
        raise RuntimeError(f"No completed candidates found under {run_root}")
    scene, _, _, _ = load_compiled(compiled)
    source_texts = load_source_texts(compiled)
    rubric = load_rubric(_resolve_rubric(args.rubric))
    judge = LlamaClient(
        args.judge_url,
        model=MODEL_PROFILES["editor"].alias,
        timeout=args.timeout,
    )
    if not judge.health():
        raise RuntimeError(f"Judge/editor is not healthy: {args.judge_url}")
    if args.phase in {"score", "all"}:
        scores = judge_candidates(
            candidates=candidates,
            scene=scene,
            source_texts=source_texts,
            compiled_dir=compiled,
            evaluation_dir=evaluation_dir,
            client=judge,
            passes=args.judge_passes,
            rubric=rubric,
        )
    else:
        scores = _load_scorecards(evaluation_dir / "scorecards.jsonl")
    if not scores:
        raise RuntimeError("No scorecards are available")
    if args.phase == "score":
        _print_json(
            {
                "candidate_count": len(candidates),
                "scorecard_count": len(scores),
                "phase": "score",
                "evaluation_dir": str(evaluation_dir),
            }
        )
        return 0
    if args.phase in {"tournament", "all"}:
        tournament = run_pairwise_tournaments(
            candidates=candidates,
            scores=scores,
            compiled_dir=compiled,
            evaluation_dir=evaluation_dir,
            client=judge,
            rubric=rubric,
        )
        write_json(evaluation_dir / "tournament.json", tournament)
    else:
        tournament_path = evaluation_dir / "tournament.json"
        if not tournament_path.exists():
            raise RuntimeError("Run the tournament phase before polishing")
        tournament = json.loads(tournament_path.read_text(encoding="utf-8"))
    if args.phase == "tournament":
        _print_json(
            {
                "candidate_count": len(candidates),
                "scorecard_count": len(scores),
                "phase": "tournament",
                "evaluation_dir": str(evaluation_dir),
            }
        )
        return 0
    if args.phase in {"polish", "all"}:
        finalists, decisions = polish_winners(
            candidates=candidates,
            scores=scores,
            tournament=tournament,
            scene=scene,
            source_texts=source_texts,
            compiled_dir=compiled,
            evaluation_dir=evaluation_dir,
            client=judge,
            rubric=rubric,
        )
        build_internal_report(
            candidates=candidates,
            scores=scores,
            tournament=tournament,
            editor_decisions=decisions,
            output_dir=evaluation_dir / "internal",
        )
        result = {
            "candidate_count": len(candidates),
            "scorecard_count": len(scores),
            "finalists": [candidate.candidate_id for candidate in finalists],
            "evaluation_dir": str(evaluation_dir),
        }
    else:
        result = {
            "candidate_count": len(candidates),
            "scorecard_count": len(scores),
            "phase": args.phase,
            "evaluation_dir": str(evaluation_dir),
        }
    _print_json(result)
    return 0


def _resolve_rubric(value: str | None) -> Path:
    if not value or value == "v1":
        return RUBRIC_PATH
    if value in {"v2", "gabaldon", "gabaldon-v2"}:
        return GABALDON_RUBRIC_PATH
    if value in {"s02", "s02-v1", "s02-proof"}:
        return S02_RUBRIC_PATH
    return Path(value)


def _command_craft_audit(args: argparse.Namespace) -> int:
    """Run the v2 intimacy diagnostics over preserved candidates without a model."""

    run_root = Path(args.run_root)
    compiled = Path(args.compiled)
    candidates = load_candidates(run_root)
    if not candidates:
        raise RuntimeError(f"No completed candidates found under {run_root}")
    scene, _, _, _ = load_compiled(compiled)
    resolved_profile = load_resolved_profile(compiled)
    source_texts = load_source_texts(compiled)
    rubric = profile_aware_rubric(
        load_rubric(_resolve_rubric(args.rubric)), resolved_profile
    )
    records: list[dict[str, Any]] = []
    by_pipeline: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        score = evaluate_candidate(
            candidate,
            scene,
            source_texts,
            rubric,
            resolved_profile=resolved_profile,
        )
        craft = score["romance_diagnostics"]["intimacy_craft"]
        count = max(1, word_count(candidate.text))
        emotional = craft["emotional_transaction"]["evidence"]
        counterpoint = craft["dialogue_body_counterpoint"]["evidence"]
        atmosphere = craft["atmospheric_participation"]["evidence"]
        sensory = craft["sensory_triage"]["evidence"]
        surface_metrics = {
            "words": count,
            "dialogue_turns_per_1000_words": round(
                emotional["dialogue_turns"] / count * 1000, 4
            ),
            "emotional_markers_per_1000_words": round(
                emotional["emotional_or_relational_markers"] / count * 1000,
                4,
            ),
            "body_actions_per_1000_words": round(
                counterpoint["body_actions"] / count * 1000, 4
            ),
            "atmosphere_markers_per_1000_words": round(
                atmosphere["atmosphere_markers"] / count * 1000, 4
            ),
            "active_sense_count": len(sensory["active_channels"]),
        }
        records.append(
            {
                "candidate_id": candidate.candidate_id,
                "pipeline": candidate.pipeline,
                "eligible": score["eligible"],
                "craft_diagnostics": craft,
                "surface_metrics": surface_metrics,
                "defects": score["defects"],
            }
        )
    for pipeline in PIPELINES:
        group = [record for record in records if record["pipeline"] == pipeline]
        if not group:
            continue
        diagnostic_names = sorted(group[0]["craft_diagnostics"])
        by_pipeline[pipeline] = {
            "candidate_count": len(group),
            "mean_surface_metrics": {
                metric: round(
                    sum(record["surface_metrics"][metric] for record in group)
                    / len(group),
                    4,
                )
                for metric in group[0]["surface_metrics"]
            },
            "diagnostic_pass_rates": {
                name: round(
                    sum(
                        1
                        for record in group
                        if record["craft_diagnostics"][name]["passed"] is True
                    )
                    / len(group),
                    4,
                )
                for name in diagnostic_names
                if any(
                    record["craft_diagnostics"][name]["passed"] is not None
                    for record in group
                )
            },
            "defect_counts": {
                defect: sum(defect in record["defects"] for record in group)
                for defect in sorted(
                    {
                        defect
                        for record in group
                        for defect in record["defects"]
                    }
                )
            },
        }
    report = {
        "rubric_id": rubric["rubric_id"],
        "candidate_count": len(records),
        "interpretation_note": (
            "Deterministic diagnostics measure surface coverage and obvious "
            "failures only. Passing does not establish character specificity, "
            "emotional quality, distance control, or physical intelligibility; "
            "those require the evidence-backed v2 editorial judge and humans."
        ),
        "by_pipeline": by_pipeline,
        "candidates": records,
    }
    if args.output:
        write_json(Path(args.output), report)
    _print_json(report if args.verbose else {
        "rubric_id": report["rubric_id"],
        "candidate_count": report["candidate_count"],
        "by_pipeline": report["by_pipeline"],
        "output": args.output,
    })
    return 0


def _command_package(args: argparse.Namespace) -> int:
    result = package_finalists(
        finalists_path=Path(args.finalists),
        output_dir=Path(args.output),
        blind_seed=args.blind_seed,
    )
    _print_json(result)
    return 0


def _finalist_payloads(path: str | Path) -> list[dict[str, Any]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    values = raw.get("finalists") if isinstance(raw, Mapping) else raw
    if not isinstance(values, list) or len(values) != 3:
        raise ValueError("finalists input must contain exactly three records")
    if any(not isinstance(item, Mapping) for item in values):
        raise TypeError("every finalist must be an object")
    return [dict(item) for item in values]


def _command_feedback_package_pairs(args: argparse.Namespace) -> int:
    manifest = build_pairwise_feedback_packets(
        finalists=_finalist_payloads(args.finalists),
        reveal_key_path=args.reveal_key,
        out_dir=args.output,
        title=args.title,
    )
    _print_json(manifest)
    return 0


def _command_feedback_summarize(args: argparse.Namespace) -> int:
    brief = summarize_feedback(
        args.responses,
        expected_package_id=args.package_id,
    )
    write_json(Path(args.output), brief.to_dict())
    _print_json(
        {
            "output": args.output,
            "package_id": brief.package_id,
            "response_count": len(brief.response_ids),
            "coverage": dict(brief.coverage),
            "winner_label": brief.winner_label,
            "fail_fast": brief.fail_fast,
            "feedback_brief_hash": brief.feedback_brief_hash,
        }
    )
    return 2 if brief.fail_fast else 0


def _command_feedback_bootstrap(args: argparse.Namespace) -> int:
    reveal = json.loads(Path(args.reveal_key).read_text(encoding="utf-8"))
    if not isinstance(reveal, Mapping) or not reveal.get("package_id"):
        raise ValueError("reveal key is missing package_id")
    brief = bootstrap_feedback_brief(
        reviewer_files=args.reviews,
        package_id=str(reveal["package_id"]),
    )
    write_json(Path(args.output), brief.to_dict())
    _print_json(
        {
            "output": args.output,
            "source_kind": brief.source_kind,
            "winner_label": brief.winner_label,
            "feedback_brief_hash": brief.feedback_brief_hash,
        }
    )
    return 0


def _command_ontology_list(args: argparse.Namespace) -> int:
    catalog = load_ontology(args.ontology)
    nodes = [
        {
            "id": node.id,
            "namespace": node.namespace,
            "label": node.label,
            "parents": list(node.parents),
        }
        for node in catalog.nodes.values()
        if not args.namespace or node.namespace == args.namespace
    ]
    _print_json(
        {
            "ontology_id": catalog.ontology_id,
            "version": catalog.version,
            "ontology_hash": catalog.ontology_hash,
            "node_count": len(nodes),
            "nodes": nodes,
        }
    )
    return 0


def _command_ontology_show(args: argparse.Namespace) -> int:
    catalog = load_ontology(args.ontology)
    _print_json(catalog.node(args.node_id).to_dict())
    return 0


def _resolved_from_args(
    args: argparse.Namespace,
):
    catalog = load_ontology(args.ontology)
    layers = load_story_profile(args.profile)
    scene = load_scene_profile(args.scene_profile) if args.scene_profile else None
    return catalog, resolve_profiles(catalog, layers, scene)


def _command_profile_validate(args: argparse.Namespace) -> int:
    catalog, profile = _resolved_from_args(args)
    _print_json(
        {
            "valid": True,
            "ontology_version": catalog.version,
            "ontology_hash": catalog.ontology_hash,
            "profile_id": profile.profile_id,
            "profile_hash": profile.profile_hash,
            "selected_coordinate_count": len(profile.selected_coordinates),
            "warning_count": len(profile.warnings),
        }
    )
    return 0


def _command_profile_resolve(args: argparse.Namespace) -> int:
    _, profile = _resolved_from_args(args)
    if args.output:
        write_resolved_profile(args.output, profile)
    _print_json(profile.to_dict())
    return 0


def _command_author_manifest_validate(args: argparse.Namespace) -> int:
    result = validate_corpus_files(
        args.manifest, permit_holdout_read=args.audit_holdout_hash
    )
    _print_json(result.to_dict())
    return 0 if result.valid else 1


def _command_author_segments_compile(args: argparse.Namespace) -> int:
    segments = compile_source_segments(
        args.manifest,
        partitions=tuple(args.partition),
    )
    records = [record.to_dict() for record, _ in segments]
    payload = {
        "record_type": "SourceSegmentIndex",
        "manifest_hash": load_corpus_manifest(args.manifest).corpus_hash,
        "segment_count": len(records),
        "partitions": sorted(set(args.partition)),
        "segments": records,
    }
    if args.output:
        write_json(Path(args.output), payload)
    _print_json(
        payload
        if args.verbose
        else {
            "manifest_hash": payload["manifest_hash"],
            "segment_count": len(records),
            "partitions": payload["partitions"],
            "output": args.output,
        }
    )
    return 0


def _load_valid_author_inputs(
    args: argparse.Namespace,
):
    manifest = load_corpus_manifest(args.manifest)
    profile = load_author_profile(args.author_profile)
    transformation = load_transformation_map(args.transformation_map)
    validate_profile_against_manifest(profile, manifest)
    validate_transformation_map(profile, transformation)
    return manifest, profile, transformation


def _command_author_profile_validate(args: argparse.Namespace) -> int:
    manifest, profile, transformation = _load_valid_author_inputs(args)
    segments = tuple(
        record
        for record, _ in compile_source_segments(
            args.manifest, partitions=("profiling", "calibration")
        )
    )
    catalog = load_ontology(args.ontology)
    validate_affordance_provenance(
        profile,
        source_segments=segments,
        known_rgo_coordinates=catalog.nodes,
    )
    result = {
        "valid": True,
        "author_id": manifest.author_id,
        "manifest_hash": manifest.corpus_hash,
        "author_profile_id": profile.profile_id,
        "author_profile_hash": profile.profile_hash,
        "affordance_count": len(profile.affordances),
        "author_signature_count": sum(
            item.scope == "author-signature" for item in profile.affordances
        ),
        "transformation_map_hash": transformation.map_hash,
    }
    _print_json(result)
    return 0


def _command_author_profile_resolve(args: argparse.Namespace) -> int:
    manifest, profile, transformation = _load_valid_author_inputs(args)
    context = resolve_author_context(
        profile,
        transformation,
        corpus_manifest_hash=manifest.corpus_hash,
        conditioning_variant=args.conditioning_variant,
        prompt_encoding=args.prompt_encoding,
        control_density=args.control_density,
        conditioning_material=_conditioning_material(args),
    )
    rendered = render_prompt_payload(
        context.prompt_payload, context.prompt_encoding
    )
    result = {
        **context.to_dict(),
        "context_hash": context.context_hash,
        "rendered_prompt": rendered,
    }
    if args.output:
        write_json(Path(args.output), result)
    _print_json(result)
    return 0


def _conditioning_material(args: argparse.Namespace) -> tuple[Mapping[str, Any], ...]:
    path = getattr(args, "conditioning_material", None)
    if not path:
        return ()
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, list) or any(
        not isinstance(item, Mapping) for item in value
    ):
        raise TypeError("conditioning material must be a JSON list of objects")
    return tuple(dict(item) for item in value)


def _author_anti_copy_index(manifest_path: str | Path) -> AntiCopyIndex:
    segments = compile_source_segments(
        manifest_path, partitions=("profiling", "calibration")
    )
    return AntiCopyIndex(
        {record.segment_id: text for record, text in segments},
        categories={
            record.segment_id: f"author-{record.partition}"
            for record, _ in segments
        },
    )


def _author_generation_index(
    manifest_path: str | Path,
    compiled_dir: str | Path,
    *,
    prompt_exemplars: Mapping[str, str] | None = None,
) -> AntiCopyIndex:
    segments = compile_source_segments(
        manifest_path, partitions=("profiling", "calibration")
    )
    author_documents = {
        record.segment_id: text for record, text in segments
    }
    project_sources = {
        f"project-source-{index:03d}": text
        for index, text in enumerate(load_source_texts(compiled_dir), 1)
    }
    return build_anti_copy_index(
        author_documents=author_documents,
        prompt_exemplars=prompt_exemplars,
        project_sources=project_sources,
    )


def _context_prompt_exemplars(
    prompt_payload: Mapping[str, Any],
) -> dict[str, str]:
    materials = prompt_payload.get("conditioning_material", ())
    if not isinstance(materials, Sequence) or isinstance(materials, str):
        raise ValueError("conditioning_material must be a sequence")
    exemplars: dict[str, str] = {}
    for index, item in enumerate(materials, 1):
        if not isinstance(item, Mapping):
            raise ValueError("conditioning material entries must be objects")
        text = str(item.get("text", "")).strip()
        if text:
            declared = str(item.get("source_id", "")).strip()
            source_id = (
                f"prompt-exemplar:{declared}"
                if declared
                else f"prompt-exemplar-{index:03d}"
            )
            if source_id in exemplars:
                raise ValueError(
                    f"duplicate conditioning-material source ID: {source_id}"
                )
            exemplars[source_id] = text
    return exemplars


def _command_author_anti_copy_build(args: argparse.Namespace) -> int:
    index = _author_anti_copy_index(args.manifest)
    result = index.manifest()
    if args.output:
        write_json(Path(args.output), result)
    _print_json(result)
    return 0


def _command_author_anti_copy_check(args: argparse.Namespace) -> int:
    index = _author_anti_copy_index(args.manifest)
    text = Path(args.candidate).read_text(encoding="utf-8")
    report = index.check(Path(args.candidate).stem, text)
    _print_json(report.to_dict())
    return 1 if report.hard_fail or report.unresolved_flags else 0


def _command_author_experiment_plan(args: argparse.Namespace) -> int:
    calibration_arms = calibration_design(
        graph_ids=tuple(args.graph_id),
        seeds=tuple(args.seed),
        winning_encoding=args.winning_encoding,
    )
    calibration_verification = verify_shared_story_programs(
        [arm.to_dict() for arm in calibration_arms]
    )
    full_arms = full_s01_design(
        winning_encoding=args.winning_encoding,
        winning_variants=tuple(
            args.full_variant
            or ("anonymous-profile", "named-profile")
        ),
        story_program_ids=tuple(
            f"s01-shared-program-{index:02d}" for index in range(1, 9)
        ),
        seeds=DEFAULT_PROSE_SEEDS,
    )
    full_verification = verify_shared_story_programs(
        [arm.to_dict() for arm in full_arms]
    )
    payload = {
        "record_type": "AuthorExperimentDesign",
        "version": "1.0",
        "calibration": {
            "arm_count": len(calibration_arms),
            "arms": [arm.to_dict() for arm in calibration_arms],
            "shared_story_program_check": calibration_verification,
        },
        "full_s01_provisional": {
            "arm_count": len(full_arms),
            "arms": [arm.to_dict() for arm in full_arms],
            "shared_story_program_check": full_verification,
            "selection_note": (
                "Replace the two provisional author variants with the "
                "Pareto-optimal calibration winners before generation."
            ),
        },
    }
    if args.output:
        write_json(Path(args.output), payload)
    _print_json(
        payload
        if args.verbose
        else {
            "calibration": {
                "arm_count": len(calibration_arms),
                "phase_counts": {
                    phase: sum(arm.phase == phase for arm in calibration_arms)
                    for phase in sorted(
                        {arm.phase for arm in calibration_arms}
                    )
                },
                "shared_story_program_check": calibration_verification,
            },
            "full_s01_provisional": {
                "arm_count": len(full_arms),
                "shared_story_program_check": full_verification,
            },
            "output": args.output,
        }
    )
    return 0


def _command_author_run(args: argparse.Namespace) -> int:
    manifest, profile, transformation = _load_valid_author_inputs(args)
    context = resolve_author_context(
        profile,
        transformation,
        corpus_manifest_hash=manifest.corpus_hash,
        conditioning_variant=args.conditioning_variant,
        prompt_encoding=args.prompt_encoding,
        control_density=args.control_density,
        conditioning_material=_conditioning_material(args),
    )
    scene, _, _, source_hashes = load_compiled(args.compiled)
    resolved = load_resolved_profile(args.compiled)
    if resolved is None:
        raise ValueError("author runs require an ontology-enabled compilation")
    creative_profile = resolved.to_dict()
    gabaldon_profile = json.loads(
        Path(args.gabaldon_profile).read_text(encoding="utf-8")
    )
    story_canon = json.loads(
        (
            Path(args.compiled)
            / "corpus"
            / "story_canon.v1.json"
        ).read_text(encoding="utf-8")
    )
    index = _author_generation_index(
        args.manifest,
        args.compiled,
        prompt_exemplars=_context_prompt_exemplars(context.prompt_payload),
    )
    ideator = LlamaClient(
        args.ideator_url,
        model=MODEL_PROFILES["base_ideator"].alias,
        timeout=args.timeout,
    )
    compiler = LlamaClient(
        args.compiler_url,
        model=MODEL_PROFILES["planner"].alias,
        timeout=args.timeout,
    )
    writer = LlamaClient(
        args.writer_url,
        model=MODEL_PROFILES["base_writer"].alias,
        timeout=args.timeout,
    )
    for name, client in (
        ("base ideator", ideator),
        ("26B compiler", compiler),
        ("base writer", writer),
    ):
        if not client.health():
            raise RuntimeError(f"{name} server is not healthy")
    result = run_author_base_pipeline(
        ideator=ideator,
        compiler=compiler,
        writer=writer,
        scene=scene,
        resolved_creative_profile=creative_profile,
        gabaldon_profile=gabaldon_profile,
        author_context=context,
        story_canon=story_canon,
        source_hashes=source_hashes,
        anti_copy_index=index,
        run_dir=args.run_root,
        run_id=args.run_id,
        idea_seeds=DEFAULT_IDEA_SEEDS[: args.idea_count],
        prose_seeds=DEFAULT_PROSE_SEEDS[: args.count],
        candidate_count=args.count,
        output_tokens=args.output_tokens,
        frontier_adapter=args.frontier_adapter,
    )
    _print_json(result.to_dict())
    return 0


def _load_author_run_candidates(run_root: str | Path) -> tuple[Candidate, ...]:
    latest: dict[str, Mapping[str, Any]] = {}
    for record in TraceStore.read(Path(run_root) / "candidates.jsonl"):
        if record.get("status") == "completed" and record.get("candidate_id"):
            latest[str(record["candidate_id"])] = record
    output: list[Candidate] = []
    for candidate_id in sorted(latest):
        payload = dict(latest[candidate_id])
        for key in ("status", "created_at", "finished_at"):
            payload.pop(key, None)
        output.append(Candidate.from_dict(payload))
    return tuple(output)


def _command_author_evaluate(args: argparse.Namespace) -> int:
    manifest, profile, transformation = _load_valid_author_inputs(args)
    context = resolve_author_context(
        profile,
        transformation,
        corpus_manifest_hash=manifest.corpus_hash,
        conditioning_variant=args.conditioning_variant,
        prompt_encoding=args.prompt_encoding,
        control_density=args.control_density,
        conditioning_material=_conditioning_material(args),
    )
    resolved = load_resolved_profile(args.compiled)
    if resolved is None:
        raise ValueError("author evaluation requires an ontology profile")
    candidates = _load_author_run_candidates(args.run_root)
    if not candidates:
        raise ValueError("no completed author-run candidates found")
    index = _author_generation_index(
        args.manifest,
        args.compiled,
        prompt_exemplars=_context_prompt_exemplars(context.prompt_payload),
    )
    judge = None
    if args.judge_url:
        judge = LlamaClient(
            args.judge_url,
            model=MODEL_PROFILES["editor"].alias,
            timeout=args.timeout,
        )
        if not judge.health():
            raise RuntimeError("author judge server is not healthy")
    score_path = Path(args.output_dir) / "author_scorecards.jsonl"
    prior = {
        str(record.get("candidate_id")): record
        for record in TraceStore.read(score_path)
        if record.get("candidate_id")
    }
    reports: list[dict[str, Any]] = []
    for index_number, candidate in enumerate(candidates, 1):
        if candidate.author_profile_hash != profile.profile_hash:
            raise ValueError(
                f"{candidate.candidate_id} was generated with another author profile"
            )
        overlap = index.check(candidate.candidate_id, candidate.text)
        report: dict[str, Any] = {
            "candidate_id": candidate.candidate_id,
            "distribution_diagnostics": distribution_diagnostics(
                candidate.text, profile
            ),
            "novelty": novelty_diagnostics(overlap),
            "provenance": {
                key: str(getattr(candidate, key))
                for key in (
                    "resolved_profile_hash",
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
            },
        }
        if judge and candidate.candidate_id not in prior:
            prompt = author_judge_prompt(
                candidate_id=candidate.candidate_id,
                candidate_text=candidate.text,
                author_context=context,
                creative_profile=resolved.to_dict(),
            )
            completion = judge.complete(
                prompt=prompt,
                seed=910_000 + index_number,
                max_tokens=2_048,
                temperature=0.1,
                top_p=0.95,
                min_p=0.0,
            )
            result = parse_author_judgment(
                completion.content,
                candidate_id=candidate.candidate_id,
                candidate_text=candidate.text,
                judge_id=completion.model,
                provenance=report["provenance"],
            )
            TraceStore._append(score_path, result.to_dict())
            report["author_judgment"] = result.to_dict()
        elif candidate.candidate_id in prior:
            report["author_judgment"] = prior[candidate.candidate_id]
        reports.append(report)
    payload = {
        "record_type": "AuthorEvaluationReport",
        "candidate_count": len(candidates),
        "author_profile_hash": profile.profile_hash,
        "anti_copy_index_hash": index.index_hash,
        "judge_enabled": judge is not None,
        "candidates": reports,
    }
    write_json(Path(args.output_dir) / "author_evaluation.json", payload)
    _print_json(
        {
            "candidate_count": len(candidates),
            "judge_enabled": judge is not None,
            "all_novelty_clear": all(
                item["novelty"]["passed"] for item in reports
            ),
            "output_dir": args.output_dir,
        }
    )
    return 0


def _command_convert_base(args: argparse.Namespace) -> int:
    roles = (
        ("base_ideator", "base_writer") if args.role == "all" else (args.role,)
    )
    commands = [
        build_base_conversion_command(
            role,
            python_path=Path(args.python),
            converter_path=Path(args.converter),
        )
        for role in roles
    ]
    if args.dry_run:
        _print_json({"commands": commands})
        return 0
    MODEL_PROFILES["base_ideator"].model_path.parent.mkdir(
        parents=True, exist_ok=True
    )
    results = []
    for role, command in zip(roles, commands):
        output = MODEL_PROFILES[role].model_path
        if output.is_file() and not args.force:
            results.append(
                {"role": role, "output": str(output), "status": "already-present"}
            )
            continue
        subprocess.run(command, check=True)
        results.append(
            {
                "role": role,
                "output": str(output),
                "bytes": output.stat().st_size,
                "status": "converted",
            }
        )
    _print_json({"results": results})
    return 0


def _command_autoresearch_corpus_compile(args: argparse.Namespace) -> int:
    payload = autoresearch_compile_corpus(args.source, args.output)
    _print_json(
        {
            "corpus_hash": payload["corpus_hash"],
            "passage_count": len(payload["passages"]),
            "partitions": payload["partitions"],
            "output": str(Path(args.output) / "corpus_manifest.v1.json"),
        }
    )
    return 0


def _command_autoresearch_benchmark_compile(args: argparse.Namespace) -> int:
    payload = autoresearch_compile_benchmarks(args.output)
    _print_json(
        {
            "benchmark_hash": payload["benchmark_hash"],
            "cell_count": len(payload["cells"]),
            "output": str(Path(args.output) / "benchmarks.v1.json"),
        }
    )
    return 0


def _v4_base_client(args: argparse.Namespace) -> LlamaClient:
    client = LlamaClient(args.url, model=args.model, timeout=args.timeout)
    if not client.health():
        raise RuntimeError(f"Gemma base endpoint is not healthy: {args.url}")
    props = client.props()
    served_alias = str(props.get("model_alias", ""))
    if served_alias != args.model:
        raise RuntimeError(
            f"served model alias {served_alias!r} does not match requested {args.model!r}"
        )
    return client


def _v4_critic_client(args: argparse.Namespace) -> LlamaClient:
    client = LlamaClient(args.critic_url, model=args.critic_model, timeout=args.timeout)
    if not client.health():
        raise RuntimeError(f"critic endpoint is not healthy: {args.critic_url}")
    return client


def _v4_admission(args: argparse.Namespace) -> SharedEndpointAdmission:
    return SharedEndpointAdmission(
        Path(args.admission_state),
        parallel_slots=args.parallel_slots,
        slot_context_tokens=args.slot_context_tokens,
        reserved_slot_tokens=args.reserved_slot_tokens,
        context_budget_tokens=args.context_budget_tokens,
    )


def _command_autoresearch_v4_campaign_init(args: argparse.Namespace) -> int:
    payload = autoresearch_v4_init_campaign(
        campaign_dir=args.campaign_dir, corpus_path=args.corpus,
        benchmarks_path=args.benchmarks, project_root=PROJECT_ROOT,
        benchmark_seal_path=args.benchmark_seal,
    )
    _print_json({"campaign_id": payload["campaign_id"], "campaign_hash": payload["campaign_hash"], "recipe_count": len(payload["recipes"])})
    return 0


def _command_autoresearch_v4_benchmark_seal(args: argparse.Namespace) -> int:
    payload = autoresearch_v4_seal_benchmark_protocol(
        benchmarks_path=args.benchmarks,
        protocol_path=args.protocol,
        output_path=args.output,
        project_root=PROJECT_ROOT,
        minimum_cells=args.minimum_cells,
    )
    _print_json({
        "output": str(Path(args.output).resolve()),
        "seal_hash": payload["seal_hash"],
        "cell_count": payload["cell_count"],
        "partitions": payload["partitions"],
    })
    return 0


def _command_autoresearch_v4_benchmark_open(args: argparse.Namespace) -> int:
    payload = autoresearch_v4_open_confirmation_benchmark(
        campaign_dir=args.campaign_dir,
    )
    _print_json({
        "opening_hash": payload["opening_hash"],
        "confirmation_cell_ids": payload["confirmation_cell_ids"],
    })
    return 0


def _command_autoresearch_v4_corpus_index(args: argparse.Namespace) -> int:
    payload = apprenticeship_compile_index(args.manifest, args.output)
    _print_json({"index_hash": payload["index_hash"], "scene_count": payload["scene_count"], "output": args.output})
    return 0


def _command_autoresearch_v4_corpus_merge(args: argparse.Namespace) -> int:
    _print_json(autoresearch_v4_merge_apprenticeship_retrievals(
        base_corpus_path=args.base_corpus,
        index_manifest_path=args.index,
        retrieval_paths=tuple(args.retrieval),
        output_path=args.output,
    ))
    return 0


def _command_autoresearch_v4_corpus_annotate_graphs(args: argparse.Namespace) -> int:
    critic = LlamaClient(args.critic_url, model=args.critic_model, timeout=args.timeout)
    if not critic.health():
        raise RuntimeError(f"critic endpoint is not healthy: {args.critic_url}")
    _print_json(autoresearch_v4_annotate_corpus_source_graphs(
        input_corpus_path=args.input, output_corpus_path=args.output,
        critic=critic, limit=args.limit,
    ))
    return 0


def _command_autoresearch_v4_runway_sample(args: argparse.Namespace) -> int:
    payload = autoresearch_v4_sample_runways(
        campaign_dir=args.campaign_dir, client=_v4_base_client(args),
        admission=_v4_admission(args), seeds=tuple(args.seeds),
        max_tokens=args.max_tokens, only_cell=args.only_cell,
        conditioning=args.conditioning, source_count=args.source_count,
        source_ids=tuple(args.source_ids),
        sampler=autoresearch_v4_SamplerV4(
            temperature=args.temperature, top_p=args.top_p, min_p=args.min_p,
            xtc_probability=args.xtc_probability,
            dry_multiplier=args.dry_multiplier,
            repeat_penalty=args.repeat_penalty,
        ),
    )
    _print_json(payload)
    return 0


def _command_autoresearch_v4_runway_sample_staged(args: argparse.Namespace) -> int:
    payload = autoresearch_v4_sample_staged_runways(
        campaign_dir=args.campaign_dir, client=_v4_base_client(args),
        admission=_v4_admission(args), seeds=tuple(args.seeds),
        only_cell=args.only_cell, source_count=args.source_count,
        source_ids=tuple(args.source_ids),
        conditioning=args.conditioning,
        spark_max_tokens=args.spark_max_tokens,
        continuation_max_tokens=args.continuation_max_tokens,
        spark_only=args.spark_only,
        sampler=autoresearch_v4_SamplerV4(
            temperature=args.temperature, top_p=args.top_p, min_p=args.min_p,
            xtc_probability=args.xtc_probability,
            dry_multiplier=args.dry_multiplier,
            repeat_penalty=args.repeat_penalty,
        ),
    )
    _print_json(payload)
    return 0


def _command_autoresearch_v4_runway_inherit(args: argparse.Namespace) -> int:
    _print_json(autoresearch_v4_inherit_verified_runways(
        source_campaign_dir=args.source_campaign,
        target_campaign_dir=args.campaign_dir,
    ))
    return 0


def _command_autoresearch_v4_runway_trim_prefix(args: argparse.Namespace) -> int:
    _print_json(autoresearch_v4_derive_verified_runway_prefix(
        source_campaign_dir=args.source_campaign,
        target_campaign_dir=args.campaign_dir,
        cell_id=args.cell, paragraph_count=args.paragraphs,
    ))
    return 0


def _command_autoresearch_v4_search_topology(args: argparse.Namespace) -> int:
    payload = autoresearch_v4_run_topology_search(
        campaign_dir=args.campaign_dir, client=_v4_base_client(args),
        admission=_v4_admission(args), seeds=tuple(args.seeds),
        max_tokens=args.max_tokens, only_recipe=args.only_recipe,
        only_cell=args.only_cell, limit=args.limit,
    )
    _print_json(payload)
    return 0


def _command_autoresearch_v4_search_topology_staged(args: argparse.Namespace) -> int:
    payload = autoresearch_v4_run_staged_topology_search(
        campaign_dir=args.campaign_dir, client=_v4_base_client(args),
        admission=_v4_admission(args), seeds=tuple(args.seeds),
        recipe_id=args.recipe, cell_id=args.cell,
        spark_max_tokens=args.spark_max_tokens,
        spark_max_words=args.spark_max_words,
        continuation_max_tokens=args.continuation_max_tokens,
    )
    _print_json(payload)
    return 0


def _command_autoresearch_v4_search_topology_branch(args: argparse.Namespace) -> int:
    payload = autoresearch_v4_run_topology_continuation_branches(
        campaign_dir=args.campaign_dir, client=_v4_base_client(args),
        admission=_v4_admission(args),
        parent_candidate_id=args.parent_candidate,
        seeds=tuple(args.seeds), max_tokens=args.max_tokens,
    )
    _print_json(payload)
    return 0


def _command_autoresearch_v4_search_sampler(args: argparse.Namespace) -> int:
    autoresearch_v4_freeze_sampler_recipes(args.campaign_dir)
    payload = autoresearch_v4_run_sampler_search(
        campaign_dir=args.campaign_dir, client=_v4_base_client(args),
        admission=_v4_admission(args), seeds=tuple(args.seeds),
        max_tokens=args.max_tokens, only_recipe=args.only_recipe,
        only_cell=args.only_cell, limit=args.limit,
    )
    _print_json(payload)
    return 0


def _command_autoresearch_v4_search_context(args: argparse.Namespace) -> int:
    autoresearch_v4_freeze_context_recipes(args.campaign_dir)
    payload = autoresearch_v4_run_context_search(
        campaign_dir=args.campaign_dir, client=_v4_base_client(args),
        admission=_v4_admission(args), seeds=tuple(args.seeds),
        max_tokens=args.max_tokens, only_recipe=args.only_recipe,
        only_cell=args.only_cell, limit=args.limit,
    )
    _print_json(payload)
    return 0


def _command_autoresearch_v4_search_behavioral(args: argparse.Namespace) -> int:
    autoresearch_v4_freeze_behavioral_recipes(
        args.campaign_dir, parent_recipe_ids=tuple(args.parents),
    )
    payload = autoresearch_v4_run_behavioral_search(
        campaign_dir=args.campaign_dir, client=_v4_base_client(args),
        admission=_v4_admission(args), seeds=tuple(args.seeds),
        parent_recipe_ids=tuple(args.parents), max_tokens=args.max_tokens,
        only_recipe=args.only_recipe, only_cell=args.only_cell, limit=args.limit,
    )
    _print_json(payload)
    return 0


def _command_autoresearch_v4_judge(args: argparse.Namespace) -> int:
    if args.pairwise:
        if args.phase == "runways":
            raise ValueError("pairwise judging applies to candidate phases, not runways")
        payload = autoresearch_v4_judge_pairwise_candidates(
            campaign_dir=args.campaign_dir, critic=_v4_critic_client(args),
            phase=args.phase, recipe_ids=tuple(args.recipe_ids), limit=args.limit,
        )
    else:
        payload = autoresearch_v4_judge_candidates(
            campaign_dir=args.campaign_dir, critic=_v4_critic_client(args),
            phase=args.phase, only_candidate=args.only_candidate,
        )
    _print_json(payload)
    return 0


def _command_autoresearch_v4_promote(args: argparse.Namespace) -> int:
    if args.phase == "runways":
        selected: dict[str, str] = {}
        for value in args.select:
            if "=" not in value:
                raise ValueError("--select must use cell_id=runway_id")
            cell_id, runway_id = value.split("=", 1)
            selected[cell_id] = runway_id
        payload = autoresearch_v4_promote_runways(
            args.campaign_dir, selected_runway_ids=selected,
        )
    elif args.phase == "topology":
        payload = autoresearch_v4_promote_topologies(args.campaign_dir)
    elif args.phase == "behavioral":
        payload = autoresearch_v4_promote_behavioral(args.campaign_dir)
    elif args.phase == "context":
        payload = autoresearch_v4_promote_context(args.campaign_dir)
    elif args.phase == "sampler":
        payload = autoresearch_v4_promote_sampler(args.campaign_dir)
    else:
        payload = autoresearch_v4_promote_bootstrap(args.campaign_dir)
    _print_json(payload)
    return 0


def _command_autoresearch_v4_bootstrap(args: argparse.Namespace) -> int:
    payload = autoresearch_v4_run_bootstrap(
        campaign_dir=args.campaign_dir, client=_v4_base_client(args),
        admission=_v4_admission(args), seeds=tuple(args.seeds),
        max_tokens=args.max_tokens, limit=args.limit,
    )
    _print_json(payload)
    return 0


def _command_autoresearch_v4_trajectories(args: argparse.Namespace) -> int:
    payload = autoresearch_v4_sample_s01_trajectories(
        campaign_dir=args.campaign_dir, base_client=_v4_base_client(args),
        critic_client=_v4_critic_client(args), admission=_v4_admission(args),
        seeds=tuple(args.seeds), max_tokens=args.max_tokens,
        select_count=args.select_count,
    )
    _print_json(payload)
    return 0


def _command_autoresearch_v4_loom(args: argparse.Namespace) -> int:
    payload = autoresearch_v4_run_branch_loom(
        campaign_dir=args.campaign_dir, base_client=_v4_base_client(args),
        critic_client=_v4_critic_client(args), admission=_v4_admission(args),
        cell_id=args.cell, recipe_id=args.recipe,
        branches_per_parent=args.branches, survivors=args.survivors,
        movement_min_words=args.movement_min_words,
        movement_max_words=args.movement_max_words,
        max_tokens=args.max_tokens, seed=args.seed,
        trajectory_id=args.trajectory_id,
        prefix_candidate_id=args.prefix_candidate,
        prefix_campaign_dir=args.prefix_campaign,
        start_movement=args.start_movement,
        movement_local_sources=args.movement_local_sources,
        movement_excerpt_sources=args.movement_excerpt_sources,
        stop_after_movements=args.stop_after_movements,
        max_resample_pools=args.max_resample_pools,
    )
    _print_json({"finalist_set_hash": payload["finalist_set_hash"], "candidate_count": len(payload["finalists"]), "cell_id": payload["cell_id"]})
    return 0


def _command_autoresearch_v4_movement_audition(args: argparse.Namespace) -> int:
    payload = autoresearch_v4_sample_movement_auditions(
        campaign_dir=args.campaign_dir, base_client=_v4_base_client(args),
        critic_client=_v4_critic_client(args), admission=_v4_admission(args),
        cell_id=args.cell, prefix_candidate_id=args.prefix_candidate,
        prefix_campaign_dir=args.prefix_campaign,
        movement_number=args.movement_number, seeds=tuple(args.seeds),
        max_tokens=args.max_tokens, source_count=args.source_count,
        background_source_count=args.background_source_count,
        paired_examples=args.paired_examples,
        matched_source_ids=tuple(args.matched_source_id),
    )
    _print_json(payload)
    return 0


def _command_autoresearch_v4_mine_movement_sparks(args: argparse.Namespace) -> int:
    _print_json(autoresearch_v4_mine_movement_boundary_sparks(
        campaign_dir=args.campaign_dir, source_campaign_dir=args.source_campaign,
        cell_id=args.cell, prefix_candidate_id=args.prefix_candidate,
        prefix_campaign_dir=args.prefix_campaign,
        movement_number=args.movement_number,
    ))
    return 0


def _command_autoresearch_v4_readmit_movement(args: argparse.Namespace) -> int:
    _print_json(autoresearch_v4_readmit_movement_audition(
        campaign_dir=args.campaign_dir,
        source_campaign_dir=args.source_campaign,
        prefix_campaign_dir=args.prefix_campaign,
        cell_id=args.cell, source_branch_id=args.source_branch,
        movement_number=args.movement_number,
        critic_client=_v4_critic_client(args),
    ))
    return 0


def _command_autoresearch_v4_package(args: argparse.Namespace) -> int:
    payload = autoresearch_v4_package_finalists(
        campaign_dir=args.campaign_dir, output_dir=args.output,
        cell_id=args.cell, maximum=args.maximum,
    )
    _print_json(payload)
    return 0


def _command_autoresearch_v4_verify(args: argparse.Namespace) -> int:
    _print_json(autoresearch_v4_verify_assembly(args.assembly, PROJECT_ROOT))
    return 0


def _command_autoresearch_v4_replay(args: argparse.Namespace) -> int:
    _print_json(autoresearch_v4_cold_replay_call(
        campaign_dir=args.campaign_dir, call_id=args.call_id,
        client=_v4_base_client(args), admission=_v4_admission(args),
    ))
    return 0


def _command_autoresearch_v4_reextract(args: argparse.Namespace) -> int:
    _print_json(autoresearch_v4_reextract_phase_candidates(
        args.campaign_dir, phase=args.phase,
        minimum_words=args.minimum_words, maximum_words=args.maximum_words,
    ))
    return 0


def _command_autoresearch_v4_revalidate(args: argparse.Namespace) -> int:
    _print_json(autoresearch_v4_revalidate_phase_candidates(
        args.campaign_dir, phase=args.phase,
    ))
    return 0


def _command_autoresearch_v4_audit_assemblies(args: argparse.Namespace) -> int:
    report = autoresearch_v4_audit_assemblies(PROJECT_ROOT, args.output)
    _print_json({
        "output": str(Path(args.output)),
        "total": report["total"],
        "counts": report["counts"],
        "audit_hash": report["audit_hash"],
    })
    return 0


def _command_autoresearch_campaign_init(args: argparse.Namespace) -> int:
    payload = autoresearch_campaign_init(
        campaign_dir=args.campaign_dir,
        corpus_path=args.corpus,
        benchmarks_path=args.benchmarks,
        bridge_dir=args.bridges,
        project_root=PROJECT_ROOT,
    )
    _print_json(
        {
            "campaign_id": payload["campaign_id"],
            "campaign_hash": payload["campaign_hash"],
            "recipe_count": len(payload["recipes"]),
            "campaign_dir": args.campaign_dir,
        }
    )
    return 0


def _command_autoresearch_round_run(args: argparse.Namespace) -> int:
    client = LlamaClient(
        args.url,
        model=args.model,
        timeout=args.timeout,
    )
    if not client.health():
        raise RuntimeError(f"autoresearch endpoint is not healthy: {args.url}")
    admission = SharedEndpointAdmission(
        state_path=Path(args.admission_state),
        parallel_slots=args.parallel_slots,
        slot_context_tokens=args.slot_context_tokens,
        reserved_slot_tokens=args.reserved_slot_tokens,
        context_budget_tokens=args.context_budget_tokens,
    )
    payload = autoresearch_run_round1(
        campaign_dir=args.campaign_dir,
        client=client,
        admission=admission,
        round_number=args.round,
        max_tokens=args.max_tokens,
        only_recipe=args.only_recipe,
        only_cell=args.only_cell,
        only_seed=args.only_seed,
        limit=args.limit,
    )
    _print_json(payload)
    return 0


def _command_autoresearch_review_export(args: argparse.Namespace) -> int:
    output = Path(args.output) if args.output else (
        Path(args.campaign_dir) / f"round-{args.round}" / "review"
    )
    _print_json(autoresearch_export_review(args.campaign_dir, args.round, output))
    return 0


def _command_autoresearch_review_admit(args: argparse.Namespace) -> int:
    _print_json(
        autoresearch_admit_reviews(
            args.campaign_dir, args.round, args.review_file, args.reviewer_id
        )
    )
    return 0


def _command_autoresearch_review_admit_research(args: argparse.Namespace) -> int:
    _print_json(
        autoresearch_admit_research_review(
            args.campaign_dir,
            args.round,
            args.review_file,
            args.reviewer_id,
            args.role,
        )
    )
    return 0


def _command_autoresearch_v4_review_admit(args: argparse.Namespace) -> int:
    _print_json(autoresearch_v4_admit_research_review(
        args.campaign_dir, phase=args.phase, review_file=args.review_file,
        reviewer_id=args.reviewer_id, role=args.role,
    ))
    return 0


def _command_autoresearch_traces_analyze(args: argparse.Namespace) -> int:
    output = Path(args.output) if args.output else (
        Path(args.campaign_dir) / f"round-{args.round}" / "trace_analysis.v1.json"
    )
    payload = autoresearch_analyze_traces(args.campaign_dir, args.round, output)
    _print_json(
        {
            "round": payload["round"],
            "arm_count": len(payload["arms"]),
            "analysis_hash": payload["analysis_hash"],
            "output": str(output),
        }
    )
    return 0


def _command_autoresearch_v4_traces_analyze(args: argparse.Namespace) -> int:
    output = Path(args.output) if args.output else (
        Path(args.campaign_dir) / args.phase / "trace_analysis.v1.json"
    )
    payload = autoresearch_v4_analyze_traces(
        args.campaign_dir, phase=args.phase, output=output,
    )
    _print_json({
        "phase": payload["phase"], "arm_count": len(payload["arms"]),
        "analysis_hash": payload["analysis_hash"], "output": str(output),
    })
    return 0


def _command_autoresearch_overlap_adjudicate(args: argparse.Namespace) -> int:
    client = LlamaClient(args.url, model=args.model, timeout=args.timeout)
    if not client.health():
        raise RuntimeError(f"local overlap endpoint is not healthy: {args.url}")
    output = Path(args.output) if args.output else (
        Path(args.campaign_dir)
        / f"round-{args.round}"
        / "review"
        / "overlap_adjudications.jsonl"
    )
    _print_json(
        autoresearch_adjudicate_overlap_flags(
            args.campaign_dir, args.round, client, output
        )
    )
    return 0


def _command_autoresearch_decide(args: argparse.Namespace) -> int:
    trace = Path(args.trace_analysis) if args.trace_analysis else (
        Path(args.campaign_dir) / f"round-{args.round}" / "trace_analysis.v1.json"
    )
    output = Path(args.output) if args.output else (
        Path(args.campaign_dir) / f"round-{args.round}" / "decision.v1.json"
    )
    payload = autoresearch_decide_round(
        args.campaign_dir, args.round, trace, output
    )
    _print_json(payload)
    return 0


def _command_autoresearch_report(args: argparse.Namespace) -> int:
    output = Path(args.output) if args.output else (
        Path(args.campaign_dir) / "autoresearch_report.md"
    )
    rendered = autoresearch_render_report(args.campaign_dir, output)
    _print_json(
        {"output": str(output), "sha256": hash_file(output), "characters": len(rendered)}
    )
    return 0


def _command_autoresearch_package(args: argparse.Namespace) -> int:
    manifest = Path(args.campaign_dir) / "campaign_manifest.v1.json"
    if manifest.is_file():
        campaign = json.loads(manifest.read_text(encoding="utf-8"))
        if str(campaign.get("version", "")).startswith("gemma-fiction-autoresearch.v4"):
            output = Path(args.output) if args.output else Path(args.campaign_dir) / "human_appraisal" / args.cell
            return _command_autoresearch_v4_package(argparse.Namespace(
                campaign_dir=args.campaign_dir, output=str(output),
                cell=args.cell, maximum=args.max_finalists,
            ))
    output = Path(args.output) if args.output else (
        Path(args.campaign_dir) / "human_appraisal"
    )
    _print_json(
        autoresearch_package_human_finalists(
            args.campaign_dir,
            args.round,
            output,
            max_finalists=args.max_finalists,
        )
    )
    return 0


def _autoloom_runtime(args: argparse.Namespace) -> tuple[LlamaClient, SharedEndpointAdmission]:
    client = LlamaClient(args.url, model=args.model, timeout=args.timeout)
    if not client.health():
        raise RuntimeError(f"autoloom endpoint is not healthy: {args.url}")
    admission = SharedEndpointAdmission(
        state_path=Path(args.admission_state),
        parallel_slots=args.parallel_slots,
        slot_context_tokens=args.slot_context_tokens,
        reserved_slot_tokens=args.reserved_slot_tokens,
        context_budget_tokens=args.context_budget_tokens,
    )
    return client, admission


def _command_autoloom_init(args: argparse.Namespace) -> int:
    _print_json(
        autoloom_init_campaign(
            campaign_dir=args.campaign_dir,
            corpus_source=args.source,
            bridge_dir=args.bridges,
            parent_program_set=args.parent_program_set,
            apprenticeship_index=args.apprenticeship_index,
            apprenticeship_retrieval=args.apprenticeship_retrieval,
        )
    )
    return 0


def _command_autoloom_propose(args: argparse.Namespace) -> int:
    client, admission = _autoloom_runtime(args)
    _print_json(
        autoloom_propose_programs(
            campaign_dir=args.campaign_dir,
            client=client,
            admission=admission,
            only_cell=args.only_cell,
            max_tokens=args.max_tokens,
        )
    )
    return 0


def _command_autoloom_propose_mode(args: argparse.Namespace) -> int:
    client, admission = _autoloom_runtime(args)
    _print_json(
        autoloom_propose_mode_engines(
            campaign_dir=args.campaign_dir,
            client=client,
            admission=admission,
            only_cell=args.only_cell,
            max_tokens=args.max_tokens,
        )
    )
    return 0


def _command_autoloom_replay_mode(args: argparse.Namespace) -> int:
    _print_json(
        autoloom_replay_mode_engines(
            campaign_dir=args.campaign_dir,
            source_dir=args.source_dir,
            only_cell=args.only_cell,
        )
    )
    return 0


def _command_autoloom_replay_causal(args: argparse.Namespace) -> int:
    _print_json(
        autoloom_replay_causal_programs(
            campaign_dir=args.campaign_dir,
            source_dir=args.source_dir,
            only_cell=args.only_cell,
        )
    )
    return 0


def _command_autoloom_draft(args: argparse.Namespace) -> int:
    client, admission = _autoloom_runtime(args)
    _print_json(
        autoloom_draft(
            campaign_dir=args.campaign_dir,
            client=client,
            admission=admission,
            only_recipe=args.only_recipe,
            only_cell=args.only_cell,
            only_seed=args.only_seed,
            limit=args.limit,
            max_tokens=args.max_tokens,
        )
    )
    return 0


def _command_autoloom_staged(args: argparse.Namespace) -> int:
    client, admission = _autoloom_runtime(args)
    _print_json(
        autoloom_run_staged(
            campaign_dir=args.campaign_dir,
            client=client,
            admission=admission,
            stage=args.stage,
            recipe_id=args.recipe,
            cell_id=args.cell,
            limit=args.limit,
        )
    )
    return 0


def _command_autoloom_propose_transaction(args: argparse.Namespace) -> int:
    client, admission = _autoloom_runtime(args)
    _print_json(
        autoloom_propose_transaction_programs(
            campaign_dir=args.campaign_dir,
            client=client,
            admission=admission,
            max_tokens=args.max_tokens,
        )
    )
    return 0


def _command_autoloom_import_approach(args: argparse.Namespace) -> int:
    _print_json(autoloom_import_approach_selection(
        campaign_dir=args.campaign_dir, source_selection=args.source_selection,
    ))
    return 0


def _command_autoloom_import_programs(args: argparse.Namespace) -> int:
    _print_json(autoloom_import_locked_program_set(
        campaign_dir=args.campaign_dir, source_program_set=args.source_program_set,
    ))
    return 0


def _command_autoloom_replay_transaction(args: argparse.Namespace) -> int:
    _print_json(autoloom_replay_transaction_programs(
        campaign_dir=args.campaign_dir, source_dir=args.source_dir,
    ))
    return 0


def _command_autoloom_replay_transaction_candidates(args: argparse.Namespace) -> int:
    _print_json(autoloom_replay_transaction_candidates(
        campaign_dir=args.campaign_dir, source_candidates=args.source_candidates,
    ))
    return 0


def _command_autoloom_summarize(args: argparse.Namespace) -> int:
    _print_json(autoloom_summarize(args.campaign_dir, args.output))
    return 0


def _command_apprenticeship_fetch(args: argparse.Namespace) -> int:
    payload = apprenticeship_fetch_sources(args.spec, args.output)
    _print_json({
        "corpus_id": payload["corpus_id"],
        "corpus_hash": payload["corpus_hash"],
        "works": len(payload["works"]),
        "manifest": str(Path(args.output) / "corpus_manifest.v1.json"),
    })
    return 0


def _command_apprenticeship_index(args: argparse.Namespace) -> int:
    payload = apprenticeship_compile_index(args.manifest, args.output)
    _print_json(payload)
    return 0


def _command_apprenticeship_retrieve(args: argparse.Namespace) -> int:
    query = apprenticeship_load_query(args.query)
    payload = apprenticeship_retrieve_scenes(args.index, query)
    if args.output:
        write_json(Path(args.output), payload)
    _print_json(payload)
    return 0


def _command_apprenticeship_compile(args: argparse.Namespace) -> int:
    retrieval = json.loads(Path(args.retrieval).read_text(encoding="utf-8"))
    target_contract = Path(args.target_contract).read_text(encoding="utf-8")
    runway = Path(args.runway).read_text(encoding="utf-8")
    payload = apprenticeship_compile_prompt(
        index_manifest_path=args.index, retrieval=retrieval,
        target_contract=target_contract, runway=runway, output_dir=args.output,
    )
    _print_json(payload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fiction-harness",
        description="Three reproducible local Gemma 4 fiction pipelines.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    command = subparsers.add_parser("preflight", help="Verify disk, runtime, and model paths")
    command.add_argument("--data-path", default=str(PROJECT_ROOT))
    command.add_argument("--minimum-free-gb", type=float, default=5.0)
    command.add_argument("--full-hash", action="store_true")
    command.set_defaults(func=_command_preflight)

    provenance = subparsers.add_parser(
        "provenance",
        help="Audit and verify proof-carrying manuscript provenance",
    )
    provenance_sub = provenance.add_subparsers(
        dest="provenance_command", required=True
    )
    command = provenance_sub.add_parser(
        "audit", help="Quarantine historical Codex/frontier contamination"
    )
    command.add_argument("--project-root", default=str(PROJECT_ROOT))
    command.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "04_review_governance" / "provenance"),
    )
    command.set_defaults(func=_command_provenance_audit)
    command = provenance_sub.add_parser(
        "verify", help="Verify ledger, raw derivation, and replay witness"
    )
    command.add_argument("candidate")
    command.add_argument("--candidate-id", default="")
    command.add_argument(
        "--without-replay",
        action="store_true",
        help="Verify generation derivation only; never sufficient for promotion",
    )
    command.set_defaults(func=_command_provenance_verify)
    command = provenance_sub.add_parser(
        "replay", help="Reissue the exact recorded model call and write a witness"
    )
    command.add_argument("candidate")
    command.add_argument("--candidate-id", default="")
    command.add_argument("--url", required=True)
    command.add_argument("--timeout", type=float, default=3600.0)
    command.set_defaults(func=_command_provenance_replay)

    command = subparsers.add_parser("compile", help="Compile trusted project reads")
    command.add_argument("--project-root", default=str(PROJECT_ROOT))
    command.add_argument(
        "--output",
        help=(
            "Output directory; defaults to s01-v1 for legacy compilation and "
            "s01-v2-ontology when --profile is supplied"
        ),
    )
    command.add_argument("--config")
    command.add_argument(
        "--ontology",
        default=str(DEFAULT_ONTOLOGY_PATH),
        help="RGO catalog used when --profile is supplied",
    )
    command.add_argument(
        "--profile",
        help="Story profile or profile overlay; omit for byte-compatible legacy compilation",
    )
    command.add_argument("--scene-profile")
    command.set_defaults(func=_command_compile)

    autoresearch = subparsers.add_parser(
        "autoresearch",
        help="Run hash-locked prompt-engineering research campaigns",
    )
    autoresearch_sub = autoresearch.add_subparsers(
        dest="autoresearch_command", required=True
    )

    corpus = autoresearch_sub.add_parser("corpus", help="Compile local craft examples")
    corpus_sub = corpus.add_subparsers(dest="autoresearch_corpus_command", required=True)
    command = corpus_sub.add_parser("compile")
    command.add_argument("--source", default=str(DEFAULT_AUTORESEARCH_SOURCE))
    command.add_argument("--output", default=str(DEFAULT_AUTORESEARCH_COMPILED))
    command.set_defaults(func=_command_autoresearch_corpus_compile)
    command = corpus_sub.add_parser("index", help="Build a dramatic-function scene index")
    command.add_argument("--manifest", required=True)
    command.add_argument("--output", required=True)
    command.set_defaults(func=_command_autoresearch_v4_corpus_index)
    command = corpus_sub.add_parser("merge-apprenticeship", help="Merge retrieved complete scenes into a v4 prompt corpus")
    command.add_argument("--base-corpus", required=True)
    command.add_argument("--index", required=True)
    command.add_argument("--retrieval", action="append", required=True)
    command.add_argument("--output", required=True)
    command.set_defaults(func=_command_autoresearch_v4_corpus_merge)
    command = corpus_sub.add_parser(
        "annotate-graphs", help="Add local read-only dramatic-function graphs"
    )
    command.add_argument("--input", required=True)
    command.add_argument("--output", required=True)
    command.add_argument("--critic-url", default="http://127.0.0.1:8093")
    command.add_argument("--critic-model", default="gemma-4-e4b-it-read-only-critic")
    command.add_argument("--timeout", type=float, default=1800)
    command.add_argument("--limit", type=int)
    command.set_defaults(func=_command_autoresearch_v4_corpus_annotate_graphs)

    benchmark = autoresearch_sub.add_parser("benchmark", help="Compile fixed benchmark cells")
    benchmark_sub = benchmark.add_subparsers(dest="autoresearch_benchmark_command", required=True)
    command = benchmark_sub.add_parser("compile")
    command.add_argument("--output", default=str(DEFAULT_AUTORESEARCH_COMPILED))
    command.set_defaults(func=_command_autoresearch_benchmark_compile)
    command = benchmark_sub.add_parser(
        "seal-v4", help="Freeze benchmark splits and the complete confirmation protocol"
    )
    command.add_argument("--benchmarks", required=True)
    command.add_argument("--protocol", required=True)
    command.add_argument("--output", required=True)
    command.add_argument("--minimum-cells", type=int, default=24)
    command.set_defaults(func=_command_autoresearch_v4_benchmark_seal)
    command = benchmark_sub.add_parser(
        "open-v4", help="Open a sealed confirmation split exactly once"
    )
    command.add_argument("--campaign-dir", required=True)
    command.set_defaults(func=_command_autoresearch_v4_benchmark_open)

    campaign = autoresearch_sub.add_parser("campaign", help="Initialize a campaign manifest")
    campaign_sub = campaign.add_subparsers(dest="autoresearch_campaign_command", required=True)
    command = campaign_sub.add_parser("init")
    command.add_argument("--campaign-dir", default=str(DEFAULT_AUTORESEARCH_ROOT))
    command.add_argument("--corpus", default=str(DEFAULT_AUTORESEARCH_COMPILED / "corpus.private.v1.json"))
    command.add_argument("--benchmarks", default=str(DEFAULT_AUTORESEARCH_COMPILED / "benchmarks.v1.json"))
    command.add_argument("--bridges", default=str(DEFAULT_AUTORESEARCH_BRIDGES))
    command.set_defaults(func=_command_autoresearch_campaign_init)
    command = campaign_sub.add_parser("init-v4", help="Initialize the integrity-first branch loom")
    command.add_argument("--campaign-dir", default=str(DEFAULT_AUTORESEARCH_V4_ROOT))
    command.add_argument("--corpus", default=str(DEFAULT_AUTORESEARCH_COMPILED / "corpus.private.v1.json"))
    command.add_argument("--benchmarks", default=str(DEFAULT_AUTORESEARCH_COMPILED / "benchmarks.v1.json"))
    command.add_argument("--benchmark-seal")
    command.set_defaults(func=_command_autoresearch_v4_campaign_init)

    def add_autoresearch_v4_runtime(command: argparse.ArgumentParser, *, critic: bool = False) -> None:
        command.add_argument("--campaign-dir", default=str(DEFAULT_AUTORESEARCH_V4_ROOT))
        command.add_argument("--url", default="http://127.0.0.1:8097")
        command.add_argument("--model", default="gemma-4-31b-base")
        if critic:
            command.add_argument("--critic-url", default="http://127.0.0.1:8093")
            command.add_argument("--critic-model", default="gemma-4-e4b-it-read-only-critic")
        command.add_argument("--timeout", type=float, default=3600)
        command.add_argument("--admission-state", default="/private/tmp/fiction-shared-base31-admission.v1.json")
        command.add_argument("--parallel-slots", type=int, default=1)
        command.add_argument("--slot-context-tokens", type=int, default=65536)
        command.add_argument("--reserved-slot-tokens", type=int, default=2048)
        command.add_argument("--context-budget-tokens", type=int, default=63488)

    runway = autoresearch_sub.add_parser("runway", help="Generate model-authored manuscript openings")
    runway_sub = runway.add_subparsers(dest="autoresearch_runway_command", required=True)
    command = runway_sub.add_parser("sample")
    add_autoresearch_v4_runtime(command)
    command.add_argument("--seeds", type=int, nargs="+", default=[932001, 932019, 932037, 932055, 932073, 932091, 932109, 932127])
    command.add_argument("--max-tokens", type=int, default=260)
    command.add_argument("--only-cell", default="")
    command.add_argument(
        "--conditioning",
        choices=(
            "story-card", "source-anthology", "source-bookfront",
            "source-bookfront-synopsis", "graph-paired-bookfront",
            "graph-paired-canon-bookfront",
            "graph-paired-continuity-bookfront",
            "graph-paired-named-continuity-bookfront",
            "parallel-book-continuity",
            "parallel-book-persona",
        ),
        default="story-card",
    )
    command.add_argument("--source-count", type=int, default=5)
    command.add_argument("--source-ids", nargs="*", default=[])
    command.add_argument("--temperature", type=float, default=0.98)
    command.add_argument("--top-p", type=float, default=0.98)
    command.add_argument("--min-p", type=float, default=0.02)
    command.add_argument("--xtc-probability", type=float, default=0.15)
    command.add_argument("--dry-multiplier", type=float, default=0.0)
    command.add_argument("--repeat-penalty", type=float, default=1.02)
    command.set_defaults(func=_command_autoresearch_v4_runway_sample)
    command = runway_sub.add_parser(
        "sample-staged",
        help="Sample Gemma opening sparks, then continue from their exact manuscript bytes",
    )
    add_autoresearch_v4_runtime(command)
    command.add_argument("--seeds", type=int, nargs="+", required=True)
    command.add_argument("--only-cell", default="fulcrum-s01")
    command.add_argument("--source-count", type=int, default=3)
    command.add_argument("--source-ids", nargs="*", default=[])
    command.add_argument(
        "--conditioning",
        choices=(
            "parallel-book-persona", "natural-anthology",
            "direct-apprenticeship", "dwell-apprenticeship", "isomorphic-dwell",
            "ordered-isomorphic-dwell",
        ),
        default="parallel-book-persona",
    )
    command.add_argument("--spark-max-tokens", type=int, default=150)
    command.add_argument("--continuation-max-tokens", type=int, default=560)
    command.add_argument(
        "--spark-only", action="store_true",
        help="Persist eligible 35-160 word Gemma sparks as runway candidates without expansion",
    )
    command.add_argument("--temperature", type=float, default=0.95)
    command.add_argument("--top-p", type=float, default=0.97)
    command.add_argument("--min-p", type=float, default=0.02)
    command.add_argument("--xtc-probability", type=float, default=0.10)
    command.add_argument("--dry-multiplier", type=float, default=0.0)
    command.add_argument("--repeat-penalty", type=float, default=1.02)
    command.set_defaults(func=_command_autoresearch_v4_runway_sample_staged)
    command = runway_sub.add_parser("inherit", help="Reuse hash-verified Gemma runways in a new campaign")
    command.add_argument("--source-campaign", required=True)
    command.add_argument("--campaign-dir", default=str(DEFAULT_AUTORESEARCH_V4_ROOT))
    command.set_defaults(func=_command_autoresearch_v4_runway_inherit)
    command = runway_sub.add_parser(
        "trim-prefix",
        help="Derive a locked runway from an exact prefix of verified Gemma prose",
    )
    command.add_argument("--source-campaign", required=True)
    command.add_argument("--campaign-dir", default=str(DEFAULT_AUTORESEARCH_V4_ROOT))
    command.add_argument("--cell", required=True)
    command.add_argument("--paragraphs", type=int, required=True)
    command.set_defaults(func=_command_autoresearch_v4_runway_trim_prefix)

    search = autoresearch_sub.add_parser("search", help="Search prompt and sampler distributions")
    search_sub = search.add_subparsers(dest="autoresearch_search_command", required=True)
    command = search_sub.add_parser("topology")
    add_autoresearch_v4_runtime(command)
    command.add_argument("--seeds", type=int, nargs="+", default=[933001, 933019])
    command.add_argument("--max-tokens", type=int, default=760)
    command.add_argument("--only-recipe", default="")
    command.add_argument("--only-cell", default="")
    command.add_argument("--limit", type=int)
    command.set_defaults(func=_command_autoresearch_v4_search_topology)
    command = search_sub.add_parser(
        "topology-staged",
        help="Sample a causal Gemma spark, then continue from its exact prose bytes",
    )
    add_autoresearch_v4_runtime(command)
    command.add_argument("--seeds", type=int, nargs="+", required=True)
    command.add_argument("--recipe", default="v4-anthology")
    command.add_argument("--cell", default="charged-restraint")
    command.add_argument("--spark-max-tokens", type=int, default=240)
    command.add_argument("--spark-max-words", type=int, default=350)
    command.add_argument("--continuation-max-tokens", type=int, default=620)
    command.set_defaults(func=_command_autoresearch_v4_search_topology_staged)
    command = search_sub.add_parser(
        "topology-branch",
        help="Sample independent Gemma continuations from one verified causal spark",
    )
    add_autoresearch_v4_runtime(command)
    command.add_argument("--parent-candidate", required=True)
    command.add_argument("--seeds", type=int, nargs="+", required=True)
    command.add_argument("--max-tokens", type=int, default=620)
    command.set_defaults(func=_command_autoresearch_v4_search_topology_branch)
    command = search_sub.add_parser("behavioral")
    add_autoresearch_v4_runtime(command)
    command.add_argument("--parents", nargs="*", default=[])
    command.add_argument("--seeds", type=int, nargs="+", default=[933071, 933089])
    command.add_argument("--max-tokens", type=int, default=760)
    command.add_argument("--only-recipe", default="")
    command.add_argument("--only-cell", default="")
    command.add_argument("--limit", type=int)
    command.set_defaults(func=_command_autoresearch_v4_search_behavioral)
    command = search_sub.add_parser("context")
    add_autoresearch_v4_runtime(command)
    command.add_argument("--seeds", type=int, nargs="+", default=[933101, 933119, 933137, 933155])
    command.add_argument("--max-tokens", type=int, default=760)
    command.add_argument("--only-recipe", default="")
    command.add_argument("--only-cell", default="")
    command.add_argument("--limit", type=int)
    command.set_defaults(func=_command_autoresearch_v4_search_context)
    command = search_sub.add_parser("sampler")
    add_autoresearch_v4_runtime(command)
    command.add_argument("--seeds", type=int, nargs="+", default=[934001, 934019, 934037, 934055, 934073, 934091])
    command.add_argument("--max-tokens", type=int, default=760)
    command.add_argument("--only-recipe", default="")
    command.add_argument("--only-cell", default="")
    command.add_argument("--limit", type=int)
    command.set_defaults(func=_command_autoresearch_v4_search_sampler)

    command = autoresearch_sub.add_parser("judge", help="Read-only literary judging for a frozen phase")
    add_autoresearch_v4_runtime(command, critic=True)
    command.add_argument("--phase", choices=("runways", "topology", "topology-staged", "topology-branch", "behavioral", "context", "sampler", "bootstrap"), required=True)
    command.add_argument("--only-candidate", default="")
    command.add_argument("--pairwise", action="store_true")
    command.add_argument("--recipe-ids", nargs="*", default=[])
    command.add_argument("--limit", type=int)
    command.set_defaults(func=_command_autoresearch_v4_judge)

    command = autoresearch_sub.add_parser("promote", help="Apply v4 promotion without rewriting prose")
    command.add_argument("--campaign-dir", default=str(DEFAULT_AUTORESEARCH_V4_ROOT))
    command.add_argument("--phase", choices=("runways", "topology", "behavioral", "context", "sampler", "bootstrap"), required=True)
    command.add_argument("--select", nargs="*", default=[])
    command.set_defaults(func=_command_autoresearch_v4_promote)

    command = autoresearch_sub.add_parser("bootstrap", help="Generate verified Gemma project movements")
    add_autoresearch_v4_runtime(command)
    command.add_argument("--seeds", type=int, nargs="+", default=[935001 + 17 * index for index in range(24)])
    command.add_argument("--max-tokens", type=int, default=760)
    command.add_argument("--limit", type=int)
    command.set_defaults(func=_command_autoresearch_v4_bootstrap)

    command = autoresearch_sub.add_parser("trajectories", help="Sample verbatim Gemma S01 trajectories")
    add_autoresearch_v4_runtime(command, critic=True)
    command.add_argument("--seeds", type=int, nargs="+", default=[936001 + 17 * index for index in range(32)])
    command.add_argument("--max-tokens", type=int, default=850)
    command.add_argument("--select-count", type=int, default=4)
    command.set_defaults(func=_command_autoresearch_v4_trajectories)

    loom = autoresearch_sub.add_parser("loom", help="Branch and rank raw Gemma continuations")
    loom_sub = loom.add_subparsers(dest="autoresearch_loom_command", required=True)
    command = loom_sub.add_parser("run")
    add_autoresearch_v4_runtime(command, critic=True)
    command.add_argument("--cell", required=True)
    command.add_argument("--recipe", default="")
    command.add_argument("--trajectory-id", default="")
    command.add_argument("--prefix-candidate", default="")
    command.add_argument(
        "--prefix-campaign", default="",
        help="Campaign containing a hash-verified Gemma prefix candidate or loom branch",
    )
    command.add_argument("--start-movement", type=int, default=1)
    command.add_argument(
        "--stop-after-movements", type=int, default=0,
        help="Stop at a durable branch-selection boundary after N movements",
    )
    command.add_argument(
        "--movement-local-sources", action="store_true",
        help="Derive a one-axis recipe whose raw exemplars match each dramatic movement",
    )
    command.add_argument(
        "--movement-excerpt-sources", action="store_true",
        help="Use movement-matched exact source excerpts at the target dwell length",
    )
    command.add_argument("--branches", type=int, default=6)
    command.add_argument("--survivors", type=int, default=2)
    command.add_argument(
        "--max-resample-pools", type=int, default=3,
        help="Bound fresh branch pools at one manuscript boundary (1..3)",
    )
    command.add_argument("--movement-min-words", type=int, default=250)
    command.add_argument("--movement-max-words", type=int, default=450)
    command.add_argument("--max-tokens", type=int, default=760)
    command.add_argument("--seed", type=int, default=1250001)
    command.set_defaults(func=_command_autoresearch_v4_loom)

    command = loom_sub.add_parser(
        "audition", help="Sample verbatim Gemma movements at a stubborn boundary",
    )
    add_autoresearch_v4_runtime(command, critic=True)
    command.add_argument("--cell", required=True)
    command.add_argument("--prefix-candidate", required=True)
    command.add_argument("--prefix-campaign", required=True)
    command.add_argument("--movement-number", type=int, required=True)
    command.add_argument("--seeds", type=int, nargs="+", required=True)
    command.add_argument("--source-count", type=int, default=1)
    command.add_argument(
        "--background-source-count", type=int, default=0,
        help="Add full mode-matched apprenticeship scenes before the nearest exact excerpt",
    )
    command.add_argument(
        "--paired-examples", action="store_true",
        help="Render each source as a dramatic-design to exact-prose apprenticeship pair",
    )
    command.add_argument(
        "--matched-source-id", action="append", default=[],
        help="Pin a profiling source scene before exact movement excerpting; repeat as needed",
    )
    command.add_argument("--max-tokens", type=int, default=300)
    command.set_defaults(func=_command_autoresearch_v4_movement_audition)

    command = loom_sub.add_parser(
        "readmit", help="Re-evaluate an immutable Gemma audition under current gates",
    )
    add_autoresearch_v4_runtime(command, critic=True)
    command.add_argument("--cell", required=True)
    command.add_argument("--source-campaign", required=True)
    command.add_argument("--source-branch", required=True)
    command.add_argument("--prefix-campaign", required=True)
    command.add_argument("--movement-number", type=int, required=True)
    command.set_defaults(func=_command_autoresearch_v4_readmit_movement)

    command = loom_sub.add_parser(
        "mine-sparks", help="Mine exact causal boundary paragraphs from failed Gemma auditions",
    )
    command.add_argument("--campaign-dir", required=True)
    command.add_argument("--source-campaign", required=True)
    command.add_argument("--cell", required=True)
    command.add_argument("--prefix-candidate", required=True)
    command.add_argument("--prefix-campaign", required=True)
    command.add_argument("--movement-number", type=int, required=True)
    command.set_defaults(func=_command_autoresearch_v4_mine_movement_sparks)

    command = autoresearch_sub.add_parser("verify-v4", help="Verify model-span assembly")
    command.add_argument("assembly")
    command.set_defaults(func=_command_autoresearch_v4_verify)
    command = autoresearch_sub.add_parser("replay-v4", help="Cold-replay one frozen Gemma base call")
    add_autoresearch_v4_runtime(command)
    command.add_argument("call_id")
    command.set_defaults(func=_command_autoresearch_v4_replay)
    command = autoresearch_sub.add_parser("reextract-v4", help="Re-derive paragraph spans from preserved raw responses")
    command.add_argument("--campaign-dir", default=str(DEFAULT_AUTORESEARCH_V4_ROOT))
    command.add_argument(
        "--phase",
        choices=("topology", "topology-staged", "topology-branch", "behavioral", "context", "sampler", "bootstrap", "loom"),
        default="topology",
    )
    command.add_argument("--minimum-words", type=int, default=300)
    command.add_argument("--maximum-words", type=int, default=500)
    command.set_defaults(func=_command_autoresearch_v4_reextract)
    command = autoresearch_sub.add_parser("revalidate-v4", help="Recompute deterministic gates without changing prose")
    command.add_argument("--campaign-dir", default=str(DEFAULT_AUTORESEARCH_V4_ROOT))
    command.add_argument(
        "--phase",
        choices=("topology", "topology-staged", "topology-branch", "behavioral", "context", "sampler", "bootstrap", "loom"),
        default="topology",
    )
    command.set_defaults(func=_command_autoresearch_v4_revalidate)
    command = autoresearch_sub.add_parser(
        "audit-assemblies-v4",
        help="Write a non-mutating invalidation ledger for every historical V4 assembly",
    )
    command.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "04_review_governance" / "provenance" / "v4_assembly_invalidation.v1.json"),
    )
    command.set_defaults(func=_command_autoresearch_v4_audit_assemblies)

    round_cmd = autoresearch_sub.add_parser("round", help="Run a resumable research round")
    round_sub = round_cmd.add_subparsers(dest="autoresearch_round_command", required=True)
    command = round_sub.add_parser("run")
    command.add_argument("--round", type=int, choices=(1, 2, 3), required=True)
    command.add_argument("--campaign-dir", default=str(DEFAULT_AUTORESEARCH_ROOT))
    command.add_argument("--url", default="http://127.0.0.1:8097")
    command.add_argument("--model", default="gemma-4-31b-base")
    command.add_argument("--max-tokens", type=int, default=2000)
    command.add_argument("--timeout", type=float, default=3600)
    command.add_argument("--only-recipe")
    command.add_argument("--only-cell")
    command.add_argument("--only-seed", type=int)
    command.add_argument("--limit", type=int)
    command.add_argument("--admission-state", default="/private/tmp/fiction-shared-base31-admission.v1.json")
    command.add_argument("--parallel-slots", type=int, default=4)
    command.add_argument("--slot-context-tokens", type=int, default=32768)
    command.add_argument("--reserved-slot-tokens", type=int, default=2048)
    command.add_argument("--context-budget-tokens", type=int, default=122880)
    command.set_defaults(func=_command_autoresearch_round_run)

    review = autoresearch_sub.add_parser("review", help="Export or admit blinded reviews")
    review_sub = review.add_subparsers(dest="autoresearch_review_command", required=True)
    command = review_sub.add_parser("export")
    command.add_argument("--campaign-dir", default=str(DEFAULT_AUTORESEARCH_ROOT))
    command.add_argument("--round", type=int, choices=(1, 2, 3), required=True)
    command.add_argument("--output")
    command.set_defaults(func=_command_autoresearch_review_export)
    command = review_sub.add_parser("admit")
    command.add_argument("--campaign-dir", default=str(DEFAULT_AUTORESEARCH_ROOT))
    command.add_argument("--round", type=int, choices=(1, 2, 3), required=True)
    command.add_argument("--review-file", required=True)
    command.add_argument("--reviewer-id", required=True)
    command.set_defaults(func=_command_autoresearch_review_admit)
    command = review_sub.add_parser(
        "admit-research",
        help="Admit a post-blind prompt/trace critique",
    )
    command.add_argument("--campaign-dir", default=str(DEFAULT_AUTORESEARCH_ROOT))
    command.add_argument("--round", type=int, choices=(1, 2, 3), required=True)
    command.add_argument("--review-file", required=True)
    command.add_argument("--reviewer-id", required=True)
    command.add_argument(
        "--role", choices=("trace_critic", "research_lead"), required=True
    )
    command.set_defaults(func=_command_autoresearch_review_admit_research)
    command = review_sub.add_parser(
        "admit-v4-research", help="Admit hash-linked v4 prompt/trace criticism"
    )
    command.add_argument("--campaign-dir", default=str(DEFAULT_AUTORESEARCH_V4_ROOT))
    command.add_argument("--phase", choices=("topology", "topology-staged", "topology-branch", "behavioral", "context", "sampler", "bootstrap", "loom"), default="topology")
    command.add_argument("--review-file", required=True)
    command.add_argument("--reviewer-id", required=True)
    command.add_argument("--role", choices=("trace_critic", "research_lead"), required=True)
    command.set_defaults(func=_command_autoresearch_v4_review_admit)

    overlap = autoresearch_sub.add_parser(
        "overlap", help="Resolve locally flagged source-neighbor overlaps"
    )
    overlap_sub = overlap.add_subparsers(
        dest="autoresearch_overlap_command", required=True
    )
    command = overlap_sub.add_parser("adjudicate")
    command.add_argument("--campaign-dir", default=str(DEFAULT_AUTORESEARCH_ROOT))
    command.add_argument("--round", type=int, choices=(1, 2, 3), required=True)
    command.add_argument("--url", default="http://127.0.0.1:8093")
    command.add_argument("--model", default="gemma-4-e4b-it-local-copy-judge")
    command.add_argument("--timeout", type=float, default=1800)
    command.add_argument("--output")
    command.set_defaults(func=_command_autoresearch_overlap_adjudicate)

    traces = autoresearch_sub.add_parser("traces", help="Analyze prompts and traces after blind review")
    traces_sub = traces.add_subparsers(dest="autoresearch_traces_command", required=True)
    command = traces_sub.add_parser("analyze")
    command.add_argument("--campaign-dir", default=str(DEFAULT_AUTORESEARCH_ROOT))
    command.add_argument("--round", type=int, choices=(1, 2, 3), required=True)
    command.add_argument("--output")
    command.set_defaults(func=_command_autoresearch_traces_analyze)
    command = traces_sub.add_parser("analyze-v4")
    command.add_argument("--campaign-dir", default=str(DEFAULT_AUTORESEARCH_V4_ROOT))
    command.add_argument("--phase", choices=("topology", "topology-staged", "topology-branch", "behavioral", "context", "sampler", "bootstrap", "loom"), default="topology")
    command.add_argument("--output")
    command.set_defaults(func=_command_autoresearch_v4_traces_analyze)

    command = autoresearch_sub.add_parser("decide", help="Apply the preregistered promotion rule")
    command.add_argument("--campaign-dir", default=str(DEFAULT_AUTORESEARCH_ROOT))
    command.add_argument("--round", type=int, choices=(1, 2, 3), required=True)
    command.add_argument("--trace-analysis")
    command.add_argument("--output")
    command.set_defaults(func=_command_autoresearch_decide)
    command = autoresearch_sub.add_parser("report", help="Render the campaign report")
    command.add_argument("--campaign-dir", default=str(DEFAULT_AUTORESEARCH_ROOT))
    command.add_argument("--output")
    command.set_defaults(func=_command_autoresearch_report)
    command = autoresearch_sub.add_parser(
        "package", help="Build the final blinded HTML and Markdown packet"
    )
    command.add_argument("--campaign-dir", default=str(DEFAULT_AUTORESEARCH_V4_ROOT))
    command.add_argument("--round", type=int, choices=(1, 2, 3), default=1)
    command.add_argument("--cell", default="fulcrum-s01")
    command.add_argument("--output")
    command.add_argument("--max-finalists", type=int, default=6)
    command.set_defaults(func=_command_autoresearch_package)

    autoloom = subparsers.add_parser(
        "autoloom",
        help="Run entropy-preserving base-program to base-prose experiments",
    )
    autoloom_sub = autoloom.add_subparsers(dest="autoloom_command", required=True)
    command = autoloom_sub.add_parser("init", help="Freeze an autoloom campaign")
    command.add_argument("--campaign-dir", default=str(DEFAULT_AUTOLOOM_ROOT))
    command.add_argument("--source", default=str(DEFAULT_AUTORESEARCH_SOURCE))
    command.add_argument("--bridges", default=str(DEFAULT_AUTORESEARCH_BRIDGES))
    command.add_argument("--parent-program-set")
    command.add_argument("--apprenticeship-index")
    command.add_argument("--apprenticeship-retrieval")
    command.set_defaults(func=_command_autoloom_init)

    def add_autoloom_runtime(command: argparse.ArgumentParser) -> None:
        command.add_argument("--campaign-dir", default=str(DEFAULT_AUTOLOOM_ROOT))
        command.add_argument("--url", default="http://127.0.0.1:8097")
        command.add_argument("--model", default="gemma-4-31b-base")
        command.add_argument("--timeout", type=float, default=3600)
        command.add_argument("--admission-state", default="/private/tmp/fiction-shared-base31-admission.v1.json")
        command.add_argument("--parallel-slots", type=int, default=4)
        command.add_argument("--slot-context-tokens", type=int, default=32768)
        command.add_argument("--reserved-slot-tokens", type=int, default=2048)
        command.add_argument("--context-budget-tokens", type=int, default=122880)

    command = autoloom_sub.add_parser("propose", help="Sample and lock diverse story programs")
    add_autoloom_runtime(command)
    command.add_argument("--only-cell")
    command.add_argument("--max-tokens", type=int, default=700)
    command.set_defaults(func=_command_autoloom_propose)
    command = autoloom_sub.add_parser(
        "propose-mode", help="Sample intimacy engines and compose them with causal programs"
    )
    add_autoloom_runtime(command)
    command.add_argument("--only-cell")
    command.add_argument("--max-tokens", type=int, default=850)
    command.set_defaults(func=_command_autoloom_propose_mode)
    command = autoloom_sub.add_parser(
        "replay-causal", help="Reparse preserved causal draws without inference"
    )
    command.add_argument("--campaign-dir", default=str(DEFAULT_AUTOLOOM_ROOT))
    command.add_argument("--source-dir", required=True)
    command.add_argument("--only-cell")
    command.set_defaults(func=_command_autoloom_replay_causal)
    command = autoloom_sub.add_parser(
        "replay-mode", help="Reparse preserved mode draws without inference"
    )
    command.add_argument("--campaign-dir", default=str(DEFAULT_AUTOLOOM_ROOT))
    command.add_argument("--source-dir", required=True)
    command.add_argument("--only-cell")
    command.set_defaults(func=_command_autoloom_replay_mode)
    command = autoloom_sub.add_parser("draft", help="Generate scenes from locked programs")
    add_autoloom_runtime(command)
    command.add_argument("--only-recipe")
    command.add_argument("--only-cell")
    command.add_argument("--only-seed", type=int)
    command.add_argument("--limit", type=int)
    command.add_argument("--max-tokens", type=int, default=2000)
    command.set_defaults(func=_command_autoloom_draft)
    command = autoloom_sub.add_parser(
        "staged", help="Sample and select one resumable manuscript stage"
    )
    add_autoloom_runtime(command)
    command.add_argument("--stage", choices=("approach", "transaction", "aftermath"), required=True)
    command.add_argument("--recipe", default="loom-runway-doc")
    command.add_argument("--cell", default="married-explicit")
    command.add_argument("--limit", type=int)
    command.set_defaults(func=_command_autoloom_staged)
    command = autoloom_sub.add_parser(
        "propose-transaction", help="Sample stage-local embodied transaction programs"
    )
    add_autoloom_runtime(command)
    command.add_argument("--max-tokens", type=int, default=1050)
    command.set_defaults(func=_command_autoloom_propose_transaction)
    command = autoloom_sub.add_parser(
        "import-approach", help="Import immutable approach checkpoints into a prompt fork"
    )
    command.add_argument("--campaign-dir", default=str(DEFAULT_AUTOLOOM_ROOT))
    command.add_argument("--source-selection", required=True)
    command.set_defaults(func=_command_autoloom_import_approach)
    command = autoloom_sub.add_parser(
        "import-programs", help="Import an immutable program set into a prompt fork"
    )
    command.add_argument("--campaign-dir", default=str(DEFAULT_AUTOLOOM_ROOT))
    command.add_argument("--source-program-set", required=True)
    command.set_defaults(func=_command_autoloom_import_programs)
    command = autoloom_sub.add_parser(
        "replay-transaction", help="Reparse preserved transaction-program draws without inference"
    )
    command.add_argument("--campaign-dir", default=str(DEFAULT_AUTOLOOM_ROOT))
    command.add_argument("--source-dir", required=True)
    command.set_defaults(func=_command_autoloom_replay_transaction)
    command = autoloom_sub.add_parser(
        "replay-transaction-candidates",
        help="Re-evaluate preserved transaction prose without inference",
    )
    command.add_argument("--campaign-dir", default=str(DEFAULT_AUTOLOOM_ROOT))
    command.add_argument("--source-candidates", required=True)
    command.set_defaults(func=_command_autoloom_replay_transaction_candidates)
    command = autoloom_sub.add_parser("summarize", help="Render mechanical and diversity results")
    command.add_argument("--campaign-dir", default=str(DEFAULT_AUTOLOOM_ROOT))
    command.add_argument("--output")
    command.set_defaults(func=_command_autoloom_summarize)

    apprenticeship = subparsers.add_parser(
        "apprenticeship",
        help="Build retrieved literary apprenticeship prompts for base models",
    )
    apprenticeship_sub = apprenticeship.add_subparsers(
        dest="apprenticeship_command", required=True
    )
    command = apprenticeship_sub.add_parser(
        "fetch", help="Fetch a literary source set"
    )
    command.add_argument("--spec", required=True)
    command.add_argument("--output", required=True)
    command.set_defaults(func=_command_apprenticeship_fetch)
    command = apprenticeship_sub.add_parser(
        "index", help="Segment works and compile the hybrid scene index"
    )
    command.add_argument("--manifest", required=True)
    command.add_argument("--output", required=True)
    command.set_defaults(func=_command_apprenticeship_index)
    command = apprenticeship_sub.add_parser(
        "retrieve", help="Retrieve a diverse stage-matched apprenticeship set"
    )
    command.add_argument("--index", required=True)
    command.add_argument("--query", required=True)
    command.add_argument("--output")
    command.set_defaults(func=_command_apprenticeship_retrieve)
    command = apprenticeship_sub.add_parser(
        "compile", help="Compile retrieved scenes into a base-model prompt"
    )
    command.add_argument("--index", required=True)
    command.add_argument("--retrieval", required=True)
    command.add_argument("--target-contract", required=True)
    command.add_argument("--runway", required=True)
    command.add_argument("--output", required=True)
    command.set_defaults(func=_command_apprenticeship_compile)

    ontology = subparsers.add_parser(
        "ontology", help="Browse the Romance Generation Ontology"
    )
    ontology_sub = ontology.add_subparsers(dest="ontology_command", required=True)
    command = ontology_sub.add_parser("list", help="List RGO coordinates")
    command.add_argument("--ontology", default=str(DEFAULT_ONTOLOGY_PATH))
    command.add_argument("--namespace")
    command.set_defaults(func=_command_ontology_list)
    command = ontology_sub.add_parser("show", help="Show one RGO coordinate")
    command.add_argument("node_id")
    command.add_argument("--ontology", default=str(DEFAULT_ONTOLOGY_PATH))
    command.set_defaults(func=_command_ontology_show)

    profile = subparsers.add_parser(
        "profile", help="Validate and resolve creative profiles"
    )
    profile_sub = profile.add_subparsers(dest="profile_command", required=True)
    command = profile_sub.add_parser("validate", help="Validate and hash profiles")
    command.add_argument(
        "profile", nargs="?", default=str(DEFAULT_STORY_PROFILE_PATH)
    )
    command.add_argument(
        "--scene-profile", default=str(DEFAULT_SCENE_PROFILE_PATH)
    )
    command.add_argument("--ontology", default=str(DEFAULT_ONTOLOGY_PATH))
    command.set_defaults(func=_command_profile_validate)
    command = profile_sub.add_parser(
        "resolve", help="Render the fully inherited creative profile"
    )
    command.add_argument(
        "profile", nargs="?", default=str(DEFAULT_STORY_PROFILE_PATH)
    )
    command.add_argument(
        "--scene-profile", default=str(DEFAULT_SCENE_PROFILE_PATH)
    )
    command.add_argument("--ontology", default=str(DEFAULT_ONTOLOGY_PATH))
    command.add_argument("--output")
    command.set_defaults(func=_command_profile_resolve)

    author = subparsers.add_parser(
        "author", help="Manage author corpora, profiles, copy checks, and experiments"
    )
    author_sub = author.add_subparsers(dest="author_command", required=True)

    manifest = author_sub.add_parser("manifest", help="Author corpus operations")
    manifest_sub = manifest.add_subparsers(
        dest="author_manifest_command", required=True
    )
    command = manifest_sub.add_parser(
        "validate", help="Validate corpus partitions and local hashes"
    )
    command.add_argument("--manifest", default=str(DEFAULT_AUTHOR_MANIFEST))
    command.add_argument(
        "--audit-holdout-hash",
        action="store_true",
        help="Read the holdout solely to verify its declared hash",
    )
    command.set_defaults(func=_command_author_manifest_validate)

    segments = author_sub.add_parser("segments", help="Source-segment operations")
    segments_sub = segments.add_subparsers(
        dest="author_segments_command", required=True
    )
    command = segments_sub.add_parser(
        "compile", help="Compile non-holdout segment metadata"
    )
    command.add_argument("--manifest", default=str(DEFAULT_AUTHOR_MANIFEST))
    command.add_argument(
        "--partition",
        action="append",
        choices=("profiling", "calibration"),
        default=["profiling"],
    )
    command.add_argument("--output")
    command.add_argument("--verbose", action="store_true")
    command.set_defaults(func=_command_author_segments_compile)

    profile_cmd = author_sub.add_parser(
        "profile", help="Validate or resolve derived author profiles"
    )
    profile_sub = profile_cmd.add_subparsers(
        dest="author_profile_command", required=True
    )
    for action, handler in (
        ("validate", _command_author_profile_validate),
        ("resolve", _command_author_profile_resolve),
    ):
        command = profile_sub.add_parser(action)
        command.add_argument("--manifest", default=str(DEFAULT_AUTHOR_MANIFEST))
        command.add_argument(
            "--author-profile", default=str(DEFAULT_AUTHOR_PROFILE)
        )
        command.add_argument(
            "--transformation-map", default=str(DEFAULT_TRANSFORMATION_MAP)
        )
        command.add_argument("--ontology", default=str(DEFAULT_ONTOLOGY_PATH))
        if action == "resolve":
            command.add_argument(
                "--conditioning-variant",
                default="anonymous-profile",
                choices=(
                    "none",
                    "name-only",
                    "anonymous-profile",
                    "named-profile",
                    "profile-sparse-exemplars",
                    "plot-review-nshot",
                    "dense-retrieval",
                    "raw-rag",
                ),
            )
            command.add_argument(
                "--prompt-encoding",
                default="xml",
                choices=("xml", "markdown", "json"),
            )
            command.add_argument(
                "--control-density",
                default="medium",
                choices=("organic", "light", "medium", "dense", "raw-rag"),
            )
            command.add_argument("--output")
            command.add_argument(
                "--conditioning-material",
                help=(
                    "Explicit JSON list for sparse-exemplar, plot/review, or "
                    "retrieval experimental variants"
                ),
            )
        command.set_defaults(func=handler)

    copy_cmd = author_sub.add_parser("anti-copy", help="Local overlap operations")
    copy_sub = copy_cmd.add_subparsers(
        dest="author_anti_copy_command", required=True
    )
    command = copy_sub.add_parser("build", help="Build source index metadata")
    command.add_argument("--manifest", default=str(DEFAULT_AUTHOR_MANIFEST))
    command.add_argument("--output")
    command.set_defaults(func=_command_author_anti_copy_build)
    command = copy_sub.add_parser("check", help="Check one candidate locally")
    command.add_argument("candidate")
    command.add_argument("--manifest", default=str(DEFAULT_AUTHOR_MANIFEST))
    command.set_defaults(func=_command_author_anti_copy_check)

    command = author_sub.add_parser(
        "experiment-plan",
        help="Emit calibration and provisional full-S01 designs",
    )
    command.add_argument(
        "--graph-id", action="append", default=["calibration-a", "calibration-b"]
    )
    command.add_argument(
        "--seed", action="append", type=int, default=[4101, 4102, 4103, 4104]
    )
    command.add_argument(
        "--winning-encoding",
        default="xml",
        choices=("xml", "markdown", "json"),
    )
    command.add_argument(
        "--full-variant",
        action="append",
        default=None,
        choices=(
            "none",
            "name-only",
            "anonymous-profile",
            "named-profile",
            "profile-sparse-exemplars",
            "plot-review-nshot",
            "dense-retrieval",
        ),
        help=(
            "One of exactly two provisional full-S01 author variants; defaults "
            "to anonymous-profile and named-profile"
        ),
    )
    command.add_argument("--output")
    command.add_argument("--verbose", action="store_true")
    command.set_defaults(func=_command_author_experiment_plan)

    command = author_sub.add_parser(
        "run",
        help="Run base ideation, 26B compilation, and base-writer drafting",
    )
    command.add_argument("--manifest", default=str(DEFAULT_AUTHOR_MANIFEST))
    command.add_argument("--author-profile", default=str(DEFAULT_AUTHOR_PROFILE))
    command.add_argument(
        "--transformation-map", default=str(DEFAULT_TRANSFORMATION_MAP)
    )
    command.add_argument(
        "--compiled", default=str(DEFAULT_ONTOLOGY_COMPILED)
    )
    command.add_argument(
        "--gabaldon-profile",
        default=str(
            PROJECT_ROOT
            / "fiction_harness"
            / "craft_profiles"
            / "gabaldon_intimacy_v1.json"
        ),
    )
    command.add_argument("--run-root", default=str(DEFAULT_AUTHOR_RUN_ROOT))
    command.add_argument("--run-id", default="s01-author-control-v1")
    command.add_argument("--ideator-url", default="http://127.0.0.1:8094")
    command.add_argument("--compiler-url", default="http://127.0.0.1:8091")
    command.add_argument("--writer-url", default="http://127.0.0.1:8095")
    command.add_argument(
        "--conditioning-variant",
        default="anonymous-profile",
        choices=(
            "none",
            "name-only",
            "anonymous-profile",
            "named-profile",
            "profile-sparse-exemplars",
            "plot-review-nshot",
            "dense-retrieval",
            "raw-rag",
        ),
    )
    command.add_argument(
        "--prompt-encoding",
        default="xml",
        choices=("xml", "markdown", "json"),
    )
    command.add_argument(
        "--control-density",
        default="medium",
        choices=("organic", "light", "medium", "dense", "raw-rag"),
    )
    command.add_argument("--idea-count", type=int, default=32, choices=range(8, 33))
    command.add_argument("--count", type=int, default=8, choices=range(1, 9))
    command.add_argument("--output-tokens", type=int, default=6_144)
    command.add_argument("--frontier-adapter", default="none-local")
    command.add_argument(
        "--conditioning-material",
        help=(
            "Explicit JSON list for source-exposure experimental variants; "
            "omitted for all normal derived-profile runs"
        ),
    )
    command.add_argument("--timeout", type=float, default=1_800)
    command.set_defaults(func=_command_author_run)

    command = author_sub.add_parser(
        "evaluate",
        help="Run local copy/style diagnostics and optional evidence-backed 31B judging",
    )
    command.add_argument("--manifest", default=str(DEFAULT_AUTHOR_MANIFEST))
    command.add_argument("--author-profile", default=str(DEFAULT_AUTHOR_PROFILE))
    command.add_argument(
        "--transformation-map", default=str(DEFAULT_TRANSFORMATION_MAP)
    )
    command.add_argument(
        "--compiled", default=str(DEFAULT_ONTOLOGY_COMPILED)
    )
    command.add_argument("--run-root", default=str(DEFAULT_AUTHOR_RUN_ROOT))
    command.add_argument(
        "--output-dir",
        default=str(DEFAULT_AUTHOR_RUN_ROOT / "evaluation"),
    )
    command.add_argument("--judge-url")
    command.add_argument(
        "--conditioning-variant",
        default="anonymous-profile",
        choices=(
            "none",
            "name-only",
            "anonymous-profile",
            "named-profile",
            "profile-sparse-exemplars",
            "plot-review-nshot",
            "dense-retrieval",
            "raw-rag",
        ),
    )
    command.add_argument(
        "--prompt-encoding", default="xml", choices=("xml", "markdown", "json")
    )
    command.add_argument(
        "--control-density",
        default="medium",
        choices=("organic", "light", "medium", "dense", "raw-rag"),
    )
    command.add_argument("--conditioning-material")
    command.add_argument("--timeout", type=float, default=1_800)
    command.set_defaults(func=_command_author_evaluate)

    command = subparsers.add_parser("serve", help="Serve one exact local model role")
    command.add_argument(
        "role",
        choices=(
            "base_ideator",
            "base_writer",
            "base_31b_writer",
            "base_31b_writer_full",
            "generator",
            "planner",
            "editor",
            "raw_writer",
            "fast_judge",
        ),
    )
    command.add_argument("--host", default="127.0.0.1")
    command.add_argument("--port", type=int)
    command.add_argument("--dry-run", action="store_true")
    command.set_defaults(func=_command_serve)

    command = subparsers.add_parser(
        "convert-base", help="Convert cached Gemma base checkpoints to Q8 GGUF"
    )
    command.add_argument(
        "role", choices=("base_ideator", "base_writer", "all")
    )
    command.add_argument("--python", default=sys.executable)
    command.add_argument(
        "--converter", default="/Users/george/llama.cpp/convert_hf_to_gguf.py"
    )
    command.add_argument("--force", action="store_true")
    command.add_argument("--dry-run", action="store_true")
    command.set_defaults(func=_command_convert_base)

    command = subparsers.add_parser("run", help="Run one or all generation pipelines")
    command.add_argument(
        "pipeline",
        choices=("all", "direct", "verbalized", "verbalized_sampling", "actor", "actor_novelist"),
    )
    command.add_argument("--compiled", default=str(DEFAULT_COMPILED))
    command.add_argument("--run-root", default=str(DEFAULT_RUN_ROOT))
    command.add_argument("--run-id", default="s01-comparison-v1")
    command.add_argument("--generator-url", default="http://127.0.0.1:8091")
    command.add_argument("--fast-url", default="http://127.0.0.1:8093")
    command.add_argument("--count", type=int, default=8, choices=range(1, 9))
    command.add_argument("--output-tokens", type=int, default=6_144)
    command.add_argument("--timeout", type=float, default=1_800)
    command.set_defaults(func=_command_run)

    command = subparsers.add_parser(
        "evaluate", help="Gate, judge, and tournament-rank raw candidates"
    )
    command.add_argument(
        "--phase", choices=("score", "tournament"), default="score"
    )
    command.add_argument("--compiled", default=str(DEFAULT_COMPILED))
    command.add_argument("--run-root", default=str(DEFAULT_RUN_ROOT))
    command.add_argument("--evaluation-dir", default=str(DEFAULT_EVALUATION))
    command.add_argument("--judge-url", default="http://127.0.0.1:8092")
    command.add_argument("--judge-passes", type=int, default=2, choices=(1, 2))
    command.add_argument(
        "--rubric",
        default="v1",
        help="v1, gabaldon-v2, or a rubric JSON path",
    )
    command.add_argument("--timeout", type=float, default=1_800)
    command.set_defaults(func=_command_evaluate)

    command = subparsers.add_parser(
        "craft-audit",
        help="Run deterministic intimacy-craft diagnostics over preserved candidates",
    )
    command.add_argument("--compiled", default=str(DEFAULT_COMPILED))
    command.add_argument("--run-root", default=str(DEFAULT_RUN_ROOT))
    command.add_argument("--rubric", default="gabaldon-v2")
    command.add_argument("--output")
    command.add_argument("--verbose", action="store_true")
    command.set_defaults(func=_command_craft_audit)

    command = subparsers.add_parser("package", help="Build the blind HTML/Markdown packet")
    command.add_argument(
        "--finalists", default=str(DEFAULT_EVALUATION / "finalists.json")
    )
    command.add_argument(
        "--output", default=str(DEFAULT_RUN_ROOT / "appraisal")
    )
    command.add_argument("--blind-seed", default="s01-human-appraisal-v1")
    command.set_defaults(func=_command_package)

    feedback = subparsers.add_parser(
        "feedback", help="Build and aggregate blind human-feedback packets"
    )
    feedback_sub = feedback.add_subparsers(
        dest="feedback_command", required=True
    )
    command = feedback_sub.add_parser(
        "package-pairs", help="Build A/B, A/C, B/C, and all-three packets"
    )
    command.add_argument(
        "--finalists", default=str(DEFAULT_EVALUATION / "finalists.json")
    )
    command.add_argument(
        "--reveal-key",
        default=str(DEFAULT_RUN_ROOT / "internal" / "reveal_key.json"),
    )
    command.add_argument("--output", default=str(DEFAULT_FEEDBACK_ROOT))
    command.add_argument("--title", default="The Calibration Game")
    command.set_defaults(func=_command_feedback_package_pairs)
    command = feedback_sub.add_parser(
        "summarize", help="Aggregate exported reader response JSON files"
    )
    command.add_argument("responses", nargs="+")
    command.add_argument("--package-id")
    command.add_argument(
        "--output",
        default=str(DEFAULT_FEEDBACK_ROOT / "human_feedback_brief.v1.json"),
    )
    command.set_defaults(func=_command_feedback_summarize)
    command = feedback_sub.add_parser(
        "bootstrap",
        help="Build a clearly marked non-human brief from blind Codex reviews",
    )
    command.add_argument(
        "--reviews",
        action="append",
        required=True,
        help="Blind Codex reviewer JSON; repeat for each reviewer",
    )
    command.add_argument(
        "--reveal-key",
        default=str(DEFAULT_RUN_ROOT / "internal" / "reveal_key.json"),
    )
    command.add_argument(
        "--output",
        default=str(DEFAULT_FEEDBACK_ROOT / "bootstrap_feedback_brief.v1.json"),
    )
    command.set_defaults(func=_command_feedback_bootstrap)

    continuation = subparsers.add_parser(
        "continuation",
        help="Prepare, generate, and gate the controlled S02 proof stories",
    )
    continuation_sub = continuation.add_subparsers(
        dest="continuation_command", required=True
    )

    def add_continuation_inputs(command: argparse.ArgumentParser) -> None:
        command.add_argument("--compiled", default=str(DEFAULT_S02_COMPILED))
        command.add_argument(
            "--finalists",
            default=str(DEFAULT_EVALUATION / "finalists.json"),
        )
        command.add_argument(
            "--reveal-key",
            default=str(DEFAULT_RUN_ROOT / "internal" / "reveal_key.json"),
        )
        command.add_argument(
            "--feedback-brief",
            default=str(
                DEFAULT_FEEDBACK_ROOT / "bootstrap_feedback_brief.v1.json"
            ),
        )
        command.add_argument(
            "--author-manifest", default=str(DEFAULT_AUTHOR_MANIFEST)
        )
        command.add_argument(
            "--author-profile", default=str(DEFAULT_AUTHOR_PROFILE)
        )
        command.add_argument(
            "--author-transformation-map",
            default=str(DEFAULT_S02_TRANSFORMATION_MAP),
        )
        command.add_argument(
            "--author-conditioning-variant",
            default="anonymous-profile",
            choices=(
                "none",
                "name-only",
                "anonymous-profile",
                "named-profile",
                "profile-sparse-exemplars",
                "plot-review-nshot",
                "dense-retrieval",
                "raw-rag",
            ),
        )
        command.add_argument(
            "--author-prompt-encoding",
            default="xml",
            choices=("xml", "markdown", "json"),
        )
        command.add_argument(
            "--author-control-density",
            default="light",
            choices=("organic", "light", "medium", "dense", "raw-rag"),
        )
        command.add_argument(
            "--conditioning-material",
            help=(
                "Explicit JSON list for continuation author-conditioning "
                "experiments; every included excerpt is added to anti-copy"
            ),
        )

    command = continuation_sub.add_parser(
        "prepare",
        help="Compile the compact S02 story state and immutable-prefix manifest",
    )
    add_continuation_inputs(command)
    command.add_argument("--output", default=str(DEFAULT_S02_CONTEXT))
    command.set_defaults(func=_command_continuation_prepare)

    command = continuation_sub.add_parser(
        "propose",
        help="Sample diverse base-model plans for a base-to-instruction arm",
    )
    add_continuation_inputs(command)
    command.add_argument("--run-root", default=str(DEFAULT_S02_RUN_ROOT))
    command.add_argument("--ideator-url")
    command.add_argument(
        "--mode",
        choices=(
            BASE31_PLAN_MODE,
            BASE_PROGRAM_MODE,
            LEGACY_BASE_PROGRAM_MODE,
        ),
        default=BASE_PROGRAM_MODE,
    )
    command.add_argument("--count", type=int, default=8, choices=range(1, 9))
    command.add_argument("--timeout", type=float, default=1_800)
    command.set_defaults(func=_command_continuation_propose)

    command = continuation_sub.add_parser(
        "verbalize",
        help="Elicit and select two long-tail Verbalized Sampling distributions",
    )
    add_continuation_inputs(command)
    command.add_argument("--run-root", default=str(DEFAULT_S02_RUN_ROOT))
    command.add_argument("--planner-url", default="http://127.0.0.1:8096")
    command.add_argument("--count", type=int, default=8, choices=range(1, 9))
    command.add_argument("--timeout", type=float, default=2_400)
    command.set_defaults(func=_command_continuation_verbalize)

    command = continuation_sub.add_parser(
        "rank-verbalized",
        help="Blind-score the Verbalized plan pool twice and lock a quality-first v2 set",
    )
    add_continuation_inputs(command)
    command.add_argument("--run-root", default=str(DEFAULT_S02_RUN_ROOT))
    command.add_argument("--judge-url", default="http://127.0.0.1:8096")
    command.add_argument("--count", type=int, default=8, choices=range(1, 9))
    command.add_argument("--timeout", type=float, default=2_400)
    command.set_defaults(func=_command_continuation_rank_verbalized)

    command = continuation_sub.add_parser(
        "adjudicate-verbalized",
        help="Apply an explicit audited policy and lock the Verbalized v3 plan set",
    )
    command.add_argument("--run-root", default=str(DEFAULT_S02_RUN_ROOT))
    command.add_argument(
        "--policy", default=str(DEFAULT_S02_VERBALIZED_ADJUDICATION)
    )
    command.add_argument("--count", type=int, default=8, choices=range(1, 9))
    command.set_defaults(func=_command_continuation_adjudicate_verbalized)

    command = continuation_sub.add_parser(
        "compile-programs",
        help="Compile base or verbalized proposals into validated S02 programs",
    )
    add_continuation_inputs(command)
    command.add_argument("--run-root", default=str(DEFAULT_S02_RUN_ROOT))
    command.add_argument("--compiler-url", default="http://127.0.0.1:8096")
    command.add_argument(
        "--mode",
        choices=(
            BASE_PROGRAM_MODE,
            LEGACY_BASE_PROGRAM_MODE,
        ),
        default=BASE_PROGRAM_MODE,
    )
    command.add_argument("--count", type=int, default=8, choices=range(1, 9))
    command.add_argument("--timeout", type=float, default=2_400)
    command.set_defaults(func=_command_continuation_compile_programs)

    command = continuation_sub.add_parser(
        "run",
        help="Generate one S02 comparison arm with the shared pacing controller",
    )
    add_continuation_inputs(command)
    command.add_argument("mode", choices=GENERATION_MODES)
    command.add_argument("--run-root", default=str(DEFAULT_S02_RUN_ROOT))
    command.add_argument("--run-id", default="s02-compute-v4.1-literary")
    command.add_argument("--writer-url")
    command.add_argument(
        "--writer-role",
        choices=("generator", "editor", "raw_writer", "base_31b_writer"),
        help=(
            "Override the historical mode-to-model mapping for a controlled "
            "writer-checkpoint ablation; recorded in RunConfig and telemetry"
        ),
    )
    command.add_argument(
        "--locked-plan-set",
        help=(
            "Reuse an immutable versioned plan manifest from another run; "
            "its internal hashes and generation mode are revalidated"
        ),
    )
    command.add_argument("--count", type=int, default=8, choices=range(1, 9))
    command.add_argument(
        "--max-new-candidates",
        type=int,
        choices=range(1, 9),
        help=(
            "Stop after committing this many previously unfinished candidates, "
            "or this many new partial checkpoints when --stop-after-sequences "
            "is active, without changing the eight-seed RunConfig."
        ),
    )
    command.add_argument(
        "--stop-after-sequences",
        type=int,
        choices=(1, 2),
        help=(
            "Persist a partial checkpoint and stop after this many macro "
            "sequences; rerun without the flag to resume from completed calls"
        ),
    )
    command.add_argument("--timeout", type=float, default=2_400)
    command.set_defaults(func=_command_continuation_run)

    command = continuation_sub.add_parser(
        "gate",
        help="Run immutable-prefix, S02, length, consent, and anti-copy gates",
    )
    add_continuation_inputs(command)
    command.add_argument("--run-root", default=str(DEFAULT_S02_RUN_ROOT))
    command.add_argument(
        "--output",
        default=str(DEFAULT_S02_RUN_ROOT / "evaluation" / "gates.json"),
    )
    command.set_defaults(func=_command_continuation_gate)

    command = continuation_sub.add_parser(
        "evaluate",
        help="Score and tournament-rank raw complete proof stories",
    )
    add_continuation_inputs(command)
    command.add_argument(
        "--phase",
        choices=("score", "tournament"),
        default="score",
    )
    command.add_argument("--run-root", default=str(DEFAULT_S02_RUN_ROOT))
    command.add_argument(
        "--evaluation-dir",
        default=str(DEFAULT_S02_RUN_ROOT / "evaluation"),
    )
    command.add_argument("--judge-url", default="http://127.0.0.1:8092")
    command.add_argument(
        "--judge-role",
        choices=("fast_judge", "editor"),
        default="editor",
        help=(
            "Use fast_judge for staged absolute screening; tournament requires editor."
        ),
    )
    command.add_argument(
        "--rubric",
        default="s02-v1",
        help="s02-v1 (default), gabaldon-v2 for historical S01-compatible runs, or a JSON path",
    )
    command.add_argument("--timeout", type=float, default=2_400)
    command.set_defaults(func=_command_continuation_evaluate)

    command = continuation_sub.add_parser(
        "package",
        help="Build a blind three-finalist S02 appraisal from accepted mode winners",
    )
    command.add_argument(
        "--evaluation-dir",
        default=str(DEFAULT_S02_RUN_ROOT / "evaluation"),
    )
    command.add_argument(
        "--output",
        default=str(DEFAULT_S02_RUN_ROOT / "appraisal"),
    )
    command.add_argument("--blind-seed", default="s02-compute-comparison-v4.1")
    command.set_defaults(func=_command_continuation_package)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("Interrupted; completed JSONL records remain resumable.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
