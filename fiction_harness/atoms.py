"""Immutable dramatic occurrences for sparse novelist conditioning.

Local models are useful inventors of props, social moves, and reversals even
when their prose is unusable.  This module preserves those inventions as
source-backed records while rendering only a small, wording-neutral event
bundle to the downstream novelist.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import random
import re
from typing import Any, Mapping, Sequence

from .core import hash_json


ATOM_KINDS = frozenset(
    {
        "object",
        "speech_act",
        "social_move",
        "countermove",
        "observable_reaction",
        "constraint_change",
        "sensory_anchor",
        "romantic_action",
        "mystery_observation",
    }
)

_CONTROL_LANGUAGE = re.compile(
    r"\b(?:rubric|score|judge|pipeline|prompt|instruction|theme|lesson|"
    r"narrative\s+force|character\s+truth|epistemic\s+texture|"
    r"romantic\s+engine|theological\s+coherence)\b",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class DramaticAtom:
    atom_id: str
    scene_id: str
    sequence_id: str
    kind: str
    participants: tuple[str, ...]
    setup_fact: str
    observable_move: str
    observable_response: str
    local_constraint_change: str
    required_entities: tuple[str, ...]
    source_call_id: str
    source_text_hash: str
    source_span: str
    proposed_probability: float

    def __post_init__(self) -> None:
        if self.kind not in ATOM_KINDS:
            raise ValueError(f"unknown dramatic atom kind: {self.kind}")
        if not self.atom_id or not self.scene_id or not self.sequence_id:
            raise ValueError("atom identity fields cannot be empty")
        if not self.participants:
            raise ValueError("dramatic atom requires at least one participant")
        for field_name in (
            "setup_fact",
            "observable_move",
            "observable_response",
            "local_constraint_change",
            "source_call_id",
            "source_text_hash",
            "source_span",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"dramatic atom {field_name} cannot be empty")
        if not 0 < self.proposed_probability < 0.10:
            raise ValueError("atom probability must be greater than zero and below 0.10")
        visible = " ".join(
            (
                self.setup_fact,
                self.observable_move,
                self.observable_response,
                self.local_constraint_change,
            )
        )
        if _CONTROL_LANGUAGE.search(visible):
            raise ValueError("dramatic atom contains evaluator or prompt language")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DramaticAtom":
        expected = {field.name for field in cls.__dataclass_fields__.values()}
        unknown = set(value) - expected
        missing = expected - set(value)
        if unknown or missing:
            raise ValueError(
                f"invalid dramatic atom fields; missing={sorted(missing)}, "
                f"unknown={sorted(unknown)}"
            )
        payload = dict(value)
        payload["participants"] = tuple(payload["participants"])
        payload["required_entities"] = tuple(payload["required_entities"])
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class AtomBundle:
    bundle_id: str
    scene_id: str
    sequence_id: str
    ordered_atom_ids: tuple[str, ...]
    required_atom_ids: tuple[str, ...]
    optional_atom_ids: tuple[str, ...]
    source_pool_hash: str
    selection_policy_hash: str
    editorial_overlay: str
    editorial_overlay_hash: str
    bundle_hash: str = ""

    def __post_init__(self) -> None:
        ordered = tuple(self.ordered_atom_ids)
        if not 1 <= len(ordered) <= 6:
            raise ValueError("novelist-visible atom bundle must contain 1-6 atoms")
        if len(set(ordered)) != len(ordered):
            raise ValueError("atom bundle cannot repeat an atom")
        if set(self.required_atom_ids) | set(self.optional_atom_ids) != set(ordered):
            raise ValueError("required and optional atom IDs must partition ordered IDs")
        if set(self.required_atom_ids) & set(self.optional_atom_ids):
            raise ValueError("an atom cannot be both required and optional")
        if self.editorial_overlay and not self.editorial_overlay_hash:
            raise ValueError("editorial overlay must be hashed separately")
        computed = self.computed_hash()
        if self.bundle_hash and self.bundle_hash != computed:
            raise ValueError("atom bundle hash mismatch")
        if not self.bundle_hash:
            object.__setattr__(self, "bundle_hash", computed)

    def hash_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("bundle_hash", None)
        return payload

    def computed_hash(self) -> str:
        return hash_json(self.hash_payload())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AtomBundle":
        expected = {field.name for field in cls.__dataclass_fields__.values()}
        unknown = set(value) - expected
        missing = expected - set(value)
        if unknown or missing:
            raise ValueError(
                f"invalid atom bundle fields; missing={sorted(missing)}, "
                f"unknown={sorted(unknown)}"
            )
        payload = dict(value)
        for key in ("ordered_atom_ids", "required_atom_ids", "optional_atom_ids"):
            payload[key] = tuple(payload[key])
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class AtomRealization:
    atom_id: str
    status: str
    action_evidence: str
    consequence_evidence: str
    explanation_only: bool = False

    def __post_init__(self) -> None:
        if self.status not in {"realized", "partial", "omitted", "contradicted"}:
            raise ValueError(f"invalid atom realization status: {self.status}")
        if self.status == "realized":
            if not self.action_evidence or not self.consequence_evidence:
                raise ValueError("realized atom requires action and consequence evidence")
            if self.action_evidence == self.consequence_evidence:
                raise ValueError("action and consequence require separate evidence")
            if self.explanation_only:
                raise ValueError("explanation alone cannot realize a dramatic atom")


@dataclass(frozen=True, slots=True)
class AtomRealizationReport:
    candidate_id: str
    bundle_hash: str
    per_atom: tuple[AtomRealization, ...]
    endpoint_status: str
    invented_conflicts: tuple[str, ...]
    judge_id: str

    def __post_init__(self) -> None:
        if self.endpoint_status not in {"pass", "fail", "uncertain"}:
            raise ValueError("invalid atom realization endpoint status")
        ids = [item.atom_id for item in self.per_atom]
        if len(ids) != len(set(ids)):
            raise ValueError("atom realization report cannot repeat an atom")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def select_atoms_weighted_without_replacement(
    atoms: Sequence[DramaticAtom],
    *,
    count: int,
    seed: int,
) -> tuple[DramaticAtom, ...]:
    """Reproducibly sample valid atoms while respecting verbalized weights."""

    if not 0 < count <= min(6, len(atoms)):
        raise ValueError("atom selection count must be 1-6 and fit the pool")
    remaining = list(atoms)
    selected: list[DramaticAtom] = []
    rng = random.Random(seed)
    while len(selected) < count:
        total = sum(atom.proposed_probability for atom in remaining)
        threshold = rng.random() * total
        cumulative = 0.0
        chosen = remaining[-1]
        for atom in remaining:
            cumulative += atom.proposed_probability
            if cumulative >= threshold:
                chosen = atom
                break
        selected.append(chosen)
        remaining.remove(chosen)
    return tuple(selected)


def render_novelist_packet(
    *,
    manuscript_tail: str,
    current_state: Mapping[str, Any],
    character_invariants: Mapping[str, Any],
    word_range: tuple[int, int],
    endpoint: str,
    bundle: AtomBundle,
    atoms: Mapping[str, DramaticAtom],
) -> dict[str, Any]:
    """Return the sparse packet; provenance and donor wording stay outside it."""

    if word_range[0] < 1 or word_range[0] > word_range[1]:
        raise ValueError("invalid novelist word range")
    if set(bundle.ordered_atom_ids) - set(atoms):
        raise ValueError("atom bundle references missing atoms")
    occurrences = []
    for atom_id in bundle.ordered_atom_ids:
        atom = atoms[atom_id]
        if atom.scene_id != bundle.scene_id or atom.sequence_id != bundle.sequence_id:
            raise ValueError("atom does not belong to bundle scene and sequence")
        occurrences.append(
            {
                "atom_id": atom.atom_id,
                "required": atom.atom_id in bundle.required_atom_ids,
                "participants": list(atom.participants),
                "setup": atom.setup_fact,
                "move": atom.observable_move,
                "response": atom.observable_response,
                "constraint_change": atom.local_constraint_change,
            }
        )
    return {
        "task": (
            "Write only the next manuscript passage. The listed occurrences "
            "are facts to enact, not wording to reuse. Choose the dialogue, "
            "narration, transitions, imagery, and interpretation. Do not explain "
            "an occurrence after the action has already made it legible."
        ),
        "manuscript_tail": manuscript_tail,
        "current_state": dict(current_state),
        "character_invariants": dict(character_invariants),
        "sequence": {
            "scene_id": bundle.scene_id,
            "sequence_id": bundle.sequence_id,
            "minimum_words": word_range[0],
            "maximum_words": word_range[1],
            "endpoint": endpoint,
        },
        "occurrences": occurrences,
    }


def render_scene_novelist_packet(
    *,
    opening_runway: str,
    current_state: Mapping[str, Any],
    character_invariants: Mapping[str, Any],
    scene_contract: Mapping[str, Any],
    word_range: tuple[int, int],
    endpoint: str,
    phase_bundles: Sequence[AtomBundle],
    atoms: Mapping[str, DramaticAtom],
) -> dict[str, Any]:
    """Project several phase bundles into one provenance-free scene packet.

    The durable atom pool retains donor spans, probabilities, labels, and model
    lineage.  The novelist receives only observable occurrences, the scene
    contract, and a short opening runway.  This keeps exploration evidence on
    one side of the boundary and sentence ownership on the other.
    """

    if word_range[0] < 1 or word_range[0] > word_range[1]:
        raise ValueError("invalid novelist word range")
    if not phase_bundles:
        raise ValueError("scene novelist packet requires at least one phase bundle")
    scene_ids = {bundle.scene_id for bundle in phase_bundles}
    if len(scene_ids) != 1:
        raise ValueError("all phase bundles must belong to one scene")
    sequence_ids = [bundle.sequence_id for bundle in phase_bundles]
    if len(sequence_ids) != len(set(sequence_ids)):
        raise ValueError("scene novelist packet cannot repeat a phase")

    phases = []
    for bundle in phase_bundles:
        if set(bundle.ordered_atom_ids) - set(atoms):
            raise ValueError("phase bundle references missing atoms")
        occurrences = []
        for atom_id in bundle.ordered_atom_ids:
            atom = atoms[atom_id]
            if atom.scene_id != bundle.scene_id or atom.sequence_id != bundle.sequence_id:
                raise ValueError("atom does not belong to its phase bundle")
            occurrences.append(
                {
                    "atom_id": atom.atom_id,
                    "required": atom.atom_id in bundle.required_atom_ids,
                    "participants": list(atom.participants),
                    "setup": atom.setup_fact,
                    "move": atom.observable_move,
                    "response": atom.observable_response,
                    "constraint_change": atom.local_constraint_change,
                }
            )
        phases.append(
            {
                "phase_id": bundle.sequence_id,
                "minimum_words": word_range[0] // len(phase_bundles),
                "maximum_words": word_range[1] // len(phase_bundles),
                "occurrences": occurrences,
            }
        )

    return {
        "task": (
            "Write one complete manuscript scene. Enact the listed occurrences "
            "in phase order, but own every sentence, transition, image, and line "
            "of dialogue. The occurrences are facts, never wording to reuse. "
            "Trust action and consequence; do not append an explanation of what "
            "a legible beat means. Connecting actions may be invented when they "
            "respect the scene contract and endpoint."
        ),
        "opening_runway": opening_runway,
        "current_state": dict(current_state),
        "character_invariants": dict(character_invariants),
        "scene_contract": dict(scene_contract),
        "scene": {
            "scene_id": next(iter(scene_ids)),
            "minimum_words": word_range[0],
            "maximum_words": word_range[1],
            "endpoint": endpoint,
        },
        "phases": phases,
    }


def validate_atom_realization_report(
    *,
    candidate_text: str,
    bundle: AtomBundle,
    report: AtomRealizationReport,
) -> None:
    """Validate quoted enactment evidence without conflating it with quality."""

    if report.bundle_hash != bundle.bundle_hash:
        raise ValueError("atom realization report uses the wrong bundle")
    by_id = {item.atom_id: item for item in report.per_atom}
    if set(by_id) != set(bundle.ordered_atom_ids):
        raise ValueError("atom realization report must cover every bundled atom")
    for item in report.per_atom:
        for evidence in (item.action_evidence, item.consequence_evidence):
            if evidence and evidence not in candidate_text:
                raise ValueError(
                    f"atom realization evidence for {item.atom_id} is not an exact quote"
                )
    missing_required = [
        atom_id
        for atom_id in bundle.required_atom_ids
        if by_id[atom_id].status != "realized"
    ]
    if missing_required:
        raise ValueError(
            "required atoms were not realized: " + ", ".join(missing_required)
        )


def atom_role_distance(
    left: AtomBundle,
    right: AtomBundle,
    *,
    atoms: Mapping[str, DramaticAtom],
) -> float:
    """Compare event/participant/entity roles rather than surface n-grams."""

    def signature(bundle: AtomBundle) -> set[tuple[str, tuple[str, ...], tuple[str, ...]]]:
        result = set()
        for atom_id in bundle.ordered_atom_ids:
            atom = atoms[atom_id]
            result.add(
                (
                    atom.kind,
                    tuple(sorted(atom.participants)),
                    tuple(sorted(atom.required_entities)),
                )
            )
        return result

    left_signature = signature(left)
    right_signature = signature(right)
    union = left_signature | right_signature
    if not union:
        return 0.0
    return round(1.0 - len(left_signature & right_signature) / len(union), 6)
