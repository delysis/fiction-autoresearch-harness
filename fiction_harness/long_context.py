"""Long-context calibration for native base-model fiction continuation.

The ordinary author-conditioning workflow is deliberately compact.  This
module tests the separate question of whether a large base checkpoint benefits
from a substantial, cache-stable archive of demonstrations and craft evidence.
It keeps one story program, manuscript runway, sampler, and seed set fixed while
varying only context dose and evidence layout.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from .anti_copy import AntiCopyIndex, SourceOverlapError, StreamingNgramGuard
from .continuation import clean_generated_prose, packet_leakage_markers
from .core import atomic_write_text, hash_json, sha256_text, write_json
from .evaluation import diversity_report, literary_style_diagnostics, word_count
from .model_client import LlamaClient
from .runtime import TraceStore, model_runtime_provenance, utc_now
from .shared_endpoint import SharedEndpointAdmission


WORD_RE = re.compile(r"\b[\w’'-]+\b", re.UNICODE)
EXPERIMENT_VERSION = "long-context.base31.v5"

# These are transport boundaries, not story instructions. Earlier prompts used
# XML around preparation and the base model sometimes answered with an invented
# empty closing element instead of prose. Keep all preparation in a closed,
# non-XML notebook section and let the final runway be ordinary manuscript.
BASE_OUTPUT_STOP_SEQUENCES = (
    "\n# SOURCE MATERIAL",
    "\n# FICTION CONTINUATION",
    "\n# NOVELIST",
    "<fiction-preparation>",
)
MIN_CHECKPOINT_WORDS = 650
SELF_REPEAT_WINDOW_WORDS = 50


S03_CHECKPOINT_PROGRAM = {
    "scene_id": "S03",
    "title": "The Alignment Vigil — opening movement",
    "pov": "Close third-person Mara only.",
    "time_and_place": (
        "An overnight Fulcrum alignment vigil in the glass chapel-lab while "
        "wildfire smoke turns the moon orange."
    ),
    "opening_offer": (
        "The vigil begins with real beauty, technical urgency, and shared "
        "devotion to keeping a world-saving infrastructure project alive."
    ),
    "causal_program": (
        "Two teams receive opposite expectations about the same synchronized "
        "exercise. Their expectations cause them to notice incompatible threat "
        "patterns. Mara first observes the divergence through exact words, "
        "timestamps, bodily actions, and instrumentation rather than choosing "
        "an explanation. Livia makes one genuinely impressive read and is "
        "briefly elevated as the strongest interpreter. A shared image or phrase "
        "then appears across participants and becomes newly important."
    ),
    "relationship_state": (
        "Mara and Jonah have shared one mutually wanted doorway kiss that they "
        "stopped while it was still desired. His restraint attracts her, but he "
        "remains implicated in Fulcrum and is not a moral oracle."
    ),
    "local_endpoint": (
        "Stop shortly after the shared image or phrase is established as a "
        "dangerous object of attention, before accusation, lockdown, confession, "
        "institutional reform, or metaphysical resolution."
    ),
    "intimacy": (
        "Attraction changes attention and trust through particular action. This "
        "checkpoint contains no consummation and no second kiss."
    ),
    "epistemic_constraint": (
        "Keep ordinary, technical, psychological, and supernatural explanations "
        "live. Accurate observation does not license an interpretation."
    ),
    "target_words": "850-1150",
}


S03_OPENING_FRAGMENT = (
    "By midnight, the wildfire had turned the moon above Fulcrum's glass chapel "
    "the color of a banked coal."
)


@dataclass(frozen=True, slots=True)
class LongContextArm:
    arm_id: str
    target_prompt_words: int
    evidence_variant: str
    layout: str
    control_density: str

    def __post_init__(self) -> None:
        if self.target_prompt_words < 4_000:
            raise ValueError("long-context arms require at least 4,000 prompt words")
        if self.evidence_variant not in {"none", "distilled", "full-guide"}:
            raise ValueError(f"unknown evidence variant: {self.evidence_variant}")
        if self.layout not in {"evidence-first", "contract-first"}:
            raise ValueError(f"unknown evidence layout: {self.layout}")
        if self.control_density not in {"organic", "full"}:
            raise ValueError(f"unknown control density: {self.control_density}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_ARMS = (
    LongContextArm("lc08-contract", 8_000, "none", "contract-first", "full"),
    LongContextArm("lc24-distilled", 24_000, "distilled", "evidence-first", "full"),
    LongContextArm("lc64-guide-early", 64_000, "full-guide", "evidence-first", "full"),
    LongContextArm("lc64-guide-late", 64_000, "full-guide", "contract-first", "full"),
    LongContextArm("lc64-organic", 64_000, "full-guide", "evidence-first", "organic"),
)


@dataclass(frozen=True, slots=True)
class CompiledLongContext:
    arm: LongContextArm
    prompt: str
    component_hashes: Mapping[str, str]
    component_words: Mapping[str, int]
    manuscript_hash: str
    program_hash: str

    @property
    def prompt_hash(self) -> str:
        return sha256_text(self.prompt)

    @property
    def prompt_words(self) -> int:
        return word_count(self.prompt)

    def manifest(self) -> dict[str, Any]:
        return {
            "record_type": "LongContextPrompt",
            "version": EXPERIMENT_VERSION,
            "arm": self.arm.to_dict(),
            "prompt_hash": self.prompt_hash,
            "prompt_words": self.prompt_words,
            "component_hashes": dict(self.component_hashes),
            "component_words": dict(self.component_words),
            "manuscript_hash": self.manuscript_hash,
            "program_hash": self.program_hash,
        }


def _paragraphs(text: str) -> tuple[str, ...]:
    return tuple(
        item.strip()
        for item in re.split(r"\n\s*\n", text.replace("\r\n", "\n"))
        if item.strip()
    )


def _without_quoted_examples(text: str) -> str:
    """Keep Gabaldon's craft discussion while removing quoted novel passages."""

    lines = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(">"):
            continue
        if re.match(r"^Example\s*\(", stripped, flags=re.IGNORECASE):
            continue
        lines.append(line)
    return "\n".join(lines)


def _take_words(text: str, maximum_words: int) -> str:
    """Truncate only at paragraph boundaries for deterministic evidence doses."""

    if maximum_words <= 0:
        return ""
    selected: list[str] = []
    used = 0
    for paragraph in _paragraphs(text):
        count = word_count(paragraph)
        if selected and used + count > maximum_words:
            break
        if not selected and count > maximum_words:
            words = paragraph.split()
            return " ".join(words[:maximum_words])
        selected.append(paragraph)
        used += count
    return "\n\n".join(selected)


def _contract_document(*, organic: bool) -> str:
    if organic:
        return (
            "# STORY CONTINUITY\n\n"
            "This is a contemporary Christian romantic-suspense story about "
            "Mara Vale at Fulcrum. Desire sharpens perception without deciding "
            "truth. Freedom, accurate witness, costly restraint, and concrete "
            "consequences carry the moral action. Other minds remain inferred "
            "from observable behavior.\n\n"
            "# PRESENT STORY MOVEMENT\n\n"
            + "\n".join(f"{key}: {value}" for key, value in S03_CHECKPOINT_PROGRAM.items())
        )
    return (
        "# LOCKED FICTION CONTRACT\n\n"
        "The following coordinates govern the continuation. They are preparation "
        "notes, not language to repeat or explain in the manuscript.\n\n"
        + "\n".join(f"{key.upper()}: {value}" for key, value in S03_CHECKPOINT_PROGRAM.items())
        + "\n\n# PROSE TRANSFER RULES\n\n"
        "Enact causality through dialogue, physical action, selective sensation, "
        "and changed choices. Keep Livia caring, funny, skilled, acquisitive, and "
        "capable of being hurt. Keep Jonah attractive because restraint costs him "
        "something, not because narration certifies him as good. Let prayer alter "
        "attention or action rather than supply serenity or a detachable sermon. "
        "Do not explain a legible action in the following sentence."
    )


def _evidence_document(
    *,
    arm: LongContextArm,
    guide_text: str,
    craft_distillation: str,
    available_words: int,
) -> str:
    if arm.evidence_variant == "none" or available_words <= 0:
        return ""
    header = (
        "# LOCAL CRAFT ARCHIVE\n\n"
        "The archive below is evidence about how intimate and romantic fiction "
        "works. Its plots, names, period dialect, explicit acts, and wording do "
        "not belong to the manuscript. Transfer mechanisms: character-specific "
        "emotional exchange; dialogue joined to body language; selective sensory "
        "logistics; atmosphere; narrative distance; interruption; restraint; and "
        "contact that changes the available choice.\n\n"
    )
    if arm.evidence_variant == "distilled":
        body = craft_distillation + "\n\n" + _without_quoted_examples(guide_text)
    else:
        body = guide_text
    return header + _take_words(body, max(0, available_words - word_count(header)))


def compile_long_context(
    arm: LongContextArm,
    *,
    manuscript: str,
    guide_text: str,
    craft_distillation: str,
) -> CompiledLongContext:
    manuscript = manuscript.strip()
    if not manuscript:
        raise ValueError("approved manuscript runway cannot be empty")
    contract = _contract_document(organic=arm.control_density == "organic")
    manuscript_block = (
        "# APPROVED MANUSCRIPT\n\n"
        + manuscript
        + "\n\n* * *\n\n"
        + S03_OPENING_FRAGMENT
    )
    fixed_words = word_count(contract) + word_count(manuscript_block) + 80
    evidence = _evidence_document(
        arm=arm,
        guide_text=guide_text,
        craft_distillation=craft_distillation,
        available_words=max(0, arm.target_prompt_words - fixed_words),
    )
    preamble = (
        "This local working file precedes a manuscript continuation. Source "
        "passages are research, not continuable text. The final section is the "
        "only manuscript runway. The new passage owns every sentence and carries "
        "the present story movement to its local endpoint."
    )
    research_section = "RESEARCH ARCHIVE\n\n" + evidence
    contract_section = "STORY CONTRACT\n\n" + contract
    ordered_sections = (
        (research_section, contract_section)
        if arm.layout == "evidence-first"
        else (contract_section, research_section)
    )
    preparation = (
        "===== FICTION PREPARATION NOTEBOOK =====\n\n"
        + preamble
        + "\n\n"
        + "\n\n".join(ordered_sections)
        + "\n\n===== END FICTION PREPARATION NOTEBOOK ====="
    )
    prompt = (
        preparation
        + "\n\n"
        + manuscript_block.removeprefix("# APPROVED MANUSCRIPT\n\n").rstrip()
        + "\n"
    )
    components = {
        "preamble": preparation,
        "contract": contract,
        "evidence": evidence,
        "manuscript": manuscript_block,
    }
    return CompiledLongContext(
        arm=arm,
        prompt=prompt,
        component_hashes={key: sha256_text(value) for key, value in components.items()},
        component_words={key: word_count(value) for key, value in components.items()},
        manuscript_hash=sha256_text(manuscript),
        program_hash=hash_json(S03_CHECKPOINT_PROGRAM),
    )


def compile_experiment(
    *,
    run_root: str | Path,
    manuscript_path: str | Path,
    guide_path: str | Path,
    craft_distillation_path: str | Path,
    arms: Sequence[LongContextArm] = DEFAULT_ARMS,
) -> dict[str, Any]:
    run_root = Path(run_root)
    prompts = run_root / "prompts"
    prompts.mkdir(parents=True, exist_ok=True)
    manuscript = Path(manuscript_path).read_text(encoding="utf-8")
    guide = Path(guide_path).read_text(encoding="utf-8")
    craft = Path(craft_distillation_path).read_text(encoding="utf-8")
    records = []
    for arm in arms:
        compiled = compile_long_context(
            arm,
            manuscript=manuscript,
            guide_text=guide,
            craft_distillation=craft,
        )
        prompt_path = prompts / f"{arm.arm_id}.prompt.txt"
        atomic_write_text(prompt_path, compiled.prompt)
        manifest = {**compiled.manifest(), "prompt_path": str(prompt_path)}
        write_json(prompts / f"{arm.arm_id}.manifest.json", manifest)
        records.append(manifest)
    payload = {
        "record_type": "LongContextExperimentManifest",
        "version": EXPERIMENT_VERSION,
        "story_program": S03_CHECKPOINT_PROGRAM,
        "story_program_hash": hash_json(S03_CHECKPOINT_PROGRAM),
        "manuscript_path": str(Path(manuscript_path)),
        "manuscript_hash": sha256_text(manuscript.strip()),
        "guide_path": str(Path(guide_path)),
        "guide_hash": sha256_text(guide),
        "craft_distillation_path": str(Path(craft_distillation_path)),
        "craft_distillation_hash": sha256_text(craft),
        "arms": records,
    }
    payload["manifest_hash"] = hash_json(payload)
    write_json(run_root / "experiment_manifest.v1.json", payload)
    return payload


def build_long_context_anti_copy_index(
    *, manuscript: str, guide_text: str, extra_sources: Mapping[str, str] | None = None
) -> AntiCopyIndex:
    documents = {
        "approved-manuscript-runway": manuscript,
        "gabaldon-local-craft-guide": guide_text,
        **dict(extra_sources or {}),
    }
    return AntiCopyIndex(
        documents,
        categories={
            "approved-manuscript-runway": "project-exemplar",
            "gabaldon-local-craft-guide": "author-corpus",
            **{key: "prompt-exemplar" for key in (extra_sources or {})},
        },
    )


def self_repetition_report(text: str) -> dict[str, Any]:
    """Detect base-model loops without treating ordinary motifs as copying."""

    normalized_words = [
        match.group(0).casefold().replace("’", "'")
        for match in WORD_RE.finditer(text)
    ]
    seen_windows: dict[tuple[str, ...], int] = {}
    duplicate_windows: list[dict[str, int]] = []
    for start in range(
        max(0, len(normalized_words) - SELF_REPEAT_WINDOW_WORDS + 1)
    ):
        window = tuple(normalized_words[start : start + SELF_REPEAT_WINDOW_WORDS])
        prior = seen_windows.get(window)
        if prior is None:
            seen_windows[window] = start
        elif start - prior >= SELF_REPEAT_WINDOW_WORDS:
            duplicate_windows.append({"first_word": prior, "repeat_word": start})

    paragraph_positions: dict[str, int] = {}
    duplicate_paragraphs: list[dict[str, int]] = []
    for index, paragraph in enumerate(_paragraphs(text)):
        if word_count(paragraph) < 20:
            continue
        normalized = " ".join(
            match.group(0).casefold().replace("’", "'")
            for match in WORD_RE.finditer(paragraph)
        )
        prior = paragraph_positions.get(normalized)
        if prior is None:
            paragraph_positions[normalized] = index
        else:
            duplicate_paragraphs.append(
                {"first_paragraph": prior, "repeat_paragraph": index}
            )
    return {
        "hard_fail": bool(duplicate_windows or duplicate_paragraphs),
        "window_words": SELF_REPEAT_WINDOW_WORDS,
        "duplicate_window_count": len(duplicate_windows),
        "duplicate_windows": duplicate_windows[:20],
        "duplicate_paragraph_count": len(duplicate_paragraphs),
        "duplicate_paragraphs": duplicate_paragraphs[:20],
    }


def run_experiment(
    *,
    client: LlamaClient,
    run_root: str | Path,
    seeds: Sequence[int],
    anti_copy_index: AntiCopyIndex,
    max_tokens: int = 1_700,
    arm_ids: Sequence[str] | None = None,
    max_new_candidates: int | None = None,
    max_retries: int = 2,
    admission: SharedEndpointAdmission | None = None,
    prompt_token_counts: Mapping[str, int] | None = None,
) -> tuple[dict[str, Any], ...]:
    run_root = Path(run_root)
    manifest = __import__("json").loads(
        (run_root / "experiment_manifest.v1.json").read_text(encoding="utf-8")
    )
    store = TraceStore(run_root)
    candidate_dir = run_root / "candidates"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[dict[str, Any]] = []
    allowed_arms = set(arm_ids or ())
    newly_committed = 0
    committed = {
        str(record.get("candidate_id")): record
        for record in TraceStore.read(store.candidates_path)
        if record.get("record_type") == "LongContextCandidate"
    }
    for arm_record in manifest["arms"]:
        arm_id = str(arm_record["arm"]["arm_id"])
        if allowed_arms and arm_id not in allowed_arms:
            continue
        prompt_path = Path(arm_record["prompt_path"])
        prompt = prompt_path.read_text(encoding="utf-8")
        if sha256_text(prompt) != arm_record["prompt_hash"]:
            raise ValueError(f"prompt bytes changed for {arm_id}")
        declared_prompt_tokens: int | None = None
        if admission is not None:
            supplied = (prompt_token_counts or {}).get(arm_id)
            declared_prompt_tokens = (
                int(supplied) if supplied is not None else client.token_count(prompt)
            )
            if declared_prompt_tokens < 1:
                raise ValueError(f"invalid prompt-token declaration for {arm_id}")
        for seed in seeds:
            candidate_id = f"{arm_id}.seed-{seed}"
            if candidate_id in committed:
                outputs.append(dict(committed[candidate_id]))
                continue
            call_id = f"long-context:{candidate_id}"
            prior = store.completed_call(call_id)
            if prior:
                result = dict(prior["result"])
                actual_seed = int(prior.get("seed", seed))
            else:
                failed = sum(
                    record.get("call_id") == call_id
                    and record.get("status")
                    in {"rejected_source_overlap", "rejected_generation_shape"}
                    for record in TraceStore.read(store.calls_path)
                )
                result = {}
                actual_seed = int(seed)
                for retry in range(failed, max_retries + 1):
                    actual_seed = int(seed) + retry * 100_003
                    base = {
                        "call_id": call_id,
                        "attempt_index": retry + 1,
                        "stage": "long_context_base_prose",
                        "status": "started",
                        "arm_id": arm_id,
                        "seed": actual_seed,
                        "declared_seed": int(seed),
                        "prompt_hash": arm_record["prompt_hash"],
                        "experiment_manifest_hash": manifest["manifest_hash"],
                        "anti_copy_index_hash": anti_copy_index.index_hash,
                        "runtime": model_runtime_provenance(client.model),
                        "parameters": {
                            "temperature": 0.9,
                            "top_p": 0.95,
                            "min_p": 0.02,
                            "xtc_probability": 0.05,
                            "max_tokens": max_tokens,
                        },
                        "admission": {
                            "enabled": admission is not None,
                            "prompt_tokens": declared_prompt_tokens,
                            "completion_tokens": max_tokens,
                            "declared_total_tokens": (
                                declared_prompt_tokens + max_tokens
                                if declared_prompt_tokens is not None
                                else None
                            ),
                        },
                        "started_at": utc_now(),
                    }
                    store.append_call(base)
                    guard = StreamingNgramGuard(anti_copy_index)
                    try:
                        lease_context = (
                            admission.acquire(
                                owner=f"long-context:{candidate_id}:attempt-{retry + 1}",
                                prompt_hash=str(arm_record["prompt_hash"]),
                                prompt_tokens=int(declared_prompt_tokens),
                                completion_tokens=max_tokens,
                            )
                            if admission is not None
                            else None
                        )
                        if lease_context is None:
                            completion = client.stream_raw(
                                prompt=prompt,
                                seed=actual_seed,
                                max_tokens=max_tokens,
                                temperature=0.9,
                                top_p=0.95,
                                min_p=0.02,
                                xtc_probability=0.05,
                                on_delta=guard.feed,
                                stop=BASE_OUTPUT_STOP_SEQUENCES,
                            )
                        else:
                            with lease_context:
                                completion = client.stream_raw(
                                    prompt=prompt,
                                    seed=actual_seed,
                                    max_tokens=max_tokens,
                                    temperature=0.9,
                                    top_p=0.95,
                                    min_p=0.02,
                                    xtc_probability=0.05,
                                    on_delta=guard.feed,
                                    stop=BASE_OUTPUT_STOP_SEQUENCES,
                                )
                    except SourceOverlapError as exc:
                        store.append_call(
                            {
                                **base,
                                "status": "rejected_source_overlap",
                                "match": exc.match,
                                "finished_at": utc_now(),
                            }
                        )
                        continue
                    trial_result = completion.to_dict()
                    trial_result.pop("raw", None)
                    trial_prose = clean_generated_prose(
                        str(trial_result.get("content", ""))
                    )
                    shape_defects: list[str] = []
                    if word_count(trial_prose) < MIN_CHECKPOINT_WORDS:
                        shape_defects.append(
                            f"under_minimum_words:{word_count(trial_prose)}"
                        )
                    leakage = packet_leakage_markers(trial_prose)
                    if leakage:
                        shape_defects.extend(f"packet_leakage:{item}" for item in leakage)
                    self_repeat = self_repetition_report(trial_prose)
                    if self_repeat["hard_fail"]:
                        shape_defects.append(
                            "self_repetition:"
                            f"{self_repeat['duplicate_window_count']}-windows,"
                            f"{self_repeat['duplicate_paragraph_count']}-paragraphs"
                        )
                    if shape_defects:
                        store.append_call(
                            {
                                **base,
                                "status": "rejected_generation_shape",
                                "defects": shape_defects,
                                "result": trial_result,
                                "finished_at": utc_now(),
                            }
                        )
                        continue
                    result = trial_result
                    store.append_call(
                        {
                            **base,
                            "status": "completed",
                            "result": result,
                            "finished_at": utc_now(),
                        }
                    )
                    break
                if not result:
                    continue
            prose = clean_generated_prose(str(result.get("content", "")))
            overlap = anti_copy_index.check(candidate_id, prose)
            record = {
                "record_type": "LongContextCandidate",
                "version": EXPERIMENT_VERSION,
                "candidate_id": candidate_id,
                "arm_id": arm_id,
                "seed": actual_seed,
                "declared_seed": int(seed),
                "text": prose,
                "text_hash": sha256_text(prose),
                "word_count": word_count(prose),
                "prompt_hash": arm_record["prompt_hash"],
                "prompt_words": arm_record["prompt_words"],
                "program_hash": manifest["story_program_hash"],
                "manuscript_hash": manifest["manuscript_hash"],
                "anti_copy_index_hash": anti_copy_index.index_hash,
                "overlap_report": overlap.to_dict(),
                "telemetry": result,
            }
            TraceStore._append(store.candidates_path, record)
            atomic_write_text(candidate_dir / f"{candidate_id}.md", prose.rstrip() + "\n")
            outputs.append(record)
            newly_committed += 1
            if (
                max_new_candidates is not None
                and newly_committed >= max_new_candidates
            ):
                return tuple(outputs)
    return tuple(outputs)


def _s03_checkpoint_diagnostics(text: str) -> dict[str, Any]:
    folded = text.casefold()
    checks = {
        "mara_present": bool(re.search(r"\bmara\b", folded)),
        "livia_present": bool(re.search(r"\blivia\b", folded)),
        "wildfire_or_orange_moon": bool(re.search(r"\b(?:wildfire|orange moon|banked coal)\b", folded)),
        "opposed_expectations": bool(re.search(r"\b(?:opposite|different|incompatible|two teams|both teams)\b", folded)),
        "shared_image_or_phrase": bool(re.search(r"\b(?:shared|same)\b.{0,90}\b(?:image|phrase|word|words)\b", folded)),
        "no_confirmed_paranormal": not bool(re.search(r"\b(?:proved|confirmed|undeniably)\b.{0,60}\b(?:demon|supernatural|miracle|psychic)\b", folded)),
        "no_final_resolution": not bool(re.search(r"\b(?:institution had changed forever|fulcrum was reformed|mystery was solved)\b", folded)),
        "close_third_no_obvious_head_hop": not bool(re.search(r"\b(?:jonah|livia|miriam)\b(?:\s+\w+){0,3}\s+(?:thought|knew|realized|remembered|wanted)\b", text, flags=re.IGNORECASE)),
    }
    return {
        "checks": checks,
        "passed_count": sum(checks.values()),
        "check_count": len(checks),
        "packet_leakage_markers": list(packet_leakage_markers(text)),
        "natural_stop": bool(re.search(r"[.!?][\"”’')\]]*\s*$", text.rstrip())),
    }


def evaluate_experiment(*, run_root: str | Path) -> dict[str, Any]:
    run_root = Path(run_root)
    calls = TraceStore.read(run_root / "calls.jsonl")
    records = [
        item
        for item in TraceStore.read(run_root / "candidates.jsonl")
        if item.get("record_type") == "LongContextCandidate"
    ]
    latest = {str(item["candidate_id"]): item for item in records}
    reports = []
    for candidate_id, record in sorted(latest.items()):
        text = str(record["text"])
        checkpoint = _s03_checkpoint_diagnostics(text)
        self_repeat = self_repetition_report(text)
        overlap = record["overlap_report"]
        eligible = (
            650 <= word_count(text) <= 1_300
            and checkpoint["passed_count"] == checkpoint["check_count"]
            and checkpoint["natural_stop"]
            and not checkpoint["packet_leakage_markers"]
            and not self_repeat["hard_fail"]
            and not overlap["hard_fail"]
            and not overlap["unresolved_flags"]
        )
        reports.append(
            {
                "candidate_id": candidate_id,
                "arm_id": record["arm_id"],
                "seed": record["seed"],
                "word_count": word_count(text),
                "eligible": eligible,
                "checkpoint": checkpoint,
                "self_repetition": self_repeat,
                "literary_style": literary_style_diagnostics(text),
                "anti_copy": overlap,
                "prompt_words": record["prompt_words"],
                "prompt_tokens": record.get("telemetry", {}).get("cache", {}).get("prompt_n"),
                "elapsed_seconds": record.get("telemetry", {}).get("elapsed_seconds"),
            }
        )
    diversity = diversity_report(
        [{"candidate_id": item["candidate_id"], "text": latest[item["candidate_id"]]["text"]} for item in reports]
    )
    attempt_counts: dict[str, int] = {}
    attempt_reports: list[dict[str, Any]] = []
    for call in calls:
        if call.get("stage") != "long_context_base_prose" or call.get("status") == "started":
            continue
        status = str(call.get("status", "unknown"))
        attempt_counts[status] = attempt_counts.get(status, 0) + 1
        result = call.get("result", {})
        content = str(result.get("content", "")) if isinstance(result, Mapping) else ""
        attempt_reports.append(
            {
                "call_id": call.get("call_id"),
                "arm_id": call.get("arm_id"),
                "attempt_index": call.get("attempt_index"),
                "seed": call.get("seed"),
                "status": status,
                "word_count": word_count(clean_generated_prose(content)),
                "defects": list(call.get("defects", ())),
                "source_match": call.get("match"),
                "finish_reason": result.get("finish_reason")
                if isinstance(result, Mapping)
                else None,
            }
        )
    payload = {
        "record_type": "LongContextCalibrationReport",
        "version": EXPERIMENT_VERSION,
        "candidate_count": len(reports),
        "attempt_count": len(attempt_reports),
        "attempt_status_counts": attempt_counts,
        "attempts": attempt_reports,
        "candidates": reports,
        "diversity": diversity,
    }
    write_json(run_root / "evaluation" / "calibration_report.v1.json", payload)
    return payload
