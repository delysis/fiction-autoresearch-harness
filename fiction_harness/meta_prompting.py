"""Long-context native-base prompt experiments for fiction realization.

The experiment treats prompting as empirical distribution construction.  A
base checkpoint sees either a short control dossier, a prose library, paired
scene-ledger-to-manuscript demonstrations, or the complete stack.  The target
story state and sampler seeds remain fixed across arms.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import fcntl
import json
import os
from pathlib import Path
import random
import re
from typing import Any, Iterable, Mapping, Sequence

from .anti_copy import AntiCopyIndex, AntiCopyPolicy, StreamingNgramGuard
from .continuation import clean_generated_prose, literary_style_diagnostics
from .core import atomic_write_text, hash_json, sha256_text, write_json
from .evaluation import word_count
from .model_client import LlamaClient
from .shared_endpoint import SharedEndpointAdmission


META_PROMPT_VERSION = "base-meta-prompt.v3"
DEFAULT_SEEDS = (881_003, 881_019, 881_041, 881_063)
OPENING_RUNWAY = (
    "Four nights after the calibration game, the alignment session had run "
    "twenty-three minutes past its promised end."
)


@dataclass(frozen=True, slots=True)
class Demonstration:
    demonstration_id: str
    ledger: str
    prose: str
    ledger_hash: str
    prose_hash: str
    provenance: Mapping[str, str]

    @classmethod
    def create(
        cls,
        demonstration_id: str,
        ledger: str,
        prose: str,
        provenance: Mapping[str, str],
    ) -> "Demonstration":
        return cls(
            demonstration_id=demonstration_id,
            ledger=ledger.strip(),
            prose=prose.strip(),
            ledger_hash=sha256_text(ledger.strip()),
            prose_hash=sha256_text(prose.strip()),
            provenance=dict(provenance),
        )


@dataclass(frozen=True, slots=True)
class PromptArm:
    arm_id: str
    family: str
    nominal_context_tokens: int
    prompt_path: str
    prompt_hash: str
    prompt_words: int
    demonstration_ids: tuple[str, ...]
    library_source_ids: tuple[str, ...]
    target_packet_hash: str
    canonical_prefix_hash: str


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def render_occurrence_ledger(packet: Mapping[str, Any]) -> str:
    """Render model-independent atoms as an editorial event ledger."""

    phases = packet.get("phases")
    if isinstance(phases, Sequence):
        groups = phases
    else:
        groups = (
            {
                "phase_id": str(
                    (packet.get("sequence") or {}).get("sequence_id", "scene")
                ),
                "occurrences": packet.get("occurrences", ()),
            },
        )
    lines: list[str] = []
    number = 0
    for group in groups:
        if not isinstance(group, Mapping):
            continue
        phase = str(group.get("phase_id", "scene")).replace("-", " ")
        lines.append(f"Phase: {phase}")
        for occurrence in group.get("occurrences", ()):
            if not isinstance(occurrence, Mapping):
                continue
            number += 1
            participants = ", ".join(
                str(item) for item in occurrence.get("participants", ())
            )
            lines.extend(
                (
                    f"{number}. Given: {occurrence.get('setup', '')}",
                    f"   Action ({participants}): {occurrence.get('move', '')}",
                    f"   Visible response: {occurrence.get('response', '')}",
                    "   What changes: "
                    + str(occurrence.get("constraint_change", "")),
                )
            )
    scene = packet.get("scene") or packet.get("sequence") or {}
    endpoint = scene.get("endpoint") if isinstance(scene, Mapping) else ""
    if endpoint:
        lines.append("Local stopping state: " + str(endpoint))
    return "\n".join(lines).strip()


def load_s01_demonstrations(project_root: Path) -> tuple[Demonstration, ...]:
    run_root = project_root / "03_scene_lab/runs/s01-atom-rewrite-v1"
    identities = (
        (
            "s01-gift-status",
            "s01-bundle-a-gift-status.novelist_packet.v1.json",
            "s01-a-gift-status.codex.v1.md",
        ),
        (
            "s01-somatic-control",
            "s01-bundle-b-somatic-control.novelist_packet.v1.json",
            "s01-b-somatic-control.codex.v1.md",
        ),
        (
            "s01-method-audit",
            "s01-bundle-c-method-audit.novelist_packet.v1.json",
            "s01-c-method-audit.codex.v1.md",
        ),
    )
    values: list[Demonstration] = []
    for demo_id, packet_name, candidate_name in identities:
        packet_path = run_root / "novelist_packets" / packet_name
        prose_path = run_root / "candidates" / candidate_name
        packet = _read_json(packet_path)
        values.append(
            Demonstration.create(
                demo_id,
                render_occurrence_ledger(packet),
                prose_path.read_text(encoding="utf-8"),
                {
                    "packet_path": str(packet_path.relative_to(project_root)),
                    "prose_path": str(prose_path.relative_to(project_root)),
                    "packet_hash": sha256_text(packet_path.read_text(encoding="utf-8")),
                    "prose_hash": sha256_text(prose_path.read_text(encoding="utf-8")),
                },
            )
        )
    return tuple(values)


def _gutenberg_body(text: str) -> str:
    start = re.search(r"\*\*\* START OF THE PROJECT GUTENBERG EBOOK.*?\*\*\*", text)
    end = re.search(r"\*\*\* END OF THE PROJECT GUTENBERG EBOOK.*?\*\*\*", text)
    left = start.end() if start else 0
    right = end.start() if end else len(text)
    return text[left:right].strip()


def _chapters(text: str) -> list[str]:
    body = _gutenberg_body(text)
    starts = list(re.finditer(r"(?m)^CHAPTER\s+[IVXLCDM]+\.?\s*$", body))
    if not starts:
        return [body]
    values: list[str] = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(body)
        chapter = body[match.start() : end].strip()
        if 500 <= word_count(chapter) <= 8_000:
            values.append(chapter)
    return values


def select_dialogue_rich_library(
    project_root: Path,
    *,
    maximum_words: int,
    seed: int = 7729,
) -> tuple[tuple[str, str], ...]:
    """Select complete public-domain chapters by dialogue/social-action density."""

    book_root = project_root / "fixtures/author_control/jane_austen/books"
    candidates: list[tuple[float, str, str]] = []
    terms = re.compile(
        r"\b(?:marry|marriage|love|attention|regard|refus|ask|answer|"
        r"embarrass|jealous|admire|dance|engag|promise|choice)\w*\b",
        re.IGNORECASE,
    )
    for path in sorted(book_root.glob("*.txt")):
        for index, chapter in enumerate(
            _chapters(path.read_text(encoding="utf-8", errors="replace")), 1
        ):
            words = max(1, word_count(chapter))
            dialogue = chapter.count('"') + chapter.count("“")
            social = len(terms.findall(chapter))
            score = (dialogue * 2.0 + social * 3.0) / words
            source_id = f"{path.stem}.chapter-{index:03d}"
            candidates.append((score, source_id, chapter))
    rng = random.Random(seed)
    rng.shuffle(candidates)
    candidates.sort(key=lambda item: item[0], reverse=True)
    selected: list[tuple[str, str]] = []
    total = 0
    for _, source_id, chapter in candidates:
        if total >= maximum_words:
            break
        remaining = maximum_words - total
        if word_count(chapter) > remaining and selected:
            continue
        selected.append((source_id, chapter))
        total += word_count(chapter)
    return tuple(selected)


def _story_bible(target: Mapping[str, Any]) -> str:
    invariants = target.get("character_invariants", {})
    lines = [
        "Series form: contemporary Christian romantic suspense.",
        "Narration: close third person through Mara; other minds remain inferred.",
        "World: ordinary and extraordinary explanations remain simultaneously live.",
        "Romance: adult monogamous slow burn; attraction sharpens freedom and perception.",
        "Scene boundary: no consummation, graphic anatomy, doorway kiss, or completed exit.",
    ]
    if isinstance(invariants, Mapping):
        for name, value in invariants.items():
            lines.append(f"{name}: {value}")
    return "\n".join(lines)


def _render_demonstrations(demos: Sequence[Demonstration]) -> str:
    sections = []
    for index, demo in enumerate(demos, 1):
        sections.append(
            f"CASE {index}: EDITORIAL EVENT LEDGER\n{demo.ledger}\n\n"
            f"CASE {index}: FINISHED MANUSCRIPT\n{demo.prose}\n\n"
            f"END CASE {index}"
        )
    return "\n\n".join(sections)


def _render_library(library: Sequence[tuple[str, str]]) -> str:
    return "\n\n".join(
        f"REFERENCE SCENE {index}\n{text.strip()}\nEND REFERENCE SCENE {index}"
        for index, (_, text) in enumerate(library, 1)
    )


def _target_contract(
    *,
    target: Mapping[str, Any],
    paired: bool,
) -> str:
    ledger = render_occurrence_ledger(target)
    bridge = (
        "The following editorial ledger precedes the manuscript because the "
        "preceding cases establish the ledger-to-prose convention. The ledger's "
        "events are enacted once; its explanatory wording does not enter the novel."
        if paired
        else "Editorial continuity and event notes for the next manuscript passage."
    )
    return (
        "TARGET STORY BIBLE\n"
        + _story_bible(target)
        + "\n\nTARGET EVENT LEDGER\n"
        + bridge
        + "\n"
        + ledger
    )


def _manuscript_runway(canonical_s01: str) -> str:
    return canonical_s01.strip() + "\n\nCHAPTER TWO\n\n" + OPENING_RUNWAY


def build_prompt(
    *,
    family: str,
    target: Mapping[str, Any],
    canonical_s01: str,
    demonstrations: Sequence[Demonstration],
    library: Sequence[tuple[str, str]],
) -> str:
    target_contract = _target_contract(
        target=target,
        paired=bool(demonstrations),
    )
    if family == "short-control":
        preparation = (
            "The following material is preparation, not manuscript prose.\n\n"
            + target_contract
        )
    elif family == "raw-prose-library":
        preparation = (
            "SOCIAL AND ROMANTIC FICTION REFERENCE LIBRARY\n\n"
            + _render_library(library)
            + "\n\nNEW PROJECT PREPARATION\n\n"
            + target_contract
        )
    elif family == "paired-icl":
        preparation = (
            "EDITORIAL APPRENTICESHIP ARCHIVE\n\n"
            + _render_demonstrations(demonstrations)
            + "\n\nNEW PROJECT PREPARATION\n\n"
            + target_contract
        )
    elif family == "full-stack":
        preparation = (
            "FICTION REFERENCE LIBRARY\n\n"
            + _render_library(library)
            + "\n\nEDITORIAL APPRENTICESHIP ARCHIVE\n\n"
            + _render_demonstrations(demonstrations)
            + "\n\nNEW PROJECT PREPARATION\n\n"
            + target_contract
        )
    else:
        raise ValueError(f"unknown prompt family: {family}")
    return (
        "<fiction-preparation>\n"
        + preparation
        + "\n</fiction-preparation>\n\n"
        + _manuscript_runway(canonical_s01)
    )


ARM_SPECS = (
    ("short-control-4k", "short-control", 4_000, 0),
    ("paired-icl-16k", "paired-icl", 16_000, 0),
    ("raw-prose-64k", "raw-prose-library", 64_000, 42_000),
    ("full-stack-64k", "full-stack", 64_000, 30_000),
    ("full-stack-128k", "full-stack", 128_000, 78_000),
)


def compile_meta_prompt_experiment(
    project_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    target_path = (
        project_root
        / "03_scene_lab/runs/s02-compute-v4.3-a4b/verbalized_to_instruction"
        / "novelist_packet.seq1.v1.json"
    )
    canonical_path = (
        project_root
        / "03_scene_lab/runs/s01-atom-rewrite-v1/selected"
        / "s01-b-somatic-control.codex.v2.md"
    )
    heldout_path = (
        project_root
        / "03_scene_lab/runs/s02-compute-v4.3-a4b/frontier_novelist"
        / "s02.codex.v1.md"
    )
    target = _read_json(target_path)
    # The old packet carried a weak, now superseded S01 tail.  The target atoms
    # and endpoint remain immutable; the actual canonical S01 is appended below.
    target = {key: value for key, value in target.items() if key != "manuscript_tail"}
    target_hash = hash_json(target)
    canonical_s01 = canonical_path.read_text(encoding="utf-8")
    heldout_s02 = heldout_path.read_text(encoding="utf-8")
    heldout_guard = AntiCopyIndex(
        {"accepted-s02-heldout": heldout_s02},
        policy=AntiCopyPolicy(exact_words=12),
    )
    demos = load_s01_demonstrations(project_root)
    maximum_library = max(spec[3] for spec in ARM_SPECS)
    library = select_dialogue_rich_library(
        project_root,
        maximum_words=maximum_library,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    prompt_dir = output_dir / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    source_dir = output_dir / "sources"
    source_dir.mkdir(parents=True, exist_ok=True)
    arms: list[PromptArm] = []
    source_records: dict[str, dict[str, Any]] = {}
    for source_id, text in library:
        source_path = source_dir / f"{source_id}.txt"
        atomic_write_text(source_path, text)
        source_records[source_id] = {
            "source_id": source_id,
            "path": str(source_path.relative_to(project_root)),
            "text_hash": sha256_text(text),
            "words": word_count(text),
            "category": "public-domain-reference",
        }
    for arm_id, family, nominal_tokens, library_words in ARM_SPECS:
        selected: list[tuple[str, str]] = []
        count = 0
        for source_id, text in library:
            if count >= library_words:
                break
            selected.append((source_id, text))
            count += word_count(text)
        prompt = build_prompt(
            family=family,
            target=target,
            canonical_s01=canonical_s01,
            demonstrations=demos,
            library=selected,
        )
        heldout_matches = heldout_guard.exact_matches(prompt)
        if heldout_matches:
            raise ValueError(
                f"accepted S02 leaked into {arm_id}: {heldout_matches[0]}"
            )
        prompt_path = prompt_dir / f"{arm_id}.txt"
        atomic_write_text(prompt_path, prompt)
        arms.append(
            PromptArm(
                arm_id=arm_id,
                family=family,
                nominal_context_tokens=nominal_tokens,
                prompt_path=str(prompt_path.relative_to(project_root)),
                prompt_hash=sha256_text(prompt),
                prompt_words=word_count(prompt),
                demonstration_ids=(
                    tuple(item.demonstration_id for item in demos)
                    if family in {"paired-icl", "full-stack"}
                    else ()
                ),
                library_source_ids=tuple(item[0] for item in selected),
                target_packet_hash=target_hash,
                canonical_prefix_hash=sha256_text(canonical_s01),
            )
        )
    manifest = {
        "record_type": "BaseMetaPromptExperiment",
        "version": META_PROMPT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target": {
            "scene": "S02",
            "sequence": "s02-seq-1-trap",
            "packet_path": str(target_path.relative_to(project_root)),
            "packet_hash_without_superseded_tail": target_hash,
            "opening_runway": OPENING_RUNWAY,
            "heldout_reference": {
                "path": str(heldout_path.relative_to(project_root)),
                "sha256": sha256_text(heldout_s02),
                "prompt_overlap_check": "zero exact 12-word matches in every arm",
            },
        },
        "canonical_s01": {
            "path": str(canonical_path.relative_to(project_root)),
            "sha256": sha256_text(canonical_s01),
        },
        "sampling": {
            "seeds": list(DEFAULT_SEEDS),
            "temperature": 0.95,
            "top_p": 0.97,
            "min_p": 0.02,
            "xtc_probability": 0.08,
            "maximum_new_tokens": 1_500,
            "repair": "none before literary triage",
            "model_trained_context_tokens": 262_144,
            "default_execution_context_tokens": 131_072,
            "reserved_context_tokens": 2_048,
        },
        "demonstrations": [asdict(item) for item in demos],
        "library_sources": list(source_records.values()),
        "arms": [asdict(item) for item in arms],
        "selection": {
            "screen": "paired seeds and exact target across all arms",
            "advance": "hard-gate eligibility, literary proxy, structural diversity, then cold read",
            "no_reference_leak": "accepted S02 is excluded from every prompt",
        },
    }
    write_json(output_dir / "experiment_manifest.v1.json", manifest)
    return manifest


def _append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _completed_calls(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    values: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if item.get("status") == "completed":
            values[str(item["call_id"])] = item
    return values


def _terminal_calls(path: Path) -> dict[str, dict[str, Any]]:
    """Return the latest durable completion or failure for each call id."""

    if not path.is_file():
        return {}
    values: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if item.get("status") not in {"completed", "failed"}:
            continue
        if item.get("candidate_path") or item.get("raw_path"):
            values[str(item["call_id"])] = item
    return values


def extract_complete_checkpoint(
    text: str,
    *,
    minimum_words: int = 875,
    maximum_words: int = 1_100,
) -> str:
    """Select the longest complete-paragraph prefix inside a word-count band."""

    if not 0 < minimum_words <= maximum_words:
        raise ValueError("invalid checkpoint word bounds")
    paragraphs = [
        item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()
    ]
    selected: list[str] = []
    best = ""
    for paragraph in paragraphs:
        trial = "\n\n".join((*selected, paragraph))
        words = word_count(trial)
        if words > maximum_words:
            break
        selected.append(paragraph)
        if minimum_words <= words <= maximum_words and re.search(
            r"[.!?][\"”’']?\s*$", paragraph
        ):
            best = trial
    if not best:
        raise ValueError(
            f"no complete paragraph boundary within {minimum_words}-{maximum_words} words"
        )
    return best


def load_anti_copy_sources(
    project_root: Path,
    manifest: Mapping[str, Any],
) -> tuple[dict[str, str], dict[str, str]]:
    """Load every prose source exposed to any arm and verify provenance hashes."""

    documents: dict[str, str] = {}
    categories: dict[str, str] = {}
    canonical = manifest.get("canonical_s01")
    if isinstance(canonical, Mapping):
        source_path = project_root / str(canonical["path"])
        prose = source_path.read_text(encoding="utf-8")
        if sha256_text(prose) != canonical["sha256"]:
            raise ValueError("canonical S01 hash changed")
        documents["canonical:s01"] = prose
        categories["canonical:s01"] = "canonical-prefix"
    for demo in manifest.get("demonstrations", ()):
        source_id = f"demo:{demo['demonstration_id']}"
        prose = str(demo["prose"])
        if sha256_text(prose.strip()) != demo["prose_hash"]:
            raise ValueError(f"demonstration hash changed: {source_id}")
        documents[source_id] = prose
        categories[source_id] = "project-demonstration"
    for item in manifest.get("library_sources", ()):
        source_id = f"library:{item['source_id']}"
        source_path = project_root / str(item["path"])
        prose = source_path.read_text(encoding="utf-8")
        if sha256_text(prose) != item["text_hash"]:
            raise ValueError(f"library source hash changed: {source_id}")
        documents[source_id] = prose
        categories[source_id] = str(item.get("category", "reference-library"))
    return documents, categories


def run_meta_prompt_experiment(
    project_root: Path,
    run_dir: Path,
    *,
    client: LlamaClient,
    arm_ids: Sequence[str],
    seeds: Sequence[int],
    maximum_new_tokens: int = 1_500,
    server_context_tokens: int = 131_072,
    concurrency: int = 1,
    admission: SharedEndpointAdmission | None = None,
) -> list[dict[str, Any]]:
    if concurrency < 1:
        raise ValueError("concurrency must be positive")
    manifest = _read_json(run_dir / "experiment_manifest.v1.json")
    arms = {item["arm_id"]: item for item in manifest["arms"]}
    unknown = sorted(set(arm_ids) - set(arms))
    if unknown:
        raise ValueError(f"unknown experiment arms: {', '.join(unknown)}")
    source_docs, source_categories = load_anti_copy_sources(project_root, manifest)
    calls_path = run_dir / "calls.jsonl"
    completed = _completed_calls(calls_path)
    results: list[dict[str, Any]] = []
    for arm_id in arm_ids:
        arm = arms[arm_id]
        prompt_path = project_root / arm["prompt_path"]
        prompt = prompt_path.read_text(encoding="utf-8")
        if sha256_text(prompt) != arm["prompt_hash"]:
            raise ValueError(f"prompt hash changed: {arm_id}")
        arm_sources = dict(source_docs)
        arm_categories = dict(source_categories)
        arm_sources[f"prompt:{arm_id}"] = prompt
        arm_categories[f"prompt:{arm_id}"] = "generation-control-packet"
        anti_copy = AntiCopyIndex(
            arm_sources,
            categories=arm_categories,
            policy=AntiCopyPolicy(exact_words=12),
        )
        token_count = client.token_count(prompt)
        reserved = int(manifest["sampling"]["reserved_context_tokens"])
        if token_count + maximum_new_tokens > server_context_tokens - reserved:
            raise ValueError(
                f"{arm_id} exceeds safe context budget: "
                f"{token_count} prompt + {maximum_new_tokens} completion > "
                f"{server_context_tokens - reserved}"
            )
        pending: list[int] = []
        for seed in seeds:
            call_id = f"{arm_id}:{seed}"
            prior = completed.get(call_id)
            if prior is not None:
                results.append(prior)
                continue
            pending.append(seed)

        def generate(seed: int) -> dict[str, Any]:
            call_id = f"{arm_id}:{seed}"
            started = {
                "record_type": "MetaPromptCall",
                "version": META_PROMPT_VERSION,
                "call_id": call_id,
                "status": "started",
                "arm_id": arm_id,
                "family": arm["family"],
                "prompt_hash": arm["prompt_hash"],
                "prompt_words": arm["prompt_words"],
                "prompt_tokens": token_count,
                "seed": seed,
                "server_context_tokens": server_context_tokens,
                "parameters": {
                    "temperature": 0.95,
                    "top_p": 0.97,
                    "min_p": 0.02,
                    "xtc_probability": 0.08,
                    "maximum_new_tokens": maximum_new_tokens,
                    "stop": ["\\n#", "\\n<"],
                },
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
            _append_jsonl(calls_path, started)
            raw_path = run_dir / "raw" / f"{arm_id}.{seed}.txt"
            raw_prose: str | None = None
            completion = None
            try:
                guard = StreamingNgramGuard(anti_copy)
                lease = (
                    admission.acquire(
                        owner=f"meta-prompt:{call_id}",
                        prompt_hash=str(arm["prompt_hash"]),
                        prompt_tokens=token_count,
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
                        temperature=0.95,
                        top_p=0.97,
                        min_p=0.02,
                        xtc_probability=0.08,
                        stop=("\n#", "\n<"),
                        on_delta=guard.feed,
                    )
                else:
                    with lease:
                        completion = client.stream_raw(
                            prompt=prompt,
                            seed=seed,
                            max_tokens=maximum_new_tokens,
                            temperature=0.95,
                            top_p=0.97,
                            min_p=0.02,
                            xtc_probability=0.08,
                            stop=("\n#", "\n<"),
                            on_delta=guard.feed,
                        )
                raw_prose = clean_generated_prose(completion.content)
                atomic_write_text(raw_path, raw_prose)
                prose = extract_complete_checkpoint(raw_prose)
                from .long_context import self_repetition_report

                repetition = self_repetition_report(prose)
                if repetition["hard_fail"]:
                    raise ValueError(
                        "candidate contains a repeated internal passage: "
                        + str(
                            repetition["duplicate_windows"][:1]
                            or repetition["duplicate_paragraphs"][:1]
                        )
                    )
                candidate_path = run_dir / "candidates" / f"{arm_id}.{seed}.md"
                atomic_write_text(candidate_path, prose)
                record = {
                    **started,
                    "status": "completed",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "candidate_path": str(candidate_path.relative_to(project_root)),
                    "candidate_hash": sha256_text(prose),
                    "candidate_words": word_count(prose),
                    "raw_path": str(raw_path.relative_to(project_root)),
                    "raw_hash": sha256_text(raw_prose),
                    "raw_words": word_count(raw_prose),
                    "self_repetition": repetition,
                    "finish_reason": completion.finish_reason,
                    "usage": completion.usage,
                    "timings": completion.timings,
                    "cache": completion.cache,
                    "elapsed_seconds": completion.elapsed_seconds,
                    "anti_copy_index_hash": anti_copy.index_hash,
                }
            except Exception as exc:
                record = {
                    **started,
                    "status": "failed",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "error": f"{type(exc).__name__}: {exc}",
                }
                if raw_prose is not None:
                    record.update(
                        {
                            "raw_path": str(raw_path.relative_to(project_root)),
                            "raw_hash": sha256_text(raw_prose),
                            "raw_words": word_count(raw_prose),
                        }
                    )
                if completion is not None:
                    record.update(
                        {
                            "finish_reason": completion.finish_reason,
                            "usage": completion.usage,
                            "timings": completion.timings,
                            "cache": completion.cache,
                            "elapsed_seconds": completion.elapsed_seconds,
                        }
                    )
            _append_jsonl(calls_path, record)
            return record

        if concurrency == 1:
            generated = [generate(seed) for seed in pending]
        else:
            generated = []
            with ThreadPoolExecutor(
                max_workers=min(concurrency, max(1, len(pending)))
            ) as executor:
                futures = {executor.submit(generate, seed): seed for seed in pending}
                for future in as_completed(futures):
                    generated.append(future.result())
            generated.sort(key=lambda item: int(item["seed"]))
        for record in generated:
            if record["status"] == "completed":
                completed[str(record["call_id"])] = record
            results.append(record)
    return results


def measure_meta_prompt_contexts(
    project_root: Path,
    run_dir: Path,
    *,
    client: LlamaClient,
    maximum_new_tokens: int = 1_500,
    server_context_tokens: int = 131_072,
) -> dict[str, Any]:
    """Measure all arms with the actual model tokenizer before inference."""

    manifest = _read_json(run_dir / "experiment_manifest.v1.json")
    reserved = int(manifest["sampling"]["reserved_context_tokens"])
    safe_limit = server_context_tokens - reserved
    records: list[dict[str, Any]] = []
    for arm in manifest["arms"]:
        prompt_path = project_root / arm["prompt_path"]
        prompt = prompt_path.read_text(encoding="utf-8")
        if sha256_text(prompt) != arm["prompt_hash"]:
            raise ValueError(f"prompt hash changed: {arm['arm_id']}")
        prompt_tokens = client.token_count(prompt)
        records.append(
            {
                "arm_id": arm["arm_id"],
                "prompt_hash": arm["prompt_hash"],
                "prompt_words": arm["prompt_words"],
                "prompt_tokens": prompt_tokens,
                "maximum_new_tokens": maximum_new_tokens,
                "safe_context_limit": safe_limit,
                "within_budget": prompt_tokens + maximum_new_tokens <= safe_limit,
            }
        )
    if not all(item["within_budget"] for item in records):
        raise ValueError("one or more prompt arms exceed the safe context budget")
    result = {
        "record_type": "BaseMetaPromptTokenMeasurements",
        "version": META_PROMPT_VERSION,
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "server_context_tokens": server_context_tokens,
        "model_trained_context_tokens": manifest["sampling"][
            "model_trained_context_tokens"
        ],
        "records": records,
    }
    write_json(run_dir / "token_measurements.v1.json", result)
    return result


_ABSTRACT_TERMS = re.compile(
    r"\b(?:agency|autonomy|freedom|compliance|dynamic|mechanism|"
    r"interpretation|narrative|boundary|power|control|manipulation|trap)\b",
    re.IGNORECASE,
)


def _target_atom_diagnostics(text: str) -> dict[str, Any]:
    folded = text.casefold()
    raw_access = bool(re.search(r"\braw[- ]access\b", folded)) and bool(
        re.search(r"\b(?:data|trace|monitor|tablet|permission)\w*\b", folded)
    )
    telemetry_window = bool(
        re.search(
            r"(?:raw\s+)?telemetry.{0,240}\baccess\b|"
            r"\baccess\b.{0,240}(?:raw\s+)?telemetry",
            folded,
            re.DOTALL,
        )
    ) or raw_access or bool(
        re.search(
            r"\b(?:take|bring|carry|send|copy|export)\b.{0,60}"
            r"\b(?:raw\s+(?:stream|data)|telemetry|trace)\b.{0,80}"
            r"\b(?:home|outside|away|device|laptop)\b|"
            r"\b(?:raw\s+(?:stream|data)|telemetry|trace)\b.{0,80}"
            r"\b(?:home|outside|away|keycard|permission)\b",
            folded,
            re.DOTALL,
        )
    ) or bool(
        re.search(
            r"\b(?:telemetry|raw[- ]data|raw[- ]stream)\s+"
            r"(?:key|credential|token|permission|login|account)\b|"
            r"\b(?:key|credential|token|permission|login|account)\b.{0,50}"
            r"\b(?:telemetry|raw[- ]data|raw[- ]stream)\b",
            folded,
            re.DOTALL,
        )
    )
    pending_permission = bool(
        re.search(
            r"\bpermission(?:s|\s+line|\s+window)?\b.{0,120}"
            r"\b(?:pending|accept|granted)\b",
            folded,
            re.DOTALL,
        )
    )
    checks = {
        "tea_care": "tea" in folded and ("cup" in folded or "carafe" in folded),
        "unexceptional_fear": bool(
            re.search(
                r"\b(?:unremarkable|not\s+exceptional|not\s+special|"
                r"(?:isn['’]?t|aren['’]?t)\s+exceptional(?:\s+enough)?|"
                r"merely\s+competent|only\s+competent|competent\s+but\s+not)\b|"
                r"\bfail(?:ed|ing)?\s+to\s+be\s+exceptional\b|"
                r"\b(?:test|waiting|found\s+out)\b.{0,140}\bexceptional\b|"
                r"\b(?:prove|show)\b.{0,100}\bexceptional\b|"
                r"\bexceptional\w*\b.{0,120}\b(?:afraid|fear|expensive|cost|belong)\w*\b|"
                r"\b(?:afraid|fear|expensive|cost|belong)\w*\b.{0,120}\bexceptional\w*\b",
                folded,
                re.DOTALL,
            )
        ),
        "telemetry_access": telemetry_window
        or bool(
            re.search(
                r"\bovernight\s+access\b.{0,180}\b(?:data|trace|monitor|find)\b|"
                r"\b(?:data|trace|monitor)\b.{0,180}\bovernight\s+access\b",
                folded,
                re.DOTALL,
            )
        ),
        "jonah_complicity": "jonah" in folded
        and bool(
            re.search(
                r"\b(?:the\s+)?next\s+sequence\s+(?:is|was|'s)\s+ready\b",
                folded,
            )
        ),
        "mara_accepts": (
            telemetry_window or "overnight access" in folded or pending_permission
        )
        and bool(
            re.search(
                r"\b(?:mara\s+)?(?:tap(?:ped|s)?|press(?:ed|es)?|touch(?:ed|es)?)\s+"
                r"(?:the\s+)?(?:accept|confirmation)|\baccess\s+accepted\b|"
                r"\baccepted\s+(?:the\s+)?access\b|"
                r"\bmara\b.{0,100}\btouch(?:ed|es)?\b.{0,100}\baccept\b",
                folded,
                re.DOTALL,
            )
        ),
        "session_continues": not bool(
            re.search(r"\b(?:session|meeting)\s+(?:ended|was\s+over)\b", folded)
        )
        and bool(
            re.search(
                r"\b(?:next\s+sequence\s+(?:opened|loaded|began|(?:is|was)\s+ready)|"
                r"session\s+(?:continued|remained|was\s+still\s+underway)|"
                r"room\s+(?:continued|resumed(?:\s+its\s+ordinary\s+motion)?)\s+"
                r"(?:around\s+her)?|"
                r"jonah\s+returned\s+to\s+(?:the\s+)?(?:data\s+)?traces)\b",
                folded,
            )
        ),
    }
    forbidden_future = any(
        phrase in folded
        for phrase in (
            "walked her home",
            "walk home",
            "doorway",
            "their kiss",
            "kissed him",
            "kissed her",
            "left the room",
            "leaves the room",
            "exited the room",
        )
    )
    return {
        "checks": checks,
        "coverage": sum(checks.values()) / len(checks),
        "forbidden_future": forbidden_future,
    }


def evaluate_meta_prompt_outputs(project_root: Path, run_dir: Path) -> dict[str, Any]:
    manifest = _read_json(run_dir / "experiment_manifest.v1.json")
    demo_sources, source_categories = load_anti_copy_sources(project_root, manifest)
    arms = {item["arm_id"]: item for item in manifest["arms"]}
    overlap_indexes: dict[str, AntiCopyIndex] = {}
    latest = _terminal_calls(run_dir / "calls.jsonl")
    records: list[dict[str, Any]] = []
    for call_id, call in sorted(latest.items()):
        artifact_path = call.get("candidate_path") or call.get("raw_path")
        path = project_root / str(artifact_path)
        text = path.read_text(encoding="utf-8")
        arm_id = str(call["arm_id"])
        overlap_index = overlap_indexes.get(arm_id)
        if overlap_index is None:
            arm = arms[arm_id]
            prompt_path = project_root / arm["prompt_path"]
            prompt = prompt_path.read_text(encoding="utf-8")
            if sha256_text(prompt) != arm["prompt_hash"]:
                raise ValueError(f"prompt hash changed: {arm_id}")
            arm_sources = dict(demo_sources)
            arm_categories = dict(source_categories)
            arm_sources[f"prompt:{arm_id}"] = prompt
            arm_categories[f"prompt:{arm_id}"] = "generation-control-packet"
            overlap_index = AntiCopyIndex(
                arm_sources,
                categories=arm_categories,
                policy=AntiCopyPolicy(exact_words=12),
            )
            overlap_indexes[arm_id] = overlap_index
        words = max(1, word_count(text))
        target = _target_atom_diagnostics(text)
        style = literary_style_diagnostics(text)
        from .long_context import self_repetition_report

        self_repetition = self_repetition_report(text)
        abstract_hits = len(_ABSTRACT_TERMS.findall(text))
        dialogue_turns = len(re.findall(r"[“\"]", text)) // 2
        head_hop = bool(
            re.search(
                r"\b(?:Livia|Jonah)\s+(?:knew|thought|wondered|remembered|felt)\b|"
                r"\bshe\s+knew\s+(?:that\s+)?he\s+(?:thought|was\s+thinking|wanted|intended|felt)\b",
                text,
                re.IGNORECASE,
            )
        )
        overlap = overlap_index.exact_matches(text)
        word_ok = 650 <= words <= 1_150
        ending_clean = bool(re.search(r"[.!?][\"”’']?\s*$", text))
        finish_reason = str(call.get("finish_reason", ""))
        # Generation may intentionally run past the checkpoint so the scaffold
        # can select a complete paragraph boundary. Candidate completeness is
        # therefore independent of whether the preserved raw tail hit n_predict.
        complete = ending_clean
        eligible = all(
            (
                call.get("status") == "completed",
                word_ok,
                complete,
                not target["forbidden_future"],
                not head_hop,
                not overlap,
                not self_repetition["hard_fail"],
                target["coverage"] >= 4 / 6,
            )
        )
        cadence = float(style["cadence_families"]["hits_per_1000_words"])
        proxy = (
            target["coverage"] * 45
            + min(dialogue_turns / 12, 1.0) * 15
            + max(0.0, 20.0 - cadence)
            + max(0.0, 20.0 - abstract_hits / words * 1_000)
        )
        records.append(
            {
                "call_id": call_id,
                "arm_id": call["arm_id"],
                "seed": call["seed"],
                "status": call.get("status"),
                "artifact_kind": "candidate" if call.get("candidate_path") else "raw_failure",
                "candidate_path": artifact_path,
                "candidate_hash": call.get("candidate_hash") or call.get("raw_hash"),
                "words": words,
                "eligible": eligible,
                "complete": complete,
                "finish_reason": finish_reason,
                "target_atoms": target,
                "head_hop": head_hop,
                "source_overlap": list(overlap),
                "self_repetition": self_repetition,
                "abstract_terms_per_1000": round(abstract_hits / words * 1_000, 4),
                "dialogue_turns": dialogue_turns,
                "cadence_hits_per_1000": cadence,
                "literary_proxy": round(proxy, 4),
                "prompt_tokens": call.get("prompt_tokens"),
                "cache": call.get("cache", {}),
                "elapsed_seconds": call.get("elapsed_seconds"),
            }
        )
    by_arm: dict[str, dict[str, Any]] = {}
    for arm in manifest["arms"]:
        arm_records = [item for item in records if item["arm_id"] == arm["arm_id"]]
        if not arm_records:
            continue
        eligible = [item for item in arm_records if item["eligible"]]
        by_arm[arm["arm_id"]] = {
            "family": arm["family"],
            "nominal_context_tokens": arm["nominal_context_tokens"],
            "samples": len(arm_records),
            "eligible": len(eligible),
            "mean_proxy": round(
                sum(item["literary_proxy"] for item in arm_records)
                / len(arm_records),
                4,
            ),
            "best_call_id": max(
                arm_records,
                key=lambda item: (item["eligible"], item["literary_proxy"]),
            )["call_id"],
        }
    result = {
        "record_type": "BaseMetaPromptEvaluation",
        "version": META_PROMPT_VERSION,
        "records": records,
        "by_arm": by_arm,
        "warning": "Literary proxy is a screen, never the final selector; surviving prose requires blind close reading.",
    }
    write_json(run_dir / "evaluation" / "mechanical_screen.v1.json", result)
    return result
