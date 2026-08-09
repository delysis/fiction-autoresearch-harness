"""Compose a full causal movement from bounded base-model submovements."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from .anti_copy import AntiCopyIndex, AntiCopyPolicy, StreamingNgramGuard
from .continuation import clean_generated_prose, packet_leakage_markers
from .core import atomic_write_text, hash_json, sha256_text, write_json
from .evaluation import word_count
from .heterogeneous_demonstrations import (
    load_heterogeneous_demonstrations as load_heterogeneous_demo_fixture,
)
from .long_context import self_repetition_report
from .meta_prompting import (
    Demonstration,
    _append_jsonl,
    _manuscript_runway,
    _read_json,
    _render_demonstrations,
    _story_bible,
    _terminal_calls,
    _target_atom_diagnostics,
    load_anti_copy_sources,
    load_s01_demonstrations,
    render_occurrence_ledger,
)
from .model_client import LlamaClient
from .shared_endpoint import SharedEndpointAdmission


COMPOSED_VERSION = "paired-composed.v12"

COMPOSED_OPENING_RUNWAY = (
    "Four nights after the calibration game, the alignment session had run "
    "twenty-three minutes past its promised end. Adrian and Miriam had gone, "
    "leaving Mara, Livia, and Jonah at the cedar table with the last sequence "
    "still open across three monitors. The lab door remained closed. Jonah "
    "kept typing with both hands, his attention on the live traces. Livia sat "
    "nearest the shared interface, one bare foot hooked behind the other chair. "
    "Mara had not eaten since noon, though she had blamed the tremor in her "
    "hands on data density. Her bag waited beside her chair. No one had begun "
    "to pack. The raw telemetry remained behind Fulcrum’s permission wall, "
    "visible only as summaries. Mara watched the clock change by another minute "
    "and said nothing."
)


@dataclass(frozen=True, slots=True)
class SegmentSpec:
    segment_id: str
    atom_ids: tuple[str, ...]
    minimum_words: int
    maximum_words: int
    local_endpoint: str
    required_dialogue_turns: int = 3


SEGMENTS = (
    SegmentSpec(
        "pressure",
        ("s02-a4b-22063-tea", "s02-a4b-22063-unremarkable"),
        260,
        350,
        "Livia has accurately exposed the vulnerability, but has not offered telemetry access.",
    ),
    SegmentSpec(
        "gift-and-complicity",
        ("s02-a4b-22063-access", "s02-a4b-22023-jonah-complicity"),
        200,
        270,
        "The access gift and Jonah's complicity are visible; Mara has not accepted yet.",
    ),
    SegmentSpec(
        "choice-and-trap",
        ("s02-a4b-22063-accept", "s02-a4b-22063-cooling-tea"),
        150,
        220,
        "Mara has accepted; the tea cools and the session continues without granting an exit.",
        required_dialogue_turns=0,
    ),
)


SEGMENT_RUNWAYS = {
    "gift-and-complicity": (
        "“Fulcrum doesn’t give this to new fellows,” Livia said. She rotated "
        "the shared interface and opened DATA PERMISSIONS. A new line appeared: "
        "SCOPE—RAW TELEMETRY STREAM; EXPIRES—06:00; ASSIGNEE—MARA VALE; "
        "STATUS—PENDING. Jonah stopped typing and left both hands visible above "
        "the keys."
    ),
    "choice-and-trap": (
        "The permission line remained on the shared interface: MARA VALE / "
        "PENDING. The ACCEPT control waited beneath it. Jonah’s next sequence "
        "remained ready; Mara still held the cooling tea."
    ),
}


SEGMENT_INVALID_COORDINATES = {
    "pressure": "telemetry access, acceptance, packing, exit, or time jump",
    "gift-and-complicity": (
        "physical doorway, gate, room, or key access; laptop handoff; Mara "
        "pressing or accepting the permission; anyone packing or leaving; time "
        "jump; new heading"
    ),
    "choice-and-trap": "exit, time jump, new heading, or a completed later scene",
}


def _segment_target(
    target: Mapping[str, Any], spec: SegmentSpec
) -> dict[str, Any]:
    wanted = set(spec.atom_ids)
    occurrences = [
        dict(item)
        for item in target.get("occurrences", ())
        if isinstance(item, Mapping) and item.get("atom_id") in wanted
    ]
    if tuple(item.get("atom_id") for item in occurrences) != spec.atom_ids:
        raise ValueError(f"segment atom mismatch: {spec.segment_id}")
    return {
        "character_invariants": dict(target.get("character_invariants", {})),
        "current_state": dict(target.get("current_state", {})),
        "sequence": {
            "sequence_id": f"s02-composed-{spec.segment_id}",
            "endpoint": spec.local_endpoint,
        },
        "occurrences": occurrences,
    }


def build_segment_prompt(
    *,
    target: Mapping[str, Any],
    spec: SegmentSpec,
    demonstrations: Sequence[Demonstration],
    manuscript_so_far: str,
    stable_reference_prefix: str | None = None,
    target_case_number: int = 2,
) -> str:
    local = _segment_target(target, spec)
    reference_prefix = stable_reference_prefix
    if reference_prefix is None:
        reference_prefix = (
            "<fiction-preparation>\nEDITORIAL APPRENTICESHIP ARCHIVE\n\n"
            + _render_demonstrations(demonstrations)
        )
    preparation = (
        reference_prefix.rstrip()
        + f"\n\nCASE {target_case_number}: EDITORIAL EVENT LEDGER\n"
        + _story_bible(local)
        + "\n\n"
        + "The finished manuscript below is already in progress. Continue it "
        "without a heading. Enact this local ledger once, but do not summarize "
        "or repeat its wording. Let Mara attempt one plausible coping move that "
        "changes the next response. Give the pressure time to act through at "
        f"least {spec.required_dialogue_turns} dialogue turns before reaching "
        "the local stopping state.\n"
        + render_occurrence_ledger(local)
        + f"\nInvalid coordinates: {SEGMENT_INVALID_COORDINATES[spec.segment_id]}."
        + f"\n\nLocal length band: {spec.minimum_words}-{spec.maximum_words} words; "
        "the scaffold selects only a complete paragraph boundary."
    )
    return (
        preparation
        + f"\n\nCASE {target_case_number}: FINISHED MANUSCRIPT\n\n"
        + manuscript_so_far.rstrip()
    )


def segment_gate(segment_id: str, text: str) -> dict[str, Any]:
    atoms = _target_atom_diagnostics(text)
    checks = atoms["checks"]
    folded = text.casefold()
    if segment_id == "pressure":
        required = checks["tea_care"] and checks["unexceptional_fear"]
        premature = checks["telemetry_access"] or checks["mara_accepts"]
        continuity_anchor = bool(re.search(r"\b(?:session|lab)\b", folded))
        continuity_violation = bool(
            re.search(
                r"\b(?:(?:stood|went|walked|waited|sat)\s+outside|"
                r"outside\s+(?:the\s+)?(?:lab|pavilion|door)|"
                r"on\s+the\s+(?:cedar\s+)?deck|across\s+the\s+lawn|"
                r"before\s+dinner|walked?\s+(?:away|down|home)|"
                r"livia's\s+house|livia’s\s+house)\b",
                folded,
            )
        )
    elif segment_id == "gift-and-complicity":
        required = checks["telemetry_access"] and checks["jonah_complicity"]
        premature = checks["mara_accepts"]
        continuity_anchor = True
        continuity_violation = False
    elif segment_id == "choice-and-trap":
        required = checks["mara_accepts"] and checks["session_continues"]
        premature = False
        continuity_anchor = True
        continuity_violation = bool(
            re.search(
                r"\b(?:the\s+)?next\s+morning\b|\b(?:hours?|days?)\s+later\b|"
                r"\bby\s+(?:dawn|morning)\b",
                folded,
            )
        )
    else:
        raise ValueError(f"unknown composed segment: {segment_id}")
    head_hop = bool(
        re.search(
            r"\b(?:Livia|Jonah)\s+(?:knew|thought|wondered|remembered|felt)\b",
            text,
            re.IGNORECASE,
        )
    )
    heading = bool(
        re.search(r"(?mi)^\s*(?:#|CHAPTER\b|END\b|CASE\s+\d+\b)", text)
    )
    dialogue_turns = len(re.findall(r"[“\"]", text)) // 2
    required_dialogue_turns = next(
        item.required_dialogue_turns for item in SEGMENTS if item.segment_id == segment_id
    )
    leakage = packet_leakage_markers(text)
    return {
        "required_atoms": bool(required),
        "premature_later_atom": bool(premature),
        "continuity_anchor": continuity_anchor,
        "continuity_violation": continuity_violation,
        "head_hop": head_hop,
        "heading_or_end_marker": heading,
        "forbidden_future": atoms["forbidden_future"],
        "dialogue_turns": dialogue_turns,
        "required_dialogue_turns": required_dialogue_turns,
        "packet_leakage_markers": list(leakage),
        "eligible": bool(
            required
            and not premature
            and not continuity_violation
            and not head_hop
            and not heading
            and not atoms["forbidden_future"]
            and dialogue_turns >= required_dialogue_turns
            and not leakage
        ),
    }


def extract_gated_segment(raw: str, spec: SegmentSpec) -> tuple[str, dict[str, Any]]:
    """Choose the latest complete prefix that reaches this segment's endpoint.

    A length controller must not blindly prefer a later paragraph that crosses
    into the next causal movement. Evaluate every complete paragraph boundary
    inside the local word band, then select the longest prefix that still
    satisfies the segment gate.
    """

    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", raw) if item.strip()]
    selected: list[str] = []
    eligible: list[tuple[str, dict[str, Any]]] = []
    for paragraph in paragraphs:
        trial = "\n\n".join((*selected, paragraph))
        words = word_count(trial)
        if words > spec.maximum_words:
            break
        selected.append(paragraph)
        if words < spec.minimum_words or not re.search(r"[.!?][\"”’']?\s*$", paragraph):
            continue
        gate = segment_gate(spec.segment_id, trial)
        if gate["eligible"]:
            eligible.append((trial, gate))
    if not eligible:
        raise ValueError(
            f"no gate-eligible paragraph boundary within {spec.minimum_words}-{spec.maximum_words} words"
        )
    return eligible[-1]


def build_segment_anti_copy_index(
    source_docs: Mapping[str, str], source_categories: Mapping[str, str]
) -> AntiCopyIndex:
    """Protect source prose without indexing the mutable generation envelope.

    The prompt ends on an authored manuscript runway. Indexing the whole prompt
    makes an ordinary bridging sentence look like plagiarism and also conflates
    scaffold leakage with source copying. Source books, demonstrations,
    canonical prose, and held-out prose remain protected here; packet leakage
    is rejected independently by ``segment_gate``.
    """

    return AntiCopyIndex(
        dict(source_docs),
        categories=dict(source_categories),
        policy=AntiCopyPolicy(exact_words=12),
    )


def load_promoted_segments(
    project_root: Path, promotion_manifest_path: Path
) -> tuple[dict[str, str], dict[str, Any]]:
    """Load hash-locked, gate-valid parent movements for a derived run.

    Promotion is explicit rather than inferred from a neighboring run folder.
    Both the selected prefix and its immutable raw parent are verified so a
    child run cannot silently inherit an edited checkpoint.
    """

    project_root = project_root.resolve()
    manifest_path = promotion_manifest_path.resolve()
    manifest = _read_json(manifest_path)
    if manifest.get("record_type") != "ComposedSegmentPromotion":
        raise ValueError("promotion manifest has wrong record_type")
    if manifest.get("version") != "composed-segment-promotion.v1":
        raise ValueError("unsupported promotion manifest version")
    specs = {item.segment_id: item for item in SEGMENTS}
    promoted: dict[str, str] = {}
    for segment_id, record in manifest.get("segments", {}).items():
        if segment_id not in specs or not isinstance(record, Mapping):
            raise ValueError(f"invalid promoted segment: {segment_id}")
        selected_path = project_root / str(record["selected_path"])
        source_raw_path = project_root / str(record["source_raw_path"])
        selected = selected_path.read_text(encoding="utf-8").rstrip()
        source_raw = source_raw_path.read_text(encoding="utf-8")
        if sha256_text(selected) != record.get("selected_sha256"):
            raise ValueError(f"promoted segment hash changed: {segment_id}")
        if sha256_text(source_raw) != record.get("source_raw_sha256"):
            raise ValueError(f"promoted raw parent hash changed: {segment_id}")
        if word_count(selected) != int(record.get("selected_words", -1)):
            raise ValueError(f"promoted segment word count changed: {segment_id}")
        spec = specs[segment_id]
        if not spec.minimum_words <= word_count(selected) <= spec.maximum_words:
            raise ValueError(f"promoted segment outside local word band: {segment_id}")
        gate = segment_gate(segment_id, selected)
        if not gate["eligible"]:
            raise ValueError(f"promoted segment no longer passes gate: {segment_id}")
        source_runway = str(record.get("deterministic_runway", "")).rstrip()
        if source_runway:
            if sha256_text(source_runway) != record.get("deterministic_runway_sha256"):
                raise ValueError(f"promoted deterministic runway hash changed: {segment_id}")
            source_for_extraction = source_runway + "\n\n" + source_raw
        else:
            source_for_extraction = source_raw
        extracted, _ = extract_gated_segment(source_for_extraction, spec)
        if extracted != selected:
            raise ValueError(f"promoted segment is not the selected raw prefix: {segment_id}")
        promoted[segment_id] = selected
    if not promoted:
        raise ValueError("promotion manifest contains no segments")
    provenance = {
        "path": str(manifest_path.relative_to(project_root)),
        "sha256": sha256_text(manifest_path.read_text(encoding="utf-8")),
        "segments": manifest["segments"],
    }
    return promoted, provenance


def run_composed_realization(
    project_root: Path,
    run_dir: Path,
    *,
    client: LlamaClient,
    seeds: Sequence[int],
    attempts_per_segment: int = 4,
    maximum_new_tokens: int = 750,
    admission: SharedEndpointAdmission | None = None,
    slot_id: int | None = None,
    reference_arm_id: str = "paired-icl-16k",
    stop_after_segments: int | None = None,
    archive_case_count: int = 1,
    demonstration_profile: str = "heterogeneous-public-domain-v1",
    promotion_manifest_path: Path | None = None,
    collect_next_segment_pool: bool = False,
) -> dict[str, Any]:
    if len(seeds) < len(SEGMENTS) * attempts_per_segment:
        raise ValueError("not enough deterministic seeds for composed attempts")
    if stop_after_segments is not None and not 1 <= stop_after_segments <= len(SEGMENTS):
        raise ValueError("stop_after_segments must be between 1 and 3")
    if demonstration_profile == "heterogeneous-public-domain-v1":
        demonstrations = list(load_heterogeneous_demo_fixture(project_root))
    elif demonstration_profile == "s01-variants-v1":
        demonstrations = load_s01_demonstrations(project_root)
    elif demonstration_profile == "mixed-heterogeneous-project-nearest-v1":
        demonstrations = list(load_heterogeneous_demo_fixture(project_root))
        demonstrations.append(load_s01_demonstrations(project_root)[0])
    else:
        raise ValueError(f"unknown demonstration profile: {demonstration_profile}")
    if not 1 <= archive_case_count <= len(demonstrations):
        raise ValueError("archive_case_count is outside the available demonstration range")
    promoted_segments: dict[str, str] = {}
    promotion_provenance: dict[str, Any] | None = None
    if promotion_manifest_path is not None:
        promoted_segments, promotion_provenance = load_promoted_segments(
            project_root, promotion_manifest_path
        )
    meta_run = project_root / "03_scene_lab/runs/s02-base-meta-prompt-v3"
    meta_manifest = _read_json(meta_run / "experiment_manifest.v1.json")
    target_path = (
        project_root
        / "03_scene_lab/runs/s02-compute-v4.3-a4b/verbalized_to_instruction"
        / "novelist_packet.seq1.v1.json"
    )
    target = _read_json(target_path)
    target = {key: value for key, value in target.items() if key != "manuscript_tail"}
    canonical_path = project_root / str(meta_manifest["canonical_s01"]["path"])
    canonical = canonical_path.read_text(encoding="utf-8")
    reference_arm = next(
        item for item in meta_manifest["arms"] if item["arm_id"] == reference_arm_id
    )
    reference_path = project_root / str(reference_arm["prompt_path"])
    reference_prompt = reference_path.read_text(encoding="utf-8")
    if sha256_text(reference_prompt) != reference_arm["prompt_hash"]:
        raise ValueError("reference source prompt hash changed")
    stable_reference_prefix = (
        "<fiction-preparation>\nEDITORIAL APPRENTICESHIP ARCHIVE\n\n"
        + _render_demonstrations(demonstrations[:archive_case_count])
    )
    source_docs, source_categories = load_anti_copy_sources(
        project_root, meta_manifest
    )
    heldout = meta_manifest["target"]["heldout_reference"]
    heldout_path = project_root / str(heldout["path"])
    heldout_text = heldout_path.read_text(encoding="utf-8")
    if sha256_text(heldout_text) != heldout["sha256"]:
        raise ValueError("held-out accepted S02 hash changed")
    heldout_guard = AntiCopyIndex(
        {"accepted-s02-heldout": heldout_text},
        policy=AntiCopyPolicy(exact_words=12),
    )
    if heldout_guard.exact_matches(COMPOSED_OPENING_RUNWAY):
        raise ValueError("backtranslated runway overlaps held-out accepted S02")
    for segment_id, runway in SEGMENT_RUNWAYS.items():
        if heldout_guard.exact_matches(runway):
            raise ValueError(
                f"deterministic {segment_id} runway overlaps held-out accepted S02"
            )
    source_docs["heldout:accepted-s02"] = heldout_text
    source_categories["heldout:accepted-s02"] = "heldout-reference"
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "record_type": "ComposedPairedRealization",
        "version": COMPOSED_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target_path": str(target_path.relative_to(project_root)),
        "target_hash": hash_json(target),
        "canonical_path": str(canonical_path.relative_to(project_root)),
        "canonical_hash": sha256_text(canonical),
        "opening_runway": {
            "text": COMPOSED_OPENING_RUNWAY,
            "sha256": sha256_text(COMPOSED_OPENING_RUNWAY),
            "words": word_count(COMPOSED_OPENING_RUNWAY),
            "provenance": "deterministic backtranslation of locked current state; not model output",
        },
        "segments": [asdict(item) for item in SEGMENTS],
        "deterministic_segment_runways": {
            segment_id: {
                "text": text,
                "sha256": sha256_text(text),
                "words": word_count(text),
                "provenance": "deterministic concrete backtranslation of the local event coordinates",
            }
            for segment_id, text in SEGMENT_RUNWAYS.items()
        },
        "seeds": list(seeds),
        "attempts_per_segment": attempts_per_segment,
        "maximum_new_tokens": maximum_new_tokens,
        "slot_id": slot_id,
        "stop_after_segments": stop_after_segments,
        "archive_case_count": archive_case_count,
        "demonstration_profile": demonstration_profile,
        "promoted_parent": promotion_provenance,
        "collect_next_segment_pool": collect_next_segment_pool,
        "stable_reference_prefix": {
            "source_arm_id": reference_arm_id,
            "source_prompt_path": str(reference_path.relative_to(project_root)),
            "source_prompt_hash": reference_arm["prompt_hash"],
            "prefix_hash": sha256_text(stable_reference_prefix),
            "policy": "selected paired-ledger exemplars followed immediately by the target ledger and live runway",
        },
        "selection": "first hard-gate passing attempt per segment; no literary score",
    }
    write_json(run_dir / "experiment_manifest.v1.json", manifest)
    manuscript = "CHAPTER TWO\n\n" + COMPOSED_OPENING_RUNWAY
    selected_segments: list[str] = []
    calls_path = run_dir / "calls.jsonl"
    terminal = _terminal_calls(calls_path)
    seed_index = 0
    for spec in SEGMENTS:
        selected_path = run_dir / "selected" / f"{spec.segment_id}.md"
        if spec.segment_id in promoted_segments:
            promoted = promoted_segments[spec.segment_id]
            if selected_path.is_file() and selected_path.read_text(encoding="utf-8") != promoted:
                raise ValueError(f"selected file conflicts with promoted parent: {spec.segment_id}")
            atomic_write_text(selected_path, promoted)
        if selected_path.is_file():
            selected = selected_path.read_text(encoding="utf-8")
            selected_segments.append(selected)
            manuscript += "\n\n" + selected
            seed_index += attempts_per_segment
            continue
        prompt = build_segment_prompt(
            target=target,
            spec=spec,
            demonstrations=demonstrations,
            manuscript_so_far=(
                manuscript
                + (
                    "\n\n" + SEGMENT_RUNWAYS[spec.segment_id]
                    if spec.segment_id in SEGMENT_RUNWAYS
                    else ""
                )
            ),
            stable_reference_prefix=stable_reference_prefix,
            target_case_number=archive_case_count + 1,
        )
        prompt_path = run_dir / "prompts" / f"{spec.segment_id}.txt"
        atomic_write_text(prompt_path, prompt)
        prompt_tokens = client.token_count(prompt)
        passed: str | None = None
        pool_candidates: list[dict[str, Any]] = []
        for attempt in range(attempts_per_segment):
            seed = int(seeds[seed_index + attempt])
            call_id = f"{spec.segment_id}:{seed}"
            prior = terminal.get(call_id)
            if prior is not None:
                if prior.get("status") == "completed" and prior.get("candidate_path"):
                    prior_text = (
                        project_root / str(prior["candidate_path"])
                    ).read_text(encoding="utf-8")
                    if segment_gate(spec.segment_id, prior_text)["eligible"]:
                        if collect_next_segment_pool:
                            pool_candidates.append(
                                {
                                    "seed": seed,
                                    "candidate_path": prior["candidate_path"],
                                    "candidate_hash": prior["candidate_hash"],
                                    "candidate_words": prior["candidate_words"],
                                }
                            )
                            continue
                        passed = prior_text
                        atomic_write_text(selected_path, prior_text)
                        break
                continue
            started = {
                "record_type": "ComposedSegmentCall",
                "version": COMPOSED_VERSION,
                "call_id": call_id,
                "status": "started",
                "segment_id": spec.segment_id,
                "seed": seed,
                "prompt_hash": sha256_text(prompt),
                "prompt_tokens": prompt_tokens,
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
            _append_jsonl(calls_path, started)
            anti_copy = build_segment_anti_copy_index(
                source_docs, source_categories
            )
            raw_path = run_dir / "raw" / f"{spec.segment_id}.{seed}.txt"
            raw: str | None = None
            completion = None
            try:
                guard = StreamingNgramGuard(anti_copy)
                lease = (
                    admission.acquire(
                        owner=f"composed:{call_id}",
                        prompt_hash=sha256_text(prompt),
                        prompt_tokens=prompt_tokens,
                        completion_tokens=maximum_new_tokens,
                    )
                    if admission is not None
                    else None
                )
                if lease is None:
                    completion = client.stream_raw(
                        prompt=prompt,
                        seed=seed,
                        max_tokens=maximum_new_tokens,
                        on_delta=guard.feed,
                        temperature=0.95,
                        top_p=0.97,
                        min_p=0.02,
                        xtc_probability=0.08,
                        stop=("\n#", "\n<"),
                        extra={"id_slot": slot_id} if slot_id is not None else None,
                    )
                else:
                    with lease:
                        completion = client.stream_raw(
                            prompt=prompt,
                            seed=seed,
                            max_tokens=maximum_new_tokens,
                            on_delta=guard.feed,
                            temperature=0.95,
                            top_p=0.97,
                            min_p=0.02,
                            xtc_probability=0.08,
                            stop=("\n#", "\n<"),
                            extra={"id_slot": slot_id}
                            if slot_id is not None
                            else None,
                        )
                raw = clean_generated_prose(completion.content)
                atomic_write_text(raw_path, raw)
                deterministic_runway = SEGMENT_RUNWAYS.get(spec.segment_id, "")
                candidate_source = (
                    deterministic_runway + "\n\n" + raw
                    if deterministic_runway
                    else raw
                )
                segment, gate = extract_gated_segment(candidate_source, spec)
                repetition = self_repetition_report(segment)
                if repetition["hard_fail"] or not gate["eligible"]:
                    raise ValueError(
                        f"segment gate failed: repetition={repetition['hard_fail']} gate={gate}"
                    )
                candidate_path = (
                    run_dir / "candidates" / f"{spec.segment_id}.{seed}.md"
                )
                atomic_write_text(candidate_path, segment)
                record = {
                    **started,
                    "status": "completed",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "candidate_path": str(candidate_path.relative_to(project_root)),
                    "candidate_hash": sha256_text(segment),
                    "candidate_words": word_count(segment),
                    "raw_path": str(raw_path.relative_to(project_root)),
                    "raw_hash": sha256_text(raw),
                    "raw_words": word_count(raw),
                    "deterministic_runway_hash": (
                        sha256_text(deterministic_runway)
                        if deterministic_runway
                        else None
                    ),
                    "gate": gate,
                    "self_repetition": repetition,
                    "finish_reason": completion.finish_reason,
                    "elapsed_seconds": completion.elapsed_seconds,
                    "usage": completion.usage,
                    "timings": completion.timings,
                    "cache": completion.cache,
                }
                _append_jsonl(calls_path, record)
                terminal[call_id] = record
                if collect_next_segment_pool:
                    pool_candidates.append(
                        {
                            "seed": seed,
                            "candidate_path": record["candidate_path"],
                            "candidate_hash": record["candidate_hash"],
                            "candidate_words": record["candidate_words"],
                        }
                    )
                    continue
                passed = segment
                atomic_write_text(selected_path, segment)
                break
            except Exception as exc:
                record = {
                    **started,
                    "status": "failed",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "error": f"{type(exc).__name__}: {exc}",
                }
                if raw is not None:
                    record["raw_path"] = str(raw_path.relative_to(project_root))
                    record["raw_hash"] = sha256_text(raw)
                    record["raw_words"] = word_count(raw)
                if completion is not None:
                    record["finish_reason"] = completion.finish_reason
                    record["elapsed_seconds"] = completion.elapsed_seconds
                    record["usage"] = completion.usage
                    record["timings"] = completion.timings
                    record["cache"] = completion.cache
                _append_jsonl(calls_path, record)
                terminal[call_id] = record
        seed_index += attempts_per_segment
        if collect_next_segment_pool:
            pool = {
                "record_type": "ComposedSegmentCandidatePool",
                "version": COMPOSED_VERSION,
                "segment_id": spec.segment_id,
                "parent_segment_hashes": [sha256_text(item) for item in selected_segments],
                "attempts": attempts_per_segment,
                "eligible_count": len(pool_candidates),
                "candidates": pool_candidates,
                "selection_status": "pending independent literary review",
            }
            write_json(run_dir / f"{spec.segment_id}_pool.v1.json", pool)
            return pool
        if passed is None:
            raise RuntimeError(f"no passing composed segment: {spec.segment_id}")
        selected_segments.append(passed)
        manuscript += "\n\n" + passed
        if stop_after_segments is not None and len(selected_segments) >= stop_after_segments:
            checkpoint = {
                "record_type": "ComposedPairedCheckpoint",
                "version": COMPOSED_VERSION,
                "completed_segments": [item.segment_id for item in SEGMENTS[: len(selected_segments)]],
                "selected_segment_hashes": [sha256_text(item) for item in selected_segments],
                "manuscript_hash": sha256_text(manuscript),
                "next_segment": (
                    SEGMENTS[len(selected_segments)].segment_id
                    if len(selected_segments) < len(SEGMENTS)
                    else None
                ),
            }
            write_json(run_dir / "checkpoint.v1.json", checkpoint)
            return checkpoint
    composed = COMPOSED_OPENING_RUNWAY + "\n\n" + "\n\n".join(selected_segments)
    final_atoms = _target_atom_diagnostics(composed)
    final_repetition = self_repetition_report(composed)
    total_words = word_count(composed)
    final_gate = {
        "words": total_words,
        "word_band": 875 <= total_words <= 1_100,
        "target_coverage": final_atoms["coverage"],
        "all_target_atoms": final_atoms["coverage"] == 1.0,
        "forbidden_future": final_atoms["forbidden_future"],
        "self_repetition": final_repetition,
    }
    final_gate["eligible"] = bool(
        final_gate["word_band"]
        and final_gate["all_target_atoms"]
        and not final_gate["forbidden_future"]
        and not final_repetition["hard_fail"]
    )
    final_path = run_dir / "composed" / "s02-seq1.md"
    atomic_write_text(final_path, composed)
    result = {
        "record_type": "ComposedPairedResult",
        "version": COMPOSED_VERSION,
        "candidate_path": str(final_path.relative_to(project_root)),
        "candidate_hash": sha256_text(composed),
        "gate": final_gate,
    }
    write_json(run_dir / "composed_result.v1.json", result)
    return result
