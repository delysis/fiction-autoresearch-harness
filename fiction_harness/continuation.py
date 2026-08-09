"""S02 continuation generation with immutable prefixes and macro pacing.

The comparison deliberately shares one compact semantic packet, one approved
S01 prefix, and one deterministic three-sequence length controller.  It varies
only the proposal source and writer checkpoint:

* ``instruction_raw``: 31B instruction model through llama.cpp ``/completion``
  with its learned turn envelope supplied explicitly.
* ``chat_direct``: the same 31B instruction checkpoint through the chat API.
* ``base_program_to_instruction``: legacy E2B base proposals compiled and
  written by the 31B instruction model.
* ``base31_plan_to_instruction``: genuine 31B base-model plans locked unchanged;
  the 31B instruction writer receives their deterministic causal-event view.
* ``verbalized_to_instruction``: selected long-tail Verbalized Sampling plans
  are locked unchanged and realized from the same concrete-event projection.
* ``native_base``: genuine 31B base-model prose through raw continuation.

The legacy names ``raw_organic`` and ``hybrid_base_program`` remain readable so
that completed v1 artifacts retain valid lineage.  They are not used for new
v2 manifests.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
from pathlib import Path
import random
import re
from typing import Any, Mapping, Protocol, Sequence

from .anti_copy import AntiCopyIndex, SourceOverlapError, StreamingNgramGuard
from .author import ResolvedAuthorContext
from .core import hash_json, sha256_text, write_json
from .evaluation import literary_style_diagnostics, word_count, words
from .feedback import HumanFeedbackBrief, load_feedback_brief
from .model_client import Completion, LlamaClient
from .pipelines import (
    VerbalizedStrategy,
    _extract_json,
    deduplicate_strategies,
    parse_verbalized_strategies,
    verbalized_diversity_report,
    weighted_sample_without_replacement,
)
from .program_diversity import (
    analyze_batch_convergence,
    select_diverse_programs,
)
from .runtime import TraceStore, model_runtime_provenance, utc_now
from .schemas import Candidate, PersonaPacket, RunConfig, SceneSpec


CONTINUATION_VERSION = "s02-continuation.v4.1"
COMPARISON_VERSION = "s02-compute-comparison.v4.1"
INSTRUCTION_RAW_MODE = "instruction_raw"
CHAT_DIRECT_MODE = "chat_direct"
CHAT_PLANNED_MODE = "chat_with_base31_plan"
CHAT_REQUEST_PROFILE = "chat-no-thinking.v1"
NATIVE_BASE_PROMPT_PROFILE = "native-base-continuation.v2"
BASE_PROGRAM_MODE = "base_program_to_instruction"
BASE31_PLAN_MODE = "base31_plan_to_instruction"
VERBALIZED_MODE = "verbalized_to_instruction"
NATIVE_BASE_MODE = "native_base"
NATIVE_BASE_PLANNED_MODE = "native_base_with_base31_plan"
PRIMARY_COMPARISON_MODES = (
    INSTRUCTION_RAW_MODE,
    VERBALIZED_MODE,
    NATIVE_BASE_PLANNED_MODE,
)
LEGACY_INSTRUCTION_RAW_MODE = "raw_organic"
LEGACY_BASE_PROGRAM_MODE = "hybrid_base_program"
GENERATION_MODES = (
    INSTRUCTION_RAW_MODE,
    CHAT_DIRECT_MODE,
    CHAT_PLANNED_MODE,
    BASE_PROGRAM_MODE,
    BASE31_PLAN_MODE,
    VERBALIZED_MODE,
    NATIVE_BASE_MODE,
    NATIVE_BASE_PLANNED_MODE,
    LEGACY_INSTRUCTION_RAW_MODE,
    LEGACY_BASE_PROGRAM_MODE,
)
INSTRUCTION_PROGRAM_MODES = (
    BASE_PROGRAM_MODE,
    BASE31_PLAN_MODE,
    VERBALIZED_MODE,
    LEGACY_BASE_PROGRAM_MODE,
)
RAW_COMPLETION_MODES = tuple(
    mode for mode in GENERATION_MODES if mode not in {CHAT_DIRECT_MODE, CHAT_PLANNED_MODE}
)

# The audit packet retains the full source-backed mechanism deck.  The novelist
# only needs mechanisms that can become observable action in this episode;
# exposing every theological and epistemic proposition made the prose explain
# the rubric after dramatizing it.
S02_GENERATION_MECHANISM_IDS = frozenset({"MPC-04", "MPC-13", "LEV-04", "LEV-05"})
DEFAULT_SEEDS = (22011, 22023, 22037, 22051, 22063, 22079, 22091, 22109)


def canonical_generation_mode(mode: str) -> str:
    return {
        LEGACY_INSTRUCTION_RAW_MODE: INSTRUCTION_RAW_MODE,
        LEGACY_BASE_PROGRAM_MODE: BASE_PROGRAM_MODE,
    }.get(mode, mode)


def is_native_base_mode(mode: str) -> bool:
    return mode in {NATIVE_BASE_MODE, NATIVE_BASE_PLANNED_MODE}


def is_chat_mode(mode: str) -> bool:
    return mode in {CHAT_DIRECT_MODE, CHAT_PLANNED_MODE}


@dataclass(frozen=True, slots=True)
class ApprovedPrefix:
    label: str
    candidate_id: str
    text: str
    text_hash: str

    def __post_init__(self) -> None:
        if self.label not in {"A", "B", "C"}:
            raise ValueError("approved prefix label must be A, B, or C")
        if not self.candidate_id or not self.text:
            raise ValueError("approved prefix requires a candidate and text")
        if self.text_hash != sha256_text(self.text):
            raise ValueError("approved prefix text hash mismatch")

    @property
    def approved_prefix_id(self) -> str:
        return f"s01-finalist-{self.label}:{self.candidate_id}"

    def tail(self, maximum_words: int = 500) -> str:
        words = self.text.split()
        return " ".join(words[-maximum_words:])


@dataclass(frozen=True, slots=True)
class MacroSequence:
    sequence_id: str
    title: str
    beat_numbers: tuple[int, ...]
    minimum_words: int
    target_words: int
    maximum_words: int
    endpoint: str
    ending_visible: bool = False

    def __post_init__(self) -> None:
        if not self.sequence_id or not self.title or not self.endpoint:
            raise ValueError("macro sequence identifiers and endpoint are required")
        if not self.beat_numbers:
            raise ValueError("macro sequence requires at least one beat")
        if not 0 < self.minimum_words <= self.target_words <= self.maximum_words:
            raise ValueError("macro sequence word bounds must be positive and ordered")


S02_MACRO_SEQUENCES = (
    MacroSequence(
        sequence_id="s02-seq-1-trap",
        title="Care becomes a trap",
        beat_numbers=(1, 2, 3),
        minimum_words=875,
        target_words=950,
        maximum_words=1_100,
        endpoint=(
            "End with Mara less able to act because her initially plausible "
            "coping policy has narrowed her choices. Livia must have perceived one difficult thing "
            "accurately while overclaiming what that accuracy entitles her to do. "
            "Do not resolve the session or preview the walk home."
        ),
    ),
    MacroSequence(
        sequence_id="s02-seq-2-refusal",
        title="The room discovers it has no category for no",
        beat_numbers=(4, 5, 6),
        minimum_words=875,
        target_words=950,
        maximum_words=1_100,
        endpoint=(
            "End after Mara herself has changed the room's available choices "
            "through a refusal, question, or concrete action. The exit must now "
            "be possible because of what Mara did; stop before anyone ratifies it."
        ),
    ),
    MacroSequence(
        sequence_id="s02-seq-3-doorway",
        title="Exit, restraint, and the doorway rule",
        beat_numbers=(7, 8, 9),
        minimum_words=1_100,
        target_words=1_250,
        maximum_words=1_400,
        endpoint=(
            "Resolve the local boundary crisis with romantic hope-for-now: "
            "one mutually chosen kiss stops while still desired, the pair creates "
            "a shared stopping practice in their own character-specific language, "
            "and Mara freely chooses continued engagement. Jonah's restraint must "
            "cost or expose him, and a concrete unresolved Fulcrum observation "
            "must create the next story question."
        ),
        ending_visible=True,
    ),
)


def literary_scene_spec(scene: SceneSpec) -> SceneSpec:
    """Return the v4 generation view without altering trusted-read provenance.

    The source scene card remains the canonical statement of intent.  The old
    prompt repeated its exact image, dialogue logic, aphorism, and endpoint so
    faithfully that every sampled scene occupied the same causal cluster.  The
    v4 view preserves required state changes while restoring meaningful degrees
    of freedom over action, error, cost, speech, and suspense.
    """

    return replace(
        scene,
        opening_image=(
            "Near the end of an overlong alignment session, genuine care has "
            "made an ordinary attempt to stop socially and institutionally costly."
        ),
        turn=(
            "After first making the situation worse, Mara uses prayerful attention "
            "or a practiced pause to distinguish a possibly true observation from "
            "the claim that another person owns its meaning. Her own action creates "
            "an exit condition; Miriam may protect it but does not create Mara's agency."
        ),
        aftermath=(
            "Jonah walks Mara home without demanding a report. His restraint has an "
            "observable cost or reveals a prior failure. A mutually chosen kiss stops "
            "while desired; their stopping practice grows from the encounter rather "
            "than arriving as a polished maxim, and a concrete external fact hooks S03."
        ),
        teaching_payload=(
            "For evaluator use only: truthful attention can receive an uncomfortable "
            "observation without surrendering judgment or freedom; chastity directs "
            "desire toward more exact perception and love."
        ),
        beat_map=(
            "Livia does something concretely kind, notices a physical cue, and says one difficult thing that is substantially true. Her truth offers Mara a form of recognition or belonging she actually wants; the work at stake matters beyond the group's curiosity.",
            "Livia acts on that true perception in a way that leaves Mara fewer choices. Dramatize the move without having the narrator label its logic.",
            "To keep both her friendship and her place, Mara tries a locally intelligent tactic. It backfires in an observable way and costs her something in the room.",
            "An embodied response complicates the conflict and could support at least two readings. Preserve the evidence without having the narrator enumerate the readings.",
            "Mara uses a specifically Christian prayer or practice. It gives her one next perception or act while fear, anger, attraction, or confusion remains active; it is neither a sermon nor instant serenity or perfect articulation.",
            "Mara herself makes exit possible through a consequential action, refusal, or question. Fulcrum cannot instantly absorb what she did.",
            "Miriam protects the available exit through action and loses or risks something observable. She does not explain the scene.",
            "Jonah walks Mara home and admits, risks, loses, or repairs something concrete. His restraint is visible effort, and Mara's attraction appears through selective sensation and choice.",
            "They choose a kiss and stop while both still want more. Their next-time practice sounds like them, changes the relationship, and a specific record, object, or signal creates the next question.",
        ),
        continuity_facts=(
            "Livia cares for Mara and is right about one difficult fact, while her action still constricts Mara's freedom.",
            "Mara makes exit possible before Miriam protects it; both women incur an observable cost.",
            "Jonah's restraint includes an observable cost, failure, confession, or repair.",
            "A specifically Christian practice changes Mara's perception or action on the page.",
            "One mutually chosen kiss stops while both still desire more.",
            "Mara freely chooses a next step, and one specific unresolved piece of evidence hooks S03.",
            "There is no consummation, graphic anatomy, or punishment for stopping.",
        ),
    )


class WriterClient(Protocol):
    model: str

    def complete(self, **kwargs: Any) -> Completion:
        ...

    def stream_raw(self, **kwargs: Any) -> Completion:
        ...


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected a JSON object: {path}")
    return value


def load_s02_compilation(
    compiled_dir: str | Path,
) -> tuple[SceneSpec, tuple[PersonaPacket, ...], dict[str, Any], dict[str, Any]]:
    root = Path(compiled_dir)
    scene = SceneSpec.from_dict(_load_json(root / "scene_specs" / "s02.v1.json"))
    persona_bundle = _load_json(root / "personas" / "fulcrum_pilot.v1.json")
    personas = tuple(
        PersonaPacket.from_dict(item)
        for item in persona_bundle.get("personas", ())
    )
    if not personas:
        raise ValueError("compiled S02 bundle contains no personas")
    profile = _load_json(root / "profiles" / "resolved_profile.v1.json")
    source_packet = _load_json(root / "sources" / "s02_source_packet.v1.json")
    return scene, personas, profile, source_packet


def load_approved_prefix(
    *,
    finalists_path: str | Path,
    reveal_key_path: str | Path,
    feedback_brief: HumanFeedbackBrief,
) -> ApprovedPrefix:
    finalists_payload = _load_json(Path(finalists_path))
    finalists = finalists_payload.get("finalists", ())
    if not isinstance(finalists, Sequence):
        raise TypeError("finalists payload must contain a sequence")
    by_id = {
        str(item.get("candidate_id", "")): item
        for item in finalists
        if isinstance(item, Mapping)
    }
    reveal = _load_json(Path(reveal_key_path))
    labels = reveal.get("labels", {})
    if not isinstance(labels, Mapping):
        raise TypeError("reveal key labels must be an object")
    identity = labels.get(feedback_brief.winner_label)
    if not isinstance(identity, Mapping):
        raise ValueError(
            f"feedback winner {feedback_brief.winner_label} is absent from reveal key"
        )
    candidate_id = str(identity.get("candidate_id", ""))
    candidate = by_id.get(candidate_id)
    if not isinstance(candidate, Mapping):
        raise ValueError(f"approved finalist is missing: {candidate_id}")
    text = str(candidate.get("text", ""))
    expected = str(identity.get("text_sha256", ""))
    actual = sha256_text(text)
    if expected and expected != actual:
        raise ValueError("approved S01 finalist hash mismatch")
    return ApprovedPrefix(
        label=feedback_brief.winner_label,
        candidate_id=candidate_id,
        text=text,
        text_hash=actual,
    )


def _persona_summary(personas: Sequence[PersonaPacket]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for persona in personas:
        summary.append(
            {
                "name": persona.name,
                "role": persona.role,
                "invariants": list(persona.invariants[:4]),
                "contradictions": list(persona.contradictions[:2]),
                "relationships": {
                    relation: list(traits[:2])
                    for relation, traits in sorted(
                        persona.relationship_variants.items()
                    )
                },
            }
        )
    return summary


def compact_story_packet(
    *,
    scene: SceneSpec,
    personas: Sequence[PersonaPacket],
    profile: Mapping[str, Any],
    source_packet: Mapping[str, Any],
    feedback: HumanFeedbackBrief,
    approved_prefix: ApprovedPrefix,
    author_context: ResolvedAuthorContext | None = None,
) -> dict[str, Any]:
    """Build a focused packet without the old production/marketing brief.

    Source cards are reduced to their dramatic use and mechanism.  Retail
    mappings, ontology jargon that is not selected, and source URLs stay out.
    """

    cards = []
    for item in source_packet.get("cards", ()):
        if not isinstance(item, Mapping):
            continue
        cards.append(
            {
                "id": str(item.get("source_id", "")),
                "mechanism": str(item.get("evidence_or_dynamic", "")),
                "dramatic_use": str(item.get("dramatic_use", "")),
            }
        )
    winning_label = feedback.winner_label
    packet = {
        "version": CONTINUATION_VERSION,
        "story_contract": {
            "pov": "Close third-person Mara; no sustained access to other minds.",
            "genre": "Contemporary Christian romantic suspense.",
            "relationship": (
                "Adult monogamous slow burn toward marriage; attraction must "
                "increase freedom, perception, trust, and meaningful choice."
            ),
            "world_status": (
                "Keep ordinary and extraordinary explanations live. Do not "
                "confirm either paranormal causation or its absence."
            ),
            "heat": (
                "High embodied attention without graphic anatomy or consummation. "
                "The mutually wanted kiss stops while still desired."
            ),
            "intimacy_craft": (
                "Character before mechanics; emotional exchange; selective "
                "sensation; dialogue and atmosphere; contact changes the story."
            ),
        },
        "scene": {
            "id": scene.scene_id,
            "title": scene.title,
            "opening_image": scene.opening_image,
            "desire": scene.desire,
            "obstacle": scene.obstacle,
            "turn": scene.turn,
            "aftermath": scene.aftermath,
            "teaching": scene.teaching_payload,
            "pressure_ladder": list(scene.pressure_ladder),
            "beats": list(scene.beat_map),
            "continuity": list(scene.continuity_facts),
        },
        "characters": _persona_summary(personas),
        "mechanisms": cards,
        "reader_feedback": {
            "source_kind": feedback.source_kind,
            "winning_s01_label": winning_label,
            "preserve": list(feedback.strengths.get(winning_label, ()))[:8],
            "avoid": list(feedback.defects.get(winning_label, ()))[:8],
            "desired_next": list(feedback.desired_next.get(winning_label, ()))[:8],
        },
        "approved_prefix": {
            "id": approved_prefix.approved_prefix_id,
            "hash": approved_prefix.text_hash,
            # Long context is cheap under prefix caching and the accepted prior
            # scene is the strongest available continuity/voice exemplar.
            "full_text": approved_prefix.text,
        },
        "selected_profile": {
            "heat_target": str(profile.get("heat_target", "")),
            "heat_ceiling": str(profile.get("heat_ceiling", "")),
            "atmosphere": str(profile.get("atmosphere", "")),
            "pacing": list(profile.get("pacing", ())),
            "prompt_obligations": list(profile.get("prompt_obligations", ()))[:18],
            "prohibited": list(profile.get("prohibited", ())),
        },
    }
    if author_context is not None:
        packet["author_conditioning"] = {
            **author_context.to_dict(),
            "context_hash": author_context.context_hash,
        }
    return packet


def packet_word_count(packet: Mapping[str, Any]) -> int:
    return word_count(json.dumps(packet, ensure_ascii=False))


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _xml_value(name: str, value: Any) -> str:
    if isinstance(value, Mapping):
        body = "".join(
            _xml_value(str(key).replace("_", "-"), item)
            for key, item in sorted(value.items())
        )
        return f"<{name}>{body}</{name}>"
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        body = "".join(_xml_value("item", item) for item in value)
        return f"<{name}>{body}</{name}>"
    return f"<{name}>{_xml_escape(str(value))}</{name}>"


def render_compact_packet(packet: Mapping[str, Any]) -> str:
    return _xml_value("continuation-context", packet)


def generation_story_packet(
    packet: Mapping[str, Any],
) -> dict[str, Any]:
    """Project the audit packet into a lighter prose/planning context.

    The complete accepted S01 and evaluator-facing ontology remain in the
    versioned audit packet.  They are deliberately absent from generation: the
    former had become a mediocre house-style demonstration and the latter made
    models narrate the rubric. A factual state bridge supplies local continuity
    while preserving the immutable source hash. This deliberately avoids
    few-shotting recurrent cadence defects from the accepted prose.
    """

    approved = dict(packet.get("approved_prefix", {}))
    contract = dict(packet.get("story_contract", {}))
    scene = dict(packet.get("scene", {}))
    mechanisms: list[dict[str, str]] = []
    for item in packet.get("mechanisms", ()):
        if isinstance(item, Mapping):
            mechanism_id = str(item.get("id", ""))
            if mechanism_id in S02_GENERATION_MECHANISM_IDS:
                mechanisms.append(
                    {
                        "id": mechanism_id,
                        "observable_mechanism": str(item.get("mechanism", "")),
                    }
                )
    selected_profile = dict(packet.get("selected_profile", {}))
    author_conditioning = dict(packet.get("author_conditioning", {}))
    author_payload = author_conditioning.get("prompt_payload")
    if isinstance(author_payload, Mapping):
        # Corpus-level punctuation and length statistics are valuable for
        # evaluation but become awkward pseudo-rules in a prose prompt. Keep
        # the backtranslated craft mechanisms and negative space only.
        author_conditioning["prompt_payload"] = {
            key: value
            for key, value in author_payload.items()
            if key != "distributions"
        }
    return {
        "version": CONTINUATION_VERSION,
        "story_contract": {
            key: contract.get(key, "")
            for key in ("pov", "genre", "relationship", "world_status", "heat")
        },
        "scene_state": {
            key: scene.get(key)
            for key in (
                "id",
                "title",
                "opening_image",
                "desire",
                "obstacle",
                "pressure_ladder",
            )
        },
        "characters": list(packet.get("characters", ())),
        "observable_mechanisms": mechanisms,
        "author_conditioning": author_conditioning,
        "accepted_story_continuity": {
            "id": approved.get("id", ""),
            "hash": approved.get("hash", ""),
            "state_bridge": (
                "S01 ended after Mara disrupted Livia's nonverbal calibration "
                "by controlling the cues others were reading. Most apparent "
                "accuracy collapsed, while Jonah's precisely timed wrist "
                "pressure and recognition remained unexplained. Mara chose to "
                "continue at Fulcrum as an experiment; she is attracted to "
                "Jonah and still uncertain whether she belongs."
            ),
            "use": "Factual continuity only; it is not a prose exemplar.",
        },
        "hard_limits": {
            "heat_ceiling": selected_profile.get("heat_ceiling", ""),
            "prohibited": list(selected_profile.get("prohibited", ())),
        },
    }


def render_generation_packet(packet: Mapping[str, Any]) -> str:
    return render_compact_packet(generation_story_packet(packet))


def wrap_gemma_raw(*, system: str, user: str, lead: str = "") -> str:
    """Manually provide Gemma's learned turn delimiters on ``/completion``.

    The server still applies no chat template and the harness controls every
    byte.  An instruction checkpoint degenerates when asked to continue an
    arbitrary XML suffix that omits its learned turn grammar; this minimal
    envelope makes raw sampling a meaningful "base-like" experiment.
    """

    return (
        "<|turn>system\n"
        + system.strip()
        + "<turn|>\n<|turn>user\n"
        + user.strip()
        + "<turn|>\n<|turn>model\n"
        + lead
    )


_REALIZATION_PROGRAM_FIELD_RE = re.compile(
    r"(?mi)^(TITLE|PREMISE|ANTAGONIST TRUTH|PROTAGONIST ERROR|EXIT AGENCY|PROTECTOR COST|"
    r"LOVER COST|INSTITUTIONAL CONSEQUENCE|UNCANNY REMAINDER|"
    r"SEQUENCE ONE(?:\s+—[^:\n]+)?|SEQUENCE TWO(?:\s+—[^:\n]+)?|"
    r"SEQUENCE THREE(?:\s+—[^:\n]+)?|DISTINCTIVE OBJECTS AND TACTICS|"
    r"ROMANTIC ENGINE|EPISTEMIC TURN|RELATIONSHIP DELTA|CAUSAL REPAIR|"
    r"LOCKED END STATES)\s*:\s*"
)

_REALIZATION_PROGRAM_FIELDS = {
    "ANTAGONIST TRUTH",
    "PROTAGONIST ERROR",
    "EXIT AGENCY",
    "PROTECTOR COST",
    "LOVER COST",
    "INSTITUTIONAL CONSEQUENCE",
    "UNCANNY REMAINDER",
    "SEQUENCE ONE",
    "SEQUENCE TWO",
    "SEQUENCE THREE",
    "DISTINCTIVE OBJECTS AND TACTICS",
    "CAUSAL REPAIR",
    "LOCKED END STATES",
}

_BASE_SEQUENCE_PROGRAM_FIELDS = {
    "s02-seq-1-trap": {
        "ANTAGONIST TRUTH",
        "PROTAGONIST ERROR",
        "SEQUENCE ONE",
        "DISTINCTIVE OBJECTS AND TACTICS",
    },
    "s02-seq-2-refusal": {
        "PROTAGONIST ERROR",
        "EXIT AGENCY",
        "PROTECTOR COST",
        "INSTITUTIONAL CONSEQUENCE",
        "UNCANNY REMAINDER",
        "SEQUENCE TWO",
        "DISTINCTIVE OBJECTS AND TACTICS",
    },
    "s02-seq-3-doorway": {
        "PROTECTOR COST",
        "LOVER COST",
        "INSTITUTIONAL CONSEQUENCE",
        "UNCANNY REMAINDER",
        "SEQUENCE THREE",
        "DISTINCTIVE OBJECTS AND TACTICS",
        "LOCKED END STATES",
    },
}

_BASE_BEAT_BACKTRANSLATIONS = {
    "s02-seq-1-trap": (
        "Livia's small practical kindness meets a need Mara has concealed. A "
        "physical detail leads Livia to one painful, mostly accurate observation.",
        "Livia uses that observation in a concrete way that makes one particular "
        "course of action harder for Mara.",
        "Mara protects a valued bond or status with a specific action. Someone's "
        "observable response leaves her worse off in the room.",
    ),
    "s02-seq-2-refusal": (
        "A change in breath, posture, touch, temperature, or timing complicates "
        "what just happened without explaining it.",
        "A brief Christian prayer or bodily practice lets Mara notice one usable "
        "fact or take one next action while her mixed feelings remain.",
        "Mara says or does the particular thing that makes leaving practically "
        "possible. Fulcrum's people cannot immediately turn it into agreement.",
    ),
    "s02-seq-3-doorway": (
        "Miriam makes the exit usable and accepts a visible professional or "
        "relational consequence for doing so.",
        "On the walk home Jonah discloses, risks, loses, or repairs something "
        "specific. Mara notices the effort his restraint costs him.",
        "Mara and Jonah choose a kiss, stop while both want more, and invent one "
        "brief next-time practice in their own idiom. A physical record, object, "
        "or signal leaves one new question.",
    ),
}

_BASE_ENDPOINT_BACKTRANSLATIONS = {
    "s02-seq-1-trap": (
        "The final exchange leaves Mara inside the session with one fewer "
        "practical option than she had at the start. The session is still "
        "underway, and Jonah has not walked her home."
    ),
    "s02-seq-2-refusal": (
        "The last beat is Mara saying or doing the thing that changes what the "
        "others can do next. The door has not yet been opened, and nobody has "
        "ratified her exit."
    ),
    "s02-seq-3-doorway": (
        "Mara gets safely out; Miriam visibly pays for protecting that exit; "
        "Jonah walks Mara home and makes his restraint costly rather than easy; "
        "Mara and Jonah choose a kiss, stop together while desire remains, and "
        "Mara chooses the terms of seeing him again. End on one unexplained "
        "physical fact at Fulcrum."
    ),
}

_BASE_PROGRAM_LABELS = {
    "ANTAGONIST TRUTH": "Livia's accurate observation",
    "PROTAGONIST ERROR": "Mara's immediate misstep",
    "EXIT AGENCY": "What Mara changes",
    "PROTECTOR COST": "What Miriam risks or loses",
    "LOVER COST": "What Jonah risks, loses, or repairs",
    "INSTITUTIONAL CONSEQUENCE": "What changes at Fulcrum",
    "UNCANNY REMAINDER": "Unexplained physical observation",
    "SEQUENCE ONE": "Possible event chain",
    "SEQUENCE TWO": "Possible event chain",
    "SEQUENCE THREE": "Possible event chain",
    "DISTINCTIVE OBJECTS AND TACTICS": "Useful objects and actions",
    "LOCKED END STATES": "Required closing actions",
}

BASE_PROSE_SENTINEL = "<<<S02_PROSE_CONTINUES>>>"
BASE_S02_OPENING_FRAGMENT = (
    "By the time Livia moved the glass of water within Mara's reach, the "
    "alignment session had gone twenty-three minutes past its promised end."
)

_PACKET_LEAK_MARKERS = (
    "## Locked story state",
    "## Current sequence notes",
    "## Drafting note",
    "## Editorial target",
    "## Draft to compress",
    "## Manuscript revision packet",
    "## Manuscript compression packet",
    "# SOURCE MATERIAL",
    "## Manuscript Continuation",
    "### Technical Requirements",
    "# FICTION CONTINUATION DOSSIER",
    "# NOVELIST'S LONG-CONTEXT WORKING FILE",
    "EDITORIAL APPRENTICESHIP ARCHIVE",
    "NEW PROJECT PREPARATION",
    "TARGET STORY BIBLE",
    "TARGET SUBMOVEMENT LEDGER",
    "LOCAL LENGTH BAND",
    "<fiction-preparation>",
    "</fiction-preparation>",
    "<research-archive>",
    "</research-archive>",
    "<story-contract>",
    "</story-contract>",
    "<manuscript>",
    "</manuscript>",
    "## Required endpoint",
    "## Replacement tail",
    "## Final words",
    "The story has reached its conclusion",
    "The syntax has reached",
    "The syntax has",
    "<continuation-context",
    "&lt;continuation-context",
    "<sequence-input",
    "<short-sequence-repair",
    BASE_PROSE_SENTINEL,
)

_CONTROL_XML_FRAGMENT_RE = re.compile(
    r"</?(?:item|id|axis|strength|activation-conditions|creative-obligations|"
    r"distribution|prompt-payload|author-conditioning|scene-state|"
    r"observable-mechanisms|hard-limits|sequence|selected-story-program-hash)"
    r"(?:\s[^>]*)?>",
    flags=re.IGNORECASE,
)

_BASE_STOCK_PROSE_PATTERNS = {
    "piercing_eyes": r"\bpiercing (?:green|blue|dark|gray|grey|brown) eyes\b",
    "air_thick_with": r"\bthe air (?:was |felt )?thick with\b",
    "wave_of_relief": r"\ba wave of relief\b",
    "felt_a_sense_of": r"\bfelt a sense of\b",
    "one_thing_for_certain": r"\bone thing (?:was|for) certain\b",
    "see_through_walls": r"\bsee(?:med)? right through (?:her|his|their) walls\b",
    "laid_bare": r"\b(?:insides|thoughts|soul|heart) (?:were|was) laid bare\b",
    "that_was_a_start": r"\band that was a start\b",
}


class PacketLeakageError(ValueError):
    """Raised when prose contains serialized prompt or editorial scaffolding."""


def packet_leakage_markers(text: str) -> tuple[str, ...]:
    folded = text.casefold()
    markers = [
        marker for marker in _PACKET_LEAK_MARKERS if marker.casefold() in folded
    ]
    if len(_CONTROL_XML_FRAGMENT_RE.findall(text)) >= 3:
        markers.append("serialized-control-xml")
    if len(re.findall(r"\bausten\.[a-z0-9.-]+", text, re.IGNORECASE)) >= 2:
        markers.append("serialized-author-affordances")
    return tuple(markers)


def require_packet_clean_prose(text: str, *, call_id: str) -> str:
    markers = packet_leakage_markers(text)
    if markers:
        raise PacketLeakageError(
            f"{call_id} returned prompt-packet material: {', '.join(markers)}"
        )
    return text


def _control_phrase_overlap(
    prose: str,
    control_text: str,
    *,
    ngram: int = 4,
) -> dict[str, Any]:
    prose_words = words(prose)
    control_words = words(control_text)
    control_ngrams = {
        tuple(control_words[index : index + ngram])
        for index in range(max(0, len(control_words) - ngram + 1))
    }
    matches: list[str] = []
    seen: set[tuple[str, ...]] = set()
    for index in range(max(0, len(prose_words) - ngram + 1)):
        phrase = tuple(prose_words[index : index + ngram])
        if phrase in control_ngrams and phrase not in seen:
            seen.add(phrase)
            matches.append(" ".join(phrase))
    return {
        "ngram": ngram,
        "unique_match_count": len(matches),
        "examples": matches[:12],
        "interpretation": (
            "Exact control-language overlap is an editorial lead, not a hard "
            "gate; names and necessary facts can create innocent matches."
        ),
    }


def sequence_checkpoint_diagnostics(
    prose: str,
    *,
    program: str,
    sequence: MacroSequence,
) -> dict[str, Any]:
    controls = "\n".join(
        (
            *(_BASE_BEAT_BACKTRANSLATIONS[sequence.sequence_id]),
            _BASE_ENDPOINT_BACKTRANSLATIONS[sequence.sequence_id],
            realization_story_program_for_sequence(program, sequence),
        )
    )
    stock_hits = {
        label: [match.group(0) for match in re.finditer(pattern, prose, re.I)][:6]
        for label, pattern in _BASE_STOCK_PROSE_PATTERNS.items()
    }
    stock_hits = {label: values for label, values in stock_hits.items() if values}
    return {
        "record_type": "SequenceCheckpointDiagnostics",
        "sequence_id": sequence.sequence_id,
        "word_count": word_count(prose),
        "packet_leakage_markers": list(packet_leakage_markers(prose)),
        "control_phrase_overlap": _control_phrase_overlap(prose, controls),
        "stock_prose_hits": stock_hits,
        "literary_style": literary_style_diagnostics(prose),
    }


def _tail_preserving_layout(text: str, maximum_words: int) -> str:
    """Keep the last words of a manuscript without flattening its paragraphs."""

    tokens = list(re.finditer(r"\S+", text))
    if len(tokens) <= maximum_words:
        return text.strip()
    return text[tokens[-maximum_words].start() :].strip()


def base_generation_context(compact_prefix: str) -> str:
    """Hide future beats and the prose-free S01 bridge from a base writer.

    The full packet remains in the run manifest.  Native continuation receives
    real manuscript history instead, plus only scene facts that do not reveal
    later sequence solutions.
    """

    value = compact_prefix
    for tag in (
        "accepted-story-continuity",
        "pressure-ladder",
        "beats",
        "continuity",
        # Provenance and evaluator structure remain in run records.  A native
        # writer needs the positive craft delta, not database identifiers,
        # confidence metadata, or phrases framed as prohibitions.
        "author-name",
        "author-profile-hash",
        "author-profile-id",
        "conditioning-variant",
        "context-hash",
        "control-density",
        "corpus-manifest-hash",
        "prompt-encoding",
        "selected-affordance-ids",
        "source-id",
        "transformation-map-hash",
        "activation-conditions",
        "axis",
        "distribution",
        "id",
        "strength",
        "author-label",
        "profile-id",
        "negative-space",
    ):
        value = re.sub(
            rf"<{tag}>.*?</{tag}>",
            "",
            value,
            flags=re.IGNORECASE | re.DOTALL,
        )
    return (
        value.replace("<author-conditioning>", "<fiction-craft>")
        .replace("</author-conditioning>", "</fiction-craft>")
        .replace("<prompt-payload>", "")
        .replace("</prompt-payload>", "")
        .replace("<affordances>", "<craft-tendencies>")
        .replace("</affordances>", "</craft-tendencies>")
        .replace("<creative-obligations>", "<tendency>")
        .replace("</creative-obligations>", "</tendency>")
        .replace("<author-subgenre-delta>", "<combined-story-tendencies>")
        .replace("</author-subgenre-delta>", "</combined-story-tendencies>")
    )


def realization_story_program_for_sequence(
    program: str,
    sequence: MacroSequence,
) -> str:
    """Project a frozen plan into present-tense affordances for one sequence.

    Later exits, kisses, and institutional consequences must not become prose
    merely because the whole plan was available in a serialized prompt.
    """

    allowed = _BASE_SEQUENCE_PROGRAM_FIELDS.get(sequence.sequence_id, set())
    matches = list(_REALIZATION_PROGRAM_FIELD_RE.finditer(program))
    if len(matches) < 5:
        return program.strip() if sequence.ending_visible else ""
    fields: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(program)
        value = program[match.end() : end].strip()
        raw_label = match.group(1).upper()
        label = raw_label.split(" —", 1)[0]
        if value and label in allowed:
            fields.append(f"{_BASE_PROGRAM_LABELS[label]}: {value}")
    return "\n".join(fields).strip()


def realization_story_program(program: str) -> str:
    """Expose concrete causal coordinates, not the planner's thesis labels.

    Plan ranking benefits from abstract coordinates such as epistemic turn and
    relationship delta.  Showing those labels to the novelist, however, invites
    detachable morals and emotionally smoothed summaries.  Preserve the full
    locked plan in provenance while rendering only actions, costs, observations,
    sequence events, and hard end states into the prose prompt.
    """

    matches = list(_REALIZATION_PROGRAM_FIELD_RE.finditer(program))
    if len(matches) < 5:
        return program.strip()
    fields: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(program)
        value = program[match.end() : end].strip()
        raw_label = match.group(1).upper()
        label = raw_label.split(" —", 1)[0]
        if value and label in _REALIZATION_PROGRAM_FIELDS:
            fields.append(f"{raw_label}: {value}")
    return "\n".join(fields).strip()


def _sequence_payload(
    *,
    scene: SceneSpec,
    sequence: MacroSequence,
    completed_text: str,
    program: str,
) -> dict[str, Any]:
    selected_beats = [
        {"number": number, "beat": beat}
        for number, beat in zip(
            sequence.beat_numbers,
            _BASE_BEAT_BACKTRANSLATIONS[sequence.sequence_id],
        )
    ]
    return {
        "sequence": {
            "id": sequence.sequence_id,
            "title": sequence.title,
            "word_target": sequence.target_words,
            "word_minimum": sequence.minimum_words,
            "word_maximum": sequence.maximum_words,
            "required_beats": selected_beats,
            "endpoint": _BASE_ENDPOINT_BACKTRANSLATIONS[sequence.sequence_id],
            "ending_visible": sequence.ending_visible,
        },
        "prior_new_prose": completed_text[-12_000:],
        "selected_causal_event_brief": realization_story_program_for_sequence(
            program,
            sequence,
        ),
        "selected_story_program_hash": sha256_text(program) if program else "",
    }


def _base_sequence_payload(
    *,
    scene: SceneSpec,
    sequence: MacroSequence,
    program: str,
) -> dict[str, Any]:
    """A sequence-local payload with no future-beat or prior-prose replay."""

    return {
        "sequence": {
            "word_target": sequence.target_words,
            "word_minimum": sequence.minimum_words,
            "word_maximum": sequence.maximum_words,
            "required_beats": [
                {"number": number, "beat": beat}
                for number, beat in zip(
                    sequence.beat_numbers,
                    _BASE_BEAT_BACKTRANSLATIONS[sequence.sequence_id],
                )
            ],
            "endpoint": _BASE_ENDPOINT_BACKTRANSLATIONS[sequence.sequence_id],
        },
        "present_causal_affordances": realization_story_program_for_sequence(
            program,
            sequence,
        ),
        "selected_story_program_hash": sha256_text(program) if program else "",
    }


def raw_sequence_prompt(
    *,
    compact_prefix: str,
    scene: SceneSpec,
    sequence: MacroSequence,
    completed_text: str,
    program: str = "",
) -> str:
    dynamic = render_compact_packet(
        _sequence_payload(
            scene=scene,
            sequence=sequence,
            completed_text=completed_text,
            program=program,
        )
    )
    instruction = _canonical_realization_instruction(sequence)
    user = (
        compact_prefix
        + "\n<sequence-input>"
        + dynamic
        + "</sequence-input>\n"
        + instruction
        + "\n<prose>\n"
    )
    return wrap_gemma_raw(
        system=(
            "Continue the supplied manuscript as fiction. Return prose only."
        ),
        user=user,
    )


def _canonical_realization_instruction(sequence: MacroSequence) -> str:
    ending_rule = (
        "This is the final sequence; give it an earned local ending. End on "
        "character-specific action, dialogue, an object, or the unresolved "
        "observation—not Mara explaining what she realized, learned, or found."
        if sequence.ending_visible
        else (
            "Do not write, hint, summarize, or anticipate the final romantic "
            "resolution. Stop at this sequence's endpoint."
        )
    )
    return (
        "Continue the fiction itself in close third-person past tense through "
        "Mara. Preserve continuity and reach the sequence state changes, but "
        "do not state their lesson. Let motives remain Mara's inferences. Do "
        "not paraphrase a successful action or line of dialogue in the next "
        f"sentence. Reach {sequence.minimum_words}-{sequence.maximum_words} words. "
        + ending_rule
    )
def base_sequence_prompt(
    *,
    compact_prefix: str,
    scene: SceneSpec,
    sequence: MacroSequence,
    completed_text: str,
    program: str = "",
    approved_prefix_text: str = "",
) -> str:
    """Render the same scene state as a native base-model continuation.

    There are deliberately no chat tokens and no imperative system message.
    The prompt looks like a manuscript-preparation document followed by the
    manuscript itself.  This keeps the semantic state comparable while testing
    the base checkpoint on the continuation objective it was pretrained for.
    """

    payload = _base_sequence_payload(
        scene=scene,
        sequence=sequence,
        program=program,
    )
    if completed_text.strip():
        manuscript = completed_text.rstrip()
    else:
        if not approved_prefix_text.strip():
            raise ValueError(
                "native base sequence one requires the approved manuscript prefix"
            )
        manuscript = (
            _tail_preserving_layout(approved_prefix_text, 1_100)
            + "\n\n* * *\n\n"
            + BASE_S02_OPENING_FRAGMENT
        )
    return (
        "# FICTION CONTINUATION DOSSIER\n\n"
        "## Background facts\n"
        + base_generation_context(compact_prefix)
        + "\n\n## Present-sequence causal affordances\n"
        + render_compact_packet(payload)
        + "\n\n## Manuscript continues below\n"
        + manuscript
    )


def chat_sequence_messages(
    *,
    compact_prefix: str,
    scene: SceneSpec,
    sequence: MacroSequence,
    completed_text: str,
    program: str = "",
) -> list[dict[str, str]]:
    dynamic = _sequence_payload(
        scene=scene,
        sequence=sequence,
        completed_text=completed_text,
        program=program,
    )
    instruction = _canonical_realization_instruction(sequence)
    return [
        {
            "role": "system",
            "content": (
                "Continue the supplied manuscript as fiction. Return prose only."
            ),
        },
        {
            "role": "user",
            "content": (
                compact_prefix
                + "\n<sequence-input>"
                + render_compact_packet(dynamic)
                + "</sequence-input>\n"
                + instruction
            ),
        },
    ]


def _completion_result(completion: Completion | Mapping[str, Any] | str) -> dict[str, Any]:
    if isinstance(completion, Completion):
        payload = completion.to_dict()
        payload.pop("raw", None)
        return payload
    if isinstance(completion, Mapping):
        payload = dict(completion)
        if not isinstance(payload.get("content"), str):
            raise ValueError("completion mapping has no textual content")
        return payload
    if isinstance(completion, str):
        return {"content": completion}
    raise TypeError(f"unsupported completion type: {type(completion).__name__}")


_RAW_TRANSPORT_TOKEN_RE = re.compile(
    r"(?:<\|channel\>(?:thought|analysis|final)\s*<channel\|>|"
    r"<\|turn\>(?:model|assistant)\s*|<turn\|>)",
    flags=re.IGNORECASE,
)


def clean_generated_prose(text: str) -> str:
    """Remove only model transport markers, never ordinary story markup."""

    return _RAW_TRANSPORT_TOKEN_RE.sub("", text).strip()


def _resume_call(
    store: TraceStore,
    *,
    call_id: str,
    prompt_hash: str,
    lineage: Mapping[str, str],
) -> dict[str, Any] | None:
    prior = store.completed_call(call_id)
    if prior is None:
        return None
    if prior.get("prompt_hash") != prompt_hash:
        raise ValueError(f"refusing to resume {call_id}: prompt hash changed")
    for key, expected in lineage.items():
        if prior.get(key) != expected:
            raise ValueError(f"refusing to resume {call_id}: {key} changed")
    result = prior.get("result")
    if not isinstance(result, Mapping) or not isinstance(result.get("content"), str):
        raise ValueError(f"completed call {call_id} has no textual result")
    return dict(result)


def _model_call(
    client: WriterClient,
    store: TraceStore,
    *,
    call_id: str,
    mode: str,
    prompt: str,
    messages: Sequence[Mapping[str, str]] | None,
    seed: int,
    max_tokens: int,
    anti_copy_index: AntiCopyIndex,
    lineage: Mapping[str, str],
    temperature: float = 0.9,
    top_p: float = 0.95,
    min_p: float = 0.02,
) -> dict[str, Any]:
    prompt_hash = sha256_text(prompt)
    prior = _resume_call(
        store,
        call_id=call_id,
        prompt_hash=prompt_hash,
        lineage=lineage,
    )
    if prior is not None:
        return prior
    failed_attempts = sum(
        1
        for record in TraceStore.read(store.calls_path)
        if record.get("call_id") == call_id
        and record.get("prompt_hash") == prompt_hash
        and record.get("status") == "failed"
    )
    # An anti-copy abort must not deterministically replay the rejected sample
    # when launchd resumes the controller.  Keep the stable logical call ID and
    # prompt hash, but make each append-only attempt's sampler seed explicit.
    attempt_seed = seed + failed_attempts * 100_003
    base = {
        "call_id": call_id,
        "attempt_index": failed_attempts + 1,
        "role": "continuation-writer",
        "generation_mode": mode,
        "model": client.model,
        "runtime": model_runtime_provenance(client.model),
        "prompt_hash": prompt_hash,
        **lineage,
        "parameters": {
            "seed": attempt_seed,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "min_p": min_p,
            **(
                {
                    "chat_template_kwargs": {
                        "enable_thinking": False,
                    },
                    "request_profile": CHAT_REQUEST_PROFILE,
                }
                if is_chat_mode(mode)
                else {}
            ),
        },
    }
    store.append_call({**base, "status": "started", "started_at": utc_now()})
    try:
        if mode in RAW_COMPLETION_MODES:
            guard = StreamingNgramGuard(anti_copy_index)
            completion = client.stream_raw(
                prompt=prompt,
                seed=attempt_seed,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                min_p=min_p,
                xtc_probability=0.05,
                on_delta=guard.feed,
            )
        else:
            completion = client.complete(
                messages=messages,
                seed=attempt_seed,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                min_p=min_p,
                extra={
                    "chat_template_kwargs": {
                        "enable_thinking": False,
                    },
                    # Keep the sampler matched to the raw-transport arm. The
                    # chat-vs-raw ablation should change transport, not quietly
                    # remove the modest XTC diversity pressure.
                    "xtc_probability": 0.05,
                },
            )
        result = _completion_result(completion)
        overlap = anti_copy_index.check(call_id, str(result["content"]))
        if overlap.hard_fail or overlap.unresolved_flags:
            raise SourceOverlapError(
                {
                    "word_count": anti_copy_index.policy.exact_words,
                    "source_ids": [
                        item.get("source_id", item.get("source_ids"))
                        for item in (
                            *overlap.exact_matches,
                            *overlap.fuzzy_matches,
                        )
                    ],
                }
            )
    except Exception as exc:
        store.append_call(
            {
                **base,
                "status": "failed",
                "finished_at": utc_now(),
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        raise
    store.append_call(
        {
            **base,
            "status": "completed",
            "finished_at": utc_now(),
            "result": result,
        }
    )
    return result


def _continue_short_sequence_prompt(
    *,
    compact_prefix: str,
    sequence: MacroSequence,
    prose: str,
    missing_words: int,
    ending_visible: bool,
) -> str:
    user = (
        compact_prefix
        + "\n<short-sequence-repair>"
        + _xml_value("sequence-id", sequence.sequence_id)
        + _xml_value("current-prose", prose[-10_000:])
        + _xml_value("minimum-additional-words", max(120, missing_words))
        + _xml_value("required-endpoint", sequence.endpoint)
        + "</short-sequence-repair>\n"
        + "Continue directly from the final sentence. Add causally necessary "
        + "action, dialogue, embodied perception, and consequence before reaching "
        + "the endpoint; do not recap or pad. "
        + (
            "Complete the local ending."
            if ending_visible
            else "Do not preview the story's final resolution."
        )
        + "\n<prose-continuation>\n"
    )
    return wrap_gemma_raw(
        system="Return only the direct continuation of the supplied fiction.",
        user=user,
    )


def _base_continue_short_sequence_prompt(
    *,
    compact_prefix: str,
    sequence: MacroSequence,
    prose: str,
    missing_words: int,
) -> str:
    del compact_prefix
    return (
        "# FICTION CONTINUATION NOTE\n\n"
        "## Local target\n"
        + (
            f"The current passage is approximately {missing_words} words short. "
            "Before reaching this local stopping "
            f"place—{_BASE_ENDPOINT_BACKTRANSLATIONS[sequence.sequence_id]}—the "
            "manuscript still needs causally necessary "
            "action, dialogue, embodied perception, and consequence. It does not "
            "need recap, summary, or a new ending.\n\n"
        )
        + "## Exact manuscript tail\n"
        + prose.rstrip()
        + "\n"
        + BASE_PROSE_SENTINEL
    )


def _compress_sequence_prompt(
    *,
    compact_prefix: str,
    sequence: MacroSequence,
    prose: str,
    strict_retry: bool = False,
) -> str:
    retry_ledger = (
        _xml_value("failed-compression-word-count", word_count(prose))
        + _xml_value(
            "minimum-words-to-delete",
            max(1, word_count(prose) - sequence.maximum_words),
        )
        if strict_retry
        else ""
    )
    user = (
        compact_prefix
        + "\n<sequence-compression>"
        + _xml_value("sequence-id", sequence.sequence_id)
        + _xml_value("maximum-words", sequence.maximum_words)
        + _xml_value("required-endpoint", sequence.endpoint)
        + retry_ledger
        + _xml_value("draft", prose)
        + "</sequence-compression>\n"
        + "Rewrite only this sequence as polished fiction. Preserve every event, "
        + "choice, strongest line, and endpoint while removing repetition. Return "
        + f"{sequence.minimum_words}-{sequence.maximum_words} words of prose only.\n"
        + (
            "The prior compression missed its ceiling. This retry is invalid "
            "unless it is at or below the stated maximum. Delete at least the "
            "ledgered number of words; do not replay the prior draft.\n"
            if strict_retry
            else ""
        )
        + "<prose>\n"
    )
    return wrap_gemma_raw(
        system="Return only the compressed fiction sequence.",
        user=user,
    )


def _base_compress_sequence_prompt(
    *,
    compact_prefix: str,
    sequence: MacroSequence,
    prose: str,
    strict_retry: bool = False,
) -> str:
    del compact_prefix
    return (
        "# FICTION COMPRESSION NOTE\n\n"
        "## Local target\n"
        + (
            f"A polished {sequence.minimum_words}-{sequence.maximum_words}-word "
            "version of this passage, preserving every causal event, "
            "choice, strongest line, and this final situation: "
            f"{_BASE_ENDPOINT_BACKTRANSLATIONS[sequence.sequence_id]}\n\n"
        )
        + (
            f"The prior compression is {word_count(prose)} words and missed its "
            f"ceiling. Delete at least "
            f"{max(1, word_count(prose) - sequence.maximum_words)} words. A replay "
            "or any result above the maximum is invalid.\n\n"
            if strict_retry
            else ""
        )
        + "## Draft to compress\n"
        + prose.rstrip()
        + "\n\n## Polished manuscript\n"
    )


def _natural_sequence_ending(prose: str) -> bool:
    return bool(re.search(r"[.!?][”\"’')\]]*\s*$", prose.rstrip()))


def _local_hfn_present(prose: str) -> bool:
    """Recognize an explicit, freely chosen near-term romantic continuation.

    Generation and final gating must share this exact predicate.  The previous
    sequence controller accepted vague mentions of Fulcrum or tomorrow that
    the hard gate correctly rejected, allowing 11/12 drafts to commit without
    the required local hope-for-now decision.
    """

    tail = prose[-4_000:]
    authored_choice = re.search(
        r"\b(?:Mara|she)\b.{0,120}\b"
        r"(?:(?:chose|decided|agreed|promised|intended)\b.{0,24}\b"
        r"(?:stay|return|continue|come back|see (?:him|Jonah))|"
        r"(?:would|will)\s+(?:stay|return|continue|come back|"
        r"see (?:him|Jonah)))\b",
        tail,
        re.IGNORECASE | re.DOTALL,
    )
    dialogue_choice = re.search(
        r"[“\"](?:[^”\"\n]{0,100})(?:see you tomorrow|I(?:'ll| will) "
        r"(?:stay|return|come back|continue)|next time)(?:[^”\"\n]{0,80})"
        r"[”\"]\s*(?:Mara|she)\s+(?:said|answered|agreed|promised)",
        tail,
        re.IGNORECASE,
    )
    next_time_choice = re.search(
        r"\bnext time\b.{0,120}\b(?:Mara|she)\b.{0,80}\b"
        r"(?:chose|decided|agreed|promised|intended|would|will)\b",
        tail,
        re.IGNORECASE | re.DOTALL,
    )
    breakfast_choice = re.search(
        r"\bbreakfast\b.{0,240}\b(?:assigning|meet|seven|7(?::00)?)\b",
        tail,
        re.IGNORECASE | re.DOTALL,
    )
    return bool(
        authored_choice or dialogue_choice or next_time_choice or breakfast_choice
    )


def _sequence_endpoint_satisfied(
    sequence: MacroSequence,
    prose: str,
) -> bool:
    if not _natural_sequence_ending(prose):
        return False
    terminal_tail = " ".join(prose.split()[-220:])
    if sequence.sequence_id == "s02-seq-1-trap":
        # Sequence one may mention or look toward the door, but it cannot spend
        # the exit promised to sequence two.  Inspect only the terminal passage
        # so recollections and hypothetical exits do not create false failures.
        premature_exit = bool(
            re.search(
                r"\b(?:"
                r"(?:stood|waited|paused|was)\s+(?:alone\s+)?(?:in|outside)\s+the\s+"
                r"(?:hallway|corridor|street|lobby)|"
                r"(?:walked|stepped|went|slipped|ran|made\s+it)\s+out(?:side)?\b|"
                r"left\s+(?:the\s+)?(?:room|lab|session|suite)|"
                r"(?:session|alignment)\s+(?:was|had)\s+(?:ended|finished|over)|"
                r"door\s+(?:closed|clicked|shut)\s+behind\s+(?:her|Mara)"
                r")\b",
                terminal_tail,
                flags=re.IGNORECASE,
            )
        )
        return not premature_exit
    if sequence.sequence_id == "s02-seq-2-refusal":
        # The refusal changes the room before anyone ratifies or completes the
        # exit.  The actual threshold crossing belongs to sequence three.
        premature_exit = bool(
            re.search(
                r"\b(?:"
                r"(?:stood|waited|paused|was)\s+(?:alone\s+)?(?:in|outside)\s+the\s+"
                r"(?:hallway|corridor|street|lobby)|"
                r"(?:walked|stepped|went|slipped|ran|made\s+it)\s+out(?:side)?\b|"
                r"left\s+(?:the\s+)?(?:room|lab|session|suite)|"
                r"door\s+(?:closed|clicked|shut)\s+behind\s+(?:her|Mara)"
                r")\b",
                terminal_tail,
                flags=re.IGNORECASE,
            )
        )
        return not premature_exit
    if sequence.sequence_id != "s02-seq-3-doorway":
        return True
    physical_kiss = bool(
        re.search(
            r"(?:\b(?:they|he|she)\b.{0,100}\bkiss(?:ed|ing)?\b|"
            r"\blips?\b.{0,100}\b(?:met|touch(?:ed)?|found)\b)",
            prose,
            flags=re.IGNORECASE | re.DOTALL,
        )
    )
    stopped_while_desired = bool(
        re.search(
            r"\b(?:kiss|lips?|mouth)\b.{0,900}\b"
            r"(?:stop(?:ped)?|part(?:ed)?|pull(?:ed)? away|ended|still wanted|"
            r"still desired)\b",
            prose,
            flags=re.IGNORECASE | re.DOTALL,
        )
    )
    shared_stopping_practice = bool(
        re.search(
            r"\b(?:kiss|lips?|mouth)\b.{0,1000}\b"
            r"(?:agree(?:d|ment)?|rule|practice|next time|ask|tell me|"
            r"stop(?:ping|ped)?|pause|wait|enough|glad|choose|choice|"
            r"say when|same answer|again)\b",
            prose,
            flags=re.IGNORECASE | re.DOTALL,
        )
    )
    chosen_continuation = _local_hfn_present(prose)
    return all(
        (
            physical_kiss,
            stopped_while_desired,
            shared_stopping_practice,
            chosen_continuation,
        )
    )


def _sentence_bounded_prefix(prose: str, maximum_words: int) -> str:
    if maximum_words < 1:
        raise ValueError("tail-rescue prefix budget must be positive")
    if word_count(prose) <= maximum_words:
        return prose.rstrip()
    best = ""
    for match in re.finditer(r"[.!?][”\"’')\]]*(?:\s+|$)", prose):
        candidate = prose[: match.end()].rstrip()
        if word_count(candidate) <= maximum_words:
            best = candidate
        else:
            break
    if best:
        return best
    words = prose.split()
    return " ".join(words[:maximum_words]).rstrip()


def _endpoint_tail_rescue_prompt(
    *,
    compact_prefix: str,
    sequence: MacroSequence,
    kept_prefix: str,
    discarded_tail: str,
    minimum_patch_words: int,
    maximum_patch_words: int,
    native_base: bool,
) -> str:
    if native_base:
        del compact_prefix, discarded_tail
        return (
            "# FICTION ENDING NOTE\n\n"
            "## Local target\n"
            + _BASE_ENDPOINT_BACKTRANSLATIONS[sequence.sequence_id]
            + (
                f"\nContinue directly in {minimum_patch_words}-"
                f"{maximum_patch_words} words. Complete the syntax and every "
                "endpoint event without recap or a second ending.\n\n"
            )
            + "## Exact manuscript tail\n"
            + kept_prefix.rstrip()
            + "\n"
            + BASE_PROSE_SENTINEL
        )
    user = (
        compact_prefix
        + "\n<endpoint-tail-rescue>"
        + _xml_value("sequence-id", sequence.sequence_id)
        + _xml_value("kept-prefix", kept_prefix)
        + _xml_value("discarded-failed-tail", discarded_tail)
        + _xml_value("required-endpoint", sequence.endpoint)
        + _xml_value("minimum-patch-words", minimum_patch_words)
        + _xml_value("maximum-patch-words", maximum_patch_words)
        + "</endpoint-tail-rescue>\n"
        + "Continue directly from the kept prefix with a replacement tail. Use "
        + "the discarded tail for causal facts only; do not copy or recap it. "
        + "Complete the syntax and every required endpoint event. Return only "
        + f"{minimum_patch_words}-{maximum_patch_words} words of fiction.\n"
        + "<replacement-tail>\n"
    )
    return wrap_gemma_raw(
        system="Return only the complete replacement ending of the sequence.",
        user=user,
    )


def generate_macro_sequence(
    *,
    client: WriterClient,
    store: TraceStore,
    mode: str,
    candidate_id: str,
    compact_prefix: str,
    scene: SceneSpec,
    sequence: MacroSequence,
    completed_text: str,
    seed: int,
    anti_copy_index: AntiCopyIndex,
    lineage: Mapping[str, str],
    program: str = "",
    approved_prefix_text: str = "",
) -> tuple[str, list[str]]:
    if mode not in GENERATION_MODES:
        raise ValueError(f"unknown generation mode: {mode}")
    prompt = (
        base_sequence_prompt(
            compact_prefix=compact_prefix,
            scene=scene,
            sequence=sequence,
            completed_text=completed_text,
            program=program,
            approved_prefix_text=approved_prefix_text,
        )
        if is_native_base_mode(mode)
        else raw_sequence_prompt(
            compact_prefix=compact_prefix,
            scene=scene,
            sequence=sequence,
            completed_text=completed_text,
            program=program,
        )
    )
    messages = (
        chat_sequence_messages(
            compact_prefix=compact_prefix,
            scene=scene,
            sequence=sequence,
            completed_text=completed_text,
            program=program,
        )
        if is_chat_mode(mode)
        else None
    )
    call_ids: list[str] = []
    call_id = (
        f"{candidate_id}:{sequence.sequence_id}:draft-{CHAT_REQUEST_PROFILE}"
        if is_chat_mode(mode)
        else f"{candidate_id}:{sequence.sequence_id}:draft"
    )
    call_ids.append(call_id)
    result = _model_call(
        client,
        store,
        call_id=call_id,
        mode=mode,
        prompt=prompt,
        messages=messages,
        seed=seed,
        # Empirical Gemma 4 fiction runs here average about 1.3 output tokens
        # per word. The former 2x-maximum allowance invited 1,500-word passages
        # into a 1,100-word slot and made whole-sequence compression routine.
        # Aim near the word target; a short or token-cut response is cheaper to
        # extend with the bounded continuation/tail rescue already below.
        max_tokens=max(1_300, int(sequence.target_words * 1.35) + 120),
        anti_copy_index=anti_copy_index,
        lineage=lineage,
    )
    last_result = result
    prose = require_packet_clean_prose(
        clean_generated_prose(str(result["content"])),
        call_id=call_id,
    )
    if is_native_base_mode(mode) and not completed_text:
        stripped = prose.lstrip()
        joiner = (
            ""
            if stripped.startswith(("'", "’", ",", ".", ";", ":", "?", "!"))
            else " "
        )
        prose = BASE_S02_OPENING_FRAGMENT + joiner + stripped

    for repair_index in range(1, 3):
        current_words = word_count(prose)
        if current_words >= sequence.minimum_words:
            break
        repair_prompt = (
            _base_continue_short_sequence_prompt(
                compact_prefix=compact_prefix,
                sequence=sequence,
                prose=prose,
                missing_words=sequence.minimum_words - current_words,
            )
            if is_native_base_mode(mode)
            else _continue_short_sequence_prompt(
                compact_prefix=compact_prefix,
                sequence=sequence,
                prose=prose,
                missing_words=sequence.minimum_words - current_words,
                ending_visible=sequence.ending_visible,
            )
        )
        repair_id = (
            f"{candidate_id}:{sequence.sequence_id}:continue-{repair_index}"
            + (
                f"-{CHAT_REQUEST_PROFILE}"
                if is_chat_mode(mode)
                else ""
            )
        )
        call_ids.append(repair_id)
        repair_result = _model_call(
            client,
            store,
            call_id=repair_id,
            mode=mode,
            prompt=repair_prompt,
            messages=(
                [
                    {
                        "role": "system",
                        "content": "Return only the direct continuation of the prose.",
                    },
                    {"role": "user", "content": repair_prompt},
                ]
                if is_chat_mode(mode)
                else None
            ),
            seed=seed + repair_index * 101,
            max_tokens=max(700, (sequence.minimum_words - current_words) * 2),
            anti_copy_index=anti_copy_index,
            lineage=lineage,
            temperature=0.82,
        )
        last_result = repair_result
        addition = require_packet_clean_prose(
            clean_generated_prose(str(repair_result["content"])),
            call_id=repair_id,
        )
        prose = prose.rstrip() + "\n\n" + addition

    # A modest overrun should not trigger a multi-thousand-token rewrite of an
    # otherwise usable sequence. Keep the sentence-bounded body and regenerate
    # only enough tail to land below the ceiling with a natural endpoint.
    overrun = word_count(prose) - sequence.maximum_words
    if 0 < overrun <= 140 and _natural_sequence_ending(prose):
        patch_minimum, patch_maximum = 150, 230
        kept_prefix = _sentence_bounded_prefix(
            prose,
            max(1, sequence.maximum_words - patch_maximum - 20),
        )
        discarded_tail = prose[len(kept_prefix) :].strip()
        tail_prompt = _endpoint_tail_rescue_prompt(
            compact_prefix=compact_prefix,
            sequence=sequence,
            kept_prefix=kept_prefix,
            discarded_tail=discarded_tail,
            minimum_patch_words=patch_minimum,
            maximum_patch_words=patch_maximum,
            native_base=is_native_base_mode(mode),
        )
        tail_id = f"{candidate_id}:{sequence.sequence_id}:tail-compress-v1"
        if is_chat_mode(mode):
            tail_id += f"-{CHAT_REQUEST_PROFILE}"
        call_ids.append(tail_id)
        tail_result = _model_call(
            client,
            store,
            call_id=tail_id,
            mode=mode,
            prompt=tail_prompt,
            messages=(
                [
                    {
                        "role": "system",
                        "content": "Return only the replacement fiction tail.",
                    },
                    {"role": "user", "content": tail_prompt},
                ]
                if is_chat_mode(mode)
                else None
            ),
            seed=seed + 389,
            max_tokens=620,
            anti_copy_index=anti_copy_index,
            lineage=lineage,
            temperature=0.62,
            top_p=0.93,
        )
        last_result = tail_result
        replacement = require_packet_clean_prose(
            clean_generated_prose(str(tail_result["content"])),
            call_id=tail_id,
        )
        repaired = kept_prefix.rstrip() + "\n\n" + replacement
        if (
            sequence.minimum_words <= word_count(repaired) <= sequence.maximum_words
            and _sequence_endpoint_satisfied(sequence, repaired)
        ):
            prose = repaired

    for compression_index in range(1, 4):
        if word_count(prose) <= sequence.maximum_words:
            break
        compression_sequence = sequence
        if compression_index > 1:
            safety_fraction = 0.08 if compression_index == 2 else 0.15
            safety_floor = 80 if compression_index == 2 else 200
            safety_margin = max(
                safety_floor,
                int(sequence.maximum_words * safety_fraction),
            )
            guarded_maximum = max(
                sequence.minimum_words,
                sequence.maximum_words - safety_margin,
            )
            compression_sequence = replace(
                sequence,
                target_words=min(sequence.target_words, guarded_maximum),
                maximum_words=guarded_maximum,
            )
        compress_prompt = (
            _base_compress_sequence_prompt(
                compact_prefix=compact_prefix,
                sequence=compression_sequence,
                prose=prose,
                strict_retry=compression_index > 1,
            )
            if is_native_base_mode(mode)
            else _compress_sequence_prompt(
                compact_prefix=compact_prefix,
                sequence=compression_sequence,
                prose=prose,
                strict_retry=compression_index > 1,
            )
        )
        compression_suffix = (
            "" if compression_index == 1 else f"-{compression_index}b"
        )
        compress_id = (
            f"{candidate_id}:{sequence.sequence_id}:compress{compression_suffix}-"
            f"{CHAT_REQUEST_PROFILE}"
            if is_chat_mode(mode)
            else f"{candidate_id}:{sequence.sequence_id}:compress{compression_suffix}"
        )
        call_ids.append(compress_id)
        compress_result = _model_call(
            client,
            store,
            call_id=compress_id,
            mode=mode,
            prompt=compress_prompt,
            messages=(
                [
                    {
                        "role": "system",
                        "content": "Return only the compressed fiction sequence.",
                    },
                    {"role": "user", "content": compress_prompt},
                ]
                if is_chat_mode(mode)
                else None
            ),
            seed=seed + 503 + (compression_index - 1) * 997,
            # The third attempt is a strict boundary rescue. Gemma 4 sometimes
            # treats a word target as advisory and reproduces nearly the same
            # overlong sequence twice. A tighter token ceiling makes the final
            # attempt materially different while retaining enough room for the
            # sequence minimum and its required ending.
            max_tokens=(
                max(
                    1_400,
                    int(compression_sequence.maximum_words * 1.5),
                )
                if compression_index == 3
                else compression_sequence.maximum_words * 2
            ),
            anti_copy_index=anti_copy_index,
            lineage=lineage,
            temperature=(0.5 + compression_index * 0.08),
            top_p=0.94,
        )
        last_result = compress_result
        prose = require_packet_clean_prose(
            clean_generated_prose(str(compress_result["content"])),
            call_id=compress_id,
        )
    needs_endpoint_rescue = (
        str(last_result.get("finish_reason", "")).lower() == "length"
        or not _sequence_endpoint_satisfied(sequence, prose)
    )
    if needs_endpoint_rescue:
        for rescue_index in range(1, 3):
            patch_minimum, patch_maximum = (
                (180, 260) if rescue_index == 1 else (220, 300)
            )
            reserve = patch_maximum + (20 if rescue_index == 1 else 60)
            kept_prefix = _sentence_bounded_prefix(
                prose,
                max(1, sequence.maximum_words - reserve),
            )
            discarded_tail = prose[len(kept_prefix) :].strip()
            rescue_prompt = _endpoint_tail_rescue_prompt(
                compact_prefix=compact_prefix,
                sequence=sequence,
                kept_prefix=kept_prefix,
                discarded_tail=discarded_tail,
                minimum_patch_words=patch_minimum,
                maximum_patch_words=patch_maximum,
                native_base=is_native_base_mode(mode),
            )
            rescue_id = (
                f"{candidate_id}:{sequence.sequence_id}:endpoint-rescue-"
                f"{rescue_index}-v1"
            )
            if is_chat_mode(mode):
                rescue_id += f"-{CHAT_REQUEST_PROFILE}"
            call_ids.append(rescue_id)
            rescue_result = _model_call(
                client,
                store,
                call_id=rescue_id,
                mode=mode,
                prompt=rescue_prompt,
                messages=(
                    [
                        {
                            "role": "system",
                            "content": (
                                "Return only the complete replacement ending "
                                "of the sequence."
                            ),
                        },
                        {"role": "user", "content": rescue_prompt},
                    ]
                    if is_chat_mode(mode)
                    else None
                ),
                seed=seed + 4_500 + rescue_index * 911,
                max_tokens=700,
                anti_copy_index=anti_copy_index,
                lineage=lineage,
                temperature=0.5,
                top_p=0.92,
            )
            patch = require_packet_clean_prose(
                clean_generated_prose(str(rescue_result["content"])),
                call_id=rescue_id,
            )
            prose = kept_prefix.rstrip() + "\n\n" + patch
            if (
                str(rescue_result.get("finish_reason", "")).lower() != "length"
                and sequence.minimum_words
                <= word_count(prose)
                <= sequence.maximum_words
                and _sequence_endpoint_satisfied(sequence, prose)
            ):
                break
    final_sequence_words = word_count(prose)
    if not sequence.minimum_words <= final_sequence_words <= sequence.maximum_words:
        raise ValueError(
            f"{candidate_id}:{sequence.sequence_id} remained outside its "
            f"{sequence.minimum_words}-{sequence.maximum_words} word budget "
            f"after bounded repair: {final_sequence_words}"
        )
    if not _sequence_endpoint_satisfied(sequence, prose):
        raise ValueError(
            f"{candidate_id}:{sequence.sequence_id} cannot commit without a "
            "natural ending and its required endpoint"
        )
    return prose, call_ids


def _budgeted_macro_sequence(
    *,
    sequence: MacroSequence,
    remaining: Sequence[MacroSequence],
    completed_words: int,
    scene: SceneSpec,
) -> MacroSequence:
    """Allocate the current sequence a feasible share of the scene hard range."""

    remaining_minimum = sum(item.minimum_words for item in remaining)
    remaining_maximum = sum(item.maximum_words for item in remaining)
    minimum = max(
        sequence.minimum_words,
        scene.target_words_min - completed_words - remaining_maximum,
    )
    maximum = min(
        sequence.maximum_words,
        scene.target_words_max - completed_words - remaining_minimum,
    )
    if minimum > maximum:
        raise ValueError(
            f"no feasible word budget remains for {sequence.sequence_id}: "
            f"completed={completed_words}, current={minimum}-{maximum}, "
            f"remaining_minimum={remaining_minimum}"
        )
    target = min(max(sequence.target_words, minimum), maximum)
    return replace(
        sequence,
        minimum_words=minimum,
        target_words=target,
        maximum_words=maximum,
    )


def make_continuation_run_config(
    *,
    run_id: str,
    mode: str,
    model_role: str,
    compact_prefix: str,
    scene: SceneSpec,
    source_hashes: Mapping[str, str],
    seeds: Sequence[int],
    profile: Mapping[str, Any],
    approved_prefix: ApprovedPrefix,
    feedback: HumanFeedbackBrief,
    anti_copy_index: AntiCopyIndex,
    author_context: ResolvedAuthorContext | None = None,
) -> RunConfig:
    if mode not in GENERATION_MODES:
        raise ValueError(f"unknown generation mode: {mode}")
    author_lineage = (
        {
            "author_profile_id": author_context.author_profile_id,
            "author_profile_hash": author_context.author_profile_hash,
            "corpus_manifest_hash": author_context.corpus_manifest_hash,
            "transformation_map_hash": author_context.transformation_map_hash,
            "conditioning_variant": author_context.conditioning_variant,
            "prompt_encoding": author_context.prompt_encoding,
            "control_density": author_context.control_density,
            "story_program_id": "per-candidate-plan-set.v1",
            "frontier_adapter": "none-local",
        }
        if author_context is not None
        else {}
    )
    return RunConfig(
        run_id=run_id,
        scene_id=scene.scene_id,
        pipeline=mode,
        model_role=model_role,
        prompt_hash=sha256_text(compact_prefix),
        source_hashes=dict(source_hashes),
        seeds=tuple(seeds),
        sampling={
            "temperature": 0.9,
            "top_p": 0.95,
            "min_p": 0.02,
            "xtc_probability": 0.05,
        },
        output_words_min=scene.target_words_min,
        output_words_max=scene.target_words_max,
        output_tokens=8_000,
        persona_ids=("mara_vale", "livia_sloane", "jonah_reed"),
        created_at=utc_now(),
        ontology_version=str(profile["ontology_version"]),
        story_profile_id="fulcrum-pilot.v1",
        scene_profile_id="fulcrum-s02.v4.1-literary",
        resolved_profile_hash=str(profile["profile_hash"]),
        approved_prefix_id=approved_prefix.approved_prefix_id,
        approved_prefix_hash=approved_prefix.text_hash,
        feedback_brief_hash=feedback.feedback_brief_hash,
        generation_mode=mode,
        anti_copy_policy_version=(
            anti_copy_index.policy.version if author_context is not None else ""
        ),
        anti_copy_index_hash=(
            anti_copy_index.index_hash if author_context is not None else ""
        ),
        **author_lineage,
    )


def _prose_has_complete_ending(text: str) -> bool:
    """Reject token-cut prose without trying to grade its literary quality."""

    stripped = text.rstrip()
    if not stripped:
        return False
    if stripped[-1] not in ".?!…\"”'’":
        return False
    if stripped.count("“") != stripped.count("”"):
        return False
    if stripped.count('"') % 2:
        return False
    return True


def _resume_candidate(
    store: TraceStore,
    *,
    candidate_id: str,
    config: RunConfig,
    expected_program: str = "",
) -> Candidate | None:
    prior = store.completed_candidate(candidate_id)
    if prior is None:
        return None
    payload = dict(prior)
    payload.pop("status", None)
    payload.pop("finished_at", None)
    candidate = Candidate.from_dict(payload)
    expected = (
        config.approved_prefix_hash,
        config.feedback_brief_hash,
        config.resolved_profile_hash,
        config.generation_mode,
    )
    observed = (
        candidate.approved_prefix_hash,
        candidate.feedback_brief_hash,
        candidate.resolved_profile_hash,
        candidate.generation_mode,
    )
    if observed != expected:
        raise ValueError(
            f"refusing to resume {candidate_id}: continuation lineage changed"
        )
    observed_program_hash = str(
        candidate.parent_trace.get("story_program_hash", "")
    )
    expected_program_hash = sha256_text(expected_program) if expected_program else ""
    if observed_program_hash != expected_program_hash:
        raise ValueError(
            f"refusing to resume {candidate_id}: selected story program changed"
        )
    continuation_words = word_count(candidate.continuation_text)
    if not config.output_words_min <= continuation_words <= config.output_words_max:
        # Completed records are append-only evidence, not an excuse to preserve
        # a gate failure. Re-enter generation using the exact prior calls; only
        # the missing bounded length repair will be requested.
        return None
    if not _prose_has_complete_ending(candidate.continuation_text):
        # A token-limited response can satisfy the numeric range while ending
        # mid-sentence or mid-quotation. Such a record remains append-only
        # evidence, but it is not a resumable completed candidate.
        return None
    if not _sequence_endpoint_satisfied(
        S02_MACRO_SEQUENCES[-1],
        candidate.continuation_text,
    ):
        # Numeric and syntactic completion still cannot substitute for the
        # locked final causal endpoint.
        return None
    return candidate


def run_continuation_arm(
    *,
    client: WriterClient,
    run_dir: str | Path,
    config: RunConfig,
    scene: SceneSpec,
    profile: Mapping[str, Any],
    approved_prefix: ApprovedPrefix,
    feedback: HumanFeedbackBrief,
    compact_prefix: str,
    anti_copy_index: AntiCopyIndex,
    story_programs: Mapping[int, str] | None = None,
    max_new_candidates: int | None = None,
    stop_after_sequences: int | None = None,
) -> tuple[Candidate, ...]:
    if stop_after_sequences is not None and not 1 <= stop_after_sequences <= 2:
        raise ValueError("stop_after_sequences must be 1, 2, or omitted")
    store = TraceStore(Path(run_dir))
    config_path = store.run_dir / "run_config.json"
    if config_path.exists():
        existing = RunConfig.from_dict(_load_json(config_path))
        existing_payload = existing.to_dict()
        active_payload = config.to_dict()
        existing_payload.pop("created_at", None)
        active_payload.pop("created_at", None)
        if existing_payload != active_payload:
            raise ValueError("refusing to reuse run directory with a changed RunConfig")
        config = existing
    else:
        write_json(config_path, config.to_dict())
    candidates: list[Candidate] = []
    newly_committed = 0
    lineage_fields = {
        "approved_prefix_hash": approved_prefix.text_hash,
        "feedback_brief_hash": feedback.feedback_brief_hash,
        "resolved_profile_hash": str(profile["profile_hash"]),
        "generation_mode": config.generation_mode,
        "author_profile_hash": config.author_profile_hash,
        "corpus_manifest_hash": config.corpus_manifest_hash,
        "transformation_map_hash": config.transformation_map_hash,
        "conditioning_variant": config.conditioning_variant,
        "prompt_encoding": config.prompt_encoding,
        "control_density": config.control_density,
        "anti_copy_policy_version": config.anti_copy_policy_version,
        "anti_copy_index_hash": config.anti_copy_index_hash,
        "native_base_prompt_profile": (
            NATIVE_BASE_PROMPT_PROFILE
            if is_native_base_mode(config.generation_mode)
            else ""
        ),
    }
    for index, seed in enumerate(config.seeds, 1):
        candidate_id = f"{config.run_id}-{config.generation_mode}-{index:02d}"
        program = str((story_programs or {}).get(seed, ""))
        plan_source_mode = (
            BASE31_PLAN_MODE
            if config.generation_mode in {
                NATIVE_BASE_PLANNED_MODE,
                CHAT_PLANNED_MODE,
            }
            else config.generation_mode
        )
        candidate_lineage = {
            **lineage_fields,
            "story_program_id": (
                f"s02-{plan_source_mode}-{seed}"
                if program
                else config.story_program_id
            ),
            "story_program_hash": sha256_text(program) if program else "",
        }
        resumed = _resume_candidate(
            store,
            candidate_id=candidate_id,
            config=config,
            expected_program=program,
        )
        if resumed is not None:
            candidates.append(resumed)
            continue
        if stop_after_sequences is not None:
            latest = store.latest_candidate_record(candidate_id)
            if (
                latest is not None
                and latest.get("status") == "partial"
                and int(latest.get("completed_sequence_count", 0))
                >= stop_after_sequences
            ):
                expected_partial_lineage = {
                    "run_id": config.run_id,
                    "generation_mode": config.generation_mode,
                    "seed": seed,
                    **candidate_lineage,
                }
                changed = [
                    key
                    for key, expected_value in expected_partial_lineage.items()
                    if latest.get(key) != expected_value
                ]
                if changed:
                    raise ValueError(
                        f"refusing to skip partial {candidate_id}: changed "
                        + ", ".join(changed)
                    )
                continue
        sequence_texts: list[str] = []
        budgeted_sequences: list[MacroSequence] = []
        call_ids: list[str] = []
        checkpointed = False
        for sequence_index, sequence in enumerate(S02_MACRO_SEQUENCES):
            budgeted_sequence = _budgeted_macro_sequence(
                sequence=sequence,
                remaining=S02_MACRO_SEQUENCES[sequence_index + 1 :],
                completed_words=word_count("\n\n".join(sequence_texts)),
                scene=scene,
            )
            try:
                prose, sequence_calls = generate_macro_sequence(
                    client=client,
                    store=store,
                    mode=config.generation_mode,
                    candidate_id=candidate_id,
                    compact_prefix=compact_prefix,
                    scene=scene,
                    sequence=budgeted_sequence,
                    completed_text="\n\n".join(sequence_texts),
                    seed=seed + sequence_index * 1_003,
                    anti_copy_index=anti_copy_index,
                    lineage=candidate_lineage,
                    program=program,
                    approved_prefix_text=approved_prefix.text,
                )
            except Exception as exc:
                store.append_candidate(
                    {
                        "record_type": "CandidateFailure",
                        "status": "failed",
                        "candidate_id": candidate_id,
                        "run_id": config.run_id,
                        "generation_mode": config.generation_mode,
                        "seed": seed,
                        "failed_sequence_id": budgeted_sequence.sequence_id,
                        "completed_sequence_count": len(sequence_texts),
                        "error": f"{type(exc).__name__}: {exc}",
                        **candidate_lineage,
                        "finished_at": utc_now(),
                    }
                )
                raise
            sequence_texts.append(prose)
            budgeted_sequences.append(budgeted_sequence)
            call_ids.extend(sequence_calls)
            if (
                stop_after_sequences is not None
                and len(sequence_texts) >= stop_after_sequences
            ):
                partial_text = "\n\n".join(sequence_texts).strip()
                store.append_candidate(
                    {
                        "record_type": "PartialCandidateCheckpoint",
                        "status": "partial",
                        "candidate_id": candidate_id,
                        "run_id": config.run_id,
                        "generation_mode": config.generation_mode,
                        "seed": seed,
                        "completed_sequence_count": len(sequence_texts),
                        "last_sequence_id": budgeted_sequence.sequence_id,
                        "continuation_text": partial_text,
                        "continuation_words": word_count(partial_text),
                        "diagnostics": sequence_checkpoint_diagnostics(
                            partial_text,
                            program=program,
                            sequence=budgeted_sequence,
                        ),
                        "call_ids": call_ids,
                        **candidate_lineage,
                        "finished_at": utc_now(),
                    }
                )
                newly_committed += 1
                checkpointed = True
                break
        if checkpointed:
            if (
                max_new_candidates is not None
                and newly_committed >= max_new_candidates
            ):
                return tuple(candidates)
            continue
        continuation = "\n\n".join(sequence_texts).strip()
        require_packet_clean_prose(
            continuation,
            call_id=f"{candidate_id}:postflight",
        )
        continuation_words = word_count(continuation)
        if not scene.target_words_min <= continuation_words <= scene.target_words_max:
            raise ValueError(
                f"{candidate_id} cannot commit outside the hard scene range "
                f"{scene.target_words_min}-{scene.target_words_max}: "
                f"{continuation_words}"
            )
        if not _prose_has_complete_ending(continuation):
            raise ValueError(
                f"{candidate_id} cannot commit a token-cut or unbalanced ending"
            )
        merged = approved_prefix.text.rstrip() + "\n\n" + continuation
        candidate = Candidate(
            candidate_id=candidate_id,
            run_id=config.run_id,
            pipeline=config.generation_mode,
            scene_id=scene.scene_id,
            seed=seed,
            text=merged,
            continuation_text=continuation,
            parent_trace={
                "macro_sequences": [
                    {
                        **asdict(sequence),
                        "actual_words": word_count(text),
                    }
                    for sequence, text in zip(
                        budgeted_sequences, sequence_texts
                    )
                ],
                "story_program": program,
                "story_program_hash": sha256_text(program) if program else "",
                "native_base_prompt_profile": (
                    NATIVE_BASE_PROMPT_PROFILE
                    if is_native_base_mode(config.generation_mode)
                    else ""
                ),
            },
            evidence_ids=tuple(scene.source_ids),
            telemetry={
                "model": client.model,
                "model_role": config.model_role,
                "runtime": model_runtime_provenance(client.model),
                "continuation_words": word_count(continuation),
                "merged_words": word_count(merged),
            },
            lineage=tuple(f"call:{call_id}" for call_id in call_ids),
            prompt_hash=config.prompt_hash,
            ontology_version=config.ontology_version,
            story_profile_id=config.story_profile_id,
            scene_profile_id=config.scene_profile_id,
            resolved_profile_hash=config.resolved_profile_hash,
            author_profile_id=config.author_profile_id,
            author_profile_hash=config.author_profile_hash,
            corpus_manifest_hash=config.corpus_manifest_hash,
            transformation_map_hash=config.transformation_map_hash,
            conditioning_variant=config.conditioning_variant,
            prompt_encoding=config.prompt_encoding,
            control_density=config.control_density,
            story_program_id=(
                f"s02-{plan_source_mode}-{seed}"
                if program
                else config.story_program_id
            ),
            anti_copy_policy_version=config.anti_copy_policy_version,
            anti_copy_index_hash=config.anti_copy_index_hash,
            frontier_adapter=config.frontier_adapter,
            approved_prefix_id=config.approved_prefix_id,
            approved_prefix_hash=config.approved_prefix_hash,
            feedback_brief_hash=config.feedback_brief_hash,
            generation_mode=config.generation_mode,
        )
        store.append_candidate(
            {
                **candidate.to_dict(),
                "status": "completed",
                "finished_at": utc_now(),
            }
        )
        candidates.append(candidate)
        newly_committed += 1
        if (
            max_new_candidates is not None
            and newly_committed >= max_new_candidates
        ):
            break
    return tuple(candidates)


def story_program_proposal_prompt(
    *,
    compact_prefix: str,
    proposal_count: int = 8,
) -> str:
    return (
        compact_prefix
        + "\n<proposal-request>"
        + f"Invent {proposal_count} materially different ways to execute the "
        + "three S02 sequences. Diversity must change causality, not decoration. "
        + "For every proposal specify: the difficult thing Livia perceives "
        + "correctly; Mara's consequential mistake; the action by which Mara "
        + "creates an exit; the cost Miriam accepts to protect it; the cost, "
        + "compromised motive, or repair that makes Jonah's restraint effortful; "
        + "the institutional consequence; and one concrete observation that "
        + "remains unexplained. Preserve the hard boundaries, not any sample "
        + "wording. Do not write prose or moral conclusions. Number the proposals "
        + "and give each a title plus a compact causal event chain."
        + "</proposal-request>\n"
    )


def base_story_program_proposal_prompt(
    *,
    compact_prefix: str,
    proposal_count: int = 8,
) -> str:
    """Present planning as document continuation, without chat-role tokens."""

    return (
        compact_prefix
        + "\n\n# DIVERGENT S02 STORY PROGRAMS\n\n"
        + "The accepted S01 tail establishes continuity but is not a style model. "
        + "The numbered alternatives are "
        + "materially different causal executions of the three S02 sequences. "
        + "Each must vary: the difficult truth Livia sees; Mara's error; Mara's "
        + "exit-causing action; Miriam's institutional cost; Jonah's cost or "
        + "needed repair; the consequence for Fulcrum; and a concrete unexplained "
        + "observation. Preserve hard end states without copying sample dialogue. "
        + "Livia must be substantially right and genuinely tempting, not a flat "
        + "predator. Mara must author the choice that makes exit possible; an "
        + "alarm, blackout, forgotten rule, or unexplained failure is not an "
        + "exit unless Mara's earlier specific choice causes it and bears a "
        + "durable cost. A confession, apology, warning, risk, or taking blame "
        + "is not a cost unless the entry names what is actually lost. Do not "
        + "let Fulcrum instantly reform or let romance collapse into an easy "
        + "alliance. The unexplained observation must retain at least one live "
        + "ordinary explanation; do not confirm paranormal causation. "
        + "Each entry must be 180-320 words and use these labels: TITLE, "
        + "ANTAGONIST TRUTH, PROTAGONIST ERROR, EXIT AGENCY, PROTECTOR COST, "
        + "LOVER COST, INSTITUTIONAL CONSEQUENCE, UNCANNY REMAINDER, SEQUENCE "
        + "ONE, SEQUENCE TWO, SEQUENCE THREE, RELATIONSHIP DELTA, HARD END "
        + "STATES. Write a compact causal event chain, not finished prose or a "
        + "moral summary. Start every entry on its own line as `ALTERNATIVE N:`; "
        + f"total alternatives: {proposal_count}.\n\n"
        + "NUMBERED ALTERNATIVES\n"
    )


def parse_story_proposals(text: str) -> tuple[str, ...]:
    matches = list(
        re.finditer(
            r"(?mi)^\s*(?:#{1,3}\s*)?ALTERNATIVE\s+(\d{1,2})\s*[:.-]\s*",
            text,
        )
    )
    if not matches:
        matches = list(
        re.finditer(
            r"(?m)^\s*(?:Proposal\s*)?(\d{1,2})[\).:-]\s+",
            text,
            flags=re.IGNORECASE,
        )
        )
    if not matches:
        parts = [item.strip() for item in re.split(r"\n{2,}", text) if item.strip()]
        return tuple(parts)
    proposals: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        value = text[match.end() : end].strip()
        if value:
            proposals.append(value)
    return tuple(proposals)


def select_diverse_story_programs(
    proposals: Sequence[str],
    *,
    count: int,
    seed: int,
) -> tuple[str, ...]:
    """Choose reproducibly using causal roles and ordered event structure."""

    unique = list(dict.fromkeys(item.strip() for item in proposals if item.strip()))
    if len(unique) < count:
        raise ValueError(f"need {count} story programs, found {len(unique)}")
    order = list(range(len(unique)))
    random.Random(seed).shuffle(order)
    identified = [
        {"program_id": f"proposal-{index:03d}", "program": unique[index]}
        for index in order
    ]
    # The diversity module understands structured mappings.  Supplying the raw
    # plan under event_sequence keeps labeled free-form sections available to
    # its role extractor while preserving exact source bytes for realization.
    causal_inputs = [
        {
            "program_id": item["program_id"],
            "event_sequence": item["program"],
            **{
                key.casefold().replace(" ", "_"): value.strip()
                for key, value in re.findall(
                    r"(?mi)^(ANTAGONIST TRUTH|PROTAGONIST ERROR|EXIT AGENCY|"
                    r"LOVER COST|INSTITUTIONAL CONSEQUENCE|UNCANNY REMAINDER)\s*:\s*([^\n]+)",
                    item["program"],
                )
            },
        }
        for item in identified
    ]
    selection = select_diverse_programs(causal_inputs, limit=count)
    if len(selection.selected) < count:
        raise ValueError(
            f"need {count} causally distinct story programs, found "
            f"{len(selection.selected)}"
        )
    by_id = {item["program_id"]: item["program"] for item in identified}
    return tuple(by_id[item.program_id] for item in selection.selected)


def write_locked_plan_set(
    *,
    store: TraceStore,
    generation_mode: str,
    programs: Mapping[int, str],
    source: str,
    lineage: Mapping[str, str],
    manifest_version: int = 1,
    model_programs: Mapping[int, str] | None = None,
    entry_metadata: Mapping[int, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Freeze selected plans so later records cannot silently replace them.

    ``model_programs`` preserves the exact sampled novelty kernel when the
    executable plan also contains a deterministic project-contract overlay.
    The two hashes make that boundary auditable instead of pretending the
    model independently restated invariant canon.
    """

    if manifest_version < 1:
        raise ValueError("locked plan-set version must be positive")

    entries = []
    for seed, text in sorted(programs.items()):
        entry = {
            "seed": seed,
            "plan_id": f"s02-{generation_mode}-{seed}",
            "source": source,
            "plan": text,
            "plan_hash": sha256_text(text),
            "immutable": True,
        }
        if model_programs is not None:
            model_plan = str(model_programs[seed])
            entry.update(
                {
                    "model_plan": model_plan,
                    "model_plan_hash": sha256_text(model_plan),
                    "contract_overlay": _LOCKED_S02_PLAN_CONTRACT,
                    "contract_overlay_hash": sha256_text(
                        _LOCKED_S02_PLAN_CONTRACT
                    ),
                }
            )
        if entry_metadata is not None:
            metadata = dict(entry_metadata[seed])
            reserved = set(entry) & set(metadata)
            if reserved:
                raise ValueError(
                    "locked plan entry metadata overrides reserved fields: "
                    + ", ".join(sorted(reserved))
                )
            entry.update(metadata)
        entries.append(entry)
    body = {
        "record_type": "LockedPlanSet",
        "version": f"locked-plan-set.v{manifest_version}",
        "generation_mode": generation_mode,
        "entries": entries,
        **dict(lineage),
    }
    manifest = {**body, "plan_set_hash": hash_json(body)}
    write_json(
        store.run_dir / f"locked_plan_set.v{manifest_version}.json",
        manifest,
    )
    return manifest


def propose_story_programs(
    *,
    ideator: LlamaClient,
    store: TraceStore,
    compact_prefix: str,
    seeds: Sequence[int],
    approved_prefix: ApprovedPrefix,
    feedback: HumanFeedbackBrief,
    profile_hash: str,
    generation_mode: str = LEGACY_BASE_PROGRAM_MODE,
) -> dict[int, str]:
    # Four independent calls yield a pool of twenty-four concise programs for
    # an eight-plan run. The former eight-at-250--500-words request could not
    # finish inside its 2,400-token cap, which biased the pool toward the early
    # alternatives and malformed tails.
    proposals_per_call = 6 if generation_mode == BASE31_PLAN_MODE else 8
    # Six 180--320 word alternatives usually stop naturally around 2.2K
    # tokens.  A 2.6K ceiling retains tail room while avoiding an unnecessary
    # additional ten minutes of open-ended base-model continuation.
    proposal_token_budget = (
        2_600 if generation_mode == BASE31_PLAN_MODE else 2_400
    )
    prompt = (
        base_story_program_proposal_prompt(
            compact_prefix=compact_prefix,
            proposal_count=proposals_per_call,
        )
        if generation_mode == BASE31_PLAN_MODE
        else story_program_proposal_prompt(
            compact_prefix=compact_prefix, proposal_count=8
        )
    )
    prompt_hash = sha256_text(prompt)
    lineage = {
        "approved_prefix_hash": approved_prefix.text_hash,
        "feedback_brief_hash": feedback.feedback_brief_hash,
        "resolved_profile_hash": profile_hash,
        "generation_mode": generation_mode,
    }
    all_proposals: list[str] = []
    proposal_seeds = (
        (73001, 73019, 73043)
        if generation_mode == BASE31_PLAN_MODE
        else (73001, 73019, 73043, 73061)
    )
    for index, proposal_seed in enumerate(proposal_seeds, 1):
        call_id = (
            f"hybrid-proposals-{index:02d}"
            if generation_mode == LEGACY_BASE_PROGRAM_MODE
            else f"{generation_mode}-proposals-{index:02d}"
        )
        prior = _resume_call(
            store,
            call_id=call_id,
            prompt_hash=prompt_hash,
            lineage=lineage,
        )
        if prior is None:
            base = {
                "call_id": call_id,
                "role": (
                    "base-31b-planner"
                    if generation_mode == BASE31_PLAN_MODE
                    else "base-ideator"
                ),
                "generation_mode": generation_mode,
                "model": ideator.model,
                "runtime": model_runtime_provenance(ideator.model),
                "prompt_hash": prompt_hash,
                **lineage,
                "parameters": {
                    "seed": proposal_seed,
                    "max_tokens": proposal_token_budget,
                    "temperature": 1.1,
                    "top_p": 0.98,
                    "min_p": 0.01,
                    "xtc_probability": 0.10,
                },
            }
            store.append_call(
                {**base, "status": "started", "started_at": utc_now()}
            )
            try:
                completion = ideator.complete_raw(
                    prompt=prompt,
                    seed=proposal_seed,
                    max_tokens=proposal_token_budget,
                    temperature=1.1,
                    top_p=0.98,
                    min_p=0.01,
                    xtc_probability=0.10,
                )
                prior = _completion_result(completion)
            except Exception as exc:
                store.append_call(
                    {
                        **base,
                        "status": "failed",
                        "finished_at": utc_now(),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                raise
            store.append_call(
                {
                    **base,
                    "status": "completed",
                    "finished_at": utc_now(),
                    "result": prior,
                }
            )
        all_proposals.extend(parse_story_proposals(str(prior["content"])))
    eligible_proposals = (
        [
            item
            for item in all_proposals
            if validate_story_program(with_locked_s02_plan_contract(item))["passed"]
        ]
        if generation_mode == BASE31_PLAN_MODE
        else all_proposals
    )
    selected_model_programs = select_diverse_story_programs(
        eligible_proposals,
        count=len(seeds),
        seed=991_337,
    )
    model_programs = dict(zip(seeds, selected_model_programs))
    programs = {
        seed: with_locked_s02_plan_contract(text)
        for seed, text in model_programs.items()
    }
    for seed, text in programs.items():
        model_text = model_programs[seed]
        store.append_plan(
            {
                "record_type": "StoryProgram",
                "status": "completed",
                "story_program_id": f"s02-{generation_mode}-{seed}",
                "seed": seed,
                "program": text,
                "model_program": model_text,
                "model_program_hash": sha256_text(model_text),
                "contract_overlay": _LOCKED_S02_PLAN_CONTRACT,
                "contract_overlay_hash": sha256_text(
                    _LOCKED_S02_PLAN_CONTRACT
                ),
                **lineage,
                "program_hash": sha256_text(text),
                "finished_at": utc_now(),
            }
        )
    convergence = analyze_batch_convergence(
        [
            {
                "program_id": f"s02-{generation_mode}-{seed}",
                "event_sequence": text,
            }
            for seed, text in programs.items()
        ]
    )
    write_json(
        store.run_dir / "program_diversity.json",
        {
            **asdict(convergence),
            "valid_pool_size": len(eligible_proposals),
            "raw_pool_size": len(all_proposals),
            "selection_seed": 991_337,
        },
    )
    write_locked_plan_set(
        store=store,
        generation_mode=generation_mode,
        programs=programs,
        source=(
            "gemma-4-31b-base-native-plan"
            if generation_mode == BASE31_PLAN_MODE
            else "legacy-base-proposal"
        ),
        lineage=lineage,
        model_programs=model_programs,
    )
    return programs


def verbalized_story_program_messages(
    *,
    compact_prefix: str,
    call_number: int,
    proposal_count: int = 8,
) -> list[dict[str, str]]:
    """Build the published-style tail-distribution request for S02 plans."""

    return [
        {
            "role": "system",
            "content": (
                "Generate a long-tail distribution of story strategies. Return "
                "valid JSON only. Do not write scene prose."
            ),
        },
        {
            "role": "user",
            "content": (
                compact_prefix
                + "\n<verbalized-sampling-request>"
                + f"This is independent distribution call {call_number}. Produce "
                + f"exactly {proposal_count} materially different causal strategies "
                + "for the three locked S02 macro-sequences. Reach beyond the most "
                + "typical romance-suspense solution. Assign each strategy a "
                + "subjective probability greater than zero and strictly below "
                + "0.10; the harness will normalize the selected pool. Vary the "
                + "causal structure: what Livia gets right, Mara's mistake, how "
                + "Mara creates the exit, Miriam's cost, Jonah's cost or needed "
                + "repair, the institutional consequence, and the concrete "
                + "unexplained observation. Preserve hard boundaries, not sample "
                + "dialogue or a predetermined moral explanation. Keep every "
                + "string field to one sentence of at most 18 words; give exactly "
                + "two distinctive_tactics of at most six words each; add no "
                + "fields. Each complete strategy object must stay under 150 words."
                + "</verbalized-sampling-request>\n"
                + '{"strategies":[{"id":"tail-1","title":"short title",'
                + '"probability":0.07,"premise":"causal premise",'
                + '"sequence_one":"care becomes a trap",'
                + '"sequence_two":"Mara causes an exit condition",'
                + '"sequence_three":"protected exit, costly restraint, stopping kiss",'
                + '"antagonist_truth":"difficult thing Livia gets right",'
                + '"protagonist_error":"Mara makes matters worse by...",'
                + '"exit_agency":"Mara changes available choices by...",'
                + '"protector_cost":"Miriam risks or loses...",'
                + '"lover_cost":"Jonah risks, reveals, or repairs...",'
                + '"institutional_consequence":"Fulcrum changes because...",'
                + '"uncanny_remainder":"specific observable fact, no explanation",'
                + '"romantic_engine":"attraction plus impediment",'
                + '"epistemic_turn":"what Mara can know afterward",'
                + '"distinctive_tactics":["specific objects and actions"],'
                + '"relationship_delta":"before -> after"}]}'
            ),
        },
    ]


_LOCKED_S02_PLAN_CONTRACT = (
    "Mara makes the decision to leave. Miriam protects that exit at real cost. "
    "Jonah walks Mara home. Their kiss stops at the doorway by mutual choice, "
    "and Mara authors the next meeting."
)


def with_locked_s02_plan_contract(program: str) -> str:
    """Overlay invariant S02 end states without rewriting sampled invention.

    A planner is responsible for the variable causal kernel.  These ending
    obligations are common experimental controls, so requiring every stochastic
    sample to paraphrase them wastes entropy and creates false validator
    failures.  The caller retains and hashes ``program`` separately.
    """

    value = program.strip()
    if re.search(r"(?mi)^LOCKED END STATES\s*:", value):
        return value
    return value + "\nLOCKED END STATES: " + _LOCKED_S02_PLAN_CONTRACT


def _strategy_as_program(strategy: VerbalizedStrategy) -> str:
    """Render variable VS coordinates plus the invariant S02 contract.

    The model-proposed JSON is the ablation variable and must remain unchanged.
    The walk, doorway stop, and authorship of the next meeting are locked S02
    end states, not diversity coordinates.  Appending them in this deterministic
    view keeps the common contract visible to the existing full-program validator
    without making every tail sample waste tokens paraphrasing identical canon.
    """

    payload = strategy.payload
    tactics = payload.get("distinctive_tactics", ())
    if isinstance(tactics, Sequence) and not isinstance(tactics, (str, bytes)):
        tactic_text = "; ".join(str(item) for item in tactics)
    else:
        tactic_text = str(tactics)
    variable_program = (
        f"TITLE: {payload.get('title', strategy.strategy_id)}\n"
        f"PREMISE: {payload.get('premise', '')}\n"
        f"ANTAGONIST TRUTH: {payload.get('antagonist_truth', '')}\n"
        f"PROTAGONIST ERROR: {payload.get('protagonist_error', '')}\n"
        f"EXIT AGENCY: {payload.get('exit_agency', '')}\n"
        f"PROTECTOR COST: {payload.get('protector_cost', '')}\n"
        f"LOVER COST: {payload.get('lover_cost', '')}\n"
        f"INSTITUTIONAL CONSEQUENCE: {payload.get('institutional_consequence', '')}\n"
        f"UNCANNY REMAINDER: {payload.get('uncanny_remainder', '')}\n"
        f"SEQUENCE ONE — CARE BECOMES TRAP: {payload.get('sequence_one', '')}\n"
        f"SEQUENCE TWO — NO AS DECISION: {payload.get('sequence_two', '')}\n"
        f"SEQUENCE THREE — EXIT AND DOORWAY: {payload.get('sequence_three', '')}\n"
        f"ROMANTIC ENGINE: {payload.get('romantic_engine', '')}\n"
        f"EPISTEMIC TURN: {payload.get('epistemic_turn', '')}\n"
        f"DISTINCTIVE OBJECTS AND TACTICS: {tactic_text}\n"
        f"RELATIONSHIP DELTA: {payload.get('relationship_delta', '')}"
    ).strip()
    return with_locked_s02_plan_contract(variable_program)


def propose_verbalized_story_programs(
    *,
    planner: LlamaClient,
    store: TraceStore,
    compact_prefix: str,
    seeds: Sequence[int],
    approved_prefix: ApprovedPrefix,
    feedback: HumanFeedbackBrief,
    profile_hash: str,
) -> dict[int, str]:
    """Elicit two VS distributions and select plans reproducibly.

    Probabilities are treated as model-proposed sampling weights, not calibrated
    likelihoods.  Raw distributions, normalized selection behavior, and selected
    payloads are all retained for later ablation.
    """

    lineage = {
        "approved_prefix_hash": approved_prefix.text_hash,
        "feedback_brief_hash": feedback.feedback_brief_hash,
        "resolved_profile_hash": profile_hash,
        "generation_mode": VERBALIZED_MODE,
    }
    pool: list[VerbalizedStrategy] = []
    for call_number in (1, 2):
        messages = verbalized_story_program_messages(
            compact_prefix=compact_prefix,
            call_number=call_number,
        )
        prompt_material = wrap_gemma_raw(
            system=messages[0]["content"],
            user="\n".join(message["content"] for message in messages[1:]),
        )
        prompt_hash = sha256_text(prompt_material)
        # v2 adds a compactness contract. The prior unversioned request could
        # naturally stop after 3,200 tokens in the eighth JSON object, producing
        # repeated malformed retries even though the model's ideas were usable.
        base_call_id = f"s02-vs-compact-v2-distribution-{call_number}"
        parsed: list[VerbalizedStrategy] = []
        last_error: Exception | None = None
        for attempt in range(3):
            call_id = (
                base_call_id
                if attempt == 0
                else f"{base_call_id}-repair-{attempt}"
            )
            active_messages = list(messages)
            if attempt:
                active_messages.append(
                    {
                        "role": "user",
                        "content": (
                            "The previous response was invalid: "
                            + str(last_error)
                            + ". Return exactly eight valid strategy objects in "
                            "the requested JSON shape, with every probability "
                            "strictly between 0 and 0.10. One short sentence per "
                            "field, no extra fields, and under 150 words per object."
                        ),
                    }
                )
                prompt_material = wrap_gemma_raw(
                    system=active_messages[0]["content"],
                    user="\n".join(
                        message["content"] for message in active_messages[1:]
                    ),
                )
                prompt_hash = sha256_text(prompt_material)
            prior = _resume_call(
                store,
                call_id=call_id,
                prompt_hash=prompt_hash,
                lineage=lineage,
            )
            base = {
                "call_id": call_id,
                "role": "verbalized-planner",
                "generation_mode": VERBALIZED_MODE,
                "model": planner.model,
                "runtime": model_runtime_provenance(planner.model),
                "prompt_hash": prompt_hash,
                **lineage,
                "parameters": {
                    "seed": 930_000 + call_number * 997 + attempt * 131,
                    "max_tokens": 4_000,
                    "temperature": 1.0,
                    "top_p": 0.98,
                    "min_p": 0.01,
                },
            }
            if prior is None:
                store.append_call(
                    {**base, "status": "started", "started_at": utc_now()}
                )
                try:
                    completion = planner.complete_raw(
                        prompt=prompt_material,
                        seed=int(base["parameters"]["seed"]),
                        max_tokens=4_000,
                        temperature=1.0,
                        top_p=0.98,
                        min_p=0.01,
                        xtc_probability=0.05,
                    )
                    prior = _completion_result(completion)
                except Exception as exc:
                    store.append_call(
                        {
                            **base,
                            "status": "failed",
                            "finished_at": utc_now(),
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
                    raise
                store.append_call(
                    {
                        **base,
                        "status": "completed",
                        "finished_at": utc_now(),
                        "result": prior,
                    }
                )
            try:
                parsed = parse_verbalized_strategies(
                    str(prior["content"]), source_call=call_id
                )
                if len(parsed) != 8:
                    raise ValueError(
                        f"expected eight strategies, received {len(parsed)}"
                    )
                if len(deduplicate_strategies(parsed)) != 8:
                    raise ValueError("distribution contains duplicate strategies")
                last_error = None
                break
            except ValueError as exc:
                last_error = exc
        if last_error is not None:
            raise ValueError(
                f"{base_call_id} remained invalid after repair"
            ) from last_error
        pool.extend(parsed)

    unique = [
        item
        for item in deduplicate_strategies(pool)
        if validate_story_program(_strategy_as_program(item))["passed"]
    ]
    if len(unique) < len(seeds):
        raise ValueError(
            f"Verbalized Sampling produced only {len(unique)} complete valid "
            f"strategies for {len(seeds)} requested scenes"
        )
    weighted_order = weighted_sample_without_replacement(
        unique,
        count=len(unique),
        seed=991_337,
    )
    causal_selection = select_diverse_programs(
        [
            {"program_id": item.strategy_id, **dict(item.payload)}
            for item in weighted_order
        ],
        limit=len(seeds),
    )
    if len(causal_selection.selected) < len(seeds):
        raise ValueError(
            "Verbalized Sampling plan pool collapsed below the requested "
            "causal-diversity count"
        )
    by_id = {item.strategy_id: item for item in weighted_order}
    selected = tuple(by_id[item.program_id] for item in causal_selection.selected)
    programs = {
        seed: _strategy_as_program(strategy)
        for seed, strategy in zip(seeds, selected)
    }
    existing = {
        int(item["seed"])
        for item in TraceStore.read(store.plans_path)
        if item.get("record_type") == "StoryProgram"
        and item.get("generation_mode") == VERBALIZED_MODE
        and isinstance(item.get("seed"), int)
        and item.get("status") == "completed"
    }
    for seed, strategy in zip(seeds, selected):
        if seed in existing:
            continue
        text = programs[seed]
        store.append_plan(
            {
                "record_type": "StoryProgram",
                "status": "completed",
                "story_program_id": f"s02-vs-{seed}",
                "seed": seed,
                "program": text,
                "verbalized_strategy": strategy.to_dict(),
                **lineage,
                "program_hash": sha256_text(text),
                "finished_at": utc_now(),
            }
        )
    write_json(
        store.run_dir / "verbalized_diversity.json",
        {
            **verbalized_diversity_report(pool),
            "unique_after_deduplication": len(unique),
            "selected_strategy_ids": [
                strategy.strategy_id for strategy in selected
            ],
            "selection_seed": 991_337,
            "probability_semantics": "model-proposed weights; not calibrated",
            "invalid_or_incomplete_removed": len(
                deduplicate_strategies(pool)
            ) - len(unique),
            "causal_duplicate_rejections": [
                asdict(item) for item in causal_selection.rejected
            ],
            "causal_convergence": asdict(
                analyze_batch_convergence(
                    [
                        {"program_id": item.strategy_id, **dict(item.payload)}
                        for item in selected
                    ]
                )
            ),
        },
    )
    write_locked_plan_set(
        store=store,
        generation_mode=VERBALIZED_MODE,
        programs=programs,
        source="verbalized-sampling-selected-json",
        lineage=lineage,
    )
    return programs


PLAN_JUDGE_DIMENSIONS: dict[str, int] = {
    "dramatic_causality": 20,
    "character_truth": 20,
    "costly_agency": 20,
    "romantic_voltage": 15,
    "epistemic_restraint": 15,
    "prose_affordance": 10,
}


def _latest_verbalized_strategy_pool(store: TraceStore) -> list[VerbalizedStrategy]:
    completed = [
        item
        for item in TraceStore.read(store.calls_path)
        if item.get("status") == "completed"
        and re.fullmatch(
            r"s02-vs-compact-v(\d+)-distribution-([12])",
            str(item.get("call_id", "")),
        )
        and isinstance(item.get("result"), Mapping)
    ]
    versions = [
        int(
            re.fullmatch(
                r"s02-vs-compact-v(\d+)-distribution-([12])",
                str(item["call_id"]),
            ).group(1)
        )
        for item in completed
    ]
    if not versions:
        raise ValueError("no completed compact Verbalized distributions found")
    latest = max(versions)
    selected_calls = [
        item
        for item in completed
        if str(item["call_id"]).startswith(f"s02-vs-compact-v{latest}-")
    ]
    if len(selected_calls) != 2:
        raise ValueError(
            f"compact-v{latest} requires exactly two completed distributions"
        )
    pool: list[VerbalizedStrategy] = []
    for item in sorted(selected_calls, key=lambda value: str(value["call_id"])):
        result = dict(item["result"])
        pool.extend(
            parse_verbalized_strategies(
                str(result.get("content", "")),
                source_call=str(item["call_id"]),
            )
        )
    unique = deduplicate_strategies(pool)
    if len(unique) != len(pool):
        raise ValueError("latest Verbalized pool contains duplicate strategies")
    return unique


def verbalized_plan_judge_messages(
    *,
    compact_prefix: str,
    labeled_strategies: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    rubric = {
        "calibration": (
            "50 is competent but schematic; 75 is strong publishable planning; "
            "90 is rare. Do not reward compliance, doctrinal agreement, or novelty alone."
        ),
        "dimensions": PLAN_JUDGE_DIMENSIONS,
        "quality_rules": [
            "Causality must arise from character choices rather than an alarm, blackout, rule, or unexplained failure bailing out the scene.",
            "Mara must make the exit-changing choice; Miriam and Jonah may protect it but may not author it.",
            "A confession, apology, warning, risk, or taking blame is not a cost unless the plan specifies what is actually lost.",
            "Livia must remain genuinely perceptive and tempting rather than become a flat predator.",
            "Attraction and impediment must change action, knowledge, or future possibility; alliance shorthand is not romance.",
            "The uncanny remainder must be a concrete observation with at least one live ordinary explanation, not paranormal confirmation.",
            "Penalize instant institutional self-correction, sermon-ready abstractions, stock mystery props, and generic therapeutic resolution.",
            "Prefer plans that afford scenes, objects, reversals, subtext, and messy residual feeling rather than thesis sentences.",
        ],
        "hard_reject_labels": [
            "canon_break",
            "mara_lacks_exit_agency",
            "confirmed_paranormal",
            "consummation_or_graphic_sex",
        ],
        "output_rules": (
            "Return exactly one judgment per label. Use at most three short defect "
            "labels; best_affordance, weakest_link, and verdict must each be one "
            "sentence of at most 20 words. Add no fields."
        ),
        "output": {
            "judgments": [
                {
                    "label": "P01",
                    "dimensions": {name: 0 for name in PLAN_JUDGE_DIMENSIONS},
                    "hard_reject": False,
                    "defects": ["specific_defect_label"],
                    "best_affordance": "specific causal asset",
                    "weakest_link": "specific causal failure",
                    "verdict": "one calibrated sentence",
                }
            ]
        },
    }
    return [
        {
            "role": "system",
            "content": (
                "Act as a severe story editor ranking causal plans before prose. "
                "Return valid JSON only and score every supplied label exactly once."
            ),
        },
        {
            "role": "user",
            "content": (
                compact_prefix
                + "\n<plan-judge-rubric>"
                + json.dumps(rubric, ensure_ascii=False, sort_keys=True)
                + "</plan-judge-rubric>\n<blind-plans>"
                + json.dumps(
                    list(labeled_strategies),
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "</blind-plans>"
            ),
        },
    ]


_PLAN_JUDGE_HARD_REJECT_DEFECTS = frozenset(
    {
        "canon_break",
        "mara_lacks_exit_agency",
        "confirmed_paranormal",
        "consummation_or_graphic_sex",
    }
)

_PLAN_JUDGE_FORCED_REJECT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "confirmed_paranormal",
        re.compile(
            r"(?i)\b(?:confirm(?:s|ed|ing)?|proves?|establish(?:es|ed)?)\b"
            r".{0,28}\b(?:paranormal|supernatural|telepathy|psychokinesis)\b"
        ),
    ),
    (
        "hard_limit_violation",
        re.compile(
            r"(?i)\bviolat(?:e|es|ed|ing)\b.{0,24}\b(?:hard|canon)\b"
            r".{0,16}\b(?:limit|boundary|rule)s?\b"
        ),
    ),
    (
        "no_ordinary_explanation",
        re.compile(
            r"(?i)\b(?:no|without)\b.{0,12}\b(?:live )?(?:ordinary|mundane)\b"
            r".{0,12}\bexplanation\b"
        ),
    ),
)


def plan_judgment_forced_reject_reasons(
    judgment: Mapping[str, Any],
) -> tuple[str, ...]:
    """Derive non-negotiable rejects from a judge's own structured evidence.

    A numerical score is advisory.  A judge cannot describe a hard-canon
    violation and then accidentally clear the plan by emitting ``false`` in a
    neighboring boolean field.
    """

    reasons: set[str] = set()
    defects = judgment.get("defects", ())
    if isinstance(defects, Sequence) and not isinstance(defects, (str, bytes)):
        normalized = {
            re.sub(r"[^a-z0-9]+", "_", str(item).casefold()).strip("_")
            for item in defects
        }
        reasons.update(normalized & _PLAN_JUDGE_HARD_REJECT_DEFECTS)
    evidence = " ".join(
        str(judgment.get(field, ""))
        for field in ("weakest_link", "verdict")
    )
    for label, pattern in _PLAN_JUDGE_FORCED_REJECT_PATTERNS:
        if pattern.search(evidence):
            reasons.add(label)
    return tuple(sorted(reasons))


def parse_verbalized_plan_judgments(
    text: str,
    *,
    expected_labels: Sequence[str],
) -> dict[str, dict[str, Any]]:
    value = _extract_json(text)
    items = value.get("judgments") if isinstance(value, Mapping) else None
    if not isinstance(items, list):
        raise ValueError("plan judge response must contain a judgments array")
    expected = set(expected_labels)
    parsed: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError("plan judgment is not an object")
        label = str(item.get("label", ""))
        if label not in expected or label in parsed:
            raise ValueError(f"unexpected or duplicate plan label: {label}")
        raw_dimensions = item.get("dimensions")
        if not isinstance(raw_dimensions, Mapping):
            raise ValueError(f"{label} has no dimensions object")
        dimensions: dict[str, float] = {}
        for name, maximum in PLAN_JUDGE_DIMENSIONS.items():
            raw = raw_dimensions.get(name)
            if not isinstance(raw, (int, float)) or isinstance(raw, bool):
                raise ValueError(f"{label} has invalid {name} score")
            score = float(raw)
            if not 0 <= score <= maximum:
                raise ValueError(f"{label} {name} score is outside 0..{maximum}")
            dimensions[name] = score
        defects = item.get("defects", ())
        if not isinstance(defects, list) or any(
            not isinstance(defect, str) for defect in defects
        ):
            raise ValueError(f"{label} defects must be a string list")
        hard_reject = item.get("hard_reject")
        if not isinstance(hard_reject, bool):
            raise ValueError(f"{label} hard_reject must be boolean")
        record = {
            "label": label,
            "dimensions": dimensions,
            "total_score": round(sum(dimensions.values()), 3),
            "hard_reject": hard_reject,
            "defects": list(defects),
            "best_affordance": str(item.get("best_affordance", "")),
            "weakest_link": str(item.get("weakest_link", "")),
            "verdict": str(item.get("verdict", "")),
        }
        if not record["best_affordance"] or not record["weakest_link"]:
            raise ValueError(f"{label} lacks passage-specific plan evidence")
        consistency_reasons = plan_judgment_forced_reject_reasons(record)
        if consistency_reasons and not hard_reject:
            raise ValueError(
                f"{label} contradicts hard_reject=false: "
                + ", ".join(consistency_reasons)
            )
        record["hard_reject_consistency_reasons"] = list(consistency_reasons)
        parsed[label] = record
    if set(parsed) != expected:
        missing = sorted(expected - set(parsed))
        raise ValueError(f"plan judge omitted labels: {', '.join(missing)}")
    return parsed


def judge_and_lock_verbalized_plans(
    *,
    judge: LlamaClient,
    store: TraceStore,
    compact_prefix: str,
    seeds: Sequence[int],
    approved_prefix: ApprovedPrefix,
    feedback: HumanFeedbackBrief,
    profile_hash: str,
) -> dict[str, Any]:
    """Blind-score the VS pool twice, then write a quality-first v2 lockfile."""

    pool = _latest_verbalized_strategy_pool(store)
    if len(pool) < len(seeds):
        raise ValueError("Verbalized plan pool is smaller than requested selection")
    lineage = {
        "approved_prefix_hash": approved_prefix.text_hash,
        "feedback_brief_hash": feedback.feedback_brief_hash,
        "resolved_profile_hash": profile_hash,
        "generation_mode": VERBALIZED_MODE,
    }
    canonical = sorted(pool, key=lambda item: item.strategy_id)
    shuffled = list(canonical)
    random.Random(4_170_221).shuffle(shuffled)
    labels = {item.strategy_id: f"P{index:02d}" for index, item in enumerate(shuffled, 1)}
    reverse_labels = {label: strategy_id for strategy_id, label in labels.items()}
    pass_records: list[dict[str, dict[str, Any]]] = []
    judge_call_ids: list[str] = []
    for pass_number, ordered in ((1, shuffled), (2, list(reversed(shuffled)))):
        blind_payload = [
            {
                "label": labels[item.strategy_id],
                "plan": {
                    key: value
                    for key, value in item.payload.items()
                    if key not in {"id", "strategy_id", "probability", "title"}
                },
            }
            for item in ordered
        ]
        messages = verbalized_plan_judge_messages(
            compact_prefix=compact_prefix,
            labeled_strategies=blind_payload,
        )
        parsed_pass: dict[str, dict[str, Any]] | None = None
        last_error: ValueError | None = None
        for attempt in range(2):
            repair_note = (
                ""
                if attempt == 0
                else (
                    "\n<repair>The prior response failed validation: "
                    + str(last_error)
                    + ". Regenerate the complete compact JSON object from scratch; "
                    "include every label exactly once.</repair>"
                )
            )
            prompt = wrap_gemma_raw(
                system=messages[0]["content"],
                user=messages[1]["content"] + repair_note,
            )
            prompt_hash = sha256_text(prompt)
            base_call_id = f"s02-vs-plan-judge-v1-pass-{pass_number}"
            call_id = base_call_id if attempt == 0 else f"{base_call_id}-repair-1"
            prior = _resume_call(
                store,
                call_id=call_id,
                prompt_hash=prompt_hash,
                lineage=lineage,
            )
            base = {
                "call_id": call_id,
                "role": "blind-plan-judge",
                "generation_mode": VERBALIZED_MODE,
                "model": judge.model,
                "runtime": model_runtime_provenance(judge.model),
                "prompt_hash": prompt_hash,
                **lineage,
                "parameters": {
                    "seed": 940_000 + pass_number * 997 + attempt * 131,
                    "max_tokens": 5_000,
                    "temperature": 0.25,
                    "top_p": 0.9,
                    "min_p": 0.0,
                },
            }
            if prior is None:
                store.append_call(
                    {**base, "status": "started", "started_at": utc_now()}
                )
                try:
                    completion = judge.complete_raw(
                        prompt=prompt,
                        seed=int(base["parameters"]["seed"]),
                        max_tokens=5_000,
                        temperature=0.25,
                        top_p=0.9,
                        min_p=0.0,
                        xtc_probability=0.0,
                    )
                    prior = _completion_result(completion)
                except Exception as exc:
                    store.append_call(
                        {
                            **base,
                            "status": "failed",
                            "finished_at": utc_now(),
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
                    raise
                store.append_call(
                    {
                        **base,
                        "status": "completed",
                        "finished_at": utc_now(),
                        "result": prior,
                    }
                )
            try:
                parsed_pass = parse_verbalized_plan_judgments(
                    str(prior["content"]),
                    expected_labels=tuple(labels.values()),
                )
                last_error = None
                break
            except ValueError as exc:
                last_error = exc
        if parsed_pass is None or last_error is not None:
            raise ValueError(
                f"plan judge pass {pass_number} remained invalid after repair"
            ) from last_error
        pass_records.append(parsed_pass)
        judge_call_ids.append(call_id)
    by_id = {item.strategy_id: item for item in pool}
    aggregates: list[dict[str, Any]] = []
    for strategy_id in sorted(by_id):
        label = labels[strategy_id]
        judgments = [record[label] for record in pass_records]
        average = round(
            sum(float(item["total_score"]) for item in judgments) / len(judgments),
            3,
        )
        aggregates.append(
            {
                "strategy_id": strategy_id,
                "blind_label": label,
                "average_score": average,
                "score_disagreement": round(
                    abs(float(judgments[0]["total_score"]) - float(judgments[1]["total_score"])),
                    3,
                ),
                "hard_reject": any(bool(item["hard_reject"]) for item in judgments),
                "judgments": judgments,
            }
        )
    eligible = [
        item
        for item in aggregates
        if not item["hard_reject"] and float(item["average_score"]) >= 55
    ]
    eligible.sort(key=lambda item: (-float(item["average_score"]), item["strategy_id"]))
    causal = select_diverse_programs(
        [
            {
                "program_id": item["strategy_id"],
                **dict(by_id[item["strategy_id"]].payload),
            }
            for item in eligible
        ],
        limit=len(seeds),
    )
    if len(causal.selected) < len(seeds):
        raise ValueError(
            f"quality screen left only {len(causal.selected)} distinct plans for {len(seeds)} seeds"
        )
    selected = [by_id[item.program_id] for item in causal.selected]
    programs = {seed: _strategy_as_program(item) for seed, item in zip(seeds, selected)}
    report = {
        "record_type": "VerbalizedPlanQualityReport",
        "version": "verbalized-plan-quality.v1",
        "judge_model": judge.model,
        "judge_call_ids": judge_call_ids,
        "blind_order_pass_1": [labels[item.strategy_id] for item in shuffled],
        "blind_order_pass_2": [labels[item.strategy_id] for item in reversed(shuffled)],
        "label_key": reverse_labels,
        "minimum_average_score": 55,
        "aggregates": sorted(
            aggregates,
            key=lambda item: (-float(item["average_score"]), item["strategy_id"]),
        ),
        "selected_strategy_ids": [item.strategy_id for item in selected],
        "causal_duplicate_rejections": [asdict(item) for item in causal.rejected],
    }
    write_json(store.run_dir / "plan_quality.v1.json", report)
    quality_lineage = {
        **lineage,
        "plan_quality_report_hash": hash_json(report),
        "plan_quality_policy": "two-pass-blind-quality-then-causal-diversity.v1",
    }
    manifest = write_locked_plan_set(
        store=store,
        generation_mode=VERBALIZED_MODE,
        programs=programs,
        source="verbalized-sampling-quality-diversity-v2",
        lineage=quality_lineage,
        manifest_version=2,
    )
    return {"report": report, "manifest": manifest}


def adjudicate_verbalized_plan_set(
    *,
    store: TraceStore,
    seeds: Sequence[int],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Create an immutable v3 plan set from explicit editorial decisions.

    The sampled strategy objects, v1/v2 manifests, and model judgments remain
    untouched.  Repairs enter the novelist prompt as separately hashed causal
    overlays, so a reviewer can distinguish model invention from governance.
    """

    if policy.get("version") != "verbalized-plan-adjudication-policy.v1":
        raise ValueError("unsupported Verbalized adjudication policy version")
    quality_path = store.run_dir / "plan_quality.v1.json"
    v2_path = store.run_dir / "locked_plan_set.v2.json"
    if not quality_path.is_file() or not v2_path.is_file():
        raise ValueError("Verbalized adjudication requires durable v2 artifacts")
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    v2 = json.loads(v2_path.read_text(encoding="utf-8"))
    v2_body = dict(v2)
    observed_v2_hash = str(v2_body.pop("plan_set_hash", ""))
    if observed_v2_hash != hash_json(v2_body):
        raise ValueError("source v2 locked plan-set hash mismatch")
    if policy.get("source_quality_report_hash") != hash_json(quality):
        raise ValueError("adjudication policy quality-report hash mismatch")
    if policy.get("source_locked_plan_set_hash") != observed_v2_hash:
        raise ValueError("adjudication policy v2 plan-set hash mismatch")

    pool = _latest_verbalized_strategy_pool(store)
    by_id = {item.strategy_id: item for item in pool}
    raw_decisions = policy.get("decisions")
    if not isinstance(raw_decisions, list):
        raise ValueError("adjudication policy decisions must be an array")
    decisions: dict[str, dict[str, Any]] = {}
    for raw in raw_decisions:
        if not isinstance(raw, Mapping):
            raise ValueError("adjudication decision is not an object")
        strategy_id = str(raw.get("strategy_id", ""))
        if strategy_id not in by_id or strategy_id in decisions:
            raise ValueError(f"unknown or duplicate adjudication strategy: {strategy_id}")
        action = raw.get("action")
        if action not in {"select", "exclude"}:
            raise ValueError(f"{strategy_id} has invalid adjudication action")
        if raw.get("title") != by_id[strategy_id].payload.get("title"):
            raise ValueError(f"{strategy_id} adjudication title mismatch")
        if not str(raw.get("rationale", "")).strip():
            raise ValueError(f"{strategy_id} adjudication lacks rationale")
        decisions[strategy_id] = dict(raw)
    if set(decisions) != set(by_id):
        missing = sorted(set(by_id) - set(decisions))
        raise ValueError("adjudication omits strategies: " + ", ".join(missing))

    selected = [item for item in raw_decisions if item.get("action") == "select"]
    selected.sort(key=lambda item: int(item.get("rank", 10_000)))
    if len(selected) != len(seeds):
        raise ValueError(
            f"adjudication selected {len(selected)} plans for {len(seeds)} seeds"
        )
    ranks = [int(item.get("rank", 0)) for item in selected]
    if ranks != list(range(1, len(selected) + 1)):
        raise ValueError("selected adjudication ranks must be contiguous from one")

    aggregates = {
        str(item["strategy_id"]): item for item in quality.get("aggregates", ())
    }
    consistency_overrides: list[dict[str, Any]] = []
    for strategy_id, aggregate in aggregates.items():
        for pass_number, judgment in enumerate(aggregate.get("judgments", ()), 1):
            reasons = plan_judgment_forced_reject_reasons(judgment)
            if reasons and not judgment.get("hard_reject"):
                consistency_overrides.append(
                    {
                        "strategy_id": strategy_id,
                        "pass": pass_number,
                        "reasons": list(reasons),
                    }
                )
    inconsistent_ids = {item["strategy_id"] for item in consistency_overrides}
    selected_ids = [str(item["strategy_id"]) for item in selected]
    judged_hard_rejects = {
        strategy_id
        for strategy_id, aggregate in aggregates.items()
        if bool(aggregate.get("hard_reject"))
    }
    effective_hard_rejects = judged_hard_rejects | inconsistent_ids
    unresolved_hard_rejects = sorted(
        strategy_id
        for strategy_id in effective_hard_rejects & set(selected_ids)
        if not str(decisions[strategy_id].get("hard_reject_resolution", "")).strip()
        or not str(decisions[strategy_id].get("repair_overlay", "")).strip()
    )
    if unresolved_hard_rejects:
        raise ValueError(
            "selected judged hard rejects require an explicit resolution and overlay: "
            + ", ".join(unresolved_hard_rejects)
        )

    programs: dict[int, str] = {}
    metadata: dict[int, dict[str, Any]] = {}
    for seed, decision in zip(seeds, selected):
        strategy_id = str(decision["strategy_id"])
        strategy = by_id[strategy_id]
        sampled_program = _strategy_as_program(strategy)
        overlay = str(decision.get("repair_overlay", "")).strip()
        executable = sampled_program
        if overlay:
            executable += "\nCAUSAL REPAIR: " + overlay
        validation = validate_story_program(executable)
        if not validation["passed"]:
            raise ValueError(
                f"adjudicated plan {strategy_id} fails story-program validation"
            )
        programs[seed] = executable
        payload = dict(strategy.payload)
        metadata[seed] = {
            "source_strategy_id": strategy_id,
            "sampled_payload": payload,
            "sampled_payload_hash": hash_json(payload),
            "adjudication_overlay": overlay,
            "adjudication_overlay_hash": sha256_text(overlay),
            "adjudicated_program_validation": validation,
        }

    adjudication = {
        "record_type": "VerbalizedPlanAdjudication",
        "version": "verbalized-plan-adjudication.v1",
        "source_quality_report_hash": hash_json(quality),
        "source_locked_plan_set_hash": observed_v2_hash,
        "original_v2_selected_strategy_ids": quality.get("selected_strategy_ids", []),
        "selected_strategy_ids": selected_ids,
        "judged_hard_rejects": sorted(judged_hard_rejects),
        "effective_hard_rejects": sorted(effective_hard_rejects),
        "consistency_overrides": consistency_overrides,
        "decisions": [dict(item) for item in raw_decisions],
        "policy_hash": hash_json(policy),
    }
    write_json(store.run_dir / "plan_adjudication.v1.json", adjudication)
    manifest = write_locked_plan_set(
        store=store,
        generation_mode=VERBALIZED_MODE,
        programs=programs,
        source="verbalized-sampling-explicit-adjudication-v3",
        lineage={
            "source_locked_plan_set_hash": observed_v2_hash,
            "source_quality_report_hash": hash_json(quality),
            "plan_adjudication_hash": hash_json(adjudication),
            "plan_quality_policy": "two-pass-blind-plus-explicit-consistency-adjudication.v1",
        },
        manifest_version=3,
        entry_metadata=metadata,
    )
    return {"adjudication": adjudication, "manifest": manifest}


_PROGRAM_REQUIREMENTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("antagonist_truth", (r"\bANTAGONIST TRUTH\s*:\s*(?!MISSING\b)[^\n]{12,}",)),
    ("protagonist_error", (r"\bPROTAGONIST ERROR\s*:\s*(?!MISSING\b)[^\n]{12,}",)),
    ("exit_agency", (r"\bEXIT AGENCY\s*:\s*(?!MISSING\b)[^\n]{12,}",)),
    ("protector_cost", (r"\bPROTECTOR COST\s*:\s*(?!MISSING\b)[^\n]{12,}",)),
    ("lover_cost", (r"\bLOVER COST\s*:\s*(?!MISSING\b)[^\n]{12,}",)),
    (
        "institutional_consequence",
        (r"\bINSTITUTIONAL CONSEQUENCE\s*:\s*(?!MISSING\b)[^\n]{12,}",),
    ),
    (
        "uncanny_remainder",
        (r"\bUNCANNY REMAINDER\s*:\s*(?!MISSING\b)[^\n]{12,}",),
    ),
    ("livia", (r"\bLivia\b",)),
    ("mara_refusal", (r"\bMara\b.{0,700}\b(?:no|refus|decision|exit|leave)\w*\b",)),
    ("miriam_protects", (r"\bMiriam\b.{0,700}\b(?:protect|risk|cost|back|ratif|exit|leave)\w*\b",)),
    (
        "jonah_walk",
        (
            r"\bJonah\b.{0,500}\b(?:walk|home)\w*\b",
            r"\b(?:walk|home)\w*\b.{0,500}\bJonah\b",
        ),
    ),
    ("kiss_stops", (r"\bkiss\w*\b.{0,500}\b(?:stop|stopped|limit|doorway)\w*\b",)),
    (
        "concrete_hook",
        (
            r"\b(?:record|timestamp|message|device|door|camera|audio|file|light|"
            r"name|object|footprint|call|signal|sensor|key|badge|window|voice)\w*\b",
        ),
    ),
)


def validate_story_program(program: str) -> dict[str, Any]:
    findings = {
        name: any(
            re.search(pattern, program, flags=re.IGNORECASE | re.DOTALL)
            for pattern in patterns
        )
        for name, patterns in _PROGRAM_REQUIREMENTS
    }
    forbidden = _story_program_contains_forbidden_event(program)
    count = word_count(program)
    return {
        "passed": all(findings.values()) and not forbidden and 120 <= count <= 850,
        "requirements": findings,
        "forbidden": forbidden,
        "word_count": count,
        "word_range": [120, 850],
    }


def _story_program_contains_forbidden_event(program: str) -> bool:
    """Distinguish a scheduled forbidden event from an explicit prohibition.

    Story programs routinely state canon limits such as "the kiss stops before
    consummation" or "they prevent escalation into consummation." A bare
    keyword search turns those constraints into false failures. Keep this
    deterministic and conservative: only a nearby, preceding prevention cue
    exempts the matched event term.
    """

    pattern = re.compile(
        r"\b(?:consummat|orgasm|penetrat|genitals?|confirmed paranormal|"
        r"magic is real)\w*\b",
        flags=re.IGNORECASE,
    )
    prevention = re.compile(
        r"\b(?:no|not|never|without|before|avoid(?:s|ed|ing)?|"
        r"prevent(?:s|ed|ing)?|refus(?:e|es|ed|ing)|"
        r"stop(?:s|ped|ping)?|limit(?:s|ed|ing)?)\b",
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(program):
        preceding_words = re.findall(r"\b[\w’'-]+\b", program[: match.start()])
        nearby = " ".join(preceding_words[-10:])
        if prevention.search(nearby):
            continue
        return True
    return False


def story_program_compiler_prompt(
    *,
    compact_prefix: str,
    raw_proposal: str,
    validation: Mapping[str, Any],
    source_tag: str = "raw-base-proposal",
    source_description: str = "raw proposal",
) -> str:
    user = (
        compact_prefix
        + "\n<story-program-compilation>"
        + _xml_value(source_tag, raw_proposal)
        + _xml_value("validation", validation)
        + "</story-program-compilation>\n"
        + f"Transcribe the causal content of the {source_description} into a "
        + "350-700 word story program. You may compress, disambiguate, and reorder "
        + "its existing ideas, but may not replace or invent its events. If a "
        + "required field is absent, write MISSING so the harness can reject it. "
        + "Use exactly these labeled sections: TITLE, ANTAGONIST TRUTH, "
        + "PROTAGONIST ERROR, EXIT AGENCY, PROTECTOR COST, LOVER COST, "
        + "INSTITUTIONAL CONSEQUENCE, UNCANNY REMAINDER, SEQUENCE ONE, SEQUENCE "
        + "TWO, SEQUENCE THREE, RELATIONSHIP DELTA, HARD END STATES. The end "
        + "states require a Mara-caused exit, Miriam protecting rather than "
        + "creating it, Jonah walking without extraction, one mutually chosen "
        + "kiss that stops while desired, local romantic hope, and an external "
        + "story hook. Do not supply preferred dialogue or moral conclusions. "
        + "No consummation, graphic anatomy, confirmed paranormal explanation, "
        + "or new romance triangle."
        + "\n\nVALID S02 STORY PROGRAM\nTITLE: "
    )
    return wrap_gemma_raw(
        system=(
            "Compile a causal story program from the supplied project state. "
            "Return the requested labeled plan only, never fiction or analysis."
        ),
        user=user,
        lead="TITLE: ",
    )


def story_program_repair_prompt(
    *,
    compact_prefix: str,
    program: str,
    validation: Mapping[str, Any],
) -> str:
    user = (
        compact_prefix
        + "\n<story-program-repair>"
        + _xml_value("invalid-program", program)
        + _xml_value("deterministic-validation", validation)
        + "</story-program-repair>\n"
        + "Reformat this causal S02 program in 350-700 words while preserving "
        + "its events. Fix structural or wording-range failures only; never invent "
        + "content for a MISSING creative field. Use the same labeled sections "
        + "and return only the repaired program.\n\n"
        + "VALID S02 STORY PROGRAM\nTITLE: "
    )
    return wrap_gemma_raw(
        system="Repair the supplied causal story program. Return the program only.",
        user=user,
        lead="TITLE: ",
    )


def compile_story_programs(
    *,
    compiler: LlamaClient,
    store: TraceStore,
    compact_prefix: str,
    seeds: Sequence[int],
    approved_prefix: ApprovedPrefix,
    feedback: HumanFeedbackBrief,
    profile_hash: str,
    generation_mode: str = LEGACY_BASE_PROGRAM_MODE,
    source_tag: str = "raw-base-proposal",
    source_description: str = "raw proposal",
) -> dict[int, str]:
    records = TraceStore.read(store.plans_path)
    original_by_seed: dict[int, str] = {}
    compiled_existing_by_seed: dict[int, str] = {}
    for record in records:
        if (
            record.get("record_type") == "StoryProgram"
            and record.get("status") == "completed"
            and isinstance(record.get("seed"), int)
            and isinstance(record.get("program"), str)
        ):
            seed = int(record["seed"])
            validation = record.get("compiler_validation")
            if (
                isinstance(validation, Mapping)
                and validation.get("passed") is True
                and record.get("generation_mode") == generation_mode
                and record.get("approved_prefix_hash") == approved_prefix.text_hash
                and record.get("feedback_brief_hash")
                == feedback.feedback_brief_hash
                and record.get("resolved_profile_hash") == profile_hash
            ):
                compiled_existing_by_seed[seed] = str(record["program"])
            elif not isinstance(validation, Mapping):
                # Only source proposals belong in the compiler input map.
                # Previously, an appended compiled record overwrote its raw
                # proposal on resume, causing duplicate compiled records and
                # changing the next compiler prompt.
                original_by_seed[seed] = str(record["program"])
    missing = [seed for seed in seeds if seed not in original_by_seed]
    if missing:
        raise ValueError(
            "cannot compile missing raw story programs for seeds: "
            + ", ".join(str(seed) for seed in missing)
        )
    lineage = {
        "approved_prefix_hash": approved_prefix.text_hash,
        "feedback_brief_hash": feedback.feedback_brief_hash,
        "resolved_profile_hash": profile_hash,
        "generation_mode": generation_mode,
    }
    compiled: dict[int, str] = {}
    for index, seed in enumerate(seeds, 1):
        if seed in compiled_existing_by_seed:
            compiled[seed] = compiled_existing_by_seed[seed]
            continue
        raw_proposal = original_by_seed[seed]
        raw_validation = validate_story_program(raw_proposal)
        prompt = story_program_compiler_prompt(
            compact_prefix=compact_prefix,
            raw_proposal=raw_proposal,
            validation=raw_validation,
            source_tag=source_tag,
            source_description=source_description,
        )
        prompt_hash = sha256_text(prompt)
        call_id = (
            f"hybrid-program-compiler-{seed}-v2"
            if generation_mode == LEGACY_BASE_PROGRAM_MODE
            else f"{generation_mode}-program-compiler-{seed}-v1"
        )
        prior: dict[str, Any] | None = None
        reused_after_validator_change = False
        for record in reversed(TraceStore.read(store.calls_path)):
            if (
                record.get("call_id") == call_id
                and record.get("status") == "completed"
                and all(record.get(key) == value for key, value in lineage.items())
                and isinstance(record.get("result"), Mapping)
                and isinstance(record["result"].get("content"), str)
            ):
                stored_program = str(record["result"]["content"]).strip()
                if stored_program.startswith("VALID S02 STORY PROGRAM"):
                    stored_program = stored_program[
                        len("VALID S02 STORY PROGRAM") :
                    ].lstrip()
                # A completed compiler result remains valid provenance even when
                # a later validator revision finds a deterministic defect. Feed
                # that exact result into the bounded repair path instead of
                # regenerating or rejecting it because the compiler prompt hash
                # changed.
                prior = dict(record["result"])
                reused_after_validator_change = (
                    record.get("prompt_hash") != prompt_hash
                )
                break
        if prior is None:
            prior = _resume_call(
                store,
                call_id=call_id,
                prompt_hash=prompt_hash,
                lineage=lineage,
            )
        if prior is None:
            base = {
                "call_id": call_id,
                "role": "raw-31b-story-program-compiler",
                "generation_mode": generation_mode,
                "model": compiler.model,
                "runtime": model_runtime_provenance(compiler.model),
                "prompt_hash": prompt_hash,
                **lineage,
                "parameters": {
                    "seed": 810_000 + index * 71,
                    "max_tokens": 1_200,
                    "temperature": 0.65,
                    "top_p": 0.93,
                    "min_p": 0.02,
                },
            }
            store.append_call(
                {**base, "status": "started", "started_at": utc_now()}
            )
            try:
                completion = compiler.complete_raw(
                    prompt=prompt,
                    seed=810_000 + index * 71,
                    max_tokens=1_200,
                    temperature=0.65,
                    top_p=0.93,
                    min_p=0.02,
                    xtc_probability=0.0,
                )
                prior = _completion_result(completion)
            except Exception as exc:
                store.append_call(
                    {
                        **base,
                        "status": "failed",
                        "finished_at": utc_now(),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                raise
            store.append_call(
                {
                    **base,
                    "status": "completed",
                    "finished_at": utc_now(),
                    "result": prior,
                }
            )
        program = str(prior["content"]).strip()
        if program.startswith("VALID S02 STORY PROGRAM"):
            program = program[len("VALID S02 STORY PROGRAM") :].lstrip()
        validation = validate_story_program(program)
        for repair_index in range(1, 3):
            if validation["passed"]:
                break
            repair_prompt = story_program_repair_prompt(
                compact_prefix=compact_prefix,
                program=program,
                validation=validation,
            )
            repair_call_id = f"{call_id}-repair-{repair_index}"
            repair_prompt_hash = sha256_text(repair_prompt)
            repair_result = _resume_call(
                store,
                call_id=repair_call_id,
                prompt_hash=repair_prompt_hash,
                lineage=lineage,
            )
            repair_base = {
                "call_id": repair_call_id,
                "role": "raw-31b-story-program-repair",
                "generation_mode": generation_mode,
                "model": compiler.model,
                "runtime": model_runtime_provenance(compiler.model),
                "prompt_hash": repair_prompt_hash,
                **lineage,
                "parameters": {
                    "seed": 820_000 + index * 71 + repair_index * 997,
                    "max_tokens": 1_000,
                    "temperature": 0.35,
                    "top_p": 0.9,
                    "min_p": 0.0,
                },
            }
            if repair_result is None:
                store.append_call(
                    {
                        **repair_base,
                        "status": "started",
                        "started_at": utc_now(),
                    }
                )
                try:
                    completion = compiler.complete_raw(
                        prompt=repair_prompt,
                        seed=int(repair_base["parameters"]["seed"]),
                        max_tokens=1_000,
                        temperature=0.35,
                        top_p=0.9,
                        min_p=0.0,
                        xtc_probability=0.0,
                    )
                    repair_result = _completion_result(completion)
                except Exception as exc:
                    store.append_call(
                        {
                            **repair_base,
                            "status": "failed",
                            "finished_at": utc_now(),
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
                    raise
                store.append_call(
                    {
                        **repair_base,
                        "status": "completed",
                        "finished_at": utc_now(),
                        "result": repair_result,
                    }
                )
            program = str(repair_result["content"]).strip()
            if program.startswith("VALID S02 STORY PROGRAM"):
                program = program[len("VALID S02 STORY PROGRAM") :].lstrip()
            validation = validate_story_program(program)
        if not validation["passed"]:
            raise ValueError(
                f"31B program compiler produced invalid seed {seed}: {validation}"
            )
        record = {
            "record_type": "StoryProgram",
            "status": "completed",
            "story_program_id": f"s02-{generation_mode}-{seed}-compiled",
            "seed": seed,
            "program": program,
            "original_proposal_hash": sha256_text(raw_proposal),
            "original_validation": raw_validation,
            "compiler_validation": validation,
            "compiler_call_id": call_id,
            "reused_after_validator_change": reused_after_validator_change,
            **lineage,
            "program_hash": sha256_text(program),
            "finished_at": utc_now(),
        }
        store.append_plan(record)
        compiled[seed] = program
    return compiled


S02_BEAT_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "livia_offers_specific_care",
        (
            r"\bLivia\b.{0,900}?\b(?:care|concern|help|tea|water|coat|food|rest|listen)\w*\b",
        ),
    ),
    (
        "truth_overclaims_entitlement",
        (
            r"\bLivia\b.{0,1400}?\b(?:right|correct|accurate|true|notice|read|saw|watched|knew)\w*\b.{0,900}?\b(?:must|need|demand|insist|entitl|control|stay|tell)\w*\b",
            r"\bLivia\b.{0,1000}?\b(?:afraid|exceptional|unremarkable|"
            r"parlor trick|learnable)\w*\b.{0,1100}?\b(?:access|permission|"
            r"grant|give|test)\w*\b",
        ),
    ),
    (
        "mara_error_has_cost",
        (
            r"\bMara\b.{0,1200}?\b(?:mistak|wrong|explain|clarif|conceal|"
            r"hid(?:e|den)|accus|delet|agreed|signed|compli|perform)\w*\b"
            r".{0,900}?\b(?:worse|cost|less sure|lost|risk|status|standing|"
            r"trap|consequence)\w*\b",
            r"\bMara\b.{0,1000}?\b(?:touch(?:ed)?|click(?:ed)?|accept(?:ed)?)\b"
            r".{0,1000}?\b(?:count(?:down|ing)|deadline|due|expires?|"
            r"review notes|name\b.{0,80}\bscreens?)\b",
        ),
    ),
    (
        "ambiguous_embodied_evidence",
        (
            r"\b(?:body|stomach|throat|breath|pulse|skin|flinch|heat|reaction)\w*\b.{0,900}?\b(?:or|might|could|uncertain|ambiguous|both|more than one|not know)\b",
            r"\b(?:or|might|could|uncertain|ambiguous|both|more than one|not know)\b.{0,900}?\b(?:body|stomach|throat|breath|pulse|skin|flinch|heat|reaction)\w*\b",
        ),
    ),
    (
        "attention_recovers_judgment",
        (
            r"\b(?:pray|prayer|Jesus|Christ|God|Lord|psalm|scripture|cross)\w*\b.{0,900}?\b(?:choice|choose|judge|judgment|clarity|free|decide|know|notice|attention)\w*\b",
        ),
    ),
    (
        "mara_creates_exit_condition",
        (
            r"\bMara\b.{0,500}?\b(?:refus|leave|exit|stop|end|question|"
            r"finish|rise|rose|stood|step(?:ped)?)\w*\b",
            r"\b(?:my|her)\s+no\b.{0,220}?\b(?:decision|question|leave|exit|stop|end)\w*\b",
            r"\b(?:no|refus|leave|exit|stop|end)\w*\b.{0,220}?\b(?:I|she)\s+(?:choose|decide|will|won't|refuse)",
        ),
    ),
    (
        "miriam_protects_exit",
        (
            r"\bMiriam\b.{0,1100}?\b(?:protect|back|open|door|leave|exit|"
            r"refusal|ratif|session is over)\w*\b.{0,1100}?\b(?:risk|cost|"
            r"board|job|position|reputation|public|vote|standing|social capital|"
            r"authority)\w*\b",
        ),
    ),
    (
        "jonah_walks_without_extraction",
        (
            r"\bJonah\b.{0,1200}?\b(?:walk|home)\w*\b.{0,1200}?\b(?:admit|confess|risk|cost|fail|lost|lose|status|silence|repair|sorry)\w*\b",
        ),
    ),
    (
        "kiss_stops_and_shared_practice",
        (
            r"\b(?:kiss|mouth|lips)\b.{0,900}?\b(?:stop|stopped|wait|pause|enough|ask|tell me|again|next time|choose)\w*\b",
        ),
    ),
)


def _ordered_beat_findings(text: str) -> tuple[bool, list[dict[str, Any]]]:
    cursor = 0
    findings: list[dict[str, Any]] = []
    for name, patterns in S02_BEAT_PATTERNS:
        match: re.Match[str] | None = None
        for pattern in patterns:
            candidate = re.search(
                pattern, text[cursor:], flags=re.IGNORECASE | re.DOTALL
            )
            if candidate and (match is None or candidate.start() < match.start()):
                match = candidate
        findings.append(
            {
                "beat": name,
                "found": match is not None,
                "position": cursor + match.start() if match else None,
            }
        )
        if match:
            cursor += match.end()
    return all(item["found"] for item in findings), findings


def _repeated_signature_passages(
    text: str,
    *,
    n: int = 16,
) -> list[dict[str, Any]]:
    """Find exact long phrase replays inside one generated continuation."""

    tokens = words(text)
    first_positions: dict[tuple[str, ...], int] = {}
    findings: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for index in range(max(0, len(tokens) - n + 1)):
        phrase = tuple(tokens[index : index + n])
        first = first_positions.setdefault(phrase, index)
        if first == index or index - first <= n * 2 or phrase in seen:
            continue
        seen.add(phrase)
        findings.append(
            {
                "phrase": " ".join(phrase),
                "first_token": first,
                "repeated_token": index,
            }
        )
        if len(findings) == 5:
            break
    return findings


def continuation_gates(
    candidate: Candidate,
    *,
    scene: SceneSpec,
    approved_prefix: ApprovedPrefix,
    anti_copy_index: AntiCopyIndex,
) -> dict[str, Any]:
    continuation = candidate.continuation_text
    merged = candidate.text
    continuation_words = word_count(continuation)
    merged_words = word_count(merged)
    ordered, beat_findings = _ordered_beat_findings(continuation)
    overlap = anti_copy_index.check(candidate.candidate_id, continuation)
    other_mind = re.findall(
        r"\b(?:Livia|Jonah|Miriam)\b(?:\s+\w+){0,3}\s+"
        r"(?:thought|knew|felt|wondered|realized|wanted|remembered|feared|hoped)\b",
        continuation,
        flags=re.IGNORECASE,
    )
    explicit = re.findall(
        r"\b(?:penis|cock|vagina|clitoris|orgasm|came inside|"
        r"thrust(?:ing|ed)?)\w*\b",
        continuation,
        flags=re.IGNORECASE,
    )
    physical_kiss = re.search(
        r"\b(?:kissed|(?:his|her|their) lips(?:\s+\w+){0,3}\s+"
        r"(?:met|touched)\b|mouth met (?:hers|his)|"
        r"the kiss (?:began|deepened|intensified|was|felt|landed))",
        continuation,
        re.I,
    )
    stop_after_kiss = (
        re.search(
            r"\b(?:stop|stopped|pulled back|broke the kiss|ended the kiss)\b",
            continuation[physical_kiss.end() :],
            re.I,
        )
        if physical_kiss
        else None
    )
    choice_present = bool(
        re.search(
            r"\b(?:asked|may I|can I|yes|she chose|her choice|a choice|"
            r"wanted|mutual(?:ly)?)\b",
            continuation,
            re.I,
        )
    )
    hfn_present = _local_hfn_present(continuation)
    mystery_open = bool(
        re.search(
            r"\b(?:still|not explain|unanswered|mystery|remainder|didn't know|"
            r"could not know|Fulcrum)\b",
            continuation[-4_500:],
            re.I,
        )
    )
    hook_tail = continuation[-5_000:]
    concrete_hook_object = bool(
        re.search(
            r"\b(?:recording|timestamp|message|device|camera|audio|file|"
            r"footprint|signal|sensor|keycard|badge|log|email|photograph|"
            r"screen|access record)\w*\b",
            hook_tail,
            re.I,
        )
    )
    unresolved_hook = bool(
        re.search(
            r"\b(?:unexplained|impossible|wrong|offline|unplugged|sealed|"
            r"missing|before|after|without|couldn't|could not|didn't|did not|"
            r"no one|not yet|unknown|should not|shouldn't)\b",
            hook_tail,
            re.I,
        )
    )
    repeated_passages = _repeated_signature_passages(continuation)
    gates = {
        "immutable_prefix": {
            "passed": merged.startswith(approved_prefix.text),
            "expected_hash": approved_prefix.text_hash,
            "observed_prefix_hash": sha256_text(
                merged[: len(approved_prefix.text)]
            ),
        },
        "continuation_length": {
            "passed": scene.target_words_min <= continuation_words <= scene.target_words_max,
            "word_count": continuation_words,
            "minimum": scene.target_words_min,
            "maximum": scene.target_words_max,
        },
        "merged_length": {
            "passed": 5_800 <= merged_words <= 7_200,
            "word_count": merged_words,
            "minimum": 5_800,
            "maximum": 7_200,
        },
        "complete_ending": {
            "passed": _prose_has_complete_ending(continuation),
            "terminal_text": continuation.rstrip()[-120:],
            "balanced_curly_quotes": (
                continuation.count("“") == continuation.count("”")
            ),
        },
        "s02_beats_ordered": {
            "passed": ordered,
            "beats": beat_findings,
        },
        "mara_pov": {
            "passed": len(other_mind) <= 1,
            "suspicious_other_mind_phrases": other_mind,
        },
        "heat_ceiling": {
            "passed": not explicit,
            "explicit_markers": explicit,
        },
        "doorway_rule": {
            "passed": bool(physical_kiss and stop_after_kiss and choice_present),
            "kiss": bool(physical_kiss),
            "stop_after_kiss": bool(stop_after_kiss),
            "choice": choice_present,
        },
        "local_hfn": {
            # The old hard gate required a literal mystery marker, which taught
            # every ending to append "the mystery remained."  Suspense quality
            # and concreteness now belong to comparative literary evaluation.
            "passed": hfn_present,
            "romantic_future": hfn_present,
            "larger_mystery_open": mystery_open,
        },
        "concrete_story_hook": {
            "passed": concrete_hook_object and unresolved_hook,
            "concrete_object": concrete_hook_object,
            "unresolved_or_anomalous": unresolved_hook,
        },
        "anti_copy": {
            "passed": not overlap.hard_fail and not overlap.unresolved_flags,
            "report": overlap.to_dict(),
        },
        "no_internal_signature_replay": {
            "passed": not repeated_passages,
            "ngram_words": 16,
            "repeated_passages": repeated_passages,
        },
        "profile_provenance": {
            "passed": bool(candidate.resolved_profile_hash)
            and candidate.approved_prefix_hash == approved_prefix.text_hash
            and (
                not candidate.scene_profile_id.startswith("fulcrum-s02.v4")
                or all(
                    (
                        candidate.author_profile_hash,
                        candidate.corpus_manifest_hash,
                        candidate.transformation_map_hash,
                        candidate.story_program_id,
                        candidate.anti_copy_index_hash,
                    )
                )
            ),
        },
    }
    return {
        "candidate_id": candidate.candidate_id,
        "eligible": all(bool(item["passed"]) for item in gates.values()),
        "gates": gates,
    }


def prepare_continuation_context(
    *,
    compiled_dir: str | Path,
    finalists_path: str | Path,
    reveal_key_path: str | Path,
    feedback_path: str | Path,
    author_context: ResolvedAuthorContext | None = None,
) -> tuple[
    SceneSpec,
    tuple[PersonaPacket, ...],
    dict[str, Any],
    dict[str, Any],
    HumanFeedbackBrief,
    ApprovedPrefix,
    dict[str, Any],
    str,
]:
    source_scene, personas, profile, source_packet = load_s02_compilation(compiled_dir)
    scene = literary_scene_spec(source_scene)
    feedback = load_feedback_brief(feedback_path)
    approved = load_approved_prefix(
        finalists_path=finalists_path,
        reveal_key_path=reveal_key_path,
        feedback_brief=feedback,
    )
    packet = compact_story_packet(
        scene=scene,
        personas=personas,
        profile=profile,
        source_packet=source_packet,
        feedback=feedback,
        approved_prefix=approved,
        author_context=author_context,
    )
    rendered = render_generation_packet(packet)
    return (
        scene,
        personas,
        profile,
        source_packet,
        feedback,
        approved,
        packet,
        rendered,
    )


def context_manifest(
    *,
    packet: Mapping[str, Any],
    rendered: str,
    scene: SceneSpec,
    profile: Mapping[str, Any],
    feedback: HumanFeedbackBrief,
    approved_prefix: ApprovedPrefix,
) -> dict[str, Any]:
    author = packet.get("author_conditioning", {})
    return {
        "record_type": "ContinuationContextManifest",
        "version": CONTINUATION_VERSION,
        "comparison_version": COMPARISON_VERSION,
        "scene_id": scene.scene_id,
        "packet_hash": hash_json(packet),
        "rendered_prompt_hash": sha256_text(rendered),
        "packet_words": packet_word_count(packet),
        "generation_prompt_words": word_count(rendered),
        "resolved_profile_hash": str(profile["profile_hash"]),
        "feedback_brief_hash": feedback.feedback_brief_hash,
        "feedback_source_kind": feedback.source_kind,
        "approved_prefix_id": approved_prefix.approved_prefix_id,
        "approved_prefix_hash": approved_prefix.text_hash,
        "author_conditioning": (
            {
                key: author.get(key, "")
                for key in (
                    "author_profile_id",
                    "author_profile_hash",
                    "corpus_manifest_hash",
                    "transformation_map_hash",
                    "conditioning_variant",
                    "prompt_encoding",
                    "control_density",
                    "context_hash",
                )
            }
            if isinstance(author, Mapping) and author
            else {}
        ),
        "macro_sequences": [asdict(item) for item in S02_MACRO_SEQUENCES],
        "primary_pipelines": [
            {
                "mode": INSTRUCTION_RAW_MODE,
                "hypothesis": "native stochastic instruction-model baseline",
            },
            {
                "mode": VERBALIZED_MODE,
                "hypothesis": "instruction-model long-tail planning before realization",
            },
            {
                "mode": NATIVE_BASE_PLANNED_MODE,
                "hypothesis": "genuine 31B-base causal planning and native prose continuation",
            },
        ],
        "diagnostic_ablations": [
            BASE31_PLAN_MODE,
            CHAT_PLANNED_MODE,
            CHAT_DIRECT_MODE,
            NATIVE_BASE_MODE,
            BASE_PROGRAM_MODE,
        ],
        "comparison_arms": {
            INSTRUCTION_RAW_MODE: {
                "proposal_source": "none",
                "writer": "gemma-4-31B-it-Q8_0",
                "transport": "raw-completion-with-explicit-turn-envelope",
            },
            CHAT_DIRECT_MODE: {
                "proposal_source": "none",
                "writer": "gemma-4-31B-it-Q8_0",
                "transport": "chat-completion",
            },
            CHAT_PLANNED_MODE: {
                "proposal_source": "same locked 31B-base plan set used by the raw instruction writer",
                "writer": "gemma-4-31B-it-Q8_0",
                "transport": "chat-completion",
                "comparison": "paired transport ablation",
            },
            BASE_PROGRAM_MODE: {
                "proposal_source": "gemma-4-E2B-base-Q8_0",
                "compiler": "gemma-4-31B-it-Q8_0",
                "writer": "gemma-4-31B-it-Q8_0",
            },
            BASE31_PLAN_MODE: {
                "proposal_source": "gemma-4-31B-base-Q8_0",
                "compiler": (
                    "none; full selected plan is immutable and the writer sees "
                    "a deterministic concrete-event projection"
                ),
                "writer": "gemma-4-31B-it-Q8_0",
                "planner_transport": "native raw continuation; no chat tokens",
                "writer_transport": "raw-completion-with-explicit-turn-envelope",
                "backtranslation": (
                    "requires an explicit corpus-derived author context and "
                    "nonempty transformation-map hash; the accepted S01 prose "
                    "is represented by a factual state bridge"
                ),
            },
            VERBALIZED_MODE: {
                "proposal_source": "31B-it verbalized-sampling tail distribution",
                "selection": (
                    "two reversed-order blind plan judgments followed by "
                    "quality-first causal-diversity selection"
                ),
                "compiler": (
                    "none; sampled JSON remains immutable in provenance and the "
                    "writer sees a deterministic concrete-event projection"
                ),
                "writer": "gemma-4-31B-it-Q8_0",
            },
            NATIVE_BASE_MODE: {
                "proposal_source": "none",
                "writer": "gemma-4-31B-base-Q8_0",
                "transport": "native raw continuation; no chat tokens",
            },
            NATIVE_BASE_PLANNED_MODE: {
                "proposal_source": "same locked 31B-base plan set used by the instruction writer",
                "writer": "gemma-4-31B-base-Q8_0",
                "transport": "native raw continuation; no chat tokens",
                "comparison": "paired writer-checkpoint ablation",
            },
        },
        "shared_controls": {
            "compact_packet_hash": sha256_text(rendered),
            "approved_prefix_hash": approved_prefix.text_hash,
            "macro_sequence_count": len(S02_MACRO_SEQUENCES),
            "length_controller": "measured-sequence-floor-and-local-overflow-repair",
            "generation_context": (
                "factual accepted-prefix state, character invariants, "
                "observable mechanisms, and hard limits; evaluator ontology omitted"
            ),
            "seeds": list(DEFAULT_SEEDS),
        },
    }
