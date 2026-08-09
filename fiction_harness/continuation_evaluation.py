"""Evidence-backed evaluation and selection for complete S01+S02 proof stories."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from statistics import mean
from typing import Any, Mapping, Sequence

from .anti_copy import AntiCopyIndex
from .continuation import (
    ApprovedPrefix,
    canonical_generation_mode,
    clean_generated_prose,
    continuation_gates,
)
from .core import canonical_json_text, sha256_text, write_json
from .evaluation import (
    aggregate_pairwise,
    batch_literary_style_diagnostics,
    diversity_report,
    literary_style_diagnostics,
    load_rubric,
    pairwise_prompt,
    parse_pairwise_payload,
    quality_diversity_frontier,
    word_count,
)
from .feedback import HumanFeedbackBrief
from .model_client import LlamaClient
from .ontology import profile_aware_rubric
from .runtime import TraceStore, stable_prompt
from .schemas import Candidate, SceneSpec
from .workflow import (
    _judge_one,
    _judge_prefix,
    _pairwise_payload_with_exact_evidence,
    _pairwise_prefix,
    _resumable_completion,
    load_resolved_profile,
)


PROOF_EVALUATION_VERSION = "s02-proof-evaluation.v2"
# The immutable S01 prefix is identical across candidates and made absolute
# judging dramatically slower without adding much discrimination. Score every
# S02 continuation once; pairwise tournaments still compare Candidate.text,
# i.e. the complete proof story, for the survivors.
SCOPE_NAMES = ("continuation",)


def _require_v4_provenance(candidate: Candidate) -> None:
    if not candidate.scene_profile_id.startswith("fulcrum-s02.v4"):
        return
    required = {
        "author_profile_id": candidate.author_profile_id,
        "author_profile_hash": candidate.author_profile_hash,
        "corpus_manifest_hash": candidate.corpus_manifest_hash,
        "transformation_map_hash": candidate.transformation_map_hash,
        "conditioning_variant": candidate.conditioning_variant,
        "prompt_encoding": candidate.prompt_encoding,
        "control_density": candidate.control_density,
        "story_program_id": candidate.story_program_id,
        "anti_copy_policy_version": candidate.anti_copy_policy_version,
        "anti_copy_index_hash": candidate.anti_copy_index_hash,
        "frontier_adapter": candidate.frontier_adapter,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError(
            f"{candidate.candidate_id} lacks v4 comparison provenance: "
            + ", ".join(missing)
        )
    if candidate.parent_trace.get("story_program") and not candidate.parent_trace.get(
        "story_program_hash"
    ):
        raise ValueError(
            f"{candidate.candidate_id} has an unlocked story program"
        )


def _scope_candidate(candidate: Candidate, scope: str) -> Candidate:
    if scope == "continuation":
        return replace(
            candidate,
            candidate_id=f"{candidate.candidate_id}:continuation",
            text=candidate.continuation_text,
        )
    if scope == "merged_story":
        return replace(
            candidate,
            candidate_id=f"{candidate.candidate_id}:merged",
        )
    raise ValueError(f"unknown proof-story scope: {scope}")


def _scope_prefix(
    base: str,
    *,
    scope: str,
    feedback: HumanFeedbackBrief,
) -> str:
    obligations = {
        "scope": scope,
        "additional_diagnostics": (
            "Beginning-to-ending causal closure",
            "Romantic hope-for-now satisfaction",
            "Attraction changes trust and choice",
            "Reader-requested strengths are preserved",
            "Reader-identified defects are avoided",
            "The doorway rule converts restraint into intimacy",
        ),
        "reader_priorities": {
            "preserve": list(feedback.strengths.get(feedback.winner_label, ())),
            "avoid": list(feedback.defects.get(feedback.winner_label, ())),
            "desired_next": list(
                feedback.desired_next.get(feedback.winner_label, ())
            ),
        },
        "scope_rule": (
            "Score only S02 as a continuation with an inherited opening."
            if scope == "continuation"
            else (
                "Score the complete two-act proof story, including causal closure "
                "from S01 into S02 and the earned local HFN."
            )
        ),
    }
    return (
        base
        + "\n<PROOF_STORY_OVERLAY>\n"
        + canonical_json_text(obligations)
        + "\n"
    )


def _compact_literary_preflight(diagnostics: Mapping[str, Any]) -> dict[str, Any]:
    """Keep judge-facing style evidence small while preserving full traces."""

    cadence = dict(diagnostics.get("cadence_families", {}))
    families = {
        str(name): {
            "count": int(values.get("count", 0)),
            "per_1000_words": float(values.get("per_1000_words", 0)),
            "examples": [
                str(item.get("evidence", item.get("match", "")))
                for item in list(values.get("evidence", ()))[:2]
            ],
        }
        for name, raw_values in dict(cadence.get("families", {})).items()
        if isinstance(raw_values, Mapping)
        and (values := dict(raw_values)).get("count", 0)
    }
    gloss = dict(diagnostics.get("explanatory_gloss", {}))
    voice = dict(diagnostics.get("dialogue_voice", {}))
    return {
        "heuristic_not_automatic_penalty": True,
        "cadence": {
            "total_hits": int(cadence.get("total_family_hits", 0)),
            "hits_per_1000_words": float(
                cadence.get("hits_per_1000_words", 0)
            ),
            "families": families,
        },
        "immediate_explanatory_gloss": {
            "possible_count": int(
                gloss.get("possible_explanatory_glosses", 0)
            ),
            "per_100_dialogue_passages": float(
                gloss.get("glosses_per_100_dialogue_passages", 0)
            ),
            "examples": list(gloss.get("evidence", ()))[:4],
        },
        "dialogue_voice": {
            "comparable_speaker_count": int(
                voice.get("comparable_speaker_count", 0)
            ),
            "possible_voice_indistinctness": voice.get(
                "possible_voice_indistinctness"
            ),
            "mean_shared_over_smaller_vocabulary": voice.get(
                "mean_shared_over_smaller_vocabulary"
            ),
            "mean_unigram_frequency_cosine": voice.get(
                "mean_unigram_frequency_cosine"
            ),
        },
    }


def judge_proof_candidates(
    *,
    candidates: Sequence[Candidate],
    scene: SceneSpec,
    approved_prefix: ApprovedPrefix,
    feedback: HumanFeedbackBrief,
    anti_copy_index: AntiCopyIndex,
    compiled_dir: str | Path,
    evaluation_dir: str | Path,
    client: LlamaClient,
    rubric_path: str | Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Judge every S02 once; reserve merged-story comparison for survivors."""

    output = Path(evaluation_dir)
    output.mkdir(parents=True, exist_ok=True)
    store = TraceStore(output)
    resolved = load_resolved_profile(compiled_dir)
    active_rubric = profile_aware_rubric(
        load_rubric(rubric_path), resolved
    )
    base_prefix = _judge_prefix(Path(compiled_dir), scene, active_rubric)
    gate_reports: list[dict[str, Any]] = []
    scores: list[dict[str, Any]] = []
    for candidate_index, candidate in enumerate(candidates):
        _require_v4_provenance(candidate)
        gates = continuation_gates(
            candidate,
            scene=scene,
            approved_prefix=approved_prefix,
            anti_copy_index=anti_copy_index,
        )
        gate_reports.append(gates)
        write_json(
            output / "deterministic" / f"{candidate.candidate_id}.json",
            gates,
        )
        gate_bools = {
            name: bool(detail["passed"])
            for name, detail in gates["gates"].items()
        }
        for scope_index, scope in enumerate(SCOPE_NAMES):
            view = _scope_candidate(candidate, scope)
            literary = literary_style_diagnostics(view.text)
            literary_prefix = (
                _scope_prefix(base_prefix, scope=scope, feedback=feedback)
                + "\n<LITERARY_PREFLIGHT>\n"
                + canonical_json_text(_compact_literary_preflight(literary))
                + "\n</LITERARY_PREFLIGHT>\n"
                + "The preflight is heuristic evidence, not an automatic "
                + "penalty. Inspect its quoted passages in the candidate. On "
                + "prose_and_voice, explicitly account for cadence repetition, "
                + "immediate narration that merely explains successful dialogue, "
                + "and whether named speakers have distinguishable language.\n"
            )
            judged = _judge_one(
                client=client,
                store=store,
                candidate=view,
                prefix=literary_prefix,
                pass_number=1,
                seed=1_240_000 + candidate_index * 211 + scope_index * 37,
                rubric=active_rubric,
            )
            judged.update(
                {
                    "candidate_id": candidate.candidate_id,
                    "scope": scope,
                    "scope_candidate_id": view.candidate_id,
                    "hard_gates": gate_bools,
                    "gate_details": gates["gates"],
                    "eligible": bool(gates["eligible"]),
                    "ontology_version": candidate.ontology_version,
                    "story_profile_id": candidate.story_profile_id,
                    "scene_profile_id": candidate.scene_profile_id,
                    "resolved_profile_hash": candidate.resolved_profile_hash,
                    "author_profile_id": candidate.author_profile_id,
                    "author_profile_hash": candidate.author_profile_hash,
                    "corpus_manifest_hash": candidate.corpus_manifest_hash,
                    "transformation_map_hash": candidate.transformation_map_hash,
                    "conditioning_variant": candidate.conditioning_variant,
                    "prompt_encoding": candidate.prompt_encoding,
                    "control_density": candidate.control_density,
                    "story_program_id": candidate.story_program_id,
                    "story_program_hash": str(
                        candidate.parent_trace.get("story_program_hash", "")
                    ),
                    "anti_copy_policy_version": candidate.anti_copy_policy_version,
                    "anti_copy_index_hash": candidate.anti_copy_index_hash,
                    "frontier_adapter": candidate.frontier_adapter,
                    "approved_prefix_id": candidate.approved_prefix_id,
                    "approved_prefix_hash": candidate.approved_prefix_hash,
                    "feedback_brief_hash": candidate.feedback_brief_hash,
                    "generation_mode": candidate.generation_mode,
                    "literary_diagnostics": literary,
                }
            )
            scores.append(judged)
            write_json(
                output
                / "scorecards"
                / f"{candidate.candidate_id}.{scope}.json",
                judged,
            )
    TraceStore._append(
        output / "evaluation_events.jsonl",
        {
            "record_type": "ProofEvaluationComplete",
            "version": PROOF_EVALUATION_VERSION,
            "candidate_count": len(candidates),
            "scorecard_count": len(scores),
            "feedback_brief_hash": feedback.feedback_brief_hash,
        },
    )
    with (output / "scorecards.jsonl").open(
        "w", encoding="utf-8", newline="\n"
    ) as handle:
        for score in scores:
            handle.write(
                json.dumps(
                    score,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )
    return gate_reports, scores


def aggregate_proof_scores(
    candidates: Sequence[Candidate],
    scores: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    editor_repairable_gates = {
        "complete_ending",
        "doorway_rule",
        "local_hfn",
    }
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        attached = [
            score
            for score in scores
            if score.get("candidate_id") == candidate.candidate_id
        ]
        by_scope = {
            str(score.get("scope")): float(score.get("total_score", 0))
            for score in attached
        }
        failed_gates = sorted(
            {
                str(name)
                for score in attached
                for name, passed in dict(score.get("hard_gates", {})).items()
                if not bool(passed)
            }
        )
        rows.append(
            {
                "candidate_id": candidate.candidate_id,
                "generation_mode": canonical_generation_mode(
                    candidate.generation_mode
                ),
                "artifact_generation_mode": candidate.generation_mode,
                "eligible": bool(attached)
                and all(bool(score.get("eligible")) for score in attached),
                "failed_gates": failed_gates,
                "editor_repairable": bool(attached)
                and bool(failed_gates)
                and set(failed_gates).issubset(editor_repairable_gates),
                "scope_scores": by_scope,
                "combined_score": round(
                    mean(by_scope.values()) if by_scope else 0.0, 4
                ),
                "defects": sorted(
                    {
                        str(defect)
                        for score in attached
                        for defect in score.get("defects", ())
                    }
                ),
            }
        )
    rows.sort(
        key=lambda row: (
            not (row["eligible"] or row["editor_repairable"]),
            -float(row["combined_score"]),
            str(row["candidate_id"]),
        )
    )
    by_mode: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_mode.setdefault(str(row["generation_mode"]), []).append(row)
    candidates_by_mode: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        candidates_by_mode.setdefault(
            canonical_generation_mode(candidate.generation_mode), []
        ).append(candidate)
    generation_diagnostics: dict[str, dict[str, Any]] = {}
    for mode, mode_candidates in sorted(candidates_by_mode.items()):
        word_counts = [
            word_count(candidate.continuation_text) for candidate in mode_candidates
        ]
        generation_diagnostics[mode] = {
            "candidate_count": len(mode_candidates),
            "artifact_mode_labels": sorted(
                {candidate.generation_mode for candidate in mode_candidates}
            ),
            "writer_models": sorted(
                {
                    str(candidate.telemetry.get("model", ""))
                    for candidate in mode_candidates
                    if str(candidate.telemetry.get("model", ""))
                }
            ),
            "word_counts": word_counts,
            "length_compliant": sum(
                2_800 <= count <= 3_600 for count in word_counts
            ),
            "continuation_repairs": sum(
                "continue-" in item
                for candidate in mode_candidates
                for item in candidate.lineage
            ),
            "local_compressions": sum(
                "compress" in item
                for candidate in mode_candidates
                for item in candidate.lineage
            ),
            "diversity": diversity_report(mode_candidates),
            "literary_style": batch_literary_style_diagnostics(
                mode_candidates
            ),
        }
    return {
        "record_type": "ProofScoreAggregate",
        "version": PROOF_EVALUATION_VERSION,
        "rows": rows,
        "by_mode": by_mode,
        "generation_diagnostics": generation_diagnostics,
        "quality_diversity_frontier": quality_diversity_frontier(
            candidates, scores
        ),
    }


def _pairwise_one(
    *,
    client: LlamaClient,
    store: TraceStore,
    left: Candidate,
    right: Candidate,
    call_id: str,
    seed: int,
    rubric: Mapping[str, Any],
    reversed_order: bool,
) -> dict[str, Any]:
    prompt = stable_prompt(
        _pairwise_prefix(rubric),
        pairwise_prompt(left.text, right.text, rubric),
    )
    result = _resumable_completion(
        client=client,
        store=store,
        call_id=call_id,
        prompt=prompt,
        seed=seed,
        max_tokens=1_536,
        temperature=0.2,
        top_p=0.9,
    )
    response = result["content"]
    payload: dict[str, Any] | None = None
    audits: list[dict[str, Any]] = []
    last_error: ValueError | None = None
    for repair_index in range(3):
        try:
            payload, audits = _pairwise_payload_with_exact_evidence(
                response,
                left.text,
                right.text,
                allow_lexical_fallback=repair_index >= 1,
            )
            break
        except ValueError as exc:
            last_error = exc
            if repair_index == 2:
                raise
            suffix = "-repair" if repair_index == 0 else "-repair-2"
            repair_instruction = (
                "\nYour evidence was invalid. Return the complete JSON again, "
                "copying 5–12 exact consecutive words from each candidate."
                if repair_index == 0
                else (
                    "\nThe previous JSON/evidence response was invalid: "
                    + str(exc)
                    + ". Return one complete syntactically valid JSON object. "
                    + "Every evidence item must copy 5–12 exact consecutive "
                    + "words from the corresponding candidate; never quote "
                    + "rubric or prompt instructions."
                )
            )
            repair = _resumable_completion(
                client=client,
                store=store,
                call_id=call_id + suffix,
                prompt=prompt + repair_instruction,
                seed=seed ^ (0x4A11 + repair_index * 0x101),
                max_tokens=1_536,
                temperature=0.1,
                top_p=0.9,
            )
            response = repair["content"]
    if payload is None:
        raise ValueError("pairwise judgment remained invalid") from last_error
    judgment = parse_pairwise_payload(
        payload,
        left.candidate_id,
        right.candidate_id,
        client.model,
        order_reversed=reversed_order,
    )
    judgment["evidence_repairs"] = audits
    return judgment


def tournament_top_two(
    *,
    candidates: Sequence[Candidate],
    score_aggregate: Mapping[str, Any],
    compiled_dir: str | Path,
    evaluation_dir: str | Path,
    client: LlamaClient,
    rubric_path: str | Path,
) -> dict[str, Any]:
    """Run a four-survivor reversed-order bracket per generation mode.

    Three survivors come from screened quality and one from diversity. The
    semifinals compare S02 only; the final compares the complete proof story.
    The historical function name remains API-stable.
    """

    resolved = load_resolved_profile(compiled_dir)
    rubric = profile_aware_rubric(load_rubric(rubric_path), resolved)
    by_id = {item.candidate_id: item for item in candidates}
    store = TraceStore(Path(evaluation_dir) / "pairwise")
    results: dict[str, Any] = {}

    def resolve_match(
        judgments: Sequence[Mapping[str, Any]],
        left_id: str,
        right_id: str,
        screen_scores: Mapping[str, float],
    ) -> tuple[str, dict[str, Any], str]:
        aggregate = aggregate_pairwise(judgments)
        if aggregate["ranking"] and not aggregate["order_disagreements"]:
            return str(aggregate["ranking"][0]), aggregate, "pairwise"
        winner = max(
            (left_id, right_id),
            key=lambda item: (float(screen_scores.get(item, 0)), item),
        )
        return winner, aggregate, "screen_score_after_order_disagreement"

    for mode, rows in dict(score_aggregate["by_mode"]).items():
        eligible = [
            row
            for row in rows
            if row["eligible"] or row.get("editor_repairable")
        ]
        pool = eligible if len(eligible) >= 2 else list(rows)
        if len(pool) < 2:
            raise ValueError(f"{mode} has fewer than two candidates")
        screen_scores = {
            str(row["candidate_id"]): float(row["combined_score"])
            for row in pool
        }
        per_candidate_diversity = (
            dict(score_aggregate.get("generation_diagnostics", {}))
            .get(mode, {})
            .get("diversity", {})
            .get("per_candidate", {})
        )
        selected = list(pool[: min(3, len(pool))])
        remaining = [row for row in pool if row not in selected]
        if remaining:
            selected.append(
                max(
                    remaining,
                    key=lambda row: (
                        float(
                            dict(
                                per_candidate_diversity.get(
                                    str(row["candidate_id"]), {}
                                )
                            ).get("diversity_contribution", 0)
                        ),
                        float(row["combined_score"]),
                        str(row["candidate_id"]),
                    ),
                )
            )
        selected = selected[:4]

        # Small smoke runs retain the old two-survivor behavior.
        if len(selected) < 4:
            selected = selected[:2]
            first = by_id[str(selected[0]["candidate_id"])]
            second = by_id[str(selected[1]["candidate_id"])]
            judgments = [
                _pairwise_one(
                    client=client,
                    store=store,
                    left=first,
                    right=second,
                    call_id=f"{mode}-top-two-forward",
                    seed=1_360_000 + len(results) * 101,
                    rubric=rubric,
                    reversed_order=False,
                ),
                _pairwise_one(
                    client=client,
                    store=store,
                    left=second,
                    right=first,
                    call_id=f"{mode}-top-two-reverse",
                    seed=1_360_037 + len(results) * 101,
                    rubric=rubric,
                    reversed_order=True,
                ),
            ]
            winner, aggregate, tie_break = resolve_match(
                judgments, first.candidate_id, second.candidate_id, screen_scores
            )
            semifinals: list[dict[str, Any]] = []
            finalists = [first, second]
        else:
            seeded = [by_id[str(row["candidate_id"])] for row in selected]
            semifinal_pairs = ((seeded[0], seeded[3]), (seeded[1], seeded[2]))
            finalists = []
            semifinals = []
            for match_index, (left_raw, right_raw) in enumerate(semifinal_pairs):
                left = replace(left_raw, text=left_raw.continuation_text)
                right = replace(right_raw, text=right_raw.continuation_text)
                match_judgments = [
                    _pairwise_one(
                        client=client,
                        store=store,
                        left=left,
                        right=right,
                        call_id=f"{mode}-semifinal-{match_index + 1}-forward",
                        seed=1_360_000 + len(results) * 701 + match_index * 101,
                        rubric=rubric,
                        reversed_order=False,
                    ),
                    _pairwise_one(
                        client=client,
                        store=store,
                        left=right,
                        right=left,
                        call_id=f"{mode}-semifinal-{match_index + 1}-reverse",
                        seed=1_360_037 + len(results) * 701 + match_index * 101,
                        rubric=rubric,
                        reversed_order=True,
                    ),
                ]
                match_winner, match_aggregate, match_tie = resolve_match(
                    match_judgments,
                    left_raw.candidate_id,
                    right_raw.candidate_id,
                    screen_scores,
                )
                finalists.append(by_id[match_winner])
                semifinals.append(
                    {
                        "selected": [left_raw.candidate_id, right_raw.candidate_id],
                        "text_scope": "continuation",
                        "judgments": match_judgments,
                        "aggregate": match_aggregate,
                        "winner": match_winner,
                        "tie_break": match_tie,
                    }
                )
            first, second = finalists
            judgments = [
                _pairwise_one(
                    client=client,
                    store=store,
                    left=first,
                    right=second,
                    call_id=f"{mode}-final-forward",
                    seed=1_361_000 + len(results) * 701,
                    rubric=rubric,
                    reversed_order=False,
                ),
                _pairwise_one(
                    client=client,
                    store=store,
                    left=second,
                    right=first,
                    call_id=f"{mode}-final-reverse",
                    seed=1_361_037 + len(results) * 701,
                    rubric=rubric,
                    reversed_order=True,
                ),
            ]
            winner, aggregate, tie_break = resolve_match(
                judgments, first.candidate_id, second.candidate_id, screen_scores
            )

        results[str(mode)] = {
            "selected": [str(row["candidate_id"]) for row in selected],
            "selection_rule": "top_three_screen_scores_plus_diversity_wildcard",
            "semifinals": semifinals,
            "finalists": [item.candidate_id for item in finalists],
            "final_text_scope": "complete_proof_story",
            "judgments": judgments,
            "aggregate": aggregate,
            "winner": winner,
            "tie_break": tie_break,
        }
        write_json(
            Path(evaluation_dir) / "pairwise" / f"{mode}.json",
            results[str(mode)],
        )
    payload = {
        "record_type": "ProofPairwiseTournament",
        "version": PROOF_EVALUATION_VERSION,
        "modes": results,
        "hash": sha256_text(canonical_json_text(results)),
    }
    write_json(Path(evaluation_dir) / "tournament.json", payload)
    return payload


def _editor_defects(
    candidate_id: str,
    scores: Sequence[Mapping[str, Any]],
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    attached = [
        score for score in scores if score.get("candidate_id") == candidate_id
    ]
    axis_values: dict[str, list[tuple[float, str, str]]] = {}
    named_defects: set[str] = set()
    for score in attached:
        named_defects.update(str(item) for item in score.get("defects", ()))
        evidence = dict(score.get("passage_evidence", {}))
        for axis, detail in dict(score.get("rubric_breakdown", {})).items():
            quotes = evidence.get(axis, ())
            quote = str(quotes[0]) if quotes else ""
            axis_values.setdefault(str(axis), []).append(
                (
                    float(detail.get("raw_0_100", 0)),
                    quote,
                    str(score.get("scope", "")),
                )
            )
    defects: list[dict[str, Any]] = []
    for axis, values in sorted(
        axis_values.items(),
        key=lambda item: mean(value[0] for value in item[1]),
    ):
        weakest = min(values, key=lambda value: value[0])
        defects.append(
            {
                "axis": axis,
                "mean_raw_score": round(mean(value[0] for value in values), 2),
                "scope": weakest[2],
                "passage": weakest[1],
                "named_defects": sorted(named_defects),
            }
        )
        if len(defects) == limit:
            break
    return defects


def _literary_editor_defects(
    candidate_id: str,
    scores: Sequence[Mapping[str, Any]],
    *,
    limit: int = 2,
) -> list[dict[str, Any]]:
    """Promote conspicuous preflight patterns into passage-specific edit leads."""

    continuation_score = next(
        (
            item
            for item in scores
            if item.get("candidate_id") == candidate_id
            and item.get("scope") == "continuation"
        ),
        None,
    )
    if continuation_score is None or limit <= 0:
        return []
    literary = dict(continuation_score.get("literary_diagnostics", {}))
    cadence = dict(literary.get("cadence_families", {}))
    gloss = dict(literary.get("explanatory_gloss", {}))
    leads: list[dict[str, Any]] = []

    family_rows = sorted(
        (
            (name, dict(values))
            for name, values in dict(cadence.get("families", {})).items()
        ),
        key=lambda item: int(item[1].get("count", 0)),
        reverse=True,
    )
    if (
        int(cadence.get("total_family_hits", 0)) >= 12
        and float(cadence.get("hits_per_1000_words", 0)) >= 4.0
        and family_rows
        and int(family_rows[0][1].get("count", 0)) >= 4
    ):
        family, values = family_rows[0]
        evidence = list(values.get("evidence", ()))
        passage = str(evidence[0].get("match", "")) if evidence else ""
        leads.append(
            {
                "axis": "prose_and_voice",
                "scope": "deterministic_literary_preflight",
                "passage": passage,
                "named_defects": [
                    f"The {family} cadence repeats {values.get('count', 0)} "
                    "times; vary or delete the recurrent rhetorical turn while "
                    "preserving any occurrence that earns its emphasis."
                ],
            }
        )

    gloss_count = int(gloss.get("possible_explanatory_glosses", 0))
    gloss_evidence = list(gloss.get("evidence", ()))
    if gloss_count >= 4 and gloss_evidence and len(leads) < limit:
        item = gloss_evidence[0]
        leads.append(
            {
                "axis": "prose_and_voice",
                "scope": "deterministic_literary_preflight",
                "passage": str(item.get("narration", "")),
                "named_defects": [
                    f"Possible immediate explanatory gloss ({gloss_count} "
                    "instances): trust strong dialogue or action when the "
                    "following narration only restates it."
                ],
            }
        )
    return leads[:limit]


def _editorial_overrides(
    evaluation_dir: str | Path,
    candidate: Candidate,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    """Load optional human-authored, exact-passage editor defects.

    The override file is deliberately downstream of selection: it may sharpen
    the editor's attention on a finalist, but it cannot affect which raw
    candidate wins its scaffold.  Exact passage validation keeps the record
    auditable and prevents stale notes from being applied to another draft.
    """

    if limit <= 0:
        return []
    path = Path(evaluation_dir) / "editorial_overrides.json"
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    by_candidate = payload.get("candidate_defects", {})
    if not isinstance(by_candidate, Mapping):
        raise ValueError("editorial_overrides candidate_defects must be an object")
    raw_items = by_candidate.get(candidate.candidate_id, ())
    if not isinstance(raw_items, list):
        raise ValueError(
            f"editorial overrides for {candidate.candidate_id} must be a list"
        )
    defects: list[dict[str, Any]] = []
    for raw_item in raw_items[:limit]:
        if not isinstance(raw_item, Mapping):
            raise ValueError("each editorial override must be an object")
        passage = str(raw_item.get("passage", "")).strip()
        if not passage or passage not in candidate.continuation_text:
            raise ValueError(
                "editorial override passage must occur exactly in "
                f"{candidate.candidate_id}: {passage!r}"
            )
        named = raw_item.get("named_defects", ())
        if isinstance(named, str):
            named = [named]
        if not isinstance(named, list) or not named:
            raise ValueError("editorial override requires named_defects")
        defects.append(
            {
                "axis": str(raw_item.get("axis", "prose_and_voice")),
                "scope": "human_close_read",
                "passage": passage,
                "named_defects": [str(item) for item in named],
            }
        )
    return defects


def edit_mode_winners(
    *,
    candidates: Sequence[Candidate],
    scores: Sequence[Mapping[str, Any]],
    tournament: Mapping[str, Any],
    compact_context: str,
    approved_prefix: ApprovedPrefix,
    feedback: HumanFeedbackBrief,
    anti_copy_index: AntiCopyIndex,
    scene: SceneSpec,
    evaluation_dir: str | Path,
    client: LlamaClient,
) -> tuple[Candidate, ...]:
    """Legacy frontier prose editor, disabled for scaffold research."""

    raise RuntimeError(
        "frontier manuscript rewriting is disabled: emit structured defects "
        "and regenerate with the declared writer scaffold"
    )

    by_id = {candidate.candidate_id: candidate for candidate in candidates}
    store = TraceStore(Path(evaluation_dir) / "editor")
    revisions: list[Candidate] = []
    for mode_index, (mode, result) in enumerate(
        dict(tournament["modes"]).items()
    ):
        raw_id = str(result["winner"])
        raw = by_id[raw_id]
        raw_gates = continuation_gates(
            raw,
            scene=scene,
            approved_prefix=approved_prefix,
            anti_copy_index=anti_copy_index,
        )
        gate_repairs = {
            "complete_ending": (
                "The continuation is token-cut or syntactically incomplete. "
                "Give it a complete final sentence and earned ending."
            ),
            "doorway_rule": (
                "Dramatize an actual mutually chosen kiss, then a stop after "
                "contact while desire remains; a discussion of kissing alone "
                "does not satisfy the doorway rule."
            ),
            "local_hfn": (
                "Near the ending, make Mara explicitly and freely choose to "
                "stay, return, or continue at Fulcrum while leaving its larger "
                "psychotechnology mystery unresolved."
            ),
        }
        defects: list[dict[str, Any]] = [
            {
                "axis": gate_name,
                "scope": "hard_gate",
                "passage": "",
                "named_defects": [repair],
            }
            for gate_name, repair in gate_repairs.items()
            if not raw_gates["gates"][gate_name]["passed"]
        ]
        defects.extend(
            _editorial_overrides(
                evaluation_dir,
                raw,
                limit=max(0, 5 - len(defects)),
            )
        )
        defects.extend(
            _literary_editor_defects(
                raw_id,
                scores,
                limit=max(0, 5 - len(defects)),
            )
        )
        defects.extend(
            _editor_defects(
                raw_id,
                scores,
                limit=max(0, 5 - len(defects)),
            )
        )
        defects = defects[:5]
        prompt = (
            "You are a surgical final fiction editor. The approved S01 first act "
            "is immutable and is not supplied for rewriting. Revise only the S02 "
            "continuation below. Preserve its plot, point of view, voice, strongest "
            "lines, and successful language. Repair only the five or fewer "
            "passage-specific defects. Return the complete revised S02 prose and "
            "nothing else; 2,800–3,600 words. Do not add graphic anatomy or "
            "consummation. The mutually chosen kiss must stop while still desired, "
            "the local HFN must remain earned, and Fulcrum's larger mystery remains "
            "open.\n\n<COMPACT_CONTEXT>\n"
            + compact_context
            + "\n</COMPACT_CONTEXT>\n<HUMAN_PRIORITIES>\n"
            + canonical_json_text(
                {
                    "preserve": list(
                        feedback.strengths.get(feedback.winner_label, ())
                    ),
                    "avoid": list(
                        feedback.defects.get(feedback.winner_label, ())
                    ),
                    "desired_next": list(
                        feedback.desired_next.get(feedback.winner_label, ())
                    ),
                }
            )
            + "\n</HUMAN_PRIORITIES>\n<TARGETED_DEFECTS>\n"
            + canonical_json_text(defects)
            + "\n</TARGETED_DEFECTS>\n<S02_CONTINUATION>\n"
            + raw.continuation_text
            + "\n</S02_CONTINUATION>"
        )
        call_id = f"edit-{mode}-{raw_id}"
        completion = _resumable_completion(
            client=client,
            store=store,
            call_id=call_id,
            prompt=prompt,
            seed=1_480_000 + mode_index * 313,
            max_tokens=7_000,
            temperature=0.3,
            top_p=0.9,
        )
        continuation = clean_generated_prose(
            str(completion["content"])
        )
        revision = replace(
            raw,
            candidate_id=f"{raw_id}-polished",
            text=approved_prefix.text.rstrip() + "\n\n" + continuation,
            continuation_text=continuation,
            parent_trace={
                **dict(raw.parent_trace),
                "raw_winner": raw_id,
                "targeted_defects": defects,
            },
            telemetry={
                **dict(raw.telemetry),
                "editor_model": client.model,
                "editor_usage": completion.get("usage", {}),
            },
            lineage=raw.lineage + (f"editor:{call_id}",),
            prompt_hash=sha256_text(prompt),
        )
        gates = continuation_gates(
            revision,
            scene=scene,
            approved_prefix=approved_prefix,
            anti_copy_index=anti_copy_index,
        )
        store.append_candidate(
            {
                **revision.to_dict(),
                "status": "completed",
                "editor_gate_eligible": gates["eligible"],
            }
        )
        write_json(
            Path(evaluation_dir)
            / "editor"
            / f"{revision.candidate_id}.gates.json",
            gates,
        )
        revisions.append(revision)
    return tuple(revisions)


def accept_editor_revisions(
    *,
    raw_candidates: Sequence[Candidate],
    revisions: Sequence[Candidate],
    raw_scores: Sequence[Mapping[str, Any]],
    revision_scores: Sequence[Mapping[str, Any]],
    output_path: str | Path,
) -> tuple[Candidate, ...]:
    """Accept edits only if gates, total quality, and human-priority axes hold."""

    raw_by_id = {candidate.candidate_id: candidate for candidate in raw_candidates}
    accepted: list[Candidate] = []
    decisions: list[dict[str, Any]] = []
    human_axes = (
        "narrative_force",
        "character_truth",
        "heat_with_agency",
        "prose_and_voice",
    )

    def scope_scores(
        records: Sequence[Mapping[str, Any]], candidate_id: str
    ) -> list[Mapping[str, Any]]:
        return [
            record
            for record in records
            if record.get("candidate_id") == candidate_id
        ]

    for revision in revisions:
        raw_id = str(revision.parent_trace["raw_winner"])
        raw = raw_by_id[raw_id]
        raw_attached = scope_scores(raw_scores, raw_id)
        revision_attached = scope_scores(
            revision_scores, revision.candidate_id
        )
        raw_total = mean(
            float(item.get("total_score", 0)) for item in raw_attached
        )
        revision_total = mean(
            float(item.get("total_score", 0)) for item in revision_attached
        )
        axis_checks: dict[str, bool] = {}
        for axis in human_axes:
            raw_axis = mean(
                float(item.get("rubric_scores", {}).get(axis, 0))
                for item in raw_attached
            )
            revision_axis = mean(
                float(item.get("rubric_scores", {}).get(axis, 0))
                for item in revision_attached
            )
            axis_checks[axis] = revision_axis >= raw_axis
        gates_pass = bool(revision_attached) and all(
            bool(item.get("eligible")) for item in revision_attached
        )
        accepted_revision = (
            gates_pass
            and revision_total >= raw_total
            and all(axis_checks.values())
        )
        selected = revision if accepted_revision else raw
        accepted.append(selected)
        decisions.append(
            {
                "raw_id": raw_id,
                "revision_id": revision.candidate_id,
                "selected_id": selected.candidate_id,
                "accepted": accepted_revision,
                "gates_pass": gates_pass,
                "raw_total": round(raw_total, 4),
                "revision_total": round(revision_total, 4),
                "human_axis_checks": axis_checks,
            }
        )
    write_json(
        output_path,
        {
            "record_type": "ProofEditorDecisions",
            "version": PROOF_EVALUATION_VERSION,
            "decisions": decisions,
        },
    )
    return tuple(accepted)
