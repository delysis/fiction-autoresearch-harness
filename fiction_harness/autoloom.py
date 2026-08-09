"""Entropy-preserving base-model autoloom for short fiction calibration.

The loom treats a base model as a continuation engine, not an instruction
follower.  Story-shape proposals and prose are sampled separately.  No
instruction model is allowed to normalize proposals before drafting.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import random
import re
import time
from typing import Any, Mapping, Sequence

from .anti_copy import AntiCopyIndex, AntiCopyPolicy, SourceOverlapError
from .apprenticeship import render_retrieved_archive
from .autoresearch import (
    BenchmarkCell,
    IntimacySceneGraph,
    SourcePassage,
    _candidate_gate,
    _graph_for,
    default_benchmarks,
    extract_gabaldon_examples,
)
from .core import atomic_write_text, canonical_json_text, hash_file, hash_json, sha256_text, write_json
from .evaluation import cadence_family_diagnostics
from .model_client import LlamaClient
from .shared_endpoint import SharedEndpointAdmission


AUTOLOOM_VERSION = "base-autoloom.v25"
SCENE_SENTINEL = "<END_SCENE>"
PROGRAM_SEEDS = (941_003, 941_041, 941_083)
PROSE_SEEDS = (942_007, 942_053, 942_101, 942_151)
TRAJECTORY_SEEDS = tuple(943_001 + 37 * index for index in range(12))
TRAJECTORY_STAGES = (
    {"stage": "approach", "probe_tokens": 300, "target_words": [160, 230], "survivors": 4},
    {"stage": "transaction", "probe_tokens": 1050, "target_words": [420, 560], "survivors": 1},
    {"stage": "aftermath", "probe_tokens": 300, "target_words": [100, 170], "survivors": 1},
)
TRANSACTION_PLAN_SEEDS = (944_011, 944_083)
TRANSACTION_PLAN_FIELDS = (
    "OFFER",
    "COUNTEROFFER",
    "CONSENT TURN",
    "BODY LOGIC",
    "SENSORY ASYMMETRY",
    "DISCLOSURE",
    "PLOT PAYMENT",
    "ENDING STATE",
)
PROGRAM_SAMPLING = {
    "temperature": 1.15,
    "top_p": 0.98,
    "min_p": 0.01,
    "xtc_probability": 0.12,
    "extra": {
        "dynatemp_range": 0.20,
        "dynatemp_exponent": 1.0,
        "dry_multiplier": 0.55,
        "dry_base": 1.75,
        "dry_allowed_length": 3,
        "dry_penalty_last_n": 1024,
    },
}
PROSE_SAMPLING = {
    "temperature": 0.92,
    "top_p": 0.97,
    "min_p": 0.02,
    "xtc_probability": 0.08,
    "extra": {
        "repeat_penalty": 1.02,
        "dynatemp_range": 0.16,
        "dynatemp_exponent": 1.0,
        "dry_multiplier": 0.80,
        "dry_base": 1.75,
        "dry_allowed_length": 3,
        "dry_penalty_last_n": 2048,
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.write(json.dumps(dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        __import__("os").fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _completed(path: Path, key: str) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    if not path.is_file():
        return found
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if item.get("status") == "completed":
            found[str(item[key])] = item
    return found


def _terminal_call_ids(path: Path, key: str) -> set[str]:
    """Return IDs whose latest durable ledger state is completed or failed."""

    latest: dict[str, str] = {}
    if not path.is_file():
        return set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if key in item:
            latest[str(item[key])] = str(item.get("status", ""))
    return {item_id for item_id, status in latest.items() if status in {"completed", "failed"}}


@dataclass(frozen=True, slots=True)
class LoomProgram:
    program_id: str
    cell_id: str
    pressure_engine: str
    offer: str
    counteroffer: str
    embodied_engine: str
    mode_engine: str
    reversal: str
    image_system: str
    ending_motion: str
    raw_proposal_hash: str
    proposal_seed: int

    @property
    def program_hash(self) -> str:
        return hash_json(asdict(self))


@dataclass(frozen=True, slots=True)
class ModeEngine:
    engine_id: str
    cell_id: str
    attention_offer: str
    consent_sequence: str
    physical_sequence: str
    plot_coupling: str
    aftermath: str
    image_anchor: str
    raw_proposal_hash: str
    proposal_seed: int

    @property
    def engine_hash(self) -> str:
        return hash_json(asdict(self))


@dataclass(frozen=True, slots=True)
class TransactionProgram:
    transaction_id: str
    parent_id: str
    offer: str
    counteroffer: str
    consent_turn: str
    body_logic: str
    sensory_asymmetry: str
    disclosure: str
    plot_payment: str
    ending_state: str
    raw_proposal_hash: str
    proposal_seed: int

    @property
    def transaction_hash(self) -> str:
        return hash_json(asdict(self))


@dataclass(frozen=True, slots=True)
class LoomRecipe:
    recipe_id: str
    topology: str
    description: str
    source_pairs: int
    include_bridge: bool
    include_graphs: bool
    include_raw_prose: bool
    include_program: bool = True
    encoding: str = "documentary"

    @property
    def recipe_hash(self) -> str:
        return hash_json(asdict(self))


def loom_recipes() -> tuple[LoomRecipe, ...]:
    return (
        LoomRecipe("loom-form-doc", "form-only", "Length-matched project form demonstration.", 0, True, False, False),
        LoomRecipe("loom-spice-doc", "raw-spice-form", "Mode-matched spicy prose followed by the project form bridge.", 3, True, False, True),
        LoomRecipe("loom-paired-doc", "graph-prose-form", "Content graphs paired with their finished scenes, then the bridge.", 4, True, True, True),
        LoomRecipe("loom-dense-doc", "dense-apprenticeship", "Eight graph-to-prose pairs plus the nearest project bridge.", 8, True, True, True),
        LoomRecipe(
            "loom-activated-doc", "full-apprenticeship",
            "All eligible positive craft pairs, three project heat bridges, and a target-adjacent mode activation.",
            99, True, True, True,
        ),
        LoomRecipe(
            "loom-runway-doc", "naturalistic-runway",
            "Two raw explicit exemplars, one project bridge, a compact weave, and an in-scene prose runway.",
            3, True, False, True,
        ),
        LoomRecipe(
            "loom-source-nearest-doc", "source-nearest-runway",
            "Project bridge followed by a mode-matched author scene immediately before the target manuscript.",
            1, True, False, True,
        ),
    )


PROGRAM_FIELDS = (
    "PRESSURE ENGINE",
    "OFFER",
    "COUNTEROFFER",
    "EMBODIED ENGINE",
    "MODE ENGINE",
    "REVERSAL",
    "IMAGE SYSTEM",
    "ENDING MOTION",
)


def render_program_prompt(cell: BenchmarkCell) -> str:
    return (
        "STORY LOOM ARCHIVE\n\n"
        "ARCHIVED CASE: customs interview / estranged sisters / no romance\n"
        "PROPOSAL A\n"
        "PRESSURE ENGINE: Their dead father's mechanical watch is ticking again inside the evidence bag, and only one sister knows it was broken before his death.\n"
        "OFFER: The elder sister deliberately mistranslates the officer's question, giving the younger ten seconds to choose a story.\n"
        "COUNTEROFFER: The younger corrects the translation and includes one fact that makes them both look guilty.\n"
        "EMBODIED ENGINE: Each lie makes the watch migrate across the metal table as the officer's thumb nudges the bag.\n"
        "MODE ENGINE: No erotic charge; physical attention remains evidentiary and familial.\n"
        "REVERSAL: The humiliating truth that divides the sisters is also the only account that clears them of the larger crime.\n"
        "IMAGE SYSTEM: Green customs glass, a second hand with no face, two wet passport photographs.\n"
        "ENDING MOTION: The officer returns one passport; the sisters must decide who walks out first.\n"
        "END PROPOSAL\n\n"
        "ARCHIVED CASE: married spies / reconciliation / explicit intimacy\n"
        "PROPOSAL B\n"
        "PRESSURE ENGINE: A microdot is glued beneath the wedding ring he removed during capture; recovering it requires her to decide whether the ring means evidence, betrayal, or marriage.\n"
        "OFFER: He places the ring in her palm and gives her the solvent, making both the secret and first touch hers to initiate.\n"
        "COUNTEROFFER: She retrieves the microdot, then slides the damaged ring onto his finger rather than accepting it back.\n"
        "EMBODIED ENGINE: Solvent, scar tissue, and the tight metal band make every movement physically exact.\n"
        "MODE ENGINE: Married explicit intimacy advances by visible permissions: mouth and hands first, then chosen penetration; each transition exposes a withheld fact, and orgasm commits neither partner to premature forgiveness.\n"
        "REVERSAL: The intimate act that seems to forgive him instead commits him to disclose the name encoded on the microdot.\n"
        "IMAGE SYSTEM: Bitter orange solvent, a pale ring-mark, mirrored letters on translucent film.\n"
        "ENDING MOTION: Still joined, they turn the bedside lamp through the film and read the name together.\n"
        "END PROPOSAL\n\n"
        "ARCHIVED CASE: chapel fundraiser / forbidden attraction / chosen restraint\n"
        "PROPOSAL C\n"
        "PRESSURE ENGINE: The donation counter jams while they are alone, trapping his cuff and scattering consecration cards across the floor as the building alarm counts down.\n"
        "OFFER: She frees the cuff one thread at a time, close enough to feel him choose stillness instead of converting accident into permission.\n"
        "COUNTEROFFER: She asks for one deliberate touch after the necessity ends, then names when it must stop.\n"
        "EMBODIED ENGINE: Torn linen, pulse under a loosened cuff, and the alarm's red flashes turn timing into mutual action.\n"
        "MODE ENGINE: One deliberate kiss intensifies through reciprocal choices and stops while both still want more; stopping makes the later trust possible.\n"
        "REVERSAL: Stopping does not cool the attraction; it lets her entrust him with the envelope that could expose the pastor.\n"
        "IMAGE SYSTEM: Gold paper caught in black gears, one white thread, red light across bare wrist.\n"
        "ENDING MOTION: They leave by separate doors carrying halves of the same torn card.\n"
        "END PROPOSAL\n\n"
        "NEW ARCHIVE CASE: four-draw set\n"
        f"MODE: {cell.intimacy_mode}\nHEAT BAND: {cell.heat_band}\n"
        f"OPENING SENTENCE (literal target anchor): {cell.opening_fragment}\n"
        "LOCKED EVENTS:\n- " + "\n- ".join(cell.story_program) + "\n"
        "INVARIANTS:\n- " + "\n- ".join(cell.hard_constraints) + "\n"
        f"DISTRIBUTION NOTE: Four causally different mechanisms; every proposal continues the literal opening and keeps its named people and charged object active; behavior before explanation; MODE ENGINE concretely realizes {cell.heat_band}; no larger-plot resolution.\n\n"
        "PROPOSAL 1\n"
    )


MODE_FIELDS = (
    "ATTENTION OFFER",
    "CONSENT SEQUENCE",
    "PHYSICAL SEQUENCE",
    "PLOT COUPLING",
    "AFTERMATH",
    "IMAGE ANCHOR",
)


def render_mode_prompt(cell: BenchmarkCell) -> str:
    if cell.heat_band == "explicit":
        archive = (
            "ARCHIVED ENGINE A: married anger / explicit / truth remains costly\n"
            "ATTENTION OFFER: She places his hand at her waist while naming the decision she has not forgiven.\n"
            "CONSENT SEQUENCE: Invitation to kiss; a fresh yes before undressing; a pause before oral touch; still-yes before penetration; either may stop without relational punishment.\n"
            "PHYSICAL SEQUENCE: Angry kiss -> alternating shirt buttons -> mouth on breast -> her hand around his cock while she questions him -> oral attention to her -> move to bed -> slow chosen penetration -> mutually responsive climax.\n"
            "PLOT COUPLING: Each escalation earns one operational disclosure; penetration begins only after he agrees that tomorrow's dangerous decision belongs to both of them.\n"
            "AFTERMATH: Anger and danger remain; they open the evidence together rather than treating orgasm as absolution.\n"
            "IMAGE ANCHOR: A brass key warms in her palm and remains visible beside the bed.\n"
            "END ENGINE\n\n"
            "ARCHIVED ENGINE B: playful married reunion / explicit / competence attraction\n"
            "ATTENTION OFFER: He asks her to demonstrate the knot that saved the rigging; she uses his body as the line and makes him follow instructions.\n"
            "CONSENT SEQUENCE: Teasing proposal -> spoken yes -> she controls pace and position -> check-in after a tender scar is exposed -> reciprocal choice to continue.\n"
            "PHYSICAL SEQUENCE: Rope-guided hand placement -> kiss interrupted by laughter -> clothes removed as part of the demonstration -> manual stimulation -> she straddles him -> penetration paced by her -> climax changes the joke into a vow to act.\n"
            "PLOT COUPLING: Her embodied competence proves his rescue account incomplete and determines which route they take at dawn.\n"
            "AFTERMATH: They annotate the map while still naked, disagreement transformed into a joint experiment rather than erased.\n"
            "IMAGE ANCHOR: Salt-stiff rope leaves a temporary diagonal mark across clean sheets.\n"
            "END ENGINE\n\n"
            "ARCHIVED ENGINE C: married repair / explicit / responsibility preserved\n"
            "ATTENTION OFFER: She invites one deliberate touch after he visibly protects fragile work from their urgency.\n"
            "CONSENT SEQUENCE: She initiates; he asks at each changed act; she redirects once; he stops instantly; she actively resumes on different terms.\n"
            "PHYSICAL SEQUENCE: Thumb in mouth -> hard kiss -> breast and nipple attention -> her guided hand at clitoris -> she opens his trousers -> blanket on floor -> she lowers onto his cock -> rhythm adjusted around injury -> orgasm while maintaining eye contact.\n"
            "PLOT COUPLING: Their sexual responsiveness becomes evidence for a concrete rule against unilateral professional decisions.\n"
            "AFTERMATH: She writes the next decision in her own hand and gives him the phone to enact it with her.\n"
            "IMAGE ANCHOR: White rosin fingerprints cross his chest and remain afterward.\n"
            "END ENGINE\n\n"
        )
    elif cell.heat_band == "none":
        archive = (
            "ARCHIVED ENGINE A: institutional pressure / no erotic charge\n"
            "ATTENTION OFFER: Accurate tea and a warm chair make refusal socially expensive.\n"
            "CONSENT SEQUENCE: A professional request is narrowed, restated, timed, and made revocable.\n"
            "PHYSICAL SEQUENCE: Cup accepted -> notebook divided into observation and interpretation -> timer turned outward -> door opened.\n"
            "PLOT COUPLING: The coping move changes what the authority figure may quote and preserves uncertain evidence.\n"
            "AFTERMATH: Care remains real and controlling; no romance or erotic attention enters.\n"
            "IMAGE ANCHOR: A white card means insufficient evidence.\n"
            "END ENGINE\n\n"
        )
    else:
        archive = (
            "ARCHIVED ENGINE A: chosen restraint / desire remains active\n"
            "ATTENTION OFFER: An open hand is offered without interpretation; contact begins only when the other closes the distance.\n"
            "CONSENT SEQUENCE: Asked touch -> reciprocal kiss -> pause -> mutually chosen stopping while desire remains explicit.\n"
            "PHYSICAL SEQUENCE: Hand contact -> thumb across knuckle -> kiss deepens by small answers -> one partner breaks it -> the other does not follow.\n"
            "PLOT COUPLING: Restraint makes a future trust decision possible and yields evidence about character.\n"
            "AFTERMATH: Desire remains embodied; tomorrow belongs to the person who stopped.\n"
            "IMAGE ANCHOR: Wet rosemary and an unlit porch.\n"
            "END ENGINE\n\n"
        )
    return (
        "INTIMACY MODE LOOM ARCHIVE\n\n" + archive
        + "NEW MODE CASE: four-draw set\n"
        + f"MODE: {cell.intimacy_mode}\nHEAT BAND: {cell.heat_band}\n"
        + "LOCKED RELATIONSHIP EFFECTS:\n- " + "\n- ".join(cell.story_program[-2:]) + "\n"
        + "INVARIANTS:\n- " + "\n- ".join(cell.hard_constraints) + "\n"
        + "ENGINE 1\n"
    )


def parse_mode_engines(raw: str, cell: BenchmarkCell, seed: int) -> tuple[ModeEngine, ...]:
    field_union = "|".join(re.escape(field) for field in MODE_FIELDS)
    if re.match(rf"(?i)^\s*(?:{field_union})\s*:", raw):
        raw = "ENGINE 1\n" + raw
    starts = list(re.finditer(r"(?mi)^\s*ENGINE\s+(\d+)\s*$", raw))
    engines: list[ModeEngine] = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(raw)
        chunk = raw[match.end():end]
        # Base completions often preserve the field vocabulary while freely
        # reordering it.  Parse the labels in their *observed* order instead of
        # assuming the prompt's schema order; completeness remains strict.
        found: list[tuple[int, int, str]] = []
        for field in MODE_FIELDS:
            field_match = re.search(rf"(?mi)^\s*{re.escape(field)}\s*:\s*", chunk)
            if field_match:
                found.append((field_match.start(), field_match.end(), field))
        found.sort()
        engine_end = re.search(r"(?mi)^\s*END ENGINE(?:\s+\d+)?\s*$", chunk)
        final_boundary = engine_end.start() if engine_end else len(chunk)
        values: dict[str, str] = {}
        for field_index, (_, value_start, field) in enumerate(found):
            value_end = (
                found[field_index + 1][0]
                if field_index + 1 < len(found)
                else final_boundary
            )
            value = " ".join(chunk[value_start:value_end].strip().split())
            if value:
                values[field] = value
        if set(values) != set(MODE_FIELDS):
            continue
        engines.append(
            ModeEngine(
                engine_id=f"mode.{cell.cell_id}.{seed}.{match.group(1)}",
                cell_id=cell.cell_id,
                attention_offer=values["ATTENTION OFFER"],
                consent_sequence=values["CONSENT SEQUENCE"],
                physical_sequence=values["PHYSICAL SEQUENCE"],
                plot_coupling=values["PLOT COUPLING"],
                aftermath=values["AFTERMATH"],
                image_anchor=values["IMAGE ANCHOR"],
                raw_proposal_hash=sha256_text(raw),
                proposal_seed=seed,
            )
        )
    return tuple(engines)


def parse_program_proposals(raw: str, cell: BenchmarkCell, seed: int) -> tuple[LoomProgram, ...]:
    if re.match(r"(?i)^\s*PRESSURE ENGINE\s*:", raw):
        raw = "PROPOSAL 1\n" + raw
    starts = list(re.finditer(r"(?mi)^\s*PROPOSAL\s+(\d+)\s*$", raw))
    programs: list[LoomProgram] = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(raw)
        chunk = raw[match.end():end]
        found: list[tuple[int, int, str]] = []
        for field in PROGRAM_FIELDS:
            field_match = re.search(rf"(?mi)^\s*{re.escape(field)}\s*:\s*", chunk)
            if field_match:
                found.append((field_match.start(), field_match.end(), field))
        found.sort()
        proposal_end = re.search(r"(?mi)^\s*END PROPOSAL(?:\s+\d+)?\s*$", chunk)
        final_boundary = proposal_end.start() if proposal_end else len(chunk)
        values: dict[str, str] = {}
        for field_index, (_, value_start, field) in enumerate(found):
            value_end = found[field_index + 1][0] if field_index + 1 < len(found) else final_boundary
            value = " ".join(chunk[value_start:value_end].strip().split())
            if value:
                values[field] = value
        if set(values) != set(PROGRAM_FIELDS):
            continue
        number = match.group(1)
        programs.append(
            LoomProgram(
                program_id=f"{cell.cell_id}.{seed}.{number}",
                cell_id=cell.cell_id,
                pressure_engine=values["PRESSURE ENGINE"],
                offer=values["OFFER"],
                counteroffer=values["COUNTEROFFER"],
                embodied_engine=values["EMBODIED ENGINE"],
                mode_engine=values["MODE ENGINE"],
                reversal=values["REVERSAL"],
                image_system=values["IMAGE SYSTEM"],
                ending_motion=values["ENDING MOTION"],
                raw_proposal_hash=sha256_text(raw),
                proposal_seed=seed,
            )
        )
    return tuple(programs)


def program_compatible(program: LoomProgram, cell: BenchmarkCell) -> bool:
    text = canonical_json_text(asdict(program)).casefold()
    if cell.heat_band == "none" and re.search(
        r"\b(?:kiss|sexual|erotic|arousal|breast|nipple|groin|orgasm|undress)\w*\b",
        text,
    ):
        return False
    if cell.heat_band == "charged-restraint" and re.search(
        r"\b(?:penetrat|intercourse|orgasm|consummat|genitals?)\w*\b", text
    ):
        return False
    if cell.heat_band == "explicit":
        # The target starts on a recovered drive and broken seal.  A plan that
        # silently replaces those anchors is a different story, however vivid.
        if cell.cell_id == "married-explicit" and not (
            "drive" in text and "seal" in text and "esther" in text and "simon" in text
        ):
            return False
        if not re.search(
            r"\b(?:oral|mouth|naked|undress|breast|nipple|clitoris|cock|penis|"
            r"penetrat|inside|intercourse|orgasm|consummat|sexual)\w*\b",
            program.mode_engine,
            re.I,
        ):
            return False
        if not re.search(
            r"\b(?:ask|yes|choos|permission|consent|stop|pause|invite)\w*\b",
            program.mode_engine,
            re.I,
        ):
            return False
    if re.search(r"\b(?:ignores? (?:a |her |his )?no|cannot refuse|forces? (?:her|him))\b", text):
        return False
    if "ambiguous supernatural status" in cell.hard_constraints and re.search(
        r"\b(?:confirmed paranormal|proves? (?:the )?supernatural|literal magic)\b", text
    ):
        return False
    return True


def causal_program_compatible(program: LoomProgram, cell: BenchmarkCell) -> bool:
    """Validate the story loom without asking it to solve the intimacy loom."""

    text = canonical_json_text(asdict(program)).casefold()
    if cell.cell_id == "married-explicit" and not (
        "drive" in text and "seal" in text and "esther" in text and "simon" in text
    ):
        return False
    if re.search(r"\b(?:ignores? (?:a |her |his )?no|cannot refuse|forces? (?:her|him))\b", text):
        return False
    if "ambiguous supernatural status" in cell.hard_constraints and re.search(
        r"\b(?:confirmed paranormal|proves? (?:the )?supernatural|literal magic)\b", text
    ):
        return False
    return True


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z]{3,}", text.casefold()))


def _similarity(left: LoomProgram, right: LoomProgram) -> float:
    def content(item: LoomProgram) -> str:
        return " ".join(
            (
                item.pressure_engine,
                item.offer,
                item.counteroffer,
                item.embodied_engine,
                item.mode_engine,
                item.reversal,
                item.image_system,
                item.ending_motion,
            )
        )
    a = _tokens(content(left))
    b = _tokens(content(right))
    return len(a & b) / max(1, len(a | b))


def select_programs(programs: Sequence[LoomProgram], *, count: int, seed: int) -> tuple[LoomProgram, ...]:
    """Seeded novelty-weighted sampling without replacement.

    This is deliberately not a top-1 or temperature-zero selector.  Rarity
    changes the draw probabilities while preserving a real chance for every
    valid proposal.
    """

    unique: list[LoomProgram] = []
    for item in programs:
        if item.cell_id and all(_similarity(item, prior) < 0.90 for prior in unique):
            unique.append(item)
    if len(unique) < count:
        raise ValueError(f"need {count} distinct valid programs, found {len(unique)}")
    rng = random.Random(seed)
    pool = list(unique)
    chosen: list[LoomProgram] = []
    while pool and len(chosen) < count:
        weights = []
        for item in pool:
            nearest = max((_similarity(item, other) for other in pool if other is not item), default=0.0)
            distance_from_chosen = min((1.0 - _similarity(item, prior) for prior in chosen), default=1.0)
            weights.append(max(0.05, (1.05 - nearest) * (0.35 + distance_from_chosen)))
        pick = rng.choices(range(len(pool)), weights=weights, k=1)[0]
        chosen.append(pool.pop(pick))
    return tuple(chosen)


def _bridge_name(cell: BenchmarkCell) -> str:
    if cell.cell_id == "institutional-pressure-control":
        return "institutional-pressure.md"
    if cell.heat_band == "explicit":
        return "married-explicit-workshop.md"
    if cell.intimacy_mode == "married-intimacy":
        return "married-intimacy.md"
    return "charged-restraint.md"


def _matched_passages(cell: BenchmarkCell, passages: Sequence[SourcePassage], count: int) -> tuple[SourcePassage, ...]:
    eligible = [
        item
        for item in passages
        if item.prompt_eligible and "counterexample" not in item.intimacy_mode
    ]
    if cell.heat_band == "explicit":
        matched = [item for item in eligible if item.heat_band == "explicit"]
    elif cell.heat_band == "charged-restraint":
        matched = [item for item in eligible if item.heat_band == "charged-restraint"]
    elif cell.heat_band == "none":
        matched = []
    else:
        matched = [item for item in eligible if item.heat_band != "explicit"]
    return tuple(sorted(matched, key=lambda item: item.example_number)[:count])


def _scene_form(label: str, blueprint: str, prose: str, mode: str) -> str:
    return (
        f"SCENE FORM EXAMPLE: {label}\n"
        f"MODE: {mode}\n"
        f"APPROXIMATE LENGTH: {len(prose.split())} words\n"
        "SCENE BLUEPRINT:\n" + blueprint.strip() + "\n\n"
        "MANUSCRIPT\n" + prose.strip() + "\n" + SCENE_SENTINEL
    )


def _graph_document(graph: IntimacySceneGraph) -> str:
    return (
        f"Emotional offer: {graph.emotional_offer}\n"
        f"Counteroffer: {graph.emotional_counteroffer}\n"
        f"Present stakes: {graph.present_stakes}\n"
        f"Dialogue movement: {' -> '.join(graph.dialogue_act_sequence)}\n"
        f"Bodily counterpoint: {'; '.join(graph.body_language_counterpoint)}\n"
        f"Sensory channels: {', '.join(graph.sensory_channels)}\n"
        f"Agency actions: {' -> '.join(graph.agency_actions)}\n"
        f"Relationship delta: {graph.relationship_delta}\n"
        f"Story-state change: {graph.story_state_change}"
    )


def _program_document(program: LoomProgram) -> str:
    return (
        f"Pressure engine: {program.pressure_engine}\n"
        f"Offer: {program.offer}\n"
        f"Counteroffer: {program.counteroffer}\n"
        f"Embodied engine: {program.embodied_engine}\n"
        f"Mode engine: {program.mode_engine}\n"
        f"Reversal: {program.reversal}\n"
        f"Image system: {program.image_system}\n"
        f"Ending motion: {program.ending_motion}"
    )


def _transaction_document(program: TransactionProgram) -> str:
    return (
        f"Offer: {program.offer}\n"
        f"Counteroffer: {program.counteroffer}\n"
        f"Consent turn: {program.consent_turn}\n"
        f"Body logic: {program.body_logic}\n"
        f"Sensory asymmetry: {program.sensory_asymmetry}\n"
        f"Disclosure: {program.disclosure}\n"
        f"Plot payment: {program.plot_payment}\n"
        f"Ending state: {program.ending_state}"
    )


def _transaction_case_from_graph(graph: IntimacySceneGraph, number: int) -> str:
    body = "; ".join(graph.body_language_counterpoint)
    agency = " -> ".join(graph.agency_actions)
    senses = ", ".join(graph.sensory_channels)
    return (
        f"CASE {number}\n"
        f"OFFER: {graph.emotional_offer}\n"
        f"COUNTEROFFER: {graph.emotional_counteroffer}\n"
        f"CONSENT TURN: {agency}\n"
        f"BODY LOGIC: {body}\n"
        f"SENSORY ASYMMETRY: {senses}; one channel leads and another contradicts it\n"
        f"DISCLOSURE: bodily attention makes the present stake harder to evade\n"
        f"PLOT PAYMENT: {graph.story_state_change}\n"
        f"ENDING STATE: {graph.relationship_delta}\n"
        f"END CASE {number}"
    )


def render_transaction_prompt(
    *, parent: Mapping[str, Any], program: LoomProgram,
    passages: Sequence[SourcePassage], graphs: Mapping[str, IntimacySceneGraph],
) -> str:
    """Render a content-neutral loom for stochastic middle-movement programs."""

    examples: list[str] = []
    eligible = [
        item for item in passages
        if item.prompt_eligible and item.heat_band == "explicit"
        and "counterexample" not in item.intimacy_mode
    ]
    for number, passage in enumerate(eligible[:3], start=1):
        examples.append(_transaction_case_from_graph(graphs[passage.passage_id], number))
    manuscript = str(parent["cumulative_completion"])
    return (
        "INTIMACY TRANSACTION NOTEBOOK\n\n"
        "These records describe causal mechanisms, not reusable wording. A strong "
        "transaction changes what two adults know, risk, promise, or choose. Explicitness "
        "is a consequence of attention and agency, never a substitute for them.\n\n"
        + "\n\n".join(examples)
        + "\n\nNEW CASE: ESTHER AND SIMON\n"
        "They are married adults. The broken drive seal proves that Simon again made a "
        "dangerous unilateral decision. Their desire is active; sex cannot serve as "
        "automatic pardon. The transaction must pay for itself in new evidence and a "
        "concrete joint decision.\n\n"
        "CAUSAL WEAVE\n" + _program_document(program) + "\n\n"
        "MANUSCRIPT AT THE BRINK\n" + manuscript + "\n\n"
        "Continue the notebook with four genuinely different possible transactions. "
        "Make each field one concrete sentence of at most 24 words. Vary who initiates, "
        "what is learned, bodily geometry, sensory emphasis, and whether desire advances "
        "through play, argument, vulnerability, or surprise. Preserve the drive problem.\n\n"
        "CARD 1\nOFFER:"
    )


def parse_transaction_programs(
    raw: str, *, parent_id: str, seed: int,
) -> tuple[TransactionProgram, ...]:
    text = "CARD 1\nOFFER:" + raw if not re.search(r"(?im)^\s*CARD\s+1\b", raw) else raw
    text = re.sub(
        r"(?im)^\s*SENSORY\s+ASYMMETR\w*\s*:",
        "SENSORY ASYMMETRY:", text,
    )
    starts = list(re.finditer(r"(?im)^\s*CARD\s+(\d+)\s*$", text))
    parsed: list[TransactionProgram] = []
    field_pattern = "|".join(re.escape(item) for item in TRANSACTION_PLAN_FIELDS)
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        block = text[match.end():end]
        values: dict[str, str] = {}
        fields = list(re.finditer(rf"(?im)^\s*({field_pattern})\s*:\s*", block))
        for field_index, field in enumerate(fields):
            value_end = fields[field_index + 1].start() if field_index + 1 < len(fields) else len(block)
            value = block[field.end():value_end]
            value = re.split(r"(?im)^\s*END\s+CARD\b", value, maxsplit=1)[0].strip()
            values[field.group(1).upper()] = " ".join(value.split())
        if set(values) != set(TRANSACTION_PLAN_FIELDS):
            continue
        if any(not 4 <= len(values[field].split()) <= 48 for field in TRANSACTION_PLAN_FIELDS):
            continue
        consent = values["CONSENT TURN"]
        payment = values["PLOT PAYMENT"]
        body = values["BODY LOGIC"]
        if not re.search(r"\b(?:ask|answer|yes|no|stop|choose|guide|want|agree|permission|confirm|request|accept|reject|consent|refus|invitation|check-in)\w*\b", consent, re.I):
            continue
        if not re.search(r"\b(?:drive|seal|decision|evidence|name|witness|risk|plan|strategy|data|procedure|operation|protocol|security|breach|report)\w*\b", payment, re.I):
            continue
        if not re.search(r"\b(?:hand|mouth|hip|thigh|skin|body|bed|stand|sit|kneel|turn|touch|kiss|finger|breath|cloth|flesh)\w*\b", body, re.I):
            continue
        if re.search(r"\bwithout permission\b", body, re.I):
            continue
        number = match.group(1)
        parsed.append(TransactionProgram(
            transaction_id=f"transaction-plan.{parent_id}.{seed}.{number}",
            parent_id=parent_id,
            offer=values["OFFER"], counteroffer=values["COUNTEROFFER"],
            consent_turn=consent, body_logic=body,
            sensory_asymmetry=values["SENSORY ASYMMETRY"],
            disclosure=values["DISCLOSURE"], plot_payment=payment,
            ending_state=values["ENDING STATE"],
            raw_proposal_hash=sha256_text(raw), proposal_seed=seed,
        ))
    unique: dict[str, TransactionProgram] = {}
    for item in parsed:
        semantic = sha256_text(" ".join(
            re.findall(r"\b[\w'-]+\b", _transaction_document(item).casefold())
        ))
        unique.setdefault(semantic, item)
    return tuple(unique.values())


def _transaction_program_score(program: TransactionProgram) -> float:
    text = _transaction_document(program)
    concrete = len(re.findall(
        r"\b(?:drive|seal|hand|mouth|hip|thigh|skin|bed|table|shirt|kiss|ask|stop|choose|name|record|call|tomorrow)\w*\b",
        text, re.I,
    ))
    vague = len(re.findall(
        r"\b(?:connection|vulnerability|intimacy|emotion|feeling|passion|desire|truth)\w*\b",
        text, re.I,
    ))
    return max(0.1, 1.0 + concrete * 0.35 - vague * 0.18)


def _select_transaction_programs(
    programs: Sequence[TransactionProgram], *, count: int, seed: int,
) -> tuple[TransactionProgram, ...]:
    pool = list(programs)
    if len(pool) < count:
        raise ValueError(f"need {count} valid transaction programs, found {len(pool)}")
    rng = random.Random(seed)
    chosen: list[TransactionProgram] = []
    while pool and len(chosen) < count:
        weights: list[float] = []
        for item in pool:
            novelty = min(
                (1.0 - _candidate_similarity(_transaction_document(item), _transaction_document(prior)) for prior in chosen),
                default=1.0,
            )
            weights.append(_transaction_program_score(item) * (0.4 + novelty))
        position = rng.choices(range(len(pool)), weights=weights, k=1)[0]
        chosen.append(pool.pop(position))
    return tuple(chosen)


def target_runway(recipe: LoomRecipe, cell: BenchmarkCell) -> str:
    """Return the literal manuscript prefix presented to and stored from the model."""

    runway = cell.opening_fragment
    if recipe.topology == "full-apprenticeship" and cell.cell_id == "married-explicit":
        runway += (
            "\n\nEsther put two fingers on the broken seal. Then she crossed "
            "the space between them and put those same fingers against his mouth."
        )
    elif recipe.topology in {"naturalistic-runway", "source-nearest-runway"} and cell.cell_id == "married-explicit":
        runway += (
            "\n\nEsther touched the cracked seal with her forefinger.\n\n"
            "\"Tell me before I ask,\" she said.\n\n"
            "\"I opened it.\"\n\n"
            "\"That isn't the thing I haven't asked.\" She crossed the room, "
            "put the same finger against his lower lip, and waited until he met "
            "her eyes. \"Who did you leave inside?\""
        )
    return runway


def render_draft_prompt(
    *,
    recipe: LoomRecipe,
    cell: BenchmarkCell,
    program: LoomProgram,
    passages: Sequence[SourcePassage],
    graphs: Mapping[str, IntimacySceneGraph],
    bridge_dir: Path,
) -> tuple[str, tuple[str, ...]]:
    source_ids: list[str] = []
    if recipe.topology in {"naturalistic-runway", "source-nearest-runway"}:
        chunks = [
            "MANUSCRIPT APPRENTICESHIP ARCHIVE",
            "Finished scenes appear first. The last manuscript is unfinished. "
            "Its people and predicament are its own. Complete that manuscript "
            "in the demonstrated scene form, then print the archive end marker.",
        ]
    else:
        chunks = [
            "FICTION APPRENTICESHIP FILE",
            "The following are finished scene forms. Continue the final unfinished "
            "form as fiction, following its mode and causal shape. The literal "
            "people, places, incidents, and wording in prior forms do not carry "
            "forward. End a complete scene with the same end marker used below.",
        ]
    if recipe.topology == "full-apprenticeship":
        # Broad-to-near: non-explicit craft first, explicit scenes nearest the
        # target.  Holdout/calibration/counterexample passages remain excluded.
        matched = tuple(sorted(
            (
                item for item in passages
                if item.prompt_eligible and "counterexample" not in item.intimacy_mode
            ),
            key=lambda item: (item.heat_band == "explicit", item.example_number),
        ))
    elif recipe.topology == "source-nearest-runway":
        matched = ()
    else:
        matched = _matched_passages(cell, passages, recipe.source_pairs)
    for passage in matched:
        source_ids.append(passage.passage_id)
        if recipe.include_graphs:
            graph = graphs[passage.passage_id]
            blueprint = _graph_document(graph)
        else:
            blueprint = (
                "Observe how dialogue, physical action, desire, agency, and a "
                "story-state change are braided into one scene."
            )
        if recipe.include_raw_prose:
            chunks.append(_scene_form(passage.passage_id, blueprint, passage.text, passage.intimacy_mode))
    if recipe.topology == "full-apprenticeship" and cell.heat_band == "explicit":
        for bridge_name, bridge_mode, bridge_heat in (
            ("charged-restraint.md", "non-sex-sex-scene", "charged-restraint"),
            ("married-intimacy.md", "married-intimacy", "open-door-nongraphic"),
        ):
            bridge_path = bridge_dir / bridge_name
            bridge = bridge_path.read_text(encoding="utf-8").strip()
            source_ids.append(f"bridge.{bridge_path.stem}")
            chunks.append(_scene_form(
                f"project-{bridge_path.stem}",
                "Contemporary project voice. Physical attention changes a concrete "
                "decision; dialogue and bodily action counterpoint each other; the "
                "selected heat ceiling is honored without draining desire.",
                bridge, bridge_mode,
            ))
    if recipe.include_bridge:
        bridge_path = bridge_dir / _bridge_name(cell)
        bridge = bridge_path.read_text(encoding="utf-8").strip()
        source_ids.append(f"bridge.{bridge_path.stem}")
        if cell.heat_band == "explicit":
            bridge_blueprint = (
                "Emotional offer: Celia turns anger at Marcus's unilateral decision "
                "into an invitation he must answer attentively. Counteroffer: he "
                "protects the violin before touching her and follows rather than "
                "seizing her pace. Dialogue movement: accusation -> diagnostic joke "
                "-> invitation -> fresh yes -> rule for tomorrow. Physical movement: "
                "thumb in mouth -> kiss -> hand beneath skirt -> reciprocal manual "
                "touch -> blanket -> she controls penetration -> climax -> shared "
                "inspection. Story delta: sex does not pardon the interference; it "
                "makes a joint-decision rule concrete. Sensory anchors: hide glue, "
                "rosin, spruce, cold coffee, humidity gauge."
            )
        else:
            bridge_blueprint = (
                f"Contemporary adult fiction; mode={cell.intimacy_mode}; heat={cell.heat_band}. "
                "Concrete behavior carries the argument. Attraction or care changes "
                "knowledge, trust, choice, or future possibility. Bodies remain "
                "spatially intelligible; agency remains visible."
            )
        chunks.append(_scene_form(f"project-{bridge_path.stem}", bridge_blueprint, bridge, cell.intimacy_mode))
    if recipe.topology == "source-nearest-runway":
        nearest = next(
            item for item in passages
            if item.passage_id == "gabaldon.example-03" and item.prompt_eligible
        )
        source_ids.append(nearest.passage_id)
        chunks.append(_scene_form(
            "anonymous-mode-apprenticeship",
            "A married argument becomes playful, negotiated physical action. One "
            "partner controls tempo; logistics, dialogue, pleasure, and relationship "
            "remain simultaneous rather than sequential.",
            nearest.text, nearest.intimacy_mode,
        ))
    if recipe.topology in {"naturalistic-runway", "source-nearest-runway"}:
        target_blueprint = (
            "Esther and Simon are married adults reunited after a dangerous separation. "
            "The broken drive seal proves Simon made another unilateral choice. "
            f"Pressure: {program.pressure_engine} "
            f"Countermove: {program.counteroffer} "
            f"Embodied middle: {program.mode_engine} "
            f"Turn: {program.reversal} "
            f"Last image/action: {program.ending_motion} "
            "The sex is explicit, consensual, spatially lucid, and changes their "
            "next joint decision; it does not function as automatic forgiveness. "
            f"Complete roughly {cell.word_min}–{cell.word_max} words total."
        )
    else:
        target_blueprint = (
            "LOCKED CAUSAL SPINE\n- " + "\n- ".join(cell.story_program) + "\n\n"
            "INVARIANTS\n- " + "\n- ".join(cell.hard_constraints) + "\n\n"
            "SAMPLED CAUSAL WEAVE\n" + _program_document(program) + "\n\n"
            f"FORM\nOne complete scene in the demonstrated {cell.word_min}–{cell.word_max}-word form. "
            "The middle dwells in embodied transaction. The final movement receives "
            "real space: reversal, relationship change, concrete next decision, then "
            f"{SCENE_SENTINEL}. Heat, consent, and darkness remain independent; this "
            f"scene inhabits {cell.heat_band} heat and does not drift into another band."
        )
    activation = ""
    if recipe.topology == "full-apprenticeship":
        activation = (
            "TARGET-NEAR MODE ACTIVATION\n"
            "The following is the active middle of this scene, not an offstage "
            "promise or a later chapter:\n" + program.mode_engine
        )
    runway = target_runway(recipe, cell)
    target_chunks = [
        "TARGET SCENE FORM",
        f"MODE: {cell.intimacy_mode}\nHEAT: {cell.heat_band}\n"
        "SCENE BLUEPRINT:\n" + target_blueprint,
    ]
    if activation:
        target_chunks.append(activation)
    target_chunks.append("MANUSCRIPT\n" + runway)
    chunks.extend(target_chunks)
    prompt = "\n\n".join(chunks).rstrip()
    if not prompt.endswith(runway):
        raise AssertionError("base prompt must end on the prose runway")
    return prompt, tuple(source_ids)


def init_campaign(
    *, campaign_dir: str | Path, corpus_source: str | Path, bridge_dir: str | Path,
    parent_program_set: str | Path | None = None,
    apprenticeship_index: str | Path | None = None,
    apprenticeship_retrieval: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(campaign_dir)
    root.mkdir(parents=True, exist_ok=True)
    source = Path(corpus_source).resolve()
    bridges = Path(bridge_dir).resolve()
    parent_path = Path(parent_program_set).resolve() if parent_program_set else None
    if bool(apprenticeship_index) != bool(apprenticeship_retrieval):
        raise ValueError("apprenticeship index and retrieval must be supplied together")
    apprenticeship_index_path = Path(apprenticeship_index).resolve() if apprenticeship_index else None
    apprenticeship_retrieval_path = Path(apprenticeship_retrieval).resolve() if apprenticeship_retrieval else None
    parent_payload = json.loads(parent_path.read_text(encoding="utf-8")) if parent_path else None
    payload = {
        "record_type": "AutoloomCampaign",
        "version": AUTOLOOM_VERSION,
        "campaign_id": root.name,
        "corpus_source": str(source),
        "corpus_hash": hash_file(source),
        "bridge_dir": str(bridges),
        "bridge_hashes": {path.name: hash_file(path) for path in sorted(bridges.glob("*.md"))},
        "recipes": [asdict(item) | {"recipe_hash": item.recipe_hash} for item in loom_recipes()],
        "program_seeds": list(PROGRAM_SEEDS),
        "prose_seeds": list(PROSE_SEEDS),
        "trajectory_seeds": list(TRAJECTORY_SEEDS),
        "trajectory_stages": list(TRAJECTORY_STAGES),
        "transaction_plan_seeds": list(TRANSACTION_PLAN_SEEDS),
        "program_sampling": PROGRAM_SAMPLING,
        "prose_sampling": PROSE_SAMPLING,
        "scene_sentinel": SCENE_SENTINEL,
        "parent_program_set": str(parent_path) if parent_path else "",
        "parent_program_set_hash": hash_file(parent_path) if parent_path else "",
        "apprenticeship_index": str(apprenticeship_index_path) if apprenticeship_index_path else "",
        "apprenticeship_index_hash": hash_file(apprenticeship_index_path) if apprenticeship_index_path else "",
        "apprenticeship_retrieval": str(apprenticeship_retrieval_path) if apprenticeship_retrieval_path else "",
        "apprenticeship_retrieval_hash": hash_file(apprenticeship_retrieval_path) if apprenticeship_retrieval_path else "",
        "harness_hashes": {
            name: hash_file(Path(__file__).resolve().parent / name)
            for name in (
                "autoloom.py", "autoresearch.py", "anti_copy.py",
                "model_client.py", "shared_endpoint.py", "apprenticeship.py",
            )
        },
        "created_at": _now(),
    }
    payload["campaign_hash"] = hash_json({key: value for key, value in payload.items() if key != "created_at"})
    manifest = root / "campaign_manifest.v1.json"
    if manifest.is_file():
        prior = json.loads(manifest.read_text(encoding="utf-8"))
        if prior["campaign_hash"] != payload["campaign_hash"]:
            raise ValueError("autoloom campaign inputs changed; create a new campaign directory")
        payload = prior
    else:
        write_json(manifest, payload)
    if parent_payload:
        valid_cells = {item.cell_id for item in default_benchmarks()}
        supplied_cells = set(parent_payload.get("programs", {}))
        if not supplied_cells or not supplied_cells <= valid_cells:
            raise ValueError("parent program set has unexpected benchmark cells")
        write_json(root / "programs" / "parent_causal_program_set.v1.json", parent_payload)
    return payload


def _load(root: Path) -> tuple[dict[str, Any], tuple[SourcePassage, ...], tuple[BenchmarkCell, ...]]:
    campaign = json.loads((root / "campaign_manifest.v1.json").read_text(encoding="utf-8"))
    if hash_file(Path(campaign["corpus_source"])) != campaign["corpus_hash"]:
        raise ValueError("corpus source changed")
    current_bridges = {path.name: hash_file(path) for path in sorted(Path(campaign["bridge_dir"]).glob("*.md"))}
    if current_bridges != campaign["bridge_hashes"]:
        raise ValueError("bridge set changed")
    current_harness = {
        name: hash_file(Path(__file__).resolve().parent / name)
        for name in campaign.get("harness_hashes", {})
    }
    if current_harness != campaign.get("harness_hashes", {}):
        raise ValueError("autoloom harness changed; start a new campaign version")
    for path_key, hash_key in (
        ("apprenticeship_index", "apprenticeship_index_hash"),
        ("apprenticeship_retrieval", "apprenticeship_retrieval_hash"),
    ):
        if campaign.get(path_key) and hash_file(Path(campaign[path_key])) != campaign.get(hash_key):
            raise ValueError(f"{path_key.replace('_', ' ')} changed")
    return campaign, extract_gabaldon_examples(campaign["corpus_source"]), default_benchmarks()


class _ProgramSetComplete(Exception):
    """Internal signal used to close a stream after four complete proposals."""


class _ModeSetComplete(Exception):
    """Internal signal used to close a stream after four complete engines."""


def propose_programs(
    *, campaign_dir: str | Path, client: LlamaClient, admission: SharedEndpointAdmission,
    only_cell: str | None = None, max_tokens: int = 700,
) -> dict[str, Any]:
    root = Path(campaign_dir)
    campaign, _, cells = _load(root)
    calls = root / "programs" / "calls.jsonl"
    completed = _completed(calls, "call_id")
    all_programs: dict[str, list[LoomProgram]] = {}
    for cell in cells:
        if only_cell and cell.cell_id != only_cell:
            continue
        collected: list[LoomProgram] = []
        for seed in PROGRAM_SEEDS:
            call_id = f"program.{cell.cell_id}.{seed}"
            prior = completed.get(call_id)
            if prior:
                collected.extend(LoomProgram(**item) for item in prior["programs"])
                continue
            prompt = render_program_prompt(cell)
            prompt_hash = sha256_text(prompt)
            prompt_tokens = client.token_count(prompt)
            prompt_dir = root / "programs" / "prompts"
            prompt_dir.mkdir(parents=True, exist_ok=True)
            prompt_path = prompt_dir / f"{cell.cell_id}.txt"
            if prompt_path.is_file() and sha256_text(prompt_path.read_text(encoding="utf-8")) != prompt_hash:
                raise ValueError(f"program prompt drift for {cell.cell_id}")
            atomic_write_text(prompt_path, prompt)
            _append_jsonl(calls, {"call_id": call_id, "status": "started", "prompt_hash": prompt_hash, "seed": seed, "started_at": _now()})
            parts: list[str] = []
            def on_delta(delta: str) -> None:
                parts.append(delta)
                if "".join(parts).upper().count("END PROPOSAL") >= 4:
                    raise _ProgramSetComplete()
            started = time.monotonic()
            result = None
            semantic_stop = False
            try:
                with admission.acquire(owner=call_id, prompt_hash=prompt_hash, prompt_tokens=prompt_tokens, completion_tokens=max_tokens):
                    result = client.stream_raw(prompt=prompt, seed=seed, max_tokens=max_tokens, on_delta=on_delta, **PROGRAM_SAMPLING)
            except _ProgramSetComplete:
                semantic_stop = True
            raw_content = "".join(parts) if semantic_stop else str(result.content if result else "")
            raw_dir = root / "programs" / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            raw_path = raw_dir / f"{call_id}.txt"
            atomic_write_text(raw_path, raw_content)
            parsed = parse_program_proposals(raw_content, cell, seed)
            record = {
                "call_id": call_id, "status": "completed", "cell_id": cell.cell_id,
                "prompt_hash": prompt_hash, "prompt_tokens": prompt_tokens,
                "seed": seed, "raw_path": str(raw_path), "raw_hash": sha256_text(raw_content),
                "finish_reason": "semantic-four-proposal-stop" if semantic_stop else (result.finish_reason if result else ""),
                "usage": result.usage if result else {}, "timings": result.timings if result else {"elapsed_seconds": time.monotonic() - started},
                "programs": [asdict(item) for item in parsed], "completed_at": _now(),
            }
            _append_jsonl(calls, record)
            collected.extend(parsed)
        selection_seed = int(sha256_text(cell.cell_id)[:8], 16)
        compatible = [item for item in collected if program_compatible(item, cell)]
        selected = select_programs(compatible, count=4, seed=selection_seed)
        all_programs[cell.cell_id] = list(selected)
    lock = {
        "record_type": "AutoloomLockedProgramSet", "campaign_hash": campaign["campaign_hash"],
        "programs": {key: [asdict(item) | {"program_hash": item.program_hash} for item in value] for key, value in all_programs.items()},
    }
    lock["plan_set_hash"] = hash_json(lock)
    write_json(root / "programs" / "locked_program_set.v1.json", lock)
    return {"plan_set_hash": lock["plan_set_hash"], "cells": {key: len(value) for key, value in all_programs.items()}}


def _mode_engine_compatible(engine: ModeEngine, cell: BenchmarkCell) -> bool:
    text = canonical_json_text(asdict(engine)).casefold()
    if cell.heat_band == "explicit":
        return bool(re.search(
            r"\b(?:oral|mouth|naked|undress|breast|nipple|clitoris|cock|penis|"
            r"penetrat|inside|intercourse|orgasm|consummat|sexual)\w*\b", text
        )) and bool(re.search(
            r"\b(?:ask|yes|choos|permission|consent|stop|pause|invite)\w*\b", text
        ))
    if cell.heat_band == "none":
        return not bool(re.search(
            r"\b(?:kiss|sexual|erotic|arousal|breast|nipple|groin|orgasm|undress)\w*\b",
            text,
        ))
    return True


def _select_mode_engines(
    engines: Sequence[ModeEngine], *, count: int, seed: int
) -> tuple[ModeEngine, ...]:
    unique: list[ModeEngine] = []
    for item in engines:
        words = _tokens(canonical_json_text(asdict(item)))
        if all(
            len(words & _tokens(canonical_json_text(asdict(prior))))
            / max(1, len(words | _tokens(canonical_json_text(asdict(prior)))))
            < 0.90
            for prior in unique
        ):
            unique.append(item)
    if len(unique) < count:
        raise ValueError(f"need {count} distinct compatible mode engines, found {len(unique)}")
    rng = random.Random(seed)
    pool = list(unique)
    chosen: list[ModeEngine] = []
    while pool and len(chosen) < count:
        pick = rng.randrange(len(pool))
        chosen.append(pool.pop(pick))
    return tuple(chosen)


def _mode_document(engine: ModeEngine) -> str:
    return (
        f"Attention offer: {engine.attention_offer}\n"
        f"Consent sequence: {engine.consent_sequence}\n"
        f"Physical sequence: {engine.physical_sequence}\n"
        f"Plot coupling: {engine.plot_coupling}\n"
        f"Aftermath: {engine.aftermath}\n"
        f"Image anchor: {engine.image_anchor}"
    )


def _compose_mode_programs(
    *, campaign: Mapping[str, Any], parent_path: Path,
    selected_modes: Mapping[str, Sequence[ModeEngine]], root: Path,
    replay_provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    composed: dict[str, list[LoomProgram]] = {}
    for cell_id, modes in selected_modes.items():
        causal_items = parent.get("programs", {}).get(cell_id, [])
        if len(causal_items) < len(modes):
            raise ValueError(
                f"parent set for {cell_id} has {len(causal_items)} programs; "
                f"need {len(modes)}"
            )
        combined: list[LoomProgram] = []
        for index, (causal, mode) in enumerate(zip(causal_items, modes)):
            base = {
                key: value
                for key, value in causal.items()
                if key not in {"program_hash", "mode_engine"}
            }
            base["program_id"] = f"composed.{cell_id}.{index + 1}"
            base["mode_engine"] = _mode_document(mode)
            combined.append(LoomProgram(**base))
        composed[cell_id] = combined
    mode_lock: dict[str, Any] = {
        "record_type": "AutoloomLockedModeSet",
        "campaign_hash": campaign["campaign_hash"],
        "engines": {
            key: [asdict(item) | {"engine_hash": item.engine_hash} for item in value]
            for key, value in selected_modes.items()
        },
    }
    if replay_provenance:
        mode_lock["replay_provenance"] = dict(replay_provenance)
    mode_lock["mode_set_hash"] = hash_json(mode_lock)
    write_json(root / "modes" / "locked_mode_set.v1.json", mode_lock)
    plan_lock = {
        "record_type": "AutoloomComposedProgramSet",
        "campaign_hash": campaign["campaign_hash"],
        "parent_plan_set_hash": hash_file(parent_path),
        "mode_set_hash": mode_lock["mode_set_hash"],
        "programs": {
            key: [asdict(item) | {"program_hash": item.program_hash} for item in value]
            for key, value in composed.items()
        },
    }
    plan_lock["plan_set_hash"] = hash_json(plan_lock)
    write_json(root / "programs" / "locked_program_set.v1.json", plan_lock)
    return {
        "mode_set_hash": mode_lock["mode_set_hash"],
        "plan_set_hash": plan_lock["plan_set_hash"],
        "cells": {key: len(value) for key, value in composed.items()},
    }


def replay_causal_programs(
    *, campaign_dir: str | Path, source_dir: str | Path,
    only_cell: str | None = None,
) -> dict[str, Any]:
    """Recover target-anchored causal plans without scoring their mode fields."""

    root = Path(campaign_dir)
    source = Path(source_dir).resolve()
    campaign, _, cells = _load(root)
    selected: dict[str, list[LoomProgram]] = {}
    source_records: list[dict[str, Any]] = []
    for cell in cells:
        if only_cell and cell.cell_id != only_cell:
            continue
        collected: list[LoomProgram] = []
        for path in sorted(source.glob(f"program.{cell.cell_id}.*.txt")):
            seed_match = re.search(r"\.(\d+)\.txt$", path.name)
            if not seed_match:
                continue
            seed = int(seed_match.group(1))
            raw = path.read_text(encoding="utf-8")
            parsed = parse_program_proposals(raw, cell, seed)
            collected.extend(parsed)
            source_records.append({
                "path": str(path), "hash": sha256_text(raw), "seed": seed,
                "cell_id": cell.cell_id, "parsed_count": len(parsed),
            })
        compatible = [item for item in collected if causal_program_compatible(item, cell)]
        if compatible:
            chosen = select_programs(
                compatible, count=4,
                seed=int(sha256_text("causal." + cell.cell_id)[:8], 16),
            )
            selected[cell.cell_id] = [
                LoomProgram(
                    **{
                        **asdict(item),
                        "mode_engine": "Supplied by the separately sampled intimacy loom.",
                    }
                )
                for item in chosen
            ]
    if not selected:
        raise ValueError(f"no compatible causal programs found in {source}")
    lock: dict[str, Any] = {
        "record_type": "AutoloomCausalProgramSet",
        "campaign_hash": campaign["campaign_hash"],
        "programs": {
            key: [asdict(item) | {"program_hash": item.program_hash} for item in value]
            for key, value in selected.items()
        },
        "replay_provenance": {
            "method": "off-model-causal-reparse",
            "source_dir": str(source), "source_records": source_records,
            "replayed_at": _now(),
        },
    }
    lock["plan_set_hash"] = hash_json(lock)
    write_json(root / "programs" / "parent_causal_program_set.v1.json", lock)
    write_json(root / "programs" / "locked_program_set.v1.json", lock)
    write_json(root / "programs" / "causal_replay_record.v1.json", {
        "plan_set_hash": lock["plan_set_hash"],
        "source_records": source_records, "inference_calls": 0,
    })
    return {
        "plan_set_hash": lock["plan_set_hash"],
        "cells": {key: len(value) for key, value in selected.items()},
        "source_files": len(source_records), "inference_calls": 0,
    }


def replay_mode_engines(
    *, campaign_dir: str | Path, source_dir: str | Path,
    only_cell: str | None = None,
) -> dict[str, Any]:
    """Reparse preserved raw mode draws under the current deterministic parser.

    This performs no inference.  It exists so parser corrections do not erase
    or resample a successful stochastic draw.
    """

    root = Path(campaign_dir)
    source = Path(source_dir).resolve()
    campaign, _, cells = _load(root)
    parent_path = root / "programs" / "parent_causal_program_set.v1.json"
    if not parent_path.is_file():
        raise ValueError("mode replay requires --parent-program-set at init")
    selected_modes: dict[str, list[ModeEngine]] = {}
    source_records: list[dict[str, Any]] = []
    for cell in cells:
        if only_cell and cell.cell_id != only_cell:
            continue
        collected: list[ModeEngine] = []
        paths = sorted(source.glob(f"mode.{cell.cell_id}.*.txt"))
        for path in paths:
            seed_match = re.search(r"\.(\d+)\.txt$", path.name)
            if not seed_match:
                continue
            seed = int(seed_match.group(1))
            raw = path.read_text(encoding="utf-8")
            parsed = parse_mode_engines(raw, cell, seed)
            collected.extend(parsed)
            source_records.append(
                {
                    "path": str(path), "hash": sha256_text(raw),
                    "seed": seed, "cell_id": cell.cell_id,
                    "parsed_count": len(parsed),
                }
            )
        compatible = [item for item in collected if _mode_engine_compatible(item, cell)]
        if compatible:
            selected_modes[cell.cell_id] = list(
                _select_mode_engines(
                    compatible, count=4,
                    seed=int(sha256_text("mode." + cell.cell_id)[:8], 16),
                )
            )
    if not selected_modes:
        raise ValueError(f"no compatible mode engines found in {source}")
    provenance = {
        "method": "off-model-reparse",
        "source_dir": str(source),
        "source_records": source_records,
        "replayed_at": _now(),
    }
    result = _compose_mode_programs(
        campaign=campaign, parent_path=parent_path,
        selected_modes=selected_modes, root=root,
        replay_provenance=provenance,
    )
    write_json(root / "modes" / "replay_record.v1.json", provenance | result)
    return result | {"source_files": len(source_records), "inference_calls": 0}


def propose_mode_engines(
    *, campaign_dir: str | Path, client: LlamaClient,
    admission: SharedEndpointAdmission, only_cell: str | None = None,
    max_tokens: int = 850,
) -> dict[str, Any]:
    root = Path(campaign_dir)
    campaign, _, cells = _load(root)
    parent_path = root / "programs" / "parent_causal_program_set.v1.json"
    if not parent_path.is_file():
        raise ValueError("factorized mode loom requires --parent-program-set at init")
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    calls = root / "modes" / "calls.jsonl"
    completed = _completed(calls, "call_id")
    selected_modes: dict[str, list[ModeEngine]] = {}
    for cell in cells:
        if only_cell and cell.cell_id != only_cell:
            continue
        if cell.cell_id not in parent.get("programs", {}):
            continue
        collected: list[ModeEngine] = []
        for seed in PROGRAM_SEEDS[:2]:
            call_id = f"mode.{cell.cell_id}.{seed}"
            prior = completed.get(call_id)
            if prior:
                collected.extend(ModeEngine(**item) for item in prior["engines"])
                continue
            prompt = render_mode_prompt(cell)
            prompt_hash = sha256_text(prompt)
            prompt_tokens = client.token_count(prompt)
            prompt_dir = root / "modes" / "prompts"
            prompt_dir.mkdir(parents=True, exist_ok=True)
            atomic_write_text(prompt_dir / f"{cell.cell_id}.txt", prompt)
            start = {"call_id": call_id, "status": "started", "prompt_hash": prompt_hash, "seed": seed, "started_at": _now()}
            _append_jsonl(calls, start)
            parts: list[str] = []
            def on_delta(delta: str) -> None:
                parts.append(delta)
                if "".join(parts).upper().count("END ENGINE") >= 4:
                    raise _ModeSetComplete()
            result = None
            semantic_stop = False
            started = time.monotonic()
            try:
                with admission.acquire(owner=call_id, prompt_hash=prompt_hash, prompt_tokens=prompt_tokens, completion_tokens=max_tokens):
                    result = client.stream_raw(prompt=prompt, seed=seed, max_tokens=max_tokens, on_delta=on_delta, **PROGRAM_SAMPLING)
            except _ModeSetComplete:
                semantic_stop = True
            raw = "".join(parts) if semantic_stop else str(result.content if result else "")
            raw_dir = root / "modes" / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            raw_path = raw_dir / f"{call_id}.txt"
            atomic_write_text(raw_path, raw)
            parsed = parse_mode_engines(raw, cell, seed)
            record = {
                **start, "status": "completed", "cell_id": cell.cell_id,
                "prompt_tokens": prompt_tokens, "raw_path": str(raw_path),
                "raw_hash": sha256_text(raw),
                "finish_reason": "semantic-four-engine-stop" if semantic_stop else (result.finish_reason if result else ""),
                "usage": result.usage if result else {},
                "timings": result.timings if result else {"elapsed_seconds": time.monotonic() - started},
                "engines": [asdict(item) for item in parsed], "completed_at": _now(),
            }
            _append_jsonl(calls, record)
            collected.extend(parsed)
        compatible = [item for item in collected if _mode_engine_compatible(item, cell)]
        modes = _select_mode_engines(
            compatible, count=4, seed=int(sha256_text("mode." + cell.cell_id)[:8], 16)
        )
        selected_modes[cell.cell_id] = list(modes)
    return _compose_mode_programs(
        campaign=campaign, parent_path=parent_path,
        selected_modes=selected_modes, root=root,
    )


def draft(
    *, campaign_dir: str | Path, client: LlamaClient, admission: SharedEndpointAdmission,
    only_recipe: str | None = None, only_cell: str | None = None,
    only_seed: int | None = None, limit: int | None = None, max_tokens: int = 2000,
) -> dict[str, Any]:
    root = Path(campaign_dir)
    campaign, passages, cells = _load(root)
    locked_path = root / "programs" / "locked_program_set.v1.json"
    locked = json.loads(locked_path.read_text(encoding="utf-8"))
    graphs = {item.passage_id: _graph_for(item) for item in passages}
    recipes = loom_recipes()
    bridge_dir = Path(campaign["bridge_dir"])
    source_docs = {item.passage_id: item.text for item in passages}
    source_docs.update({f"bridge.{path.stem}": path.read_text(encoding="utf-8") for path in bridge_dir.glob("*.md")})
    anti_copy = AntiCopyIndex(source_docs, policy=AntiCopyPolicy())
    calls = root / "drafts" / "calls.jsonl"
    candidates_path = root / "drafts" / "candidates.jsonl"
    completed = _completed(candidates_path, "candidate_id")
    made = 0
    attempted = 0
    for recipe in recipes:
        if only_recipe and recipe.recipe_id != only_recipe:
            continue
        for cell in cells:
            if only_cell and cell.cell_id != only_cell:
                continue
            programs = [LoomProgram(**{key: value for key, value in item.items() if key != "program_hash"}) for item in locked["programs"][cell.cell_id]]
            for index, seed in enumerate(PROSE_SEEDS):
                if only_seed is not None and seed != only_seed:
                    continue
                if limit is not None and attempted >= limit:
                    return {"new": made, "stopped_at_limit": True}
                attempted += 1
                program = programs[index % len(programs)]
                candidate_id = f"{recipe.recipe_id}.{cell.cell_id}.{seed}"
                if candidate_id in completed:
                    continue
                prompt, source_ids = render_draft_prompt(recipe=recipe, cell=cell, program=program, passages=passages, graphs=graphs, bridge_dir=bridge_dir)
                prompt_hash = sha256_text(prompt)
                prompt_tokens = client.token_count(prompt)
                prompt_dir = root / "drafts" / "prompts" / recipe.recipe_id
                prompt_dir.mkdir(parents=True, exist_ok=True)
                atomic_write_text(prompt_dir / f"{cell.cell_id}.{seed}.txt", prompt)
                start = {"candidate_id": candidate_id, "status": "started", "prompt_hash": prompt_hash, "prompt_tokens": prompt_tokens, "program_hash": program.program_hash, "seed": seed, "started_at": _now()}
                _append_jsonl(calls, start)
                parts: list[str] = []
                runway = target_runway(recipe, cell)
                def on_delta(delta: str) -> None:
                    parts.append(delta)
                    match = anti_copy.first_exact_match(runway + "".join(parts))
                    if match:
                        raise SourceOverlapError(match)
                try:
                    with admission.acquire(owner=candidate_id, prompt_hash=prompt_hash, prompt_tokens=prompt_tokens, completion_tokens=max_tokens):
                        result = client.stream_raw(prompt=prompt, seed=seed, max_tokens=max_tokens, on_delta=on_delta, stop=(SCENE_SENTINEL,), **PROSE_SAMPLING)
                    completion = result.content
                    text = (runway.rstrip() + ("\n\n" if completion[:1].isspace() else " ") + completion.lstrip()).strip()
                    raw_dir = root / "drafts" / "raw"
                    raw_dir.mkdir(parents=True, exist_ok=True)
                    raw_path = raw_dir / f"{candidate_id}.txt"
                    atomic_write_text(raw_path, completion)
                    overlap = anti_copy.check(candidate_id, text).to_dict()
                    gate = calibration_gate(
                        cell, _candidate_gate(cell, text, overlap, result.finish_reason)
                    )
                    cliche_hits = [
                        match.group(0)
                        for pattern in CLICHE_PATTERNS
                        for match in re.finditer(pattern, text, flags=re.I)
                    ]
                    gate["diagnostics"]["cliche_hits"] = cliche_hits
                    gate["diagnostics"]["cliche_hit_count"] = len(cliche_hits)
                    gate["diagnostics"]["cadence_families"] = cadence_family_diagnostics(text)
                    motif_counts = {
                        motif: len(re.findall(rf"\b{motif}\w*\b", text, flags=re.I))
                        for motif in (
                            "salt", "scar", "bruise", "truth", "pattern",
                            "choice", "record", "evidence", "again", "body",
                        )
                    }
                    gate["diagnostics"]["motif_saturation"] = {
                        key: value for key, value in motif_counts.items() if value >= 4
                    }
                    record = {
                        "record_type": "AutoloomCandidate", "candidate_id": candidate_id,
                        "status": "completed", "campaign_hash": campaign["campaign_hash"],
                        "recipe_id": recipe.recipe_id, "recipe_hash": recipe.recipe_hash,
                        "cell_id": cell.cell_id, "cell_hash": cell.cell_hash,
                        "program_id": program.program_id, "program_hash": program.program_hash,
                        "prompt_hash": prompt_hash, "prompt_tokens": prompt_tokens,
                        "source_ids": list(source_ids), "seed": seed,
                        "sampling": PROSE_SAMPLING, "max_completion_tokens": max_tokens,
                        "text": text, "text_hash": sha256_text(text),
                        "raw_path": str(raw_path), "raw_hash": sha256_text(completion),
                        "finish_reason": result.finish_reason, "usage": result.usage,
                        "timings": result.timings, "cache": result.cache,
                        "overlap": overlap, "mechanical": gate, "completed_at": _now(),
                    }
                    _append_jsonl(candidates_path, record)
                    _append_jsonl(calls, {**start, "status": "completed", "text_hash": record["text_hash"], "finish_reason": result.finish_reason, "completed_at": _now()})
                    made += 1
                except Exception as exc:
                    partial = runway + "".join(parts)
                    failure_dir = root / "drafts" / "failures"
                    failure_dir.mkdir(parents=True, exist_ok=True)
                    path = failure_dir / f"{candidate_id}.txt"
                    atomic_write_text(path, partial)
                    _append_jsonl(calls, {**start, "status": "failed", "error_type": type(exc).__name__, "error": str(exc), "partial_path": str(path), "failed_at": _now()})
                    if not isinstance(exc, SourceOverlapError):
                        raise
    latest = _completed(candidates_path, "candidate_id")
    return {"new": made, "total": len(latest), "eligible": sum(bool(item["mechanical"]["passed"]) for item in latest.values())}


class _TransactionSetComplete(Exception):
    """Internal semantic stop after four complete transaction cards."""


def propose_transaction_programs(
    *, campaign_dir: str | Path, client: LlamaClient,
    admission: SharedEndpointAdmission, max_tokens: int = 1050,
) -> dict[str, Any]:
    """Sample stage-local transaction programs for every selected approach."""

    root = Path(campaign_dir)
    campaign, passages, cells = _load(root)
    cell = next(item for item in cells if item.cell_id == "married-explicit")
    approaches = _stage_parent_records(root, "transaction")
    locked = json.loads((root / "programs" / "locked_program_set.v1.json").read_text(encoding="utf-8"))
    programs = {
        item["program_hash"]: LoomProgram(**{key: value for key, value in item.items() if key != "program_hash"})
        for item in locked["programs"][cell.cell_id]
    }
    graphs = {item.passage_id: _graph_for(item) for item in passages}
    calls_path = root / "staged" / "calls.transaction-plans.jsonl"
    completed = _completed(calls_path, "call_id")
    all_by_parent: dict[str, list[TransactionProgram]] = {
        str(parent["stage_candidate_id"]): [] for parent in approaches
    }
    made = 0
    for parent in approaches:
        parent_id = str(parent["stage_candidate_id"])
        causal = programs[str(parent["program_hash"])]
        for seed in TRANSACTION_PLAN_SEEDS:
            call_id = f"transaction-plans.{parent_id}.{seed}"
            prior = completed.get(call_id)
            if prior:
                all_by_parent[parent_id].extend(TransactionProgram(**item) for item in prior["programs"])
                continue
            prompt = render_transaction_prompt(
                parent=parent, program=causal, passages=passages, graphs=graphs,
            )
            prompt_hash = sha256_text(prompt)
            prompt_tokens = client.token_count(prompt)
            prompt_dir = root / "staged" / "prompts" / "transaction-plans"
            prompt_dir.mkdir(parents=True, exist_ok=True)
            prompt_path = prompt_dir / f"{parent_id}.txt"
            if prompt_path.is_file() and sha256_text(prompt_path.read_text(encoding="utf-8")) != prompt_hash:
                raise ValueError(f"transaction prompt drift for {parent_id}")
            atomic_write_text(prompt_path, prompt)
            start = {
                "call_id": call_id, "status": "started", "parent_id": parent_id,
                "parent_hash": parent["cumulative_hash"], "program_hash": causal.program_hash,
                "prompt_hash": prompt_hash, "prompt_tokens": prompt_tokens,
                "seed": seed, "started_at": _now(),
            }
            _append_jsonl(calls_path, start)
            parts: list[str] = []
            result = None
            semantic_stop = False
            def on_delta(delta: str) -> None:
                parts.append(delta)
                if len(re.findall(r"(?im)^\s*END\s+CARD\s+\d+\s*$", "".join(parts))) >= 4:
                    raise _TransactionSetComplete()
            started = time.monotonic()
            try:
                with admission.acquire(
                    owner=call_id, prompt_hash=prompt_hash,
                    prompt_tokens=prompt_tokens, completion_tokens=max_tokens,
                ):
                    result = client.stream_raw(
                        prompt=prompt, seed=seed, max_tokens=max_tokens,
                        on_delta=on_delta, **PROGRAM_SAMPLING,
                    )
            except _TransactionSetComplete:
                semantic_stop = True
            raw = "".join(parts) if semantic_stop else str(result.content if result else "")
            raw_dir = root / "staged" / "raw" / "transaction-plans"
            raw_dir.mkdir(parents=True, exist_ok=True)
            raw_path = raw_dir / f"{call_id}.txt"
            atomic_write_text(raw_path, raw)
            parsed = parse_transaction_programs(raw, parent_id=parent_id, seed=seed)
            if not parsed:
                _append_jsonl(calls_path, {
                    **start, "status": "failed", "error_type": "TransactionParseError",
                    "error": "no valid transaction cards", "raw_path": str(raw_path),
                    "raw_hash": sha256_text(raw), "failed_at": _now(),
                })
                continue
            record = {
                **start, "status": "completed", "campaign_hash": campaign["campaign_hash"],
                "programs": [asdict(item) for item in parsed],
                "raw_path": str(raw_path), "raw_hash": sha256_text(raw),
                "finish_reason": "semantic-four-card-stop" if semantic_stop else (result.finish_reason if result else ""),
                "usage": result.usage if result else {},
                "timings": result.timings if result else {"elapsed_seconds": time.monotonic() - started},
                "completed_at": _now(),
            }
            _append_jsonl(calls_path, record)
            completed[call_id] = record
            all_by_parent[parent_id].extend(parsed)
            made += 1
    expected = len(approaches) * len(TRANSACTION_PLAN_SEEDS)
    terminal = _terminal_call_ids(calls_path, "call_id")
    if len(terminal) < expected:
        return {"new": made, "completed_calls": len(terminal), "expected_calls": expected, "selection_ready": False}
    selected_by_parent: dict[str, list[dict[str, Any]]] = {}
    for parent_id, proposals in all_by_parent.items():
        semantic_unique: dict[str, TransactionProgram] = {}
        for item in proposals:
            semantic_unique.setdefault(sha256_text(_transaction_document(item).casefold()), item)
        selection_seed = int(sha256_text(campaign["campaign_hash"] + ":" + parent_id + ":transaction-plan")[:8], 16)
        chosen = _select_transaction_programs(
            tuple(semantic_unique.values()), count=min(2, len(semantic_unique)), seed=selection_seed,
        )
        if not chosen:
            raise ValueError(f"no valid transaction programs for {parent_id}")
        selected_by_parent[parent_id] = [
            asdict(item) | {"transaction_hash": item.transaction_hash,
                            "selection_seed": selection_seed,
                            "quality_signal": _transaction_program_score(item)}
            for item in chosen
        ]
    payload = {
        "record_type": "AutoloomTransactionProgramSet",
        "campaign_hash": campaign["campaign_hash"],
        "sampling": PROGRAM_SAMPLING,
        "selection_method": "seeded-quality-diversity-without-replacement",
        "programs": selected_by_parent,
    }
    payload["transaction_set_hash"] = hash_json(payload)
    write_json(root / "staged" / "transaction_program_set.v1.json", payload)
    return {
        "new": made, "completed_calls": len(terminal), "expected_calls": expected,
        "parents": len(selected_by_parent), "selected": sum(map(len, selected_by_parent.values())),
        "transaction_set_hash": payload["transaction_set_hash"],
    }


def import_approach_selection(
    *, campaign_dir: str | Path, source_selection: str | Path,
) -> dict[str, Any]:
    """Import immutable approach checkpoints into a new prompt-research fork."""

    root = Path(campaign_dir)
    campaign, _, _ = _load(root)
    source = Path(source_selection).resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    selected = [dict(item) for item in payload.get("selected", ())]
    if not selected:
        raise ValueError("source approach selection contains no candidates")
    if any(item.get("stage") != "approach" for item in selected):
        raise ValueError("only approach checkpoints may be imported")
    for item in selected:
        if sha256_text(target_runway(
            next(recipe for recipe in loom_recipes() if recipe.recipe_id == item["recipe_id"]),
            next(cell for cell in default_benchmarks() if cell.cell_id == item["cell_id"]),
        ) + item["cumulative_completion"]) != item["cumulative_hash"]:
            raise ValueError(f"approach checkpoint hash mismatch: {item['stage_candidate_id']}")
        item["source_campaign_hash"] = item.get("campaign_hash", "")
        item["campaign_hash"] = campaign["campaign_hash"]
    imported = {
        "record_type": "AutoloomStageSelection",
        "campaign_hash": campaign["campaign_hash"],
        "stage": "approach",
        "selection_method": "immutable-import-from-prior-prompt-fork",
        "source_selection": str(source),
        "source_selection_hash": hash_file(source),
        "candidate_count": len(selected),
        "terminal_failure_count": int(payload.get("terminal_failure_count", 0)),
        "eligible_pool": sum(bool(item["diagnostics"]["eligible"]) for item in selected),
        "fallback_used": any(not item["diagnostics"]["eligible"] for item in selected),
        "selected": selected,
    }
    imported["selection_hash"] = hash_json(imported)
    write_json(root / "staged" / "selection.approach.v1.json", imported)
    return {
        "selected": len(selected), "selection_hash": imported["selection_hash"],
        "source_selection_hash": imported["source_selection_hash"],
    }


def import_locked_program_set(
    *, campaign_dir: str | Path, source_program_set: str | Path,
) -> dict[str, Any]:
    """Import an immutable causal/mode program set into a prompt-only fork."""

    root = Path(campaign_dir)
    campaign, _, _ = _load(root)
    source = Path(source_program_set).resolve()
    value = json.loads(source.read_text(encoding="utf-8"))
    raw_programs = value.get("programs")
    if not isinstance(raw_programs, Mapping) or not raw_programs:
        raise ValueError("source program set contains no programs")
    valid_cells = {item.cell_id for item in default_benchmarks()}
    if not set(raw_programs) <= valid_cells:
        raise ValueError("source program set contains an unknown benchmark cell")
    programs: dict[str, list[dict[str, Any]]] = {}
    for cell_id, items in raw_programs.items():
        if not isinstance(items, list) or not items:
            raise ValueError(f"source program set has no programs for {cell_id}")
        validated: list[dict[str, Any]] = []
        for raw in items:
            supplied_hash = str(raw.get("program_hash", ""))
            program = LoomProgram(**{
                key: item for key, item in raw.items() if key != "program_hash"
            })
            if program.cell_id != cell_id:
                raise ValueError("source program cell does not match its map key")
            if supplied_hash and supplied_hash != program.program_hash:
                raise ValueError(f"source program hash mismatch: {program.program_id}")
            validated.append(asdict(program) | {"program_hash": program.program_hash})
        programs[str(cell_id)] = validated
    payload = {
        "record_type": "AutoloomImportedProgramSet",
        "campaign_hash": campaign["campaign_hash"],
        "selection_method": "immutable-import-for-single-axis-prompt-fork",
        "source_program_set": str(source),
        "source_program_set_hash": hash_file(source),
        "source_campaign_hash": str(value.get("campaign_hash", "")),
        "programs": programs,
    }
    payload["plan_set_hash"] = hash_json(payload)
    write_json(root / "programs" / "locked_program_set.v1.json", payload)
    return {
        "cells": {key: len(items) for key, items in programs.items()},
        "plan_set_hash": payload["plan_set_hash"],
        "source_program_set_hash": payload["source_program_set_hash"],
    }


def replay_transaction_programs(
    *, campaign_dir: str | Path, source_dir: str | Path,
) -> dict[str, Any]:
    """Reparse preserved transaction draws under the current parser, no inference."""

    root = Path(campaign_dir)
    campaign, _, _ = _load(root)
    parents = _stage_parent_records(root, "transaction")
    source = Path(source_dir).resolve()
    selected_by_parent: dict[str, list[dict[str, Any]]] = {}
    provenance: list[dict[str, Any]] = []
    for parent in parents:
        parent_id = str(parent["stage_candidate_id"])
        proposals: list[TransactionProgram] = []
        for path in sorted(source.glob(f"transaction-plans.{parent_id}.*.txt")):
            seed_match = re.search(r"\.(\d+)\.txt$", path.name)
            if not seed_match:
                continue
            seed = int(seed_match.group(1))
            raw = path.read_text(encoding="utf-8")
            parsed = parse_transaction_programs(raw, parent_id=parent_id, seed=seed)
            proposals.extend(parsed)
            provenance.append({
                "path": str(path), "hash": sha256_text(raw), "parent_id": parent_id,
                "seed": seed, "parsed_count": len(parsed),
            })
        semantic_unique: dict[str, TransactionProgram] = {}
        for item in proposals:
            normalized = " ".join(re.findall(r"\b[\w'-]+\b", _transaction_document(item).casefold()))
            semantic_unique.setdefault(sha256_text(normalized), item)
        selection_seed = int(sha256_text(campaign["campaign_hash"] + ":" + parent_id + ":transaction-plan")[:8], 16)
        chosen = _select_transaction_programs(
            tuple(semantic_unique.values()), count=min(2, len(semantic_unique)), seed=selection_seed,
        )
        if not chosen:
            raise ValueError(f"no valid transaction programs for {parent_id}")
        selected_by_parent[parent_id] = [
            asdict(item) | {"transaction_hash": item.transaction_hash,
                            "selection_seed": selection_seed,
                            "quality_signal": _transaction_program_score(item)}
            for item in chosen
        ]
    payload = {
        "record_type": "AutoloomTransactionProgramSet",
        "campaign_hash": campaign["campaign_hash"],
        "sampling": PROGRAM_SAMPLING,
        "selection_method": "off-model-reparse-then-seeded-quality-diversity",
        "source_dir": str(source), "source_records": provenance,
        "programs": selected_by_parent,
    }
    payload["transaction_set_hash"] = hash_json(payload)
    write_json(root / "staged" / "transaction_program_set.v1.json", payload)
    return {
        "inference_calls": 0, "source_files": len(provenance),
        "parsed": sum(item["parsed_count"] for item in provenance),
        "selected": sum(map(len, selected_by_parent.values())),
        "transaction_set_hash": payload["transaction_set_hash"],
    }


def replay_transaction_candidates(
    *, campaign_dir: str | Path, source_candidates: str | Path,
) -> dict[str, Any]:
    """Re-evaluate preserved transaction prose under the current diagnostics."""

    root = Path(campaign_dir)
    campaign, passages, cells = _load(root)
    source = Path(source_candidates).resolve()
    parents = {
        item["stage_candidate_id"]: item
        for item in _stage_parent_records(root, "transaction")
    }
    source_docs = {item.passage_id: item.text for item in passages}
    source_docs.update({
        f"bridge.{path.stem}": path.read_text(encoding="utf-8")
        for path in Path(campaign["bridge_dir"]).glob("*.md")
    })
    if campaign.get("apprenticeship_index"):
        _, apprenticeship_sources = render_retrieved_archive(
            index_manifest_path=campaign["apprenticeship_index"],
            retrieval_path=campaign["apprenticeship_retrieval"],
        )
        source_docs.update(apprenticeship_sources)
    anti_copy = AntiCopyIndex(source_docs, policy=AntiCopyPolicy())
    replayed: list[dict[str, Any]] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        original = json.loads(line)
        if original.get("status") != "completed" or original.get("stage") != "transaction":
            continue
        parent_id = str(original["parent_id"])
        if parent_id not in parents:
            continue
        segment = str(original["segment"])
        if sha256_text(segment) != original["segment_hash"]:
            raise ValueError(f"source segment hash mismatch: {original['stage_candidate_id']}")
        expected_completion = str(parents[parent_id]["cumulative_completion"]) + "\n\n" + segment
        if expected_completion != original["cumulative_completion"]:
            raise ValueError(f"source lineage mismatch: {original['stage_candidate_id']}")
        recipe = next(item for item in loom_recipes() if item.recipe_id == original["recipe_id"])
        cell = next(item for item in cells if item.cell_id == original["cell_id"])
        cumulative = target_runway(recipe, cell) + expected_completion
        overlap = anti_copy.check(str(original["stage_candidate_id"]), cumulative).to_dict()
        diagnostics = _stage_diagnostics("transaction", segment, cumulative)
        diagnostics["anti_copy_passed"] = not overlap.get("hard_fail") and not overlap.get("unresolved_flags")
        diagnostics["eligible"] = bool(diagnostics["eligible"] and diagnostics["anti_copy_passed"])
        item = dict(original)
        item["source_campaign_hash"] = item.get("campaign_hash", "")
        item["campaign_hash"] = campaign["campaign_hash"]
        item["source_candidate_file"] = str(source)
        item["source_candidate_file_hash"] = hash_file(source)
        item["diagnostics"] = diagnostics
        item["overlap"] = overlap
        item["cumulative_hash"] = sha256_text(cumulative)
        replayed.append(item)
    if not replayed:
        raise ValueError("no compatible transaction candidates to replay")
    candidates_path = root / "staged" / "candidates.transaction.jsonl"
    atomic_write_text(
        candidates_path,
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for item in replayed),
    )
    spec = next(item for item in TRAJECTORY_STAGES if item["stage"] == "transaction")
    selection_seed = int(sha256_text(campaign["campaign_hash"] + ":transaction")[:8], 16)
    selected = _seeded_diverse_stage_selection(
        replayed, count=int(spec["survivors"]), seed=selection_seed,
    )
    selection = {
        "record_type": "AutoloomStageSelection",
        "campaign_hash": campaign["campaign_hash"], "stage": "transaction",
        "selection_seed": selection_seed,
        "selection_method": "off-model-diagnostic-replay-then-seeded-quality-diversity",
        "source_candidates": str(source), "source_candidates_hash": hash_file(source),
        "candidate_count": len(replayed), "terminal_failure_count": 0,
        "eligible_pool": sum(bool(item["diagnostics"]["eligible"]) for item in replayed),
        "fallback_used": any(not item["diagnostics"]["eligible"] for item in selected),
        "selected": list(selected),
    }
    selection["selection_hash"] = hash_json(selection)
    write_json(root / "staged" / "selection.transaction.v1.json", selection)
    return {
        "inference_calls": 0, "replayed": len(replayed),
        "eligible": selection["eligible_pool"],
        "selected": [item["stage_candidate_id"] for item in selected],
        "selection_hash": selection["selection_hash"],
    }


def _complete_stage_prefix(
    raw: str, *, minimum_words: int, maximum_words: int,
) -> str:
    """Keep the longest sentence-complete paragraph prefix in a stage band."""

    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", raw) if item.strip()]
    selected: list[str] = []
    best = ""
    for paragraph in paragraphs:
        trial = "\n\n".join((*selected, paragraph))
        count = len(re.findall(r"\b[\w’'-]+\b", trial))
        if count > maximum_words:
            break
        selected.append(paragraph)
        if count >= minimum_words and re.search(r"[.!?][\"”’']?\s*$", paragraph):
            best = trial
    if not best:
        raise ValueError(
            f"no complete stage boundary within {minimum_words}-{maximum_words} words"
        )
    return best


def render_stage_prompt(
    *, stage: str, recipe: LoomRecipe, cell: BenchmarkCell,
    program: LoomProgram, passages: Sequence[SourcePassage],
    graphs: Mapping[str, IntimacySceneGraph], bridge_dir: Path,
    prior_completion: str = "",
    transaction: TransactionProgram | None = None,
    apprenticeship_archive: str = "",
) -> tuple[str, tuple[str, ...]]:
    """Render stage-local conditioning while ending on uninterrupted manuscript."""

    base, source_ids = render_draft_prompt(
        recipe=recipe, cell=cell, program=program,
        passages=passages, graphs=graphs, bridge_dir=bridge_dir,
    )
    if apprenticeship_archive:
        base = apprenticeship_archive.rstrip() + "\n\n" + base
    if stage in {"approach", "transaction"}:
        # A staged probe is an unfinished movement, not a miniature complete
        # scene.  End markers in demonstrations taught the base model to stop
        # naturally after 100–150 words, well before the trajectory budget.
        base = base.replace(SCENE_SENTINEL, "")
        base = base.replace("then print the archive end marker.", "then continue the unfinished manuscript.")
        base = base.replace("End a complete scene with the same end marker used below.", "Continue the final unfinished manuscript in the demonstrated mode.")
    runway = target_runway(recipe, cell)
    marker = "MANUSCRIPT\n" + runway
    if not base.endswith(marker):
        raise ValueError("stage prompt cannot locate the manuscript boundary")
    prefix = base[:-len(marker)]
    if stage == "approach":
        local = (
            "LOCAL MOVEMENT: APPROACH\n"
            "Let pressure acquire a body. End at a live offer or discovery, before "
            "consummation and before anyone resolves the disagreement. Dialogue and "
            "physical behavior must each change the available interpretation."
        )
    elif stage == "transaction":
        if transaction is None:
            raise ValueError("transaction stage requires a sampled transaction program")
        if recipe.topology == "source-nearest-runway":
            local = (
                "CURRENT IMPULSE\n"
                f"Offer: {transaction.offer}\n"
                f"Counteroffer: {transaction.counteroffer}\n"
                f"Consent turn: {transaction.consent_turn}\n"
                f"Body logic: {transaction.body_logic}\n"
                f"Sensory asymmetry: {transaction.sensory_asymmetry}\n"
                f"Discovery: {transaction.disclosure}\n"
                f"Story payment: {transaction.plot_payment}\n\n"
                f"Ending state: {transaction.ending_state}\n\n"
                "Continue in the temporal patience and bodily specificity of the nearest "
                "finished scene. Put the disagreement into concrete acts and replies; do "
                "not replace it with relationship-policy summary. Keep positions and every "
                "change of initiative physically legible. Let play, speech, logistics, and "
                "pleasure remain active at once. If this movement reaches climax, render "
                "the mutually responsive completion rather than jumping to 'afterward.' "
                "End only after the sampled ending state becomes a visible choice."
            )
        else:
            local = (
                "LOCAL MOVEMENT: EMBODIED TRANSACTION\n"
                + _transaction_document(transaction)
                + "\n\nRealize this as spatially lucid fiction, not as a checklist. Every physical "
                "action must either answer, complicate, or redirect the prior action. Give "
                "desire a particular texture and tempo. Keep the drive problem physically "
                "present. The movement ends only after intimacy produces new evidence and a "
                "changed choice; save reflective settling for the aftermath."
            )
    else:
        local = (
            "LOCAL MOVEMENT: AFTERMATH\n"
            "Let the altered bodies and altered evidence coexist. Make the concrete next "
            "decision visible through action and dialogue. Do not summarize the lesson, "
            "repeat the climax, or erase the disagreement. End on a specific shared or "
            "contested action, then print the archive end marker."
        )
    manuscript = runway + (("\n\n" + prior_completion) if prior_completion else "")
    prompt = prefix + local + "\n\nMANUSCRIPT\n" + manuscript
    if not prompt.endswith(manuscript):
        raise AssertionError("stage prompt must end on exact manuscript prose")
    return prompt, source_ids


def _stage_diagnostics(stage: str, segment: str, cumulative: str) -> dict[str, Any]:
    words = re.findall(r"\b[\w’'-]+\b", segment)
    dialogue_turns = len(re.findall(r"(?:^|\n)\s*[\"“]", segment))
    anchors = {
        term: bool(re.search(rf"\b{term}\w*\b", cumulative, re.I))
        for term in ("drive", "seal", "Esther", "Simon")
    }
    contact = len(re.findall(
        r"\b(?:touch|hand|finger|mouth|lip|kiss|skin|shirt|waist|thigh|hip)\w*\b",
        segment, re.I,
    ))
    explicit = len(re.findall(
        r"\b(?:cock|clitoris|nipple|breast|penetrat|entered her|inside her|"
        r"slid? (?:into|inside)|slide of (?:him|her) inside|orgasm|climax|came)\w*\b",
        segment, re.I,
    ))
    agency = len(re.findall(
        r"\b(?:ask|answer|yes|no|stop|wait|choose|guide|want|agree|permission|"
        r"confirm|direct|allow|invite|offer|hold|slower|faster)\w*\b",
        segment, re.I,
    ))
    plot_payment = len(re.findall(
        r"\b(?:drive|seal|decision|evidence|name|witness|risk|plan|strategy|data|"
        r"tomorrow|tonight|call|record|verify|copy|opened|papers?|courier|service|"
        r"house|compromis|remove|take everything)\w*\b",
        segment, re.I,
    ))
    sensory_channels = {
        "touch": bool(re.search(r"\b(?:touch|skin|hand|finger|pressure|texture|rough|smooth)\w*\b", segment, re.I)),
        "sound": bool(re.search(r"\b(?:hear|sound|voice|breath|whisper|click|scrape|groan)\w*\b", segment, re.I)),
        "temperature": bool(re.search(r"\b(?:warm|cold|cool|heat|hot|temperature)\w*\b", segment, re.I)),
        "smell": bool(re.search(r"\b(?:smell|scent|salt|soap|sweat|perfume)\w*\b", segment, re.I)),
        "taste": bool(re.search(r"\b(?:taste|tongue|mouth|lip|salt)\w*\b", segment, re.I)),
        "sight": bool(re.search(r"\b(?:see|saw|look|watch|light|color|red|white|dark)\w*\b", segment, re.I)),
    }
    sensory_count = sum(sensory_channels.values())
    progression = sum(bool(re.search(pattern, segment, re.I)) for pattern in (
        r"\b(?:approach|closer|crossed|step)\w*\b",
        r"\b(?:touch|hand|finger|palm)\w*\b",
        r"\b(?:kiss|mouth|lip|tongue)\w*\b",
        r"\b(?:shirt|button|skirt|trouser|undress|naked)\w*\b",
        r"\b(?:thigh|hip|breast|cock|inside|penetrat)\w*\b",
        r"\b(?:pause|stop|wait|ask|answer|choose|direct)\w*\b",
    ))
    completed_intimacy_matches = [
        match.group(0) for match in re.finditer(
            r"\b(?:climax(?:ed)?|orgasm(?:ed)?|contractions?|spent himself)\b"
            r"|\b(?:his|her) seed burst\b"
            r"|\b(?:his|her|their) (?:shared )?release\b"
            r"|\b(?:he|she|Esther|Simon)\s+came\b"
            r"(?!\s+(?:back|closer|forward|home|inside the room|to))",
            segment, re.I,
        )
    ]
    completed_intimacy = len(completed_intimacy_matches)
    aftermath = len(re.findall(
        r"\b(?:afterward|later|tomorrow|decision|decide|together|phone|witness|promise|rule)\w*\b",
        segment, re.I,
    ))
    cliche_hits = [
        match.group(0)
        for pattern in CLICHE_PATTERNS
        for match in re.finditer(pattern, segment, flags=re.I)
    ]
    motif_counts = {
        motif: len(re.findall(rf"\b{motif}\w*\b", segment, flags=re.I))
        for motif in (
            "salt", "scar", "bruise", "truth", "pattern", "choice",
            "record", "evidence", "again", "body",
        )
    }
    cadence = cadence_family_diagnostics(segment)
    packet_leakage = bool(re.search(
        r"(?:TARGET SCENE FORM|SCENE BLUEPRINT|MODE ENGINE|END_SCENE|APPRENTICESHIP|"
        r"WRITERS?' ROOM NOTES|PREVIOUS PAGE|NEXT PAGE|SCENE-FORM NOTES|REVISION NOTES)",
        segment, re.I,
    ))
    if stage == "approach":
        stage_ok = dialogue_turns >= 2 and contact >= 2 and explicit == 0
    elif stage == "transaction":
        stage_ok = bool(
            contact >= 8 and explicit >= 1 and agency >= 3
            and plot_payment >= 3 and sensory_count >= 3 and progression >= 4
            and completed_intimacy >= 1
        )
    else:
        stage_ok = aftermath >= 2 and explicit <= 2
    motif_saturation = bool(
        motif_counts.get("scar", 0) > 3
        or motif_counts.get("bruise", 0) > 3
        or motif_counts.get("pattern", 0) > 3
        or motif_counts.get("again", 0) > 9
    )
    eligible = bool(
        all(anchors.values())
        and stage_ok
        and not packet_leakage
        and not cliche_hits
        and not motif_saturation
        and cadence["hits_per_1000_words"] <= 12
    )
    quality = (
        10.0 * int(eligible)
        + min(dialogue_turns, 8) * 0.3
        + min(contact, 12) * 0.25
        + min(explicit, 4) * (0.25 if stage == "transaction" else 0.05)
        + min(agency, 8) * (0.45 if stage == "transaction" else 0.1)
        + min(plot_payment, 8) * (0.45 if stage == "transaction" else 0.1)
        + sensory_count * (0.5 if stage == "transaction" else 0.1)
        + progression * (0.4 if stage == "transaction" else 0.1)
        + min(aftermath, 6) * (0.5 if stage == "aftermath" else 0.1)
        - len(cliche_hits) * 2.0
        - max(0, motif_counts.get("scar", 0) - 2) * 0.8
        - max(0, motif_counts.get("bruise", 0) - 2) * 0.8
        - max(0, motif_counts.get("pattern", 0) - 2) * 0.8
        - cadence["hits_per_1000_words"] * 0.05
    )
    return {
        "eligible": eligible,
        "quality_signal": round(quality, 4),
        "word_count": len(words),
        "dialogue_turns": dialogue_turns,
        "anchor_presence": anchors,
        "contact_signal": contact,
        "explicit_signal": explicit,
        "agency_signal": agency,
        "plot_payment_signal": plot_payment,
        "sensory_channels": sensory_channels,
        "sensory_channel_count": sensory_count,
        "physical_progression_signal": progression,
        "completed_intimacy_signal": completed_intimacy,
        "completed_intimacy_evidence": completed_intimacy_matches,
        "aftermath_signal": aftermath,
        "cliche_hits": cliche_hits,
        "motif_counts": {key: value for key, value in motif_counts.items() if value},
        "motif_saturation": motif_saturation,
        "cadence_families": cadence,
        "packet_leakage": packet_leakage,
    }


def _seeded_diverse_stage_selection(
    candidates: Sequence[Mapping[str, Any]], *, count: int, seed: int,
) -> tuple[dict[str, Any], ...]:
    """Sample survivors by quality and distance; do not collapse to top-k."""

    pool = [dict(item) for item in candidates if item["diagnostics"]["eligible"]]
    if len(pool) < count:
        # Keep the experiment moving when a stage misses its aspirational gate,
        # but make fallback status explicit and never call it eligible.
        seen = {item["stage_candidate_id"] for item in pool}
        fallbacks = sorted(
            (dict(item) for item in candidates if item["stage_candidate_id"] not in seen),
            key=lambda item: (-float(item["diagnostics"]["quality_signal"]), item["stage_candidate_id"]),
        )
        pool.extend(fallbacks[: count - len(pool)])
    if len(pool) < count:
        raise ValueError(f"need {count} stage candidates, found {len(pool)}")
    rng = random.Random(seed)
    chosen: list[dict[str, Any]] = []
    while pool and len(chosen) < count:
        weights: list[float] = []
        for item in pool:
            novelty = min(
                (1.0 - _candidate_similarity(item["segment"], prior["segment"]) for prior in chosen),
                default=1.0,
            )
            quality = max(0.1, float(item["diagnostics"]["quality_signal"]) + 2.0)
            weights.append(max(0.01, quality * (0.35 + novelty)))
        pick = rng.choices(range(len(pool)), weights=weights, k=1)[0]
        chosen.append(pool.pop(pick))
    return tuple(chosen)


def _stage_parent_records(root: Path, stage: str) -> tuple[dict[str, Any], ...]:
    if stage == "approach":
        return ()
    prior = "approach" if stage == "transaction" else "transaction"
    path = root / "staged" / f"selection.{prior}.v1.json"
    if not path.is_file():
        raise ValueError(f"run and select {prior} before {stage}")
    value = json.loads(path.read_text(encoding="utf-8"))
    return tuple(dict(item) for item in value["selected"])


def run_staged_autoloom(
    *, campaign_dir: str | Path, client: LlamaClient,
    admission: SharedEndpointAdmission, stage: str,
    recipe_id: str = "loom-runway-doc", cell_id: str = "married-explicit",
    limit: int | None = None,
) -> dict[str, Any]:
    """Run one resumable stochastic manuscript stage and select survivors."""

    root = Path(campaign_dir)
    campaign, passages, cells = _load(root)
    if stage not in {item["stage"] for item in TRAJECTORY_STAGES}:
        raise ValueError(f"unknown trajectory stage {stage!r}")
    spec = next(item for item in TRAJECTORY_STAGES if item["stage"] == stage)
    recipe = next(item for item in loom_recipes() if item.recipe_id == recipe_id)
    cell = next(item for item in cells if item.cell_id == cell_id)
    locked = json.loads((root / "programs" / "locked_program_set.v1.json").read_text(encoding="utf-8"))
    programs = [
        LoomProgram(**{key: value for key, value in item.items() if key != "program_hash"})
        for item in locked["programs"][cell.cell_id]
    ]
    graphs = {item.passage_id: _graph_for(item) for item in passages}
    bridge_dir = Path(campaign["bridge_dir"])
    source_docs = {item.passage_id: item.text for item in passages}
    source_docs.update({
        f"bridge.{path.stem}": path.read_text(encoding="utf-8")
        for path in bridge_dir.glob("*.md")
    })
    apprenticeship_archive = ""
    apprenticeship_source_ids: tuple[str, ...] = ()
    if campaign.get("apprenticeship_index"):
        apprenticeship_archive, apprenticeship_sources = render_retrieved_archive(
            index_manifest_path=campaign["apprenticeship_index"],
            retrieval_path=campaign["apprenticeship_retrieval"],
        )
        source_docs.update(apprenticeship_sources)
        apprenticeship_source_ids = tuple(apprenticeship_sources)
    anti_copy = AntiCopyIndex(source_docs, policy=AntiCopyPolicy())
    parents = _stage_parent_records(root, stage)
    jobs: list[tuple[str, int, LoomProgram, dict[str, Any] | None, TransactionProgram | None]] = []
    if stage == "approach":
        for index, seed in enumerate(TRAJECTORY_SEEDS):
            jobs.append((f"approach.{seed}", seed, programs[index % len(programs)], None, None))
    elif stage == "transaction":
        transaction_path = root / "staged" / "transaction_program_set.v1.json"
        if not transaction_path.is_file():
            raise ValueError("sample transaction programs before transaction prose")
        transaction_set = json.loads(transaction_path.read_text(encoding="utf-8"))
        if transaction_set["campaign_hash"] != campaign["campaign_hash"]:
            raise ValueError("transaction programs belong to another campaign")
        for parent in parents:
            parent_id = str(parent["stage_candidate_id"])
            program = next(item for item in programs if item.program_hash == parent["program_hash"])
            parent_transactions = tuple(transaction_set["programs"].get(parent_id, ()))
            realizations_per_program = 3 if len(parent_transactions) == 1 else 1
            for branch, item in enumerate(parent_transactions, start=1):
                transaction = TransactionProgram(**{
                    key: value for key, value in item.items()
                    if key not in {"transaction_hash", "selection_seed", "quality_signal"}
                })
                for realization in range(1, realizations_per_program + 1):
                    seed = int(sha256_text(
                        f"{parent_id}:{stage}:{transaction.transaction_hash}:{realization}"
                    )[:8], 16)
                    jobs.append((
                        f"{stage}.{parent_id}.{branch}.{realization}",
                        seed, program, parent, transaction,
                    ))
    else:
        for parent in parents:
            program = next(item for item in programs if item.program_hash == parent["program_hash"])
            inherited = parent.get("transaction_program")
            transaction = TransactionProgram(**inherited) if isinstance(inherited, Mapping) else None
            for branch in range(3):
                seed = int(sha256_text(f"{parent['stage_candidate_id']}:{stage}:{branch}")[:8], 16)
                jobs.append((f"{stage}.{parent['stage_candidate_id']}.{branch + 1}", seed, program, parent, transaction))
    calls = root / "staged" / f"calls.{stage}.jsonl"
    candidates_path = root / "staged" / f"candidates.{stage}.jsonl"
    completed = _completed(candidates_path, "stage_candidate_id")
    made = 0
    attempted = 0
    terminal_ids = _terminal_call_ids(calls, "stage_candidate_id")
    for stage_candidate_id, seed, program, parent, transaction in jobs:
        if stage_candidate_id in completed:
            continue
        if stage_candidate_id in terminal_ids:
            continue
        if limit is not None and attempted >= limit:
            break
        attempted += 1
        prior_completion = str(parent["cumulative_completion"]) if parent else ""
        prompt, source_ids = render_stage_prompt(
            stage=stage, recipe=recipe, cell=cell, program=program,
            passages=passages, graphs=graphs, bridge_dir=bridge_dir,
            prior_completion=prior_completion, transaction=transaction,
            apprenticeship_archive=apprenticeship_archive,
        )
        source_ids = apprenticeship_source_ids + source_ids
        prompt_hash = sha256_text(prompt)
        prompt_tokens = client.token_count(prompt)
        start = {
            "stage_candidate_id": stage_candidate_id, "status": "started",
            "stage": stage, "seed": seed, "program_hash": program.program_hash,
            "parent_id": parent["stage_candidate_id"] if parent else "",
            "parent_hash": parent["cumulative_hash"] if parent else "",
            "prompt_hash": prompt_hash, "prompt_tokens": prompt_tokens,
            "started_at": _now(),
        }
        _append_jsonl(calls, start)
        parts: list[str] = []
        runway = target_runway(recipe, cell)
        def on_delta(delta: str) -> None:
            parts.append(delta)
            match = anti_copy.first_exact_match(runway + prior_completion + "".join(parts))
            if match:
                raise SourceOverlapError(match)
        try:
            with admission.acquire(
                owner=stage_candidate_id, prompt_hash=prompt_hash,
                prompt_tokens=prompt_tokens, completion_tokens=int(spec["probe_tokens"]),
            ):
                result = client.stream_raw(
                    prompt=prompt, seed=seed, max_tokens=int(spec["probe_tokens"]),
                    on_delta=on_delta, stop=(SCENE_SENTINEL,), **PROSE_SAMPLING,
                )
            raw = result.content
            minimum_words, maximum_words = map(int, spec["target_words"])
            segment = _complete_stage_prefix(
                raw, minimum_words=minimum_words, maximum_words=maximum_words,
            )
            cumulative_completion = prior_completion + (("\n\n" if prior_completion else "") + segment)
            cumulative = target_runway(recipe, cell) + cumulative_completion
            overlap = anti_copy.check(stage_candidate_id, cumulative).to_dict()
            diagnostics = _stage_diagnostics(stage, segment, cumulative)
            diagnostics["anti_copy_passed"] = not overlap.get("hard_fail") and not overlap.get("unresolved_flags")
            diagnostics["eligible"] = bool(diagnostics["eligible"] and diagnostics["anti_copy_passed"])
            raw_dir = root / "staged" / "raw" / stage
            raw_dir.mkdir(parents=True, exist_ok=True)
            raw_path = raw_dir / f"{stage_candidate_id}.txt"
            atomic_write_text(raw_path, raw)
            record = {
                "record_type": "AutoloomStageCandidate",
                **start, "status": "completed", "campaign_hash": campaign["campaign_hash"],
                "recipe_id": recipe.recipe_id, "recipe_hash": recipe.recipe_hash,
                "cell_id": cell.cell_id, "cell_hash": cell.cell_hash,
                "source_ids": list(source_ids), "segment": segment,
                "segment_hash": sha256_text(segment),
                "cumulative_completion": cumulative_completion,
                "cumulative_hash": sha256_text(cumulative),
                "raw_path": str(raw_path), "raw_hash": sha256_text(raw),
                "finish_reason": result.finish_reason, "usage": result.usage,
                "timings": result.timings, "cache": result.cache,
                "sampling": PROSE_SAMPLING, "diagnostics": diagnostics,
                "overlap": overlap, "completed_at": _now(),
            }
            if transaction is not None:
                record["transaction_program"] = asdict(transaction)
                record["transaction_hash"] = transaction.transaction_hash
            _append_jsonl(candidates_path, record)
            _append_jsonl(calls, {**start, "status": "completed", "segment_hash": record["segment_hash"], "completed_at": _now()})
            completed[stage_candidate_id] = record
            made += 1
        except Exception as exc:
            failure_dir = root / "staged" / "failures" / stage
            failure_dir.mkdir(parents=True, exist_ok=True)
            path = failure_dir / f"{stage_candidate_id}.txt"
            atomic_write_text(path, "".join(parts))
            _append_jsonl(calls, {**start, "status": "failed", "error_type": type(exc).__name__, "error": str(exc), "partial_path": str(path), "failed_at": _now()})
            if isinstance(exc, SourceOverlapError):
                continue
    expected = len(jobs)
    terminal_ids = _terminal_call_ids(calls, "stage_candidate_id")
    if len(terminal_ids) < expected:
        return {"stage": stage, "new": made, "completed": len(completed), "terminal": len(terminal_ids), "expected": expected, "selection_ready": False}
    if len(completed) < int(spec["survivors"]):
        return {"stage": stage, "new": made, "completed": len(completed), "terminal": len(terminal_ids), "expected": expected, "selection_ready": False, "terminal_failure": True}
    selection_seed = int(sha256_text(campaign["campaign_hash"] + ":" + stage)[:8], 16)
    selected = _seeded_diverse_stage_selection(
        tuple(completed.values()), count=int(spec["survivors"]), seed=selection_seed,
    )
    selection = {
        "record_type": "AutoloomStageSelection", "campaign_hash": campaign["campaign_hash"],
        "stage": stage, "selection_seed": selection_seed,
        "selection_method": "seeded-quality-diversity-without-replacement",
        "candidate_count": len(completed),
        "terminal_failure_count": expected - len(completed),
        "eligible_pool": sum(bool(item["diagnostics"]["eligible"]) for item in completed.values()),
        "fallback_used": any(not item["diagnostics"]["eligible"] for item in selected),
        "selected": list(selected),
    }
    selection["selection_hash"] = hash_json(selection)
    write_json(root / "staged" / f"selection.{stage}.v1.json", selection)
    if stage == "aftermath":
        finalists: list[dict[str, Any]] = []
        for item in selected:
            text = target_runway(recipe, cell) + item["cumulative_completion"]
            overlap = anti_copy.check(item["stage_candidate_id"], text).to_dict()
            mechanical = calibration_gate(cell, _candidate_gate(cell, text, overlap, "stop"))
            finalists.append({
                "candidate_id": "staged." + item["stage_candidate_id"],
                "text": text, "text_hash": sha256_text(text),
                "lineage": [item["parent_id"], item["stage_candidate_id"]],
                "program_hash": item["program_hash"], "mechanical": mechanical,
                "overlap": overlap,
            })
        payload = {
            "record_type": "AutoloomStagedFinalists", "campaign_hash": campaign["campaign_hash"],
            "selection_hash": selection["selection_hash"], "finalists": finalists,
        }
        payload["finalists_hash"] = hash_json(payload)
        write_json(root / "staged" / "finalists.v1.json", payload)
    return {
        "stage": stage, "new": made, "completed": len(completed),
        "expected": expected, "selected": len(selected),
        "eligible_pool": sum(bool(item["diagnostics"]["eligible"]) for item in completed.values()),
        "selection_hash": selection["selection_hash"],
    }


def _candidate_similarity(left: str, right: str) -> float:
    a = _tokens(left)
    b = _tokens(right)
    return len(a & b) / max(1, len(a | b))


CLICHE_PATTERNS = (
    r"\bair (?:between them )?(?:thickened|crackled)\b",
    r"\btrail of fire\b",
    r"\b(?:hard|hot) and deep\b",
    r"\beyes? darkened\b",
    r"\bbreath (?:he|she|they) (?:didn't|hadn't) know[n]? (?:he|she|they) (?:was|were) holding\b",
    r"\bheat pooled\b",
    r"\bevery fiber of (?:his|her|their) being\b",
    r"\bpiercing (?:green|blue|gray|grey) eyes\b",
    r"\bpredatory (?:smile|grin)\b",
    r"\bbodies moved together\b",
    r"\bcarved from the same (?:stone|marble)\b",
    r"\bwarm and yielding\b",
    r"\bpleasure (?:broke|crashed|washed) (?:through|over)\b",
    r"\beach (?:movement|stroke) deliberate\b",
    r"\bmatching (?:her|his|their) (?:pace|rhythm)\b",
)


def calibration_gate(cell: BenchmarkCell, gate: Mapping[str, Any]) -> dict[str, Any]:
    """Add target-floor checks that generic canon gates intentionally omit."""

    result = json.loads(json.dumps(gate))
    diagnostics = result["diagnostics"]
    gates = result["gates"]
    heat = int(diagnostics["erotic_charge_signal"])
    anatomy = int(diagnostics["anatomical_specificity_signal"])
    completed = int(diagnostics["completed_intimacy_action_signal"])
    consent = int(diagnostics["consent_language_signal"])
    if cell.heat_band == "explicit":
        gates["heat_target_floor"] = heat >= 10 and anatomy >= 2 and completed >= 1
        gates["explicit_agency_visible"] = consent >= 2
    elif cell.heat_band == "open-door-nongraphic":
        gates["heat_target_floor"] = heat >= 5
    elif cell.heat_band == "charged-restraint":
        gates["heat_target_floor"] = heat >= 5
    else:
        gates["heat_target_floor"] = heat <= 1
    result["passed"] = all(bool(value) for value in gates.values())
    return result


def summarize(campaign_dir: str | Path, output: str | Path | None = None) -> dict[str, Any]:
    """Render an off-model, evidence-linked calibration summary."""

    root = Path(campaign_dir)
    campaign, _, _ = _load(root)
    candidates = list(_completed(root / "drafts" / "candidates.jsonl", "candidate_id").values())
    by_recipe: dict[str, list[dict[str, Any]]] = {}
    for item in candidates:
        by_recipe.setdefault(str(item["recipe_id"]), []).append(item)
    arms: list[dict[str, Any]] = []
    for recipe_id, items in sorted(by_recipe.items()):
        pairs = [
            _candidate_similarity(left["text"], right["text"])
            for index, left in enumerate(items)
            for right in items[index + 1:]
        ]
        gates = [item["mechanical"]["gates"] for item in items]
        arms.append(
            {
                "recipe_id": recipe_id,
                "candidate_count": len(items),
                "eligible_count": sum(bool(item["mechanical"]["passed"]) for item in items),
                "word_band_passes": sum(bool(item["word_band"]) for item in gates),
                "natural_stop_passes": sum(bool(item["natural_stop"]) for item in gates),
                "repetition_passes": sum(bool(item["no_repetition_loop"]) for item in gates),
                "word_counts": [item["mechanical"]["word_count"] for item in items],
                "mean_pairwise_token_jaccard": round(sum(pairs) / len(pairs), 4) if pairs else 0.0,
                "candidate_ids": [item["candidate_id"] for item in items],
            }
        )
    payload = {
        "record_type": "AutoloomCalibrationSummary",
        "campaign_hash": campaign["campaign_hash"],
        "candidate_count": len(candidates),
        "arms": arms,
    }
    payload["summary_hash"] = hash_json(payload)
    destination = Path(output) if output else root / "calibration_summary.v1.json"
    write_json(destination, payload)
    lines = [
        "# Base Autoloom Calibration",
        "",
        f"Campaign hash: `{campaign['campaign_hash']}`",
        f"Candidates: {len(candidates)}",
        "",
        "| Recipe | Eligible | Word band | Natural stop | Loop-free | Mean lexical overlap |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for arm in arms:
        total = arm["candidate_count"]
        lines.append(
            f"| {arm['recipe_id']} | {arm['eligible_count']}/{total} | "
            f"{arm['word_band_passes']}/{total} | {arm['natural_stop_passes']}/{total} | "
            f"{arm['repetition_passes']}/{total} | {arm['mean_pairwise_token_jaccard']:.3f} |"
        )
    markdown = destination.with_suffix(".md")
    atomic_write_text(markdown, "\n".join(lines) + "\n")
    return {**payload, "path": str(destination), "markdown": str(markdown)}
