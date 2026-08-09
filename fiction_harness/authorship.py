"""Proof-carrying authorship and research-promotion eligibility.

Hashes written beside a candidate are not proof of origin: the same writer can
fabricate both.  A research-eligible artifact therefore has to resolve its
model call in an independent append-only ledger and reconstruct byte-for-byte
from the preserved raw response.  Final promotion additionally requires an
exact replay witness.

Version 1 records remain readable as historical metadata, but cannot support a
new claim about a model, prompt, sampler, or autonomous scaffold.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence


LEGACY_AUTHORSHIP_VERSION = "artifact-authorship.v1"
AUTHORSHIP_VERSION = "artifact-authorship.v2"
MODEL_CREATION_KINDS = frozenset({"model_generation", "model_edit"})
MANUAL_CREATION_KINDS = frozenset({"codex_manual_edit", "human_edit"})
CREATION_KINDS = MODEL_CREATION_KINDS | MANUAL_CREATION_KINDS | {
    "deterministic_assembly"
}
RESEARCH_CLAIM_SCOPE = "scaffold_research"
NON_RESEARCH_SCOPES = frozenset({"product_edit", "historical_control"})
REVIEW_EXPOSURES = frozenset(
    {"blind_manuscript", "manuscript_only", "trace_aware", "coordinated"}
)
DERIVATION_OPERATIONS = frozenset(
    {"identity", "strip", "literal_prefix_plus_raw", "autoresearch_manuscript_v1"}
)
ALLOWED_LITERAL_PREFIX_ORIGINS = frozenset(
    {"benchmark_opening_fragment", "locked_canon_fragment", "model_parent"}
)


def text_sha256(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def canonical_record_hash(record: Mapping[str, Any]) -> str:
    return text_sha256(
        json.dumps(
            dict(record),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    )


def _required_string(record: Mapping[str, Any], key: str) -> str:
    value = str(record.get(key, "")).strip()
    if not value:
        raise ValueError(f"artifact authorship requires {key}")
    return value


def _digest(record: Mapping[str, Any], key: str) -> str:
    value = _required_string(record, key)
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"artifact authorship {key} must be a lowercase SHA-256")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ValueError(f"provenance ledger does not exist: {path}")
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid provenance JSONL at {path}:{line_number}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"non-object provenance record at {path}:{line_number}")
        records.append(value)
    return records


def _resolve_path(value: str, evidence_root: str | Path | None) -> Path:
    path = Path(value)
    if not path.is_absolute():
        if evidence_root is None:
            raise ValueError("relative provenance path requires evidence_root")
        path = Path(evidence_root) / path
    return path.resolve(strict=False)


def _completed_call(
    path: Path, *, call_id: str, expected_hash: str
) -> dict[str, Any]:
    matches = [
        record
        for record in _read_jsonl(path)
        if record.get("call_id") == call_id and record.get("status") == "completed"
    ]
    if not matches:
        raise ValueError(f"no completed call {call_id!r} in {path}")
    matching_hashes = [
        record for record in matches if canonical_record_hash(record) == expected_hash
    ]
    if len(matching_hashes) != 1:
        raise ValueError(
            f"completed call {call_id!r} does not resolve uniquely to call_record_hash"
        )
    return matching_hashes[0]


def _raw_response(
    evidence: Mapping[str, Any],
    call: Mapping[str, Any],
    *,
    evidence_root: str | Path | None,
) -> str:
    source = _required_string(evidence, "response_source")
    if source == "call_result_content":
        result = call.get("result")
        if not isinstance(result, Mapping) or not isinstance(result.get("content"), str):
            raise ValueError("completed call lacks result.content")
        raw = str(result["content"])
    elif source == "raw_response_file":
        raw_path = _resolve_path(
            _required_string(evidence, "raw_response_path"), evidence_root
        )
        if not raw_path.is_file():
            raise ValueError(f"raw response does not exist: {raw_path}")
        raw = raw_path.read_text(encoding="utf-8")
    else:
        raise ValueError(f"unsupported response_source: {source}")
    if text_sha256(raw) != _digest(evidence, "raw_response_sha256"):
        raise ValueError("raw response hash does not match preserved response")
    return raw


def _autoresearch_extract(raw: str, stop_markers: Sequence[str]) -> str:
    cut = len(raw)
    for marker in stop_markers:
        position = raw.find(marker)
        if 0 <= position < cut:
            cut = position
    manuscript = raw[:cut].strip()
    paragraphs = [
        item.strip() for item in re.split(r"\n\s*\n", manuscript) if item.strip()
    ]
    return "\n\n".join(paragraphs)


def derive_text(raw: str, derivation: Mapping[str, Any]) -> str:
    """Apply one declared deterministic transformation to a raw response."""

    operation = _required_string(derivation, "operation")
    if operation not in DERIVATION_OPERATIONS:
        raise ValueError(f"unsupported text derivation operation: {operation}")
    if operation == "identity":
        return raw
    if operation == "strip":
        return raw.strip()

    prefix = str(derivation.get("literal_prefix", ""))
    prefix_origin = _required_string(derivation, "literal_prefix_origin")
    if prefix_origin not in ALLOWED_LITERAL_PREFIX_ORIGINS:
        raise ValueError(
            "literal prefix origin is not clean-room eligible: " + prefix_origin
        )
    if text_sha256(prefix) != _digest(derivation, "literal_prefix_sha256"):
        raise ValueError("literal prefix hash mismatch")
    if operation == "literal_prefix_plus_raw":
        return prefix + raw

    markers = derivation.get("stop_markers", ())
    if not isinstance(markers, (list, tuple)) or not all(
        isinstance(item, str) for item in markers
    ):
        raise TypeError("autoresearch derivation stop_markers must be strings")
    manuscript = _autoresearch_extract(raw, markers)
    separator = "\n\n" if raw[:1].isspace() else " "
    return (prefix.rstrip() + separator + manuscript.lstrip()).strip()


def proof_carrying_model_authorship(
    *,
    artifact_id: str,
    text: str,
    model_id: str,
    call_id: str,
    prompt_hash: str,
    seed: int,
    call_ledger_path: str | Path,
    derivation: Mapping[str, Any],
    created_at: str,
    response_source: str = "call_result_content",
    raw_response_path: str | Path | None = None,
    replay_ledger_path: str | Path | None = None,
    parents: Sequence[Mapping[str, str]] = (),
    creation_kind: str = "model_generation",
    claim_scope: str = RESEARCH_CLAIM_SCOPE,
) -> dict[str, Any]:
    """Build v2 provenance from evidence already committed independently."""

    ledger = Path(call_ledger_path).resolve(strict=False)
    completed = [
        record
        for record in _read_jsonl(ledger)
        if record.get("call_id") == call_id and record.get("status") == "completed"
    ]
    if not completed:
        raise ValueError(f"cannot attest absent completed call: {call_id}")
    call = completed[-1]
    call_hash = canonical_record_hash(call)
    evidence: dict[str, Any] = {
        "call_ledger_path": str(ledger),
        "response_source": response_source,
        "raw_response_sha256": "",
        "derivation": dict(derivation),
        "replay_ledger_path": str(
            Path(replay_ledger_path or ledger.with_name("replays.jsonl")).resolve(
                strict=False
            )
        ),
    }
    runtime = call.get("runtime")
    if not isinstance(runtime, Mapping):
        raise ValueError("completed call lacks runtime identity")
    evidence["runtime_identity"] = {
        key: runtime.get(key)
        for key in (
            "model_alias",
            "model_blob",
            "model_size_bytes",
            "model_blob_sha256",
            "model_blob_sample_sha256",
            "llama_server",
            "llama_server_sha256",
            "llama_version",
        )
    }
    if response_source == "call_result_content":
        result = call.get("result")
        if not isinstance(result, Mapping) or not isinstance(result.get("content"), str):
            raise ValueError("completed call lacks result.content")
        raw = str(result["content"])
    elif response_source == "raw_response_file":
        if raw_response_path is None:
            raise ValueError("raw_response_file evidence requires raw_response_path")
        raw_path = Path(raw_response_path).resolve(strict=False)
        if not raw_path.is_file():
            raise ValueError(f"raw response does not exist: {raw_path}")
        evidence["raw_response_path"] = str(raw_path)
        raw = raw_path.read_text(encoding="utf-8")
    else:
        raise ValueError(f"unsupported response_source: {response_source}")
    evidence["raw_response_sha256"] = text_sha256(raw)

    record = {
        "record_type": "ArtifactAuthorship",
        "schema_version": AUTHORSHIP_VERSION,
        "artifact_id": artifact_id,
        "creation_kind": creation_kind,
        "claim_scope": claim_scope,
        "creator_id": f"model-runtime:{model_id}",
        "creator_kind": "model_runtime",
        "created_at": created_at,
        "text_sha256": text_sha256(text),
        "parents": [dict(parent) for parent in parents],
        "model_pipeline_eligible": creation_kind == "model_generation"
        and claim_scope == RESEARCH_CLAIM_SCOPE,
        "model_call": {
            "model_id": model_id,
            "call_id": call_id,
            "prompt_hash": prompt_hash,
            "call_record_hash": call_hash,
            "seed": seed,
        },
        "generation_evidence": evidence,
    }
    validate_artifact_authorship(
        record,
        text=text,
        artifact_id=artifact_id,
        require_model_pipeline=False,
        require_replay=False,
    )
    return record


def model_artifact_authorship(
    *,
    artifact_id: str,
    text: str,
    model_id: str,
    call_id: str,
    prompt_hash: str,
    seed: int,
    call_record: Mapping[str, Any],
    created_at: str,
    parents: Sequence[Mapping[str, str]] = (),
    creation_kind: str = "model_generation",
) -> dict[str, Any]:
    """Build a legacy self-attestation for historical compatibility only.

    New research code must use :func:`proof_carrying_model_authorship`.
    """

    record = {
        "record_type": "ArtifactAuthorship",
        "schema_version": LEGACY_AUTHORSHIP_VERSION,
        "artifact_id": artifact_id,
        "creation_kind": creation_kind,
        "creator_id": f"model-runtime:{model_id}",
        "creator_kind": "model_runtime",
        "created_at": created_at,
        "text_sha256": text_sha256(text),
        "parents": [dict(parent) for parent in parents],
        "model_pipeline_eligible": False,
        "model_call": {
            "model_id": model_id,
            "call_id": call_id,
            "prompt_hash": prompt_hash,
            "call_record_hash": canonical_record_hash(call_record),
            "seed": seed,
        },
        "historical_only_reason": "self-attested call record is not independent evidence",
    }
    validate_artifact_authorship(record, text=text, artifact_id=artifact_id)
    return record


def _verify_replay(
    evidence: Mapping[str, Any],
    model_call: Mapping[str, Any],
    *,
    evidence_root: str | Path | None,
) -> dict[str, Any]:
    path = _resolve_path(
        _required_string(evidence, "replay_ledger_path"), evidence_root
    )
    if not path.is_file():
        raise ValueError(f"promotion requires replay witness ledger: {path}")
    witnesses = []
    for item in _read_jsonl(path):
        if (
            item.get("record_type") == "ModelReplayWitness"
            and item.get("call_id") == model_call.get("call_id")
            and item.get("original_call_record_hash")
            == model_call.get("call_record_hash")
            and item.get("matches_original") is True
        ):
            body = dict(item)
            witness_hash = str(body.pop("witness_hash", ""))
            if witness_hash == canonical_record_hash(body):
                witnesses.append(item)
    if len(witnesses) != 1:
        raise ValueError("promotion requires one valid exact replay witness")
    witness = witnesses[0]
    if witness.get("raw_response_sha256") != evidence.get("raw_response_sha256"):
        raise ValueError("replay response does not match original raw response")
    original_runtime = evidence.get("runtime_identity")
    replay_runtime = witness.get("runtime")
    if not isinstance(original_runtime, Mapping) or not isinstance(
        replay_runtime, Mapping
    ):
        raise ValueError("replay witness lacks runtime identity")
    for key in (
        "model_blob_sha256",
        "model_blob_sample_sha256",
        "model_size_bytes",
        "llama_server_sha256",
        "llama_version",
    ):
        if original_runtime.get(key) != replay_runtime.get(key):
            raise ValueError(f"replay runtime differs from original: {key}")
    return dict(witness)


def validate_artifact_authorship(
    record: Mapping[str, Any],
    *,
    text: str,
    artifact_id: str = "",
    require_model_pipeline: bool = False,
    require_replay: bool | None = None,
    evidence_root: str | Path | None = None,
) -> dict[str, Any]:
    """Validate authorship; research promotion is fail-closed and replay-backed."""

    if not isinstance(record, Mapping) or not record:
        raise ValueError("candidate lacks required artifact_authorship")
    if record.get("record_type") != "ArtifactAuthorship":
        raise ValueError("artifact_authorship has wrong record_type")
    version = str(record.get("schema_version", ""))
    if version not in {LEGACY_AUTHORSHIP_VERSION, AUTHORSHIP_VERSION}:
        raise ValueError("artifact_authorship has unsupported schema_version")
    recorded_id = _required_string(record, "artifact_id")
    if artifact_id and recorded_id != artifact_id:
        raise ValueError("artifact_authorship artifact_id does not match candidate")
    creation_kind = _required_string(record, "creation_kind")
    if creation_kind not in CREATION_KINDS:
        raise ValueError(f"unsupported artifact creation_kind: {creation_kind}")
    _required_string(record, "creator_id")
    creator_kind = _required_string(record, "creator_kind")
    if creator_kind not in {"model_runtime", "codex_task", "human", "harness"}:
        raise ValueError(f"unsupported artifact creator_kind: {creator_kind}")
    _required_string(record, "created_at")
    if _digest(record, "text_sha256") != text_sha256(text):
        raise ValueError("artifact_authorship text_sha256 does not match candidate text")

    parents = record.get("parents", ())
    if not isinstance(parents, (list, tuple)):
        raise TypeError("artifact_authorship parents must be a list")
    for parent in parents:
        if not isinstance(parent, Mapping):
            raise TypeError("artifact_authorship parent must be an object")
        _required_string(parent, "artifact_id")
        _digest(parent, "text_sha256")

    eligible = record.get("model_pipeline_eligible")
    if not isinstance(eligible, bool):
        raise TypeError("artifact_authorship model_pipeline_eligible must be boolean")
    model_call = record.get("model_call")
    if creation_kind in MODEL_CREATION_KINDS:
        if not isinstance(model_call, Mapping):
            raise ValueError("model-created artifact requires model_call provenance")
        for key in ("model_id", "call_id", "prompt_hash", "call_record_hash"):
            if key.endswith("hash"):
                _digest(model_call, key)
            else:
                _required_string(model_call, key)
        if not isinstance(model_call.get("seed"), int):
            raise TypeError("model_call seed must be an integer")
        if creation_kind == "model_edit" and not parents:
            raise ValueError("model_edit requires at least one parent")
    elif model_call not in (None, {}):
        raise ValueError("non-model artifact must not claim model_call provenance")

    if creation_kind in MANUAL_CREATION_KINDS:
        if not parents:
            raise ValueError("manual edit requires at least one parent")
        if eligible:
            raise ValueError("manual edit cannot be model_pipeline_eligible")
    if creation_kind == "deterministic_assembly":
        if not parents:
            raise ValueError("deterministic assembly requires parents")
        if record.get("prose_added") is not False:
            raise ValueError("deterministic assembly must attest prose_added=false")
        _digest(record, "assembly_record_hash")

    # Version 1 records can describe history but can never prove a research claim.
    if version == LEGACY_AUTHORSHIP_VERSION:
        if require_model_pipeline:
            raise ValueError(
                "legacy self-attested provenance is historical-only, not scaffold evidence"
            )
        return dict(record)

    claim_scope = _required_string(record, "claim_scope")
    if claim_scope not in {RESEARCH_CLAIM_SCOPE, *NON_RESEARCH_SCOPES}:
        raise ValueError(f"unsupported authorship claim_scope: {claim_scope}")
    if creation_kind in MODEL_CREATION_KINDS:
        evidence = record.get("generation_evidence")
        if not isinstance(evidence, Mapping):
            raise ValueError("v2 model artifact requires generation_evidence")
        ledger = _resolve_path(
            _required_string(evidence, "call_ledger_path"), evidence_root
        )
        call = _completed_call(
            ledger,
            call_id=_required_string(model_call, "call_id"),
            expected_hash=_digest(model_call, "call_record_hash"),
        )
        runtime = call.get("runtime")
        if not isinstance(runtime, Mapping):
            raise ValueError("completed call lacks runtime identity")
        normalized_runtime = {
            key: runtime.get(key)
            for key in (
                "model_alias",
                "model_blob",
                "model_size_bytes",
                "model_blob_sha256",
                "model_blob_sample_sha256",
                "llama_server",
                "llama_server_sha256",
                "llama_version",
            )
        }
        evidence_runtime = evidence.get("runtime_identity")
        if evidence_runtime is None:
            # Builder-created records bind to the independently logged runtime.
            # The normalized copy is returned below only after all checks pass.
            pass
        elif evidence_runtime != normalized_runtime:
            raise ValueError("authorship runtime identity differs from call ledger")
        if call.get("prompt_hash") != model_call.get("prompt_hash"):
            raise ValueError("call ledger prompt hash differs from authorship")
        if str(call.get("model", call.get("model_id", ""))) != str(
            model_call.get("model_id")
        ):
            raise ValueError("call ledger model differs from authorship")
        parameters = call.get("parameters", {})
        call_seed = parameters.get("seed") if isinstance(parameters, Mapping) else call.get("seed")
        if call_seed != model_call.get("seed"):
            raise ValueError("call ledger seed differs from authorship")
        raw = _raw_response(evidence, call, evidence_root=evidence_root)
        derivation = evidence.get("derivation")
        if not isinstance(derivation, Mapping):
            raise ValueError("generation_evidence requires deterministic derivation")
        reconstructed = derive_text(raw, derivation)
        if reconstructed != text:
            raise ValueError("candidate text cannot be reconstructed from raw model response")

    if require_model_pipeline:
        if creation_kind != "model_generation":
            raise ValueError(
                f"{creation_kind} is not eligible as autonomous scaffold evidence"
            )
        if claim_scope != RESEARCH_CLAIM_SCOPE or not eligible:
            raise ValueError("artifact is not declared as scaffold research evidence")
        runtime = record["generation_evidence"].get("runtime_identity")
        if not isinstance(runtime, Mapping):
            raise ValueError("promotion requires bound runtime identity")
        for key in (
            "model_blob_sha256",
            "model_blob_sample_sha256",
            "llama_server_sha256",
            "llama_version",
        ):
            if not runtime.get(key):
                raise ValueError(f"promotion requires runtime identity field {key}")
        replay_required = True if require_replay is None else require_replay
        if replay_required:
            witness = _verify_replay(
                record["generation_evidence"], model_call, evidence_root=evidence_root
            )
            normalized = dict(record)
            normalized["verified_replay"] = witness
            return normalized
    return dict(record)


def validate_review_attestations(
    reviews: Sequence[Mapping[str, Any]],
    *,
    creator_id: str,
    minimum_independent: int = 0,
) -> dict[str, Any]:
    """Validate review identity and count genuinely independent blind reads."""

    independent: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for review in reviews:
        if not isinstance(review, Mapping):
            raise TypeError("review attestation must be an object")
        reviewer_id = _required_string(review, "reviewer_id")
        exposure = _required_string(review, "exposure")
        if exposure not in REVIEW_EXPOSURES:
            raise ValueError(f"unsupported review exposure: {exposure}")
        review_hash = _digest(review, "review_hash")
        claimed_independent = review.get("independent")
        if not isinstance(claimed_independent, bool):
            raise TypeError("review independent flag must be boolean")
        actually_independent = reviewer_id != creator_id and exposure == "blind_manuscript"
        if claimed_independent != actually_independent:
            raise ValueError(
                "review independence claim conflicts with creator identity/exposure"
            )
        if actually_independent:
            independent.add(reviewer_id)
        normalized.append(
            {**dict(review), "review_hash": review_hash, "independent": actually_independent}
        )
    if len(independent) < minimum_independent:
        raise ValueError(
            f"promotion requires {minimum_independent} independent blind reviews; "
            f"found {len(independent)}"
        )
    return {
        "reviews": normalized,
        "independent_blind_reviewers": sorted(independent),
        "independent_blind_review_count": len(independent),
    }
