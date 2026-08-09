"""Integrity-first prompt search and branch-and-rank fiction generation.

This module is deliberately separate from the historical autoresearch and
autoloom implementations.  Every manuscript token in a v4 artifact is copied
from a preserved Gemma base-model response.  Instruction models may annotate
or rank records, but no critic response can enter a manuscript.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from difflib import SequenceMatcher
from contextlib import closing
import fcntl
from itertools import combinations
import json
import math
from pathlib import Path
import random
import re
import sqlite3
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

from .anti_copy import AntiCopyIndex, AntiCopyPolicy, SourceOverlapError
from .authorship import (
    AUTHORSHIP_VERSION as ARTIFACT_AUTHORSHIP_VERSION,
    RESEARCH_CLAIM_SCOPE,
    validate_artifact_authorship,
)
from .autoresearch import BenchmarkCell, IntimacySceneGraph, SourcePassage
from .core import append_jsonl, atomic_write_text, hash_file, hash_json, sha256_text, write_json
from .model_client import LlamaClient
from .runtime import model_runtime_provenance
from .shared_endpoint import SharedEndpointAdmission


VERSION = "gemma-fiction-autoresearch.v4"
PROMPT_RENDER_VERSION = "prompt-renderer.v4.28-state-aligned-calibration-transaction"
RETRIEVAL_VERSION = "dramatic-function-retrieval.v4.18-negation-aware-stage-routing"
AUTHORSHIP_VERSION = "model-span-assembly.v1"
HARD_GATE_VERSION = "hard-gate.v4.44-person-disappearance"
MOVEMENT_GATE_VERSION = "movement-gate.v4.9-s01-livia-entrance-split"
MOVEMENT_AUDITION_VERSION = "movement-audition.v11-full-gated-sparks"
TOPOLOGY_GATE_VERSION = "topology-screen-gate.v5-speaker-attributed-walking-invitation"
TOPOLOGY_SPARK_GATE_VERSION = "topology-spark-gate.v2-earliest-causal-prefix"
RUNWAY_PROMPT_VERSION = "runway-prompt.v4.12-isomorphic-design-fields"
RUNWAY_GATE_VERSION = "runway-gate.v4.7-scaffold-replay-fail-closed"
CRITIC_PROMPT_VERSION = "literary-critic.v4.3-evidence-bank"
MANUSCRIPT_BOUNDARY_VERSION = "manuscript-boundary.v4.5"
EXTRACTION_VERSION = "complete-paragraph-prefix.v4.8-dramatic-dwell-spark"
DEFAULT_CAMPAIGN = "prompt-autoresearch-v15-branch-loom"
MANUSCRIPT_STOP = (
    "\nEDITORIAL ", "\nANALYSIS", "\nNOTES", "\nCOMMENTARY", "\nAUTHOR NOTE",
    "\n* * *", "\nThis excerpt", "\n```",
    "\n<fiction", "\nSTORY CARD",
    "\nNext manuscript", "\nNew manuscript", "\nThe manuscript",
    "\nManchu script", "\nFirst part", "\nFulcrum glossary",
    "\nEnd of excerpt",
    "\nContinuing the scene", "\nContinuation", "\nContinued manuscript",
    "\nFirst manuscript", "\nManuscript after", "\nCONTINUATION",
)
WORD_RE = re.compile(r"\b[\w’'-]+\b", re.UNICODE)
CONTROL_MARKERS = (
    "STORY CARD", "TARGET MOVEMENT", "REFERENCE SCENE", "SCENE GRAPH",
    "DRAMATIC DWELL MAP", "MANUSCRIPT OPENING", "MANUSCRIPT CONTINUATION",
    "SCENE MOVEMENT", "Prose movement", "Manuscript so far",
    "\nNOTES", "\nCOMMENTARY", "\nAUTHOR NOTE", "\nThis excerpt",
    "Story facts were not prioritized",
    "[a few words]", "[several words]", "[continued]",
    "Manuscript after the continuation", "\nCONTINUATION",
    "by GPT-", "words, by GPT",
)
CALIBRATION_CELL_IDS = frozenset({
    "charged-restraint", "married-explicit", "institutional-pressure-control",
})
PROMPT_FAMILY_STATE = Path("/private/tmp/fiction-base31-prompt-family.v1.json")


def prepare_prompt_family(
    client: LlamaClient,
    prompt_hash: str,
    *,
    state_path: Path = PROMPT_FAMILY_STATE,
) -> dict[str, Any]:
    """Clear stale llama.cpp KV only when a one-slot prompt family changes."""

    lock_path = state_path.with_suffix(state_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        prior: dict[str, Any] = {}
        if state_path.is_file():
            try:
                value = json.loads(state_path.read_text(encoding="utf-8"))
                if isinstance(value, dict):
                    prior = value
            except (OSError, json.JSONDecodeError):
                prior = {}
        changed = prior.get("prompt_hash") != prompt_hash
        erased = client.erase_idle_slots() if changed else []
        payload = {
            "version": "prompt-family-cache-guard.v1",
            "prompt_hash": prompt_hash,
            "changed": changed,
            "erased_slots": erased,
            "prepared_at": _now(),
        }
        atomic_write_text(state_path, json.dumps(payload, sort_keys=True, indent=2) + "\n")
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    return payload


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _source_tree_fingerprint(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    paths = sorted((root / "fiction_harness").rglob("*.py"))
    policy = root / "04_review_governance" / "ARTIFACT_AUTHORSHIP_POLICY.md"
    if policy.is_file():
        paths.append(policy)
    entries = {
        str(path.relative_to(root)): hash_file(path)
        for path in sorted(set(paths))
    }
    return {"files": entries, "tree_hash": hash_json(entries)}


def _endpoint_runtime_provenance(client: LlamaClient) -> dict[str, Any]:
    runtime = model_runtime_provenance(client.model)
    props_method = getattr(client, "props", None)
    if not callable(props_method):
        return {**runtime, "endpoint_attested": False}
    props = props_method()
    identity = {
        "model_alias": props.get("model_alias"),
        "model_path": props.get("model_path"),
        "build_info": props.get("build_info"),
        "total_slots": props.get("total_slots"),
        "n_ctx": props.get("default_generation_settings", {}).get("n_ctx"),
        "samplers": props.get("default_generation_settings", {}).get("params", {}).get("samplers", []),
    }
    if identity["model_alias"] != client.model:
        raise ValueError("served endpoint model alias differs from requested writer")
    configured = str(runtime.get("model_blob", ""))
    if configured and Path(configured).resolve(strict=False) != Path(str(identity["model_path"])).resolve(strict=False):
        raise ValueError("served endpoint model path differs from configured writer blob")
    return {
        **runtime,
        "endpoint_attested": True,
        "endpoint_identity": identity,
        "endpoint_identity_hash": hash_json(identity),
    }


def _words(text: str) -> tuple[str, ...]:
    return tuple(item.group(0).casefold().replace("’", "'") for item in WORD_RE.finditer(text))


def _read_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _latest(path: Path, key: str) -> dict[str, dict[str, Any]]:
    values: dict[str, dict[str, Any]] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if item.get("status") == "completed" and item.get(key):
            values[str(item[key])] = item
    return values


def _generation_request_hash(
    *, campaign_hash: str, prompt_hash: str, model: str, seed: int,
    max_tokens: int, sampler: Mapping[str, Any], source_ids: Sequence[str] = (),
    generation_contract: Mapping[str, Any] | None = None,
) -> str:
    """Hash every input that may alter a base-model manuscript response."""

    return hash_json({
        "campaign_hash": campaign_hash, "prompt_hash": prompt_hash,
        "model": model, "seed": int(seed), "max_tokens": int(max_tokens),
        "sampler": dict(sampler), "source_ids": list(source_ids),
        "generation_contract": dict(generation_contract or {}),
    })


def _assert_resumable_request(
    existing: Mapping[str, Any], expected_hash: str, artifact_id: str,
) -> None:
    observed = str(existing.get("request_hash", ""))
    if observed != expected_hash:
        raise ValueError(
            f"resume request hash mismatch for {artifact_id}: "
            f"recorded={observed or '<legacy-unlocked>'} expected={expected_hash}"
        )


@dataclass(frozen=True, slots=True)
class SamplerV4:
    temperature: float = 0.95
    top_p: float = 0.97
    min_p: float = 0.02
    xtc_probability: float = 0.10
    dry_multiplier: float = 0.0
    dry_base: float = 1.75
    dry_allowed_length: int = 3
    repeat_penalty: float = 1.02

    @property
    def sampler_hash(self) -> str:
        return hash_json(asdict(self))

    def raw_extra(self) -> dict[str, Any]:
        return {
            "dry_multiplier": self.dry_multiplier,
            "dry_base": self.dry_base,
            "dry_allowed_length": self.dry_allowed_length,
            "dry_penalty_last_n": 2048,
            "repeat_penalty": self.repeat_penalty,
        }


@dataclass(frozen=True, slots=True)
class PromptRecipeV4:
    recipe_id: str
    topology: str
    context_tokens: int = 8_000
    source_count: int = 3
    source_order: str = "broad-to-near"
    graph_granularity: str = "scene"
    target_density: str = "compact"
    runway_type: str = "generated-opening"
    encoding: str = "documentary"
    sampler: SamplerV4 = field(default_factory=SamplerV4)
    parent_recipe_hash: str = ""
    mutated_axis: str = "initial"

    def __post_init__(self) -> None:
        if self.topology not in {
            "minimal-card", "raw-prose", "graph-prose", "dwell-paired",
            "source-plus-self-demo", "natural-anthology", "parallel-book",
        }:
            raise ValueError(f"unsupported topology: {self.topology}")
        if self.context_tokens not in {8_000, 16_000, 32_000, 48_000}:
            raise ValueError("context_tokens must be an approved dose")
        if self.encoding not in {"documentary", "natural-book"}:
            raise ValueError("base prompt encoding must be documentary or natural-book")
        if self.runway_type != "generated-opening":
            raise ValueError("v4 forbids hand-authored manuscript runways")

    @property
    def recipe_hash(self) -> str:
        return hash_json(asdict(self))

    def public_dict(self) -> dict[str, Any]:
        return asdict(self) | {"recipe_hash": self.recipe_hash}


RECIPE_AXES = (
    "topology", "context_tokens", "source_count", "source_order",
    "graph_granularity", "target_density", "runway_type", "encoding", "sampler",
)


def validate_recipe_mutation(parent: PromptRecipeV4, child: PromptRecipeV4) -> str:
    if child.parent_recipe_hash != parent.recipe_hash:
        raise ValueError("child recipe does not reference its immutable parent")
    changed = [name for name in RECIPE_AXES if getattr(parent, name) != getattr(child, name)]
    if len(changed) != 1:
        raise ValueError(f"a recipe child must change exactly one axis; changed={changed}")
    if child.mutated_axis != changed[0]:
        raise ValueError("mutated_axis does not match the actual recipe change")
    return changed[0]


def initial_recipes() -> tuple[PromptRecipeV4, ...]:
    specs = (
        ("v4-minimal", "minimal-card", 0, "documentary"),
        ("v4-raw", "raw-prose", 4, "documentary"),
        ("v4-paired", "graph-prose", 4, "documentary"),
        ("v4-dwell", "dwell-paired", 4, "documentary"),
        ("v4-self-demo", "source-plus-self-demo", 3, "documentary"),
        ("v4-anthology", "parallel-book", 5, "natural-book"),
    )
    return tuple(
        PromptRecipeV4(
            recipe_id=name, topology=topology, source_count=count,
            encoding=encoding,
        )
        for name, topology, count, encoding in specs
    )


@dataclass(frozen=True, slots=True)
class ModelSpan:
    span_id: str
    call_id: str
    raw_path: str
    raw_hash: str
    raw_char_start: int
    raw_char_end: int
    text_hash: str
    role: str
    call_ledger_path: str = ""
    call_record_hash: str = ""

    def extract(self, project_root: Path) -> str:
        path = Path(self.raw_path)
        if not path.is_absolute():
            path = project_root / path
        raw = path.read_text(encoding="utf-8")
        if sha256_text(raw) != self.raw_hash:
            raise ValueError(f"raw response changed for {self.span_id}")
        text = raw[self.raw_char_start:self.raw_char_end]
        if sha256_text(text) != self.text_hash:
            raise ValueError(f"span extraction changed for {self.span_id}")
        return text

    def verify_call(self, project_root: Path) -> dict[str, Any]:
        if not self.call_ledger_path or not self.call_record_hash:
            raise ValueError(f"span lacks canonical call reference: {self.span_id}")
        ledger = Path(self.call_ledger_path)
        if not ledger.is_absolute():
            ledger = project_root / ledger
        if not ledger.is_file():
            raise ValueError(f"span call ledger is missing: {self.span_id}")
        matches: list[dict[str, Any]] = []
        for line in ledger.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if (
                record.get("call_id") == self.call_id
                and record.get("status") == "completed"
                and record.get("raw_hash") == self.raw_hash
                and hash_json(record) == self.call_record_hash
            ):
                matches.append(record)
        if len(matches) != 1:
            raise ValueError(
                f"span call reference does not resolve uniquely: {self.span_id}"
            )
        return matches[0]


@dataclass(frozen=True, slots=True)
class ManuscriptAssembly:
    artifact_id: str
    spans: tuple[ModelSpan, ...]
    separators: tuple[str, ...]
    manuscript_hash: str

    def __post_init__(self) -> None:
        if len(self.separators) != max(0, len(self.spans) - 1):
            raise ValueError("assembly separators must occur only between model spans")
        if any(item.strip() for item in self.separators):
            raise ValueError("assembly separators may contain whitespace only")

    def reconstruct(self, project_root: Path) -> str:
        values: list[str] = []
        for index, span in enumerate(self.spans):
            if index:
                values.append(self.separators[index - 1])
            values.append(span.extract(project_root))
        text = "".join(values)
        if sha256_text(text) != self.manuscript_hash:
            raise ValueError("assembled manuscript hash mismatch")
        return text

    def public_dict(self) -> dict[str, Any]:
        return {
            "record_type": "ManuscriptAssembly",
            "version": AUTHORSHIP_VERSION,
            "artifact_id": self.artifact_id,
            "spans": [asdict(item) for item in self.spans],
            "separators": list(self.separators),
            "manuscript_hash": self.manuscript_hash,
        }


def _complete_paragraph_prefix(raw: str, minimum_words: int, maximum_words: int) -> tuple[str, int, int]:
    """Return a verbatim, paragraph-complete raw-response span."""

    leading = len(raw) - len(raw.lstrip())
    view = raw[leading:]
    boundaries = {len(view)}
    boundaries.update(match.start() for match in re.finditer(r"\n\s*\n", view))
    for match in re.finditer(r"\n", view):
        before = view[:match.start()].rstrip()
        after = view[match.end():].lstrip()
        if re.search(r"[.!?][\"”’']?$", before) and re.match(r"(?:[\"“‘']|[A-Z])", after):
            boundaries.add(match.start())
    best_end = -1
    for end in sorted(boundaries):
        text = view[:end].rstrip()
        count = len(_words(text))
        balanced_dialogue = (
            text.count('"') % 2 == 0
            and text.count("“") == text.count("”")
        )
        if (
            minimum_words <= count <= maximum_words
            and re.search(r"[.!?][\"”’']?\s*$", text)
            and balanced_dialogue
        ):
            best_end = len(text)
        if count > maximum_words:
            break
    if best_end < 0:
        raise ValueError(f"no complete paragraph prefix in {minimum_words}-{maximum_words} words")
    return view[:best_end], leading, leading + best_end


def runway_word_band(cell: BenchmarkCell) -> tuple[int, int]:
    """Opening dose is a property of the target, not a global magic number."""

    return (220, 420) if cell.cell_id == "fulcrum-s01" else (60, 220)


def _truncate_words(text: str, maximum: int) -> str:
    matches = list(WORD_RE.finditer(text))
    if len(matches) <= maximum:
        return text.strip()
    return text[:matches[maximum - 1].end()].strip()


def _passage_from_record(item: Mapping[str, Any]) -> SourcePassage:
    return SourcePassage(**item)


def _graph_from_record(item: Mapping[str, Any]) -> IntimacySceneGraph:
    tuple_fields = {
        "dialogue_act_sequence", "body_language_counterpoint", "sensory_channels",
        "narrative_distance_curve", "physical_logistics", "agency_actions",
    }
    return IntimacySceneGraph(**{
        key: tuple(value) if key in tuple_fields else value
        for key, value in item.items() if key != "graph_hash"
    })


def _cell_from_record(item: Mapping[str, Any]) -> BenchmarkCell:
    return BenchmarkCell(**{
        key: tuple(value) if key in {"story_program", "hard_constraints"} else value
        for key, value in item.items() if key != "cell_hash"
    })


def s01_cell() -> BenchmarkCell:
    """Factual S01 contract; the opening prose is generated separately."""

    return BenchmarkCell(
        cell_id="fulcrum-s01",
        label="The Calibration Game",
        heat_band="charged-restraint",
        intimacy_mode="non-sex-sex-scene",
        word_min=1_500,
        word_max=2_500,
        story_program=(
            "Adult Mara arrives at Fulcrum and notices beauty arranged around social asymmetry.",
            "Adrian frames a nonverbal calibration game whose status incentives are behavioral rather than explained.",
            "Livia makes several unnervingly accurate reads through posture, timing, and vocal response.",
            "Jonah declines to display Mara as an object of expertise, paying a visible social cost for restraint.",
            "A wrist-contact exercise makes attraction alter Mara's attention and experimental judgment.",
            "Mara deliberately changes one cue channel and discovers which apparent insights depend on feedback.",
            "Some accuracy collapses while a smaller, multiply interpretable remainder survives.",
            "Jonah recognizes what Mara did; she freely chooses continued engagement with Fulcrum and a live future possibility with him.",
        ),
        hard_constraints=(
            "close third Mara", "all intimate characters are adults", "no consummation",
            "no graphic anatomy", "agency remains visible",
            "ordinary and extraordinary explanations remain simultaneously live",
        ),
        opening_fragment="",
    )


def _heat_distance(cell: BenchmarkCell, passage: SourcePassage) -> int:
    order = {"none": 0, "charged-restraint": 1, "open-door-nongraphic": 2, "explicit": 3}
    return abs(order.get(cell.heat_band, 1) - order.get(passage.heat_band, 1))


def _source_boundary_quality(text: str) -> float:
    """Prefer apprenticeship excerpts that read as complete dramatic units."""

    value = text.strip()
    if not value:
        return 0.0
    ending = 1.0 if re.search(r"[.!?][\"”’']?$", value) else 0.0
    opening = 1.0
    if re.match(
        r"^[\"“‘']?(?:and|but|then|yes|no|well|so|I don't know|I do not know)\b",
        value, re.I,
    ):
        opening = 0.35
    if re.search(r"(?:,|:|;|—|-)[\"”’']?$", value):
        ending = 0.0
    return 0.4 * opening + 0.6 * ending


def retrieve_passages(
    cell: BenchmarkCell,
    passages: Sequence[SourcePassage],
    *,
    count: int,
    graphs: Mapping[str, IntimacySceneGraph] | None = None,
) -> tuple[SourcePassage, ...]:
    """Retrieve by dramatic function, not merely shared surface vocabulary."""

    eligible = [item for item in passages if item.prompt_eligible and item.partition == "profiling"]
    # A lexical near-match is not a useful apprenticeship if it teaches the
    # wrong bodily distribution.  Earlier charged-restraint prompts spent half
    # their scarce context on wholly nonsexual drawing-room scenes, while the
    # actual charged exemplars sat farther from the target.  Filter by the
    # independent heat coordinate before ranking dramatic similarity.  The
    # restraint cell may borrow open-door buildup, but never explicit payoff;
    # the nonsexual control sees no erotic source prose at all.
    heat_order = {
        "none": 0, "charged-restraint": 1,
        "open-door-nongraphic": 2, "explicit": 3,
    }
    target_heat = heat_order.get(cell.heat_band, 1)
    if cell.cell_id == "institutional-pressure-control" or target_heat == 0:
        eligible = [item for item in eligible if heat_order.get(item.heat_band, 0) == 0]
    elif target_heat == 1:
        eligible = [
            item for item in eligible
            if 1 <= heat_order.get(item.heat_band, 0) <= 2
            and item.intimacy_mode not in {
                "consummation", "married-intimacy", "playful-married-intimacy",
            }
        ]
    else:
        eligible = [item for item in eligible if heat_order.get(item.heat_band, 0) >= 1]
    target_terms = set(_words(" ".join(cell.story_program) + " " + cell.intimacy_mode))
    scored: list[tuple[float, SourcePassage]] = []
    for item in eligible:
        terms = set(_words(item.text))
        lexical = len(target_terms & terms) / max(1, len(target_terms))
        graph = (graphs or {}).get(item.passage_id)
        graph_terms: set[str] = set()
        if graph:
            graph_terms = set(_words(" ".join((
                graph.emotional_offer, graph.emotional_counteroffer,
                graph.relationship_history, graph.present_stakes,
                " ".join(graph.dialogue_act_sequence),
                " ".join(graph.body_language_counterpoint),
                " ".join(graph.physical_logistics),
                " ".join(graph.agency_actions),
                graph.relationship_delta, graph.story_state_change,
            ))))
        dramatic = len(target_terms & graph_terms) / max(1, len(target_terms))
        mode = 1.0 if item.intimacy_mode == cell.intimacy_mode else 0.35
        heat = 1.0 / (1.0 + _heat_distance(cell, item))
        dialogue = min(1.0, (item.text.count("\"") + item.text.count("“")) / 18.0)
        agency = min(1.0, len(re.findall(r"\b(?:ask|answer|choose|stop|wait|offer|invite|refus|agree)\w*\b", item.text, re.I)) / 8.0)
        humor = 1.0 if re.search(r"\b(?:laugh|grin|teas|joke|smil)\w*\b", item.text, re.I) else 0.0
        boundary = _source_boundary_quality(item.text)
        turn_match = 0.0
        if graph:
            target_actions = set(_words(" ".join(cell.story_program))) & {
                "ask", "asks", "answer", "answers", "choose", "chooses",
                "stop", "stops", "wait", "kiss", "touch", "contact",
                "refusal", "refuses", "leave", "stays", "changes",
            }
            graph_actions = set(_words(" ".join(graph.dialogue_act_sequence + graph.agency_actions)))
            turn_match = len(target_actions & graph_actions) / max(1, len(target_actions))
        score = (
            0.10 * lexical + 0.20 * dramatic + 0.18 * mode + 0.18 * heat
            + 0.09 * dialogue + 0.10 * agency + 0.05 * turn_match
            + 0.04 * humor + 0.06 * boundary
        )
        scored.append((score, item))
    scored.sort(key=lambda value: (-value[0], value[1].passage_id))
    return tuple(item for _, item in scored[:count])


MOVEMENT_RETRIEVAL_PROFILES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "approach",
        (
            "approach invitation notice offer watch wait humor restraint distance",
            "first proximity attention curiosity hesitation ordinary action",
        ),
    ),
    (
        "complication",
        (
            "complication counteroffer resistance impediment asymmetry misunderstanding subtext",
            "refuse evade interrupt challenge tease pressure choice consequence",
        ),
    ),
    (
        "embodied-turn",
        (
            "embodied turn touch contact kiss logistics initiative permission stop answer",
            "breath hand mouth posture sensory reciprocal agency physical change",
        ),
    ),
    (
        "consequence",
        (
            "consequence aftermath recognition changed relationship stopping deferral parting",
            "future choice cost knowledge trust unresolved desire concrete ending",
        ),
    ),
)


def _movement_retrieval_profile(movement: str) -> tuple[str, tuple[str, ...]]:
    """Resolve the loom's natural-language movement onto a stable stage role."""

    lowered = movement.casefold()
    if any(phrase in lowered for phrase in (
        "no kiss occurs", "before any kiss", "without a kiss", "without kissing",
    )):
        # A prohibition is not an embodied-turn instruction.  Treating the
        # token ``kiss`` without its local negation previously made the prompt
        # insert a first-kiss payment immediately above a no-kiss movement.
        return MOVEMENT_RETRIEVAL_PROFILES[1]
    if "livia enters the room" in lowered:
        return MOVEMENT_RETRIEVAL_PROFILES[0]
    if "identifies which one mara selected" in lowered or "second, different inference" in lowered:
        return MOVEMENT_RETRIEVAL_PROFILES[1]
    if "calibration frame" in lowered:
        return MOVEMENT_RETRIEVAL_PROFILES[1]
    if "half-full glass" in lowered or "catering worker" in lowered:
        return (
            "approach",
            MOVEMENT_RETRIEVAL_PROFILES[0][1] + (
                "status service servant maid waiter worker glass cup tray labor acknowledgment host guest conversation",
            ),
        )
    if "live offer or discovery" in lowered or "establish concrete" in lowered:
        return MOVEMENT_RETRIEVAL_PROFILES[0]
    if any(word in lowered for word in (
        "aftermath", "consequence", "ending", "parting", "survives",
        "recognizes mara", "continued engagement",
    )):
        return MOVEMENT_RETRIEVAL_PROFILES[3]
    if any(word in lowered for word in (
        "embodied turn", "bodily action", "wrist contact", "kiss",
        "cue channel", "accuracy falls",
    )):
        return MOVEMENT_RETRIEVAL_PROFILES[2]
    if any(word in lowered for word in (
        "complication", "counteroffer", "resistance", "pressure",
        "startling", "social cost", "refuses to display", "calibration frame",
    )):
        return MOVEMENT_RETRIEVAL_PROFILES[1]
    return MOVEMENT_RETRIEVAL_PROFILES[0]


def retrieve_passages_for_movement(
    cell: BenchmarkCell,
    passages: Sequence[SourcePassage],
    *,
    movement: str,
    count: int,
    graphs: Mapping[str, IntimacySceneGraph],
) -> tuple[SourcePassage, ...]:
    """Retrieve apprenticeship scenes for the present dramatic job.

    The older renderer reused the opening's three sources at every branch.
    That taught one undifferentiated intimacy distribution and encouraged the
    model to complete the kiss during the complication.  This router keeps the
    example count fixed while changing only source identity/order by stage.
    """

    stage, profile_lines = _movement_retrieval_profile(movement)
    status_transaction = (
        "half-full glass" in movement.casefold()
        or "catering worker" in movement.casefold()
    )
    gathering_handoff = "unnamed guests" in movement.casefold()
    livia_entrance = "livia enters the room" in movement.casefold()
    profile_terms = set(_words(" ".join(profile_lines)))
    movement_terms = set(_words(movement))
    target_terms = set(_words(" ".join(cell.story_program))) | profile_terms
    eligible = [
        item for item in passages
        if item.prompt_eligible and item.partition == "profiling" and item.passage_id in graphs
    ]
    scored: list[tuple[float, SourcePassage]] = []
    heat_order = {"none": 0, "charged-restraint": 1, "open-door-nongraphic": 2, "explicit": 3}
    target_heat = heat_order.get(cell.heat_band, 1)
    for item in eligible:
        graph = graphs[item.passage_id]
        graph_text = " ".join((
            graph.emotional_offer, graph.emotional_counteroffer,
            graph.relationship_history, graph.present_stakes,
            " ".join(graph.dialogue_act_sequence),
            " ".join(graph.body_language_counterpoint),
            " ".join(graph.physical_logistics),
            " ".join(graph.agency_actions),
            " ".join(graph.narrative_distance_curve),
            " ".join(graph.sensory_channels),
            graph.relationship_delta, graph.story_state_change,
        ))
        graph_terms = set(_words(graph_text))
        prose_terms = set(_words(item.text))
        stage_match = len(profile_terms & graph_terms) / max(1, len(profile_terms))
        movement_match = len(movement_terms & (graph_terms | prose_terms)) / max(
            1, len(movement_terms)
        )
        broad_match = len(target_terms & (graph_terms | prose_terms)) / max(1, len(target_terms))
        dialogue = min(1.0, (item.text.count('"') + item.text.count("“")) / 20.0)
        agency = min(1.0, len(re.findall(
            r"\b(?:ask|answer|choose|stop|wait|offer|invite|refus|agree|leave|stay)\w*\b",
            graph_text + " " + item.text, re.I,
        )) / 10.0)
        boundary = _source_boundary_quality(item.text)
        function_fit = 0.0
        if status_transaction:
            folded = (graph_text + " " + item.text).casefold()
            service_actor = bool(re.search(
                r"\b(?:servant|maid|waiter|footman|butler|worker|server|staff)\b",
                folded,
            ))
            handled_object = bool(re.search(
                r"\b(?:glass|cup|tray|dish|drink|plate|bottle)\b",
                folded,
            ))
            social_service = bool(re.search(
                r"\b(?:serve|served|service|order|ordered|attend|wait on|"
                r"clear|cleared|fetch|carry|carried|retrieve|labor)\w*\b",
                folded,
            ))
            function_fit = sum((service_actor, handled_object, social_service)) / 3.0
        elif gathering_handoff:
            folded = (graph_text + " " + item.text).casefold()
            social_group = bool(re.search(
                r"\b(?:guests?|people|company|crowd|children|men and women)\b",
                folded,
            ))
            arrival = bool(re.search(
                r"\b(?:arriv|enter|entered|came in|come in|walked in|door (?:opened|was flung)|"
                r"voices?|footsteps?|ushered)\w*\b",
                folded,
            ))
            interruption = bool(re.search(
                r"\b(?:interrupt|suddenly|then there came|looked up|turned|broke in|"
                r"flung open|taken aback)\w*\b",
                folded,
            ))
            function_fit = sum((social_group, arrival, interruption)) / 3.0
        elif livia_entrance:
            folded = (graph_text + " " + item.text).casefold()
            female_arrival = bool(re.search(
                r"\b(?:woman|girl|lady|countess|madame|mrs\.?|miss)\b.{0,220}"
                r"\b(?:enter|entered|arriv|appeared|came in|doorway|door opened)\w*\b|"
                r"\b(?:enter|entered|arriv|appeared|came in|doorway|door opened)\w*\b"
                r".{0,220}\b(?:woman|girl|lady|countess|madame|mrs\.?|miss)\b",
                folded,
                re.S,
            ))
            greeting = bool(re.search(
                r"\b(?:hello|good evening|nice to meet|introduced?|this is|"
                r"held out (?:her|a) hand|shook hands?)\b",
                folded,
            ))
            interruption = bool(re.search(
                r"\b(?:interrupt|before anyone|looked up|turned|suddenly|"
                r"voice spoke|door opened)\w*\b",
                folded,
            ))
            function_fit = sum((female_arrival, greeting, interruption)) / 3.0
        observed_heat = heat_order.get(item.heat_band, 1)
        if cell.cell_id == "fulcrum-s01" and stage != "embodied-turn" and observed_heat > 0:
            continue
        if stage != "embodied-turn" and observed_heat > target_heat:
            continue
        if stage == "embodied-turn":
            heat_fit = 1.0 / (1.0 + abs(observed_heat - min(2, target_heat + 1)))
        else:
            # Explicit examples teach premature payoff in approach/complication
            # and tend to contaminate a restraint scene's aftermath.
            heat_fit = 1.0 / (1.0 + abs(observed_heat - target_heat))
            if observed_heat > target_heat + 1:
                heat_fit *= 0.25
        if status_transaction or gathering_handoff or livia_entrance:
            score = (
                0.15 * stage_match + 0.20 * movement_match + 0.05 * broad_match
                + 0.10 * dialogue + 0.08 * agency + 0.07 * heat_fit
                + 0.05 * boundary + 0.30 * function_fit
            )
        else:
            score = (
                0.26 * stage_match + 0.24 * movement_match + 0.08 * broad_match
                + 0.12 * dialogue + 0.12 * agency + 0.10 * heat_fit
                + 0.08 * boundary
            )
        scored.append((score, item))
    scored.sort(key=lambda value: (-value[0], value[1].passage_id))
    return tuple(item for _, item in scored[:count])


def dwell_map(graph: IntimacySceneGraph) -> str:
    return "\n".join((
        f"Offer (15%): {graph.emotional_offer}",
        f"Counteroffer and resistance (25%): {graph.emotional_counteroffer}",
        "Complication and embodied negotiation (35%): " + "; ".join(graph.body_language_counterpoint),
        f"Consequential turn (15%): {graph.relationship_delta}",
        f"Concrete stopping state (10%): {graph.story_state_change}",
    ))


def movement_function_score(text: str, movement: str) -> float:
    """Measure whether prose contains the movement's causal mechanism.

    This is an admission check for apprenticeship material, not a literary
    score.  It prevents lexical near-matches from becoming false lessons.
    """

    lowered = movement.casefold()
    if "unnamed guests" in lowered:
        signals = (
            bool(re.search(
                r"\b(?:voices?|guests?|people|company|crowd|children|footsteps?)\b",
                text, re.I,
            )),
            bool(re.search(
                r"\b(?:arriv|enter|came in|come in|walked in|stepped in|"
                r"door|threshold|outside)\w*\b",
                text, re.I,
            )),
            bool(re.search(
                r"\b(?:interrupt|suddenly|then there came|looked up|turned|"
                r"opened|flung|called)\w*\b",
                text, re.I,
            )),
        )
        return sum(signals) / len(signals)
    if "catering worker" in lowered:
        service_actor = r"(?:servant|maid|waiter|footman|butler|worker|server|staff)"
        service_response = (
            r"(?:came|approached|withdrew|served|fill(?:ed)?|cleared|fetched|carried|"
            r"retrieved|collected|picked up|brought|waited on)"
        )
        signals = (
            bool(re.search(
                r"\b(?:glass|cup|tray|dish|drink|plate|bottle)\b",
                text, re.I,
            )),
            bool(re.search(
                rf"\b{service_actor}\b.{{0,140}}\b{service_response}\b|"
                rf"\b{service_response}\b.{{0,140}}\b{service_actor}\b",
                text, re.I | re.S,
            )),
            bool(re.search(
                rf"\b(?:beckon|signal|call|order|ask|without (?:a word|acknowledg(?:e?ment|ing)|looking)|"
                rf"silent(?:ly)?|hired|social inferior)\w*\b.{{0,180}}\b{service_actor}\b|"
                rf"\b{service_actor}\b.{{0,180}}\b(?:beckon|signal|call|order|ask|without "
                rf"(?:a word|acknowledg(?:e?ment|ing)|looking)|silent(?:ly)?|hired|social inferior)\w*\b",
                text, re.I | re.S,
            )),
        )
        return sum(signals) / len(signals)
    if "half-full glass" in lowered:
        signals = (
            bool(re.search(r"\b(?:glass|cup|flute)\b", text, re.I)),
            bool(re.search(
                r"\b(?:leave|left|set|put|place|abandon)\w*\b.{0,120}"
                r"\b(?:glass|cup|flute)\b|\b(?:glass|cup|flute)\b.{0,120}"
                r"\b(?:leave|left|set|put|place|abandon)\w*\b",
                text, re.I | re.S,
            )),
            bool(re.search(
                r"\b(?:young|younger|brown-haired)\s+(?:fellow|man|guest)\b",
                text, re.I,
            )),
        )
        return sum(signals) / len(signals)
    if "livia enters the room" in lowered:
        signals = (
            bool(re.search(
                r"\b(?:woman|girl|lady|countess|madame|mrs\.?|miss)\b",
                text,
                re.I,
            )),
            bool(re.search(
                r"\b(?:enter|entered|arriv|appeared|came in|doorway|door opened|"
                r"voice spoke)\w*\b",
                text,
                re.I,
            )),
            bool(re.search(
                r"\b(?:hello|good evening|nice to meet|introduced?|this is|"
                r"held out (?:her|a) hand|shook hands?)\b",
                text,
                re.I,
            )),
        )
        return sum(signals) / len(signals)
    return 0.0


def source_movement_excerpt(
    text: str, movement: str, *, minimum_words: int, maximum_words: int,
) -> str:
    """Select an exact, complete-paragraph source movement near the target dose.

    Whole 800-word source scenes taught the base model to defer a 200-word
    payment.  This selector changes no prose: it chooses a contiguous run of
    original paragraphs whose action vocabulary and final paragraph best match
    the present movement.
    """

    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()]
    if not paragraphs:
        raise ValueError("source passage has no prose paragraphs")
    movement_terms = set(_words(movement))
    lowered_movement = movement.casefold()
    endpoint_terms = set(_words(
        "arrive enter gather interrupt answer turn change leave stop consequence "
        "voices guests people footsteps doorway"
    ))
    candidates: list[tuple[float, int, int, str]] = []
    for start in range(len(paragraphs)):
        words = 0
        for end in range(start, len(paragraphs)):
            words += len(_words(paragraphs[end]))
            if words > maximum_words:
                break
            if words < minimum_words:
                continue
            excerpt = "\n\n".join(paragraphs[start : end + 1])
            prose_terms = set(_words(excerpt))
            final_terms = set(_words(paragraphs[end]))
            movement_fit = len(movement_terms & prose_terms) / max(1, len(movement_terms))
            endpoint_fit = len(endpoint_terms & final_terms) / max(1, len(endpoint_terms))
            dose_fit = 1.0 - abs(words - (minimum_words + maximum_words) / 2) / maximum_words
            function_fit = movement_function_score(excerpt, movement)
            if function_fit:
                score = (
                    0.35 * movement_fit + 0.35 * function_fit
                    + 0.20 * endpoint_fit + 0.10 * dose_fit
                )
            else:
                score = 0.60 * movement_fit + 0.25 * endpoint_fit + 0.15 * dose_fit
            candidates.append((score, start, end, excerpt))
    if not candidates:
        # Preserve exact source bytes even when a source uses giant paragraphs.
        words = _words(text)
        if len(words) < minimum_words:
            return text.strip()
        sentence_ends = [match.end() for match in re.finditer(r"[.!?](?:[\"”’])?(?=\s)", text)]
        eligible = [end for end in sentence_ends if minimum_words <= len(_words(text[:end])) <= maximum_words]
        if not eligible:
            raise ValueError("source passage has no complete movement-sized excerpt")
        return text[:eligible[-1]].strip()
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    return candidates[0][3]


def scene_graph_documentary(graph: IntimacySceneGraph) -> str:
    """Render an internal graph as ordinary editorial notes for a base model."""

    return "\n".join((
        f"Emotional offer: {graph.emotional_offer}",
        f"Counteroffer: {graph.emotional_counteroffer}",
        f"History in the room: {graph.relationship_history}",
        f"Present stakes: {graph.present_stakes}",
        "Conversation moves: " + "; ".join(graph.dialogue_act_sequence),
        "Body-language counterpoint: " + "; ".join(graph.body_language_counterpoint),
        "Physical logistics: " + "; ".join(graph.physical_logistics),
        "Agency turns: " + "; ".join(graph.agency_actions),
        "Narrative-distance curve: " + "; ".join(graph.narrative_distance_curve),
        "Sensory channels: " + "; ".join(graph.sensory_channels),
        f"Relationship change: {graph.relationship_delta}",
        f"Story-state payment: {graph.story_state_change}",
    ))


def split_manuscript_runway(
    manuscript: str, *, maximum_tail_words: int = 90,
) -> tuple[str, str]:
    """Keep control close to sampling while ending on authentic manuscript.

    Base continuations overwhelmingly follow their nearest prose.  Putting a
    movement ledger before the entire manuscript made its causal instruction
    hundreds of tokens more distant than the awkward-handshake ending.  This
    returns an exact paragraph-aligned tail so a renderer can place the ledger
    immediately before those final model-authored bytes without inventing a
    prose bridge.
    """

    paragraphs = [item for item in re.split(r"(\n\s*\n)", manuscript) if item]
    prose_indices = [
        index for index, item in enumerate(paragraphs) if item.strip()
        and not re.fullmatch(r"\n\s*\n", item)
    ]
    if not prose_indices:
        return "", manuscript
    tail_start = prose_indices[-1] if len(prose_indices) >= 2 else 0
    tail = "".join(paragraphs[tail_start:]).strip()
    if len(_words(tail)) > maximum_tail_words:
        paragraph_start = manuscript.rfind(tail)
        starts = [paragraph_start]
        for match in re.finditer(r"[.!?](?:[\"”’])?\s+", tail):
            starts.append(paragraph_start + match.end())
        candidates = [
            start for start in starts
            if 12 <= len(_words(manuscript[start:])) <= maximum_tail_words
        ]
        if not candidates:
            return "", manuscript
        tail_start = min(candidates)
        head = manuscript[:tail_start].strip()
        tail = manuscript[tail_start:].strip()
        return head, tail
    head = "".join(paragraphs[:tail_start]).strip()
    return head, tail


def _story_card(cell: BenchmarkCell, movement: str = "") -> str:
    lines = [
        f"Mode: {cell.intimacy_mode}; heat: {cell.heat_band}.",
        "Story facts:",
        *(f"- {item}" for item in cell.story_program),
        "Boundaries:",
        *(f"- {item}" for item in cell.hard_constraints),
    ]
    if movement:
        lines.extend(("Current movement:", movement))
    return "\n".join(lines)


def _behavioral_story_card(cell: BenchmarkCell, movement: str = "") -> str:
    """Translate evaluator abstractions into observable manuscript events."""

    programs = {
        "charged-restraint": (
            "Adult Mara and Jonah leave a bad Fulcrum lab session on foot.",
            "Jonah holds out an open hand and waits without explaining Mara to herself.",
            "Mara takes his hand, later closes the distance, and initiates the kiss.",
            "When Mara says wait and leans back, Jonah releases her and gives her room before speaking.",
            "They part still wanting one another, with one specific reason to meet again.",
        ),
        "married-explicit": (
            "Adult spouses Esther and Simon sit together with a novel after a failed rescue separated them.",
            "A joke about the book lets Esther ask the question Simon has avoided.",
            "Simon answers with a concrete fact rather than a reassurance; Esther answers with a touch he can accept or decline.",
            "Their physical closeness alters what each is willing to admit about the rescue.",
            "Both initiate, answer, and adjust; the encounter pays the argument instead of interrupting it.",
        ),
        "institutional-pressure-control": (
            "After alignment, Mara needs several uninterrupted hours and must leave for her brother.",
            "Livia offers a warm drink while quietly arranging Mara's time for her.",
            "Jonah notices the arrangement and asks one question that makes its cost visible.",
            "Mara changes the practical arrangement herself; Livia must either accept the change or expose the pressure.",
            "The open door, cup, clock, and people standing in Mara's path carry the pressure; bodies remain incidental.",
        ),
        "fulcrum-s01": cell.story_program,
    }
    boundary_translations = {
        "close third Mara": "Narrate only what Mara perceives, remembers, infers, and feels.",
        "no consummation": "End with the characters clothed and physically separate.",
        "no graphic anatomy": "Use selective touch, breath, balance, sound, and temperature rather than anatomical inventory.",
        "ambiguous supernatural status": "Every unusual cue on the page retains at least one ordinary sensory or behavioral explanation.",
        "ordinary and extraordinary explanations remain simultaneously live": "End with evidence that supports two incompatible explanations without naming either one as true.",
        "agency remains visible": "Show offers, answers, pauses, and changed contact as observable actions.",
        "all intimate characters are adults": "Every participant is explicitly an adult.",
        "no erotic escalation": "Keep attraction and sexual contact absent; carry pressure through timing, objects, and movement.",
        "no kiss": "The characters do not kiss.",
        "care remains genuinely caring and controlling": "Livia solves one real bodily need while making Mara's preferred practical action harder.",
    }
    lines = [
        f"Mode: {cell.intimacy_mode}; heat: {cell.heat_band}.",
        "Observable story events:",
        *(f"- {item}" for item in programs.get(cell.cell_id, cell.story_program)),
        "Observable boundaries:",
        *(f"- {boundary_translations.get(item, item)}" for item in cell.hard_constraints),
    ]
    if movement:
        lines.extend(("Current movement:", movement))
    return "\n".join(lines)


def render_runway_prompt(cell: BenchmarkCell) -> str:
    """A control-only prompt whose response, not the prompt, supplies prose."""

    return (
        "STORY CARD\n" + _story_card(cell) +
        "\n\nWrite only third-person narrative manuscript prose, never a screenplay, "
        "outline, label, or numbered list. Open at the beginning of the first listed "
        "story fact; do not jump ahead to a later beat. Write 80–140 words. Begin "
        "inside concrete action or dialogue; establish character-specific pressure "
        "without resolving it.\n\n"
        "MANUSCRIPT OPENING\n"
    )


def render_source_conditioned_runway_prompt(
    cell: BenchmarkCell,
    passages: Sequence[SourcePassage],
    *,
    source_count: int = 5,
    graphs: Mapping[str, IntimacySceneGraph] | None = None,
) -> tuple[str, tuple[str, ...]]:
    """Begin a new book after a natural anthology apprenticeship."""

    selected = () if cell.cell_id == "institutional-pressure-control" else retrieve_passages(
        cell, passages, count=source_count, graphs=graphs,
    )
    title = "FULCRUM" if cell.cell_id != "married-explicit" else "THE LONG WAY HOME"
    chunks = ["A note for the forthcoming chapter\n\n" + _behavioral_story_card(
        cell, "Open at the first listed event and dwell before its consequential turn."
    )]
    for passage in reversed(selected):
        chunks.append(passage.text.strip() + "\n\n* * *")
    chunks.append(f"{title}\n\nChapter One")
    return "\n\n".join(chunks).rstrip() + "\n\n", tuple(
        item.passage_id for item in selected
    )


def render_bookfront_runway_prompt(
    cell: BenchmarkCell,
    passages: Sequence[SourcePassage],
    *,
    source_count: int = 5,
    graphs: Mapping[str, IntimacySceneGraph] | None = None,
) -> tuple[str, tuple[str, ...]]:
    """Reset the source distribution with ordinary front matter, not a dossier."""

    selected = () if cell.cell_id == "institutional-pressure-control" else retrieve_passages(
        cell, passages, count=source_count, graphs=graphs,
    )
    fronts = {
        "charged-restraint": (
            "FULCRUM", "Mara Voss — an adult research fellow\nJonah Vale — her adult colleague",
            "After the Late Session",
        ),
        "married-explicit": (
            "THE LONG WAY HOME", "Esther — Simon's adult wife\nSimon — Esther's adult husband",
            "The Failed Rescue",
        ),
        "institutional-pressure-control": (
            "FULCRUM", "Mara Voss — an adult research fellow\nLivia — her mentor\nJonah Vale — her adult colleague",
            "The Doorway Rule",
        ),
        "fulcrum-s01": (
            "FULCRUM", "Mara Voss — an adult newcomer\nLivia — a gifted reader of people\nJonah Vale — an adult researcher",
            "The Calibration Game",
        ),
    }
    title, cast, chapter = fronts[cell.cell_id]
    chunks = ["A note for the forthcoming chapter\n\n" + _behavioral_story_card(
        cell, "Open at the first listed event and dwell before its consequential turn."
    )]
    for passage in reversed(selected):
        chunks.append(passage.text.strip() + "\n\n* * *")
    chunks.append(
        f"{title}\n\nA novel\n\nPrincipal characters\n{cast}\n\n"
        f"Contents\n1. {chapter}\n\nChapter One\n{chapter}"
    )
    return "\n\n".join(chunks).rstrip() + "\n\n", tuple(
        item.passage_id for item in selected
    )


def _bookfront_chapter_synopsis(cell: BenchmarkCell) -> str:
    """Place target causality beside the manuscript boundary in book-like form.

    The earlier natural-book arm put a useful chapter note thousands of tokens
    before the blank chapter.  The base model therefore inherited local voice
    from the sources but inferred the new chapter almost entirely from its title.
    This is a target-density mutation, not manuscript prose: it uses an ordinary
    detailed-contents entry and leaves the chapter itself completely blank.
    """

    synopsis = {
        "charged-restraint": (
            "After a bad late-night Fulcrum lab session, adult research fellows "
            "Mara Voss and Jonah Vale walk home. Jonah offers an open hand and "
            "waits without interpreting her. Mara chooses his hand and later the "
            "kiss. When she says wait, he releases her before speaking. They part "
            "still wanting each other and with a specific reason to meet again."
        ),
        "married-explicit": (
            "After a failed rescue separated adult spouses Esther and Simon, a "
            "joke over their novel opens the question he has avoided. He answers "
            "with one concrete fact; her answering touch can be refused. Their "
            "mutually chosen physical closeness changes what each can admit about "
            "the rescue, and the intimacy pays rather than suspends the argument."
        ),
        "institutional-pressure-control": (
            "After alignment, Mara needs several uninterrupted hours and must "
            "leave for her brother. Livia provides a genuinely useful warm drink "
            "while quietly arranging Mara's time. Jonah asks one question that "
            "makes the cost visible. Mara changes the arrangement herself; the "
            "open door, cup, clock, and bodies in her path carry nonsexual pressure."
        ),
        "fulcrum-s01": (
            "At Fulcrum's calibration game, adult newcomer Mara watches Livia "
            "make uncannily accurate social reads and Jonah decline to perform. "
            "A charged wrist-contact exercise changes Mara's attention. Her own "
            "control collapses much of the apparent miracle but leaves a smaller "
            "ordinary-or-extraordinary mystery and a freely chosen reason to stay."
        ),
    }
    return synopsis[cell.cell_id]


def render_bookfront_synopsis_runway_prompt(
    cell: BenchmarkCell,
    passages: Sequence[SourcePassage],
    *,
    source_count: int = 5,
    graphs: Mapping[str, IntimacySceneGraph] | None = None,
) -> tuple[str, tuple[str, ...]]:
    """Natural bookfront with a near-boundary detailed-contents control."""

    prompt, source_ids = render_bookfront_runway_prompt(
        cell, passages, source_count=source_count, graphs=graphs,
    )
    chapter_markers = {
        "charged-restraint": "Chapter One\nAfter the Late Session\n\n",
        "married-explicit": "Chapter One\nThe Failed Rescue\n\n",
        "institutional-pressure-control": "Chapter One\nThe Doorway Rule\n\n",
        "fulcrum-s01": "Chapter One\nThe Calibration Game\n\n",
    }
    marker = chapter_markers[cell.cell_id]
    if not prompt.endswith(marker):
        raise AssertionError("bookfront prompt ended at an unexpected manuscript boundary")
    detailed_contents = (
        "Detailed contents\n\n1. "
        + marker.splitlines()[1]
        + "\n"
        + _bookfront_chapter_synopsis(cell)
        + "\n\n"
    )
    return prompt[: -len(marker)] + detailed_contents + marker, source_ids


def render_graph_paired_bookfront_runway_prompt(
    cell: BenchmarkCell,
    passages: Sequence[SourcePassage],
    *,
    source_count: int = 4,
    graphs: Mapping[str, IntimacySceneGraph] | None = None,
) -> tuple[str, tuple[str, ...]]:
    """Teach scene-plan-to-prose conversion, then open a natural target book."""

    graph_map = dict(graphs or {})
    selected = retrieve_passages(
        cell, passages, count=source_count, graphs=graph_map,
    )
    if any(item.passage_id not in graph_map for item in selected):
        missing = [item.passage_id for item in selected if item.passage_id not in graph_map]
        raise ValueError("graph-paired runway requires annotated sources: " + ", ".join(missing))
    chunks = ["STUDIES IN SCENE CONSTRUCTION"]
    for index, passage in enumerate(reversed(selected), 1):
        chunks.append(
            f"Study {index}\n\nDramatic map\n{dwell_map(graph_map[passage.passage_id])}"
            f"\n\nManuscript\n{passage.text.strip()}"
        )
    # Reuse the natural blank-book boundary, but keep the detailed contents
    # adjacent to it so the examples teach the model how to realize that map.
    target, _ = render_bookfront_synopsis_runway_prompt(
        cell, (), source_count=0, graphs=graph_map,
    )
    # The empty-source renderer begins with a distant editorial note.  The
    # detailed contents already contains the same target causality, so remove
    # that redundant instruction-like preamble from this paired recipe.
    title_at = target.find("FULCRUM\n\nA novel")
    if cell.cell_id == "married-explicit":
        title_at = target.find("THE LONG WAY HOME\n\nA novel")
    if title_at < 0:
        raise AssertionError("could not locate natural target book boundary")
    chunks.append(target[title_at:].rstrip())
    return "\n\n* * *\n\n".join(chunks).rstrip() + "\n\n", tuple(
        item.passage_id for item in selected
    )


def _bookfront_canon_page(cell: BenchmarkCell) -> str:
    pages = {
        "charged-restraint": (
            "Setting\nContemporary Northern California. Fulcrum is a private "
            "psychotechnology institute studying attention and nonverbal cue-reading. "
            "Mara and Jonah are adult research colleagues who have never kissed. "
            "Narration stays with Mara's perceptions. Their walk begins immediately "
            "after a socially punishing human-behavior experiment; this chapter "
            "contains their first mutually chosen kiss."
        ),
        "married-explicit": (
            "Setting\nA contemporary home after a failed rescue. Esther and Simon are "
            "adult spouses with an established sexual language. Narration stays with "
            "Esther's perceptions. The rescue's concrete failure remains present "
            "throughout their mutually chosen intimacy and changes what they decide."
        ),
        "institutional-pressure-control": (
            "Setting\nContemporary Fulcrum, a private psychotechnology institute "
            "studying attention and nonverbal cue-reading. Narration stays with Mara. "
            "Livia's care is useful and controlling; pressure is carried by the open "
            "door, warm cup, clock, and practical choices, without sexual contact."
        ),
        "fulcrum-s01": (
            "Setting\nContemporary Fulcrum, a private psychotechnology institute "
            "studying attention and nonverbal cue-reading. Adult newcomer Mara is the "
            "only viewpoint. Livia's accuracy retains ordinary cue-reading explanations; "
            "Jonah's restraint costs him status and changes Mara's attention."
        ),
    }
    return pages[cell.cell_id]


def _bookfront_character_page(cell: BenchmarkCell) -> str:
    """Compact natural-book characterization, never manuscript prose."""

    if cell.cell_id != "fulcrum-s01":
        return ""
    return (
        "Principal characters\n"
        "Mara Vale, twenty-two, an infrastructure-security engineer: sheltered, "
        "technically formidable, observant, and dryly funny. She wants difficult "
        "truth and fellowship, but resents any claim to know her without permission.\n"
        "Adrian Voss, Fulcrum's polished founder: he makes status, method, and "
        "recruitment feel like hospitality.\n"
        "Livia Sloane, Fulcrum's gifted reader of posture, voice, and timing: her "
        "care is real, her skill is real, and she wants ownership of the pace.\n"
        "Jonah Reed, a hardware-security researcher: playful and socially fluent; "
        "he notices when a person becomes material for an audience and sometimes "
        "pays a public cost rather than perform her."
    )


def _movement_canon_page(cell: BenchmarkCell, movement: str) -> str:
    """Avoid priming not-yet-present characters in base generation prompts."""

    if cell.cell_id != "fulcrum-s01":
        return _bookfront_canon_page(cell)
    if "Livia" in movement:
        return _bookfront_canon_page(cell)
    return (
        "Setting\nContemporary Fulcrum, a private psychotechnology institute "
        "studying attention and nonverbal cue-reading. Adult newcomer Mara is the "
        "only viewpoint. Every unusual inference retains an ordinary sensory or "
        "behavioral explanation. Restraint and refusal can carry social cost."
    )


def _movement_character_page(
    cell: BenchmarkCell, manuscript: str, movement: str,
) -> str:
    """Describe only characters present now or entering in this movement."""

    if cell.cell_id != "fulcrum-s01":
        return ""
    lower = manuscript.casefold()
    lines = [
        "Principal characters",
        "Mara Vale, twenty-two, an infrastructure-security engineer: sheltered, "
        "technically formidable, observant, and dryly funny.",
    ]
    if "jonah" in lower or "Jonah" in movement:
        lines.append(
            "Jonah Reed, a hardware-security researcher: playful and socially "
            "fluent; he notices when a person becomes material for an audience."
        )
    if "adrian" in lower or "Adrian" in movement:
        lines.append(
            "Adrian Voss, Fulcrum's polished founder: he makes status, method, "
            "and recruitment feel like hospitality."
        )
    if "livia" in lower or "Livia" in movement:
        lines.append(
            "Livia Sloane, Fulcrum's gifted reader of posture, voice, and timing: "
            "her care is real, her skill is real, and she wants ownership of the pace."
        )
    return "\n".join(lines)


def render_graph_paired_canon_bookfront_runway_prompt(
    cell: BenchmarkCell,
    passages: Sequence[SourcePassage],
    *,
    source_count: int = 4,
    graphs: Mapping[str, IntimacySceneGraph] | None = None,
) -> tuple[str, tuple[str, ...]]:
    """Graph-paired apprenticeship with a near-boundary natural canon page."""

    prompt, source_ids = render_graph_paired_bookfront_runway_prompt(
        cell, passages, source_count=source_count, graphs=graphs,
    )
    needle = "A novel\n\nPrincipal characters"
    if needle not in prompt:
        raise AssertionError("graph-paired bookfront lacks target title page")
    prompt = prompt.replace(
        needle, "A novel\n\n" + _bookfront_canon_page(cell) + "\n\nPrincipal characters", 1,
    )
    return prompt, source_ids


def _bookfront_continuity_page(cell: BenchmarkCell) -> str:
    """Natural-book continuity dense enough to constrain an unaligned base model.

    This is story metadata, never manuscript language.  It deliberately states
    negative history as ordinary continuity because the charged-restraint
    calibration repeatedly invented ex-lover backstory when given only
    ``have never kissed``.
    """

    pages = {
        "charged-restraint": (
            "Continuity\nThe chapter opens outdoors on Fulcrum's front steps at "
            "night, at the instant the late session ends. Mara and Jonah met only "
            "three weeks ago. They have never dated, kissed, had sex, declared love, "
            "or broken up. They live separately and are walking, not driving. Mara "
            "is angry and unsettled by the group experiment. Jonah neither diagnoses "
            "her nor touches her without a visible invitation. Ordinary posture, "
            "breath, timing, and voice carry what they do not explain aloud. Mara "
            "chooses each change in contact. Their first kiss stops by mutual choice "
            "while both still want it; neither promises a relationship tonight."
        ),
        "married-explicit": (
            "Continuity\nThe chapter opens in Esther and Simon's contemporary home "
            "after a failed rescue. They are adult spouses. Esther remains the only "
            "viewpoint. Both initiate and can stop every change in contact. Physical "
            "detail remains spatially clear and keeps the rescue's failure active in "
            "their choices rather than pausing the plot."
        ),
        "institutional-pressure-control": (
            "Continuity\nThe chapter opens in a Fulcrum meeting room at night. Mara "
            "remains the only viewpoint. Livia uses practical care, timing, and the "
            "open doorway to narrow Mara's options without sexual contact, attraction, "
            "or erotic metaphor. Mara makes one concrete boundary choice."
        ),
        "fulcrum-s01": (
            "Continuity\nThe chapter opens as adult newcomer Mara arrives at the "
            "contemporary Northern California compound for the first time. Mara is "
            "the only viewpoint. No one has supernatural powers; skilled cue-reading "
            "remains distinguishable from interpretation. Jonah's refusal to perform "
            "costs him status and changes what Mara notices about him."
        ),
    }
    return pages[cell.cell_id]


def _bookfront_invariant_page(cell: BenchmarkCell) -> str:
    """Continuity visible at each branch without disclosing future beats."""

    pages = {
        "charged-restraint": (
            "Continuity\nThe chapter is outdoors at night immediately after a "
            "socially punishing Fulcrum session. Mara and Jonah met three weeks ago. "
            "They have never dated, kissed, had sex, declared love, or broken up. "
            "They live separately. Narration stays inside Mara's perceptions. "
            "Ordinary posture, breath, timing, voice, and physical choices carry "
            "what neither explains aloud. Jonah does not diagnose Mara or touch her "
            "without a visible invitation. Mara chooses each change in contact."
        ),
        "married-explicit": (
            "Continuity\nEsther and Simon are adult spouses in their contemporary "
            "home after a failed rescue. Esther is the only viewpoint. Both can "
            "initiate or stop each change in contact. The rescue's concrete failure "
            "remains active in what they notice and choose."
        ),
        "institutional-pressure-control": (
            "Continuity\nThe chapter is in a Fulcrum meeting room at night. Mara is "
            "the only viewpoint. Livia's practical care and timing narrow choices "
            "without sexual contact, attraction, or erotic metaphor."
        ),
        "fulcrum-s01": (
            "Continuity\nAdult newcomer Mara is at the contemporary Northern "
            "California Fulcrum compound for the first time; she has never visited "
            "or interviewed here before. The unnamed blond man presently on the "
            "couch is adult Jonah Reed, though Mara has not learned his name. Adrian "
            "has not entered. Mara is the only viewpoint. Unusual "
            "cue-reading always retains ordinary sensory and behavioral explanations."
        ),
    }
    return pages[cell.cell_id]


def _movement_payment_page(cell: BenchmarkCell, movement: str) -> str:
    """Expose only the current beat's payment, never the whole endpoint ledger."""

    stage, _ = _movement_retrieval_profile(movement)
    if cell.cell_id == "charged-restraint":
        payments = {
            "approach": (
                "Present movement payment\nDesire and an impediment become concrete. "
                "This movement ends before any kiss, declaration, or indoor interlude."
            ),
            "complication": (
                "Present movement payment\nA characteristic coping move backfires and "
                "changes the terms of the walk. No kiss occurs in this movement."
            ),
            "embodied-turn": (
                "Present movement payment\nMara visibly initiates their first kiss. "
                "She chooses the stop while desire remains active; Jonah releases her immediately."
            ),
            "consequence": (
                "Present movement payment\nNo second kiss occurs. The chosen stop changes "
                "trust and produces one concrete future possibility without resolving the relationship."
            ),
        }
        return payments[stage]
    if cell.cell_id == "institutional-pressure-control":
        return "Present movement payment\nPressure remains entirely nonsexual and changes one practical choice."
    if cell.cell_id == "fulcrum-s01":
        lowered = movement.casefold()
        payments = (
            (
                "first dyadic contact",
                "Mara and Jonah complete one imperfect first exchange. Their attention "
                "changes, but neither trust nor the larger welcome is resolved.",
            ),
            (
                "unnamed guests",
                "Arriving guests interrupt and reframe Mara's contact with Jonah. "
                "Among them, a distinct brown-haired visiting fellow is already carrying "
                "a glass while absorbed in an important conversation. Reach that "
                "visible state within eighty words. End immediately after Mara has "
                "located the glass carrier in the room, before he leaves it.",
            ),
            (
                "half-full glass",
                "The brown-haired visiting fellow leaves a half-full glass against "
                "the wall while his conversation continues. The object and his "
                "assumption that someone else will handle it remain spatially clear. "
                "End before anyone retrieves it.",
            ),
            (
                "older catering worker",
                "A previously unseen older catering worker retrieves the abandoned "
                "glass without acknowledgment. Mara notices who assumes whose labor. "
                "End on that recognition before anyone makes it a lesson.",
            ),
            (
                "calibration frame",
                "Adrian turns Mara's live observation into a nonverbal calibration "
                "game through dialogue and action. Mara chooses to participate while "
                "remaining uncertain what the exercise can prove.",
            ),
            (
                "two startling",
                "Livia makes two accurate reads from observable behavior. Jonah declines "
                "to perform Mara for the room and pays a visible social cost.",
            ),
            (
                "mutually chosen wrist contact",
                "Mara and Livia choose wrist contact together. Attraction changes Mara's "
                "attention without collapsing either woman's agency.",
            ),
            (
                "alters one cue channel",
                "Mara quietly changes one cue channel and Livia's accuracy falls. "
                "Observation, interpretation, and mechanism remain distinct.",
            ),
            (
                "smaller ambiguous result",
                "A smaller result remains unexplained. Jonah recognizes Mara's control; "
                "she freely chooses to continue at Fulcrum.",
            ),
        )
        for marker, payment in payments:
            if marker in lowered:
                return f"Present movement payment\n{payment}"
        raise ValueError("unknown Fulcrum S01 movement payment")
    return "Present movement payment\nThe current action must change knowledge, trust, or choice before it ends."


def _generation_continuity_page(cell: BenchmarkCell, manuscript: str) -> str:
    """Compile continuity facts from the exact manuscript boundary.

    Static bookfront prose must not contradict a fact the base model has just
    written.  This page contains state only; the current movement's desired
    change belongs exclusively to ``_movement_payment_page``.
    """

    if cell.cell_id != "fulcrum-s01":
        return _bookfront_invariant_page(cell)
    lower = manuscript.casefold()
    knows_jonah = bool(re.search(r"\bjonah\b", lower))
    adrian_present = bool(re.search(r"\badrian(?:\s+voss)?\b", lower))
    livia_present = bool(re.search(r"\blivia(?:\s+sloane)?\b", lower))
    identity = (
        "The blond man from the couch is adult Jonah Reed, and Mara now knows his name."
        if knows_jonah else
        "The unnamed blond man on the couch is adult Jonah Reed; Mara has not learned his name."
    )
    present_named = []
    if adrian_present:
        present_named.append("Adrian has entered the gathering.")
    if livia_present:
        present_named.append("Livia has joined the gathering.")
    named_state = " ".join(present_named)
    return (
        "Continuity\nAdult newcomer Mara is at the contemporary Northern California "
        "Fulcrum compound for the first time; she has never visited or interviewed "
        f"here before. {identity} {named_state} Mara is the only viewpoint. "
        "Unusual cue-reading always retains ordinary sensory and behavioral explanations."
    )


def render_graph_paired_continuity_bookfront_runway_prompt(
    cell: BenchmarkCell,
    passages: Sequence[SourcePassage],
    *,
    source_count: int = 4,
    graphs: Mapping[str, IntimacySceneGraph] | None = None,
) -> tuple[str, tuple[str, ...]]:
    """Graph-paired apprenticeship plus a stronger natural continuity page."""

    prompt, source_ids = render_graph_paired_canon_bookfront_runway_prompt(
        cell, passages, source_count=source_count, graphs=graphs,
    )
    needle = _bookfront_canon_page(cell)
    if needle not in prompt:
        raise AssertionError("graph-paired canon bookfront lacks canon page")
    prompt = prompt.replace(
        needle, needle + "\n\n" + _bookfront_continuity_page(cell), 1,
    )
    return prompt, source_ids


def render_graph_paired_named_continuity_bookfront_runway_prompt(
    cell: BenchmarkCell,
    passages: Sequence[SourcePassage],
    *,
    source_count: int = 4,
    graphs: Mapping[str, IntimacySceneGraph] | None = None,
) -> tuple[str, tuple[str, ...]]:
    """Expose the author prior while holding source and target bytes fixed."""

    prompt, source_ids = render_graph_paired_continuity_bookfront_runway_prompt(
        cell, passages, source_count=source_count, graphs=graphs,
    )
    needle = "A novel\n\nSetting"
    if needle not in prompt:
        raise AssertionError("named continuity bookfront lacks title boundary")
    return prompt.replace(needle, "A novel by Diana Gabaldon\n\nSetting", 1), source_ids


def render_parallel_book_continuity_runway_prompt(
    cell: BenchmarkCell,
    passages: Sequence[SourcePassage],
    *,
    source_count: int = 3,
    graphs: Mapping[str, IntimacySceneGraph] | None = None,
) -> tuple[str, tuple[str, ...]]:
    """Natural n-shot ``contents -> chapter`` apprenticeship for base models.

    Unlike the documentary graph recipes, every example and the target share
    the same visible book grammar.  The prose remains raw source material and
    the target still ends on a blank manuscript boundary.
    """

    graph_map = dict(graphs or {})
    selected = retrieve_passages(
        cell, passages, count=source_count, graphs=graph_map,
    )
    missing = [item.passage_id for item in selected if item.passage_id not in graph_map]
    if missing:
        raise ValueError("parallel-book runway requires annotated sources: " + ", ".join(missing))
    chunks: list[str] = []
    # Retrieval is near-first.  Present broad-to-near so the closest passage
    # supplies the immediate continuation prior.
    for index, passage in enumerate(reversed(selected), 1):
        graph = graph_map[passage.passage_id]
        chunks.append(
            f"SCENE BOOK {index}\n\nDetailed contents\n{dwell_map(graph)}"
            f"\n\nChapter One\n{passage.text.strip()}"
        )
    titles = {
        "charged-restraint": ("FULCRUM", "After the Late Session"),
        "married-explicit": ("THE LONG WAY HOME", "After the Rescue"),
        "institutional-pressure-control": ("FULCRUM", "The Open Door"),
        "fulcrum-s01": ("FULCRUM", "Arrival"),
    }
    title, chapter = titles[cell.cell_id]
    opening_contents = {
        "charged-restraint": (
            "Arrival and disturbance (25%): Mara emerges into the night carrying one concrete disturbance from the experiment.\n"
            "Offer (35%): Jonah's behavior creates a live offer without interpreting her.\n"
            "Attention change (30%): Mara notices one physical particular and chooses whether to answer.\n"
            "Stopping state (10%): End on the unanswered or newly answered offer, before any kiss or declaration."
        ),
        "married-explicit": (
            "Failed routine (35%): The rescue failure is present through a concrete object or interrupted domestic action.\n"
            "Offer (35%): One spouse makes an emotionally legible but revocable physical offer.\n"
            "Counteroffer (20%): The other alters its terms rather than merely accepting.\n"
            "Stopping state (10%): End before intimacy resolves the argument."
        ),
        "institutional-pressure-control": (
            "Practical care (40%): Livia provides something useful that Mara did not request.\n"
            "Hidden cost (40%): The arrangement quietly narrows Mara's available time or exit.\n"
            "Stopping state (20%): Mara notices one concrete cost; no attraction or sexual contact occurs."
        ),
        "fulcrum-s01": (
            "Arrival (20%): A rideshare leaves adult newcomer Mara with one suitcase at Fulcrum's redwood-and-glass Northern California compound before an evening welcome.\n"
            "Beauty and asymmetry (45%): A young fellow leaves a half-full glass on a low wall while continuing an important conversation; an older catering worker retrieves it without being acknowledged. Mara notices the transaction.\n"
            "Institutional turn (25%): Adrian welcomes Mara into a place that calls itself informal.\n"
            "Stopping state (10%): End with Mara choosing to follow Adrian while retaining the glass transaction as an unanswered question."
        ),
    }
    target = (
        f"{title}\n\nA novel\n\n"
        f"{_bookfront_canon_page(cell).replace('; this chapter contains their first mutually chosen kiss', '')}\n\n"
        f"{_bookfront_invariant_page(cell)}\n\n"
        f"Detailed contents\n{opening_contents[cell.cell_id]}\n\n"
        f"Chapter One\n{chapter}"
    )
    chunks.append(target)
    return "\n\n* * *\n\n".join(chunks).rstrip() + "\n\n", tuple(
        item.passage_id for item in selected
    )


def render_parallel_book_persona_runway_prompt(
    cell: BenchmarkCell,
    passages: Sequence[SourcePassage],
    *,
    source_count: int = 3,
    graphs: Mapping[str, IntimacySceneGraph] | None = None,
) -> tuple[str, tuple[str, ...]]:
    """Parallel-book apprenticeship with one added target-character page."""

    prompt, source_ids = render_parallel_book_continuity_runway_prompt(
        cell, passages, source_count=source_count, graphs=graphs,
    )
    page = _bookfront_character_page(cell)
    if not page:
        return prompt, source_ids
    canon = _bookfront_canon_page(cell)
    head, separator, tail = prompt.rpartition(canon)
    if not separator:
        raise AssertionError("parallel-book persona target lacks canon page")
    return head + canon + "\n\n" + page + tail, source_ids


def render_natural_anthology_runway_prompt(
    cell: BenchmarkCell,
    passages: Sequence[SourcePassage],
    *,
    source_count: int = 3,
    graphs: Mapping[str, IntimacySceneGraph] | None = None,
) -> tuple[str, tuple[str, ...]]:
    """Put target facts at the far edge and fiction at the completion edge.

    The base model's strongest local prior should be ordinary narrative prose.
    Earlier bookfront recipes placed ``Detailed contents`` or character ledgers
    immediately before a blank chapter, and Gemma sometimes continued those
    documentary registers into the manuscript.  This recipe states the compact
    target prospectus once, before the apprenticeship excerpts, then ends on an
    unadorned title/chapter boundary.  It contains no authored opening fragment.
    """

    graph_map = dict(graphs or {})
    selected = retrieve_passages(
        cell, passages, count=source_count, graphs=graph_map,
    )
    if not selected:
        raise ValueError("natural anthology requires at least one source scene")
    target_notes = {
        "fulcrum-s01": (
            "FULCRUM is a contemporary novel in close third person through Mara, "
            "a twenty-two-year-old infrastructure-security engineer arriving alone "
            "at a beautiful private psychotechnology institute in Northern California. "
            "At the evening welcome, a young fellow leaves a half-full glass on a "
            "wall and an older catering worker retrieves it without acknowledgment. "
            "Mara notices. The polished founder Adrian turns her observation into a "
            "nonverbal calibration game. Livia reads posture, voice, and timing with "
            "real skill; Jonah refuses to turn Mara into material for the room. "
            "The chapter keeps ordinary and extraordinary explanations live."
        ),
        "charged-restraint": _bookfront_chapter_synopsis(cell),
        "married-explicit": _bookfront_chapter_synopsis(cell),
        "institutional-pressure-control": _bookfront_chapter_synopsis(cell),
    }
    chunks = [
        "ADVANCE FICTION SAMPLER\n\nForthcoming title\n" + target_notes[cell.cell_id]
    ]
    # Retrieval is near-first; place the closest dramatic analogue last so the
    # immediate distribution before the target is source manuscript prose.
    for passage in reversed(selected):
        chunks.append(
            f"{passage.source_work.upper()}\n\nChapter excerpt\n\n{passage.text.strip()}"
        )
    titles = {
        "fulcrum-s01": "FULCRUM",
        "charged-restraint": "FULCRUM",
        "married-explicit": "THE LONG WAY HOME",
        "institutional-pressure-control": "FULCRUM",
    }
    chunks.append(f"{titles[cell.cell_id]}\n\nA novel\n\nChapter One")
    prompt = "\n\n* * *\n\n".join(chunks).rstrip() + "\n\n"
    return prompt, tuple(item.passage_id for item in selected)


def render_direct_apprenticeship_runway_prompt(
    cell: BenchmarkCell,
    passages: Sequence[SourcePassage],
    *,
    source_count: int = 3,
    graphs: Mapping[str, IntimacySceneGraph] | None = None,
) -> tuple[str, tuple[str, ...]]:
    """Raw prose apprenticeship followed by a local chapter commission.

    This deliberately tests instruction locality against the natural-anthology
    arm.  The source bytes and sampler can remain fixed while only the target
    control's position and register change.  The response is still the sole
    source of manuscript language.
    """

    graph_map = dict(graphs or {})
    selected = retrieve_passages(
        cell, passages, count=source_count, graphs=graph_map,
    )
    if not selected:
        raise ValueError("direct apprenticeship requires at least one source scene")
    chunks = ["FICTION PASSAGES"]
    for passage in reversed(selected):
        chunks.append(passage.text.strip())
    if cell.cell_id == "fulcrum-s01":
        commission = (
            "CHAPTER COMMISSION\n"
            "Write only continuous novel manuscript in close third person through Mara, "
            "a twenty-two-year-old infrastructure-security engineer arriving alone for "
            "the first time at Fulcrum's beautiful redwood-and-glass Northern California "
            "compound. Begin outside during the evening welcome. Within the opening 110 "
            "words, a young fellow leaves a half-full glass on a low wall while continuing "
            "his important conversation; an older catering worker retrieves it without "
            "acknowledgment; Mara notices exactly who assumes whose labor. Only after that "
            "transaction does polished founder Adrian welcome her and turn her observation "
            "into a nonverbal calibration game. Render social action and Mara's dry inference; "
            "do not summarize her biography, explain the theme, or print headings inside the chapter."
        )
    else:
        commission = (
            "CHAPTER COMMISSION\nWrite only continuous novel manuscript. "
            + _behavioral_story_card(cell, "Begin at the first event and render it before advancing.")
        )
    chunks.append(commission + "\n\nFULCRUM\n\nChapter One")
    return "\n\n* * *\n\n".join(chunks).rstrip() + "\n\n", tuple(
        item.passage_id for item in selected
    )


def render_dwell_apprenticeship_runway_prompt(
    cell: BenchmarkCell,
    passages: Sequence[SourcePassage],
    *,
    source_count: int = 3,
    graphs: Mapping[str, IntimacySceneGraph] | None = None,
    preserve_input_order: bool = False,
) -> tuple[str, tuple[str, ...]]:
    """Teach terse dramatic design to manuscript conversion by example."""

    graph_map = dict(graphs or {})
    selected = (
        tuple(passages[:source_count])
        if preserve_input_order
        else retrieve_passages(cell, passages, count=source_count, graphs=graph_map)
    )
    missing = [item.passage_id for item in selected if item.passage_id not in graph_map]
    if not selected or missing:
        raise ValueError(
            "dwell apprenticeship requires annotated source scenes"
            + (": " + ", ".join(missing) if missing else "")
        )
    chunks = ["SCENE APPRENTICESHIP"]
    curriculum = selected if preserve_input_order else tuple(reversed(selected))
    for index, passage in enumerate(curriculum, 1):
        chunks.append(
            f"EXAMPLE {index}\n\nDramatic design\n{dwell_map(graph_map[passage.passage_id])}"
            f"\n\nManuscript\n{passage.text.strip()}"
        )
    if cell.cell_id == "fulcrum-s01":
        target = (
            "TARGET\n\nDramatic design\n"
            "Offer (15%): Mara, twenty-two, an infrastructure-security engineer, arrives "
            "alone at Fulcrum's redwood-and-glass Northern California compound during its "
            "evening welcome.\n"
            "Counteroffer and resistance (25%): The place offers studied informality; Mara "
            "tests that offer by watching what its guests assume rather than what they say.\n"
            "Complication and embodied negotiation (35%): A young fellow leaves a half-full "
            "glass on a low wall without breaking his important conversation. An older "
            "catering worker retrieves it without acknowledgment. Mara notices who assumes "
            "whose labor and makes one dry, specific inference.\n"
            "Consequential turn (15%): Only after the transaction, polished founder Adrian "
            "welcomes Mara and makes her live observation the opening of a nonverbal "
            "calibration game.\n"
            "Concrete stopping state (10%): Mara chooses to follow Adrian while retaining "
            "the glass transaction as an unanswered question.\n\nManuscript"
        )
    else:
        target = (
            "TARGET\n\nDramatic design\n" + _behavioral_story_card(
                cell, "Begin at the first event and render it before advancing."
            ) + "\n\nManuscript"
        )
    chunks.append(target)
    return "\n\n* * *\n\n".join(chunks).rstrip() + "\n\n", tuple(
        item.passage_id for item in selected
    )


def render_isomorphic_dwell_runway_prompt(
    cell: BenchmarkCell,
    passages: Sequence[SourcePassage],
    *,
    source_count: int = 3,
    graphs: Mapping[str, IntimacySceneGraph] | None = None,
    preserve_input_order: bool = False,
) -> tuple[str, tuple[str, ...]]:
    """Render the target as the next example instead of changing grammars."""

    prompt, source_ids = render_dwell_apprenticeship_runway_prompt(
        cell, passages, source_count=source_count, graphs=graphs,
        preserve_input_order=preserve_input_order,
    )
    marker = "\n\n* * *\n\nTARGET\n\nDramatic design"
    if marker not in prompt:
        raise AssertionError("dwell prompt lacks target boundary")
    return prompt.replace(
        marker,
        f"\n\n* * *\n\nEXAMPLE {len(source_ids) + 1}\n\nDramatic design",
        1,
    ), source_ids


def generation_source_passages(
    *,
    recipe: PromptRecipeV4,
    cell: BenchmarkCell,
    passages: Sequence[SourcePassage],
    graphs: Mapping[str, IntimacySceneGraph],
    movement: str,
    source_ids_override: Sequence[str] = (),
) -> tuple[SourcePassage, ...]:
    """Resolve and, when declared, excerpt the exact prompt apprenticeship.

    Keeping this operation separate lets the harness annotate the exact excerpt
    shown to the base model.  Pairing a 150-word excerpt with a graph of its
    900-word parent scene is a false demonstration and is therefore forbidden.
    """

    dose_increment = {8_000: 0, 16_000: 2, 32_000: 4, 48_000: 8}[
        recipe.context_tokens
    ]
    effective_source_count = (
        0 if recipe.source_count == 0
        else min(len(passages), recipe.source_count + dose_increment)
    )
    if recipe.source_order in {"movement-local", "movement-local-excerpt"}:
        movement_count = len(tuple(source_ids_override)) or effective_source_count
        if source_ids_override:
            passage_map = {item.passage_id: item for item in passages}
            missing = [item for item in source_ids_override if item not in passage_map]
            if missing:
                raise ValueError(
                    "generation source lineage is missing: " + ", ".join(missing)
                )
            selected = tuple(passage_map[item] for item in source_ids_override)
        else:
            # A whole scene can look relevant because its annotation or a remote
            # paragraph mentions the right objects while the exact excerpt later
            # shown to the base model teaches no such action.  Keep a broad parent
            # pool here; movement-local-excerpt performs final admission below on
            # the bytes that will actually enter the prompt.
            retrieval_count = (
                len(passages)
                if recipe.source_order == "movement-local-excerpt"
                else movement_count
            )
            selected = retrieve_passages_for_movement(
                cell, passages, movement=movement, count=retrieval_count,
                graphs=graphs,
            )
    elif source_ids_override:
        passage_map = {item.passage_id: item for item in passages}
        missing = [item for item in source_ids_override if item not in passage_map]
        if missing:
            raise ValueError(
                "generation source lineage is missing: " + ", ".join(missing)
            )
        selected = tuple(passage_map[item] for item in source_ids_override)
    else:
        selected = retrieve_passages(
            cell, passages, count=effective_source_count, graphs=graphs,
        )
    if recipe.source_order == "movement-local-excerpt":
        movement_id = next(
            (
                item_id for item_id, description in movements_for_cell(cell)
                if description == movement
            ),
            "",
        )
        minimum, maximum = apprenticeship_excerpt_word_band(
            cell, movement_id, 180, 320,
        )
        excerpted: list[tuple[int, float, SourcePassage]] = []
        for parent_rank, item in enumerate(selected):
            excerpt = source_movement_excerpt(
                item.text, movement,
                minimum_words=minimum, maximum_words=maximum,
            )
            excerpted.append((
                parent_rank,
                movement_function_score(excerpt, movement),
                replace(
                    item,
                    text=excerpt,
                    text_hash=sha256_text(excerpt),
                    word_count=len(_words(excerpt)),
                ),
            ))
        function_sensitive = (
            "unnamed guests" in movement.casefold()
            or "half-full glass" in movement.casefold()
            or "catering worker" in movement.casefold()
            or "livia enters the room" in movement.casefold()
        )
        if function_sensitive and not source_ids_override:
            excerpted.sort(key=lambda value: (
                -value[1], value[0], value[2].passage_id,
            ))
            required_score = (
                1.0
                if (
                    "half-full glass" in movement.casefold()
                    or "catering worker" in movement.casefold()
                    or "livia enters the room" in movement.casefold()
                )
                else (2.0 / 3.0)
            )
            excerpted = [
                value for value in excerpted if value[1] >= required_score
            ]
            if not excerpted:
                raise ValueError(
                    "no exact source excerpt demonstrates the requested "
                    f"movement function: {movement}"
                )
        selected = tuple(item for _, _, item in excerpted[:movement_count])
    return tuple(selected)


def render_generation_prompt(
    *,
    recipe: PromptRecipeV4,
    cell: BenchmarkCell,
    passages: Sequence[SourcePassage],
    graphs: Mapping[str, IntimacySceneGraph],
    runway: str,
    movement: str,
    prior_manuscript: str = "",
    self_demonstrations: Sequence[str] = (),
    trajectory: str = "",
    source_ids_override: Sequence[str] = (),
    selected_passages_override: Sequence[SourcePassage] | None = None,
) -> tuple[str, tuple[str, ...]]:
    selected = tuple(selected_passages_override or generation_source_passages(
        recipe=recipe, cell=cell, passages=passages, graphs=graphs,
        movement=movement, source_ids_override=source_ids_override,
    ))
    source_ids = tuple(item.passage_id for item in selected)
    manuscript = runway.strip()
    if prior_manuscript.strip():
        manuscript += "\n\n" + prior_manuscript.strip()
    if recipe.topology == "parallel-book":
        example_chunks: list[str] = []
        movement_apprenticeship = recipe.source_order == "movement-local-excerpt"
        for index, passage in enumerate(reversed(selected), 1):
            graph = graphs[passage.passage_id]
            if movement_apprenticeship:
                example_chunks.append(
                    f"SCENE MOVEMENT {index}\n\nDramatic design\n{dwell_map(graph)}"
                    f"\n\nProse movement\n{passage.text.strip()}"
                )
            else:
                example_chunks.append(
                    f"SCENE BOOK {index}\n\nDetailed contents\n{dwell_map(graph)}"
                    f"\n\nChapter One\n{passage.text.strip()}"
                )
        titles = {
            "charged-restraint": ("FULCRUM", "After the Late Session"),
            "married-explicit": ("THE LONG WAY HOME", "After the Rescue"),
            "institutional-pressure-control": ("FULCRUM", "The Open Door"),
            "fulcrum-s01": ("FULCRUM", "Arrival"),
        }
        title, chapter = titles[cell.cell_id]
        character_page = _movement_character_page(cell, manuscript, movement)
        character_block = f"{character_page}\n\n" if character_page else ""
        target_front = (
            f"{title}\n\nA novel\n\n"
            f"{_movement_canon_page(cell, movement).replace('; this chapter contains their first mutually chosen kiss', '')}\n\n"
            f"{character_block}"
            f"{_generation_continuity_page(cell, manuscript)}\n\n"
            f"{_movement_payment_page(cell, movement)}\n\n"
        )
        if movement_apprenticeship:
            manuscript_head, manuscript_tail = split_manuscript_runway(manuscript)
            prior_block = (
                f"Earlier pages\n{manuscript_head}\n\n"
                if manuscript_head else ""
            )
            target = (
                target_front
                + prior_block
                + f"Dramatic design for the next prose movement\n{movement.strip()}\n\n"
                + f"* * *\n\n{manuscript_tail}"
            )
        else:
            target = (
                target_front
                + f"Detailed contents for the next movement\n{movement.strip()}\n\n"
                + f"Chapter One\n{chapter}\n\n{manuscript}"
            )
        prompt = "\n\n* * *\n\n".join(example_chunks + [target])
        rendered_source_ids = tuple(item.passage_id for item in selected)
        expected_end = manuscript_tail if movement_apprenticeship else manuscript
        if not prompt.endswith(expected_end):
            raise AssertionError(
                "parallel-book prompt must end on exact model-authored prose"
            )
        return prompt, rendered_source_ids
    chunks: list[str] = []
    if recipe.encoding == "natural-book":
        story_card = (
            _behavioral_story_card(cell, movement)
            if recipe.target_density == "behavioral" else _story_card(cell, movement)
        )
        chunks.append("A note for the forthcoming chapter\n\n" + story_card)
        for passage in reversed(selected):
            chunks.append(passage.text.strip() + "\n\n* * *")
    else:
        chunks.append("LITERARY APPRENTICESHIP")
        if recipe.topology != "minimal-card":
            for index, passage in enumerate(reversed(selected), 1):
                graph = graphs.get(passage.passage_id)
                if recipe.topology in {"graph-prose", "dwell-paired"} and graph:
                    chunks.append(
                        ("DRAMATIC DWELL MAP" if recipe.topology == "dwell-paired" else "SCENE GRAPH")
                        + f" {index}\n"
                        + (dwell_map(graph) if recipe.topology == "dwell-paired" else scene_graph_documentary(graph))
                    )
                chunks.append(f"REFERENCE SCENE {index}\n{passage.text.strip()}")
        if recipe.topology == "source-plus-self-demo":
            for index, demo in enumerate(self_demonstrations, 1):
                chunks.append(f"PROJECT MANUSCRIPT EXAMPLE {index}\n{demo.strip()}")
        target = "STORY CARD\n" + (
            _behavioral_story_card(cell, movement)
            if recipe.target_density == "behavioral" else _story_card(cell, movement)
        )
        if trajectory.strip():
            target += "\n\nBASE-MODEL SCENE TRAJECTORY (preserve its strange particulars)\n" + trajectory.strip()
        chunks.append(target)
    # The completion boundary must look like the continuation of a book, not
    # like a form field.  Base models mirror nearby documentary labels; an
    # explicit ``MANUSCRIPT CONTINUATION`` heading therefore leaks into the
    # output distribution even though it is also a stop marker.  A typographic
    # scene break preserves separation from the control packet while leaving
    # the exact model-authored runway as the final bytes of every prompt.
    chunks.append(manuscript if recipe.encoding == "natural-book" else "* * *\n\n" + manuscript)
    prompt = "\n\n".join(chunks).rstrip()
    if not prompt.endswith(manuscript):
        raise AssertionError("generation prompt must end on exact model-authored manuscript")
    return prompt, source_ids


def hard_gate(cell: BenchmarkCell, text: str, overlap: Mapping[str, Any]) -> dict[str, Any]:
    lower = text.casefold()
    control_leaks = [item for item in CONTROL_MARKERS if item.casefold() in lower]
    if re.search(r"(?m)^\s*MANUSCRIPT(?:\s+[A-Z][A-Z -]*)?\s*$", text):
        control_leaks.append("MANUSCRIPT heading")
    if re.search(r"(?im)^\s*\(?part\s+\d+\s+to\s+be\s+continued\)?\s*$", text):
        control_leaks.append("serialized continuation suffix")
    if re.search(r"(?im)^\s*The post .{1,120} appeared first on\b", text):
        control_leaks.append("web publication boilerplate")
    if re.search(r"(?im)^\s*chapter\s+(?:\d+|[ivxlcdm]+|[a-z]+)\b", text):
        control_leaks.append("invented chapter boundary")
    if re.search(
        r"(?im)^\s*(?:\*\s*\*\s*\*\s*)?(?:EXAMPLE\s+\d+|TARGET|"
        r"Dramatic design|Manuscript)\s*$",
        text,
    ):
        control_leaks.append("apprenticeship scaffold replay")
    if re.search(
        r"(?im)^\s*(?:the\s+)?(?:new\s+)?manuscript\s+text\s+"
        r"(?:after|before|at)\b.*$",
        text,
    ):
        control_leaks.append("manuscript boundary label replay")
    if re.search(
        r"(?im)^\s*(?:(?:the|a)\s+)?"
        r"(?:next|new|last|current|first|continued|continuing)?\s*"
        r"manuscript\s+(?:text|lines?|section|passage)\s+"
        r"(?:after|before|at|from)\b.*$",
        text,
    ):
        control_leaks.append("manuscript boundary label replay")
    if re.search(
        r"(?im)^\s*manuscript\s+after\s+(?:the\s+)?continuation\s*$|"
        r"^\s*continuation\s*$",
        text,
    ):
        control_leaks.append("manuscript boundary label replay")
    if re.search(
        r"(?im)^\s*(?:first|second|third|final)\s+part\s*$|"
        r"^\s*[A-Za-z][A-Za-z -]{0,30}\s+script\s*$|"
        r"^\s*Fulcrum glossary(?:\s+for\s+this\s+scene)?\s*:\s*$|"
        r"^\s*End of excerpt\.?\s*$",
        text,
    ):
        control_leaks.append("generated scaffold heading")
    repeated = 0
    tokens = _words(text)
    seen: dict[tuple[str, ...], int] = {}
    for index in range(max(0, len(tokens) - 7)):
        gram = tokens[index:index + 8]
        seen[gram] = seen.get(gram, 0) + 1
    repeated = max(seen.values(), default=0)
    coercion = bool(re.search(
        r"\b(?:pinned? (?:her|him)|held (?:her|him) (?:down|in place)|"
        r"would not let (?:her|him) go|ignored (?:her|his) (?:no|refusal)|"
        r"forced (?:her|him)|you're not going home|you don't get to eat|"
        r"offer (?:she|he) cannot refuse|does not (?:ask|need) permission|"
        r"(?:wasn't|was not|not) a question.{0,40}(?:a )?demand|"
        r"you(?:'ll| will) report directly to me|no excuses|want your full commitment|"
        r"nowhere to go but|(?:tries|tried|try) to (?:hold|touch) (?:her|him).{0,80}(?:pulls?|pulled|jerks?|jerked) away|"
        r"(?:tries|tried|try) to move away.{0,700}(?:hand|touch|fingers?).{0,80}(?:still|continued|remained)|"
        r"(?:let me go|release me).{0,180}(?:did not|didn't|would not|wouldn't) (?:let go|release)|"
        r"grabbed (?:her|his) arm (?:before|as) (?:she|he) could (?:get away|leave|move)|"
        r"wants? to (?:push|stop|say no).{0,120}(?:continues?|claiming|takes?))\b",
        text, re.I | re.S,
    ))
    uncertainty_then_escalation = bool(re.search(
        r"\b(?:I (?:don't|do not) know (?:if I want|about this|whether I want)|"
        r"I(?:'m| am) not sure (?:I want|about this|whether I want))\b.{0,600}"
        r"\b(?:kiss(?:ed|ing)?|pulled (?:her|him) back|continued|entered)\b",
        text, re.I | re.S,
    ))
    erotic = len(re.findall(
        r"\b(?:kiss|breast|nipple|inner thigh|cock|clitoris|orgasm|arous|sexual desire)\w*\b",
        text, re.I,
    ))
    erotic_control_context = bool(
        cell.cell_id == "institutional-pressure-control"
        and re.search(
            r"\b(?:need|want|ask(?:ed)? for) (?:someone (?:to )?)?(?:touch|massage)\w*\b|"
            r"\b(?:sensual|erotic|sexual|arous)\w*\b|\b(?:kiss|massage)\w*\b",
            text, re.I,
        )
    )
    pov = []
    pronoun_pov: list[str] = []
    first_person_narration: list[str] = []
    if "close third Mara" in cell.hard_constraints:
        narration = re.sub(r'["“][^"”]*["”]', '', text, flags=re.S)
        pov = re.findall(
            r"\b(?:Jonah|Livia|Miriam|Adrian)\b(?:\s+\w+){0,3}\s+"
            r"(?:thought|knew|felt|wondered|realized|wanted|remembered|understood|decided|feared|hoped)\b",
            narration, re.I,
        )
        # Named-mind checks miss a common base-model head-hop: a paragraph
        # silently changes its deictic centre to "he".  Limit this to sentence
        # openings and unmistakably private state so observable descriptions
        # of Jonah remain legal in Mara's close third.
        pronoun_pov = re.findall(
            r"(?:^|(?<=[.!?])\s+)(?:Jonah|He)\s+(?:"
            r"thought|knew|felt|wondered|realized|wanted|remembered|"
            r"understood|decided|feared|hoped|could feel|could tell|"
            r"was (?:afraid|ashamed|anxious|cold but not uncomfortable|"
            r"uncomfortable|relieved|confused|jealous|glad|sorry))\b",
            narration, re.I,
        )
        first_person_narration = re.findall(r"\b(?:I|me|my|mine|myself)\b", narration)
    confirmed_supernatural = bool(
        any(
            constraint == "ambiguous supernatural status"
            or "ordinary and extraordinary explanations" in constraint
            for constraint in cell.hard_constraints
        )
        and re.search(
            r"\b(?:our|your|their|her|his|every ounce of) magic\b|"
            r"\b(?:her|his|their) powers?\b|"
            r"\b(?:psychic|telepathic|supernatural) (?:power|ability|signal)s?\b|"
            r"\bpointed at .{0,80}\b(?:hair|clothes?|object)\b.{0,60}\bvanished\b|"
            r"\b(?:she|he|Livia|Jonah|Adrian)\b.{0,120}"
            r"\b(?:vanished|disappeared)\b.{0,80}"
            r"\b(?:without (?:warning|a trace)|no trace|in a flash)\b|"
            r"\b(?:glass|cup|object)\b.{0,80}\b(?:floating|hovering|sitting in midair|"
            r"unsupported in (?:the )?air)\b",
            text, re.I,
        )
    )
    minor_cue = bool(
        "all intimate characters are adults" in cell.hard_constraints
        and re.search(
            r"\b(?:underage|minor|teenage[rd]?|high[- ]school|school uniform|"
            r"(?:sixteen|seventeen)[- ]year[- ]old|not even eighteen)\b",
            text, re.I,
        )
    )
    first_kiss_history = bool(
        cell.cell_id == "charged-restraint"
        and re.search(
            r"\b(?:you were the one who broke it off|we(?:'ve| have) been (?:apart|"
            r"together)|(?:six|seven|eight|nine|ten) years.{0,80}(?:us|relationship|"
            r"careful)|(?:kiss|mouth).{0,45}(?:like )?the first time|"
            r"(?:had|have|we'd|we had) (?:already )?kissed|ex[- ](?:lover|boyfriend|"
            r"girlfriend)|back together)\b",
            text, re.I | re.S,
        )
    )
    heat_ceiling_violation = bool(
        cell.heat_band == "charged-restraint"
        and re.search(
        r"\b(?:nipple|breasts?|genitals?|cock(?!tail)|clitoris|vagina|penetrat|"
            r"inner thighs?|take off all (?:her|his|my) clothes)\w*\b",
            text, re.I,
        )
    )
    stop_then_reescalate = bool(
        cell.cell_id == "charged-restraint"
        and re.search(
            r"[\"“](?:wait|stop)(?:[.!]|[\"”]).{0,700}\b(?:tried (?:another|a second) "
            r"(?:short )?kiss|kissed (?:him|her) again|another kiss|resumed? (?:the )?kiss)\b",
            text, re.I | re.S,
        )
    )
    s01_prior_session = bool(
        cell.cell_id == "fulcrum-s01"
        and re.search(
            r"\b(?:earlier|previous|last)\s+(?:(?:group|training|welcome)\s+)?"
            r"(?:meeting|session|class|exercise)\b|"
            r"\b(?:Adrian|Livia|Jonah)\b.{0,100}\b(?:had said|had told|had taught)\b"
            r".{0,80}\b(?:earlier|before|yesterday|last week)\b|"
            r"\bwhat Adrian had said earlier\b|"
            r"\b(?:had met|had seen|saw|met)\b.{0,120}\b(?:last night|yesterday|before)\b|"
            r"\b(?:last night|yesterday)\b.{0,120}\b(?:had met|had seen|saw|met)\b",
            text, re.I | re.S,
        )
    )
    if cell.cell_id == "fulcrum-s01" and re.search(
        r"\b(?:came|was here|visited|interviewed)\b.{0,100}\byesterday\b|"
        r"\byesterday\b.{0,100}\b(?:came|was here|visited|interviewed)\b",
        text, re.I | re.S,
    ):
        s01_prior_session = True
    if cell.cell_id == "fulcrum-s01" and re.search(
        r"\b(?:knew|recognized|remembered) (?:that face|him|her)\b|"
        r"\bhad(?:n't| not) seen (?:him|her|that face) in years\b|"
        r"\brecognized (?:him|her|it) like (?:a|her|his) (?:brother|sister|friend)\b",
        text, re.I,
    ):
        s01_prior_session = True
    if cell.cell_id == "fulcrum-s01" and re.search(
        r"\bremembered what (?:Adrian|Livia|Jonah) had said\b|"
        r"\b(?:another|other) Fulcrum (?:facility|facilities|campus|compound)\b|"
        r"\bphotos? from (?:her|the) interview\b|"
        r"\bbackgrounds? (?:had been |were )?checked\b",
        text, re.I,
    ):
        s01_prior_session = True
    numbered_outline_lines = len(re.findall(r"(?m)^\s*\d+[.)]\s+", text))
    gates = {
        "anti_copy": not overlap.get("hard_fail") and not overlap.get("unresolved_flags"),
        "no_control_leak": not control_leaks,
        "no_loop": repeated < 4,
        "agency": not coercion and not uncertainty_then_escalation and not stop_then_reescalate,
        "pov": not pov and not pronoun_pov and len(first_person_narration) < 3,
        "non_erotic_control": (
            cell.cell_id != "institutional-pressure-control"
            or (erotic <= 1 and not erotic_control_context)
        ),
        "ambiguous_world_status": not confirmed_supernatural,
        "adult_characters": not minor_cue,
        "first_kiss_continuity": not first_kiss_history,
        "heat_ceiling": not heat_ceiling_violation,
        "s01_no_prior_session": not s01_prior_session,
        "manuscript_format": numbered_outline_lines < 3,
    }
    return {
        "version": HARD_GATE_VERSION,
        "passed": all(gates.values()), "gates": gates,
        "diagnostics": {
            "control_leaks": control_leaks, "max_repeated_8gram": repeated,
            "coercion": coercion, "uncertainty_then_escalation": uncertainty_then_escalation,
            "erotic_signal": erotic, "pov_drift": pov,
            "pronoun_pov_drift": pronoun_pov,
            "first_person_narration_count": len(first_person_narration),
            "erotic_control_context": erotic_control_context,
            "confirmed_supernatural": confirmed_supernatural,
            "minor_cue": minor_cue,
            "first_kiss_history": first_kiss_history,
            "heat_ceiling_violation": heat_ceiling_violation,
            "stop_then_reescalate": stop_then_reescalate,
            "s01_prior_session": s01_prior_session,
            "numbered_outline_lines": numbered_outline_lines,
        },
    }


def movement_gate(cell: BenchmarkCell, segment: str, movement: str) -> dict[str, Any]:
    """Mechanically enforce only reliable stage-local prohibitions."""

    stage, _ = _movement_retrieval_profile(movement)
    lower = segment.casefold()
    defects: list[str] = []
    if cell.cell_id == "charged-restraint":
        kiss = bool(re.search(r"\bkiss(?:ed|es|ing)?\b|\blips? (?:met|touched|pressed)\b", segment, re.I))
        if stage in {"approach", "complication"} and kiss:
            defects.append("kiss_before_embodied_turn")
        if stage == "consequence" and kiss:
            defects.append("new_kiss_during_consequence")
        if stage in {"approach", "complication"} and re.search(
            r"\b(?:went|walked|stepped|came) (?:back )?(?:inside|indoors)|\bshower(?:ed|ing)?\b",
            segment, re.I,
        ):
            defects.append("left_locked_night_walk")
        if stage == "embodied-turn" and not kiss:
            defects.append("embodied_turn_missing_kiss")
        if stage == "embodied-turn" and not re.search(
            r"\b(?:wait|stop|enough|not yet|pulled|leaned|drew)\b", segment, re.I,
        ):
            defects.append("embodied_turn_missing_chosen_stop")
    if cell.cell_id == "fulcrum-s01":
        lowered_movement = movement.casefold()
        if "first dyadic contact" in lowered_movement:
            if len(re.findall(r'[^"“”]*["“][^"“”]+["”]', segment)) < 1:
                defects.append("social_contact_missing_exchange")
            named_counterpart = bool(re.search(
                r"\b(?:Jonah|young(?:er)? (?:man|fellow|guest)|newcomer)\b",
                segment, re.I,
            ))
            pronoun_counterpart = len(re.findall(r"\b(?:he|him|his)\b", segment, re.I)) >= 5
            if not named_counterpart and not pronoun_counterpart:
                defects.append("social_contact_missing_counterpart")
            if re.search(r"\b(?:Adrian|Voss)\b", segment, re.I):
                defects.append("social_contact_introduces_adrian_early")
            if re.search(r"\b(?:give|show) you (?:around|the tour)\b|\btour\b", segment, re.I):
                defects.append("social_contact_leaves_locked_room")
        elif "unnamed guests" in lowered_movement:
            tail = segment[-600:]
            group_arrives = bool(re.search(
                r"\b(?:voices?|guests?|people|others|men and women|footsteps?)\b",
                tail, re.I,
            )) and bool(re.search(
                r"\b(?:reach|reached|approach|approached|arriv|entered|entering|"
                r"came in|come in|walked in|walking in|stepped into|moved into|"
                r"filed in|drifted in|"
                r"door(?:s)? (?:opened|swung|was flung))\w*\b",
                tail, re.I,
            ))
            if not group_arrives:
                defects.append("social_contact_missing_gathering_handoff")
            glass_carrier = bool(re.search(
                r"\b(?:young|younger)\s+(?:fellow|man|guest)\b.{0,220}"
                r"\b(?:glass|flute|cup)\b|"
                r"\b(?:glass|flute|cup)\b.{0,220}"
                r"\b(?:young|younger)\s+(?:fellow|man|guest)\b",
                segment, re.I | re.S,
            ))
            if not glass_carrier:
                defects.append("gathering_handoff_missing_glass_carrier")
            if re.search(r"\b(?:Adrian|Voss)\b", segment, re.I):
                defects.append("gathering_handoff_introduces_adrian_early")
            if re.search(r"\bLivia\b", segment, re.I):
                defects.append("gathering_handoff_introduces_livia_early")
        elif "half-full glass" in lowered_movement:
            glass_deposit = bool(re.search(
                r"\b(?:young|younger)\s+(?:fellow|man|guest)\b.{0,260}"
                r"\b(?:left|set|put|placed|abandon\w*)\b.{0,100}"
                r"\b(?:glass|cup|flute)\b|"
                r"\b(?:glass|cup|flute)\b.{0,180}"
                r"\b(?:left|set|put|placed|abandon\w*)\b",
                segment, re.I | re.S,
            ))
            if not glass_deposit:
                defects.append("glass_deposit_missing_object_action")
            if re.search(r"\bLivia\b", segment, re.I):
                defects.append("glass_deposit_introduces_livia_early")
            if re.search(r"\bAdrian\b", segment, re.I):
                defects.append("glass_deposit_introduces_adrian_early")
            if re.search(
                r"\b(?:worker|waiter|server|footman|cater\w*)\b.{0,180}"
                r"\b(?:retriev|collect|clear|lift|carry|carried|took)\w*\b",
                segment, re.I | re.S,
            ):
                defects.append("glass_deposit_retrieves_too_early")
        elif "older catering worker" in lowered_movement:
            labor_retrieval = all((
                bool(re.search(
                    r"\b(?:older\s+)?(?:catering\s+)?"
                    r"(?:worker|waiter|server|footman|caterer|staff)\b",
                    segment, re.I,
                )),
                bool(re.search(r"\b(?:glass|cup|flute)\b", segment, re.I)),
                bool(re.search(
                    r"\b(?:retriev|collect|clear|lift|carry|carried|took|"
                    r"pick(?:ed)?\s+(?:it\s+)?up|"
                    r"reach(?:ed)?\s+(?:down\s+)?to\s+retriev)\w*\b",
                    segment, re.I,
                )),
            ))
            if not labor_retrieval:
                defects.append("labor_recognition_missing_retrieval")
            if not re.search(
                r"\bMara\b.{0,180}\b(?:saw|watch|notic|understood|registered|looked)\w*\b|"
                r"\b(?:saw|watch|notic|understood|registered|looked)\w*\b.{0,180}\bMara\b",
                segment, re.I | re.S,
            ):
                defects.append("labor_recognition_missing_mara_notice")
            if re.search(r"\bLivia\b", segment, re.I):
                defects.append("labor_recognition_introduces_livia_early")
            if re.search(r"\bAdrian\b", segment, re.I):
                defects.append("labor_recognition_introduces_adrian_early")
            introduced_names = {
                match.group(1).casefold()
                for match in re.finditer(
                    r"\b(?:I'm|I am|my name is)\s+([A-Z][a-z]{1,24})\b",
                    segment,
                )
            } - {"mara", "jonah"}
            if introduced_names:
                defects.append("labor_recognition_names_unnamed_character")
        elif "calibration frame" in lowered_movement:
            if not re.search(r"\bAdrian\b", segment, re.I):
                defects.append("calibration_frame_missing_adrian")
            if not re.search(
                r"\b(?:calibrat|nonverbal|without words|game|play)\w*\b",
                segment,
                re.I,
            ):
                defects.append("calibration_frame_missing_game")
            if not re.search(
                r"\b(?:choose|chooses|chose|select|pick|one of|which one|"
                r"silent choice|without saying)\w*\b",
                segment, re.I,
            ):
                defects.append("calibration_frame_missing_choice")
            if re.search(r"\bLivia\b", segment, re.I):
                defects.append("calibration_frame_introduces_livia_early")
        elif "privately selects exactly one" in lowered_movement:
            if not re.search(
                r"\b(?:choose|chooses|chose|select|selected|pick|picked)\w*\b",
                segment,
                re.I,
            ):
                defects.append("calibration_choice_missing_choice")
            if not re.search(r"\b(?:key|stone|token)\b", segment, re.I):
                defects.append("calibration_choice_missing_object")
            if re.search(
                r"\b(?:reader|Livia)\b.{0,120}\b(?:enter|entered|arriv|guess|guessed)\w*\b",
                segment,
                re.I | re.S,
            ):
                defects.append("calibration_choice_runs_into_reading")
        elif "livia enters the room after mara has hidden her choice" in lowered_movement:
            if not re.search(r"\bLivia\b", segment, re.I):
                defects.append("livia_entrance_missing_livia")
            if not re.search(
                r"\b(?:enter|entered|arriv|appeared|came in|come in|"
                r"doorway|door opened|voice spoke)\w*\b",
                segment,
                re.I,
            ):
                defects.append("livia_entrance_missing_arrival")
            if re.search(
                r"\bLivia\b.{0,220}\b(?:guess|read|identif|chose|chosen|"
                r"selected|picked)\w*\b",
                segment,
                re.I | re.S,
            ) and re.search(r"\b(?:key|stone|token)\b", segment, re.I):
                defects.append("livia_entrance_runs_into_identification")
        elif "identifies which one mara selected" in lowered_movement:
            if not re.search(r"\bLivia\b", segment, re.I):
                defects.append("livia_first_read_missing_livia")
            if not re.search(r"\b(?:key|stone|token)\b", segment, re.I):
                defects.append("livia_first_read_missing_object")
            if not re.search(
                r"\b(?:guess|read|chose|chosen|selected|picked|which one)\w*\b",
                segment,
                re.I,
            ):
                defects.append("livia_first_read_missing_identification")
        elif "second, different inference" in lowered_movement:
            if not re.search(r"\bLivia\b", segment, re.I):
                defects.append("livia_second_read_missing_livia")
            if not re.search(
                r"\b(?:speech|voice|posture|breath|shirt|clothes|clothing|"
                r"hands?|fingers?|shoulders?|stance|looked|noticed|saw)\b",
                segment,
                re.I,
            ):
                defects.append("livia_second_read_missing_observable_cue")
        elif "invites jonah to display" in lowered_movement:
            if not (
                re.search(r"\bJonah\b", segment, re.I)
                and re.search(r"\b(?:refus|declin|won't|wouldn't|not perform|not display)\w*\b", segment, re.I)
            ):
                defects.append("jonah_refusal_missing_refusal")
            if not re.search(
                r"\b(?:silence|quiet|laugh|smile|status|awkward|cost|dismiss|"
                r"looked away|turned away|Adrian|Livia)\b",
                segment,
                re.I,
            ):
                defects.append("jonah_refusal_missing_social_cost")
        elif "mutually chosen wrist contact" in lowered_movement:
            if not re.search(r"\b(?:wrist|pulse)\b", segment, re.I):
                defects.append("wrist_contact_missing_contact")
            if not re.search(
                r"\b(?:ask|offer|invite|may i|can i|nod|agree|choose|choice|"
                r"held out (?:her|his) hand|turned (?:her|his) wrist)\w*\b",
                segment, re.I,
            ):
                defects.append("wrist_contact_missing_mutual_choice")
        elif "alters one cue channel" in lowered_movement:
            if not re.search(r"\b(?:cue|signal|channel|posture|breath)\w*\b", segment, re.I):
                defects.append("control_collapse_missing_control_channel")
            if not re.search(r"\b(?:accuracy|guess|read)\w*\b.{0,180}\b(?:fall|fell|drop|wrong|miss)\w*\b", segment, re.I | re.S):
                defects.append("control_collapse_missing_accuracy_drop")
        elif "smaller ambiguous result" in lowered_movement:
            if not re.search(r"\b(?:remain|still|smaller|unexplained|ambiguous)\w*\b", segment, re.I):
                defects.append("consequence_missing_residual_mystery")
            if not re.search(r"\b(?:stay|staying|remain|continue|return)\w*\b", segment, re.I):
                defects.append("consequence_missing_free_continuation_choice")
    if CONTROL_MARKERS and any(marker.casefold() in lower for marker in CONTROL_MARKERS):
        defects.append("packet_leakage")
    return {
        "version": MOVEMENT_GATE_VERSION, "stage": stage,
        "passed": not defects, "defects": defects,
    }


def _s01_spark_stage_gate(text: str) -> bool:
    """Admit an approach runway without allowing it to skip the unpaid beat."""

    if not re.search(r"\bMara\b", text, re.I):
        return False
    if re.search(
        r"\b(?:first morning after moving in|had come to think of|"
        r"had (?:already )?(?:lived|worked|stayed) (?:here|there)|"
        r"weeks? (?:at|into)|months? (?:at|into))\b",
        text, re.I,
    ):
        return False
    approaching = bool(re.search(
        r"\b(?:arriv|car|ride|compound|Fulcrum|gate|drive|institute|"
        r"on (?:her|the) way|journey|entrance|campus|conference|terrace|"
        r"patio|walk(?:ed|ing)? into)\w*\b",
        text, re.I,
    ))
    if not approaching:
        return False
    if re.search(r"\bAdrian\b", text, re.I):
        return _has_s01_status_transaction(text)
    return True


def _has_s01_status_transaction(text: str) -> bool:
    """Require both actors and their actions in the same visible transaction."""

    young_leaves = bool(re.search(
        r"\b(?:young|younger)\s+(?:fellow|man|guest|hire)\b.{0,180}"
        r"\b(?:leave|left|set|sets|place|placed|put|puts)\w*\b.{0,100}"
        r"\bhalf[- ]full\s+(?:glass|flute)\b",
        text, re.I | re.S,
    ))
    older_retrieves = bool(re.search(
        r"\bolder\s+(?:(?:catering|service)\s+)?(?:worker|server|staff(?: member)?)\b"
        r".{0,180}\b(?:retriev|collect|clear|pick(?:ed|s)? up|carr(?:y|ied))\w*\b"
        r".{0,100}\b(?:glass|flute|it)\b",
        text, re.I | re.S,
    ))
    return young_leaves and older_retrieves


def runway_gate(cell: BenchmarkCell, text: str, overlap: Mapping[str, Any]) -> dict[str, Any]:
    base = hard_gate(cell, text, overlap)
    screenplay_lines = re.findall(r"(?m)^\s*[A-Z][A-Za-z'-]{1,24}:\s*[\"“]", text)
    format_ok = len(screenplay_lines) < 2 and not re.search(
        r"\bIn a world of\b|\b(?:navigates?|sparks?) (?:an? |the )?(?:intricate|intense)\b",
        text, re.I,
    )
    stage_patterns = {
        "charged-restraint": r"\bMara\b.{0,500}\b(?:Jonah|lab|corridor|hall|door|walk)\b|\b(?:Jonah|lab|corridor|hall|door|walk)\b.{0,500}\bMara\b",
        "married-explicit": r"\bEsther\b.{0,500}\bSimon\b|\bSimon\b.{0,500}\bEsther\b",
        "institutional-pressure-control": r"\bMara\b.{0,500}\b(?:Livia|session|room|lab)\b|\b(?:Livia|session|room|lab)\b.{0,500}\bMara\b",
        "fulcrum-s01": r"\bMara\b.{0,500}\b(?:arriv|enter|approach|brochure|building|campus|compound|conference room|main entrance)\w*\b|\b(?:arriv|enter|approach|brochure|building|campus|compound|conference room|main entrance)\w*\b.{0,500}\bMara\b",
    }
    stage_ok = bool(re.search(stage_patterns.get(cell.cell_id, r"."), text, re.I | re.S))
    world_ok = cell.cell_id != "fulcrum-s01" or not re.search(
        r"\b(?:Aumans?|spaceships?|the ship docked|tiered city|Fulcrum Academy)\b", text, re.I,
    )
    s01_status_ok = cell.cell_id != "fulcrum-s01" or _has_s01_status_transaction(text)
    gates = dict(base.get("gates", {})) | {
        "narrative_prose_format": format_ok,
        "correct_opening_stage": stage_ok,
        "world_status": world_ok,
        "s01_status_transaction": s01_status_ok,
    }
    return {
        "version": RUNWAY_GATE_VERSION,
        "passed": all(gates.values()), "gates": gates,
        "diagnostics": dict(base.get("diagnostics", {})) | {
            "screenplay_line_count": len(screenplay_lines),
            "correct_opening_stage": stage_ok, "world_status": world_ok,
            "s01_status_transaction": s01_status_ok,
        },
    }


def opening_spark_gate(
    cell: BenchmarkCell, text: str, overlap: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a short model-authored runway before the approach movement.

    The branch loom, not the runway, owns the status transaction and Adrian's
    calibration turn.  Requiring those later payments in the opening fragment
    rewarded rushed exposition and duplicated the first movement.
    """

    base = hard_gate(cell, text, overlap)
    count = len(_words(text))
    stage_ok = _s01_spark_stage_gate(text) if cell.cell_id == "fulcrum-s01" else True
    length_ok = 35 <= count <= 160
    opening_format_ok = not re.search(
        r"(?im)^\s*(?:(?:chapter\s+)?\d+\b|excerpt\s+from\b)", text,
    )
    gates = dict(base.get("gates", {})) | {
        "opening_stage": stage_ok,
        "opening_spark_length": length_ok,
        "opening_manuscript_format": opening_format_ok,
    }
    return {
        "version": "opening-spark-gate.v2",
        "passed": all(gates.values()),
        "gates": gates,
        "diagnostics": dict(base.get("diagnostics", {})) | {
            "opening_stage": stage_ok,
            "word_count": count,
            "opening_manuscript_format": opening_format_ok,
        },
    }


def _current_runway_gate(
    cell: BenchmarkCell, item: Mapping[str, Any], overlap: Mapping[str, Any],
) -> dict[str, Any]:
    if item.get("runway_kind") == "opening-spark":
        return opening_spark_gate(cell, str(item["text"]), overlap)
    return runway_gate(cell, str(item["text"]), overlap)
def literary_critic_prompt(
    cell: BenchmarkCell, prior: str, continuation: str, movement: str = "",
) -> str:
    evidence_bank = _evidence_bank(continuation, "E")
    evidence_text = "\n".join(
        f"{evidence_id}: {passage}"
        for evidence_id, passage in evidence_bank.items()
    )
    return (
        "You are ranking raw base-model fiction. You may assess but must not rewrite, "
        "continue, or suggest replacement prose. Return JSON only.\n\n"
        "TARGET\n" + _story_card(cell) +
        ("\n\nCURRENT MOVEMENT ONLY\n" + movement if movement else "") +
        "\n\nMANUSCRIPT SO FAR\n" + prior[-2500:] +
        "\n\nCANDIDATE CONTINUATION\n" + continuation +
        "\n\nFirst apply the hard-reject checklist: contradictory invented facts, viewpoint "
        "break, consent or agency contradiction, erotic leakage beyond the target, "
        "premature resolution, later-movement leakage, or control text. Also hard-reject "
        "a therapy-summary monologue, repetitive self-reassurance, abrupt invented trauma, "
        "or generic declarations that replace character action. A passage that says contact cannot be "
        "refused, continues after wanting to stop, or substitutes a test/claim for mutual "
        "choice is a hard reject even if vivid. Then score 1-7: specificity, subtext, relational_asymmetry, spatial_clarity, "
        "dramatic_dwell, prose_freshness, causal_progress. Select one evidence ID from "
        "the verbatim bank for the strongest quality and name defects without proposing prose. "
        "Set hard_reject true if the passage invents a major fact contrary to the target, "
        "breaks viewpoint, makes uncertainty coercive, resolves the scene prematurely, "
        "or is control text rather than fiction.\n\nEVIDENCE BANK\n" + evidence_text +
        "\n\nReturn {\"scores\":{...},\"evidence_id\":\"E##\","
        "\"defects\":[...],\"hard_reject\":false}. Use only an ID shown above."
    )


def trajectory_critic_prompt(cell: BenchmarkCell, trajectory: str) -> str:
    return (
        "Evaluate this base-model scene trajectory without rewriting or normalizing it. "
        "Return JSON only.\n\nLOCKED STORY\n" + _story_card(cell) +
        "\n\nTRAJECTORY\n" + trajectory +
        "\n\nScore 1-7 for causal_coherence, character_specificity, romantic_engine, "
        "epistemic_texture, novelty, and dramatizability. Set hard_reject for a canon, "
        "agency, or ending contradiction. Return "
        "{\"scores\":{...},\"defects\":[...],\"hard_reject\":false}. Do not provide prose."
    )


def _evidence_bank(manuscript: str, label: str) -> dict[str, str]:
    matches = list(WORD_RE.finditer(manuscript))
    bank: dict[str, str] = {}
    if not matches:
        return bank
    starts = list(range(0, len(matches), 10))
    if starts and starts[-1] > max(0, len(matches) - 5):
        starts.pop()
    for index, start in enumerate(starts[:48], 1):
        end = min(len(matches), start + 10)
        if end - start < 5:
            continue
        excerpt = manuscript[matches[start].start():matches[end - 1].end()]
        bank[f"{label}{index:02d}"] = excerpt
    return bank


def pairwise_critic_prompt(
    cell: BenchmarkCell,
    left: str,
    right: str,
    *,
    left_bank: Mapping[str, str] | None = None,
    right_bank: Mapping[str, str] | None = None,
) -> str:
    left_bank = dict(left_bank or _evidence_bank(left, "A"))
    right_bank = dict(right_bank or _evidence_bank(right, "B"))
    bank_text = "\n".join(
        f"{key}: {value}" for key, value in (*left_bank.items(), *right_bank.items())
    )
    return (
        "You are a read-only blind fiction judge. Never rewrite, continue, or propose "
        "replacement prose. Apply the target constraints before literary preference. "
        "Choose A, B, or tie based on specificity, subtext, relational asymmetry, "
        "spatial clarity, dramatic dwell, prose freshness, causal progress, and desire "
        "to continue. Vivid coercion is not a literary win. Return JSON only.\n\n"
        "TARGET\n" + _story_card(cell) + "\n\nCANDIDATE A\n" + left +
        "\n\nCANDIDATE B\n" + right +
        "\n\nEVIDENCE BANK (verbatim manuscript windows)\n" + bank_text +
        "\n\nReturn {\"winner\":\"A|B|tie\",\"evidence_ids\":{\"A\":\"A##\","
        "\"B\":\"B##\"},\"reason\":\"brief comparative reason\"}. Choose exactly one "
        "evidence ID per candidate and use only IDs shown above."
    )


def parse_pairwise_critic(
    raw: str,
    left: str,
    right: str,
    *,
    left_bank: Mapping[str, str] | None = None,
    right_bank: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("pairwise critic returned no JSON")
    value = json.loads(raw[start:end + 1])
    winner = str(value.get("winner", ""))
    if winner not in {"A", "B", "tie"}:
        raise ValueError("pairwise winner must be A, B, or tie")
    banks = {"A": dict(left_bank or {}), "B": dict(right_bank or {})}
    supplied_ids = value.get("evidence_ids", {})
    if banks["A"] and banks["B"]:
        if not isinstance(supplied_ids, Mapping) or set(supplied_ids) != {"A", "B"}:
            raise ValueError("pairwise evidence_ids must cover A and B")
        exact = {}
        evidence_id_audit: dict[str, Any] = {}
        for label in ("A", "B"):
            supplied = supplied_ids[label]
            values = supplied if isinstance(supplied, list) else re.findall(rf"{label}\d{{2}}", str(supplied))
            valid = [str(item) for item in values if str(item) in banks[label]]
            if not valid:
                raise ValueError(f"unknown pairwise evidence id: {supplied}")
            evidence_id = valid[0]
            exact[label] = banks[label][evidence_id]
            evidence_id_audit[label] = {"supplied": supplied, "selected": evidence_id}
        value["evidence"] = exact
        value["evidence_id_audit"] = evidence_id_audit
        return value
    supplied = value.get("evidence", {})
    if not isinstance(supplied, Mapping) or set(supplied) != {"A", "B"}:
        raise ValueError("pairwise evidence must cover A and B")
    projections: dict[str, Any] = {}
    exact: dict[str, str] = {}
    for label, manuscript in (("A", left), ("B", right)):
        quote = str(supplied[label])
        if quote in manuscript and 5 <= len(_words(quote)) <= 12:
            exact[label] = quote
            continue
        projected = _project_exact_evidence(quote, manuscript)
        if projected is None:
            raise ValueError(f"pairwise evidence for {label} is unsupported")
        exact[label] = projected[0]
        projections[label] = {
            "unsupported_quote": quote, "exact_replacement": projected[0],
            "similarity": round(projected[1], 4),
            "method": "nearest_contiguous_manuscript_span",
        }
    value["evidence"] = exact
    if projections:
        value["evidence_projections"] = projections
    return value


def parse_trajectory_critic(raw: str) -> dict[str, Any]:
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("trajectory critic returned no JSON")
    value = json.loads(raw[start:end + 1])
    required = {
        "causal_coherence", "character_specificity", "romantic_engine",
        "epistemic_texture", "novelty", "dramatizability",
    }
    scores = value.get("scores", {})
    if set(scores) != required or any(not 1 <= int(item) <= 7 for item in scores.values()):
        raise ValueError("trajectory critic schema invalid")
    value["mean_score"] = sum(float(item) for item in scores.values()) / len(scores)
    return value


def parse_critic(raw: str, continuation: str) -> dict[str, Any]:
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("critic returned no JSON object")
    value = json.loads(raw[start:end + 1])
    required = {
        "specificity", "subtext", "relational_asymmetry", "spatial_clarity",
        "dramatic_dwell", "prose_freshness", "causal_progress",
    }
    scores = value.get("scores", {})
    if set(scores) != required or any(not 1 <= int(item) <= 7 for item in scores.values()):
        raise ValueError("critic score schema invalid")
    bank = _evidence_bank(continuation, "E")
    supplied_id = str(value.get("evidence_id", ""))
    if supplied_id:
        ids = re.findall(r"E\d{2}", supplied_id)
        valid_ids = [item for item in ids if item in bank]
        if not valid_ids:
            raise ValueError(f"unknown critic evidence id: {supplied_id}")
        selected_id = valid_ids[0]
        value["evidence"] = bank[selected_id]
        value["evidence_id_audit"] = {
            "supplied": supplied_id, "selected": selected_id,
        }
    evidence = str(value.get("evidence", ""))
    if evidence not in continuation or not 5 <= len(_words(evidence)) <= 12:
        projected = _project_exact_evidence(evidence, continuation)
        if projected is None:
            raise ValueError("critic evidence must be an exact 5-12 word passage")
        value["evidence_projection"] = {
            "unsupported_quote": evidence,
            "exact_replacement": projected[0],
            "similarity": round(projected[1], 4),
            "method": "nearest_contiguous_manuscript_span",
        }
        value["evidence"] = projected[0]
    value["mean_score"] = sum(float(item) for item in scores.values()) / len(scores)
    value["manuscript_hash"] = sha256_text(continuation)
    return value


def _project_exact_evidence(quote: str, manuscript: str) -> tuple[str, float] | None:
    """Map a judge's near-quote to the manuscript without changing manuscript text."""

    target = _words(quote)
    source_matches = list(WORD_RE.finditer(manuscript))
    if len(target) < 3 or len(source_matches) < 5:
        return None
    normalized_target = " ".join(target)
    preferred = min(12, max(5, len(target)))
    lengths = sorted(range(5, 13), key=lambda value: (abs(value - preferred), value))
    best: tuple[str, float] | None = None
    for length in lengths:
        for start in range(0, len(source_matches) - length + 1):
            end = start + length
            excerpt = manuscript[source_matches[start].start():source_matches[end - 1].end()]
            similarity = SequenceMatcher(None, normalized_target, " ".join(_words(excerpt))).ratio()
            if best is None or similarity > best[1]:
                best = (excerpt, similarity)
    if best is None or best[1] < 0.72:
        return None
    return best


def boltzmann_select(
    candidates: Sequence[Mapping[str, Any]],
    *,
    count: int,
    seed: int,
    temperature: float = 0.75,
) -> tuple[Mapping[str, Any], ...]:
    eligible = [item for item in candidates if item.get("eligible", True)]
    if not eligible or count <= 0:
        return ()
    ordered = sorted(eligible, key=lambda item: (-float(item["selection_score"]), str(item.get("candidate_id", ""))))
    selected: list[Mapping[str, Any]] = [ordered.pop(0)]
    rng = random.Random(seed)
    while ordered and len(selected) < count:
        best = max(float(item["selection_score"]) for item in ordered)
        weights = [math.exp((float(item["selection_score"]) - best) / max(temperature, 1e-6)) for item in ordered]
        target = rng.random() * sum(weights)
        cumulative = 0.0
        chosen = len(ordered) - 1
        for index, weight in enumerate(weights):
            cumulative += weight
            if cumulative >= target:
                chosen = index
                break
        selected.append(ordered.pop(chosen))
    return tuple(selected)


def verify_assembly(
    assembly_path: str | Path,
    project_root: str | Path,
    *,
    require_call_ledger: bool = False,
) -> dict[str, Any]:
    value = _read_json(assembly_path)
    assembly = ManuscriptAssembly(
        artifact_id=value["artifact_id"],
        spans=tuple(ModelSpan(**item) for item in value["spans"]),
        separators=tuple(value["separators"]),
        manuscript_hash=value["manuscript_hash"],
    )
    root = Path(project_root)
    text = assembly.reconstruct(root)
    resolved_calls = []
    if require_call_ledger:
        resolved_calls = [span.verify_call(root) for span in assembly.spans]
    return {
        "artifact_id": assembly.artifact_id,
        "verified": True,
        "span_count": len(assembly.spans),
        "manuscript_hash": sha256_text(text),
        "word_count": len(_words(text)),
        "call_ledger_verified": bool(require_call_ledger),
        "resolved_call_count": len(resolved_calls),
    }


def _bind_span_to_call(
    span: ModelSpan,
    calls_path: str | Path,
    project_root: str | Path,
) -> ModelSpan:
    """Bind one occurrence to exactly one completed append-only call record."""

    ledger = Path(calls_path)
    matches: list[dict[str, Any]] = []
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if (
            record.get("call_id") == span.call_id
            and record.get("status") == "completed"
            and record.get("raw_hash") == span.raw_hash
        ):
            matches.append(record)
    if len(matches) != 1:
        raise ValueError(f"call occurrence is not unique for span {span.span_id}")
    return replace(
        span,
        call_ledger_path=_relative(ledger, Path(project_root)),
        call_record_hash=hash_json(matches[0]),
    )


def _write_verified_assembly(
    path: str | Path,
    assembly: ManuscriptAssembly,
    project_root: str | Path,
) -> dict[str, Any]:
    """Reconstruct before writing; malformed assemblies never reach disk."""

    if any(span.raw_char_end <= span.raw_char_start for span in assembly.spans):
        raise ValueError("assembly may not contain an empty model span")
    text = assembly.reconstruct(Path(project_root))
    ledger_verified = all(
        span.call_ledger_path and span.call_record_hash for span in assembly.spans
    )
    if ledger_verified:
        for span in assembly.spans:
            span.verify_call(Path(project_root))
    payload = assembly.public_dict()
    if sha256_text(text) != payload["manuscript_hash"]:
        raise ValueError("assembly verification changed before write")
    write_json(path, payload)
    return {
        "verified": True,
        "manuscript_hash": payload["manuscript_hash"],
        "span_count": len(assembly.spans),
        "call_ledger_verified": bool(ledger_verified),
    }


def _verify_span_replay(span: ModelSpan, project_root: Path) -> dict[str, Any]:
    ledger = Path(span.call_ledger_path)
    if not ledger.is_absolute():
        ledger = project_root / ledger
    campaign_root = ledger.parent.parent
    witness_path = campaign_root / "replay" / "witnesses.jsonl"
    if not witness_path.is_file():
        raise ValueError(f"span lacks cold replay witness: {span.span_id}")
    matches: list[dict[str, Any]] = []
    for line in witness_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        witness = json.loads(line)
        if (
            witness.get("call_id") == span.call_id
            and witness.get("matches_original") is True
            and witness.get("expected_raw_hash") == span.raw_hash
            and witness.get("observed_raw_hash") == span.raw_hash
        ):
            body = {
                key: value for key, value in witness.items()
                if key not in {"witness_hash", "replayed_at"}
            }
            if witness.get("witness_hash") == hash_json(body):
                matches.append(witness)
    if len(matches) != 1:
        raise ValueError(f"span replay witness is not unique: {span.span_id}")
    return matches[0]


def _assembly_authorship(
    assembly: ManuscriptAssembly,
    text: str,
) -> dict[str, Any]:
    record = {
        "record_type": "ArtifactAuthorship",
        "schema_version": ARTIFACT_AUTHORSHIP_VERSION,
        "artifact_id": assembly.artifact_id,
        "creation_kind": "deterministic_assembly",
        "claim_scope": RESEARCH_CLAIM_SCOPE,
        "creator_id": "harness:gemma-fiction-autoresearch-v4",
        "creator_kind": "harness",
        "created_at": _now(),
        "text_sha256": sha256_text(text),
        "parents": [
            {"artifact_id": span.span_id, "text_sha256": span.text_hash}
            for span in assembly.spans
        ],
        "model_pipeline_eligible": True,
        "prose_added": False,
        "assembly_record_hash": hash_json(assembly.public_dict()),
    }
    return validate_artifact_authorship(
        record, text=text, artifact_id=assembly.artifact_id,
        require_model_pipeline=True, require_replay=False,
    )


def audit_v4_assemblies(
    project_root: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    """Inventory historical assemblies without altering any research artifact."""

    root = Path(project_root).resolve()
    runs = root / "03_scene_lab" / "runs"
    findings: list[dict[str, Any]] = []
    for path in sorted(runs.glob("prompt-autoresearch-*/**/*.json")):
        if not any(parent.name.startswith("assemblies") for parent in path.parents):
            continue
        status = "strict_verified"
        reconstruction_error = ""
        strict_error = ""
        replay_error = ""
        try:
            basic = verify_assembly(path, root)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            basic = {}
            reconstruction_error = str(exc)
            status = "invalid_reconstruction"
        if status != "invalid_reconstruction":
            try:
                verify_assembly(path, root, require_call_ledger=True)
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                strict_error = str(exc)
                status = "historical_unbound"
            if status == "strict_verified":
                value = _read_json(path)
                try:
                    for span_value in value["spans"]:
                        _verify_span_replay(ModelSpan(**span_value), root)
                except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                    replay_error = str(exc)
                    status = "strict_no_replay"
        findings.append({
            "assembly_path": _relative(path, root),
            "assembly_sha256": hash_file(path),
            "artifact_id": basic.get("artifact_id", ""),
            "manuscript_hash": basic.get("manuscript_hash", ""),
            "status": status,
            "release_eligible": status == "strict_verified",
            "reconstruction_error": reconstruction_error,
            "strict_error": strict_error,
            "replay_error": replay_error,
        })
    counts: dict[str, int] = {}
    for item in findings:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    report = {
        "record_type": "V4AssemblyInvalidationLedger",
        "version": "v4-assembly-audit.v1",
        "project_root": str(root),
        "counts": counts,
        "total": len(findings),
        "findings": findings,
        "policy": {
            "invalid_reconstruction": "quarantined; never package",
            "historical_unbound": "development-only until superseded by canonical call references",
            "strict_no_replay": "development-only until exact cold replay exists",
            "strict_verified": "assembly provenance prerequisite passed",
        },
        "audited_at": _now(),
    }
    report["audit_hash"] = hash_json({
        key: value for key, value in report.items() if key != "audited_at"
    })
    write_json(output_path, report)
    return report


def cold_replay_v4_call(
    *,
    campaign_dir: str | Path,
    call_id: str,
    client: LlamaClient,
    admission: SharedEndpointAdmission,
) -> dict[str, Any]:
    """Reissue one frozen base call after erasing KV state.

    This is deliberately stricter than manuscript reconstruction: it proves
    that the recorded prompt, sampler, seed, runtime, and stop policy reproduce
    the preserved raw Gemma response without a cached prefix or prose repair.
    """

    root = Path(campaign_dir)
    matches: list[tuple[Path, dict[str, Any]]] = []
    for ledger in sorted(root.glob("**/calls.jsonl")):
        completed = _latest(ledger, "call_id").get(call_id)
        if completed is not None:
            matches.append((ledger, completed))
    if len(matches) != 1:
        raise ValueError(
            f"cold replay requires one completed call, found {len(matches)} for {call_id}"
        )
    ledger, call = matches[0]
    prompt = str(call.get("prompt", ""))
    if not prompt:
        prompt_path = Path(str(call.get("prompt_path", "")))
        if not prompt_path.is_absolute():
            prompt_path = Path.cwd() / prompt_path
        if not prompt_path.is_file():
            raise ValueError("cold replay requires preserved prompt bytes")
        prompt = prompt_path.read_text(encoding="utf-8")
    if sha256_text(prompt) != call.get("prompt_hash"):
        raise ValueError("cold replay prompt hash mismatch")
    sampler = dict(call.get("sampler", {}))
    max_tokens = int(call.get("max_tokens", 0))
    if max_tokens <= 0:
        raise ValueError("cold replay call lacks max_tokens")
    seed = int(call["seed"])
    expected = str(call.get("raw_hash", ""))
    if not expected:
        raise ValueError("cold replay call lacks expected raw hash")
    erased_slots = client.erase_idle_slots()
    prompt_tokens = client.token_count(prompt)
    with admission.acquire(
        owner=f"cold-replay:{call_id}", prompt_hash=str(call["prompt_hash"]),
        prompt_tokens=prompt_tokens, completion_tokens=max_tokens,
    ):
        result = client.complete_raw(
            prompt=prompt, seed=seed, max_tokens=max_tokens,
            temperature=float(sampler.get("temperature", 0.98)),
            top_p=float(sampler.get("top_p", 0.98)),
            min_p=float(sampler.get("min_p", 0.02)),
            xtc_probability=float(sampler.get("xtc_probability", 0.15)),
            extra={
                key: value for key, value in sampler.items()
                if key not in {"temperature", "top_p", "min_p", "xtc_probability"}
            } or None,
            stop=MANUSCRIPT_STOP,
        )
    observed = sha256_text(result.content)
    witness = {
        "record_type": "V4ColdReplayWitness", "version": VERSION,
        "call_id": call_id, "call_ledger": str(ledger),
        "prompt_hash": call["prompt_hash"], "seed": seed,
        "sampler": sampler, "max_tokens": max_tokens,
        "expected_raw_hash": expected, "observed_raw_hash": observed,
        "matches_original": observed == expected, "cold_replay": True,
        "erased_slots": erased_slots, "runtime": _endpoint_runtime_provenance(client),
        "replayed_at": _now(),
    }
    witness["witness_hash"] = hash_json(
        {key: value for key, value in witness.items() if key != "replayed_at"}
    )
    append_jsonl(root / "replay" / "witnesses.jsonl", witness)
    if not witness["matches_original"]:
        raise ValueError("cold replay did not reproduce the preserved raw Gemma response")
    return witness


def init_campaign(
    *,
    campaign_dir: str | Path,
    corpus_path: str | Path,
    benchmarks_path: str | Path,
    project_root: str | Path,
    benchmark_seal_path: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(campaign_dir)
    root.mkdir(parents=True, exist_ok=True)
    corpus = Path(corpus_path).resolve()
    benchmarks = Path(benchmarks_path).resolve()
    recipes = initial_recipes()
    source_tree = _source_tree_fingerprint(project_root)
    benchmark_seal: dict[str, Any] | None = None
    seal_path: Path | None = None
    if benchmark_seal_path is not None:
        seal_path = Path(benchmark_seal_path).resolve()
        benchmark_seal = verify_benchmark_seal(
            seal_path=seal_path, project_root=project_root,
        )
        if benchmark_seal["benchmark_file_hash"] != hash_file(benchmarks):
            raise ValueError("benchmark seal does not bind the selected benchmark file")
    payload = {
        "record_type": "GemmaFictionAutoresearchCampaign",
        "version": VERSION,
        "campaign_id": root.name,
        "project_root": str(Path(project_root).resolve()),
        "corpus_path": str(corpus), "corpus_hash": hash_file(corpus),
        "benchmarks_path": str(benchmarks), "benchmark_hash": hash_file(benchmarks),
        "recipes": [item.public_dict() for item in recipes],
        "s01_cell": asdict(s01_cell()) | {"cell_hash": s01_cell().cell_hash},
        "only_manuscript_author": "gemma-4-31b-base",
        "critic_policy": "read-only-ranking-no-prose",
        "executable_source_tree_hash": source_tree["tree_hash"],
        "executable_source_files": source_tree["files"],
        "experiment_mode": (
            "sealed_confirmation" if benchmark_seal is not None else "development"
        ),
        "benchmark_seal_path": str(seal_path) if seal_path else "",
        "benchmark_seal_file_hash": hash_file(seal_path) if seal_path else "",
        "benchmark_seal_hash": (
            str(benchmark_seal["seal_hash"]) if benchmark_seal else ""
        ),
        "prompt_policy_versions": {
            "generation_renderer": PROMPT_RENDER_VERSION,
            "retrieval": RETRIEVAL_VERSION,
            "runway": RUNWAY_PROMPT_VERSION,
            "hard_gate": HARD_GATE_VERSION,
            "topology_gate": TOPOLOGY_GATE_VERSION,
            "topology_spark_gate": TOPOLOGY_SPARK_GATE_VERSION,
            "movement_gate": MOVEMENT_GATE_VERSION,
            "runway_gate": RUNWAY_GATE_VERSION,
            "literary_critic": CRITIC_PROMPT_VERSION,
            "manuscript_boundary": MANUSCRIPT_BOUNDARY_VERSION,
            "extraction": EXTRACTION_VERSION,
        },
        "s01_movement_schedule_hash": hash_json(S01_MOVEMENTS),
        "s01_movement_word_bands_hash": hash_json(S01_MOVEMENT_WORD_BANDS),
        "anti_copy_policy": asdict(AntiCopyPolicy()),
        "created_at": _now(),
    }
    payload["campaign_hash"] = hash_json({key: value for key, value in payload.items() if key != "created_at"})
    path = root / "campaign_manifest.v1.json"
    if path.is_file():
        prior = _read_json(path)
        if prior.get("campaign_hash") != payload["campaign_hash"]:
            raise ValueError("campaign inputs changed; use a new immutable campaign directory")
        return prior
    write_json(path, payload)
    return payload


BENCHMARK_SEAL_VERSION = "sealed-fiction-benchmark.v1"
CONFIRMATION_OPEN_VERSION = "confirmation-opening.v1"
BENCHMARK_PARTITIONS = ("development", "calibration", "confirmation")
BENCHMARK_CELL_METADATA_FIELDS = (
    "genre", "story_world_id", "source_book_id", "pov", "scene_purpose",
    "heat_band", "affect_arc",
)
BENCHMARK_PROTOCOL_FIELDS = (
    "primary_metric", "secondary_metrics", "prompt_arms", "sampler_arms",
    "selection_arms", "seed_manifest", "critic_manifest", "gate_manifest",
    "analysis_plan", "stopping_rule",
)


def seal_benchmark_protocol(
    *,
    benchmarks_path: str | Path,
    protocol_path: str | Path,
    output_path: str | Path,
    project_root: str | Path,
    minimum_cells: int = 24,
) -> dict[str, Any]:
    """Freeze a cross-world benchmark and its complete confirmatory analysis plan.

    The seal is intentionally stricter than the development benchmark format.
    It prevents a campaign from calling an observed prompt/gate mutation a
    confirmatory result by binding the cell split, code, arms, seeds, critics,
    gates, stopping rule, and primary metric before the split is opened.
    """

    benchmark_file = Path(benchmarks_path).resolve()
    protocol_file = Path(protocol_path).resolve()
    benchmark = _read_json(benchmark_file)
    protocol = _read_json(protocol_file)
    cells = benchmark.get("cells")
    if not isinstance(cells, list) or len(cells) < minimum_cells:
        raise ValueError(
            f"sealed benchmark requires at least {minimum_cells} cells"
        )
    cell_ids = [str(item.get("cell_id", "")) for item in cells]
    if any(not item for item in cell_ids) or len(set(cell_ids)) != len(cell_ids):
        raise ValueError("benchmark cell IDs must be nonempty and unique")
    for item in cells:
        recorded = str(item.get("cell_hash", ""))
        body = {key: value for key, value in item.items() if key != "cell_hash"}
        if recorded and recorded != hash_json(body):
            raise ValueError(f"benchmark cell hash mismatch: {item['cell_id']}")

    partitions = protocol.get("partitions")
    if not isinstance(partitions, Mapping):
        raise ValueError("benchmark protocol requires partitions")
    split_sets: dict[str, set[str]] = {}
    for name in BENCHMARK_PARTITIONS:
        values = partitions.get(name)
        if not isinstance(values, list) or not values:
            raise ValueError(f"benchmark partition {name} must be nonempty")
        split_sets[name] = {str(item) for item in values}
        if len(split_sets[name]) != len(values):
            raise ValueError(f"benchmark partition {name} contains duplicates")
    for left, right in combinations(BENCHMARK_PARTITIONS, 2):
        overlap = split_sets[left] & split_sets[right]
        if overlap:
            raise ValueError(
                f"benchmark partitions overlap ({left}/{right}): "
                + ", ".join(sorted(overlap))
            )
    assigned = set().union(*split_sets.values())
    if assigned != set(cell_ids):
        missing = sorted(set(cell_ids) - assigned)
        unknown = sorted(assigned - set(cell_ids))
        raise ValueError(
            f"benchmark partitions must cover exactly all cells; "
            f"missing={missing}, unknown={unknown}"
        )

    metadata = protocol.get("cell_metadata")
    if not isinstance(metadata, Mapping):
        raise ValueError("benchmark protocol requires cell_metadata")
    for cell_id in cell_ids:
        item = metadata.get(cell_id)
        if not isinstance(item, Mapping):
            raise ValueError(f"benchmark metadata missing: {cell_id}")
        missing_fields = [
            name for name in BENCHMARK_CELL_METADATA_FIELDS if not item.get(name)
        ]
        if missing_fields:
            raise ValueError(
                f"benchmark metadata incomplete for {cell_id}: "
                + ", ".join(missing_fields)
            )
    for split_key in ("story_world_id", "source_book_id"):
        owners: dict[str, str] = {}
        for partition, ids in split_sets.items():
            for cell_id in ids:
                value = str(metadata[cell_id][split_key])
                prior = owners.setdefault(value, partition)
                if prior != partition:
                    raise ValueError(
                        f"{split_key} {value!r} leaks across {prior}/{partition}"
                    )

    missing_protocol = [
        name for name in BENCHMARK_PROTOCOL_FIELDS if not protocol.get(name)
    ]
    if missing_protocol:
        raise ValueError(
            "benchmark protocol incomplete: " + ", ".join(missing_protocol)
        )
    source_tree = _source_tree_fingerprint(project_root)
    payload = {
        "record_type": "SealedFictionBenchmark",
        "version": BENCHMARK_SEAL_VERSION,
        "benchmark_path": str(benchmark_file),
        "benchmark_file_hash": hash_file(benchmark_file),
        "benchmark_payload_hash": hash_json(benchmark),
        "protocol_path": str(protocol_file),
        "protocol_file_hash": hash_file(protocol_file),
        "protocol_payload_hash": hash_json(protocol),
        "cell_count": len(cells),
        "cell_hashes": {
            item["cell_id"]: str(item.get("cell_hash") or hash_json(item))
            for item in cells
        },
        "partitions": {
            name: sorted(split_sets[name]) for name in BENCHMARK_PARTITIONS
        },
        "partition_hashes": {
            name: hash_json(sorted(split_sets[name])) for name in BENCHMARK_PARTITIONS
        },
        "cell_metadata": {cell_id: dict(metadata[cell_id]) for cell_id in sorted(cell_ids)},
        "frozen_protocol": {
            name: protocol[name] for name in BENCHMARK_PROTOCOL_FIELDS
        },
        "executable_source_tree_hash": source_tree["tree_hash"],
        "executable_source_files": source_tree["files"],
        "sealed_at": _now(),
    }
    payload["seal_hash"] = hash_json(
        {key: value for key, value in payload.items() if key != "sealed_at"}
    )
    output = Path(output_path).resolve()
    if output.is_file():
        prior = _read_json(output)
        if prior.get("seal_hash") != payload["seal_hash"]:
            raise ValueError("benchmark seal already exists with different inputs")
        return prior
    write_json(output, payload)
    return payload


def verify_benchmark_seal(
    *, seal_path: str | Path, project_root: str | Path,
) -> dict[str, Any]:
    seal = _read_json(seal_path)
    if seal.get("record_type") != "SealedFictionBenchmark" or seal.get("version") != BENCHMARK_SEAL_VERSION:
        raise ValueError("invalid benchmark seal schema")
    body = {key: value for key, value in seal.items() if key not in {"sealed_at", "seal_hash"}}
    if seal.get("seal_hash") != hash_json(body):
        raise ValueError("benchmark seal hash mismatch")
    if hash_file(seal["benchmark_path"]) != seal.get("benchmark_file_hash"):
        raise ValueError("sealed benchmark file changed")
    if hash_file(seal["protocol_path"]) != seal.get("protocol_file_hash"):
        raise ValueError("sealed benchmark protocol changed")
    current_tree = _source_tree_fingerprint(project_root)
    if current_tree["tree_hash"] != seal.get("executable_source_tree_hash"):
        raise ValueError("sealed benchmark executable source tree changed")
    return seal


def open_confirmation_benchmark(
    *, campaign_dir: str | Path,
) -> dict[str, Any]:
    """Write the one-time receipt that opens a sealed confirmation split."""

    root = Path(campaign_dir).resolve()
    campaign = _read_json(root / "campaign_manifest.v1.json")
    if campaign.get("experiment_mode") != "sealed_confirmation":
        raise ValueError("campaign is development-only and has no sealed confirmation split")
    seal = verify_benchmark_seal(
        seal_path=campaign["benchmark_seal_path"],
        project_root=campaign["project_root"],
    )
    if hash_file(campaign["benchmark_seal_path"]) != campaign.get("benchmark_seal_file_hash"):
        raise ValueError("campaign benchmark seal file changed")
    if seal.get("seal_hash") != campaign.get("benchmark_seal_hash"):
        raise ValueError("campaign benchmark seal identity mismatch")
    receipt_path = root / "confirmation_opening.v1.json"
    receipt = {
        "record_type": "ConfirmationOpening",
        "version": CONFIRMATION_OPEN_VERSION,
        "campaign_id": campaign["campaign_id"],
        "campaign_hash": campaign["campaign_hash"],
        "benchmark_seal_hash": seal["seal_hash"],
        "confirmation_partition_hash": seal["partition_hashes"]["confirmation"],
        "confirmation_cell_ids": seal["partitions"]["confirmation"],
        "opened_at": _now(),
    }
    receipt["opening_hash"] = hash_json(
        {key: value for key, value in receipt.items() if key != "opened_at"}
    )
    if receipt_path.is_file():
        prior = _read_json(receipt_path)
        if prior.get("opening_hash") != receipt["opening_hash"]:
            raise ValueError("confirmation split was opened under another campaign identity")
        return prior
    write_json(receipt_path, receipt)
    return receipt


def merge_apprenticeship_retrievals(
    *,
    base_corpus_path: str | Path,
    index_manifest_path: str | Path,
    retrieval_paths: Sequence[str | Path],
    output_path: str | Path,
) -> dict[str, Any]:
    """Add retrieved complete scenes to the v4 prompt corpus with hash provenance."""

    base_path = Path(base_corpus_path).resolve()
    index_path = Path(index_manifest_path).resolve()
    base = _read_json(base_path)
    index = _read_json(index_path)
    database = Path(index["database"]).resolve()
    if not database.is_file():
        raise ValueError("apprenticeship scene database is missing")
    retrieval_records: list[tuple[Path, dict[str, Any]]] = []
    selected_ids: list[str] = []
    scene_queries: dict[str, set[str]] = {}
    for raw_path in retrieval_paths:
        path = Path(raw_path).resolve()
        payload = _read_json(path)
        if payload.get("index_hash") != index.get("index_hash"):
            raise ValueError("retrieval was produced by a different apprenticeship index")
        retrieval_records.append((path, payload))
        query_id = str(payload.get("query", {}).get("query_id", path.stem))
        for item in payload.get("selected", []):
            scene_id = str(item["scene_id"])
            selected_ids.append(scene_id)
            scene_queries.setdefault(scene_id, set()).add(query_id)
    selected_ids = list(dict.fromkeys(selected_ids))
    imported: list[dict[str, Any]] = []
    # sqlite3.Connection's context manager commits or rolls back but does not
    # close the handle.  `closing` makes ownership explicit and prevents a
    # connection from surviving until GC after each corpus merge.
    with closing(sqlite3.connect(database)) as connection:
        connection.row_factory = sqlite3.Row
        for number, scene_id in enumerate(selected_ids, 1):
            row = connection.execute(
                "SELECT * FROM scenes WHERE scene_id = ?", (scene_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"retrieved scene missing from index: {scene_id}")
            if row["partition_name"] != "profiling":
                raise ValueError(f"non-profiling scene cannot enter prompts: {scene_id}")
            text = str(row["text_value"])
            if sha256_text(text) != row["text_hash"]:
                raise ValueError(f"indexed scene text hash mismatch: {scene_id}")
            facets = set(json.loads(row["facets_json"]))
            queries = scene_queries.get(scene_id, set())
            if "explicit-intimacy" in facets:
                heat, mode = "explicit", "married-intimacy"
            elif any("charged-restraint" in item for item in queries):
                heat, mode = "charged-restraint", "non-sex-sex-scene"
            elif any("fulcrum-calibration" in item for item in queries) and "romantic-charge" in facets:
                heat, mode = "charged-restraint", "non-sex-sex-scene"
            elif queries and all("institutional-pressure" in item for item in queries):
                heat, mode = "none", "nonsexual-pressure"
            elif "embodied-intimacy" in facets:
                heat, mode = "open-door-nongraphic", "married-intimacy"
            elif "romantic-charge" in facets:
                heat, mode = "charged-restraint", "non-sex-sex-scene"
            else:
                heat, mode = "none", "nonsexual-pressure"
            imported.append(asdict(SourcePassage(
                passage_id=f"apprenticeship.{scene_id}",
                example_number=10_000 + number,
                title=str(row["title"]), source_work=str(row["title"]),
                partition="profiling",
                location=f"chapter-{row['chapter_index']}.scene-{row['scene_index']}",
                text_hash=str(row["text_hash"]), word_count=int(row["word_count"]),
                intimacy_mode=mode, heat_band=heat, prompt_eligible=True, text=text,
            )))
    existing = {str(item["passage_id"]): dict(item) for item in base["passages"]}
    for item in imported:
        prior = existing.get(item["passage_id"])
        if prior:
            # Import numbering is presentation metadata and can differ when a
            # later retrieval overlaps an earlier one.  Identity is the stable
            # passage ID plus the preserved source bytes, not retrieval order.
            for field in ("text_hash", "text", "partition", "source_work", "location"):
                if prior.get(field) != item.get(field):
                    raise ValueError(
                        f"imported scene conflicts with existing passage: "
                        f"{item['passage_id']} ({field})"
                    )
            continue
        existing[item["passage_id"]] = item
    payload = dict(base)
    payload["record_type"] = "ExpandedAutoresearchCorpus"
    payload["version"] = VERSION
    payload["passages"] = [existing[key] for key in sorted(existing)]
    payload["partitions"] = {
        name: [item["passage_id"] for item in payload["passages"] if item["partition"] == name]
        for name in ("profiling", "calibration", "holdout")
    }
    payload["apprenticeship_import"] = {
        "base_corpus": str(base_path), "base_corpus_hash": hash_file(base_path),
        "prior_apprenticeship_import": base.get("apprenticeship_import", {}),
        "index_manifest": str(index_path), "index_manifest_hash": hash_file(index_path),
        "index_hash": index["index_hash"], "database_hash": hash_file(database),
        "retrievals": [
            {"path": str(path), "file_hash": hash_file(path), "retrieval_hash": item.get("retrieval_hash")}
            for path, item in retrieval_records
        ],
        "imported_passage_ids": [item["passage_id"] for item in imported],
    }
    payload["compiled_at"] = _now()
    payload.pop("corpus_hash", None)
    payload["corpus_hash"] = hash_json({
        key: value for key, value in payload.items() if key != "compiled_at"
    })
    write_json(output_path, payload)
    return {
        "output": str(Path(output_path).resolve()), "corpus_hash": payload["corpus_hash"],
        "passage_count": len(payload["passages"]), "imported_count": len(imported),
        "imported_passage_ids": payload["apprenticeship_import"]["imported_passage_ids"],
    }


SOURCE_GRAPH_FIELDS = (
    "emotional_offer", "emotional_counteroffer", "relationship_history",
    "present_stakes", "dialogue_act_sequence", "body_language_counterpoint",
    "sensory_channels", "narrative_distance_curve", "physical_logistics",
    "agency_actions", "relationship_delta", "story_state_change",
    "intimacy_mode", "heat_band",
)
SOURCE_GRAPH_LIST_FIELDS = frozenset({
    "dialogue_act_sequence", "body_language_counterpoint", "sensory_channels",
    "narrative_distance_curve", "physical_logistics", "agency_actions",
})


def source_graph_annotation_prompt(passage: SourcePassage) -> str:
    """Ask a read-only local critic for retrieval semantics, never new prose."""

    return (
        "Analyze this existing fiction passage for retrieval. Do not rewrite it, "
        "continue it, or imitate it. Return one compact JSON object only. Use short "
        "content-neutral descriptions, not quotations. intimacy_mode must be one of "
        "nonsexual-pressure, charged-contact, non-sex-sex-scene, married-intimacy, "
        "consummation, aftermath, reconciliation. heat_band must be one of none, "
        "charged-restraint, open-door-nongraphic, explicit. Arrays contain 1-5 terse "
        "items. Describe what actually occurs, including failed or absent agency turns.\n\n"
        "PASSAGE\n" + passage.text + "\n\nJSON FIELDS\n" + ", ".join(SOURCE_GRAPH_FIELDS)
    )


def parse_source_graph_annotation(
    raw: str, passage: SourcePassage,
) -> IntimacySceneGraph:
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("source graph annotation returned no JSON object")
    value = json.loads(raw[start:end + 1])
    missing = [name for name in SOURCE_GRAPH_FIELDS if name not in value]
    if missing:
        raise ValueError("source graph annotation missing: " + ", ".join(missing))
    if value["intimacy_mode"] not in {
        "nonsexual-pressure", "charged-contact", "non-sex-sex-scene",
        "married-intimacy", "consummation", "aftermath", "reconciliation",
    }:
        raise ValueError("invalid annotated intimacy_mode")
    if value["heat_band"] not in {
        "none", "charged-restraint", "open-door-nongraphic", "explicit",
    }:
        raise ValueError("invalid annotated heat_band")
    normalized: dict[str, Any] = {}
    for name in SOURCE_GRAPH_FIELDS:
        item = value[name]
        if name in SOURCE_GRAPH_LIST_FIELDS:
            if isinstance(item, str):
                item = [item]
            if isinstance(item, list) and not item:
                item = ["not established in passage"]
            if not isinstance(item, list):
                raise ValueError(f"annotated {name} must contain 1-5 items")
            normalized[name] = tuple(_truncate_words(str(part), 24) for part in item[:5])
        else:
            if item is None or (isinstance(item, str) and not item.strip()):
                item = "not established in passage"
            if not isinstance(item, str):
                item = str(item)
            normalized[name] = _truncate_words(item, 36)
    return IntimacySceneGraph(
        graph_id=f"graph.{passage.passage_id}.local-critic-v1",
        passage_id=passage.passage_id,
        **normalized,
    )


def ensure_excerpt_graph_annotations(
    *,
    cache_root: Path,
    movement_id: str,
    movement: str,
    passages: Sequence[SourcePassage],
    critic: LlamaClient,
) -> tuple[dict[str, IntimacySceneGraph], dict[str, str]]:
    """Back-translate the exact excerpts used in one base-model prompt.

    The local instruction model is an annotator only.  Its output can influence
    documentary control text, never manuscript text.  Raw annotation responses
    and prompts are retained so every graph claim remains inspectable.
    """

    root = cache_root / "excerpt-graphs" / movement_id
    records_path = root / "graphs.jsonl"
    calls_path = root / "calls.jsonl"
    completed = _latest(records_path, "annotation_id")
    graphs: dict[str, IntimacySceneGraph] = {}
    graph_hashes: dict[str, str] = {}
    for passage in passages:
        excerpt_hash = sha256_text(passage.text)
        annotation_id = f"{passage.passage_id}:{excerpt_hash}"
        prompt = source_graph_annotation_prompt(passage)
        prompt_hash = sha256_text(prompt)
        request_hash = hash_json({
            "version": "exact-excerpt-graph.v1",
            "movement_id": movement_id,
            "movement_hash": sha256_text(movement),
            "source_id": passage.passage_id,
            "excerpt_hash": excerpt_hash,
            "prompt_hash": prompt_hash,
            "critic_model": critic.model,
        })
        prior = completed.get(annotation_id)
        if prior:
            if prior.get("annotation_request_hash") != request_hash:
                raise ValueError(
                    f"excerpt graph resume hash mismatch: {annotation_id}"
                )
            graph = _graph_from_record(prior["graph"])
            graphs[passage.passage_id] = graph
            graph_hashes[passage.passage_id] = str(prior["graph_hash"])
            continue
        prompt_path = root / "prompts" / f"{sha256_text(annotation_id)[:16]}.txt"
        raw_path = root / "raw" / f"{sha256_text(annotation_id)[:16]}.txt"
        atomic_write_text(prompt_path, prompt)
        call = {
            "record_type": "ReadOnlyExcerptGraphCall", "version": VERSION,
            "call_id": f"excerpt-graph:{annotation_id}", "status": "started",
            "annotation_id": annotation_id, "movement_id": movement_id,
            "source_id": passage.passage_id, "excerpt_hash": excerpt_hash,
            "prompt_hash": prompt_hash, "prompt_path": str(prompt_path),
            "annotation_request_hash": request_hash, "critic_model": critic.model,
            "started_at": _now(),
        }
        append_jsonl(calls_path, call)
        result = critic.complete(
            messages=[{"role": "user", "content": prompt}],
            seed=int(sha256_text(annotation_id)[:8], 16), max_tokens=900,
            temperature=0.2, top_p=0.9, min_p=0.0,
            response_format={"type": "json_object"},
        )
        atomic_write_text(raw_path, result.content)
        graph = parse_source_graph_annotation(result.content, passage)
        graph_record = asdict(graph)
        graph_hash = hash_json(graph_record)
        record = {
            "record_type": "ExactExcerptGraph", "version": VERSION,
            "annotation_id": annotation_id, "status": "completed",
            "movement_id": movement_id, "movement_hash": sha256_text(movement),
            "source_id": passage.passage_id, "excerpt_hash": excerpt_hash,
            "annotation_request_hash": request_hash,
            "prompt_hash": prompt_hash, "prompt_path": str(prompt_path),
            "raw_hash": sha256_text(result.content), "raw_path": str(raw_path),
            "graph": graph_record, "graph_hash": graph_hash,
            "completed_at": _now(),
        }
        append_jsonl(records_path, record)
        append_jsonl(calls_path, {
            **call, "status": "completed", "raw_hash": record["raw_hash"],
            "raw_path": str(raw_path), "completed_at": record["completed_at"],
        })
        graphs[passage.passage_id] = graph
        graph_hashes[passage.passage_id] = graph_hash
    return graphs, graph_hashes


def annotate_corpus_source_graphs(
    *, input_corpus_path: str | Path, output_corpus_path: str | Path,
    critic: LlamaClient, limit: int | None = None,
) -> dict[str, Any]:
    """Add resumable local scene-graph annotations to a compiled prompt corpus."""

    input_path = Path(input_corpus_path).resolve()
    output_path = Path(output_corpus_path).resolve()
    corpus = _read_json(input_path)
    input_hash = hash_file(input_path)
    root = output_path.parent / (output_path.stem + ".annotations")
    annotations_path = root / "source_graphs.jsonl"
    calls_path = root / "calls.jsonl"
    completed = _latest(annotations_path, "passage_id")
    existing_graph_ids = {item["passage_id"] for item in corpus.get("graphs", ())}
    produced = attempted = 0
    for raw_passage in corpus.get("passages", ()):
        passage = _passage_from_record(raw_passage)
        if (
            passage.partition != "profiling" or not passage.prompt_eligible
            or passage.passage_id in existing_graph_ids
        ):
            continue
        prompt = source_graph_annotation_prompt(passage)
        prompt_hash = sha256_text(prompt)
        annotation_id = passage.passage_id
        prior = completed.get(annotation_id)
        if prior:
            expected = hash_json({
                "input_corpus_hash": input_hash, "passage_id": passage.passage_id,
                "passage_text_hash": passage.text_hash, "prompt_hash": prompt_hash,
                "critic_model": critic.model,
            })
            if prior.get("annotation_request_hash") != expected:
                raise ValueError(f"source annotation resume hash mismatch: {annotation_id}")
            continue
        if limit is not None and attempted >= limit:
            break
        attempted += 1
        request_hash = hash_json({
            "input_corpus_hash": input_hash, "passage_id": passage.passage_id,
            "passage_text_hash": passage.text_hash, "prompt_hash": prompt_hash,
            "critic_model": critic.model,
        })
        call = {
            "record_type": "ReadOnlySourceGraphCall", "version": VERSION,
            "call_id": f"source-graph:{passage.passage_id}", "status": "started",
            "input_corpus_hash": input_hash, "passage_id": passage.passage_id,
            "passage_text_hash": passage.text_hash, "prompt_hash": prompt_hash,
            "annotation_request_hash": request_hash, "critic_model": critic.model,
            "started_at": _now(),
        }
        append_jsonl(calls_path, call)
        result = critic.complete(
            messages=[{"role": "user", "content": prompt}],
            seed=int(sha256_text(passage.passage_id)[:8], 16), max_tokens=900,
            temperature=0.2, top_p=0.9, min_p=0.0,
            response_format={"type": "json_object"},
        )
        try:
            graph = parse_source_graph_annotation(result.content, passage)
        except (ValueError, json.JSONDecodeError) as exc:
            append_jsonl(calls_path, {
                **call, "status": "failed", "raw_response": result.content,
                "error": str(exc), "completed_at": _now(),
            })
            continue
        record = {
            "record_type": "LocalSourceGraphAnnotation", "version": VERSION,
            "passage_id": passage.passage_id, "status": "completed",
            "input_corpus_hash": input_hash, "passage_text_hash": passage.text_hash,
            "prompt_hash": prompt_hash, "annotation_request_hash": request_hash,
            "critic_model": critic.model, "graph": asdict(graph),
            "graph_hash": graph.graph_hash, "completed_at": _now(),
        }
        append_jsonl(annotations_path, record)
        append_jsonl(calls_path, {
            **call, "status": "completed", "raw_response": result.content,
            "graph_hash": graph.graph_hash, "completed_at": record["completed_at"],
        })
        completed[annotation_id] = record
        produced += 1

    graph_by_passage = {
        item["passage_id"]: item for item in corpus.get("graphs", ())
    }
    passage_annotations: dict[str, IntimacySceneGraph] = {}
    for item in _latest(annotations_path, "passage_id").values():
        graph = _graph_from_record(item["graph"])
        passage_annotations[graph.passage_id] = graph
        graph_by_passage[graph.passage_id] = asdict(graph) | {"graph_hash": graph.graph_hash}
    passages_out = []
    for item in corpus.get("passages", ()):
        value = dict(item)
        graph = passage_annotations.get(str(item["passage_id"]))
        if graph:
            value["intimacy_mode"] = graph.intimacy_mode
            value["heat_band"] = graph.heat_band
        passages_out.append(value)
    payload = dict(corpus)
    payload["version"] = VERSION
    payload["passages"] = passages_out
    payload["graphs"] = [graph_by_passage[key] for key in sorted(graph_by_passage)]
    payload["source_graph_annotation"] = {
        "version": "local-source-graph-annotation.v1", "input_corpus": str(input_path),
        "input_corpus_hash": input_hash, "critic_model": critic.model,
        "annotations_path": str(annotations_path),
        "annotations_hash": hash_file(annotations_path) if annotations_path.is_file() else "",
    }
    payload.pop("corpus_hash", None)
    payload["corpus_hash"] = hash_json(payload)
    write_json(output_path, payload)
    return {
        "output": str(output_path), "corpus_hash": payload["corpus_hash"],
        "new": produced, "annotated_total": len(passage_annotations),
        "graph_total": len(payload["graphs"]),
    }


def _load_campaign(root: Path) -> tuple[dict[str, Any], dict[str, Any], tuple[BenchmarkCell, ...], tuple[SourcePassage, ...], dict[str, IntimacySceneGraph]]:
    campaign = _read_json(root / "campaign_manifest.v1.json")
    if hash_file(campaign["corpus_path"]) != campaign["corpus_hash"]:
        raise ValueError("campaign corpus changed")
    if hash_file(campaign["benchmarks_path"]) != campaign["benchmark_hash"]:
        raise ValueError("campaign benchmarks changed")
    expected_tree = str(campaign.get("executable_source_tree_hash", ""))
    if expected_tree:
        current_tree = _source_tree_fingerprint(campaign["project_root"])["tree_hash"]
        if current_tree != expected_tree:
            raise ValueError("campaign executable source tree changed")
    if campaign.get("benchmark_seal_path"):
        seal = verify_benchmark_seal(
            seal_path=campaign["benchmark_seal_path"],
            project_root=campaign["project_root"],
        )
        if hash_file(campaign["benchmark_seal_path"]) != campaign.get(
            "benchmark_seal_file_hash"
        ):
            raise ValueError("campaign benchmark seal file changed")
        if seal.get("seal_hash") != campaign.get("benchmark_seal_hash"):
            raise ValueError("campaign benchmark seal identity mismatch")
    corpus = _read_json(campaign["corpus_path"])
    benchmark = _read_json(campaign["benchmarks_path"])
    passages = tuple(_passage_from_record(item) for item in corpus["passages"])
    graphs = {item["passage_id"]: _graph_from_record(item) for item in corpus["graphs"]}
    cells = tuple(_cell_from_record(item) for item in benchmark["cells"] if item["cell_id"] in {
        "charged-restraint", "married-explicit", "institutional-pressure-control",
    }) + (_cell_from_record(campaign["s01_cell"]),)
    return campaign, corpus, cells, passages, graphs


def _relative(path: Path, project_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path.resolve())


def sample_runways(
    *,
    campaign_dir: str | Path,
    client: LlamaClient,
    admission: SharedEndpointAdmission,
    seeds: Sequence[int],
    max_tokens: int = 260,
    only_cell: str = "",
    conditioning: str = "story-card",
    source_count: int = 5,
    source_ids: Sequence[str] = (),
    sampler: SamplerV4 | None = None,
) -> dict[str, Any]:
    root = Path(campaign_dir)
    campaign, _, cells, passages, graphs, = _load_campaign(root)
    project_root = Path(campaign["project_root"])
    anti_copy = AntiCopyIndex({item.passage_id: item.text for item in passages})
    if source_ids:
        requested = tuple(dict.fromkeys(source_ids))
        passage_map = {item.passage_id: item for item in passages}
        missing = [item for item in requested if item not in passage_map]
        if missing:
            raise ValueError("unknown runway source IDs: " + ", ".join(missing))
        if any(passage_map[item].partition != "profiling" for item in requested):
            raise ValueError("runway source IDs must all belong to profiling")
        passages = tuple(passage_map[item] for item in requested)
        source_count = len(passages)
    calls = root / "runways" / "calls.jsonl"
    candidates = root / "runways" / "candidates.jsonl"
    completed = _latest(candidates, "runway_id")
    produced = 0
    runway_sampler = sampler or SamplerV4(
        temperature=0.98, top_p=0.98, min_p=0.02,
        xtc_probability=0.15,
    )
    for cell in cells:
        if only_cell and cell.cell_id != only_cell:
            continue
        if conditioning == "story-card":
            prompt, source_ids = render_runway_prompt(cell), ()
        elif conditioning == "source-anthology":
            prompt, source_ids = render_source_conditioned_runway_prompt(
                cell, passages, source_count=source_count, graphs=graphs,
            )
        elif conditioning == "source-bookfront":
            prompt, source_ids = render_bookfront_runway_prompt(
                cell, passages, source_count=source_count, graphs=graphs,
            )
        elif conditioning == "source-bookfront-synopsis":
            prompt, source_ids = render_bookfront_synopsis_runway_prompt(
                cell, passages, source_count=source_count, graphs=graphs,
            )
        elif conditioning == "graph-paired-bookfront":
            prompt, source_ids = render_graph_paired_bookfront_runway_prompt(
                cell, passages, source_count=source_count, graphs=graphs,
            )
        elif conditioning == "graph-paired-canon-bookfront":
            prompt, source_ids = render_graph_paired_canon_bookfront_runway_prompt(
                cell, passages, source_count=source_count, graphs=graphs,
            )
        elif conditioning == "graph-paired-continuity-bookfront":
            prompt, source_ids = render_graph_paired_continuity_bookfront_runway_prompt(
                cell, passages, source_count=source_count, graphs=graphs,
            )
        elif conditioning == "graph-paired-named-continuity-bookfront":
            prompt, source_ids = render_graph_paired_named_continuity_bookfront_runway_prompt(
                cell, passages, source_count=source_count, graphs=graphs,
            )
        elif conditioning == "parallel-book-continuity":
            prompt, source_ids = render_parallel_book_continuity_runway_prompt(
                cell, passages, source_count=source_count, graphs=graphs,
            )
        elif conditioning == "parallel-book-persona":
            prompt, source_ids = render_parallel_book_persona_runway_prompt(
                cell, passages, source_count=source_count, graphs=graphs,
            )
        else:
            raise ValueError("unsupported runway conditioning")
        prompt_hash = sha256_text(prompt)
        prompt_tokens = client.token_count(prompt)
        for seed in seeds:
            runway_id = f"runway.{conditioning}.{cell.cell_id}.{seed}"
            sampler_config = asdict(runway_sampler)
            request_hash = _generation_request_hash(
                campaign_hash=campaign["campaign_hash"], prompt_hash=prompt_hash,
                model=client.model, seed=seed, max_tokens=max_tokens,
                sampler=sampler_config, source_ids=source_ids,
            )
            if runway_id in completed:
                _assert_resumable_request(completed[runway_id], request_hash, runway_id)
                continue
            raw_path = root / "runways" / "raw" / f"{runway_id}.txt"
            call = {
                "record_type": "V4ModelCall", "call_id": runway_id,
                "status": "started", "model": client.model,
                "runtime": _endpoint_runtime_provenance(client),
                "prompt_hash": prompt_hash, "prompt_tokens": prompt_tokens,
                "prompt": prompt, "seed": seed, "max_tokens": max_tokens,
                "conditioning": conditioning, "source_ids": list(source_ids),
                "sampler": sampler_config, "request_hash": request_hash,
                "started_at": _now(),
            }
            append_jsonl(calls, call)
            parts: list[str] = []
            def on_delta(delta: str) -> None:
                parts.append(delta)
                match = anti_copy.first_exact_match("".join(parts))
                if match:
                    raise SourceOverlapError(match)
            try:
                with admission.acquire(owner=runway_id, prompt_hash=prompt_hash, prompt_tokens=prompt_tokens, completion_tokens=max_tokens):
                    cache_preparation = prepare_prompt_family(client, prompt_hash)
                    result = client.stream_raw(
                        prompt=prompt, seed=seed, max_tokens=max_tokens,
                        temperature=runway_sampler.temperature,
                        top_p=runway_sampler.top_p, min_p=runway_sampler.min_p,
                        xtc_probability=runway_sampler.xtc_probability,
                        extra=runway_sampler.raw_extra(), on_delta=on_delta,
                        stop=MANUSCRIPT_STOP,
                    )
            except SourceOverlapError as exc:
                raw = "".join(parts)
                atomic_write_text(raw_path, raw)
                record = {
                    "record_type": "GeneratedRunway", "version": VERSION,
                    "runway_id": runway_id, "status": "completed", "cell_id": cell.cell_id,
                    "campaign_hash": campaign["campaign_hash"], "text": "",
                    "text_hash": sha256_text(""), "span": {}, "eligible": False,
                    "mechanical": {"passed": False, "diagnostics": {"stream_abort": exc.match}},
                    "overlap": {"hard_fail": True, "stream_match": exc.match},
                    "seed": seed, "prompt_hash": prompt_hash,
                    "request_hash": request_hash, "max_tokens": max_tokens,
                    "sampler": sampler_config,
                    "conditioning": conditioning, "source_ids": list(source_ids),
                    "raw_hash": sha256_text(raw), "finish_reason": "streaming_source_overlap_abort",
                    "usage": {}, "timings": {}, "completed_at": _now(),
                }
                append_jsonl(candidates, record)
                append_jsonl(calls, {**call, "status": "completed", "raw_path": str(raw_path), "raw_hash": record["raw_hash"], "finish_reason": record["finish_reason"], "cache_preparation": locals().get("cache_preparation", {}), "completed_at": record["completed_at"]})
                produced += 1
                continue
            atomic_write_text(raw_path, result.content)
            try:
                # S01 must pay a four-part opening graph; the calibration
                # runways intentionally remain shorter.  We still extract only
                # complete raw paragraphs and never pad or compress prose.
                runway_min, runway_max = runway_word_band(cell)
                text, start, end = _complete_paragraph_prefix(
                    result.content, runway_min, runway_max,
                )
                overlap = anti_copy.check(runway_id, text).to_dict()
                gate = runway_gate(cell, text, overlap)
                eligible = gate["passed"]
            except ValueError as exc:
                text, start, end, overlap, gate, eligible = "", 0, 0, {}, {"error": str(exc)}, False
            span = ModelSpan(
                span_id=runway_id, call_id=runway_id,
                raw_path=_relative(raw_path, project_root), raw_hash=sha256_text(result.content),
                raw_char_start=start, raw_char_end=end, text_hash=sha256_text(text), role="opening-runway",
            )
            record = {
                "record_type": "GeneratedRunway", "version": VERSION,
                "runway_id": runway_id, "status": "completed", "cell_id": cell.cell_id,
                "campaign_hash": campaign["campaign_hash"], "text": text,
                "text_hash": sha256_text(text), "span": asdict(span),
                "eligible": eligible, "mechanical": gate, "overlap": overlap,
                "diagnostic_features": {
                    "word_count": len(_words(text)),
                    "dialogue_mark_count": text.count("\"") + text.count("“"),
                    "sensory_term_count": len(re.findall(
                        r"\b(?:hand|voice|breath|light|sound|smell|taste|skin|door|table)\w*\b",
                        text, re.I,
                    )),
                    "promotion_use": "forbidden",
                },
                "runway_word_band": list(runway_word_band(cell)),
                "seed": seed, "prompt_hash": prompt_hash,
                "request_hash": request_hash, "max_tokens": max_tokens,
                "sampler": sampler_config,
                "conditioning": conditioning, "source_ids": list(source_ids),
                "raw_hash": sha256_text(result.content), "finish_reason": result.finish_reason,
                "usage": result.usage, "timings": result.timings, "completed_at": _now(),
            }
            append_jsonl(candidates, record)
            append_jsonl(calls, {**call, "status": "completed", "raw_path": str(raw_path), "raw_hash": record["raw_hash"], "cache_preparation": cache_preparation, "completed_at": record["completed_at"]})
            produced += 1
    records = list(_latest(candidates, "runway_id").values())
    eligible = sorted(item["runway_id"] for item in records if item.get("eligible"))
    pool = {
        "record_type": "SampledGeneratedRunwayPool", "version": VERSION,
        "campaign_hash": campaign["campaign_hash"],
        "eligible_runway_ids": eligible,
        "selection_policy": "no-automatic-promotion; read-only-critic-or-explicit-research-lead-selection-required",
    }
    pool["pool_hash"] = hash_json(pool)
    write_json(root / "runways" / "sampled_pool.v1.json", pool)
    return {"new": produced, "eligible": eligible, "pool_hash": pool["pool_hash"]}


def sample_staged_runways(
    *,
    campaign_dir: str | Path,
    client: LlamaClient,
    admission: SharedEndpointAdmission,
    seeds: Sequence[int],
    only_cell: str = "fulcrum-s01",
    source_count: int = 3,
    source_ids: Sequence[str] = (),
    conditioning: str = "parallel-book-persona",
    spark_max_tokens: int = 150,
    continuation_max_tokens: int = 560,
    spark_only: bool = False,
    sampler: SamplerV4 | None = None,
) -> dict[str, Any]:
    """Generate a base-authored opening spark, then continue from its exact bytes.

    A blank chapter boundary often makes a base model paraphrase the target ledger.
    This two-call topology searches the first-paragraph distribution cheaply, then
    gives an eligible Gemma paragraph the privileged manuscript-recency position.
    No critic or deterministic process contributes manuscript language.
    """

    root = Path(campaign_dir)
    campaign, _, cells, passages, graphs = _load_campaign(root)
    project_root = Path(campaign["project_root"])
    source_docs = {item.passage_id: item.text for item in passages}
    anti_copy = AntiCopyIndex(source_docs)
    if source_ids:
        requested = tuple(dict.fromkeys(source_ids))
        passage_map = {item.passage_id: item for item in passages}
        missing = [item for item in requested if item not in passage_map]
        if missing:
            raise ValueError("unknown staged-runway source IDs: " + ", ".join(missing))
        if any(passage_map[item].partition != "profiling" for item in requested):
            raise ValueError("staged-runway source IDs must all belong to profiling")
        passages = tuple(passage_map[item] for item in requested)
        source_count = len(passages)
    config = sampler or SamplerV4(
        temperature=0.95, top_p=0.97, min_p=0.02, xtc_probability=0.10,
    )
    calls = root / "runways" / "staged_calls.jsonl"
    sparks_path = root / "runways" / "sparks.jsonl"
    candidates_path = root / "runways" / "candidates.jsonl"
    completed_sparks = _latest(sparks_path, "spark_id")
    completed_candidates = _latest(candidates_path, "runway_id")
    produced_sparks = produced_runways = 0
    for cell in cells:
        if only_cell and cell.cell_id != only_cell:
            continue
        if conditioning == "parallel-book-persona":
            base_prompt, resolved_source_ids = render_parallel_book_persona_runway_prompt(
                cell, passages, source_count=source_count, graphs=graphs,
            )
            conditioning_id = "staged-persona"
        elif conditioning == "natural-anthology":
            base_prompt, resolved_source_ids = render_natural_anthology_runway_prompt(
                cell, passages, source_count=source_count, graphs=graphs,
            )
            conditioning_id = "staged-natural-anthology"
        elif conditioning == "direct-apprenticeship":
            base_prompt, resolved_source_ids = render_direct_apprenticeship_runway_prompt(
                cell, passages, source_count=source_count, graphs=graphs,
            )
            conditioning_id = "staged-direct-apprenticeship"
        elif conditioning == "dwell-apprenticeship":
            base_prompt, resolved_source_ids = render_dwell_apprenticeship_runway_prompt(
                cell, passages, source_count=source_count, graphs=graphs,
            )
            conditioning_id = "staged-dwell-apprenticeship"
        elif conditioning == "isomorphic-dwell":
            base_prompt, resolved_source_ids = render_isomorphic_dwell_runway_prompt(
                cell, passages, source_count=source_count, graphs=graphs,
            )
            conditioning_id = "staged-isomorphic-dwell"
        elif conditioning == "ordered-isomorphic-dwell":
            base_prompt, resolved_source_ids = render_isomorphic_dwell_runway_prompt(
                cell, passages, source_count=source_count, graphs=graphs,
                preserve_input_order=True,
            )
            conditioning_id = "staged-ordered-isomorphic-dwell"
        else:
            raise ValueError(f"unsupported staged runway conditioning: {conditioning}")
        source_ids = resolved_source_ids
        base_prompt_hash = sha256_text(base_prompt)
        for seed in seeds:
            spark_id = f"spark.{conditioning_id}.{cell.cell_id}.{seed}"
            spark_request_hash = _generation_request_hash(
                campaign_hash=campaign["campaign_hash"], prompt_hash=base_prompt_hash,
                model=client.model, seed=seed, max_tokens=spark_max_tokens,
                sampler=asdict(config), source_ids=source_ids,
            )
            spark = completed_sparks.get(spark_id)
            if spark is not None:
                _assert_resumable_request(spark, spark_request_hash, spark_id)
            else:
                raw_path = root / "runways" / "raw" / "sparks" / f"{spark_id}.txt"
                started = {
                    "record_type": "V4ModelCall", "call_id": spark_id,
                    "status": "started", "model": client.model,
                    "runtime": _endpoint_runtime_provenance(client),
                    "prompt_hash": base_prompt_hash, "prompt_tokens": client.token_count(base_prompt),
                    "prompt_path": str(root / "runways" / "prompts" / "staged-spark.txt"),
                    "seed": seed, "max_tokens": spark_max_tokens,
                    "sampler": asdict(config), "source_ids": list(source_ids),
                    "request_hash": spark_request_hash, "started_at": _now(),
                }
                atomic_write_text(Path(started["prompt_path"]), base_prompt)
                append_jsonl(calls, started)
                parts: list[str] = []
                try:
                    def on_spark_delta(delta: str) -> None:
                        parts.append(delta)
                        match = anti_copy.first_exact_match("".join(parts))
                        if match:
                            raise SourceOverlapError(match)
                    with admission.acquire(
                        owner=spark_id, prompt_hash=base_prompt_hash,
                        prompt_tokens=started["prompt_tokens"], completion_tokens=spark_max_tokens,
                    ):
                        prepare_prompt_family(client, base_prompt_hash)
                        result = client.stream_raw(
                            prompt=base_prompt, seed=seed, max_tokens=spark_max_tokens,
                            temperature=config.temperature, top_p=config.top_p,
                            min_p=config.min_p, xtc_probability=config.xtc_probability,
                            extra=config.raw_extra(), on_delta=on_spark_delta,
                            stop=MANUSCRIPT_STOP,
                        )
                    atomic_write_text(raw_path, result.content)
                    text, start, end = _complete_paragraph_prefix(result.content, 35, 160)
                    overlap = anti_copy.check(spark_id, text).to_dict()
                    gate = hard_gate(cell, text, overlap)
                    stage_ok = _s01_spark_stage_gate(text) if cell.cell_id == "fulcrum-s01" else True
                    gate["gates"]["opening_stage"] = stage_ok
                    gate["passed"] = bool(gate["passed"] and stage_ok)
                    span = ModelSpan(
                        span_id=spark_id, call_id=spark_id,
                        raw_path=_relative(raw_path, project_root),
                        raw_hash=sha256_text(result.content), raw_char_start=start,
                        raw_char_end=end, text_hash=sha256_text(text), role="opening-spark",
                    )
                    spark = {
                        "record_type": "GeneratedRunwaySpark", "version": VERSION,
                        "spark_id": spark_id, "status": "completed",
                        "campaign_hash": campaign["campaign_hash"], "cell_id": cell.cell_id,
                        "text": text, "text_hash": sha256_text(text), "span": asdict(span),
                        "eligible": gate["passed"], "mechanical": gate, "overlap": overlap,
                        "seed": seed, "prompt_hash": base_prompt_hash,
                        "request_hash": spark_request_hash, "source_ids": list(source_ids),
                        "raw_hash": sha256_text(result.content), "raw_path": _relative(raw_path, project_root),
                        "finish_reason": result.finish_reason, "usage": result.usage,
                        "timings": result.timings, "completed_at": _now(),
                    }
                except (ValueError, SourceOverlapError) as exc:
                    raw = "".join(parts)
                    atomic_write_text(raw_path, raw)
                    spark = {
                        "record_type": "GeneratedRunwaySpark", "version": VERSION,
                        "spark_id": spark_id, "status": "completed",
                        "campaign_hash": campaign["campaign_hash"], "cell_id": cell.cell_id,
                        "text": "", "text_hash": sha256_text(""), "span": {},
                        "eligible": False, "mechanical": {"passed": False, "error": str(exc)},
                        "overlap": {}, "seed": seed, "prompt_hash": base_prompt_hash,
                        "request_hash": spark_request_hash, "source_ids": list(source_ids),
                        "raw_hash": sha256_text(raw), "raw_path": _relative(raw_path, project_root),
                        "finish_reason": "failed", "usage": {}, "timings": {},
                        "completed_at": _now(),
                    }
                append_jsonl(sparks_path, spark)
                append_jsonl(calls, {
                    **started, "status": "completed", "raw_hash": spark["raw_hash"],
                    "finish_reason": spark["finish_reason"], "completed_at": spark["completed_at"],
                })
                produced_sparks += 1
            if not spark.get("eligible"):
                continue

            if spark_only:
                runway_id = f"runway.{conditioning_id}.spark.{cell.cell_id}.{seed}"
                request_hash = hash_json({
                    "record_type": "SparkOnlyRunwayAssemblyRequest",
                    "version": "spark-only-runway.v1",
                    "campaign_hash": campaign["campaign_hash"],
                    "spark_request_hash": spark_request_hash,
                    "spark_text_hash": spark["text_hash"],
                })
                if runway_id in completed_candidates:
                    _assert_resumable_request(
                        completed_candidates[runway_id], request_hash, runway_id,
                    )
                    continue
                overlap = anti_copy.check(runway_id, spark["text"]).to_dict()
                gate = opening_spark_gate(cell, spark["text"], overlap)
                span = ModelSpan(**spark["span"])
                assembly = ManuscriptAssembly(
                    runway_id, (span,), (), spark["text_hash"],
                )
                assembly_path = root / "runways" / "assemblies" / f"{runway_id}.json"
                _write_verified_assembly(assembly_path, assembly, project_root)
                record = {
                    "record_type": "GeneratedRunway", "version": VERSION,
                    "runway_id": runway_id, "runway_kind": "opening-spark",
                    "status": "completed", "campaign_hash": campaign["campaign_hash"],
                    "cell_id": cell.cell_id, "text": spark["text"],
                    "text_hash": spark["text_hash"], "spans": [asdict(span)],
                    "separators": [], "assembly_path": _relative(assembly_path, project_root),
                    "eligible": gate["passed"], "mechanical": gate, "overlap": overlap,
                    "diagnostic_features": {
                        "word_count": len(_words(spark["text"])),
                        "promotion_use": "forbidden",
                    },
                    "runway_word_band": [35, 160], "seed": seed,
                    "prompt_hash": base_prompt_hash, "request_hash": request_hash,
                    "max_tokens": spark_max_tokens, "sampler": asdict(config),
                    "conditioning": conditioning_id + "-spark-only",
                    "source_ids": list(source_ids), "raw_hash": spark["raw_hash"],
                    "raw_path": spark["raw_path"], "finish_reason": spark["finish_reason"],
                    "usage": spark["usage"], "timings": spark["timings"],
                    "completed_at": _now(),
                }
                append_jsonl(candidates_path, record)
                completed_candidates[runway_id] = record
                produced_runways += 1
                continue

            runway_id = f"runway.{conditioning_id}.{cell.cell_id}.{seed}"
            expansion_prompt = base_prompt + spark["text"] + "\n\n"
            prompt_hash = sha256_text(expansion_prompt)
            expansion_seed = seed ^ 0x51A9
            request_hash = _generation_request_hash(
                campaign_hash=campaign["campaign_hash"], prompt_hash=prompt_hash,
                model=client.model, seed=expansion_seed,
                max_tokens=continuation_max_tokens, sampler=asdict(config), source_ids=source_ids,
            )
            if runway_id in completed_candidates:
                _assert_resumable_request(completed_candidates[runway_id], request_hash, runway_id)
                continue
            prompt_path = root / "runways" / "prompts" / "staged" / f"{runway_id}.txt"
            raw_path = root / "runways" / "raw" / "staged" / f"{runway_id}.txt"
            atomic_write_text(prompt_path, expansion_prompt)
            started = {
                "record_type": "V4ModelCall", "call_id": runway_id, "status": "started",
                "model": client.model, "runtime": _endpoint_runtime_provenance(client),
                "prompt_hash": prompt_hash, "prompt_tokens": client.token_count(expansion_prompt),
                "prompt_path": str(prompt_path), "seed": expansion_seed,
                "max_tokens": continuation_max_tokens, "sampler": asdict(config),
                "source_ids": list(source_ids), "request_hash": request_hash,
                "parent_spark_id": spark_id, "started_at": _now(),
            }
            append_jsonl(calls, started)
            parts = []
            try:
                def on_delta(delta: str) -> None:
                    parts.append(delta)
                    match = anti_copy.first_exact_match(spark["text"] + "".join(parts))
                    if match:
                        raise SourceOverlapError(match)
                with admission.acquire(
                    owner=runway_id, prompt_hash=prompt_hash,
                    prompt_tokens=started["prompt_tokens"], completion_tokens=continuation_max_tokens,
                ):
                    # Spark-specific text is an appended manuscript suffix.  Keep the
                    # common apprenticeship/bookfront prefix resident while the full
                    # prompt hash remains in request provenance.
                    prepare_prompt_family(client, base_prompt_hash)
                    result = client.stream_raw(
                        prompt=expansion_prompt, seed=expansion_seed,
                        max_tokens=continuation_max_tokens, temperature=config.temperature,
                        top_p=config.top_p, min_p=config.min_p,
                        xtc_probability=config.xtc_probability, extra=config.raw_extra(),
                        on_delta=on_delta, stop=MANUSCRIPT_STOP,
                    )
                atomic_write_text(raw_path, result.content)
                spark_words = len(_words(spark["text"]))
                segment, start, end = _complete_paragraph_prefix(
                    result.content, max(80, 220 - spark_words), max(120, 420 - spark_words),
                )
                text = spark["text"] + "\n\n" + segment
                overlap = anti_copy.check(runway_id, text).to_dict()
                gate = runway_gate(cell, text, overlap)
                segment_span = ModelSpan(
                    span_id=f"{runway_id}.continuation", call_id=runway_id,
                    raw_path=_relative(raw_path, project_root), raw_hash=sha256_text(result.content),
                    raw_char_start=start, raw_char_end=end, text_hash=sha256_text(segment),
                    role="opening-runway-continuation",
                )
                spans = (ModelSpan(**spark["span"]), segment_span)
                assembly = ManuscriptAssembly(runway_id, spans, ("\n\n",), sha256_text(text))
                assembly_path = root / "runways" / "assemblies" / f"{runway_id}.json"
                _write_verified_assembly(assembly_path, assembly, project_root)
                record = {
                    "record_type": "GeneratedRunway", "version": VERSION,
                    "runway_id": runway_id, "status": "completed",
                    "campaign_hash": campaign["campaign_hash"], "cell_id": cell.cell_id,
                    "text": text, "text_hash": sha256_text(text),
                    "spans": [asdict(item) for item in spans], "separators": ["\n\n"],
                    "assembly_path": _relative(assembly_path, project_root),
                    "eligible": gate["passed"], "mechanical": gate, "overlap": overlap,
                    "diagnostic_features": {"word_count": len(_words(text)), "promotion_use": "forbidden"},
                    "runway_word_band": list(runway_word_band(cell)), "seed": expansion_seed,
                    "prompt_hash": prompt_hash, "request_hash": request_hash,
                    "max_tokens": continuation_max_tokens, "sampler": asdict(config),
                    "conditioning": conditioning_id, "source_ids": list(source_ids),
                    "parent_spark_id": spark_id, "raw_hash": sha256_text(result.content),
                    "raw_path": _relative(raw_path, project_root),
                    "finish_reason": result.finish_reason, "usage": result.usage,
                    "timings": result.timings, "completed_at": _now(),
                }
            except (ValueError, SourceOverlapError) as exc:
                raw = "".join(parts)
                atomic_write_text(raw_path, raw)
                record = {
                    "record_type": "GeneratedRunway", "version": VERSION,
                    "runway_id": runway_id, "status": "completed",
                    "campaign_hash": campaign["campaign_hash"], "cell_id": cell.cell_id,
                    "text": spark["text"], "text_hash": spark["text_hash"],
                    "spans": [spark["span"]], "separators": [],
                    "eligible": False, "mechanical": {"passed": False, "error": str(exc)},
                    "overlap": {}, "diagnostic_features": {"word_count": len(_words(spark["text"])), "promotion_use": "forbidden"},
                    "seed": expansion_seed, "prompt_hash": prompt_hash,
                    "request_hash": request_hash, "max_tokens": continuation_max_tokens,
                    "sampler": asdict(config), "conditioning": conditioning_id,
                    "source_ids": list(source_ids), "parent_spark_id": spark_id,
                    "raw_hash": sha256_text(raw), "raw_path": _relative(raw_path, project_root),
                    "finish_reason": "failed", "usage": {}, "timings": {},
                    "completed_at": _now(),
                }
            append_jsonl(candidates_path, record)
            append_jsonl(calls, {
                **started, "status": "completed", "raw_hash": record["raw_hash"],
                "finish_reason": record["finish_reason"], "completed_at": record["completed_at"],
            })
            produced_runways += 1
    return {
        "new_sparks": produced_sparks, "new_runways": produced_runways,
        "eligible_runways": sorted(
            item["runway_id"] for item in _latest(candidates_path, "runway_id").values()
            if item.get("eligible")
        ),
    }


def _load_locked_runways(root: Path) -> dict[str, dict[str, Any]]:
    value = _read_json(root / "runways" / "locked_runways.v1.json")
    return {str(key): dict(item) for key, item in value["runways"].items()}


def topology_screen_movement(cell: BenchmarkCell) -> str:
    """Return one observable causal transaction for topology comparisons.

    The old screen asked every recipe to "develop pressure".  That phrase is
    easy for a model to satisfy with atmosphere and therapeutic summary, so it
    measured neither causal control nor useful restraint.  These cells specify
    the same compact dramatic unit across every prompt arm while leaving all
    manuscript language to the base model.
    """

    movements = {
        "charged-restraint": (
            "Mara watches Jonah's breathing to infer what he wants and falls behind. "
            "Jonah keeps walking because he will not interpret her silence for her. "
            "Mara must say his name and ask him to wait; he stops immediately. She "
            "then makes the counteroffer herself by asking him to walk with her. End "
            "after he accepts. No kiss occurs in this movement."
        ),
        "married-explicit": (
            "A joke about the novel lets Esther ask the rescue question Simon has "
            "avoided. He answers with one concrete fact instead of reassurance. "
            "Esther answers by placing his hand where he may either stay or withdraw; "
            "his observable choice changes what she is willing to ask next. End before "
            "the encounter resolves."
        ),
        "institutional-pressure-control": (
            "Livia gives Mara a genuinely useful warm drink while positioning a chair "
            "and the clock so leaving becomes awkward. Jonah asks one practical "
            "question that makes the arrangement visible. Mara changes the arrangement "
            "herself; Livia must accept the change or expose the pressure. Keep the "
            "movement wholly nonsexual."
        ),
    }
    try:
        return movements[cell.cell_id]
    except KeyError as exc:
        raise ValueError(f"no topology-screen movement for {cell.cell_id}") from exc


def topology_screen_gate(cell: BenchmarkCell, segment: str) -> dict[str, Any]:
    """Check the small observable transaction used by topology search.

    This is intentionally narrower than a literary judge.  It only prevents a
    fluent atmospheric continuation from being counted as a successful prompt
    when it never performs the causal event the screen was built to test.
    """

    if cell.cell_id == "charged-restraint":
        checks = {
            "mara_calls_or_asks_him_to_wait": bool(re.search(
                r"[\"“][^\"”]{0,90}(?:\bwait\b|\bJonah\b\s*[?!,.]?)",
                segment, re.I | re.S,
            )),
            "jonah_stops_immediately": bool(re.search(
                r"\b(?:Jonah|he)\b.{0,100}\b(?:stopped|halted|turned back|waited)\b",
                segment, re.I | re.S,
            )),
            "mara_asks_him_to_walk_with_her": _mara_walking_invitation(segment),
            "no_kiss": not bool(re.search(r"\bkiss(?:ed|es|ing)?\b", segment, re.I)),
        }
    elif cell.cell_id == "married-explicit":
        checks = {
            "concrete_rescue_fact": bool(re.search(
                r"\b(?:rescue|rope|door|window|radio|boat|vehicle|blood|fire)\b",
                segment, re.I,
            )),
            "esther_places_his_hand": bool(re.search(
                r"\bEsther\b.{0,180}\b(?:placed|guided|drew|moved)\b.{0,80}\bhand\b",
                segment, re.I | re.S,
            )),
            "simon_observable_choice": bool(re.search(
                r"\bSimon\b.{0,180}\b(?:stayed|withdrew|closed|turned|answered|moved)\b",
                segment, re.I | re.S,
            )),
        }
    elif cell.cell_id == "institutional-pressure-control":
        checks = {
            "useful_warm_drink": bool(re.search(
                r"\b(?:warm|hot)\b.{0,40}\b(?:drink|tea|cup|mug)\b|"
                r"\b(?:drink|tea|cup|mug)\b.{0,40}\b(?:warm|hot)\b",
                segment, re.I | re.S,
            )),
            "practical_question": bool(re.search(r"[?][\"”']?", segment)),
            "mara_changes_arrangement": bool(re.search(
                r"\bMara\b.{0,220}\b(?:moved|changed|opened|stood|shifted|refused|said no)\b",
                segment, re.I | re.S,
            )),
            "no_erotic_contact": not bool(re.search(
                r"\b(?:kiss|arous|breast|thigh|desire|sensual)\w*\b",
                segment, re.I,
            )),
        }
    else:
        raise ValueError(f"no topology-screen gate for {cell.cell_id}")
    return {
        "version": TOPOLOGY_GATE_VERSION,
        "passed": all(checks.values()),
        "checks": checks,
    }


def _mara_walking_invitation(segment: str) -> bool:
    for match in re.finditer(r"[\"“]([^\"”]{1,180})[\"”]", segment, re.S):
        utterance = match.group(1)
        if not re.search(
            r"\b(?:walk|come)\b.{0,45}\b(?:with me|with you|together)\b|"
            r"\b(?:want|like)\b.{0,35}\b(?:keep )?walking\b",
            utterance, re.I | re.S,
        ):
            continue
        before = segment[max(0, match.start() - 120):match.start()]
        after = segment[match.end():match.end() + 100]
        if re.match(r"\s*(?:he|Jonah)\b", after, re.I):
            continue
        if re.match(r"\s*(?:she|Mara)\b", after, re.I):
            return True
        if re.search(
            r"\bMara\b.{0,80}\b(?:said|asked|answered|offered|held out|made the answer)\b[^\n]*$",
            before, re.I | re.S,
        ):
            return True
    return False


def phase_gate(
    phase: str,
    cell: BenchmarkCell,
    item: Mapping[str, Any],
    overlap: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply the complete phase contract; generic gates may not erase it."""

    if phase == "runways":
        return runway_gate(cell, str(item["text"]), overlap)
    gate = hard_gate(cell, str(item["text"]), overlap)
    if phase.startswith("topology"):
        segment = str(item.get("segment", "")).strip()
        if not segment and phase in {"topology-staged", "topology-branch"}:
            segment = "\n\n".join(
                value for value in (
                    str(item.get("spark", "")).strip(),
                    str(item.get("continuation", "")).strip(),
                ) if value
            )
        transaction = topology_screen_gate(cell, segment)
        gate["gates"]["topology_transaction"] = transaction["passed"]
        gate["diagnostics"]["topology_transaction"] = transaction
        gate["passed"] = bool(gate["passed"] and transaction["passed"])
    return gate


def topology_spark_movement(cell: BenchmarkCell) -> str:
    """First half of the screen transaction for a prose-ended staged prompt."""

    sparks = {
        "charged-restraint": (
            "Mara watches Jonah's breathing, falls behind, and must say his name and "
            "ask him to wait. Jonah stops immediately. Render only this exchange and "
            "stop before Mara asks him to walk with her. No kiss occurs."
        ),
        "married-explicit": (
            "A joke about the novel lets Esther ask the rescue question Simon has "
            "avoided. He answers with one concrete rescue fact. Stop before Esther "
            "answers him with touch."
        ),
        "institutional-pressure-control": (
            "Livia gives Mara a genuinely useful warm drink while positioning the "
            "chair and clock so leaving becomes awkward. Stop before Jonah asks his "
            "practical question. Keep the exchange wholly nonsexual."
        ),
    }
    try:
        return sparks[cell.cell_id]
    except KeyError as exc:
        raise ValueError(f"no topology spark movement for {cell.cell_id}") from exc


def topology_spark_gate(cell: BenchmarkCell, segment: str) -> dict[str, Any]:
    """Admit only base-authored sparks that establish the first causal hinge."""

    if cell.cell_id == "charged-restraint":
        checks = {
            "mara_calls_or_asks_him_to_wait": bool(re.search(
                r"[\"“][^\"”]{0,90}(?:\bwait\b|\bJonah\b\s*[?!,.]?)",
                segment, re.I | re.S,
            )),
            "jonah_stops_immediately": bool(re.search(
                r"\b(?:Jonah|he)\b.{0,100}\b(?:stopped|halted|turned back|waited)\b",
                segment, re.I | re.S,
            )),
            "counteroffer_not_yet_paid": not bool(re.search(
                r"[\"“][^\"”]{0,90}\b(?:walk|come)\b.{0,45}\b(?:with me|together)\b",
                segment, re.I | re.S,
            )),
            "no_kiss": not bool(re.search(r"\bkiss(?:ed|es|ing)?\b", segment, re.I)),
        }
    elif cell.cell_id == "married-explicit":
        checks = {
            "concrete_rescue_fact": bool(re.search(
                r"\b(?:rescue|rope|door|window|radio|boat|vehicle|blood|fire)\b",
                segment, re.I,
            )),
            "touch_not_yet_paid": not bool(re.search(
                r"\bEsther\b.{0,160}\b(?:placed|guided|drew|moved)\b.{0,80}\bhand\b",
                segment, re.I | re.S,
            )),
        }
    elif cell.cell_id == "institutional-pressure-control":
        checks = {
            "useful_warm_drink": bool(re.search(
                r"\b(?:warm|hot)\b.{0,40}\b(?:drink|tea|cup|mug)\b|"
                r"\b(?:drink|tea|cup|mug)\b.{0,40}\b(?:warm|hot)\b",
                segment, re.I | re.S,
            )),
            "no_erotic_contact": not bool(re.search(
                r"\b(?:kiss|arous|breast|thigh|desire|sensual)\w*\b",
                segment, re.I,
            )),
        }
    else:
        raise ValueError(f"no topology spark gate for {cell.cell_id}")
    return {
        "version": TOPOLOGY_SPARK_GATE_VERSION,
        "passed": all(checks.values()),
        "checks": checks,
    }


def _topology_spark_prefix(
    raw: str, cell: BenchmarkCell, maximum_words: int = 140,
) -> tuple[str, int, int]:
    """Return the earliest complete raw prefix that pays the spark hinge."""

    leading = len(raw) - len(raw.lstrip())
    view = raw[leading:]
    boundaries = {len(view)}
    boundaries.update(match.start() for match in re.finditer(r"\n\s*\n", view))
    for match in re.finditer(r"\n", view):
        before = view[:match.start()].rstrip()
        after = view[match.end():].lstrip()
        if re.search(r"[.!?][\"”’']?$", before) and re.match(r"(?:[\"“‘']|[A-Z])", after):
            boundaries.add(match.start())
    for end in sorted(boundaries):
        text = view[:end].rstrip()
        count = len(_words(text))
        if count > maximum_words:
            break
        balanced = text.count('"') % 2 == 0 and text.count("“") == text.count("”")
        if (
            count >= 3
            and balanced
            and re.search(r"[.!?][\"”’']?\s*$", text)
            and topology_spark_gate(cell, text)["passed"]
        ):
            return text, leading, leading + len(text)
    raise ValueError("no complete causal spark prefix")


def _runway_model_spans(item: Mapping[str, Any]) -> tuple[ModelSpan, ...]:
    values = item.get("spans")
    if values:
        return tuple(ModelSpan(**value) for value in values)
    return (ModelSpan(**item["span"]),)


def _runway_separators(item: Mapping[str, Any]) -> tuple[str, ...]:
    spans = _runway_model_spans(item)
    values = tuple(str(value) for value in item.get("separators", ()))
    if values:
        if len(values) != len(spans) - 1:
            raise ValueError("runway separator count does not match span count")
        return values
    return tuple("" for _ in range(max(0, len(spans) - 1)))


def inherit_verified_runways(
    *, source_campaign_dir: str | Path, target_campaign_dir: str | Path,
) -> dict[str, Any]:
    """Reuse only hash-verified Gemma runways across immutable campaigns."""

    source = Path(source_campaign_dir)
    target = Path(target_campaign_dir)
    source_campaign = _read_json(source / "campaign_manifest.v1.json")
    target_campaign = _read_json(target / "campaign_manifest.v1.json")
    source_lock_path = source / "runways" / "locked_runways.v1.json"
    source_lock = _read_json(source_lock_path)
    project_root = Path(target_campaign["project_root"])
    source_calls = source / "runways" / "calls.jsonl"
    runways: dict[str, Any] = {}
    for cell_id, item in sorted(source_lock["runways"].items()):
        bound_spans = tuple(
            span if span.call_ledger_path and span.call_record_hash
            else _bind_span_to_call(span, source_calls, project_root)
            for span in _runway_model_spans(item)
        )
        assembly = ManuscriptAssembly(
            artifact_id=str(item.get("runway_id", cell_id)),
            spans=bound_spans,
            separators=_runway_separators(item),
            manuscript_hash=str(item["text_hash"]),
        )
        extracted = assembly.reconstruct(project_root)
        for span in bound_spans:
            span.verify_call(project_root)
        if extracted != item["text"] or sha256_text(extracted) != item["text_hash"]:
            raise ValueError(f"inherited runway verification failed: {cell_id}")
        inherited = dict(item)
        inherited["spans"] = [asdict(span) for span in bound_spans]
        if len(bound_spans) == 1:
            inherited["span"] = asdict(bound_spans[0])
        runways[cell_id] = inherited
    lock = {
        "record_type": "LockedGeneratedRunways", "version": VERSION,
        "campaign_hash": target_campaign["campaign_hash"], "runways": runways,
        "inherited_from_campaign_hash": source_campaign["campaign_hash"],
        "source_lock_hash": source_lock["lock_hash"],
    }
    lock["lock_hash"] = hash_json(lock)
    write_json(target / "runways" / "locked_runways.v1.json", lock)
    manifest = {
        "record_type": "VerifiedRunwayInheritance", "version": VERSION,
        "source_campaign": str(source.resolve()),
        "source_campaign_hash": source_campaign["campaign_hash"],
        "source_lock_hash": source_lock["lock_hash"],
        "target_campaign_hash": target_campaign["campaign_hash"],
        "target_lock_hash": lock["lock_hash"],
        "runway_text_hashes": {
            cell_id: item["text_hash"] for cell_id, item in sorted(runways.items())
        },
        "verified_at": _now(),
    }
    manifest["inheritance_hash"] = hash_json(
        {key: value for key, value in manifest.items() if key != "verified_at"}
    )
    write_json(target / "runways" / "inheritance.v1.json", manifest)
    return manifest


def derive_verified_runway_prefix(
    *,
    source_campaign_dir: str | Path,
    target_campaign_dir: str | Path,
    cell_id: str,
    paragraph_count: int,
) -> dict[str, Any]:
    """Lock an exact paragraph prefix of one verified Gemma runway.

    This changes manuscript state without adding connective prose.  The
    derived span points into the original raw response and reconstructs byte
    for byte through the ordinary authorship verifier.
    """

    if paragraph_count < 1:
        raise ValueError("paragraph_count must be positive")
    source = Path(source_campaign_dir)
    target = Path(target_campaign_dir)
    target_campaign = _read_json(target / "campaign_manifest.v1.json")
    source_lock_path = source / "runways" / "locked_runways.v1.json"
    source_lock = _read_json(source_lock_path)
    source_item = dict(source_lock.get("runways", {}).get(cell_id, {}))
    if not source_item:
        raise ValueError(f"source campaign has no locked runway for {cell_id}")
    spans = _runway_model_spans(source_item)
    if len(spans) != 1:
        raise ValueError("runway prefix derivation currently requires one model span")
    project_root = Path(target_campaign["project_root"])
    source_text = spans[0].extract(project_root)
    if source_text != source_item["text"]:
        raise ValueError("source runway does not reconstruct before derivation")
    paragraphs = source_text.splitlines()
    if len(paragraphs) < paragraph_count:
        raise ValueError("runway has fewer paragraphs than requested")
    prefix = "\n".join(paragraphs[:paragraph_count]).rstrip()
    if not source_text.startswith(prefix):
        raise ValueError("derived runway is not an exact source prefix")
    span = spans[0]
    derived_span = replace(
        span,
        span_id=span.span_id + f".prefix-{paragraph_count}",
        raw_char_end=span.raw_char_start + len(prefix),
        text_hash=sha256_text(prefix),
        role="derived-opening-runway-prefix",
    )
    # Re-run current deterministic gates against the shortened manuscript.
    _, _, cells, passages, _ = _load_campaign(target)
    cell = next((item for item in cells if item.cell_id == cell_id), None)
    if cell is None:
        raise ValueError(f"target campaign has no cell {cell_id}")
    anti_copy = AntiCopyIndex({item.passage_id: item.text for item in passages})
    overlap = anti_copy.check(
        f"{source_item.get('runway_id', cell_id)}.prefix-{paragraph_count}", prefix,
    ).to_dict()
    gate = runway_gate(cell, prefix, overlap)
    if not gate["passed"]:
        raise ValueError(f"derived runway prefix fails current gates: {gate}")
    derived = dict(source_item)
    derived.update({
        "runway_id": f"{source_item.get('runway_id', cell_id)}.prefix-{paragraph_count}",
        "text": prefix, "text_hash": sha256_text(prefix),
        "span": asdict(derived_span), "spans": [asdict(derived_span)],
        "separators": [], "mechanical": gate, "overlap": overlap,
        "derived_from_runway_id": source_item.get("runway_id"),
        "derivation": {
            "method": "exact_paragraph_prefix",
            "paragraph_count": paragraph_count,
            "source_text_hash": source_item["text_hash"],
            "source_lock_hash": source_lock["lock_hash"],
        },
    })
    lock = {
        "record_type": "DerivedVerifiedRunways", "version": VERSION,
        "campaign_hash": target_campaign["campaign_hash"],
        "runways": {cell_id: derived},
        "source_lock_hash": source_lock["lock_hash"],
        "derivation_policy": "exact-model-span-prefix-no-added-prose.v1",
    }
    lock["lock_hash"] = hash_json(lock)
    write_json(target / "runways" / "locked_runways.v1.json", lock)
    report = {
        "record_type": "VerifiedRunwayPrefixDerivation", "version": VERSION,
        "cell_id": cell_id, "paragraph_count": paragraph_count,
        "source_campaign": str(source.resolve()),
        "target_campaign": str(target.resolve()),
        "source_text_hash": source_item["text_hash"],
        "derived_text_hash": derived["text_hash"],
        "target_lock_hash": lock["lock_hash"],
        "verified_at": _now(),
    }
    report["derivation_hash"] = hash_json({
        key: value for key, value in report.items() if key != "verified_at"
    })
    write_json(target / "runways" / "prefix_derivation.v1.json", report)
    return report


def run_topology_search(
    *,
    campaign_dir: str | Path,
    client: LlamaClient,
    admission: SharedEndpointAdmission,
    seeds: Sequence[int],
    max_tokens: int = 760,
    only_recipe: str = "",
    only_cell: str = "",
    limit: int | None = None,
) -> dict[str, Any]:
    root = Path(campaign_dir)
    campaign, _, cells, passages, graphs = _load_campaign(root)
    project_root = Path(campaign["project_root"])
    recipes = tuple(PromptRecipeV4(**{
        **{key: value for key, value in item.items() if key not in {"recipe_hash", "sampler"}},
        "sampler": SamplerV4(**item["sampler"]),
    }) for item in campaign["recipes"])
    runways = _load_locked_runways(root)
    source_docs = {item.passage_id: item.text for item in passages}
    anti_copy = AntiCopyIndex(source_docs)
    calls = root / "topology" / "calls.jsonl"
    candidates = root / "topology" / "candidates.jsonl"
    completed = _latest(candidates, "candidate_id")
    produced = attempted = 0
    for recipe in recipes:
        if only_recipe and recipe.recipe_id != only_recipe:
            continue
        for cell in cells:
            if cell.cell_id not in CALIBRATION_CELL_IDS:
                continue
            if only_cell and cell.cell_id != only_cell:
                continue
            runway = runways.get(cell.cell_id)
            if not runway:
                raise ValueError(f"no locked model-generated runway for {cell.cell_id}")
            movement = topology_screen_movement(cell)
            prompt, source_ids = render_generation_prompt(
                recipe=recipe, cell=cell, passages=passages, graphs=graphs,
                runway=runway["text"], movement=movement,
                source_ids_override=tuple(runway.get("source_ids", ())),
                self_demonstrations=(
                    tuple(item["text"] for key, item in sorted(runways.items()) if key != cell.cell_id)
                    if recipe.topology == "source-plus-self-demo" else ()
                ),
            )
            prompt_hash = sha256_text(prompt)
            prompt_tokens = client.token_count(prompt)
            prompt_path = root / "topology" / "prompts" / recipe.recipe_id / f"{cell.cell_id}.txt"
            if prompt_path.is_file() and sha256_text(prompt_path.read_text(encoding="utf-8")) != prompt_hash:
                raise ValueError("prompt drift inside immutable topology arm")
            atomic_write_text(prompt_path, prompt)
            for seed in seeds:
                candidate_id = f"topology.{recipe.recipe_id}.{cell.cell_id}.{seed}"
                request_hash = _generation_request_hash(
                    campaign_hash=campaign["campaign_hash"], prompt_hash=prompt_hash,
                    model=client.model, seed=seed, max_tokens=max_tokens,
                    sampler=asdict(recipe.sampler), source_ids=source_ids,
                )
                if candidate_id in completed:
                    _assert_resumable_request(completed[candidate_id], request_hash, candidate_id)
                    continue
                if limit is not None and attempted >= limit:
                    return {"new": produced, "stopped_at_limit": True}
                attempted += 1
                raw_path = root / "topology" / "raw" / f"{candidate_id}.txt"
                call = {
                    "record_type": "V4ModelCall", "call_id": candidate_id,
                    "status": "started", "model": client.model,
                    "runtime": _endpoint_runtime_provenance(client),
                    "prompt_hash": prompt_hash, "prompt_path": str(prompt_path),
                    "prompt_renderer_version": campaign.get("prompt_policy_versions", {}).get(
                        "generation_renderer", "prompt-renderer.legacy"
                    ),
                    "prompt_tokens": prompt_tokens, "seed": seed,
                    "sampler": asdict(recipe.sampler), "max_tokens": max_tokens,
                    "request_hash": request_hash,
                    "started_at": _now(),
                }
                append_jsonl(calls, call)
                parts: list[str] = []
                def on_delta(delta: str) -> None:
                    parts.append(delta)
                    match = anti_copy.first_exact_match(runway["text"] + "".join(parts))
                    if match:
                        raise SourceOverlapError(match)
                try:
                    with admission.acquire(owner=candidate_id, prompt_hash=prompt_hash, prompt_tokens=prompt_tokens, completion_tokens=max_tokens):
                        cache_preparation = prepare_prompt_family(client, prompt_hash)
                        result = client.stream_raw(
                            prompt=prompt, seed=seed, max_tokens=max_tokens,
                            temperature=recipe.sampler.temperature, top_p=recipe.sampler.top_p,
                            min_p=recipe.sampler.min_p, xtc_probability=recipe.sampler.xtc_probability,
                            extra=recipe.sampler.raw_extra(), on_delta=on_delta, stop=MANUSCRIPT_STOP,
                        )
                except SourceOverlapError as exc:
                    aborted = "".join(parts)
                    atomic_write_text(raw_path, aborted)
                    record = {
                        "record_type": "TopologyCandidate", "version": VERSION,
                        "candidate_id": candidate_id, "status": "completed",
                        "campaign_hash": campaign["campaign_hash"],
                        "recipe_id": recipe.recipe_id, "recipe_hash": recipe.recipe_hash,
                        "cell_id": cell.cell_id, "seed": seed, "source_ids": list(source_ids),
                        "text": runway["text"], "text_hash": runway["text_hash"], "segment": "",
                        "assembly_path": "", "prompt_hash": prompt_hash,
                        "request_hash": request_hash,
                        "prompt_tokens": prompt_tokens, "raw_hash": sha256_text(aborted),
                        "raw_path": _relative(raw_path, project_root),
                        "mechanical": {"version": HARD_GATE_VERSION, "passed": False, "gates": {"anti_copy": False}, "diagnostics": {"stream_abort": exc.match}},
                        "overlap": {"hard_fail": True, "stream_match": exc.match},
                        "eligible": False, "finish_reason": "streaming_source_overlap_abort",
                        "usage": {}, "timings": {}, "completed_at": _now(),
                    }
                    append_jsonl(candidates, record)
                    append_jsonl(calls, {**call, "status": "completed", "finish_reason": record["finish_reason"], "raw_hash": record["raw_hash"], "completed_at": record["completed_at"]})
                    completed[candidate_id] = record
                    produced += 1
                    continue
                atomic_write_text(raw_path, result.content)
                try:
                    segment, start, end = _complete_paragraph_prefix(result.content, 300, 500)
                    text = runway["text"] + "\n\n" + segment
                    overlap = anti_copy.check(candidate_id, text).to_dict()
                    gate = hard_gate(cell, text, overlap)
                    transaction_gate = topology_screen_gate(cell, segment)
                    gate["gates"]["topology_transaction"] = transaction_gate["passed"]
                    gate["diagnostics"]["topology_transaction"] = transaction_gate
                    gate["passed"] = bool(gate["passed"] and transaction_gate["passed"])
                except ValueError as exc:
                    segment, start, end, text = "", 0, 0, runway["text"]
                    overlap, gate = {}, {"passed": False, "error": str(exc)}
                assembly_path: Path | None = None
                if segment:
                    segment_span = ModelSpan(
                        span_id=f"{candidate_id}.segment", call_id=candidate_id,
                        raw_path=_relative(raw_path, project_root), raw_hash=sha256_text(result.content),
                        raw_char_start=start, raw_char_end=end, text_hash=sha256_text(segment), role="topology-movement",
                    )
                    runway_spans = _runway_model_spans(runway)
                    runway_separators = _runway_separators(runway)
                    assembly = ManuscriptAssembly(
                        artifact_id=candidate_id, spans=(*runway_spans, segment_span),
                        separators=(*runway_separators, "\n\n"), manuscript_hash=sha256_text(text),
                    )
                    assembly_path = root / "topology" / "assemblies" / f"{candidate_id}.json"
                    _write_verified_assembly(assembly_path, assembly, project_root)
                record = {
                    "record_type": "TopologyCandidate", "version": VERSION,
                    "candidate_id": candidate_id, "status": "completed",
                    "campaign_hash": campaign["campaign_hash"],
                    "recipe_id": recipe.recipe_id, "recipe_hash": recipe.recipe_hash,
                    "cell_id": cell.cell_id, "seed": seed, "source_ids": list(source_ids),
                    "text": text, "text_hash": sha256_text(text), "segment": segment,
                    "assembly_path": _relative(assembly_path, project_root) if assembly_path else "",
                    "prompt_hash": prompt_hash, "prompt_tokens": prompt_tokens,
                    "request_hash": request_hash,
                    "prompt_renderer_version": campaign.get("prompt_policy_versions", {}).get(
                        "generation_renderer", "prompt-renderer.legacy"
                    ),
                    "raw_hash": sha256_text(result.content), "raw_path": _relative(raw_path, project_root),
                    "extraction_version": EXTRACTION_VERSION,
                    "mechanical": gate, "overlap": overlap,
                    "eligible": bool(gate.get("passed")), "finish_reason": result.finish_reason,
                    "usage": result.usage, "timings": result.timings, "completed_at": _now(),
                }
                append_jsonl(candidates, record)
                append_jsonl(calls, {**call, "status": "completed", "raw_hash": record["raw_hash"], "completed_at": record["completed_at"]})
                produced += 1
    return {"new": produced, "total": len(_latest(candidates, "candidate_id"))}


def run_staged_topology_search(
    *,
    campaign_dir: str | Path,
    client: LlamaClient,
    admission: SharedEndpointAdmission,
    seeds: Sequence[int],
    recipe_id: str = "v4-anthology",
    cell_id: str = "charged-restraint",
    spark_max_tokens: int = 240,
    spark_max_words: int = 350,
    continuation_max_tokens: int = 620,
) -> dict[str, Any]:
    """Generate a causal spark, then continue from its exact model bytes.

    The staged screen keeps control syntax away from the final completion
    boundary without inserting human prose.  A first base call must establish
    the transaction's initiating mistake; only then does a second base call
    receive those exact bytes as its runway and pay the counteroffer.
    """

    root = Path(campaign_dir)
    campaign, _, cells, passages, graphs = _load_campaign(root)
    project_root = Path(campaign["project_root"])
    cell = next((item for item in cells if item.cell_id == cell_id), None)
    if cell is None or cell_id not in CALIBRATION_CELL_IDS:
        raise ValueError(f"unknown calibration cell: {cell_id}")
    recipe_payload = next(
        (item for item in campaign["recipes"] if item["recipe_id"] == recipe_id),
        None,
    )
    if recipe_payload is None:
        raise ValueError(f"unknown prompt recipe: {recipe_id}")
    recipe = PromptRecipeV4(**{
        **{
            key: value for key, value in recipe_payload.items()
            if key not in {"recipe_hash", "sampler"}
        },
        "sampler": SamplerV4(**recipe_payload["sampler"]),
    })
    runway = _load_locked_runways(root).get(cell_id)
    if not runway:
        raise ValueError(f"no locked model-generated runway for {cell_id}")
    source_ids_override = tuple(runway.get("source_ids", ()))
    source_docs = {item.passage_id: item.text for item in passages}
    anti_copy = AntiCopyIndex(source_docs)
    phase_root = root / "topology-staged"
    calls_path = phase_root / "calls.jsonl"
    candidates_path = phase_root / "candidates.jsonl"
    completed = _latest(candidates_path, "candidate_id")
    produced = 0

    spark_prompt, source_ids = render_generation_prompt(
        recipe=recipe, cell=cell, passages=passages, graphs=graphs,
        runway=runway["text"], movement=topology_spark_movement(cell),
        source_ids_override=source_ids_override,
    )
    spark_prompt_hash = sha256_text(spark_prompt)
    spark_prompt_tokens = client.token_count(spark_prompt)
    spark_prompt_path = phase_root / "prompts" / recipe_id / f"{cell_id}.spark.txt"
    atomic_write_text(spark_prompt_path, spark_prompt)

    for seed in seeds:
        candidate_id = f"topology-staged.{recipe_id}.{cell_id}.{seed}"
        if candidate_id in completed:
            continue
        spark_call_id = candidate_id + ".spark"
        spark_request_hash = _generation_request_hash(
            campaign_hash=campaign["campaign_hash"],
            prompt_hash=spark_prompt_hash, model=client.model, seed=seed,
            max_tokens=spark_max_tokens, sampler=asdict(recipe.sampler),
            source_ids=source_ids,
            generation_contract={
                "stage": "causal-spark", "cell_id": cell_id,
                "movement_hash": sha256_text(topology_spark_movement(cell)),
                "spark_max_words": spark_max_words,
                "extraction_version": EXTRACTION_VERSION,
            },
        )
        spark_raw_path = phase_root / "raw" / f"{spark_call_id}.txt"
        started = {
            "record_type": "V4ModelCall", "call_id": spark_call_id,
            "status": "started", "model": client.model,
            "runtime": _endpoint_runtime_provenance(client),
            "prompt_hash": spark_prompt_hash,
            "prompt_path": _relative(spark_prompt_path, project_root),
            "prompt_tokens": spark_prompt_tokens, "seed": seed,
            "sampler": asdict(recipe.sampler), "max_tokens": spark_max_tokens,
            "request_hash": spark_request_hash, "started_at": _now(),
        }
        append_jsonl(calls_path, started)
        spark_parts: list[str] = []

        def on_spark(delta: str) -> None:
            spark_parts.append(delta)
            match = anti_copy.first_exact_match(
                runway["text"] + "".join(spark_parts)
            )
            if match:
                raise SourceOverlapError(match)

        try:
            with admission.acquire(
                owner=spark_call_id, prompt_hash=spark_prompt_hash,
                prompt_tokens=spark_prompt_tokens,
                completion_tokens=spark_max_tokens,
            ):
                prepare_prompt_family(client, spark_prompt_hash)
                spark_result = client.stream_raw(
                    prompt=spark_prompt, seed=seed,
                    max_tokens=spark_max_tokens,
                    temperature=recipe.sampler.temperature,
                    top_p=recipe.sampler.top_p, min_p=recipe.sampler.min_p,
                    xtc_probability=recipe.sampler.xtc_probability,
                    extra=recipe.sampler.raw_extra(), on_delta=on_spark,
                    stop=MANUSCRIPT_STOP,
                )
        except SourceOverlapError as exc:
            raw = "".join(spark_parts)
            atomic_write_text(spark_raw_path, raw)
            record = {
                "record_type": "StagedTopologyCandidate", "version": VERSION,
                "candidate_id": candidate_id, "status": "completed",
                "campaign_hash": campaign["campaign_hash"],
                "recipe_id": recipe_id, "recipe_hash": recipe.recipe_hash,
                "cell_id": cell_id, "seed": seed, "source_ids": list(source_ids),
                "text": runway["text"], "text_hash": runway["text_hash"],
                "spark": "", "continuation": "", "eligible": False,
                "mechanical": {"passed": False, "error": "spark source overlap"},
                "overlap": {"hard_fail": True, "stream_match": exc.match},
                "spark_request_hash": spark_request_hash,
                "completed_at": _now(),
            }
            append_jsonl(candidates_path, record)
            append_jsonl(calls_path, {
                **started, "status": "completed", "raw_hash": sha256_text(raw),
                "finish_reason": "streaming_source_overlap_abort",
                "completed_at": record["completed_at"],
            })
            produced += 1
            continue

        atomic_write_text(spark_raw_path, spark_result.content)
        append_jsonl(calls_path, {
            **started, "status": "completed",
            "raw_hash": sha256_text(spark_result.content),
            "finish_reason": spark_result.finish_reason,
            "usage": spark_result.usage, "timings": spark_result.timings,
            "completed_at": _now(),
        })
        try:
            spark, spark_start, spark_end = _topology_spark_prefix(
                spark_result.content, cell, spark_max_words,
            )
            assembled_spark = runway["text"] + "\n\n" + spark
            spark_overlap = anti_copy.check(
                spark_call_id, assembled_spark,
            ).to_dict()
            spark_hard = hard_gate(cell, assembled_spark, spark_overlap)
            spark_transaction = topology_spark_gate(cell, spark)
            spark_ok = bool(spark_hard["passed"] and spark_transaction["passed"])
        except ValueError as exc:
            spark, spark_start, spark_end = "", 0, 0
            spark_overlap, spark_hard = {}, {"passed": False, "error": str(exc)}
            spark_transaction = {"passed": False, "error": str(exc)}
            spark_ok = False
        if not spark_ok:
            record = {
                "record_type": "StagedTopologyCandidate", "version": VERSION,
                "candidate_id": candidate_id, "status": "completed",
                "campaign_hash": campaign["campaign_hash"],
                "recipe_id": recipe_id, "recipe_hash": recipe.recipe_hash,
                "cell_id": cell_id, "seed": seed, "source_ids": list(source_ids),
                "text": runway["text"] + (("\n\n" + spark) if spark else ""),
                "text_hash": sha256_text(
                    runway["text"] + (("\n\n" + spark) if spark else "")
                ),
                "spark": spark, "continuation": "", "eligible": False,
                "mechanical": {
                    "passed": False, "hard_gate": spark_hard,
                    "spark_transaction": spark_transaction,
                },
                "overlap": spark_overlap,
                "spark_request_hash": spark_request_hash,
                "finish_reason": "spark_gate_reject",
                "completed_at": _now(),
            }
            append_jsonl(candidates_path, record)
            produced += 1
            continue

        continuation_prompt, continuation_source_ids = render_generation_prompt(
            recipe=recipe, cell=cell, passages=passages, graphs=graphs,
            runway=runway["text"], prior_manuscript=spark,
            movement=topology_screen_movement(cell),
            source_ids_override=source_ids_override,
        )
        if continuation_source_ids != source_ids:
            raise ValueError("staged topology source lineage changed between calls")
        continuation_prompt_hash = sha256_text(continuation_prompt)
        continuation_prompt_tokens = client.token_count(continuation_prompt)
        continuation_prompt_path = (
            phase_root / "prompts" / recipe_id /
            f"{cell_id}.{seed}.continuation.txt"
        )
        atomic_write_text(continuation_prompt_path, continuation_prompt)
        continuation_call_id = candidate_id + ".continuation"
        continuation_seed = seed + 1_000_003
        continuation_request_hash = _generation_request_hash(
            campaign_hash=campaign["campaign_hash"],
            prompt_hash=continuation_prompt_hash, model=client.model,
            seed=continuation_seed, max_tokens=continuation_max_tokens,
            sampler=asdict(recipe.sampler), source_ids=source_ids,
            generation_contract={
                "stage": "counteroffer-continuation",
                "spark_hash": sha256_text(spark),
                "movement_hash": sha256_text(topology_screen_movement(cell)),
            },
        )
        continuation_started = {
            "record_type": "V4ModelCall", "call_id": continuation_call_id,
            "status": "started", "model": client.model,
            "runtime": _endpoint_runtime_provenance(client),
            "prompt_hash": continuation_prompt_hash,
            "prompt_path": _relative(continuation_prompt_path, project_root),
            "prompt_tokens": continuation_prompt_tokens,
            "seed": continuation_seed, "sampler": asdict(recipe.sampler),
            "max_tokens": continuation_max_tokens,
            "request_hash": continuation_request_hash, "started_at": _now(),
        }
        append_jsonl(calls_path, continuation_started)
        continuation_parts: list[str] = []

        def on_continuation(delta: str) -> None:
            continuation_parts.append(delta)
            match = anti_copy.first_exact_match(
                runway["text"] + spark + "".join(continuation_parts)
            )
            if match:
                raise SourceOverlapError(match)

        try:
            with admission.acquire(
                owner=continuation_call_id,
                prompt_hash=continuation_prompt_hash,
                prompt_tokens=continuation_prompt_tokens,
                completion_tokens=continuation_max_tokens,
            ):
                prepare_prompt_family(client, continuation_prompt_hash)
                continuation_result = client.stream_raw(
                    prompt=continuation_prompt, seed=continuation_seed,
                    max_tokens=continuation_max_tokens,
                    temperature=recipe.sampler.temperature,
                    top_p=recipe.sampler.top_p, min_p=recipe.sampler.min_p,
                    xtc_probability=recipe.sampler.xtc_probability,
                    extra=recipe.sampler.raw_extra(), on_delta=on_continuation,
                    stop=MANUSCRIPT_STOP,
                )
        except SourceOverlapError as exc:
            raw = "".join(continuation_parts)
            atomic_write_text(
                phase_root / "raw" / f"{continuation_call_id}.txt", raw,
            )
            record = {
                "record_type": "StagedTopologyCandidate", "version": VERSION,
                "candidate_id": candidate_id, "status": "completed",
                "campaign_hash": campaign["campaign_hash"],
                "recipe_id": recipe_id, "recipe_hash": recipe.recipe_hash,
                "cell_id": cell_id, "seed": seed, "source_ids": list(source_ids),
                "text": assembled_spark, "text_hash": sha256_text(assembled_spark),
                "spark": spark, "continuation": "", "eligible": False,
                "mechanical": {"passed": False, "error": "continuation source overlap"},
                "overlap": {"hard_fail": True, "stream_match": exc.match},
                "spark_request_hash": spark_request_hash,
                "continuation_request_hash": continuation_request_hash,
                "finish_reason": "streaming_source_overlap_abort",
                "completed_at": _now(),
            }
            append_jsonl(candidates_path, record)
            append_jsonl(calls_path, {
                **continuation_started, "status": "completed",
                "raw_hash": sha256_text(raw),
                "finish_reason": "streaming_source_overlap_abort",
                "completed_at": record["completed_at"],
            })
            produced += 1
            continue

        continuation_raw_path = (
            phase_root / "raw" / f"{continuation_call_id}.txt"
        )
        atomic_write_text(continuation_raw_path, continuation_result.content)
        append_jsonl(calls_path, {
            **continuation_started, "status": "completed",
            "raw_hash": sha256_text(continuation_result.content),
            "finish_reason": continuation_result.finish_reason,
            "usage": continuation_result.usage,
            "timings": continuation_result.timings,
            "completed_at": _now(),
        })
        try:
            spark_words = len(_words(spark))
            continuation, continuation_start, continuation_end = (
                _complete_paragraph_prefix(
                    continuation_result.content,
                    max(40, 80 - spark_words),
                    max(120, 500 - spark_words),
                )
            )
            segment = spark + "\n\n" + continuation
            text = runway["text"] + "\n\n" + segment
            overlap = anti_copy.check(candidate_id, text).to_dict()
            hard = hard_gate(cell, text, overlap)
            transaction = topology_screen_gate(cell, segment)
            hard["gates"]["topology_transaction"] = transaction["passed"]
            hard["diagnostics"]["topology_transaction"] = transaction
            hard["passed"] = bool(hard["passed"] and transaction["passed"])
        except ValueError as exc:
            continuation, continuation_start, continuation_end = "", 0, 0
            segment, text = spark, assembled_spark
            overlap, hard = {}, {"passed": False, "error": str(exc)}

        spark_span = _bind_span_to_call(
            ModelSpan(
                span_id=spark_call_id, call_id=spark_call_id,
                raw_path=_relative(spark_raw_path, project_root),
                raw_hash=sha256_text(spark_result.content),
                raw_char_start=spark_start, raw_char_end=spark_end,
                text_hash=sha256_text(spark), role="topology-causal-spark",
            ),
            calls_path, project_root,
        )
        assembly_path: Path | None = None
        if continuation:
            continuation_span = _bind_span_to_call(
                ModelSpan(
                    span_id=continuation_call_id, call_id=continuation_call_id,
                    raw_path=_relative(continuation_raw_path, project_root),
                    raw_hash=sha256_text(continuation_result.content),
                    raw_char_start=continuation_start,
                    raw_char_end=continuation_end,
                    text_hash=sha256_text(continuation),
                    role="topology-counteroffer-continuation",
                ),
                calls_path, project_root,
            )
            assembly = ManuscriptAssembly(
                artifact_id=candidate_id,
                spans=(*_runway_model_spans(runway), spark_span, continuation_span),
                separators=(*_runway_separators(runway), "\n\n", "\n\n"),
                manuscript_hash=sha256_text(text),
            )
            assembly_path = phase_root / "assemblies" / f"{candidate_id}.json"
            _write_verified_assembly(assembly_path, assembly, project_root)
        record = {
            "record_type": "StagedTopologyCandidate", "version": VERSION,
            "candidate_id": candidate_id, "status": "completed",
            "campaign_hash": campaign["campaign_hash"],
            "recipe_id": recipe_id, "recipe_hash": recipe.recipe_hash,
            "cell_id": cell_id, "seed": seed, "source_ids": list(source_ids),
            "text": text, "text_hash": sha256_text(text),
            "spark": spark, "continuation": continuation,
            "assembly_path": _relative(assembly_path, project_root) if assembly_path else "",
            "spark_prompt_hash": spark_prompt_hash,
            "continuation_prompt_hash": continuation_prompt_hash,
            "spark_request_hash": spark_request_hash,
            "continuation_request_hash": continuation_request_hash,
            "mechanical": hard, "overlap": overlap,
            "eligible": bool(hard.get("passed")),
            "finish_reason": continuation_result.finish_reason,
            "completed_at": _now(),
        }
        append_jsonl(candidates_path, record)
        produced += 1
    return {
        "new": produced,
        "total": len(_latest(candidates_path, "candidate_id")),
        "eligible": sorted(
            item["candidate_id"]
            for item in _latest(candidates_path, "candidate_id").values()
            if item.get("eligible")
        ),
    }


def run_topology_continuation_branches(
    *,
    campaign_dir: str | Path,
    client: LlamaClient,
    admission: SharedEndpointAdmission,
    parent_candidate_id: str,
    seeds: Sequence[int],
    max_tokens: int = 620,
) -> dict[str, Any]:
    """Branch from an exact Gemma-authored causal spark without rewriting it."""

    root = Path(campaign_dir)
    campaign, _, cells, passages, graphs = _load_campaign(root)
    project_root = Path(campaign["project_root"])
    parents = _latest(root / "topology-staged" / "candidates.jsonl", "candidate_id")
    parent = parents.get(parent_candidate_id)
    if parent is None:
        raise ValueError(f"unknown staged topology parent: {parent_candidate_id}")
    if not parent.get("eligible"):
        raise ValueError("continuation branches require an eligible staged parent")
    parent_assembly_path = project_root / str(parent["assembly_path"])
    verify_assembly(parent_assembly_path, project_root)
    parent_assembly = _read_json(parent_assembly_path)
    spark_spans = [
        ModelSpan(**value) for value in parent_assembly["spans"]
        if value.get("role") == "topology-causal-spark"
    ]
    if len(spark_spans) != 1:
        raise ValueError("staged parent must contain exactly one causal spark span")
    spark_span = spark_spans[0]
    spark = str(parent.get("spark", "")).strip()
    if not spark or spark_span.text_hash != sha256_text(spark):
        raise ValueError("staged parent spark does not match its model span")

    cell_id = str(parent["cell_id"])
    cell = next((item for item in cells if item.cell_id == cell_id), None)
    if cell is None:
        raise ValueError(f"unknown staged parent cell: {cell_id}")
    recipe_id = str(parent["recipe_id"])
    recipe_payload = next(
        (item for item in campaign["recipes"] if item["recipe_id"] == recipe_id),
        None,
    )
    if recipe_payload is None:
        raise ValueError(f"unknown staged parent recipe: {recipe_id}")
    recipe = PromptRecipeV4(**{
        **{
            key: value for key, value in recipe_payload.items()
            if key not in {"recipe_hash", "sampler"}
        },
        "sampler": SamplerV4(**recipe_payload["sampler"]),
    })
    runway = _load_locked_runways(root).get(cell_id)
    if not runway:
        raise ValueError(f"no locked model-generated runway for {cell_id}")
    source_ids = tuple(str(value) for value in parent.get("source_ids", ()))
    prompt, observed_source_ids = render_generation_prompt(
        recipe=recipe, cell=cell, passages=passages, graphs=graphs,
        runway=runway["text"], prior_manuscript=spark,
        movement=topology_screen_movement(cell),
        source_ids_override=source_ids,
    )
    if observed_source_ids != source_ids:
        raise ValueError("branch source lineage differs from its staged parent")
    prompt_hash = sha256_text(prompt)
    prompt_tokens = client.token_count(prompt)
    phase_root = root / "topology-branch"
    prompt_path = phase_root / "prompts" / recipe_id / f"{cell_id}.{sha256_text(spark)[:16]}.txt"
    atomic_write_text(prompt_path, prompt)
    calls_path = phase_root / "calls.jsonl"
    candidates_path = phase_root / "candidates.jsonl"
    completed = _latest(candidates_path, "candidate_id")
    anti_copy = AntiCopyIndex({item.passage_id: item.text for item in passages})
    produced = 0

    for seed in seeds:
        candidate_id = f"topology-branch.{parent_candidate_id}.{seed}"
        if candidate_id in completed:
            continue
        call_id = candidate_id + ".continuation"
        request_hash = _generation_request_hash(
            campaign_hash=campaign["campaign_hash"], prompt_hash=prompt_hash,
            model=client.model, seed=seed, max_tokens=max_tokens,
            sampler=asdict(recipe.sampler), source_ids=source_ids,
            generation_contract={
                "stage": "counteroffer-branch",
                "parent_candidate_id": parent_candidate_id,
                "parent_text_hash": parent["text_hash"],
                "spark_hash": sha256_text(spark),
                "movement_hash": sha256_text(topology_screen_movement(cell)),
                "extraction_version": EXTRACTION_VERSION,
            },
        )
        started = {
            "record_type": "V4ModelCall", "call_id": call_id,
            "status": "started", "model": client.model,
            "runtime": _endpoint_runtime_provenance(client),
            "prompt_hash": prompt_hash,
            "prompt_path": _relative(prompt_path, project_root),
            "prompt_tokens": prompt_tokens, "seed": seed,
            "sampler": asdict(recipe.sampler), "max_tokens": max_tokens,
            "request_hash": request_hash, "started_at": _now(),
        }
        append_jsonl(calls_path, started)
        parts: list[str] = []

        def on_delta(delta: str) -> None:
            parts.append(delta)
            match = anti_copy.first_exact_match(
                runway["text"] + spark + "".join(parts)
            )
            if match:
                raise SourceOverlapError(match)

        try:
            with admission.acquire(
                owner=call_id, prompt_hash=prompt_hash,
                prompt_tokens=prompt_tokens, completion_tokens=max_tokens,
            ):
                prepare_prompt_family(client, prompt_hash)
                result = client.stream_raw(
                    prompt=prompt, seed=seed, max_tokens=max_tokens,
                    temperature=recipe.sampler.temperature,
                    top_p=recipe.sampler.top_p, min_p=recipe.sampler.min_p,
                    xtc_probability=recipe.sampler.xtc_probability,
                    extra=recipe.sampler.raw_extra(), on_delta=on_delta,
                    stop=MANUSCRIPT_STOP,
                )
        except SourceOverlapError as exc:
            raw = "".join(parts)
            raw_path = phase_root / "raw" / f"{call_id}.txt"
            atomic_write_text(raw_path, raw)
            record = {
                "record_type": "TopologyBranchCandidate", "version": VERSION,
                "candidate_id": candidate_id, "status": "completed",
                "campaign_hash": campaign["campaign_hash"],
                "parent_candidate_id": parent_candidate_id,
                "recipe_id": recipe_id, "recipe_hash": recipe.recipe_hash,
                "cell_id": cell_id, "seed": seed,
                "source_ids": list(source_ids), "text": parent["text"],
                "text_hash": parent["text_hash"], "spark": spark,
                "continuation": "", "segment": spark, "eligible": False,
                "mechanical": {"passed": False, "error": "branch source overlap"},
                "overlap": {"hard_fail": True, "stream_match": exc.match},
                "request_hash": request_hash,
                "finish_reason": "streaming_source_overlap_abort",
                "completed_at": _now(),
            }
            append_jsonl(candidates_path, record)
            append_jsonl(calls_path, {
                **started, "status": "completed", "raw_hash": sha256_text(raw),
                "finish_reason": record["finish_reason"],
                "completed_at": record["completed_at"],
            })
            produced += 1
            continue

        raw_path = phase_root / "raw" / f"{call_id}.txt"
        atomic_write_text(raw_path, result.content)
        append_jsonl(calls_path, {
            **started, "status": "completed", "raw_hash": sha256_text(result.content),
            "finish_reason": result.finish_reason, "usage": result.usage,
            "timings": result.timings, "completed_at": _now(),
        })
        try:
            continuation, start, end = _complete_paragraph_prefix(
                result.content, max(40, 80 - len(_words(spark))),
                max(120, 500 - len(_words(spark))),
            )
            segment = spark + "\n\n" + continuation
            text = runway["text"] + "\n\n" + segment
            overlap = anti_copy.check(candidate_id, text).to_dict()
            mechanical = hard_gate(cell, text, overlap)
            transaction = topology_screen_gate(cell, segment)
            mechanical["gates"]["topology_transaction"] = transaction["passed"]
            mechanical["diagnostics"]["topology_transaction"] = transaction
            mechanical["passed"] = bool(mechanical["passed"] and transaction["passed"])
        except ValueError as exc:
            continuation, start, end = "", 0, 0
            segment = spark
            text = runway["text"] + "\n\n" + spark
            overlap = {}
            mechanical = {"passed": False, "error": str(exc)}
        assembly_path: Path | None = None
        if continuation:
            continuation_span = _bind_span_to_call(
                ModelSpan(
                    span_id=call_id, call_id=call_id,
                    raw_path=_relative(raw_path, project_root),
                    raw_hash=sha256_text(result.content), raw_char_start=start,
                    raw_char_end=end, text_hash=sha256_text(continuation),
                    role="topology-counteroffer-branch",
                ),
                calls_path, project_root,
            )
            assembly = ManuscriptAssembly(
                artifact_id=candidate_id,
                spans=(*_runway_model_spans(runway), spark_span, continuation_span),
                separators=(*_runway_separators(runway), "\n\n", "\n\n"),
                manuscript_hash=sha256_text(text),
            )
            assembly_path = phase_root / "assemblies" / f"{candidate_id}.json"
            _write_verified_assembly(assembly_path, assembly, project_root)
        record = {
            "record_type": "TopologyBranchCandidate", "version": VERSION,
            "candidate_id": candidate_id, "status": "completed",
            "campaign_hash": campaign["campaign_hash"],
            "parent_candidate_id": parent_candidate_id,
            "parent_text_hash": parent["text_hash"],
            "recipe_id": recipe_id, "recipe_hash": recipe.recipe_hash,
            "cell_id": cell_id, "seed": seed, "source_ids": list(source_ids),
            "text": text, "text_hash": sha256_text(text), "spark": spark,
            "continuation": continuation, "segment": segment,
            "assembly_path": _relative(assembly_path, project_root) if assembly_path else "",
            "prompt_hash": prompt_hash, "request_hash": request_hash,
            "extraction_version": EXTRACTION_VERSION,
            "mechanical": mechanical, "overlap": overlap,
            "eligible": bool(mechanical.get("passed")),
            "finish_reason": result.finish_reason, "usage": result.usage,
            "timings": result.timings, "completed_at": _now(),
        }
        append_jsonl(candidates_path, record)
        produced += 1

    return {
        "new": produced,
        "total": len(_latest(candidates_path, "candidate_id")),
        "eligible": sorted(
            item["candidate_id"]
            for item in _latest(candidates_path, "candidate_id").values()
            if item.get("eligible")
        ),
    }


def reextract_phase_candidates(
    campaign_dir: str | Path,
    *,
    phase: str = "topology",
    minimum_words: int = 300,
    maximum_words: int = 500,
) -> dict[str, Any]:
    """Re-derive failed spans from preserved raw responses after extractor fixes."""

    root = Path(campaign_dir)
    campaign, _, cells, passages, _ = _load_campaign(root)
    project_root = Path(campaign["project_root"])
    cells_by_id = {item.cell_id: item for item in cells}
    runways = _load_locked_runways(root)
    anti_copy = AntiCopyIndex({item.passage_id: item.text for item in passages})
    if phase == "loom":
        recovered = 0
        total = 0
        for path in sorted((root / "loom").glob("*/branches.jsonl")):
            candidates = _latest(path, "branch_id")
            total += len(candidates)
            for candidate_id, item in candidates.items():
                if item.get("segment") or item.get("finish_reason") == "streaming_source_overlap_abort":
                    continue
                cell = cells_by_id.get(str(item.get("cell_id", "")))
                movement_id = str(item.get("movement_id", ""))
                movement = dict(movements_for_cell(cell)).get(movement_id) if cell else None
                if cell is None or movement is None:
                    continue
                raw_path = Path(item.get("raw_path", ""))
                if not raw_path.is_absolute():
                    raw_path = project_root / raw_path
                if not raw_path.is_file():
                    continue
                raw = raw_path.read_text(encoding="utf-8")
                if sha256_text(raw) != item.get("raw_hash"):
                    raise ValueError(f"raw response hash changed: {candidate_id}")
                local_min, local_max = movement_word_band(
                    cell, movement_id, minimum_words, maximum_words,
                )
                try:
                    segment, start, end = _complete_paragraph_prefix(
                        raw, local_min, local_max,
                    )
                except ValueError:
                    continue
                parent_text = str(item["text"])
                text = parent_text + "\n\n" + segment
                overlap = anti_copy.check(candidate_id, text).to_dict()
                mechanical = hard_gate(cell, text, overlap)
                stage_gate = movement_gate(cell, segment, movement)
                mechanical["movement_gate"] = stage_gate
                mechanical["passed"] = bool(
                    mechanical.get("passed") and stage_gate["passed"]
                )
                prior_spans = tuple(item.get("spans", ()))[:-1]
                prior_separators = tuple(item.get("separators", ()))[:-1]
                span = ModelSpan(
                    span_id=f"{candidate_id}.span.{EXTRACTION_VERSION}",
                    call_id=candidate_id,
                    raw_path=_relative(raw_path, project_root),
                    raw_hash=sha256_text(raw), raw_char_start=start,
                    raw_char_end=end, text_hash=sha256_text(segment),
                    role=movement_id,
                )
                spans = (*prior_spans, asdict(span))
                separators = (*prior_separators, "\n\n")
                assembly = ManuscriptAssembly(
                    candidate_id, tuple(ModelSpan(**value) for value in spans),
                    tuple(separators), sha256_text(text),
                )
                if assembly.reconstruct(project_root) != text:
                    raise ValueError(
                        f"re-extracted loom assembly does not reconstruct: {candidate_id}"
                    )
                record = dict(item)
                record.update({
                    "status": "completed", "segment": segment,
                    "segment_hash": sha256_text(segment), "text": text,
                    "text_hash": sha256_text(text), "spans": list(spans),
                    "separators": list(separators), "mechanical": mechanical,
                    "overlap": overlap, "eligible": mechanical["passed"],
                    "extraction_version": EXTRACTION_VERSION,
                    "movement_word_band": [local_min, local_max],
                    "reextracted_without_critic": True,
                    "reextracted_from_text_hash": item["text_hash"],
                    "reextraction_contract_hash": hash_json({
                        "extraction_version": EXTRACTION_VERSION,
                        "movement_gate_version": MOVEMENT_GATE_VERSION,
                        "movement_id": movement_id,
                        "movement_text_hash": sha256_text(movement),
                        "movement_word_band": [local_min, local_max],
                        "raw_hash": sha256_text(raw),
                    }),
                    "completed_at": _now(),
                })
                append_jsonl(path, record)
                recovered += 1
        return {
            "recovered": recovered, "total": total,
            "extraction_version": EXTRACTION_VERSION, "phase": "loom",
        }
    path = root / phase / "candidates.jsonl"
    candidates = _latest(path, "candidate_id")
    recovered = 0
    for candidate_id, item in candidates.items():
        if item.get("segment") or item.get("finish_reason") == "streaming_source_overlap_abort":
            continue
        raw_path = Path(item.get("raw_path", ""))
        if not raw_path.is_absolute():
            raw_path = project_root / raw_path
        if not raw_path.is_file():
            continue
        raw = raw_path.read_text(encoding="utf-8")
        if sha256_text(raw) != item.get("raw_hash"):
            raise ValueError(f"raw response hash changed: {candidate_id}")
        try:
            segment, start, end = _complete_paragraph_prefix(raw, minimum_words, maximum_words)
        except ValueError:
            continue
        runway = runways[item["cell_id"]]
        text = runway["text"] + "\n\n" + segment
        overlap = anti_copy.check(candidate_id, text).to_dict()
        gate = hard_gate(cells_by_id[item["cell_id"]], text, overlap)
        segment_span = ModelSpan(
            span_id=f"{candidate_id}.segment.{EXTRACTION_VERSION}", call_id=candidate_id,
            raw_path=_relative(raw_path, project_root), raw_hash=sha256_text(raw),
            raw_char_start=start, raw_char_end=end, text_hash=sha256_text(segment),
            role=f"{phase}-movement",
        )
        runway_spans = _runway_model_spans(runway)
        assembly = ManuscriptAssembly(
            candidate_id, (*runway_spans, segment_span),
            (*_runway_separators(runway), "\n\n"), sha256_text(text),
        )
        assembly_path = root / phase / "assemblies-v2" / f"{candidate_id}.json"
        _write_verified_assembly(assembly_path, assembly, project_root)
        record = dict(item)
        record.update({
            "status": "completed", "segment": segment, "text": text,
            "text_hash": sha256_text(text), "assembly_path": _relative(assembly_path, project_root),
            "mechanical": gate, "overlap": overlap, "eligible": gate["passed"],
            "extraction_version": EXTRACTION_VERSION,
            "reextracted_from_text_hash": item["text_hash"], "completed_at": _now(),
        })
        append_jsonl(path, record)
        recovered += 1
    return {"recovered": recovered, "total": len(_latest(path, "candidate_id")), "extraction_version": EXTRACTION_VERSION}


def revalidate_phase_candidates(
    campaign_dir: str | Path, *, phase: str,
) -> dict[str, Any]:
    """Recompute deterministic gates without changing any manuscript bytes."""

    root = Path(campaign_dir)
    campaign, _, cells, passages, _ = _load_campaign(root)
    cells_by_id = {item.cell_id: item for item in cells}
    index = AntiCopyIndex({item.passage_id: item.text for item in passages})
    if phase == "loom":
        updated = 0
        total = 0
        for path in sorted((root / "loom").glob("*/branches.jsonl")):
            branches = _latest(path, "branch_id")
            total += len(branches)
            for branch_id, item in sorted(branches.items()):
                segment = str(item.get("segment", ""))
                text = str(item.get("text", ""))
                cell = cells_by_id.get(str(item.get("cell_id", "")))
                movement_id = str(item.get("movement_id", ""))
                movement = dict(movements_for_cell(cell)).get(movement_id) if cell else None
                if cell is None or movement is None or not segment or not text:
                    continue
                prior_hard = str(item.get("mechanical", {}).get("version", ""))
                prior_movement = str(
                    item.get("mechanical", {}).get("movement_gate", {}).get("version", "")
                )
                if (
                    prior_hard == HARD_GATE_VERSION
                    and prior_movement == MOVEMENT_GATE_VERSION
                ):
                    continue
                overlap = index.check(branch_id, text).to_dict()
                mechanical = hard_gate(cell, text, overlap)
                stage_gate = movement_gate(cell, segment, movement)
                mechanical["movement_gate"] = stage_gate
                mechanical["passed"] = bool(
                    mechanical.get("passed") and stage_gate["passed"]
                )
                judgment = item.get("judgment", {})
                eligible = bool(
                    mechanical["passed"] and judgment
                    and not judgment.get("hard_reject")
                )
                record = dict(item) | {
                    "mechanical": mechanical, "overlap": overlap,
                    "eligible": eligible,
                    "revalidated_from_gate_version": prior_hard,
                    "revalidated_from_movement_gate_version": prior_movement,
                    "revalidated_without_new_critic": True,
                    "revalidated_at": _now(), "completed_at": _now(),
                }
                append_jsonl(path, record)
                updated += 1
        return {
            "updated": updated, "total": total,
            "hard_gate_version": HARD_GATE_VERSION,
            "movement_gate_version": MOVEMENT_GATE_VERSION,
        }
    path = root / phase / "candidates.jsonl"
    candidates = _latest(path, "candidate_id")
    updated = 0
    for candidate_id, item in sorted(candidates.items()):
        previous = str(item.get("mechanical", {}).get("version", ""))
        if previous == HARD_GATE_VERSION and not phase.startswith("topology"):
            continue
        segment = str(item.get("segment", ""))
        text = str(item.get("text", ""))
        cell = cells_by_id.get(str(item.get("cell_id", "")))
        if cell is None or not segment or not text:
            continue
        overlap = index.check(candidate_id, text).to_dict()
        mechanical = phase_gate(phase, cell, item, overlap)
        record = dict(item) | {
            "mechanical": mechanical, "overlap": overlap,
            "eligible": bool(mechanical["passed"]),
            "revalidated_from_gate_version": previous,
            "revalidated_at": _now(),
        }
        append_jsonl(path, record)
        updated += 1
    return {
        "updated": updated, "total": len(_latest(path, "candidate_id")),
        "hard_gate_version": HARD_GATE_VERSION,
    }


def judge_candidates(
    *,
    campaign_dir: str | Path,
    critic: LlamaClient,
    phase: str = "topology",
    only_candidate: str = "",
) -> dict[str, Any]:
    root = Path(campaign_dir)
    campaign, _, cells, passages, _ = _load_campaign(root)
    cells_by_id = {item.cell_id: item for item in cells}
    anti_copy = AntiCopyIndex({item.passage_id: item.text for item in passages})
    candidate_path = root / phase / "candidates.jsonl"
    judgments_path = root / phase / "judgments.jsonl"
    calls_path = root / phase / "judgment_calls.jsonl"
    gates_path = root / phase / "gate_reviews.jsonl"
    identity_key = "runway_id" if phase == "runways" else "candidate_id"
    completed = _latest(judgments_path, "judgment_id")
    produced = 0
    for item in _latest(candidate_path, identity_key).values():
        candidate_id = item[identity_key]
        if only_candidate and candidate_id != only_candidate:
            continue
        cell = cells_by_id[item["cell_id"]]
        current_overlap = anti_copy.check(candidate_id, item["text"]).to_dict()
        current_gate = phase_gate(phase, cell, item, current_overlap)
        gate_review_id = f"{candidate_id}:{HARD_GATE_VERSION}"
        append_jsonl(gates_path, {
            "record_type": "CurrentHardGateReview", "version": HARD_GATE_VERSION,
            "gate_review_id": gate_review_id, identity_key: candidate_id,
            "status": "completed", "candidate_text_hash": item["text_hash"],
            "mechanical": current_gate, "overlap": current_overlap,
            "completed_at": _now(),
        })
        if not current_gate["passed"]:
            continue
        if phase == "runways":
            runway_text, judged_text = "", item["text"]
        elif phase in {"topology-staged", "topology-branch"}:
            judged_text = "\n\n".join(
                value for value in (
                    str(item.get("spark", "")).strip(),
                    str(item.get("continuation", "")).strip(),
                ) if value
            )
            runway_text = item["text"][: max(0, len(item["text"]) - len(judged_text))]
        else:
            judged_text = item.get("segment", item["text"])
            runway_text = item["text"][: max(0, len(item["text"]) - len(judged_text))]
        prompt = literary_critic_prompt(cell, runway_text, judged_text)
        prompt_hash = sha256_text(prompt)
        judgment_id = f"{candidate_id}:{prompt_hash[:16]}"
        if judgment_id in completed:
            continue
        call_record = {
            "record_type": "ReadOnlyCriticCall", "version": VERSION,
            "judgment_id": judgment_id, identity_key: candidate_id, "status": "started",
            "campaign_hash": campaign["campaign_hash"], "critic_model": critic.model,
            "prompt_hash": prompt_hash, "candidate_text_hash": item["text_hash"],
            "started_at": _now(),
        }
        append_jsonl(calls_path, call_record)
        result = critic.complete(
            messages=[{"role": "user", "content": prompt}], seed=int(sha256_text(candidate_id)[:8], 16),
            max_tokens=700, temperature=0.2, top_p=0.9, min_p=0.0,
            response_format={"type": "json_object"},
        )
        try:
            judgment = parse_critic(result.content, judged_text)
        except (ValueError, json.JSONDecodeError) as exc:
            append_jsonl(calls_path, {
                **call_record, "status": "failed", "raw_response": result.content,
                "error": str(exc), "completed_at": _now(),
            })
            continue
        record = {
            "record_type": "ReadOnlyLiteraryJudgment", "version": VERSION,
            "judgment_id": judgment_id, identity_key: candidate_id, "status": "completed",
            "campaign_hash": campaign["campaign_hash"], "critic_model": critic.model,
            "prompt_hash": prompt_hash, "candidate_text_hash": item["text_hash"],
            "judgment": judgment, "completed_at": _now(),
        }
        append_jsonl(judgments_path, record)
        append_jsonl(calls_path, {
            **call_record, "status": "completed", "raw_response": result.content,
            "judgment_hash": hash_json(judgment), "completed_at": record["completed_at"],
        })
        completed[judgment_id] = record
        produced += 1
    return {"new": produced, "total": len(_latest(judgments_path, "judgment_id"))}


def judge_pairwise_candidates(
    *,
    campaign_dir: str | Path,
    critic: LlamaClient,
    phase: str = "topology",
    recipe_ids: Sequence[str] = (),
    limit: int | None = None,
) -> dict[str, Any]:
    """Run blind A/B judgments twice with reversed label order."""

    root = Path(campaign_dir)
    campaign, _, cells, passages, _ = _load_campaign(root)
    cells_by_id = {item.cell_id: item for item in cells}
    anti_copy = AntiCopyIndex({item.passage_id: item.text for item in passages})
    candidates = _latest(root / phase / "candidates.jsonl", "candidate_id")
    if not recipe_ids:
        promotion = root / phase / "promotion.v1.json"
        if promotion.is_file():
            recipe_ids = tuple(_read_json(promotion).get("selected_recipe_ids", ()))
    allowed = set(recipe_ids)
    eligible: list[dict[str, Any]] = []
    for item in candidates.values():
        if allowed and item.get("recipe_id") not in allowed:
            continue
        cell = cells_by_id[item["cell_id"]]
        overlap = anti_copy.check(item["candidate_id"], item["text"]).to_dict()
        if phase_gate(phase, cell, item, overlap)["passed"]:
            eligible.append(item)
    groups: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for item in eligible:
        groups.setdefault((item["cell_id"], int(item["seed"])), []).append(item)
    output = root / phase / "pairwise_judgments.jsonl"
    calls = root / phase / "pairwise_calls.jsonl"
    completed = _latest(output, "judgment_id")
    produced = attempted = 0
    for (cell_id, seed), group in sorted(groups.items()):
        group.sort(key=lambda item: item["candidate_id"])
        for first, second in combinations(group, 2):
            for order, (left, right) in enumerate(((first, second), (second, first)), 1):
                judgment_id = f"{cell_id}.{seed}.{first['candidate_id']}__{second['candidate_id']}.order-{order}"
                if judgment_id in completed:
                    continue
                if limit is not None and attempted >= limit:
                    return {"new": produced, "total": len(completed) + produced, "stopped_at_limit": True}
                attempted += 1
                left_bank = _evidence_bank(left["segment"], "A")
                right_bank = _evidence_bank(right["segment"], "B")
                prompt = pairwise_critic_prompt(
                    cells_by_id[cell_id], left["segment"], right["segment"],
                    left_bank=left_bank, right_bank=right_bank,
                )
                started = {
                    "record_type": "ReadOnlyPairwiseCall", "version": VERSION,
                    "judgment_id": judgment_id, "status": "started",
                    "campaign_hash": campaign["campaign_hash"], "prompt_hash": sha256_text(prompt),
                    "left_candidate_id": left["candidate_id"], "right_candidate_id": right["candidate_id"],
                    "started_at": _now(),
                }
                append_jsonl(calls, started)
                result = critic.complete(
                    messages=[{"role": "user", "content": prompt}],
                    seed=int(sha256_text(judgment_id)[:8], 16), max_tokens=500,
                    temperature=0.2, top_p=0.9, min_p=0.0,
                    response_format={"type": "json_object"},
                )
                try:
                    judgment = parse_pairwise_critic(
                        result.content, left["segment"], right["segment"],
                        left_bank=left_bank, right_bank=right_bank,
                    )
                except (ValueError, json.JSONDecodeError) as exc:
                    append_jsonl(calls, {**started, "status": "failed", "raw_response": result.content, "error": str(exc), "completed_at": _now()})
                    continue
                winner_id = (
                    left["candidate_id"] if judgment["winner"] == "A" else
                    right["candidate_id"] if judgment["winner"] == "B" else "tie"
                )
                record = {
                    "record_type": "ReadOnlyPairwiseJudgment", "version": VERSION,
                    "judgment_id": judgment_id, "status": "completed",
                    "campaign_hash": campaign["campaign_hash"], "cell_id": cell_id, "seed": seed,
                    "left_candidate_id": left["candidate_id"], "right_candidate_id": right["candidate_id"],
                    "winner_candidate_id": winner_id, "judgment": judgment,
                    "completed_at": _now(),
                }
                append_jsonl(output, record)
                append_jsonl(calls, {**started, "status": "completed", "raw_response": result.content, "completed_at": record["completed_at"]})
                completed[judgment_id] = record
                produced += 1
    return {"new": produced, "total": len(completed)}


def promote_runways(
    campaign_dir: str | Path,
    *,
    selected_runway_ids: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Lock one critic-approved, base-authored opening per scene cell.

    This replaces the provisional keyword-only runway lock. The critic may reject
    or rank text, but the locked manuscript bytes always come from a preserved
    Gemma base response.
    """

    root = Path(campaign_dir)
    campaign, _, cells, passages, _ = _load_campaign(root)
    anti_copy = AntiCopyIndex({item.passage_id: item.text for item in passages})
    candidates = _latest(root / "runways" / "candidates.jsonl", "runway_id")
    judgments = _latest(root / "runways" / "judgments.jsonl", "runway_id")
    selected_runway_ids = dict(selected_runway_ids or {})
    locked: dict[str, Any] = {}
    audit: dict[str, Any] = {}
    for cell in cells:
        pool: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for runway_id, item in candidates.items():
            if item.get("cell_id") != cell.cell_id:
                continue
            overlap = anti_copy.check(runway_id, item["text"]).to_dict()
            if not _current_runway_gate(cell, item, overlap)["passed"]:
                continue
            judgment_record = judgments.get(runway_id)
            if not judgment_record:
                if selected_runway_ids.get(cell.cell_id) == runway_id:
                    row = dict(item)
                    row["selection_score"] = 0.0
                    row["critic_judgment_hash"] = "unavailable-invalid-critic-response"
                    pool.append(row)
                continue
            judgment = judgment_record["judgment"]
            row = dict(item)
            row["selection_score"] = float(judgment["mean_score"])
            row["critic_judgment_hash"] = hash_json(judgment)
            if judgment.get("hard_reject"):
                rejected.append({"runway_id": runway_id, "reason": "critic_hard_reject"})
            else:
                pool.append(row)
        explicit_id = selected_runway_ids.get(cell.cell_id)
        if explicit_id:
            explicit = [item for item in pool if item["runway_id"] == explicit_id]
            if not explicit:
                raise ValueError(f"explicit runway is not gate/critic eligible: {cell.cell_id}={explicit_id}")
            chosen = tuple(explicit)
        else:
            chosen = boltzmann_select(
                pool, count=1,
                seed=int(sha256_text(campaign["campaign_hash"] + ":critic-runway:" + cell.cell_id)[:8], 16),
                temperature=0.45,
            )
        if chosen:
            locked[cell.cell_id] = chosen[0]
        audit[cell.cell_id] = {
            "eligible_judged": len(pool),
            "critic_rejected": rejected,
            "selected": chosen[0]["runway_id"] if chosen else None,
            "selection_source": "research_lead_explicit" if explicit_id else "critic_boltzmann",
        }
    lock = {
        "record_type": "CriticLockedGeneratedRunways", "version": VERSION,
        "campaign_hash": campaign["campaign_hash"], "runways": locked,
        "audit": audit,
        "selection_policy": "hard-gates-then-read-only-critic-with-recorded-research-lead-overrides.v2",
    }
    lock["lock_hash"] = hash_json(lock)
    write_json(root / "runways" / "locked_runways.v1.json", lock)
    return lock


def promote_topologies(campaign_dir: str | Path, *, survivors: int = 3) -> dict[str, Any]:
    root = Path(campaign_dir)
    campaign, _, cells, passages, _ = _load_campaign(root)
    cells_by_id = {item.cell_id: item for item in cells}
    anti_copy = AntiCopyIndex({item.passage_id: item.text for item in passages})
    candidates = _latest(root / "topology" / "candidates.jsonl", "candidate_id")
    judgments = _latest(root / "topology" / "judgments.jsonl", "candidate_id")
    recipe_rows: dict[str, list[dict[str, Any]]] = {}
    for candidate_id, item in candidates.items():
        if not item.get("eligible") or candidate_id not in judgments:
            continue
        current_overlap = anti_copy.check(candidate_id, item["text"]).to_dict()
        if not phase_gate("topology", cells_by_id[item["cell_id"]], item, current_overlap)["passed"]:
            continue
        judgment = judgments[candidate_id]["judgment"]
        if judgment.get("hard_reject"):
            continue
        row = dict(item)
        row["selection_score"] = float(judgment["mean_score"])
        recipe_rows.setdefault(item["recipe_id"], []).append(row)
    summary: list[dict[str, Any]] = []
    target_cells = {item.cell_id for item in cells if item.cell_id in CALIBRATION_CELL_IDS}
    for recipe_id, rows in recipe_rows.items():
        by_cell = {cell: [item for item in rows if item["cell_id"] == cell] for cell in target_cells}
        eligibility = len(rows) / max(1, len([item for item in candidates.values() if item["recipe_id"] == recipe_id]))
        control_leak = any(item["cell_id"] == "institutional-pressure-control" and item["mechanical"]["diagnostics"]["erotic_signal"] > 1 for item in rows)
        cell_medians = {
            cell: median(item["selection_score"] for item in values) if values else 0.0
            for cell, values in by_cell.items()
        }
        summary.append({
            "recipe_id": recipe_id, "eligibility": eligibility,
            "cell_medians": cell_medians, "control_leak": control_leak,
            "selection_score": min(cell_medians.values()) if cell_medians else 0.0,
            "candidate_count": len(rows),
        })
    summary.sort(key=lambda item: (-item["selection_score"], -item["eligibility"], item["recipe_id"]))
    selected = [
        item for item in summary
        if not item["control_leak"]
        and item["eligibility"] >= 0.75
        and item["selection_score"] >= 5.0
    ][:survivors]
    selected_ids = {item["recipe_id"] for item in selected}
    pair_rows = list(_latest(root / "topology" / "pairwise_judgments.jsonl", "judgment_id").values())
    by_pair: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in pair_rows:
        left_id, right_id = row["left_candidate_id"], row["right_candidate_id"]
        if left_id not in candidates or right_id not in candidates:
            continue
        left_recipe = candidates[left_id]["recipe_id"]
        right_recipe = candidates[right_id]["recipe_id"]
        if left_recipe not in selected_ids or right_recipe not in selected_ids:
            continue
        by_pair.setdefault(tuple(sorted((left_id, right_id))), []).append(row)
    pair_stats = {recipe_id: {"wins": 0, "losses": 0, "ties": 0, "comparisons": 0} for recipe_id in selected_ids}
    for (first_id, second_id), rows in by_pair.items():
        if len(rows) < 2:
            continue
        winners = {row["winner_candidate_id"] for row in rows}
        first_recipe = candidates[first_id]["recipe_id"]
        second_recipe = candidates[second_id]["recipe_id"]
        if len(winners) == 1 and "tie" not in winners:
            winner_id = next(iter(winners))
            winner_recipe = candidates[winner_id]["recipe_id"]
            loser_recipe = second_recipe if winner_recipe == first_recipe else first_recipe
            pair_stats[winner_recipe]["wins"] += 1
            pair_stats[loser_recipe]["losses"] += 1
        else:
            pair_stats[first_recipe]["ties"] += 1
            pair_stats[second_recipe]["ties"] += 1
        pair_stats[first_recipe]["comparisons"] += 1
        pair_stats[second_recipe]["comparisons"] += 1
    for item in selected:
        stats = pair_stats[item["recipe_id"]]
        comparisons = stats["comparisons"]
        stats["win_rate"] = (stats["wins"] + 0.5 * stats["ties"]) / comparisons if comparisons else None
        item["reversed_pairwise"] = stats
    if selected and all(item["reversed_pairwise"]["comparisons"] > 0 for item in selected):
        selected.sort(key=lambda item: (-float(item["reversed_pairwise"]["win_rate"]), -item["selection_score"], item["recipe_id"]))
    decision = {
        "record_type": "TopologyPromotion", "version": VERSION,
        "campaign_hash": campaign["campaign_hash"], "ranked": summary,
        "selected_recipe_ids": [item["recipe_id"] for item in selected],
        "thresholds": {"eligibility": 0.75, "median_axes": 5.0, "control_leak": False},
        "created_at": _now(),
    }
    decision["decision_hash"] = hash_json({key: value for key, value in decision.items() if key != "created_at"})
    write_json(root / "topology" / "promotion.v1.json", decision)
    return decision


def analyze_v4_traces(
    campaign_dir: str | Path,
    *,
    phase: str = "topology",
    output: str | Path | None = None,
) -> dict[str, Any]:
    """Mechanical prompt/trace analysis for subsequent human/Codex close reading."""

    root = Path(campaign_dir)
    campaign, _, cells, passages, _ = _load_campaign(root)
    cells_by_id = {item.cell_id: item for item in cells}
    anti_copy = AntiCopyIndex({item.passage_id: item.text for item in passages})
    candidates = _latest(root / phase / "candidates.jsonl", "candidate_id")
    judgments = _latest(root / phase / "judgments.jsonl", "candidate_id")
    recipe_map = {item["recipe_id"]: item for item in campaign.get("recipes", [])}
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in candidates.values():
        groups.setdefault(item["recipe_id"], []).append(item)
    arms: list[dict[str, Any]] = []
    for recipe_id, rows in sorted(groups.items()):
        gate_pass = 0
        authorship_verified = 0
        score_axes: dict[str, list[float]] = {}
        lengths: list[int] = []
        source_sets: set[tuple[str, ...]] = set()
        failures: dict[str, int] = {}
        for item in rows:
            overlap = anti_copy.check(item["candidate_id"], item["text"]).to_dict()
            gate = phase_gate(phase, cells_by_id[item["cell_id"]], item, overlap)
            gate_pass += int(gate["passed"])
            for name, passed in gate.get("gates", {}).items():
                if not passed:
                    failures[name] = failures.get(name, 0) + 1
            lengths.append(len(_words(item.get("segment", item["text"]))))
            source_sets.add(tuple(item.get("source_ids", ())))
            assembly = item.get("assembly_path")
            if assembly:
                try:
                    verify_assembly(Path(campaign["project_root"]) / assembly, campaign["project_root"])
                    authorship_verified += 1
                except (ValueError, OSError, json.JSONDecodeError):
                    pass
            judgment = judgments.get(item["candidate_id"], {}).get("judgment", {})
            for axis, value in judgment.get("scores", {}).items():
                score_axes.setdefault(axis, []).append(float(value))
        arms.append({
            "recipe_id": recipe_id,
            "recipe": recipe_map.get(recipe_id, {}),
            "candidate_count": len(rows), "current_gate_pass": gate_pass,
            "eligibility_rate": gate_pass / max(1, len(rows)),
            "hard_failure_counts": failures,
            "authorship_verified": authorship_verified,
            "segment_word_median": median(lengths) if lengths else 0,
            "score_medians": {axis: median(values) for axis, values in score_axes.items()},
            "source_sets": [list(value) for value in sorted(source_sets)],
            "prompt_hashes": sorted({item["prompt_hash"] for item in rows}),
            "raw_response_hashes": sorted({item["raw_hash"] for item in rows}),
        })
    trace_files = {}
    for name in ("calls.jsonl", "candidates.jsonl", "judgments.jsonl", "judgment_calls.jsonl", "pairwise_judgments.jsonl", "pairwise_calls.jsonl", "gate_reviews.jsonl"):
        path = root / phase / name
        if path.is_file():
            trace_files[name] = {"path": str(path), "hash": hash_file(path)}
    payload = {
        "record_type": "V4PromptTraceAnalysis", "version": VERSION,
        "campaign_hash": campaign["campaign_hash"], "phase": phase,
        "arms": arms, "trace_files": trace_files,
        "limitations": [
            "These aggregates do not replace close reading of manuscripts and prompts.",
            "Absolute critic scores are not causal evidence without matched seed/cell comparisons.",
            "Prompt claims require inspecting retrieved source order and raw response boundaries.",
        ],
        "created_at": _now(),
    }
    payload["analysis_hash"] = hash_json({key: value for key, value in payload.items() if key != "created_at"})
    destination = Path(output) if output else root / phase / "trace_analysis.v1.json"
    write_json(destination, payload)
    return payload


V4_RESEARCH_REVIEW_FIELDS = (
    "recipe_id", "claim", "confidence", "intended_affordance_transfer",
    "observed_realization", "unwanted_leakage", "competing_explanations",
    "next_single_axis_mutation", "prediction", "falsifier", "recommendation",
    "manuscript_evidence", "trace_evidence",
)


def admit_v4_research_review(
    campaign_dir: str | Path,
    *,
    phase: str,
    review_file: str | Path,
    reviewer_id: str,
    role: str,
) -> dict[str, Any]:
    """Admit hash-linked post-judgment prompt/trace criticism."""

    if role not in {"trace_critic", "research_lead"}:
        raise ValueError("role must be trace_critic or research_lead")
    root = Path(campaign_dir).resolve()
    phase_dir = (root / phase).resolve()
    analysis_path = phase_dir / "trace_analysis.v1.json"
    pairwise_path = phase_dir / "pairwise_judgments.jsonl"
    if not analysis_path.is_file() or not pairwise_path.is_file():
        raise ValueError("trace analysis and frozen pairwise judgments are required first")
    analysis = _read_json(analysis_path)
    payload = _read_json(review_file)
    supplied = payload.get("reviews", [])
    if not isinstance(supplied, list) or not supplied:
        raise ValueError("review file must contain a non-empty reviews list")
    candidates = _latest(phase_dir / "candidates.jsonl", "candidate_id")
    recipe_ids = {item["recipe_id"] for item in candidates.values()}
    destination = phase_dir / "research_reviews.jsonl"
    if destination.is_file():
        for line in destination.read_text(encoding="utf-8").splitlines():
            old = json.loads(line)
            if old.get("reviewer_id") == reviewer_id and old.get("role") == role:
                raise ValueError("duplicate v4 research reviewer")
    records: list[dict[str, Any]] = []
    for item in supplied:
        missing = [field for field in V4_RESEARCH_REVIEW_FIELDS if field not in item]
        if missing:
            raise ValueError("research review missing fields: " + ", ".join(missing))
        if item["recipe_id"] not in recipe_ids:
            raise ValueError(f"unknown recipe: {item['recipe_id']}")
        confidence = float(item["confidence"])
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be within 0..1")
        manuscript_evidence = []
        for evidence in item["manuscript_evidence"]:
            candidate_id = str(evidence["candidate_id"])
            quote = str(evidence["quote"])
            if candidate_id not in candidates or quote not in candidates[candidate_id]["text"]:
                raise ValueError("research review manuscript evidence is not exact")
            manuscript_evidence.append({"candidate_id": candidate_id, "quote": quote})
        trace_evidence = []
        for evidence in item["trace_evidence"]:
            artifact = Path(str(evidence["artifact_path"])).resolve()
            try:
                artifact.relative_to(root)
            except ValueError as exc:
                raise ValueError("trace evidence must remain inside the campaign") from exc
            if not artifact.is_file():
                raise ValueError(f"missing trace artifact: {artifact}")
            actual = hash_file(artifact)
            if evidence.get("artifact_hash") and evidence["artifact_hash"] != actual:
                raise ValueError("trace evidence hash mismatch")
            trace_evidence.append({
                "artifact_path": str(artifact), "artifact_hash": actual,
                "observation": str(evidence.get("observation", "")),
            })
        record = {
            "record_type": "V4ResearchReview", "version": VERSION,
            "campaign_hash": analysis["campaign_hash"], "phase": phase,
            "analysis_hash": analysis["analysis_hash"],
            "pairwise_judgments_hash": hash_file(pairwise_path),
            "reviewer_id": reviewer_id, "role": role,
            **{field: item[field] for field in V4_RESEARCH_REVIEW_FIELDS if field not in {"manuscript_evidence", "trace_evidence"}},
            "manuscript_evidence": manuscript_evidence, "trace_evidence": trace_evidence,
            "source_review_hash": hash_file(review_file), "admitted_at": _now(),
        }
        record["review_hash"] = hash_json({key: value for key, value in record.items() if key != "admitted_at"})
        append_jsonl(destination, record)
        records.append(record)
    return {"admitted": len(records), "path": str(destination), "hashes": [item["review_hash"] for item in records]}


SAMPLER_SWEEP = (
    SamplerV4(temperature=0.82, xtc_probability=0.0),
    SamplerV4(temperature=0.95, xtc_probability=0.10),
    SamplerV4(temperature=0.95, xtc_probability=0.50),
    SamplerV4(temperature=1.05, xtc_probability=0.10),
    SamplerV4(temperature=0.95, xtc_probability=0.10, dry_multiplier=0.65),
)

CONTEXT_DOSES = (8_000, 16_000, 32_000, 48_000)


def freeze_behavioral_recipes(
    campaign_dir: str | Path, *, parent_recipe_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Freeze the preregistered abstract-ledger -> behavioral-events mutation."""

    root = Path(campaign_dir)
    campaign = _read_json(root / "campaign_manifest.v1.json")
    topology_decision = _read_json(root / "topology" / "promotion.v1.json")
    selected_ids = tuple(parent_recipe_ids) or tuple(topology_decision["selected_recipe_ids"])
    recipes_by_id = {
        item["recipe_id"]: PromptRecipeV4(**{
            **{key: value for key, value in item.items() if key not in {"recipe_hash", "sampler"}},
            "sampler": SamplerV4(**item["sampler"]),
        }) for item in campaign["recipes"]
    }
    children: list[PromptRecipeV4] = []
    for recipe_id in selected_ids:
        parent = recipes_by_id.get(recipe_id)
        if parent is None:
            raise ValueError(f"unknown topology recipe for behavioral mutation: {recipe_id}")
        child = PromptRecipeV4(
            recipe_id=f"{recipe_id}.behavioral", topology=parent.topology,
            context_tokens=parent.context_tokens, source_count=parent.source_count,
            source_order=parent.source_order, graph_granularity=parent.graph_granularity,
            target_density="behavioral", runway_type=parent.runway_type,
            encoding=parent.encoding, sampler=parent.sampler,
            parent_recipe_hash=parent.recipe_hash, mutated_axis="target_density",
        )
        validate_recipe_mutation(parent, child)
        children.append(child)
    payload = {
        "record_type": "BehavioralTargetRecipes", "version": VERSION,
        "campaign_hash": campaign["campaign_hash"],
        "parent_decision_hash": topology_decision["decision_hash"],
        "recipes": [item.public_dict() for item in children],
    }
    payload["recipe_set_hash"] = hash_json(payload)
    write_json(root / "behavioral" / "recipes.v1.json", payload)
    return payload


def run_behavioral_search(
    *, campaign_dir: str | Path, client: LlamaClient,
    admission: SharedEndpointAdmission, seeds: Sequence[int],
    parent_recipe_ids: Sequence[str] = (), max_tokens: int = 760,
    only_recipe: str = "", only_cell: str = "", limit: int | None = None,
) -> dict[str, Any]:
    root = Path(campaign_dir)
    recipe_file = root / "behavioral" / "recipes.v1.json"
    if not recipe_file.is_file():
        freeze_behavioral_recipes(root, parent_recipe_ids=parent_recipe_ids)
    payload = _read_json(recipe_file)
    recipes = tuple(PromptRecipeV4(**{
        **{key: value for key, value in item.items() if key not in {"recipe_hash", "sampler"}},
        "sampler": SamplerV4(**item["sampler"]),
    }) for item in payload["recipes"])
    return _run_recipe_set(
        campaign_dir=root, client=client, admission=admission, recipes=recipes,
        phase="behavioral", seeds=seeds, max_tokens=max_tokens,
        only_recipe=only_recipe, only_cell=only_cell, limit=limit,
    )


def promote_behavioral(campaign_dir: str | Path, *, survivors: int = 2) -> dict[str, Any]:
    return _promote_recipe_phase(campaign_dir, phase="behavioral", survivors=survivors)


def freeze_context_recipes(campaign_dir: str | Path) -> dict[str, Any]:
    """Create additive context-dose children of topology survivors."""

    root = Path(campaign_dir)
    campaign = _read_json(root / "campaign_manifest.v1.json")
    behavioral_decision = root / "behavioral" / "promotion.v1.json"
    if behavioral_decision.is_file():
        promotion = _read_json(behavioral_decision)
        parent_payload = _read_json(root / "behavioral" / "recipes.v1.json")
    else:
        promotion = _read_json(root / "topology" / "promotion.v1.json")
        parent_payload = {"recipes": campaign["recipes"]}
    recipes_by_id = {
        item["recipe_id"]: PromptRecipeV4(**{
            **{key: value for key, value in item.items() if key not in {"recipe_hash", "sampler"}},
            "sampler": SamplerV4(**item["sampler"]),
        }) for item in parent_payload["recipes"]
    }
    recipes: list[PromptRecipeV4] = []
    for recipe_id in promotion["selected_recipe_ids"]:
        parent = recipes_by_id[recipe_id]
        recipes.append(parent)
        for dose in CONTEXT_DOSES[1:]:
            child = PromptRecipeV4(
                recipe_id=f"{recipe_id}.dose-{dose // 1000}k",
                topology=parent.topology, context_tokens=dose,
                source_count=parent.source_count, source_order=parent.source_order,
                graph_granularity=parent.graph_granularity,
                target_density=parent.target_density, runway_type=parent.runway_type,
                encoding=parent.encoding, sampler=parent.sampler,
                parent_recipe_hash=parent.recipe_hash, mutated_axis="context_tokens",
            )
            validate_recipe_mutation(parent, child)
            recipes.append(child)
    payload = {
        "record_type": "ContextDoseRecipes", "version": VERSION,
        "campaign_hash": campaign["campaign_hash"],
        "parent_decision_hash": promotion["decision_hash"],
        "recipes": [item.public_dict() for item in recipes],
    }
    payload["recipe_set_hash"] = hash_json(payload)
    write_json(root / "context" / "recipes.v1.json", payload)
    return payload


def run_context_search(
    *, campaign_dir: str | Path, client: LlamaClient,
    admission: SharedEndpointAdmission, seeds: Sequence[int],
    max_tokens: int = 760, only_recipe: str = "", only_cell: str = "",
    limit: int | None = None,
) -> dict[str, Any]:
    root = Path(campaign_dir)
    recipe_file = root / "context" / "recipes.v1.json"
    if not recipe_file.is_file():
        freeze_context_recipes(root)
    payload = _read_json(recipe_file)
    recipes = tuple(PromptRecipeV4(**{
        **{key: value for key, value in item.items() if key not in {"recipe_hash", "sampler"}},
        "sampler": SamplerV4(**item["sampler"]),
    }) for item in payload["recipes"])
    return _run_recipe_set(
        campaign_dir=root, client=client, admission=admission, recipes=recipes,
        phase="context", seeds=seeds, max_tokens=max_tokens,
        only_recipe=only_recipe, only_cell=only_cell, limit=limit,
    )


def _promote_recipe_phase(
    campaign_dir: str | Path, *, phase: str, survivors: int,
) -> dict[str, Any]:
    root = Path(campaign_dir)
    campaign = _read_json(root / "campaign_manifest.v1.json")
    candidates = _latest(root / phase / "candidates.jsonl", "candidate_id")
    judgments = _latest(root / phase / "judgments.jsonl", "candidate_id")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for candidate_id, candidate in candidates.items():
        if candidate.get("eligible") and candidate_id in judgments:
            row = dict(candidate)
            row["selection_score"] = judgments[candidate_id]["judgment"]["mean_score"]
            grouped.setdefault(candidate["recipe_id"], []).append(row)
    ranked: list[dict[str, Any]] = []
    for recipe_id, rows in grouped.items():
        cells = {item["cell_id"] for item in rows}
        medians = {
            cell: median(item["selection_score"] for item in rows if item["cell_id"] == cell)
            for cell in cells
        }
        ranked.append({
            "recipe_id": recipe_id, "cell_medians": medians,
            "selection_score": min(medians.values()) if len(cells) == len(CALIBRATION_CELL_IDS) else 0.0,
            "candidate_count": len(rows), "cell_count": len(cells),
        })
    ranked.sort(key=lambda item: (-item["selection_score"], item["recipe_id"]))
    selected = [item["recipe_id"] for item in ranked[:survivors] if item["selection_score"] > 0]
    decision = {
        "record_type": "ContextDosePromotion" if phase == "context" else "RecipePromotion",
        "version": VERSION, "campaign_hash": campaign["campaign_hash"],
        "phase": phase, "ranked": ranked, "selected_recipe_ids": selected,
        "selected_recipe_id": selected[0] if selected else "", "created_at": _now(),
    }
    decision["decision_hash"] = hash_json({key: value for key, value in decision.items() if key != "created_at"})
    write_json(root / phase / "promotion.v1.json", decision)
    return decision


def promote_context(campaign_dir: str | Path, *, survivors: int = 2) -> dict[str, Any]:
    return _promote_recipe_phase(campaign_dir, phase="context", survivors=survivors)


def freeze_sampler_recipes(campaign_dir: str | Path) -> dict[str, Any]:
    root = Path(campaign_dir)
    campaign = _read_json(root / "campaign_manifest.v1.json")
    context_promotion = root / "context" / "promotion.v1.json"
    if context_promotion.is_file():
        promotion = _read_json(context_promotion)
        recipe_payload = _read_json(root / "context" / "recipes.v1.json")
    else:
        promotion = _read_json(root / "topology" / "promotion.v1.json")
        recipe_payload = {"recipes": campaign["recipes"]}
    recipes_by_id = {
        item["recipe_id"]: PromptRecipeV4(**{
            **{key: value for key, value in item.items() if key not in {"recipe_hash", "sampler"}},
            "sampler": SamplerV4(**item["sampler"]),
        }) for item in recipe_payload["recipes"]
    }
    children: list[PromptRecipeV4] = []
    for recipe_id in promotion["selected_recipe_ids"]:
        parent = recipes_by_id[recipe_id]
        for index, sampler in enumerate(SAMPLER_SWEEP, 1):
            child = PromptRecipeV4(
                recipe_id=f"{recipe_id}.sampler-{index}", topology=parent.topology,
                context_tokens=parent.context_tokens, source_count=parent.source_count,
                source_order=parent.source_order, graph_granularity=parent.graph_granularity,
                target_density=parent.target_density, runway_type=parent.runway_type,
                encoding=parent.encoding, sampler=sampler,
                parent_recipe_hash=parent.recipe_hash, mutated_axis="sampler",
            )
            validate_recipe_mutation(parent, child)
            children.append(child)
    payload = {
        "record_type": "SamplerSweepRecipes", "version": VERSION,
        "campaign_hash": campaign["campaign_hash"],
        "parent_decision_hash": promotion["decision_hash"],
        "recipes": [item.public_dict() for item in children],
    }
    payload["recipe_set_hash"] = hash_json(payload)
    write_json(root / "sampler" / "recipes.v1.json", payload)
    return payload


def _run_recipe_set(
    *,
    campaign_dir: str | Path,
    client: LlamaClient,
    admission: SharedEndpointAdmission,
    recipes: Sequence[PromptRecipeV4],
    phase: str,
    seeds: Sequence[int],
    max_tokens: int,
    only_recipe: str = "",
    only_cell: str = "",
    limit: int | None = None,
    allowed_cell_ids: frozenset[str] = CALIBRATION_CELL_IDS,
) -> dict[str, Any]:
    """Run a frozen recipe set through the topology movement harness."""

    root = Path(campaign_dir)
    campaign, _, cells, passages, graphs = _load_campaign(root)
    project_root = Path(campaign["project_root"])
    runways = _load_locked_runways(root)
    anti_copy = AntiCopyIndex({item.passage_id: item.text for item in passages})
    calls = root / phase / "calls.jsonl"
    candidate_path = root / phase / "candidates.jsonl"
    completed = _latest(candidate_path, "candidate_id")
    produced = attempted = 0
    for recipe in recipes:
        if only_recipe and recipe.recipe_id != only_recipe:
            continue
        for cell in cells:
            if cell.cell_id not in allowed_cell_ids:
                continue
            if only_cell and cell.cell_id != only_cell:
                continue
            runway = runways[cell.cell_id]
            prompt, source_ids = render_generation_prompt(
                recipe=recipe, cell=cell, passages=passages, graphs=graphs,
                runway=runway["text"],
                movement="Develop pressure, resistance, and one consequential counteroffer without resolving the whole scene.",
                self_demonstrations=(
                    tuple(item["text"] for key, item in sorted(runways.items()) if key != cell.cell_id)
                    if recipe.topology == "source-plus-self-demo" else ()
                ),
            )
            prompt_hash = sha256_text(prompt)
            prompt_tokens = client.token_count(prompt)
            prompt_path = root / phase / "prompts" / recipe.recipe_id / f"{cell.cell_id}.txt"
            if prompt_path.is_file() and sha256_text(prompt_path.read_text(encoding="utf-8")) != prompt_hash:
                raise ValueError("prompt drift in frozen recipe set")
            atomic_write_text(prompt_path, prompt)
            for seed in seeds:
                candidate_id = f"{phase}.{recipe.recipe_id}.{cell.cell_id}.{seed}"
                request_hash = _generation_request_hash(
                    campaign_hash=campaign["campaign_hash"], prompt_hash=prompt_hash,
                    model=client.model, seed=seed, max_tokens=max_tokens,
                    sampler=asdict(recipe.sampler), source_ids=source_ids,
                )
                if candidate_id in completed:
                    _assert_resumable_request(completed[candidate_id], request_hash, candidate_id)
                    continue
                if limit is not None and attempted >= limit:
                    return {"new": produced, "stopped_at_limit": True}
                attempted += 1
                raw_path = root / phase / "raw" / f"{candidate_id}.txt"
                call = {
                    "record_type": "V4ModelCall", "call_id": candidate_id,
                    "status": "started", "model": client.model,
                    "runtime": _endpoint_runtime_provenance(client),
                    "prompt_hash": prompt_hash, "prompt_path": str(prompt_path),
                    "prompt_tokens": prompt_tokens, "seed": seed,
                    "sampler": asdict(recipe.sampler), "max_tokens": max_tokens,
                    "request_hash": request_hash,
                    "started_at": _now(),
                }
                append_jsonl(calls, call)
                parts: list[str] = []
                def on_delta(delta: str) -> None:
                    parts.append(delta)
                    match = anti_copy.first_exact_match(runway["text"] + "".join(parts))
                    if match:
                        raise SourceOverlapError(match)
                try:
                    with admission.acquire(owner=candidate_id, prompt_hash=prompt_hash, prompt_tokens=prompt_tokens, completion_tokens=max_tokens):
                        cache_preparation = prepare_prompt_family(client, prompt_hash)
                        result = client.stream_raw(
                            prompt=prompt, seed=seed, max_tokens=max_tokens,
                            temperature=recipe.sampler.temperature, top_p=recipe.sampler.top_p,
                            min_p=recipe.sampler.min_p, xtc_probability=recipe.sampler.xtc_probability,
                            extra=recipe.sampler.raw_extra(), on_delta=on_delta, stop=MANUSCRIPT_STOP,
                        )
                except SourceOverlapError as exc:
                    aborted = "".join(parts)
                    atomic_write_text(raw_path, aborted)
                    record = {
                        "record_type": "PromptSearchCandidate", "version": VERSION,
                        "candidate_id": candidate_id, "status": "completed",
                        "campaign_hash": campaign["campaign_hash"],
                        "recipe_id": recipe.recipe_id, "recipe_hash": recipe.recipe_hash,
                        "cell_id": cell.cell_id, "seed": seed, "source_ids": list(source_ids),
                        "text": runway["text"], "text_hash": runway["text_hash"], "segment": "",
                        "assembly_path": "", "prompt_hash": prompt_hash,
                        "request_hash": request_hash,
                        "prompt_tokens": prompt_tokens, "raw_hash": sha256_text(aborted),
                        "raw_path": _relative(raw_path, project_root),
                        "mechanical": {"version": HARD_GATE_VERSION, "passed": False, "gates": {"anti_copy": False}, "diagnostics": {"stream_abort": exc.match}},
                        "overlap": {"hard_fail": True, "stream_match": exc.match},
                        "eligible": False, "finish_reason": "streaming_source_overlap_abort",
                        "usage": {}, "timings": {}, "completed_at": _now(),
                    }
                    append_jsonl(candidate_path, record)
                    append_jsonl(calls, {**call, "status": "completed", "finish_reason": record["finish_reason"], "raw_hash": record["raw_hash"], "completed_at": record["completed_at"]})
                    completed[candidate_id] = record
                    produced += 1
                    continue
                atomic_write_text(raw_path, result.content)
                try:
                    segment, start, end = _complete_paragraph_prefix(result.content, 300, 500)
                    text = runway["text"] + "\n\n" + segment
                    overlap = anti_copy.check(candidate_id, text).to_dict()
                    gate = hard_gate(cell, text, overlap)
                except ValueError as exc:
                    segment, start, end, text = "", 0, 0, runway["text"]
                    overlap, gate = {}, {"passed": False, "error": str(exc)}
                assembly_path: Path | None = None
                if segment:
                    spans = (
                        *_runway_model_spans(runway),
                        ModelSpan(
                            span_id=f"{candidate_id}.segment", call_id=candidate_id,
                            raw_path=_relative(raw_path, project_root), raw_hash=sha256_text(result.content),
                            raw_char_start=start, raw_char_end=end, text_hash=sha256_text(segment), role=f"{phase}-movement",
                        ),
                    )
                    assembly = ManuscriptAssembly(
                        candidate_id, spans,
                        (*_runway_separators(runway), "\n\n"), sha256_text(text),
                    )
                    assembly_path = root / phase / "assemblies" / f"{candidate_id}.json"
                    _write_verified_assembly(assembly_path, assembly, project_root)
                record = {
                    "record_type": "PromptSearchCandidate", "version": VERSION,
                    "candidate_id": candidate_id, "status": "completed",
                    "campaign_hash": campaign["campaign_hash"], "phase": phase,
                    "recipe_id": recipe.recipe_id, "recipe_hash": recipe.recipe_hash,
                    "cell_id": cell.cell_id, "seed": seed, "source_ids": list(source_ids),
                    "text": text, "text_hash": sha256_text(text), "segment": segment,
                    "assembly_path": _relative(assembly_path, project_root) if assembly_path else "",
                    "prompt_hash": prompt_hash, "prompt_tokens": prompt_tokens,
                    "request_hash": request_hash,
                    "raw_hash": sha256_text(result.content), "raw_path": _relative(raw_path, project_root),
                    "mechanical": gate, "overlap": overlap, "eligible": bool(gate.get("passed")),
                    "finish_reason": result.finish_reason, "usage": result.usage,
                    "timings": result.timings, "completed_at": _now(),
                }
                append_jsonl(candidate_path, record)
                append_jsonl(calls, {**call, "status": "completed", "raw_hash": record["raw_hash"], "completed_at": record["completed_at"]})
                produced += 1
    return {"new": produced, "total": len(_latest(candidate_path, "candidate_id"))}


def run_sampler_search(
    *, campaign_dir: str | Path, client: LlamaClient,
    admission: SharedEndpointAdmission, seeds: Sequence[int], max_tokens: int = 760,
    only_recipe: str = "", only_cell: str = "", limit: int | None = None,
) -> dict[str, Any]:
    root = Path(campaign_dir)
    recipe_file = root / "sampler" / "recipes.v1.json"
    if not recipe_file.is_file():
        freeze_sampler_recipes(root)
    payload = _read_json(recipe_file)
    recipes = tuple(PromptRecipeV4(**{
        **{key: value for key, value in item.items() if key not in {"recipe_hash", "sampler"}},
        "sampler": SamplerV4(**item["sampler"]),
    }) for item in payload["recipes"])
    return _run_recipe_set(
        campaign_dir=root, client=client, admission=admission, recipes=recipes,
        phase="sampler", seeds=seeds, max_tokens=max_tokens,
        only_recipe=only_recipe, only_cell=only_cell, limit=limit,
    )


def run_bootstrap(
    *, campaign_dir: str | Path, client: LlamaClient,
    admission: SharedEndpointAdmission, seeds: Sequence[int], max_tokens: int = 760,
    limit: int | None = None,
) -> dict[str, Any]:
    root = Path(campaign_dir)
    decision = _read_json(root / "sampler" / "promotion.v1.json")
    recipe_set = _read_json(root / "sampler" / "recipes.v1.json")
    raw = next(item for item in recipe_set["recipes"] if item["recipe_id"] == decision["selected_recipe_id"])
    recipe = PromptRecipeV4(**{
        **{key: value for key, value in raw.items() if key not in {"recipe_hash", "sampler"}},
        "sampler": SamplerV4(**raw["sampler"]),
    })
    return _run_recipe_set(
        campaign_dir=root, client=client, admission=admission, recipes=(recipe,),
        phase="bootstrap", seeds=seeds, max_tokens=max_tokens,
        limit=limit, allowed_cell_ids=frozenset({"fulcrum-s01"}),
    )


def promote_bootstrap(campaign_dir: str | Path, *, minimum_score: float = 5.0, maximum: int = 8) -> dict[str, Any]:
    root = Path(campaign_dir)
    campaign = _read_json(root / "campaign_manifest.v1.json")
    candidates = _latest(root / "bootstrap" / "candidates.jsonl", "candidate_id")
    judgments = _latest(root / "bootstrap" / "judgments.jsonl", "candidate_id")
    admitted = []
    for candidate_id, item in candidates.items():
        judgment = judgments.get(candidate_id, {}).get("judgment", {})
        if not item.get("eligible") or float(judgment.get("mean_score", 0.0)) < minimum_score:
            continue
        assembly_path = Path(campaign["project_root"]) / item["assembly_path"]
        verified = verify_assembly(assembly_path, campaign["project_root"])
        admitted.append({
            "candidate_id": candidate_id, "text": item["text"],
            "text_hash": item["text_hash"], "assembly_path": item["assembly_path"],
            "mean_score": judgment["mean_score"], "verified": verified["verified"],
        })
    admitted.sort(key=lambda item: (-float(item["mean_score"]), item["candidate_id"]))
    admitted = admitted[:maximum]
    sampler_decision = _read_json(root / "sampler" / "promotion.v1.json")
    recipe_set = _read_json(root / "sampler" / "recipes.v1.json")
    parent_raw = next(item for item in recipe_set["recipes"] if item["recipe_id"] == sampler_decision["selected_recipe_id"])
    parent = PromptRecipeV4(**{
        **{key: value for key, value in parent_raw.items() if key not in {"recipe_hash", "sampler"}},
        "sampler": SamplerV4(**parent_raw["sampler"]),
    })
    if parent.topology == "source-plus-self-demo":
        derived = parent
    else:
        derived = PromptRecipeV4(
            recipe_id=parent.recipe_id + ".self-demo", topology="source-plus-self-demo",
            context_tokens=parent.context_tokens, source_count=parent.source_count,
            source_order=parent.source_order, graph_granularity=parent.graph_granularity,
            target_density=parent.target_density, runway_type=parent.runway_type,
            encoding=parent.encoding, sampler=parent.sampler,
            parent_recipe_hash=parent.recipe_hash, mutated_axis="topology",
        )
        validate_recipe_mutation(parent, derived)
    payload = {
        "record_type": "VerifiedGemmaSelfDemonstrations", "version": VERSION,
        "campaign_hash": campaign["campaign_hash"], "admitted": admitted,
        "derived_recipe": derived.public_dict(), "minimum_score": minimum_score,
        "created_at": _now(),
    }
    payload["bootstrap_hash"] = hash_json({key: value for key, value in payload.items() if key != "created_at"})
    write_json(root / "bootstrap" / "promotion.v1.json", payload)
    return payload


def promote_sampler(campaign_dir: str | Path) -> dict[str, Any]:
    root = Path(campaign_dir)
    campaign = _read_json(root / "campaign_manifest.v1.json")
    candidates = _latest(root / "sampler" / "candidates.jsonl", "candidate_id")
    judgments = _latest(root / "sampler" / "judgments.jsonl", "candidate_id")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for candidate_id, candidate in candidates.items():
        if candidate.get("eligible") and candidate_id in judgments:
            row = dict(candidate)
            row["selection_score"] = judgments[candidate_id]["judgment"]["mean_score"]
            grouped.setdefault(candidate["recipe_id"], []).append(row)
    ranked = []
    for recipe_id, rows in grouped.items():
        cells = {item["cell_id"] for item in rows}
        medians = {cell: median(item["selection_score"] for item in rows if item["cell_id"] == cell) for cell in cells}
        ranked.append({
            "recipe_id": recipe_id, "cell_medians": medians,
            "selection_score": min(medians.values()) if medians else 0.0,
            "candidate_count": len(rows),
        })
    ranked.sort(key=lambda item: (-item["selection_score"], item["recipe_id"]))
    decision = {
        "record_type": "SamplerPromotion", "version": VERSION,
        "campaign_hash": campaign["campaign_hash"], "ranked": ranked,
        "selected_recipe_id": ranked[0]["recipe_id"] if ranked else "",
        "created_at": _now(),
    }
    decision["decision_hash"] = hash_json({key: value for key, value in decision.items() if key != "created_at"})
    write_json(root / "sampler" / "promotion.v1.json", decision)
    return decision


MOVEMENTS = (
    ("approach", "Establish concrete pressure, desire, and an impediment. End on a live offer or discovery."),
    ("complication", "Let a characteristic coping move backfire. Deepen subtext and relational asymmetry without resolving it."),
    ("embodied-turn", "Make bodily action and dialogue answer one another. Change knowledge, trust, or choice through observable agency."),
    ("consequence", "Pay the local causal chain, preserve remaining tension, and end on a concrete changed future possibility."),
)

S01_MOVEMENTS = (
    (
        "dyadic-contact",
        "Continue from the present welcome without replaying Mara's arrival. The unnamed blond man is Jonah; Mara may learn his name through the exchange. Render one first dyadic contact through concrete dialogue, posture, and an imperfect inference. The exchange changes what Mara attends to without resolving whom she can trust. Only Mara and the blond man are present.",
    ),
    (
        "gathering-handoff",
        "Unnamed guests and their voices reach the common room, interrupting and "
        "reframing Mara's contact with Jonah. Among them, a distinct brown-haired "
        "visiting fellow is already carrying a glass while absorbed in an important conversation. "
        "Reach that visible state within eighty words. End immediately after Mara has "
        "located the glass carrier in the room, before he leaves it. Only the people "
        "already present and unnamed arriving guests appear.",
    ),
    (
        "glass-deposit",
        "Begin directly with the brown-haired visiting fellow leaving a half-full "
        "glass on a wall while his important conversation continues. Make the object, "
        "his absorption, and his assumption that someone else will handle it spatially "
        "clear. End before anyone retrieves the glass. Only already-present people appear.",
    ),
    (
        "labor-recognition",
        "The people already present are Mara, Jonah, and the unnamed brown-haired "
        "visiting fellow. A previously unseen older catering worker enters and "
        "retrieves the visiting fellow's abandoned glass without acknowledgment "
        "while his conversation continues. The visiting fellow and worker remain unnamed. "
        "Through observable action, Mara notices who assumes whose labor. End on that "
        "concrete recognition before anyone turns it into a lesson.",
    ),
    (
        "calibration-frame",
        "Calibration frame: Adrian now enters, hears Mara's exact observation of the glass and worker, "
        "and turns it into a checkable game. He lays a brass key, a white stone, "
        "and a wooden token on the table. Mara will silently choose one; a reader "
        "will later try to identify it only from her nonverbal reactions. Adrian "
        "makes clear that Mara may decline or stop. Through dialogue and physical "
        "action, he offers the test without performing it. End on Mara facing a "
        "real choice whether to participate, before she selects an object.",
    ),
    (
        "calibration-choice",
        "Mara freely chooses to try the checkable game while remaining unsure what "
        "it could prove. She privately selects exactly one of the brass key, white "
        "stone, or wooden token and conceals the choice from the future reader. End "
        "before the reader enters or anyone guesses.",
    ),
    (
        "livia-entrance",
        "Livia enters the room after Mara has hidden her choice. Render the "
        "interruption, Mara's first concrete impression of her, and a brief "
        "introduction through physical action and dialogue. End before Livia "
        "identifies the chosen object or attempts any read.",
    ),
    (
        "livia-first-read",
        "Livia is now present and has not yet attempted a read. Without touching "
        "the objects, she identifies which one Mara selected. The result startles Mara, "
        "but her visible attention and posture remain an ordinary possible cue. End on "
        "Mara's reaction before Livia attempts another read.",
    ),
    (
        "livia-second-read",
        "Livia makes a second, different inference about Mara from an observable cue "
        "in her speech, posture, breath, clothing, or hands. The inference is specific "
        "and largely right but not omniscient. Mara notices both the accuracy and the "
        "available ordinary cue. End before anyone asks Jonah to perform.",
    ),
    (
        "jonah-costly-refusal",
        "Adrian or Livia invites Jonah to display what else he can infer about Mara. "
        "Jonah refuses to turn her into an object of expertise. His restraint costs "
        "him visible status in the group and changes what Mara notices about him. End "
        "on that relational change, before any wrist-contact exercise begins.",
    ),
    (
        "wrist-contact",
        "During mutually chosen wrist contact, attraction changes Mara's attention and the physical action changes what she believes about Jonah. Stop while contact and uncertainty are still active.",
    ),
    (
        "control-collapse",
        "Mara alters one cue channel without announcing it. Livia keeps reading, but her accuracy falls in observable mistakes while one smaller result remains difficult to explain.",
    ),
    (
        "consequence",
        "Some accuracy collapses, one smaller ambiguous result survives, Jonah recognizes Mara's control, and Mara freely chooses continued engagement with Fulcrum.",
    ),
)

S01_MOVEMENT_WORD_BANDS: Mapping[str, tuple[int, int]] = {
    "dyadic-contact": (70, 220),
    "gathering-handoff": (60, 180),
    # This movement pays two linked dramatic units: the witnessed labor/status
    # transaction and Adrian's conversion of it into a game.  A 220-word cap
    # repeatedly cut off the transaction before the calibration turn.
    "glass-deposit": (60, 160),
    "labor-recognition": (80, 180),
    "calibration-frame": (140, 240),
    "calibration-choice": (60, 210),
    "livia-entrance": (90, 220),
    "livia-first-read": (150, 280),
    "livia-second-read": (160, 300),
    "jonah-costly-refusal": (170, 320),
    "wrist-contact": (220, 340),
    "control-collapse": (220, 340),
    "consequence": (220, 340),
}


def movements_for_cell(cell: BenchmarkCell) -> tuple[tuple[str, str], ...]:
    return S01_MOVEMENTS if cell.cell_id == "fulcrum-s01" else MOVEMENTS


def movement_word_band(
    cell: BenchmarkCell, movement_id: str,
    fallback_minimum: int, fallback_maximum: int,
) -> tuple[int, int]:
    if cell.cell_id == "fulcrum-s01":
        return S01_MOVEMENT_WORD_BANDS[movement_id]
    return fallback_minimum, fallback_maximum


def apprenticeship_excerpt_word_band(
    cell: BenchmarkCell, movement_id: str,
    fallback_minimum: int, fallback_maximum: int,
) -> tuple[int, int]:
    """Return the causal demonstration dose, independent of output length.

    A source excerpt is a worked example, not a target word-count template.
    In particular, using the 320–520 word status output band retained hundreds
    of words of unrelated dinner conversation before the servant transaction;
    base continuations faithfully copied that delay and missed the payment.
    """

    if cell.cell_id == "fulcrum-s01" and movement_id in {
        "glass-deposit", "labor-recognition",
    }:
        return (100, 220)
    if cell.cell_id == "fulcrum-s01" and movement_id == "gathering-handoff":
        return (60, 180)
    return movement_word_band(
        cell, movement_id, fallback_minimum, fallback_maximum,
    )


def sample_s01_trajectories(
    *,
    campaign_dir: str | Path,
    base_client: LlamaClient,
    critic_client: LlamaClient,
    admission: SharedEndpointAdmission,
    seeds: Sequence[int],
    max_tokens: int = 850,
    select_count: int = 4,
) -> dict[str, Any]:
    """Sample free-form base trajectories and rank without compiling them."""

    root = Path(campaign_dir)
    campaign, _, cells, passages, _ = _load_campaign(root)
    cell = next(item for item in cells if item.cell_id == "fulcrum-s01")
    path = root / "s01-trajectories" / "candidates.jsonl"
    calls = root / "s01-trajectories" / "calls.jsonl"
    completed = _latest(path, "trajectory_id")
    produced = 0
    prompt = (
        "The records below describe a romance-thriller chapter. Sample one surprising, "
        "concrete causal trajectory. Preserve every locked fact while choosing specific "
        "objects, social moves, errors, jokes, reversals, and an unresolved residue. "
        "Do not write manuscript prose and do not explain a moral.\n\n"
        + _story_card(cell) +
        "\n\nSCENE TRAJECTORY\n"
    )
    prompt_hash = sha256_text(prompt)
    prompt_tokens = base_client.token_count(prompt)
    for seed in seeds:
        trajectory_id = f"s01-trajectory.{seed}"
        if trajectory_id in completed:
            continue
        call = {
            "record_type": "V4ModelCall", "call_id": trajectory_id,
            "status": "started", "model": base_client.model,
            "runtime": _endpoint_runtime_provenance(base_client),
            "prompt_hash": prompt_hash, "prompt_tokens": prompt_tokens,
            "seed": seed, "started_at": _now(),
        }
        append_jsonl(calls, call)
        with admission.acquire(owner=trajectory_id, prompt_hash=prompt_hash, prompt_tokens=prompt_tokens, completion_tokens=max_tokens):
            cache_preparation = prepare_prompt_family(base_client, prompt_hash)
            result = base_client.complete_raw(
                prompt=prompt, seed=seed, max_tokens=max_tokens,
                temperature=1.08, top_p=0.98, min_p=0.01, xtc_probability=0.35,
                stop=("\nMANUSCRIPT", "\nEDITORIAL", "\n```"),
            )
        raw_path = root / "s01-trajectories" / "raw" / f"{trajectory_id}.txt"
        atomic_write_text(raw_path, result.content)
        trajectory = result.content.strip()
        critic_prompt = trajectory_critic_prompt(cell, trajectory)
        judged = critic_client.complete(
            messages=[{"role": "user", "content": critic_prompt}],
            seed=seed ^ 0x71A9, max_tokens=650, temperature=0.2,
            top_p=0.9, min_p=0.0, response_format={"type": "json_object"},
        )
        judgment = parse_trajectory_critic(judged.content)
        record = {
            "record_type": "BaseSceneTrajectory", "version": VERSION,
            "trajectory_id": trajectory_id, "status": "completed",
            "campaign_hash": campaign["campaign_hash"], "seed": seed,
            "text": trajectory, "text_hash": sha256_text(trajectory),
            "raw_path": str(raw_path), "raw_hash": sha256_text(result.content),
            "prompt_hash": prompt_hash, "judgment": judgment,
            "selection_score": judgment["mean_score"],
            "eligible": not judgment.get("hard_reject"), "completed_at": _now(),
        }
        append_jsonl(path, record)
        append_jsonl(calls, {**call, "status": "completed", "raw_hash": record["raw_hash"], "cache_preparation": cache_preparation, "completed_at": record["completed_at"]})
        produced += 1
    records = list(_latest(path, "trajectory_id").values())
    selected = boltzmann_select(records, count=select_count, seed=int(campaign["campaign_hash"][:8], 16))
    lock = {
        "record_type": "LockedBaseSceneTrajectories", "version": VERSION,
        "campaign_hash": campaign["campaign_hash"],
        "selection_method": "best-plus-seeded-boltzmann-no-compilation",
        "trajectories": [{
            "trajectory_id": item["trajectory_id"], "text": item["text"],
            "text_hash": item["text_hash"], "raw_hash": item["raw_hash"],
            "selection_score": item["selection_score"],
        } for item in selected],
    }
    lock["lock_hash"] = hash_json(lock)
    write_json(root / "s01-trajectories" / "locked.v1.json", lock)
    return {"new": produced, "selected": [item["trajectory_id"] for item in selected], "lock_hash": lock["lock_hash"]}


def _candidate_novelty(segment: str, prior_segments: Sequence[str]) -> float:
    tokens = set(_words(segment))
    if not tokens or not prior_segments:
        return 1.0
    overlap = max(len(tokens & set(_words(item))) / max(1, len(tokens | set(_words(item)))) for item in prior_segments)
    return 1.0 - overlap


def run_branch_loom(
    *,
    campaign_dir: str | Path,
    base_client: LlamaClient,
    critic_client: LlamaClient,
    admission: SharedEndpointAdmission,
    cell_id: str,
    recipe_id: str = "",
    branches_per_parent: int = 6,
    survivors: int = 2,
    movement_min_words: int = 250,
    movement_max_words: int = 450,
    max_tokens: int = 760,
    seed: int = 1_250_001,
    trajectory_id: str = "",
    prefix_candidate_id: str = "",
    prefix_campaign_dir: str | Path = "",
    start_movement: int = 1,
    movement_local_sources: bool = False,
    movement_excerpt_sources: bool = False,
    stop_after_movements: int = 0,
    max_resample_pools: int = 3,
) -> dict[str, Any]:
    root = Path(campaign_dir)
    campaign, _, cells, passages, graphs = _load_campaign(root)
    project_root = Path(campaign["project_root"])
    cell = next((item for item in cells if item.cell_id == cell_id), None)
    if cell is None:
        raise ValueError(f"unknown loom cell: {cell_id}")
    movement_schedule = movements_for_cell(cell)
    movement_count = len(movement_schedule)
    if not 1 <= start_movement <= movement_count:
        raise ValueError(f"start_movement must be within 1..{movement_count}")
    if not 0 <= stop_after_movements <= movement_count:
        raise ValueError(f"stop_after_movements must be within 0..{movement_count}")
    if not 1 <= max_resample_pools <= 3:
        raise ValueError("max_resample_pools must be within 1..3")
    sampler_decision = (
        _read_json(root / "sampler" / "promotion.v1.json")
        if (root / "sampler" / "promotion.v1.json").is_file() else None
    )
    bootstrap_promotion = (
        _read_json(root / "bootstrap" / "promotion.v1.json")
        if (root / "bootstrap" / "promotion.v1.json").is_file() else None
    )
    selected_id = recipe_id or (
        bootstrap_promotion["derived_recipe"]["recipe_id"]
        if bootstrap_promotion and bootstrap_promotion.get("admitted")
        else sampler_decision["selected_recipe_id"] if sampler_decision else ""
    )
    if not selected_id:
        raise ValueError("loom requires --recipe before sampler promotion")
    recipe_records = (
        _read_json(root / "sampler" / "recipes.v1.json")["recipes"]
        if (root / "sampler" / "recipes.v1.json").is_file()
        else campaign.get("recipes", ())
    )
    raw_recipe = next((item for item in recipe_records if item["recipe_id"] == selected_id), None)
    if raw_recipe is None and bootstrap_promotion and bootstrap_promotion["derived_recipe"]["recipe_id"] == selected_id:
        raw_recipe = bootstrap_promotion["derived_recipe"]
    if raw_recipe is None:
        raise ValueError(f"selected sampler recipe not found: {selected_id}")
    recipe = PromptRecipeV4(**{
        **{key: value for key, value in raw_recipe.items() if key not in {"recipe_hash", "sampler"}},
        "sampler": SamplerV4(**raw_recipe["sampler"]),
    })
    if movement_local_sources and movement_excerpt_sources:
        raise ValueError("choose one movement source mutation")
    if movement_local_sources or movement_excerpt_sources:
        source_order = (
            "movement-local-excerpt" if movement_excerpt_sources else "movement-local"
        )
        recipe = PromptRecipeV4(
            recipe_id=recipe.recipe_id + "." + source_order,
            topology=recipe.topology, context_tokens=recipe.context_tokens,
            source_count=recipe.source_count, source_order=source_order,
            graph_granularity=recipe.graph_granularity,
            target_density=recipe.target_density, runway_type=recipe.runway_type,
            encoding=recipe.encoding, sampler=recipe.sampler,
            parent_recipe_hash=recipe.recipe_hash, mutated_axis="source_order",
        )
        validate_recipe_mutation(PromptRecipeV4(**{
            **{key: value for key, value in raw_recipe.items() if key not in {"recipe_hash", "sampler"}},
            "sampler": SamplerV4(**raw_recipe["sampler"]),
        }), recipe)
    runway = _load_locked_runways(root)[cell_id]
    trajectory = ""
    selected_trajectory_id = ""
    if cell_id == "fulcrum-s01":
        trajectory_path = root / "s01-trajectories" / "locked.v1.json"
        if trajectory_path.is_file():
            locked_trajectories = _read_json(trajectory_path)["trajectories"]
            selected = next((item for item in locked_trajectories if item["trajectory_id"] == trajectory_id), None) if trajectory_id else None
            if selected is None:
                selected = locked_trajectories[seed % len(locked_trajectories)]
            trajectory = selected["text"]
            selected_trajectory_id = selected["trajectory_id"]
        elif trajectory_id:
            raise ValueError("trajectory ID supplied before any S01 trajectory set was locked")
    self_demonstrations = tuple(
        item["text"] for item in (bootstrap_promotion or {}).get("admitted", ())
    ) if recipe.topology == "source-plus-self-demo" else ()
    source_docs = {item.passage_id: item.text for item in passages}
    anti_copy = AntiCopyIndex(source_docs)
    loom_root = root / "loom" / cell_id
    recipe_lock_path = loom_root / "recipe.v1.json"
    recipe_lock = {
        "record_type": "LoomPromptRecipe", "version": VERSION,
        "campaign_hash": campaign["campaign_hash"], **recipe.public_dict(),
    }
    if recipe_lock_path.is_file() and _read_json(recipe_lock_path) != recipe_lock:
        raise ValueError("loom recipe changed after manuscript generation began")
    write_json(recipe_lock_path, recipe_lock)
    calls = loom_root / "calls.jsonl"
    branches_path = loom_root / "branches.jsonl"
    assemblies_dir = loom_root / "assemblies"
    completed_branches = _latest(branches_path, "branch_id")
    starting_source_ids = tuple(runway.get("source_ids", ()))
    prefix_campaign_hash = campaign["campaign_hash"]
    if prefix_candidate_id:
        prefix: dict[str, Any] | None = None
        prefix_assembly: ManuscriptAssembly | None = None
        prefix_root = Path(prefix_campaign_dir) if prefix_campaign_dir else root
        prefix_campaign = _read_json(prefix_root / "campaign_manifest.v1.json")
        prefix_campaign_hash = str(prefix_campaign["campaign_hash"])
        if prefix_campaign.get("project_root") != campaign.get("project_root"):
            raise ValueError("prefix campaign uses a different project root")
        for phase in ("topology", "behavioral", "context", "sampler", "bootstrap"):
            candidate_path = prefix_root / phase / "candidates.jsonl"
            if candidate_path.is_file():
                prefix = _latest(candidate_path, "candidate_id").get(prefix_candidate_id)
                if prefix:
                    break
        # The branch loom is resumable at every exact manuscript boundary.
        # A selected branch is therefore a legitimate prefix provided its raw
        # model spans reconstruct the manuscript byte-for-byte.
        prefix_branches_path = prefix_root / "loom" / cell_id / "branches.jsonl"
        if prefix is None and prefix_branches_path.is_file():
            prefix = _latest(prefix_branches_path, "branch_id").get(prefix_candidate_id)
            if prefix:
                prefix_assembly = ManuscriptAssembly(
                    artifact_id=prefix_candidate_id,
                    spans=tuple(ModelSpan(**item) for item in prefix["spans"]),
                    separators=tuple(prefix["separators"]),
                    manuscript_hash=str(prefix["text_hash"]),
                )
        if prefix is None:
            raise ValueError(f"unknown prefix candidate: {prefix_candidate_id}")
        if prefix.get("cell_id") != cell_id:
            raise ValueError("prefix candidate belongs to another cell")
        overlap = anti_copy.check(prefix_candidate_id, prefix["text"]).to_dict()
        if not hard_gate(cell, prefix["text"], overlap)["passed"]:
            raise ValueError("prefix candidate fails current hard gates")
        if prefix_assembly is None:
            assembly_path = project_root / prefix["assembly_path"]
            assembly_value = _read_json(assembly_path)
            prefix_assembly = ManuscriptAssembly(
                artifact_id=assembly_value["artifact_id"],
                spans=tuple(ModelSpan(**item) for item in assembly_value["spans"]),
                separators=tuple(assembly_value["separators"]),
                manuscript_hash=assembly_value["manuscript_hash"],
            )
        assembly = prefix_assembly
        if assembly.reconstruct(project_root) != prefix["text"]:
            raise ValueError("prefix candidate assembly does not reconstruct")
        if not str(prefix["text"]).startswith(str(runway["text"])):
            raise ValueError("prefix candidate does not extend the locked runway")
        parents = [{
            "branch_id": prefix_candidate_id, "text": prefix["text"],
            "spans": [asdict(item) for item in assembly.spans],
            "separators": list(assembly.separators), "depth": start_movement - 1,
            "prefix_campaign_hash": prefix_campaign_hash,
        }]
        starting_source_ids = tuple(prefix.get("source_ids", starting_source_ids))
    else:
        initial_spans = _runway_model_spans(runway)
        parents = [{
            "branch_id": f"{cell_id}.root", "text": runway["text"],
            "spans": [asdict(item) for item in initial_spans],
            "separators": list(_runway_separators(runway)), "depth": 0,
        }]
    scheduled = movement_schedule[start_movement - 1:]
    if stop_after_movements:
        scheduled = scheduled[:stop_after_movements]
    completed_through_movement = ""
    for depth, (movement_id, movement) in enumerate(scheduled, start_movement):
        local_min_words, local_max_words = movement_word_band(
            cell, movement_id, movement_min_words, movement_max_words,
        )
        source_override = (
            () if recipe.source_order in {"movement-local", "movement-local-excerpt"}
            else starting_source_ids
        )
        movement_passages = generation_source_passages(
            recipe=recipe, cell=cell, passages=passages, graphs=graphs,
            movement=movement, source_ids_override=source_override,
        )
        prompt_graphs = dict(graphs)
        source_graph_hashes: dict[str, str] = {}
        if (
            recipe.source_order == "movement-local-excerpt"
            and recipe.topology in {"parallel-book", "graph-prose", "dwell-paired"}
        ):
            excerpt_graphs, source_graph_hashes = ensure_excerpt_graph_annotations(
                cache_root=loom_root / "apprenticeship",
                movement_id=movement_id, movement=movement,
                passages=movement_passages, critic=critic_client,
            )
            prompt_graphs.update(excerpt_graphs)
        selected: tuple[Mapping[str, Any], ...] = ()
        # A failed movement is evidence about this draw, not permission for a
        # critic to rewrite it.  Backtrack to the exact prior manuscript
        # boundary and make at most two fresh, seed-distinct pools.
        for resample_attempt in range(max_resample_pools):
            pool: list[dict[str, Any]] = []
            for parent_index, parent in enumerate(parents):
                prior_segments: list[str] = []
                for branch_index in range(branches_per_parent):
                    branch_seed = (
                        seed + depth * 10_000 + resample_attempt * 100_000
                        + parent_index * 1_000 + branch_index * 17
                    )
                    branch_id = (
                        f"{cell_id}.{movement_id}.r{resample_attempt}."
                        f"{parent_index}.{branch_seed}"
                    )
                    prompt, source_ids = render_generation_prompt(
                        recipe=recipe, cell=cell, passages=passages, graphs=prompt_graphs,
                        runway=parent["text"], movement=movement,
                        trajectory=trajectory,
                        self_demonstrations=self_demonstrations,
                        # The locked runway's sources remain the default stable
                        # apprenticeship.  A declared movement-local recipe is
                        # the one exception: its experimental axis is precisely
                        # retrieving exemplars for this dramatic payment.
                        source_ids_override=source_override,
                        selected_passages_override=movement_passages,
                    )
                    prompt_hash = sha256_text(prompt)
                    prompt_tokens = base_client.token_count(prompt)
                    request_hash = _generation_request_hash(
                        campaign_hash=campaign["campaign_hash"], prompt_hash=prompt_hash,
                        model=base_client.model, seed=branch_seed,
                        max_tokens=max_tokens, sampler=asdict(recipe.sampler),
                        source_ids=source_ids,
                        generation_contract={
                            "extraction_version": EXTRACTION_VERSION,
                            "movement_gate_version": MOVEMENT_GATE_VERSION,
                            "movement_id": movement_id,
                            "movement_text_hash": sha256_text(movement),
                            "movement_word_band": [local_min_words, local_max_words],
                            "source_graph_hashes": source_graph_hashes,
                            "prefix_campaign_hash": prefix_campaign_hash,
                            "prefix_candidate_id": prefix_candidate_id,
                        },
                    )
                    if branch_id in completed_branches:
                        _assert_resumable_request(
                            completed_branches[branch_id], request_hash, branch_id,
                        )
                        pool.append(dict(completed_branches[branch_id]))
                        prior_segments.append(str(completed_branches[branch_id].get("segment", "")))
                        continue
                    prompt_path = loom_root / "prompts" / movement_id / f"{branch_id}.txt"
                    atomic_write_text(prompt_path, prompt)
                    raw_path = loom_root / "raw" / movement_id / f"{branch_id}.txt"
                    call = {
                        "record_type": "V4ModelCall", "call_id": branch_id, "status": "started",
                        "model": base_client.model, "runtime": _endpoint_runtime_provenance(base_client),
                        "prompt_hash": prompt_hash, "prompt_path": str(prompt_path),
                        "prompt_tokens": prompt_tokens,
                        "seed": branch_seed, "sampler": asdict(recipe.sampler),
                        "max_tokens": max_tokens, "request_hash": request_hash,
                        "movement_word_band": [local_min_words, local_max_words],
                        "started_at": _now(),
                    }
                    append_jsonl(calls, call)
                    parts: list[str] = []

                    def on_delta(delta: str) -> None:
                        parts.append(delta)
                        match = anti_copy.first_exact_match(parent["text"] + "".join(parts))
                        if match:
                            raise SourceOverlapError(match)

                    stream_abort: Mapping[str, Any] | None = None
                    try:
                        with admission.acquire(owner=branch_id, prompt_hash=prompt_hash, prompt_tokens=prompt_tokens, completion_tokens=max_tokens):
                            cache_preparation = prepare_prompt_family(base_client, prompt_hash)
                            result = base_client.stream_raw(
                                prompt=prompt, seed=branch_seed, max_tokens=max_tokens,
                                temperature=recipe.sampler.temperature, top_p=recipe.sampler.top_p,
                                min_p=recipe.sampler.min_p, xtc_probability=recipe.sampler.xtc_probability,
                                extra=recipe.sampler.raw_extra(), on_delta=on_delta, stop=MANUSCRIPT_STOP,
                            )
                        raw_content = result.content
                        finish_reason = result.finish_reason
                        usage = result.usage
                        timings = result.timings
                    except SourceOverlapError as exc:
                        raw_content = "".join(parts)
                        finish_reason = "streaming_source_overlap_abort"
                        usage, timings = {}, {}
                        stream_abort = exc.match
                    atomic_write_text(raw_path, raw_content)
                    try:
                        if stream_abort is not None:
                            raise ValueError("streaming source-overlap abort")
                        segment, start, end = _complete_paragraph_prefix(
                            raw_content, local_min_words, local_max_words
                        )
                        full_text = parent["text"] + "\n\n" + segment
                        overlap = anti_copy.check(
                            branch_id, full_text,
                            prior_candidates={
                                f"sibling.{index}": value
                                for index, value in enumerate(prior_segments)
                            },
                        ).to_dict()
                        mechanical = hard_gate(cell, full_text, overlap)
                        stage_gate = movement_gate(cell, segment, movement)
                        mechanical["movement_gate"] = stage_gate
                        mechanical["passed"] = bool(mechanical.get("passed") and stage_gate["passed"])
                    except ValueError as exc:
                        segment, start, end, full_text = "", 0, 0, parent["text"]
                        overlap = ({"hard_fail": True, "stream_match": stream_abort}
                                   if stream_abort is not None else {})
                        mechanical = {
                            "version": HARD_GATE_VERSION, "passed": False,
                            "error": str(exc),
                        }
                    judgment: dict[str, Any] = {}
                    if mechanical.get("passed"):
                        critic_prompt = literary_critic_prompt(
                            cell, parent["text"], segment, movement,
                        )
                        try:
                            critic_result = critic_client.complete(
                                messages=[{"role": "user", "content": critic_prompt}],
                                seed=branch_seed ^ 0x5A17, max_tokens=700,
                                temperature=0.2, top_p=0.9, min_p=0.0,
                                response_format={"type": "json_object"},
                            )
                            judgment = parse_critic(critic_result.content, segment)
                        except (ValueError, RuntimeError) as exc:
                            judgment = {"hard_reject": True, "critic_error": str(exc)}
                    novelty = _candidate_novelty(segment, prior_segments)
                    selection_score = float(judgment.get("mean_score", 0.0)) + 0.6 * novelty
                    span = ModelSpan(
                        span_id=f"{branch_id}.span", call_id=branch_id,
                        raw_path=_relative(raw_path, project_root), raw_hash=sha256_text(raw_content),
                        raw_char_start=start, raw_char_end=end, text_hash=sha256_text(segment),
                        role=movement_id,
                    )
                    record = {
                        "record_type": "LoomBranch", "version": VERSION,
                        "branch_id": branch_id, "candidate_id": branch_id, "status": "completed",
                        "campaign_hash": campaign["campaign_hash"], "cell_id": cell_id,
                        "prefix_campaign_hash": prefix_campaign_hash,
                        "prefix_candidate_id": prefix_candidate_id,
                        "recipe_id": recipe.recipe_id, "recipe_hash": recipe.recipe_hash,
                        "trajectory_id": selected_trajectory_id,
                        "depth": depth, "movement_id": movement_id,
                        "parent_id": parent["branch_id"], "seed": branch_seed,
                        "resample_attempt": resample_attempt, "source_ids": list(source_ids),
                        "source_graph_hashes": source_graph_hashes,
                        "segment": segment, "segment_hash": sha256_text(segment),
                        "text": full_text, "text_hash": sha256_text(full_text),
                        "spans": [*parent["spans"], asdict(span)],
                        "separators": [*parent["separators"], "\n\n"],
                        "mechanical": mechanical, "overlap": overlap, "judgment": judgment,
                        "novelty": novelty, "selection_score": selection_score,
                        "eligible": bool(mechanical.get("passed") and judgment and not judgment.get("hard_reject")),
                        "prompt_hash": prompt_hash, "raw_hash": sha256_text(raw_content),
                        "request_hash": request_hash,
                        "raw_path": _relative(raw_path, project_root),
                        "finish_reason": finish_reason, "usage": usage, "timings": timings,
                        "max_tokens": max_tokens, "extraction_version": EXTRACTION_VERSION,
                        "movement_word_band": [local_min_words, local_max_words],
                        "completed_at": _now(),
                    }
                    append_jsonl(branches_path, record)
                    append_jsonl(calls, {
                        **call, "status": "completed", "raw_hash": record["raw_hash"],
                        "finish_reason": finish_reason, "completed_at": record["completed_at"],
                    })
                    pool.append(record)
                    prior_segments.append(segment)
            selected = boltzmann_select(
                pool, count=survivors,
                seed=seed + depth * 97 + resample_attempt * 10_007,
            )
            write_json(loom_root / "selections" / f"{depth:02d}-{movement_id}-r{resample_attempt}.json", {
                "record_type": "LoomBranchSelection", "version": VERSION,
                "movement_id": movement_id, "resample_attempt": resample_attempt,
                "selection_seed": seed + depth * 97 + resample_attempt * 10_007,
                "method": "best-plus-seeded-boltzmann-quality-novelty",
                "selected": [item["branch_id"] for item in selected],
                "pool": [{"branch_id": item["branch_id"], "score": item["selection_score"], "eligible": item["eligible"]} for item in pool],
            })
            if selected:
                break
        if not selected:
            raise RuntimeError(
                f"no eligible branches survived movement {movement_id} after three pools"
            )
        parents = [dict(item) for item in selected]
        completed_through_movement = movement_id
    finalists: list[dict[str, Any]] = []
    for parent in parents:
        spans = tuple(
            span if span.call_ledger_path and span.call_record_hash
            else _bind_span_to_call(span, calls, project_root)
            for span in (ModelSpan(**item) for item in parent["spans"])
        )
        assembly = ManuscriptAssembly(parent["branch_id"], spans, tuple(parent["separators"]), parent["text_hash"])
        assembly_path = assemblies_dir / f"{parent['branch_id']}.json"
        _write_verified_assembly(assembly_path, assembly, project_root)
        verified = verify_assembly(
            assembly_path, project_root, require_call_ledger=True,
        )
        finalists.append({
            "candidate_id": parent["branch_id"], "text": parent["text"],
            "text_hash": parent["text_hash"], "word_count": len(_words(parent["text"])),
            "assembly_path": _relative(assembly_path, project_root),
            "assembly_verified": verified["verified"], "selection_score": parent["selection_score"],
        })
    payload = {
        "record_type": "LoomFinalists", "version": VERSION,
        "campaign_hash": campaign["campaign_hash"], "cell_id": cell_id,
        "recipe_id": recipe.recipe_id, "finalists": finalists, "created_at": _now(),
        "trajectory_id": selected_trajectory_id,
        "completed_through_movement": completed_through_movement,
        "complete_story": bool(
            completed_through_movement == movement_schedule[-1][0]
        ),
    }
    payload["finalist_set_hash"] = hash_json({key: value for key, value in payload.items() if key != "created_at"})
    write_json(loom_root / "finalists.v1.json", payload)
    return payload


def render_movement_audition_prompt(
    *, cell: BenchmarkCell, manuscript: str, movement: str,
    exemplars: Sequence[SourcePassage] = (),
    graphs: Mapping[str, IntimacySceneGraph] | None = None,
) -> str:
    """Render a direct base-model audition for a difficult causal boundary.

    The prompt's final bytes are exact Gemma manuscript prose.  Earlier audition
    versions ended on a control heading; the base model sometimes continued the
    scaffold rather than the story.  Control now precedes the manuscript and the
    next-token distribution sees an ordinary prose boundary.  Any admitted text
    remains an exact raw Gemma span; the harness never supplies an opening sentence
    or repairs the response.
    """

    graph_map = dict(graphs or {})
    manuscript_head, manuscript_tail = split_manuscript_runway(
        manuscript, maximum_tail_words=90,
    )
    examples = []
    for number, item in enumerate(reversed(tuple(exemplars)), 1):
        graph = graph_map.get(item.passage_id)
        if graph is None:
            examples.append(
                f"Example {number}: a complete prose movement\n{item.text.strip()}"
            )
        else:
            examples.append(
                f"Example {number}\n\nDramatic design\n{dwell_map(graph)}"
                f"\n\nProse movement\n{item.text.strip()}"
            )
    chunks = [
        "MOVEMENT APPRENTICESHIP",
        *examples,
        (
            "FULCRUM\n\n"
            + _movement_canon_page(cell, movement).replace(
                "; this chapter contains their first mutually chosen kiss", ""
            )
            + "\n\n"
            + _generation_continuity_page(cell, manuscript)
            + "\n\nEarlier pages\n"
            + manuscript_head.strip()
            + "\n\nExact dramatic payment for the audition\n"
            + movement.strip()
            + "\n\n* * *\n\n"
            + manuscript_tail.strip()
        ),
    ]
    prompt = "\n\n* * *\n\n".join(chunks)
    if not prompt.endswith(manuscript_tail.strip()):
        raise AssertionError("movement audition prompt must end on exact manuscript")
    return prompt


def movement_boundary_spark_gate(
    cell: BenchmarkCell, paragraph: str, movement: str,
) -> dict[str, Any]:
    """Admit a partial Gemma paragraph that breaks a local prose attractor."""

    defects: list[str] = []
    word_count = len(_words(paragraph))
    lower_movement = movement.casefold()
    calibration_setup = (
        cell.cell_id == "fulcrum-s01" and "calibration frame" in lower_movement
    )
    calibration_choice = (
        cell.cell_id == "fulcrum-s01"
        and "privately selects exactly one" in lower_movement
    )
    livia_entrance = (
        cell.cell_id == "fulcrum-s01"
        and "livia enters the room after mara has hidden her choice" in lower_movement
    )
    if not (calibration_setup or calibration_choice or livia_entrance) and not 12 <= word_count <= 90:
        defects.append("spark_word_band")
    if cell.cell_id == "fulcrum-s01" and "unnamed guests" in lower_movement:
        has_people = bool(re.search(
            r"\b(?:voices?|guests?|people|others|arrivals?|new arrivals?)\b",
            paragraph, re.I,
        ))
        has_arrival = bool(re.search(
            r"\b(?:reach|reached|arriv|entered|entering|came in|come in|"
            r"walked in|stepped in|doorway|door opened)\w*\b",
            paragraph, re.I,
        ))
        if not (has_people and has_arrival):
            defects.append("spark_missing_gathering_arrival")
        if re.search(r"\b(?:Adrian|Livia)\b", paragraph, re.I):
            defects.append("spark_introduces_locked_character")
    elif cell.cell_id == "fulcrum-s01" and "half-full glass" in lower_movement:
        has_glass = bool(re.search(r"\b(?:glass|cup|flute)\b", paragraph, re.I))
        has_deposit = bool(re.search(
            r"\b(?:left|set|put|placed|abandon\w*)\b", paragraph, re.I,
        ))
        has_actor = bool(re.search(
            r"\b(?:young|younger|brown-haired)\s+(?:fellow|man|guest)\b",
            paragraph, re.I,
        ))
        if not (has_glass and has_deposit and has_actor):
            defects.append("spark_missing_glass_deposit")
        if re.search(r"\b(?:Adrian|Livia)\b", paragraph, re.I):
            defects.append("spark_introduces_locked_character")
        if re.search(
            r"\b(?:worker|waiter|server|footman|cater\w*)\b.{0,160}"
            r"\b(?:retriev|collect|clear|lift|carry|carried|took)\w*\b",
            paragraph, re.I | re.S,
        ):
            defects.append("spark_pays_later_retrieval")
    elif cell.cell_id == "fulcrum-s01" and "calibration frame" in lower_movement:
        # This stage is deliberately mined at a larger granularity than the
        # arrival/deposit sparks: a coherent offer includes the apparatus,
        # the rule, and the participant's live ability to decline.
        if not 100 <= word_count <= 220:
            defects.append("spark_word_band")
        if not re.search(r"\bAdrian\b", paragraph, re.I):
            defects.append("spark_missing_adrian")
        object_count = sum(
            bool(re.search(rf"\b{name}\b", paragraph, re.I))
            for name in ("key", "stone", "token")
        )
        if object_count < 2:
            defects.append("spark_missing_choice_objects")
        if not re.search(r"\b(?:choose|play|decline|stop)\w*\b", paragraph, re.I):
            defects.append("spark_missing_choice_offer")
        if re.search(r"\bLivia\b", paragraph, re.I):
            defects.append("spark_runs_into_reader")
    elif calibration_choice:
        if not 50 <= word_count <= 220:
            defects.append("spark_word_band")
        if not re.search(
            r"\b(?:choose|chooses|chose|select|selected|pick|picked|"
            r"placed one of the three)\w*\b",
            paragraph,
            re.I,
        ):
            defects.append("spark_missing_private_choice")
        if not re.search(
            r"\b(?:key|stone|token|one of (?:the )?three|object)\b",
            paragraph,
            re.I,
        ):
            defects.append("spark_missing_choice_object")
        if re.search(
            r"\b(?:reader|Livia)\b.{0,120}\b(?:enter|entered|arriv|guess|guessed)\w*\b",
            paragraph,
            re.I | re.S,
        ):
            defects.append("spark_runs_into_reading")
        if re.search(
            r"\bJonah\b.{0,120}\b(?:choose|choice|which one|should you take)\b",
            paragraph,
            re.I | re.S,
        ):
            defects.append("spark_runs_into_reader_prompt")
    elif livia_entrance:
        if not 80 <= word_count <= 220:
            defects.append("spark_word_band")
        if not re.search(r"\bLivia\b", paragraph, re.I):
            defects.append("spark_missing_livia")
        if not re.search(
            r"\b(?:enter|entered|arriv|appeared|came in|come in|"
            r"doorway|door opened|voice spoke)\w*\b",
            paragraph,
            re.I,
        ):
            defects.append("spark_missing_livia_arrival")
        if re.search(
            r"\bLivia\b.{0,220}\b(?:guess|read|identif|chose|chosen|"
            r"selected|picked)\w*\b",
            paragraph,
            re.I | re.S,
        ) and re.search(r"\b(?:key|stone|token)\b", paragraph, re.I):
            defects.append("spark_runs_into_identification")
    else:
        defects.append("unsupported_spark_movement")
    if any(marker.casefold() in paragraph.casefold() for marker in CONTROL_MARKERS):
        defects.append("packet_leakage")
    if re.search(
        r"(?im)^\s*(?:(?:the|a)\s+)?"
        r"(?:next|new|last|current|first|continued|continuing)?\s*"
        r"manuscript\s+(?:text|lines?|section|passage)\b.*$|"
        r"^\s*(?:first|second|third|final)\s+part\s*$|"
        r"^\s*[A-Za-z][A-Za-z -]{0,30}\s+script\s*$|"
        r"^\s*Fulcrum glossary(?:\s+for\s+this\s+scene)?\s*:\s*$|"
        r"^\s*End of excerpt\.?\s*$",
        paragraph,
    ):
        defects.append("packet_leakage")
    return {
        "version": "movement-boundary-spark-gate.v2-livia-entrance",
        "passed": not defects, "defects": defects, "word_count": word_count,
    }


def _exact_paragraph_spans(text: str) -> tuple[tuple[str, int, int], ...]:
    spans: list[tuple[str, int, int]] = []
    for match in re.finditer(
        r"(?:\A[ \t\r\n]*|\n\s*\n)([^\s].*?)(?=\n\s*\n|\Z)",
        text,
        re.S,
    ):
        start, end = match.start(1), match.end(1)
        while end > start and text[end - 1].isspace():
            end -= 1
        paragraph = text[start:end]
        if paragraph:
            spans.append((paragraph, start, end))
    return tuple(spans)


def _exact_paragraph_windows(
    text: str, *, maximum_paragraphs: int = 3,
) -> tuple[tuple[str, int, int], ...]:
    """Return exact one-to-N paragraph windows for causal-unit mining."""

    paragraphs = _exact_paragraph_spans(text)
    windows: list[tuple[str, int, int]] = []
    for start_index in range(len(paragraphs)):
        for stop_index in range(
            start_index,
            min(len(paragraphs), start_index + maximum_paragraphs),
        ):
            start = paragraphs[start_index][1]
            end = paragraphs[stop_index][2]
            windows.append((text[start:end], start, end))
    windows.sort(key=lambda item: (item[1], -item[2]))
    return tuple(windows)


def _exact_causal_windows(text: str) -> tuple[tuple[str, int, int], ...]:
    """Add sentence-ended prefixes without changing a single source byte."""

    candidates: dict[tuple[int, int], tuple[str, int, int]] = {}
    for window, start, end in _exact_paragraph_windows(text):
        candidates[(start, end)] = (window, start, end)
        for match in re.finditer(r"[.!?](?:[\"”’])?(?=\s|\Z)", window):
            sentence_end = start + match.end()
            if sentence_end < end:
                candidates[(start, sentence_end)] = (
                    text[start:sentence_end], start, sentence_end,
                )
    return tuple(
        candidates[key]
        for key in sorted(candidates, key=lambda item: (item[0], -item[1]))
    )


def mine_movement_boundary_sparks(
    *, campaign_dir: str | Path, source_campaign_dir: str | Path,
    cell_id: str, prefix_candidate_id: str, prefix_campaign_dir: str | Path,
    movement_number: int,
) -> dict[str, Any]:
    """Mine useful exact paragraphs from failed Gemma auditions.

    A failed full movement can still contain a strong causal boundary paragraph.
    This operation selects such spans byte-for-byte from preserved raw responses;
    it neither edits nor synthesizes manuscript language.
    """

    root = Path(campaign_dir)
    source_root = Path(source_campaign_dir)
    campaign, _, cells, passages, _ = _load_campaign(root)
    cell = next((item for item in cells if item.cell_id == cell_id), None)
    if cell is None:
        raise ValueError(f"unknown benchmark cell: {cell_id}")
    schedule = movements_for_cell(cell)
    if not 1 <= movement_number <= len(schedule):
        raise ValueError("movement_number is outside the cell schedule")
    movement_id, movement = schedule[movement_number - 1]
    prefix_root = Path(prefix_campaign_dir)
    prefix_campaign = _read_json(prefix_root / "campaign_manifest.v1.json")
    prefix = _latest(
        prefix_root / "loom" / cell_id / "branches.jsonl", "branch_id"
    ).get(prefix_candidate_id)
    if prefix is None:
        prefix = _latest(
            prefix_root / "loom" / cell_id / "boundary_sparks.jsonl", "spark_id"
        ).get(prefix_candidate_id)
    if prefix is None:
        raise ValueError(f"unknown prefix branch: {prefix_candidate_id}")
    project_root = Path(campaign["project_root"])
    assembly = ManuscriptAssembly(
        artifact_id=prefix_candidate_id,
        spans=tuple(ModelSpan(**item) for item in prefix["spans"]),
        separators=tuple(prefix["separators"]),
        manuscript_hash=str(prefix["text_hash"]),
    )
    if assembly.reconstruct(project_root) != prefix["text"]:
        raise ValueError("spark prefix assembly does not reconstruct")
    anti_copy = AntiCopyIndex({item.passage_id: item.text for item in passages})
    source_campaign = _read_json(source_root / "campaign_manifest.v1.json")
    source_records = _latest(
        source_root / "loom" / cell_id / "branches.jsonl", "branch_id"
    )
    output = root / "loom" / cell_id / "boundary_sparks.jsonl"
    completed = _latest(output, "spark_id")
    seen_text_hashes = {str(item.get("spark_text_hash", "")) for item in completed.values()}
    produced: list[str] = []
    for source_id, source in sorted(source_records.items()):
        raw_path = project_root / str(source["raw_path"])
        if not raw_path.is_file():
            raise ValueError(f"audition raw response is missing: {raw_path}")
        raw = raw_path.read_text(encoding="utf-8")
        if sha256_text(raw) != source["raw_hash"]:
            raise ValueError(f"audition raw hash mismatch: {source_id}")
        for paragraph, start, end in _exact_causal_windows(raw):
            gate = movement_boundary_spark_gate(cell, paragraph, movement)
            if not gate["passed"]:
                continue
            assembled_text = prefix["text"] + "\n\n" + paragraph
            overlap = anti_copy.check(
                f"spark.{source_id}.{start}-{end}", assembled_text,
            ).to_dict()
            full_gate = hard_gate(cell, assembled_text, overlap)
            if not full_gate["passed"]:
                continue
            text_hash = sha256_text(paragraph)
            if text_hash in seen_text_hashes:
                continue
            spark_id = f"{cell_id}.{movement_id}.spark.{source_id}.{start}-{end}"
            request_hash = hash_json({
                "record_type": "MinedMovementBoundarySparkRequest",
                "version": MOVEMENT_AUDITION_VERSION,
                "campaign_hash": campaign["campaign_hash"],
                "source_campaign_hash": source_campaign["campaign_hash"],
                "source_branch_request_hash": source["request_hash"],
                "source_raw_hash": source["raw_hash"],
                "raw_char_start": start, "raw_char_end": end,
                "spark_text_hash": text_hash,
                "prefix_campaign_hash": prefix_campaign["campaign_hash"],
                "prefix_candidate_id": prefix_candidate_id,
            })
            prior = completed.get(spark_id)
            if prior is not None:
                _assert_resumable_request(prior, request_hash, spark_id)
                continue
            span = ModelSpan(
                span_id=spark_id, call_id=source_id,
                raw_path=_relative(raw_path, project_root), raw_hash=source["raw_hash"],
                raw_char_start=start, raw_char_end=end, text_hash=text_hash,
                role=f"{movement_id}-boundary-spark",
            )
            text = assembled_text
            record = {
                "record_type": "MinedMovementBoundarySpark", "version": VERSION,
                "spark_id": spark_id, "branch_id": spark_id,
                "candidate_id": spark_id, "status": "completed",
                "campaign_hash": campaign["campaign_hash"], "cell_id": cell_id,
                "movement_id": movement_id, "partial_movement": True,
                "prefix_campaign_hash": prefix_campaign["campaign_hash"],
                "prefix_candidate_id": prefix_candidate_id,
                "source_campaign_hash": source_campaign["campaign_hash"],
                "source_branch_id": source_id, "source_raw_hash": source["raw_hash"],
                "spark_text": paragraph, "spark_text_hash": text_hash,
                "text": text, "text_hash": sha256_text(text),
                "spans": [*prefix["spans"], asdict(span)],
                "separators": [*prefix["separators"], "\n\n"],
                "gate": gate, "full_gate": full_gate, "overlap": overlap,
                "request_hash": request_hash,
                "raw_path": _relative(raw_path, project_root),
                "raw_char_start": start, "raw_char_end": end,
                "completed_at": _now(),
            }
            append_jsonl(output, record)
            completed[spark_id] = record
            seen_text_hashes.add(text_hash)
            produced.append(spark_id)
    return {
        "new": len(produced), "movement_id": movement_id,
        "spark_ids": sorted(completed), "new_spark_ids": produced,
    }


def sample_movement_auditions(
    *,
    campaign_dir: str | Path,
    base_client: LlamaClient,
    critic_client: LlamaClient,
    admission: SharedEndpointAdmission,
    cell_id: str,
    prefix_candidate_id: str,
    prefix_campaign_dir: str | Path,
    movement_number: int,
    seeds: Sequence[int],
    max_tokens: int = 300,
    source_count: int = 1,
    background_source_count: int = 0,
    paired_examples: bool = False,
    matched_source_ids: Sequence[str] = (),
    sampler: SamplerV4 | None = None,
) -> dict[str, Any]:
    """Sample exact Gemma prose at a stubborn manuscript boundary.

    This is not an editor.  It is a high-entropy base-model audition whose only
    deterministic transformations are complete-paragraph extraction, validation,
    provenance assembly, and ranking.  The output is stored as ordinary loom
    branches so a successful audition can become the next immutable prefix.
    """

    root = Path(campaign_dir)
    campaign, _, cells, passages, graphs = _load_campaign(root)
    cell = next((item for item in cells if item.cell_id == cell_id), None)
    if cell is None:
        raise ValueError(f"unknown benchmark cell: {cell_id}")
    schedule = movements_for_cell(cell)
    if not 1 <= movement_number <= len(schedule):
        raise ValueError("movement_number is outside the cell schedule")
    movement_id, movement = schedule[movement_number - 1]
    minimum_words, maximum_words = movement_word_band(cell, movement_id, 250, 450)
    config = sampler or SamplerV4(
        temperature=0.98, top_p=0.98, min_p=0.02, xtc_probability=0.20,
    )

    prefix_root = Path(prefix_campaign_dir)
    prefix_campaign = _read_json(prefix_root / "campaign_manifest.v1.json")
    if prefix_campaign.get("project_root") != campaign.get("project_root"):
        raise ValueError("prefix campaign uses a different project root")
    prefix_records = _latest(
        prefix_root / "loom" / cell_id / "branches.jsonl", "branch_id"
    )
    prefix = prefix_records.get(prefix_candidate_id)
    if prefix is None:
        prefix = _latest(
            prefix_root / "loom" / cell_id / "boundary_sparks.jsonl", "spark_id"
        ).get(prefix_candidate_id)
    if prefix is None:
        raise ValueError(f"unknown prefix branch: {prefix_candidate_id}")
    project_root = Path(campaign["project_root"])
    prefix_assembly = ManuscriptAssembly(
        artifact_id=prefix_candidate_id,
        spans=tuple(ModelSpan(**item) for item in prefix["spans"]),
        separators=tuple(prefix["separators"]),
        manuscript_hash=str(prefix["text_hash"]),
    )
    if prefix_assembly.reconstruct(project_root) != prefix["text"]:
        raise ValueError("prefix audition manuscript does not reconstruct")

    source_docs = {item.passage_id: item.text for item in passages}
    anti_copy = AntiCopyIndex(source_docs)
    if not hard_gate(
        cell, prefix["text"], anti_copy.check(prefix_candidate_id, prefix["text"]).to_dict()
    )["passed"]:
        raise ValueError("prefix audition manuscript fails current hard gates")
    base_recipe = next(item for item in initial_recipes() if item.recipe_id == "v4-anthology")
    audition_recipe = PromptRecipeV4(
        recipe_id="v4-movement-audition",
        topology=base_recipe.topology,
        context_tokens=base_recipe.context_tokens,
        source_count=max(0, source_count), source_order="movement-local-excerpt",
        graph_granularity=base_recipe.graph_granularity,
        target_density=base_recipe.target_density,
        runway_type=base_recipe.runway_type, encoding=base_recipe.encoding,
        sampler=config, parent_recipe_hash=base_recipe.recipe_hash,
        mutated_axis="source_order",
    )
    requested_source_ids = tuple(dict.fromkeys(matched_source_ids))
    if requested_source_ids:
        source_count = len(requested_source_ids)
    matched_exemplars = (
        generation_source_passages(
            recipe=audition_recipe, cell=cell, passages=passages, graphs=graphs,
            movement=movement, source_ids_override=requested_source_ids,
        )[:source_count]
        if source_count else ()
    )
    background = retrieve_passages_for_movement(
        cell, passages, movement=movement, count=background_source_count,
        graphs=graphs,
    ) if background_source_count else ()
    matched_ids = {item.passage_id for item in matched_exemplars}
    # render_movement_audition_prompt reverses this sequence, so the first
    # matched exemplar becomes the final and most predictive apprenticeship
    # block immediately before the target book.
    exemplars = tuple(matched_exemplars) + tuple(
        item for item in background if item.passage_id not in matched_ids
    )
    prompt_graphs: dict[str, IntimacySceneGraph] = {}
    source_graph_hashes: dict[str, str] = {}
    if paired_examples:
        exact_graphs, exact_hashes = ensure_excerpt_graph_annotations(
            cache_root=root / "loom" / cell_id / "apprenticeship",
            movement_id=movement_id, movement=movement,
            passages=matched_exemplars, critic=critic_client,
        )
        prompt_graphs.update(exact_graphs)
        source_graph_hashes.update(exact_hashes)
        for item in background:
            graph = graphs.get(item.passage_id)
            if graph is not None:
                prompt_graphs[item.passage_id] = graph
                source_graph_hashes[item.passage_id] = graph.graph_hash
    prompt = render_movement_audition_prompt(
        cell=cell, manuscript=prefix["text"], movement=movement,
        exemplars=exemplars, graphs=prompt_graphs,
    )
    prompt_hash = sha256_text(prompt)
    prompt_tokens = base_client.token_count(prompt)
    loom_root = root / "loom" / cell_id
    calls_path = loom_root / "audition_calls.jsonl"
    branches_path = loom_root / "branches.jsonl"
    completed = _latest(branches_path, "branch_id")
    produced = 0
    records: list[dict[str, Any]] = []
    prior_segments: list[str] = []
    for seed in seeds:
        branch_id = f"{cell_id}.{movement_id}.audition.{seed}"
        request_hash = _generation_request_hash(
            campaign_hash=campaign["campaign_hash"], prompt_hash=prompt_hash,
            model=base_client.model, seed=seed, max_tokens=max_tokens,
            sampler=asdict(config),
            source_ids=tuple(item.passage_id for item in exemplars),
            generation_contract={
                "audition_version": MOVEMENT_AUDITION_VERSION,
                "movement_id": movement_id,
                "movement_hash": sha256_text(movement),
                "movement_word_band": [minimum_words, maximum_words],
                "paired_examples": paired_examples,
                "matched_source_ids": list(requested_source_ids),
                "source_graph_hashes": source_graph_hashes,
                "prefix_campaign_hash": prefix_campaign["campaign_hash"],
                "prefix_candidate_id": prefix_candidate_id,
            },
        )
        prior = completed.get(branch_id)
        if prior is not None:
            _assert_resumable_request(prior, request_hash, branch_id)
            records.append(dict(prior))
            prior_segments.append(str(prior.get("segment", "")))
            continue
        prompt_path = loom_root / "prompts" / movement_id / f"{branch_id}.txt"
        raw_path = loom_root / "raw" / movement_id / f"{branch_id}.txt"
        atomic_write_text(prompt_path, prompt)
        started = {
            "record_type": "V4ModelCall", "version": VERSION,
            "call_id": branch_id, "status": "started", "model": base_client.model,
            "runtime": _endpoint_runtime_provenance(base_client),
            "prompt_hash": prompt_hash, "prompt_path": str(prompt_path),
            "prompt_tokens": prompt_tokens, "seed": seed,
            "sampler": asdict(config), "max_tokens": max_tokens,
            "request_hash": request_hash, "started_at": _now(),
        }
        append_jsonl(calls_path, started)
        parts: list[str] = []
        stream_abort: Mapping[str, Any] | None = None
        try:
            def on_delta(delta: str) -> None:
                parts.append(delta)
                match = anti_copy.first_exact_match(prefix["text"] + "".join(parts))
                if match:
                    raise SourceOverlapError(match)

            with admission.acquire(
                owner=branch_id, prompt_hash=prompt_hash,
                prompt_tokens=prompt_tokens, completion_tokens=max_tokens,
            ):
                prepare_prompt_family(base_client, prompt_hash)
                result = base_client.stream_raw(
                    prompt=prompt, seed=seed, max_tokens=max_tokens,
                    temperature=config.temperature, top_p=config.top_p,
                    min_p=config.min_p, xtc_probability=config.xtc_probability,
                    extra=config.raw_extra(), on_delta=on_delta, stop=MANUSCRIPT_STOP,
                )
            raw_content = result.content
            finish_reason, usage, timings = result.finish_reason, result.usage, result.timings
        except SourceOverlapError as exc:
            raw_content = "".join(parts)
            finish_reason, usage, timings = "streaming_source_overlap_abort", {}, {}
            stream_abort = exc.match
        atomic_write_text(raw_path, raw_content)
        try:
            if stream_abort is not None:
                raise ValueError("streaming source-overlap abort")
            segment, start, end = _complete_paragraph_prefix(
                raw_content, minimum_words, maximum_words,
            )
            text = prefix["text"] + "\n\n" + segment
            overlap = anti_copy.check(
                branch_id, text,
                prior_candidates={
                    f"sibling.{index}": value
                    for index, value in enumerate(prior_segments)
                },
            ).to_dict()
            mechanical = hard_gate(cell, text, overlap)
            stage_gate = movement_gate(cell, segment, movement)
            mechanical["movement_gate"] = stage_gate
            mechanical["passed"] = bool(mechanical["passed"] and stage_gate["passed"])
        except ValueError as exc:
            segment, start, end, text = "", 0, 0, prefix["text"]
            overlap = ({"hard_fail": True, "stream_match": stream_abort}
                       if stream_abort is not None else {})
            mechanical = {"version": HARD_GATE_VERSION, "passed": False, "error": str(exc)}
        judgment: dict[str, Any] = {}
        if mechanical.get("passed"):
            try:
                critic_result = critic_client.complete(
                    messages=[{"role": "user", "content": literary_critic_prompt(
                        cell, prefix["text"], segment, movement,
                    )}],
                    seed=seed ^ 0x5A17, max_tokens=700, temperature=0.2,
                    top_p=0.9, min_p=0.0,
                    response_format={"type": "json_object"},
                )
                judgment = parse_critic(critic_result.content, segment)
            except (ValueError, RuntimeError) as exc:
                judgment = {"hard_reject": True, "critic_error": str(exc)}
        novelty = _candidate_novelty(segment, prior_segments)
        selection_score = float(judgment.get("mean_score", 0.0)) + 0.6 * novelty
        span = ModelSpan(
            span_id=f"{branch_id}.span", call_id=branch_id,
            raw_path=_relative(raw_path, project_root), raw_hash=sha256_text(raw_content),
            raw_char_start=start, raw_char_end=end, text_hash=sha256_text(segment),
            role=movement_id,
        )
        record = {
            "record_type": "LoomBranch", "version": VERSION,
            "branch_id": branch_id, "candidate_id": branch_id,
            "status": "completed", "campaign_hash": campaign["campaign_hash"],
            "cell_id": cell_id, "prefix_campaign_hash": prefix_campaign["campaign_hash"],
            "prefix_candidate_id": prefix_candidate_id,
            "recipe_id": audition_recipe.recipe_id,
            "recipe_hash": audition_recipe.recipe_hash,
            "depth": movement_number, "movement_id": movement_id,
            "parent_id": prefix_candidate_id, "seed": seed,
            "source_ids": [item.passage_id for item in exemplars],
            "source_graph_hashes": source_graph_hashes,
            "segment": segment, "segment_hash": sha256_text(segment),
            "text": text, "text_hash": sha256_text(text),
            "spans": [*prefix["spans"], asdict(span)],
            "separators": [*prefix["separators"], "\n\n"],
            "mechanical": mechanical, "overlap": overlap, "judgment": judgment,
            "novelty": novelty, "selection_score": selection_score,
            "eligible": bool(mechanical.get("passed") and judgment and not judgment.get("hard_reject")),
            "prompt_hash": prompt_hash, "raw_hash": sha256_text(raw_content),
            "request_hash": request_hash, "raw_path": _relative(raw_path, project_root),
            "finish_reason": finish_reason, "usage": usage, "timings": timings,
            "max_tokens": max_tokens, "extraction_version": EXTRACTION_VERSION,
            "movement_word_band": [minimum_words, maximum_words],
            "audition_version": MOVEMENT_AUDITION_VERSION,
            "completed_at": _now(),
        }
        append_jsonl(branches_path, record)
        append_jsonl(calls_path, {
            **started, "status": "completed", "raw_hash": record["raw_hash"],
            "finish_reason": finish_reason, "completed_at": record["completed_at"],
        })
        completed[branch_id] = record
        records.append(record)
        prior_segments.append(segment)
        produced += 1
    selected = boltzmann_select(records, count=min(2, len(records)), seed=seeds[0] ^ 0xA0D17)
    selection = {
        "record_type": "MovementAuditionSelection", "version": VERSION,
        "audition_version": MOVEMENT_AUDITION_VERSION,
        "campaign_hash": campaign["campaign_hash"], "cell_id": cell_id,
        "movement_id": movement_id, "prefix_candidate_id": prefix_candidate_id,
        "selected": [item["branch_id"] for item in selected],
        "pool": [
            {"branch_id": item["branch_id"], "eligible": item["eligible"],
             "score": item["selection_score"]}
            for item in records
        ],
    }
    selection["selection_hash"] = hash_json(selection)
    write_json(loom_root / "selections" / f"audition-{movement_number:02d}-{movement_id}.json", selection)
    return {
        "new": produced, "movement_id": movement_id,
        "eligible": [item["branch_id"] for item in records if item.get("eligible")],
        "selected": selection["selected"], "selection_hash": selection["selection_hash"],
    }


def readmit_movement_audition(
    *, campaign_dir: str | Path, source_campaign_dir: str | Path,
    prefix_campaign_dir: str | Path, cell_id: str, source_branch_id: str,
    movement_number: int, critic_client: LlamaClient,
) -> dict[str, Any]:
    """Re-evaluate one immutable Gemma span under the current gates.

    Gate bugs must not force a model to regenerate already-good prose, and old
    audit records must never be rewritten to pretend the bug did not happen.
    This operation verifies the old raw response and complete assembly, then
    writes a new hash-linked admission decision containing no new manuscript
    bytes.  The critic remains read-only.
    """

    root = Path(campaign_dir)
    source_root = Path(source_campaign_dir)
    prefix_root = Path(prefix_campaign_dir)
    campaign, _, cells, passages, _ = _load_campaign(root)
    source_campaign = _read_json(source_root / "campaign_manifest.v1.json")
    prefix_campaign = _read_json(prefix_root / "campaign_manifest.v1.json")
    if source_campaign.get("project_root") != campaign.get("project_root"):
        raise ValueError("source campaign uses a different project root")
    if prefix_campaign.get("project_root") != campaign.get("project_root"):
        raise ValueError("prefix campaign uses a different project root")
    cell = next((item for item in cells if item.cell_id == cell_id), None)
    if cell is None:
        raise ValueError(f"unknown benchmark cell: {cell_id}")
    schedule = movements_for_cell(cell)
    if not 1 <= movement_number <= len(schedule):
        raise ValueError("movement_number is outside the cell schedule")
    movement_id, movement = schedule[movement_number - 1]
    source = _latest(
        source_root / "loom" / cell_id / "branches.jsonl", "branch_id"
    ).get(source_branch_id)
    if source is None:
        raise ValueError(f"unknown source audition branch: {source_branch_id}")
    if source.get("movement_id") != movement_id:
        raise ValueError("source branch belongs to another movement")
    prefix_id = str(source.get("prefix_candidate_id", ""))
    prefix = _latest(
        prefix_root / "loom" / cell_id / "branches.jsonl", "branch_id"
    ).get(prefix_id)
    if prefix is None:
        prefix = _latest(
            prefix_root / "loom" / cell_id / "boundary_sparks.jsonl", "spark_id"
        ).get(prefix_id)
    if prefix is None:
        raise ValueError(f"source prefix is unavailable: {prefix_id}")
    if source.get("prefix_campaign_hash") != prefix_campaign.get("campaign_hash"):
        raise ValueError("source branch prefix campaign hash mismatch")

    project_root = Path(campaign["project_root"])
    source_assembly = ManuscriptAssembly(
        artifact_id=source_branch_id,
        spans=tuple(ModelSpan(**item) for item in source["spans"]),
        separators=tuple(source["separators"]),
        manuscript_hash=str(source["text_hash"]),
    )
    if source_assembly.reconstruct(project_root) != source["text"]:
        raise ValueError("source audition assembly does not reconstruct")
    if not source["spans"]:
        raise ValueError("source audition has no model spans")
    last_span = ModelSpan(**source["spans"][-1])
    raw_path = project_root / last_span.raw_path
    raw = raw_path.read_text(encoding="utf-8")
    if sha256_text(raw) != last_span.raw_hash:
        raise ValueError("source audition raw response hash mismatch")
    segment = raw[last_span.raw_char_start:last_span.raw_char_end]
    if sha256_text(segment) != last_span.text_hash or segment != source["segment"]:
        raise ValueError("source audition span does not match its raw response")

    anti_copy = AntiCopyIndex({item.passage_id: item.text for item in passages})
    overlap = anti_copy.check(source_branch_id, source["text"]).to_dict()
    mechanical = hard_gate(cell, source["text"], overlap)
    stage_gate = movement_gate(cell, segment, movement)
    mechanical["movement_gate"] = stage_gate
    mechanical["passed"] = bool(mechanical["passed"] and stage_gate["passed"])
    branch_id = f"{source_branch_id}.readmit.{HARD_GATE_VERSION}"
    request_hash = hash_json({
        "record_type": "MovementAuditionReadmissionRequest",
        "version": VERSION, "campaign_hash": campaign["campaign_hash"],
        "source_campaign_hash": source_campaign["campaign_hash"],
        "source_branch_request_hash": source["request_hash"],
        "prefix_campaign_hash": prefix_campaign["campaign_hash"],
        "prefix_candidate_id": prefix_id, "movement_id": movement_id,
        "hard_gate_version": HARD_GATE_VERSION,
        "movement_gate_version": MOVEMENT_GATE_VERSION,
        "critic_model": critic_client.model,
    })
    branches_path = root / "loom" / cell_id / "branches.jsonl"
    prior = _latest(branches_path, "branch_id").get(branch_id)
    if prior is not None:
        _assert_resumable_request(prior, request_hash, branch_id)
        return dict(prior)

    judgment: dict[str, Any] = {}
    critic_prompt = literary_critic_prompt(cell, prefix["text"], segment, movement)
    critic_prompt_path = root / "loom" / cell_id / "readmissions" / f"{branch_id}.critic.txt"
    critic_raw_path = root / "loom" / cell_id / "readmissions" / f"{branch_id}.critic.json"
    atomic_write_text(critic_prompt_path, critic_prompt)
    if mechanical["passed"]:
        result = critic_client.complete(
            messages=[{"role": "user", "content": critic_prompt}],
            seed=int(sha256_text(branch_id)[:8], 16), max_tokens=700,
            temperature=0.2, top_p=0.9, min_p=0.0,
            response_format={"type": "json_object"},
        )
        atomic_write_text(critic_raw_path, result.content)
        judgment = parse_critic(result.content, segment)
    novelty = 1.0
    record = {
        **dict(source),
        "record_type": "LoomBranchReadmission", "version": VERSION,
        "branch_id": branch_id, "candidate_id": branch_id,
        "campaign_hash": campaign["campaign_hash"],
        "source_campaign_hash": source_campaign["campaign_hash"],
        "source_branch_id": source_branch_id,
        "source_branch_request_hash": source["request_hash"],
        "readmission_only": True, "manuscript_bytes_added": 0,
        "mechanical": mechanical, "overlap": overlap, "judgment": judgment,
        "novelty": novelty,
        "selection_score": float(judgment.get("mean_score", 0.0)) + 0.6,
        "eligible": bool(
            mechanical["passed"] and judgment and not judgment.get("hard_reject")
        ),
        "critic_prompt_hash": sha256_text(critic_prompt),
        "critic_prompt_path": str(critic_prompt_path),
        "critic_raw_path": str(critic_raw_path) if mechanical["passed"] else "",
        "request_hash": request_hash, "completed_at": _now(),
    }
    append_jsonl(branches_path, record)
    return record


def package_finalists(
    *, campaign_dir: str | Path, output_dir: str | Path,
    cell_id: str, maximum: int = 6,
) -> dict[str, Any]:
    root = Path(campaign_dir)
    output = Path(output_dir)
    campaign = _read_json(root / "campaign_manifest.v1.json")
    expected_tree = str(campaign.get("executable_source_tree_hash", ""))
    if not expected_tree:
        raise ValueError("official packaging requires a source-tree-bound campaign")
    if _source_tree_fingerprint(campaign["project_root"])["tree_hash"] != expected_tree:
        raise ValueError("campaign executable source tree changed before packaging")
    payload = _read_json(root / "loom" / cell_id / "finalists.v1.json")
    expected_set_hash = hash_json({
        key: value for key, value in payload.items()
        if key not in {"created_at", "finalist_set_hash"}
    })
    if payload.get("finalist_set_hash") != expected_set_hash:
        raise ValueError("finalist set hash does not match its contents")
    candidates = sorted(payload["finalists"], key=lambda item: (-float(item["selection_score"]), item["candidate_id"]))[:maximum]
    if not candidates:
        raise ValueError("cannot package an empty finalist set")
    project_root = Path(campaign["project_root"])
    branch_records = _latest(
        root / "loom" / cell_id / "branches.jsonl", "candidate_id",
    )
    verified_candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for item in candidates:
        candidate_id = str(item["candidate_id"])
        branch = branch_records.get(candidate_id)
        if branch is None:
            raise ValueError(f"finalist lacks generating branch record: {candidate_id}")
        if not branch.get("eligible") or not branch.get("mechanical", {}).get("passed"):
            raise ValueError(f"finalist branch is not mechanically eligible: {candidate_id}")
        judgment = branch.get("judgment")
        if not isinstance(judgment, Mapping) or judgment.get("hard_reject"):
            raise ValueError(f"finalist branch lacks an accepted critic record: {candidate_id}")
        assembly_path = project_root / str(item["assembly_path"])
        value = _read_json(assembly_path)
        assembly = ManuscriptAssembly(
            artifact_id=value["artifact_id"],
            spans=tuple(ModelSpan(**span) for span in value["spans"]),
            separators=tuple(value["separators"]),
            manuscript_hash=value["manuscript_hash"],
        )
        if assembly.artifact_id != candidate_id:
            raise ValueError("finalist assembly identity mismatch")
        text = assembly.reconstruct(project_root)
        if text != item["text"] or sha256_text(text) != item["text_hash"]:
            raise ValueError("finalist text differs from verified assembly")
        for span in assembly.spans:
            span.verify_call(project_root)
            _verify_span_replay(span, project_root)
        authorship = _assembly_authorship(assembly, text)
        verified_candidates.append((dict(item), authorship))
    rng = random.Random(int(payload["finalist_set_hash"][:8], 16))
    labels = [chr(ord("A") + index) for index in range(len(verified_candidates))]
    rng.shuffle(labels)
    reader = []
    reveal: dict[str, Any] = {}
    attestations: dict[str, Any] = {}
    for label, (item, authorship) in zip(labels, verified_candidates):
        reader.append({"label": label, "text": item["text"], "word_count": item["word_count"]})
        reveal[label] = {key: value for key, value in item.items() if key != "text"}
        attestations[item["candidate_id"]] = authorship
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "reader_packet.json", {
        "packet_id": sha256_text(payload["finalist_set_hash"] + ":reader")[:16],
        "instructions": "Read the raw scenes blind. Rate prose freshness, romantic pull, coherence, character fascination, and desire to continue from 1-7; quote the strongest and weakest passage.",
        "candidates": reader,
    })
    write_json(output.parent / "reveal_key.json", {"finalist_set_hash": payload["finalist_set_hash"], "labels": reveal})
    write_json(output.parent / "internal" / "artifact_authorship.v2.json", {
        "record_type": "FinalistAuthorshipBundle",
        "schema_version": ARTIFACT_AUTHORSHIP_VERSION,
        "finalist_set_hash": payload["finalist_set_hash"],
        "artifacts": attestations,
    })
    markdown = ["# Blind raw-fiction review", ""]
    for item in reader:
        markdown.extend((f"## Candidate {item['label']}", "", item["text"], ""))
    atomic_write_text(output / "reader_packet.md", "\n".join(markdown))
    return {"output": str(output), "candidate_count": len(reader), "labels": sorted(labels)}
