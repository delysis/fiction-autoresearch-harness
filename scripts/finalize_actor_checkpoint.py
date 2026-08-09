#!/usr/bin/env python3
"""Finalize the gate-valid Actor editor checkpoint after an interrupted run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fiction_harness.core import sha256_text, write_json
from fiction_harness.evaluation import (
    evaluate_candidate,
    load_rubric,
    merge_scorecards,
)
from fiction_harness.model_client import LlamaClient
from fiction_harness.ontology import profile_aware_rubric
from fiction_harness.runtime import TraceStore
from fiction_harness.runtime import MODEL_PROFILES
from fiction_harness.schemas import Candidate
from fiction_harness.authorship import model_artifact_authorship
from fiction_harness.workflow import (
    PIPELINES,
    _candidate_mean_score,
    _editor_defects,
    _judge_one,
    _judge_prefix,
    build_internal_report,
    load_candidates,
    load_compiled,
    load_resolved_profile,
    load_source_texts,
)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def completed_call(records: list[dict[str, Any]], call_id: str) -> dict[str, Any]:
    matches = [
        record
        for record in records
        if record.get("call_id") == call_id
        and record.get("status") == "completed"
    ]
    if not matches:
        raise RuntimeError(f"No completed editor call found: {call_id}")
    record = matches[-1]
    if not record.get("prompt_hash"):
        raise RuntimeError(f"Completed editor call has no prompt hash: {call_id}")
    return record


def candidate_from_call(
    raw: Candidate,
    record: dict[str, Any],
    revision_id: str,
) -> Candidate:
    result = dict(record["result"])
    call_id = str(record["call_id"])
    revision_text = str(result["content"]).strip()
    return Candidate(
        candidate_id=revision_id,
        run_id=raw.run_id,
        pipeline=raw.pipeline,
        scene_id=raw.scene_id,
        seed=raw.seed,
        text=revision_text,
        parent_trace={
            "raw_winner": raw.candidate_id,
            "checkpoint_call_id": call_id,
            "checkpoint_prompt_hash": record["prompt_hash"],
        },
        evidence_ids=raw.evidence_ids,
        telemetry={
            key: result.get(key)
            for key in ("model", "usage", "timings", "cache", "elapsed_seconds")
            if result.get(key) is not None
        },
        lineage=raw.lineage + (f"editor:{call_id}",),
        prompt_hash=str(record["prompt_hash"]),
        ontology_version=raw.ontology_version,
        story_profile_id=raw.story_profile_id,
        scene_profile_id=raw.scene_profile_id,
        resolved_profile_hash=raw.resolved_profile_hash,
        artifact_authorship=model_artifact_authorship(
            artifact_id=revision_id,
            text=revision_text,
            model_id=str(result.get("model", "editor-checkpoint")),
            call_id=call_id,
            prompt_hash=str(record["prompt_hash"]),
            seed=raw.seed,
            call_record={
                "call_id": call_id,
                "prompt_hash": record["prompt_hash"],
                "result_metadata": {
                    key: value
                    for key, value in result.items()
                    if key not in {"content", "raw"}
                },
                "content_hash": sha256_text(revision_text),
            },
            created_at=str(record.get("finished_at", record.get("created_at", "unknown"))),
            parents=(
                {
                    "artifact_id": raw.candidate_id,
                    "text_sha256": sha256_text(raw.text),
                },
            ),
            creation_kind="model_edit",
        ),
    )


def revision_call_id(raw_id: str, revision_id: str) -> str:
    if revision_id == f"{raw_id}-polished":
        return f"edit-{raw_id}"
    prefix = f"{raw_id}-polished-r"
    if revision_id.startswith(prefix):
        return f"edit-{raw_id}-gate-repair-{revision_id.removeprefix(prefix)}"
    raise ValueError(f"Cannot map revision ID to an editor call: {revision_id}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--compiled", required=True)
    parser.add_argument("--evaluation-dir", required=True)
    parser.add_argument("--judge-url", default="http://127.0.0.1:8092")
    args = parser.parse_args()

    run_root = Path(args.run_root)
    compiled = Path(args.compiled)
    evaluation = Path(args.evaluation_dir)
    candidates = load_candidates(run_root)
    by_id = {candidate.candidate_id: candidate for candidate in candidates}
    scores = read_jsonl(evaluation / "scorecards.jsonl")
    tournament = read_json(evaluation / "tournament.json")
    calls = read_jsonl(evaluation / "editor" / "calls.jsonl")
    scene, _, _, _ = load_compiled(compiled)
    sources = load_source_texts(compiled)
    profile = load_resolved_profile(compiled)
    rubric = profile_aware_rubric(load_rubric(), profile)

    pipeline = "actor_novelist"
    raw_id = str(tournament[pipeline]["winner"])
    raw = by_id[raw_id]
    checkpoint_call_id = f"edit-{raw_id}-gate-repair-2"
    checkpoint_record = completed_call(calls, checkpoint_call_id)
    revision = candidate_from_call(
        raw,
        checkpoint_record,
        f"{raw_id}-polished-r2",
    )
    deterministic = evaluate_candidate(
        revision,
        scene,
        sources,
        rubric,
        resolved_profile=profile,
    )
    if not deterministic["eligible"]:
        raise RuntimeError(
            "Actor checkpoint is not gate-valid: "
            + json.dumps(deterministic["hard_gates"], sort_keys=True)
        )

    client = LlamaClient(
        args.judge_url,
        model=MODEL_PROFILES["editor"].alias,
        timeout=1_800,
    )
    if not client.health():
        raise RuntimeError(f"Judge/editor is not healthy: {args.judge_url}")
    store = TraceStore(evaluation / "editor")
    prefix = _judge_prefix(compiled, scene, rubric)
    judged_cards: list[dict[str, Any]] = []
    for pass_number in (1, 2):
        judged = _judge_one(
            client=client,
            store=store,
            candidate=revision,
            prefix=prefix,
            pass_number=pass_number,
            seed=995_000 + PIPELINES.index(pipeline) * 101 + pass_number,
            rubric=rubric,
        )
        judged_cards.append(merge_scorecards(deterministic, judged))

    raw_score = _candidate_mean_score(raw_id, scores)
    revision_score = mean(float(card["total_score"]) for card in judged_cards)
    if revision_score < raw_score:
        raise RuntimeError(
            f"Actor checkpoint scored {revision_score:.2f}, below raw {raw_score:.2f}"
        )
    raw_deterministic = evaluate_candidate(
        raw,
        scene,
        sources,
        rubric,
        resolved_profile=profile,
    )
    decision = {
        "raw_candidate_id": raw_id,
        "revision_candidate_id": revision.candidate_id,
        "raw_mean_score": round(raw_score, 4),
        "revision_mean_score": round(revision_score, 4),
        "revision_gates": deterministic["hard_gates"],
        "accepted": True,
        "chosen_candidate_id": revision.candidate_id,
        "targeted_defects": _editor_defects(
            raw_id, scores, raw_deterministic
        ),
        "gate_repair_attempts": [
            {
                "attempt": 2,
                "candidate_id": revision.candidate_id,
                "checkpoint_call_id": checkpoint_call_id,
                "checkpoint_prompt_hash": checkpoint_record["prompt_hash"],
                "hard_gates": deterministic["hard_gates"],
                "eligible": True,
            }
        ],
        "revision_scorecards": judged_cards,
        "checkpoint_recovery": True,
    }
    write_json(evaluation / "editor" / f"{pipeline}.decision.json", decision)

    decisions = {
        name: read_json(evaluation / "editor" / f"{name}.decision.json")
        for name in PIPELINES
    }
    finalists: list[Candidate] = []
    for name in PIPELINES:
        item = decisions[name]
        chosen_id = str(item["chosen_candidate_id"])
        raw_item = by_id[str(item["raw_candidate_id"])]
        if chosen_id == raw_item.candidate_id:
            chosen = raw_item
        else:
            call_id = revision_call_id(raw_item.candidate_id, chosen_id)
            chosen = candidate_from_call(
                raw_item,
                completed_call(calls, call_id),
                chosen_id,
            )
        finalists.append(chosen)
        finalist_dir = evaluation / "finalists"
        finalist_dir.mkdir(parents=True, exist_ok=True)
        (finalist_dir / f"{name}.md").write_text(
            chosen.text, encoding="utf-8"
        )

    write_json(
        evaluation / "finalists.json",
        {"finalists": [candidate.to_dict() for candidate in finalists]},
    )
    build_internal_report(
        candidates=candidates,
        scores=scores,
        tournament=tournament,
        editor_decisions=decisions,
        output_dir=evaluation / "internal",
    )
    print(
        json.dumps(
            {
                "actor_revision_score": round(revision_score, 4),
                "actor_raw_score": round(raw_score, 4),
                "finalists": [
                    candidate.candidate_id for candidate in finalists
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
