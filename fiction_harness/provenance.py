"""Repository-wide provenance audit and exact replay witnesses."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from .authorship import (
    AUTHORSHIP_VERSION,
    canonical_record_hash,
    text_sha256,
    validate_artifact_authorship,
)
from .model_client import LlamaClient
from .runtime import TraceStore, canonical_json, model_runtime_provenance


AUDIT_VERSION = "provenance-audit.v1"
REPLAY_VERSION = "model-replay-witness.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: Path, record: Mapping[str, Any]) -> None:
    TraceStore._append(path, record)


def _completed_call(path: Path, call_id: str, expected_hash: str) -> dict[str, Any]:
    matches = [
        item
        for item in TraceStore.read(path)
        if item.get("call_id") == call_id
        and item.get("status") == "completed"
        and canonical_record_hash(item) == expected_hash
    ]
    if len(matches) != 1:
        raise ValueError("replay requires one uniquely resolved completed call")
    return matches[0]


def replay_artifact(
    *,
    authorship: Mapping[str, Any],
    client: LlamaClient,
) -> dict[str, Any]:
    """Replay one recorded call and append an exact-match witness.

    The completed call must preserve its prompt bytes via ``prompt_path`` and
    parameters.  Chat and raw completion transports are both supported.
    """

    if authorship.get("schema_version") != AUTHORSHIP_VERSION:
        raise ValueError("only proof-carrying v2 artifacts can be replayed")
    model_call = authorship.get("model_call")
    evidence = authorship.get("generation_evidence")
    if not isinstance(model_call, Mapping) or not isinstance(evidence, Mapping):
        raise ValueError("authorship lacks model call evidence")
    ledger_path = Path(str(evidence.get("call_ledger_path", "")))
    call = _completed_call(
        ledger_path,
        str(model_call.get("call_id", "")),
        str(model_call.get("call_record_hash", "")),
    )
    prompt_path = Path(str(call.get("prompt_path", "")))
    if not prompt_path.is_file():
        raise ValueError("replay requires a preserved prompt_path")
    prompt = prompt_path.read_text(encoding="utf-8")
    if text_sha256(prompt) != call.get("prompt_hash"):
        raise ValueError("preserved replay prompt hash mismatch")
    parameters = call.get("parameters")
    if not isinstance(parameters, Mapping):
        raise ValueError("completed call lacks replay parameters")
    kwargs = {
        "prompt": prompt,
        "seed": int(parameters["seed"]),
        "max_tokens": int(parameters["max_tokens"]),
        "temperature": float(parameters.get("temperature", 0.9)),
        "top_p": float(parameters.get("top_p", 0.95)),
        "min_p": float(parameters.get("min_p", 0.02)),
    }
    erase = getattr(client, "erase_idle_slots", None)
    erased_slots = erase() if callable(erase) else []
    transport = str(call.get("transport", "chat_completion"))
    if transport == "raw_completion":
        completion = client.complete_raw(
            **kwargs,
            xtc_probability=float(parameters.get("xtc_probability", 0.0)),
            stop=tuple(parameters.get("stop", ())) or None,
        )
    elif transport == "chat_completion":
        completion = client.complete(
            **kwargs,
            stop=tuple(parameters.get("stop", ())) or None,
        )
    else:
        raise ValueError(f"unsupported replay transport: {transport}")
    replay_raw = completion.content
    expected = str(evidence.get("raw_response_sha256", ""))
    observed = text_sha256(replay_raw)
    body = {
        "record_type": "ModelReplayWitness",
        "schema_version": REPLAY_VERSION,
        "call_id": model_call["call_id"],
        "original_call_record_hash": model_call["call_record_hash"],
        "prompt_hash": model_call["prompt_hash"],
        "model_id": model_call["model_id"],
        "seed": model_call["seed"],
        "raw_response_sha256": observed,
        "expected_raw_response_sha256": expected,
        "matches_original": observed == expected,
        "cold_replay": True,
        "erased_slots": erased_slots,
        "runtime": model_runtime_provenance(client.model),
        "replayed_at": _now(),
    }
    witness = {**body, "witness_hash": canonical_record_hash(body)}
    replay_path = Path(str(evidence.get("replay_ledger_path", "")))
    _append_jsonl(replay_path, witness)
    if not witness["matches_original"]:
        raise ValueError("model replay did not reproduce the original raw response")
    return witness


def verify_candidate_record(
    candidate: Mapping[str, Any], *, require_replay: bool = True
) -> dict[str, Any]:
    candidate_id = str(candidate.get("candidate_id", candidate.get("id", "")))
    text = str(candidate.get("text", ""))
    return validate_artifact_authorship(
        candidate.get("artifact_authorship", {}),
        text=text,
        artifact_id=candidate_id,
        require_model_pipeline=True,
        require_replay=require_replay,
    )


def _json_objects(path: Path) -> Sequence[Mapping[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, list):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def audit_repository(project_root: str | Path) -> dict[str, Any]:
    """Inventory known provenance contamination without changing history."""

    root = Path(project_root).resolve()
    findings: list[dict[str, Any]] = []
    for path in sorted((root / "03_scene_lab" / "runs").rglob("*")):
        if not path.is_file():
            continue
        relative = str(path.relative_to(root))
        lower = relative.casefold()
        reasons: list[str] = []
        category = ""
        if path.suffix.casefold() in {".md", ".json", ".jsonl"} and (
            ".codex." in lower
            or "/frontier_editor/" in lower
            or "/frontier_novelist/" in lower
        ):
            category = "frontier_or_codex_artifact"
            reasons.append("path declares Codex/frontier authorship or evaluation")
        if path.name.startswith("experiment_manifest") and path.suffix == ".json":
            for obj in _json_objects(path):
                serialized = canonical_json(obj).casefold()
                if ".codex." in serialized or "frontier_novelist" in serialized or "frontier_editor" in serialized:
                    category = "experiment_conditioned_on_frontier_prose"
                    reasons.append("manifest references Codex/frontier prose")
                    break
        if path.name in {"candidates.jsonl", "finalists.json", "reveal_key.json"}:
            lines = (
                path.read_text(encoding="utf-8").splitlines()
                if path.suffix == ".jsonl"
                else [path.read_text(encoding="utf-8")]
            )
            for line in lines:
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                serialized = canonical_json(obj).casefold()
                if "codex_manual_edit" in serialized:
                    category = "manual_prose_in_candidate_or_package"
                    reasons.append("candidate/package includes a manual Codex edit")
                if "artifact-authorship.v1" in serialized:
                    reasons.append("candidate/package relies on legacy self-attestation")
                    category = category or "legacy_unverified_model_claim"
        if reasons:
            findings.append(
                {
                    "path": relative,
                    "sha256": __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
                    "category": category,
                    "reasons": sorted(set(reasons)),
                    "research_claim_status": "quarantined_historical_only",
                }
            )
    summary: dict[str, int] = {}
    for item in findings:
        summary[item["category"]] = summary.get(item["category"], 0) + 1
    body = {
        "record_type": "RepositoryProvenanceAudit",
        "schema_version": AUDIT_VERSION,
        "project_root": str(root),
        "policy": {
            "frontier_role": "critic_only",
            "clean_room": "no Codex/frontier manuscript prose in runway, exemplars, targets, or holdouts",
            "promotion": "v2 ledger resolution plus exact raw derivation plus exact replay",
            "historical_files": "preserved, never silently upgraded",
        },
        "summary": summary,
        "findings": findings,
        "audited_at": _now(),
    }
    hash_body = {key: value for key, value in body.items() if key != "audited_at"}
    return {**body, "audit_hash": canonical_record_hash(hash_body)}


def write_audit(project_root: str | Path, output_dir: str | Path) -> dict[str, str]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    report = audit_repository(project_root)
    json_path = output / "repository_provenance_audit.v1.json"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Repository provenance audit",
        "",
        "Historical files are preserved. The entries below cannot support claims about autonomous scaffold quality.",
        "",
        f"Audit hash: `{report['audit_hash']}`",
        "",
        "## Summary",
        "",
    ]
    for name, count in sorted(report["summary"].items()):
        lines.append(f"- {name}: {count}")
    lines.extend(("", "## Findings", ""))
    for item in report["findings"]:
        lines.append(f"- `{item['path']}` — {item['category']}: {'; '.join(item['reasons'])}")
    markdown_path = output / "repository_provenance_audit.v1.md"
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": str(json_path), "markdown": str(markdown_path), "audit_hash": report["audit_hash"]}


def assert_critic_only_frontier(output: Mapping[str, Any]) -> None:
    """Reject frontier responses that contain replacement manuscript prose."""

    permitted = {
        "compliant",
        "defects",
        "scores",
        "evidence",
        "prompt_mutation",
        "prediction",
        "falsifier",
    }
    unknown = set(output) - permitted
    if unknown:
        raise ValueError("frontier critic emitted non-critic fields: " + ", ".join(sorted(unknown)))
    for key in ("replacement", "rewrite", "revised_text", "manuscript", "prose"):
        if key in output:
            raise ValueError(f"frontier critic may not emit manuscript field {key}")
