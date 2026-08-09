"""Prompt-autoresearch campaign for local, source-grounded fiction generation.

The module deliberately keeps raw source text local.  Public manifests expose
only hashes and locations; prompt material is rendered only at generation time.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import html
import fcntl
import json
from pathlib import Path
import random
import re
from statistics import median
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlparse

from .anti_copy import AntiCopyIndex, AntiCopyPolicy
from .authorship import (
    proof_carrying_model_authorship,
    text_sha256 as authorship_text_sha256,
    validate_artifact_authorship,
)
from .core import atomic_write_text, canonical_json_text, hash_file, hash_json, sha256_text, write_json
from .model_client import LlamaClient
from .runtime import model_runtime_provenance
from .shared_endpoint import SharedEndpointAdmission


AUTORESEARCH_VERSION = "prompt-autoresearch.v2-cleanroom"
DEFAULT_SOURCE = Path(
    "/Users/george/.codex/attachments/"
    "d88a67cd-a639-4fba-80d6-b30acc0a4d22/pasted-text.txt"
)
DEFAULT_BASELINE = Path(
    "03_scene_lab/runs/s02-paired-composed-v7/seed-916019/prompts/pressure.txt"
)
ROUND1_SEEDS = (931_001, 931_037, 931_079)
ROUND2_SEEDS = (932_003, 932_041, 932_083, 932_129)
ROUND3_SEEDS = (933_007, 933_053, 933_101, 933_151)
SAMPLING = {
    "temperature": 0.95,
    "top_p": 0.97,
    "min_p": 0.02,
    "xtc_probability": 0.08,
}
GENERATION_POLICY = {
    "max_completion_tokens": 2000,
    "target_words_min": 800,
    "target_words_max": 1000,
    "completion_policy": "natural model stop or declared token cap; never silent truncation",
}
EXAMPLE_RE = re.compile(
    r"\*\*Example\s+(?P<number>\d+)\s*:\s*(?P<title>.*?)\*\*",
    re.IGNORECASE | re.DOTALL,
)
WORK_RE = re.compile(r"Excerpt\s+from\s+\*([^*]+)\*", re.IGNORECASE)
CONTROL_SYNTAX = (
    "<fiction-preparation>",
    "<scene_input>",
    "## Locked story state",
    "## Drafting note",
    "EDITORIAL EVENT LEDGER",
)
MANUSCRIPT_STOP_MARKERS = (
    "\n\nANALYSIS",
    "\n\nCASE MATERIAL",
    "\n\nEDITORIAL EVENT",
    "\n\nEND MANUSCRIPT",
    "\n\nEND TARGET",
    "\n\n<fiction",
)
REVIEW_AXES = (
    "romantic_pull",
    "heat_effectiveness",
    "character_fascination",
    "prose_freshness",
    "causal_coherence",
    "agency",
    "project_fit",
    "desire_to_continue",
    "unwanted_erotic_leakage",
)
RESEARCH_REVIEW_ROLES = ("trace_critic", "research_lead")
RESEARCH_REVIEW_FIELDS = (
    "claim",
    "confidence",
    "intended_affordance_transfer",
    "observed_realization",
    "unwanted_leakage",
    "competing_explanations",
    "recommended_single_axis_mutation",
    "predicted_result",
    "falsification_condition",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_markup(text: str) -> str:
    value = text.replace("\\(", "").replace("\\)", "")
    value = re.sub(r"(?:>\s*){2,}", "\n", value)
    value = re.sub(r"(?m)^\s*>\s?", "", value)
    value = value.replace("\\!", "!")
    value = re.sub(r"\*+", "", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _partition(work: str) -> str:
    folded = work.casefold()
    if "breath of snow and ashes" in folded:
        return "holdout"
    if "drums of autumn" in folded:
        return "calibration"
    return "profiling"


MODE_BY_EXAMPLE = {
    1: ("dialogue-body-language", "open-door-nongraphic"),
    2: ("trust-negotiation", "explicit"),
    3: ("playful-married-intimacy", "explicit"),
    4: ("plot-integrated-married-intimacy", "open-door-nongraphic"),
    5: ("comic-domestic-eroticism", "open-door-nongraphic"),
    6: ("coercive-counterexample", "explicit"),
    7: ("recovery-and-triage", "explicit"),
    8: ("coercive-counterexample", "explicit"),
    9: ("non-sex-sex-scene", "charged-restraint"),
    10: ("asymmetric-intimacy", "open-door-nongraphic"),
    11: ("sensory-intimacy", "open-door-nongraphic"),
    12: ("premarital-tension", "charged-restraint"),
    13: ("emotionless-sex-counterexample", "explicit"),
}


@dataclass(frozen=True, slots=True)
class SourcePassage:
    passage_id: str
    example_number: int
    title: str
    source_work: str
    partition: str
    location: str
    text_hash: str
    word_count: int
    intimacy_mode: str
    heat_band: str
    prompt_eligible: bool
    text: str

    def public_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("text")
        return value


@dataclass(frozen=True, slots=True)
class IntimacySceneGraph:
    graph_id: str
    passage_id: str
    emotional_offer: str
    emotional_counteroffer: str
    relationship_history: str
    present_stakes: str
    dialogue_act_sequence: tuple[str, ...]
    body_language_counterpoint: tuple[str, ...]
    sensory_channels: tuple[str, ...]
    narrative_distance_curve: tuple[str, ...]
    physical_logistics: tuple[str, ...]
    agency_actions: tuple[str, ...]
    relationship_delta: str
    story_state_change: str
    intimacy_mode: str
    heat_band: str

    @property
    def graph_hash(self) -> str:
        return hash_json(asdict(self))


@dataclass(frozen=True, slots=True)
class HeatAffordance:
    affordance_id: str
    claim: str
    activation_conditions: tuple[str, ...]
    prompt_semantics: tuple[str, ...]
    evaluator_semantics: tuple[str, ...]
    evidence_passage_ids: tuple[str, ...]
    counterexample_passage_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BenchmarkCell:
    cell_id: str
    label: str
    heat_band: str
    intimacy_mode: str
    word_min: int
    word_max: int
    story_program: tuple[str, ...]
    hard_constraints: tuple[str, ...]
    opening_fragment: str

    @property
    def cell_hash(self) -> str:
        return hash_json(asdict(self))


@dataclass(frozen=True, slots=True)
class PromptBlock:
    block_id: str
    kind: str
    purpose: str
    content: str
    source_partition: str = "derived"
    source_ids: tuple[str, ...] = ()
    target_facets: tuple[str, ...] = ()

    @property
    def block_hash(self) -> str:
        return sha256_text(self.content)

    def public_dict(self) -> dict[str, Any]:
        return {
            "block_id": self.block_id,
            "kind": self.kind,
            "purpose": self.purpose,
            "source_partition": self.source_partition,
            "source_ids": list(self.source_ids),
            "target_facets": list(self.target_facets),
            "block_hash": self.block_hash,
            "word_count": len(self.content.split()),
        }


@dataclass(frozen=True, slots=True)
class PromptRecipe:
    recipe_id: str
    round_number: int
    topology: str
    encoding: str
    token_target: int
    named_author: bool
    include_bridge: bool
    block_ids: tuple[str, ...]
    control_density: str = "topology-defined"
    runway_policy: str = "target-program-then-plain-manuscript-prose"
    parent_recipe_hash: str = ""
    mutated_axis: str = "initial"
    sampling: Mapping[str, float] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.encoding not in {"headings", "xml", "labeled-prose"}:
            raise ValueError(f"unsupported prompt encoding: {self.encoding}")
        if self.round_number not in {1, 2, 3}:
            raise ValueError("round_number must be 1, 2, or 3")
        if self.sampling is None:
            object.__setattr__(self, "sampling", dict(SAMPLING))

    @property
    def recipe_hash(self) -> str:
        return hash_json(asdict(self))


def _graph_for(passage: SourcePassage) -> IntimacySceneGraph:
    mode = passage.intimacy_mode
    playful = "playful" in mode or passage.example_number in {1, 3, 5}
    coercive = "counterexample" in mode
    negotiation = passage.example_number in {1, 2, 3, 4, 12}
    specific = GRAPH_SPECIFICS.get(passage.example_number, {})
    return IntimacySceneGraph(
        graph_id=f"graph.{passage.passage_id}",
        passage_id=passage.passage_id,
        emotional_offer=str(specific.get("emotional_offer",
            "One partner offers attention as a specific, embodied gift rather than a generic declaration."
        )),
        emotional_counteroffer=str(specific.get("emotional_counteroffer",
            "The other answers through a choice, joke, correction, permission, or refusal that changes the encounter."
        )),
        relationship_history=str(specific.get("relationship_history",
            "Existing history makes physical detail legible as character-specific communication."
        )),
        present_stakes=str(specific.get("present_stakes",
            "The encounter must alter trust, knowledge, or future possibility rather than merely decorate the scene."
        )),
        dialogue_act_sequence=tuple(specific.get("dialogue_act_sequence", (
            ("proposal", "teasing qualification", "negotiation", "chosen response")
            if playful
            else ("approach", "uncertainty", "clarification", "consequential response")
        ))),
        body_language_counterpoint=tuple(specific.get("body_language_counterpoint", (
            "Physical response complicates or qualifies spoken meaning.",
            "One selective contact becomes a relational fact.",
        ))),
        sensory_channels=tuple(specific.get("sensory_channels", ("touch", "sound", "smell-or-taste"))),
        narrative_distance_curve=(
            "close embodied attention",
            "brief interpretive widening",
            "return to a concrete action",
        ),
        physical_logistics=(
            "Bodies remain spatially intelligible.",
            "Each physical transition follows a visible choice.",
        ),
        agency_actions=(
            "request or invitation",
            "observable answer",
            "revocable continuation",
        ) if negotiation and not coercive else (
            "record the agency failure as counterevidence",
        ),
        relationship_delta=str(specific.get("relationship_delta",
            "The partners know something consequential about one another that they did not know before."
        )),
        story_state_change=str(specific.get("story_state_change",
            "The scene creates a decision, disclosure, alliance, cost, or future obligation."
        )),
        intimacy_mode=mode,
        heat_band=passage.heat_band,
    )


AFFORDANCES = (
    HeatAffordance(
        "heat.dialogue-is-touch",
        "Dialogue and touch form one exchange; neither is detachable decoration.",
        ("two people have enough history for subtext",),
        ("Give each spoken move a bodily answer and each contact a conversational consequence.",),
        ("Identify the offer, answer, and changed relationship fact.",),
        ("gabaldon.example-01", "gabaldon.example-02", "gabaldon.example-03"),
    ),
    HeatAffordance(
        "heat.selective-sensation",
        "A few precise sensory channels create more heat than an inventory of body parts.",
        ("embodied attraction is active",),
        ("Choose three sensory channels and make each change attention or action.",),
        ("Quote sensory details that perform causal work.",),
        ("gabaldon.example-01", "gabaldon.example-11"),
    ),
    HeatAffordance(
        "heat.character-before-mechanics",
        "Physical action remains inseparable from these characters' history, humor, defenses, and errors.",
        ("intimacy occurs",),
        ("Let characteristic decisions control physical pacing.",),
        ("Would the scene cease to work if generic lovers replaced the characters?",),
        ("gabaldon.example-01", "gabaldon.example-03", "gabaldon.example-04"),
        ("gabaldon.example-13",),
    ),
    HeatAffordance(
        "heat.restraint-increases-charge",
        "A chosen delay or interruption can intensify desire when it costs both people something.",
        ("desire is mutual", "a boundary or impediment is live"),
        ("Make stopping an active mutual choice whose cost remains perceptible.",),
        ("Show what is wanted, what stops, and what future possibility increases.",),
        ("gabaldon.example-02", "gabaldon.example-12"),
    ),
    HeatAffordance(
        "heat.plot-bearing-intimacy",
        "The intimate exchange carries plot information without turning into exposition.",
        ("an external plot is active",),
        ("Let physical or conversational intimacy disclose one plot-relevant fact.",),
        ("Name the story state that changes because the encounter occurred.",),
        ("gabaldon.example-04", "gabaldon.example-07"),
    ),
    HeatAffordance(
        "heat.agency-is-erotic",
        "Attention to a partner's actual response makes freedom and desire mutually reinforcing.",
        ("physical escalation is possible",),
        ("Render invitation, response, adjustment, and continued freedom as observable actions.",),
        ("Verify that escalation follows choices rather than narrative entitlement.",),
        ("gabaldon.example-01", "gabaldon.example-02", "gabaldon.example-04"),
        ("gabaldon.example-06", "gabaldon.example-08"),
    ),
)


GRAPH_SPECIFICS: Mapping[int, Mapping[str, Any]] = {
    1: {
        "emotional_offer": "A husband turns months of separation into a comic, detailed promise of attention.",
        "emotional_counteroffer": "His wife interrogates and teases the plan while progressively consenting to its enactment.",
        "relationship_history": "Long-married partners share scripture, private jokes, and reliable knowledge of one another's responses.",
        "present_stakes": "Reunion must feel like recognition rather than generic access to a body.",
        "dialogue_act_sequence": ("proposal", "skeptical invitation", "comic specification", "physical demonstration", "reciprocal anticipation"),
        "body_language_counterpoint": ("Domestic washing makes the erotic plan tactile.", "A kiss and resting hand verify what dialogue predicts."),
        "sensory_channels": ("taste of ale and soap", "beard and skin texture", "pressure at thigh and waist"),
        "relationship_delta": "Separation is converted into shared anticipation and renewed private fluency.",
        "story_state_change": "The couple chooses private reunion before the voyage continues.",
    },
    2: {
        "emotional_offer": "An inexperienced partner offers pleasure plainly after a transgressive first encounter.",
        "emotional_counteroffer": "The viewpoint partner answers desire with specific questions, visible fear, and negotiated control.",
        "relationship_history": "Religious guilt, uneven experience, and a newly crossed boundary make trust fragile.",
        "present_stakes": "Mutual desire must become safe enough to act on without pretending uncertainty is absent.",
        "dialogue_act_sequence": ("post-act inquiry", "comic confession", "offer", "technical negotiation", "fear disclosure", "reassurance"),
        "body_language_counterpoint": ("Blushing contradicts matter-of-fact speech.", "A trembling body makes verbal reassurance insufficient until touch gentles it."),
        "sensory_channels": ("warm fingers", "softening shoulders", "oil and pressure anticipated"),
        "relationship_delta": "Uncertainty becomes explicit mutual trust and a revocable next step.",
        "story_state_change": "A sexual and moral threshold becomes a chosen relationship fact.",
    },
    3: {
        "emotional_offer": "A wife delays consummation to savor attention and playful control.",
        "emotional_counteroffer": "Her husband submits, jokes, prays, and finally reverses the game with her delighted consent.",
        "relationship_history": "A long marriage supports irreverence, role reversal, and exact knowledge of desire.",
        "present_stakes": "The scene must renew play between established lovers rather than merely depict mechanics.",
        "dialogue_act_sequence": ("delay", "protest", "instruction", "religious joke", "comic interruption", "role reversal"),
        "body_language_counterpoint": ("Restless hips belie verbal patience.", "Laughter interrupts escalating sensation without dissipating it."),
        "sensory_channels": ("tongue and coarse hair", "breathless sound", "water-light and moisture"),
        "relationship_delta": "Familiarity becomes fresh play and reciprocal surrender.",
        "story_state_change": "Private delight delays the couple's return to public obligations.",
    },
    4: {
        "emotional_offer": "A spouse offers desire as shelter from danger and grief.",
        "emotional_counteroffer": "The other redirects a playful opening into shared mourning, then accepts closeness.",
        "relationship_history": "Weapons, political work, marriage, and recurring danger coexist in the bedroom.",
        "present_stakes": "Intimacy must carry a murder suspicion and fear of widowhood without becoming an information dump.",
        "dialogue_act_sequence": ("comic provocation", "sexual forfeit", "mood correction", "need stated", "physical union", "post-act disclosure"),
        "body_language_counterpoint": ("Comic bed logistics ground attraction.", "A hand finding another in darkness opens the plot disclosure."),
        "sensory_channels": ("wax and honey", "horse sweat", "warm bone in darkness"),
        "relationship_delta": "Desire becomes mutual refuge and permission to voice mortal fear.",
        "story_state_change": "The couple identifies a possible crime and a future family obligation.",
    },
    5: {
        "emotional_offer": "A husband interrupts work with opportunistic desire and physical comedy.",
        "emotional_counteroffer": "His wife complains, assists, and converts inconvenience into reciprocal play.",
        "relationship_history": "Domestic labor and established attraction make haste comic rather than anonymous.",
        "present_stakes": "The encounter must feel like this marriage stealing pleasure from work.",
        "dialogue_act_sequence": ("surprise approach", "practical objection", "improvised consent", "comic mishap", "shared release"),
        "body_language_counterpoint": ("Hay and clothing obstruct rather than disappear.", "Laughter and adjustment become part of arousal."),
        "sensory_channels": ("hay rustle", "cold air", "weight and breath"),
        "relationship_delta": "Routine labor briefly becomes conspiratorial delight.",
        "story_state_change": "The couple returns to obligations carrying a private comic victory.",
    },
    6: {
        "emotional_offer": "No valid offer occurs; access is taken under coercive conditions.",
        "emotional_counteroffer": "The viewpoint character dissociates and searches for survival rather than reciprocating.",
        "relationship_history": "Power and captivity replace mutual relational history.",
        "present_stakes": "This passage functions as counterevidence for agency-preserving intimacy.",
        "dialogue_act_sequence": ("threat", "coercive demand", "survival calculation", "dissociation"),
        "body_language_counterpoint": ("Physical compliance must not be misread as desire.",),
        "sensory_channels": ("pain", "room noise", "dissociative distance"),
        "relationship_delta": "Violation creates injury, not intimacy.",
        "story_state_change": "The assault changes later danger and recovery stakes.",
    },
    7: {
        "emotional_offer": "A spouse attempts careful repair after violence has made gentleness ambiguous.",
        "emotional_counteroffer": "The injured partner's actual responses revise his planned approach.",
        "relationship_history": "Deep mutual knowledge allows attention to outrank a generic rule about gentleness.",
        "present_stakes": "Physical reunion must restore safety without erasing trauma or individual difference.",
        "dialogue_act_sequence": ("careful approach", "response read", "strategy revised", "catharsis", "safety named"),
        "body_language_counterpoint": ("Planned gentleness yields to the partner's specific need.", "One vivid physical cue anchors an emotional scene."),
        "sensory_channels": ("blood and wine", "jagged metaphor", "one sharp bodily anchor"),
        "relationship_delta": "Attentive physicality restores a damaged sense of safety.",
        "story_state_change": "Trauma becomes shared recovery work rather than private contamination.",
    },
    8: {
        "emotional_offer": "A captor substitutes payment and casual speech for consent.",
        "emotional_counteroffer": "The victim survives through constrained responses rather than relational participation.",
        "relationship_history": "There is no mutual bond capable of making the act intimate.",
        "present_stakes": "The passage is a coercion counterexample and must never seed positive craft semantics.",
        "dialogue_act_sequence": ("coercion", "survival response", "transactional dismissal"),
        "body_language_counterpoint": ("Physical explicitness documents violation rather than heat." ,),
        "sensory_channels": ("pain", "clothing", "detached observation"),
        "relationship_delta": "Power becomes injury and future conflict.",
        "story_state_change": "The violation drives later recovery and confrontation.",
    },
    9: {
        "emotional_offer": "A father offers embodied proof of solidarity to an injured adult daughter.",
        "emotional_counteroffer": "She accepts the unconventional demonstration because speech alone cannot reach the wound.",
        "relationship_history": "Familial trust permits edgy physical specificity without erotic intent.",
        "present_stakes": "A non-sex scene borrows sexual charge to communicate protection and recognition.",
        "dialogue_act_sequence": ("evasion", "challenge", "physical demonstration", "recognition", "quiet acceptance"),
        "body_language_counterpoint": ("Edgy contact carries a non-erotic argument.",),
        "sensory_channels": ("specific touch", "breath", "stillness"),
        "relationship_delta": "Isolation becomes credible familial solidarity.",
        "story_state_change": "The daughter gains enough safety to continue recovery.",
    },
    10: {
        "emotional_offer": "A viewpoint character privately eroticizes a woman's jewelry and body without reciprocal encounter.",
        "emotional_counteroffer": "None; the asymmetry is the defining limitation.",
        "relationship_history": "Observation substitutes for mutual relationship knowledge.",
        "present_stakes": "The passage tests how sensory fixation differs from intimacy.",
        "dialogue_act_sequence": ("visual fixation", "private fantasy", "continued asymmetry"),
        "body_language_counterpoint": ("The observed person does not answer the viewpoint character's desire." ,),
        "sensory_channels": ("gold glint", "skin contrast", "visual repetition"),
        "relationship_delta": "No mutual relationship change occurs.",
        "story_state_change": "Desire reveals the observer rather than forming a bond.",
    },
    11: {
        "emotional_offer": "A spouse offers sensory surrender while retaining a promise of physical safety.",
        "emotional_counteroffer": "The viewpoint partner releases control because the other's hands remain trustworthy.",
        "relationship_history": "Established bodily trust allows fear and pleasure to share the same action.",
        "present_stakes": "A concentrated sensory sequence must distinguish surrender from loss of agency.",
        "dialogue_act_sequence": ("sensory approach", "fear registered", "reassurance", "chosen release"),
        "body_language_counterpoint": ("Supporting hands make an apparently risky posture safe.",),
        "sensory_channels": ("warmth in cool air", "voice at the ear", "weight against supporting hands"),
        "relationship_delta": "Trust becomes a bodily action rather than an asserted belief.",
        "story_state_change": "The partner chooses deeper surrender while remaining held.",
    },
    12: {
        "emotional_offer": "An unmarried suitor turns shelter and wet clothing into a teasing erotic possibility.",
        "emotional_counteroffer": "The woman answers through banter that acknowledges arousal without resolving it.",
        "relationship_history": "Courtship and impending commitment make double meanings consequential.",
        "present_stakes": "Premarital desire must intensify future possibility without consummation.",
        "dialogue_act_sequence": ("practical invitation", "double meaning", "mock correction", "mutual recognition", "interruption"),
        "body_language_counterpoint": ("Wet clothes and proximity carry what neither states directly.",),
        "sensory_channels": ("rain", "wet fabric", "visible bodily response"),
        "relationship_delta": "Both recognize desire and defer its fulfillment.",
        "story_state_change": "Courtship advances through charged knowledge rather than sex.",
    },
    13: {
        "emotional_offer": "Sex is conducted as transaction without emotional recognition.",
        "emotional_counteroffer": "The viewpoint character remains detached and counts material consequences.",
        "relationship_history": "The absence of mutual history is deliberately exposed.",
        "present_stakes": "The passage is counterevidence showing that explicit mechanics alone do not create intimacy.",
        "dialogue_act_sequence": ("transaction", "mechanical action", "payment", "emotional vacancy"),
        "body_language_counterpoint": ("Physical access produces no reciprocal attention." ,),
        "sensory_channels": ("muffled sound", "pressure", "coins"),
        "relationship_delta": "No bond forms; distance is reinforced.",
        "story_state_change": "The transaction reveals character and social danger rather than romance.",
    },
}


def extract_gabaldon_examples(source_path: str | Path) -> tuple[SourcePassage, ...]:
    path = Path(source_path)
    text = path.read_text(encoding="utf-8")
    matches = list(EXAMPLE_RE.finditer(text))
    passages: list[SourcePassage] = []
    for index, match in enumerate(matches):
        number = int(match.group("number"))
        if not 1 <= number <= 13:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        chunk = text[match.end() : end]
        work_matches = list(WORK_RE.finditer(chunk))
        # Numbered examples can be followed by unnumbered sidebars before the
        # next numbered heading.  The first attribution belongs to the example;
        # later attributions do not.
        work = work_matches[0].group(1).strip() if work_matches else "Unknown"
        quote_end = work_matches[0].start() if work_matches else len(chunk)
        quote_start = chunk.find(">")
        raw = chunk[quote_start:quote_end] if quote_start >= 0 else chunk[:quote_end]
        cleaned = _clean_markup(raw)
        # Do not let subsequent craft sidebars swamp the quoted scene.
        cleaned = re.split(
            r"\n(?:Commentary:|RULES OF|MALE CUNTS|IMPRESSIVELY)",
            cleaned,
            maxsplit=1,
        )[0].strip()
        mode, heat = MODE_BY_EXAMPLE[number]
        partition = _partition(work)
        line = text.count("\n", 0, match.start()) + 1
        passages.append(
            SourcePassage(
                passage_id=f"gabaldon.example-{number:02d}",
                example_number=number,
                title=_clean_markup(match.group("title")).strip(": "),
                source_work=work,
                partition=partition,
                location=f"line-{line}",
                text_hash=sha256_text(cleaned),
                word_count=len(cleaned.split()),
                intimacy_mode=mode,
                heat_band=heat,
                # Example 10 is explicitly attributed to another author's
                # novel and is useful only as counterevidence.
                prompt_eligible=partition == "profiling" and number not in {6, 8, 10, 13},
                text=cleaned,
            )
        )
    if {item.example_number for item in passages} != set(range(1, 14)):
        raise ValueError("failed to recover all thirteen numbered craft examples")
    return tuple(passages)


def extract_prompt_eligible_craft(source_path: str | Path) -> str:
    """Return general/profiling craft material with calibration/holdout removed."""

    text = Path(source_path).read_text(encoding="utf-8")
    matches = list(EXAMPLE_RE.finditer(text))
    if not matches:
        raise ValueError("craft source contains no numbered examples")
    introduction = text[: matches[0].start()]
    chapter_start = introduction.find("## 1")
    if chapter_start >= 0:
        introduction = introduction[chapter_start:]
    retained = [introduction]
    for index, match in enumerate(matches):
        number = int(match.group("number"))
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        chunk = text[match.start() : end]
        work_matches = list(WORK_RE.finditer(chunk))
        work = work_matches[0].group(1).strip() if work_matches else "Unknown"
        if _partition(work) == "profiling" and number != 10:
            retained.append(chunk)
    value = _clean_markup("\n\n".join(retained))
    # The anonymous long-context arm tests prose/craft exposure rather than a
    # model's label-conditioned prior.
    value = re.sub(r"\bDiana Gabaldon\b", "the novelist", value, flags=re.I)
    for work in (
        "Outlander",
        "Voyager",
        "The Scottish Prisoner",
        "The Fiery Cross",
        "Written in My Own Heart’s Blood",
        "Written in My Own Heart's Blood",
    ):
        value = re.sub(re.escape(work), "the source novel", value, flags=re.I)
    return value


def default_benchmarks() -> tuple[BenchmarkCell, ...]:
    return (
        BenchmarkCell(
            "charged-restraint",
            "Charged restraint and chosen stopping",
            "charged-restraint",
            "non-sex-sex-scene",
            800,
            1000,
            (
                "Adult Mara and Jonah walk from the Fulcrum lab after a coercive late session.",
                "He offers his hand without interpreting her; she chooses contact.",
                "A kiss becomes mutually desired and stops while both still want it.",
                "Stopping increases trust and future possibility rather than punishing desire.",
            ),
            ("close third Mara", "no consummation", "no graphic anatomy", "ambiguous supernatural status"),
            "Jonah stopped beneath the unlit arch and waited for Mara to decide what his silence meant.",
        ),
        BenchmarkCell(
            "married-open-door",
            "Married intimacy, open-door nongraphic",
            "open-door-nongraphic",
            "married-intimacy",
            800,
            1000,
            (
                "Esther and Simon are married adults reunited after a dangerous separation.",
                "A failed rescue decision and an unrevealed witness have made tenderness difficult.",
                "They negotiate closeness through humor, touch, and a costly disclosure.",
                "The encounter consummates off the page while changing their next joint decision.",
            ),
            ("fully consensual", "married", "no anatomical inventory", "relationship-specific humor"),
            "Simon set the recovered drive on the bedroom table and waited for Esther to ask why its seal was broken.",
        ),
        BenchmarkCell(
            "married-explicit",
            "Married intimacy, explicit and tasteful",
            "explicit",
            "married-intimacy",
            800,
            1000,
            (
                "Esther and Simon are married adults reunited after a dangerous separation.",
                "A failed rescue decision and an unrevealed witness have made tenderness difficult.",
                "They negotiate closeness through humor, touch, and a costly disclosure.",
                "Physical union remains lucid, reciprocal, character-specific, and changes their next joint decision.",
            ),
            ("fully consensual", "married", "tasteful anatomical specificity", "relationship-specific humor"),
            "Simon set the recovered drive on the bedroom table and waited for Esther to ask why its seal was broken.",
        ),
        BenchmarkCell(
            "institutional-pressure-control",
            "Institutional pressure without erotic leakage",
            "none",
            "nonsexual-pressure",
            800,
            1000,
            (
                "Adult Mara is depleted after a late Fulcrum alignment session.",
                "Livia offers accurate care that makes a professional request harder to refuse.",
                "Mara tries one concrete coping move that changes Livia's next response.",
                "Jonah remains present and implicated but is not a moral oracle or romantic reward.",
            ),
            ("close third Mara", "no erotic escalation", "no kiss", "care remains genuinely caring and controlling"),
            "The tea was exactly the temperature Mara would have chosen for herself, which made refusing it feel theatrical.",
        ),
    )


def _passage_payload(passage: SourcePassage, *, named: bool) -> str:
    attribution = (
        f"SOURCE: Diana Gabaldon, {passage.source_work}\n" if named else "SOURCE: anonymous romance passage\n"
    )
    return attribution + passage.text


def _graph_payload(graph: IntimacySceneGraph) -> str:
    return canonical_json_text(asdict(graph)).strip()


def _generic_reconstruction(graph: IntimacySceneGraph) -> str:
    acts = ", then ".join(graph.dialogue_act_sequence)
    senses = ", ".join(graph.sensory_channels)
    return (
        "GENERIC RECONSTRUCTION OF THE CONTENT GRAPH: The scene begins with "
        f"this emotional offer: {graph.emotional_offer} The other character "
        f"responds: {graph.emotional_counteroffer} Their exchange proceeds "
        f"through {acts}. The prose mentions {senses}, keeps the bodies "
        "spatially understandable, and arrives at the intended relationship "
        f"change: {graph.relationship_delta} The plot then changes because "
        f"{graph.story_state_change} This reconstruction is deliberately "
        "competent but generic; compare it with the finished passage to infer "
        "what the author's scene-specific decisions add."
    )


def _affordance_payload(items: Sequence[HeatAffordance]) -> str:
    return "\n".join(
        f"- {item.claim} " + " ".join(item.prompt_semantics)
        for item in items
    )


def _baseline_case(project_root: Path) -> str:
    path = project_root / DEFAULT_BASELINE
    text = path.read_text(encoding="utf-8")
    marker = "CASE 2: EDITORIAL EVENT LEDGER"
    if marker not in text:
        raise ValueError("baseline prompt no longer contains the expected case boundary")
    value = text.split(marker, 1)[0]
    return value.replace("<fiction-preparation>\n", "").strip()


def _project_prose_documents(project_root: Path) -> dict[str, str]:
    """Return the small, approved project-prose set used for copy checks."""

    finalist_dir = (
        project_root
        / "03_scene_lab"
        / "runs"
        / "s01-comparison-v1"
        / "evaluation"
        / "finalists"
    )
    return {
        f"project.s01-finalist.{path.stem}": path.read_text(encoding="utf-8")
        for path in sorted(finalist_dir.glob("*.md"))
    }


def _bridge_for(cell: BenchmarkCell, bridge_dir: Path) -> str:
    if cell.heat_band == "explicit":
        name = "married-explicit.md"
    elif cell.intimacy_mode == "married-intimacy":
        name = "married-intimacy.md"
    else:
        name = "charged-restraint.md"
    path = bridge_dir / name
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def build_recipe_blocks(
    *,
    recipe: PromptRecipe,
    cell: BenchmarkCell,
    passages: Sequence[SourcePassage],
    graphs: Mapping[str, IntimacySceneGraph],
    project_root: Path,
    bridge_dir: Path,
    craft_text: str = "",
) -> tuple[PromptBlock, ...]:
    eligible = [item for item in passages if item.prompt_eligible]
    if cell.heat_band == "explicit":
        matched = [item for item in eligible if item.heat_band == "explicit"]
    elif cell.heat_band == "charged-restraint":
        matched = [item for item in eligible if item.heat_band == "charged-restraint"]
    else:
        matched = [item for item in eligible if item.heat_band != "explicit"]
    ordered = sorted(matched or eligible, key=lambda item: (item.example_number, item.passage_id))
    if recipe.topology in {"curated-long", "curated-long-named"}:
        selected = ordered[:12]
    elif recipe.topology in {"paired", "paired-named", "contrastive"}:
        selected = ordered[:4]
    elif recipe.topology == "raw-spice":
        selected = ordered[:3]
    else:
        selected = ordered[:2]
    if recipe.round_number == 3:
        requested_pairs = {
            6000: 1,
            12000: 2,
            24000: 4,
            48000: 8,
            64000: 12,
        }.get(recipe.token_target, 4)
        selected = ordered[:requested_pairs]
    shared_profile = (
        "PROJECT CREATIVE PROFILE (juicy-chastity.v1): Every intimate character "
        "is an adult. The central romantic geometry is monogamous and oriented "
        "toward freely chosen marriage. Desire is integrated rather than "
        "suppressed; restraint should increase perception, delight, trust, and "
        "future possibility. Consent is affirmative, contextual, revocable, and "
        "agency-preserving. Married open-door intimacy may be sensually intense. "
        "Faith, dignity, grace, and responsibility act through choices and "
        "consequences rather than detachable exposition. Observation remains "
        "separable from interpretation, and apparently supernatural effects stay "
        "ontologically ambiguous. Attraction must change knowledge, trust, choice, "
        "or story state; it is never decorative body inventory."
    )
    blocks: list[PromptBlock] = [
        PromptBlock(
            "shared.juicy-chastity.v1",
            "creative-profile",
            "RGO-derived project invariants shared by every experimental arm",
            shared_profile,
            "project-profile",
            target_facets=(cell.heat_band, cell.intimacy_mode),
        )
    ]
    if recipe.topology == "control":
        blocks.append(PromptBlock("control.canon-only", "craft", "clean-room control with no manuscript exemplar", "Realize the target program causally in fresh manuscript prose. Preserve point of view, agency, spatial clarity, and the declared ending. Let attraction or pressure change a choice rather than merely decorate the scene.", "structured-project-canon"))
    elif recipe.topology == "craft-sheet":
        blocks.append(PromptBlock("craft.affordances", "craft", "derived intimacy craft", _affordance_payload(AFFORDANCES)))
    elif recipe.topology == "raw-spice":
        for passage in selected:
            blocks.append(PromptBlock(f"raw.{passage.passage_id}", "source-prose", "mode-matched finished prose", _passage_payload(passage, named=recipe.named_author), passage.partition, (passage.passage_id,), (passage.heat_band, passage.intimacy_mode)))
    else:
        for passage in selected:
            graph = graphs[passage.passage_id]
            blocks.append(PromptBlock(f"graph.{passage.passage_id}", "scene-graph", "content-neutral back-translation", _graph_payload(graph), "derived", (passage.passage_id,), (passage.heat_band, passage.intimacy_mode)))
            if recipe.topology == "contrastive":
                generic = _generic_reconstruction(graph)
                blocks.append(PromptBlock(f"generic.{passage.passage_id}", "generic-reconstruction", "contrastive control", generic, "derived", (passage.passage_id,)))
            blocks.append(PromptBlock(f"prose.{passage.passage_id}", "source-prose", "actual finished prose corresponding to the prior graph", _passage_payload(passage, named=recipe.named_author), passage.partition, (passage.passage_id,), (passage.heat_band, passage.intimacy_mode)))
            if recipe.topology == "contrastive":
                blocks.append(PromptBlock(f"delta.{passage.passage_id}", "author-delta", "difference between generic and actual", "DELTA: Replace generic declaration with character-specific offers, bodily counteranswers, selective sensation, humor or resistance, and a consequential relationship change.", "derived", (passage.passage_id,)))
        if recipe.topology in {"curated-long", "curated-long-named"}:
            blocks.append(PromptBlock("craft.affordances", "craft", "compact author-delta summary", _affordance_payload(AFFORDANCES)))
            if craft_text:
                # Approximate tokens from words conservatively, then allow the
                # server tokenizer to record the exact achieved dose.
                word_budget = max(0, int(recipe.token_target * 0.72))
                used_words = sum(len(block.content.split()) for block in blocks)
                remaining = max(0, word_budget - used_words)
                excerpt = " ".join(craft_text.split()[:remaining])
                if excerpt:
                    blocks.insert(
                        0,
                        PromptBlock(
                            "craft.long-context",
                            "craft-apprenticeship",
                            "curated general and profiling craft context",
                            excerpt,
                            "profiling-derived",
                            tuple(item.passage_id for item in eligible),
                        ),
                    )
    if recipe.include_bridge:
        raise ValueError(
            "clean-room autoresearch forbids unverified Codex/frontier project bridges"
        )
    if recipe.round_number == 3 and craft_text and recipe.topology not in {"curated-long", "curated-long-named"}:
        word_budget = max(0, int(recipe.token_target * 0.72))
        used_words = sum(len(block.content.split()) for block in blocks)
        remaining = max(0, word_budget - used_words)
        excerpt = " ".join(craft_text.split()[:remaining])
        if excerpt:
            blocks.insert(
                0,
                PromptBlock(
                    f"density.craft.{recipe.token_target}",
                    "craft-apprenticeship",
                    "additive context-dose material",
                    excerpt,
                    "profiling-derived",
                    tuple(item.passage_id for item in eligible),
                ),
            )
    target = {
        "cell_id": cell.cell_id,
        "word_band": [cell.word_min, cell.word_max],
        "heat_band": cell.heat_band,
        "intimacy_mode": cell.intimacy_mode,
        "story_program": list(cell.story_program),
        "hard_constraints": list(cell.hard_constraints),
        "instruction": (
            "Write one complete scene of 850 to 950 words. Realize every story "
            "beat causally, then end in finished manuscript prose immediately "
            "after the final beat. Do not add an END label, analysis, synopsis, "
            "or commentary. Do not discuss the examples or repeat their wording."
        ),
    }
    blocks.append(PromptBlock(f"target.{cell.cell_id}", "target-program", "variable target contract", canonical_json_text(target).strip(), "target", target_facets=(cell.heat_band, cell.intimacy_mode)))
    blocks.append(PromptBlock(f"runway.{cell.cell_id}", "manuscript-runway", "plain-prose completion boundary", cell.opening_fragment, "target", target_facets=(cell.heat_band, cell.intimacy_mode)))
    return tuple(blocks)


def render_prompt(blocks: Sequence[PromptBlock], encoding: str) -> str:
    if not blocks or blocks[-1].kind != "manuscript-runway":
        raise ValueError("prompt must end on a manuscript-runway block")
    preparation, runway = blocks[:-1], blocks[-1].content.strip()
    if encoding == "headings":
        chunks = ["EDITORIAL APPRENTICESHIP ARCHIVE"]
        for index, block in enumerate(preparation, 1):
            chunks.extend((f"\nCASE MATERIAL {index}: {block.kind.upper()}", block.content.strip()))
        chunks.extend(("\nMANUSCRIPT", runway))
        return "\n\n".join(chunks).rstrip()
    if encoding == "xml":
        chunks = ['<fiction_program version="1">']
        for block in preparation:
            chunks.append(
                f'<block id="{html.escape(block.block_id)}" kind="{html.escape(block.kind)}">'
                + html.escape(block.content.strip())
                + "</block>"
            )
        chunks.extend(("</fiction_program>", "MANUSCRIPT", runway))
        return "\n\n".join(chunks).rstrip()
    if encoding == "labeled-prose":
        chunks = ["Study the following editorial cases as preparation for continuing a manuscript."]
        for block in preparation:
            chunks.append(f"{block.kind}:\n{block.content.strip()}")
        chunks.extend(("Continue the manuscript in finished prose:", runway))
        return "\n\n".join(chunks).rstrip()
    raise ValueError(f"unsupported encoding: {encoding}")


def round1_recipes() -> tuple[PromptRecipe, ...]:
    specs = (
        ("r1-control", "control", False, False, 6000, "rgo-canon-only"),
        ("r1-craft-sheet", "craft-sheet", False, False, 8000, "six-affordance"),
        ("r1-raw-spice", "raw-spice", False, False, 12000, "mode-matched-raw"),
        ("r1-paired", "paired", False, False, 16000, "graph-prose-pairs"),
        ("r1-paired-named", "paired-named", True, False, 16000, "named-graph-prose-pairs"),
        ("r1-contrastive", "contrastive", False, False, 24000, "contrastive-delta"),
        ("r1-curated-long", "curated-long", False, False, 24000, "curated-long"),
        ("r1-curated-long-named", "curated-long-named", True, False, 24000, "named-curated-long"),
    )
    return tuple(
        PromptRecipe(
            recipe_id,
            1,
            topology,
            "headings",
            tokens,
            named,
            bridge,
            (),
            control_density=density,
        )
        for recipe_id, topology, named, bridge, tokens, density in specs
    )


def compile_corpus(source: str | Path, output_dir: str | Path) -> dict[str, Any]:
    source_path = Path(source).resolve()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    passages = extract_gabaldon_examples(source_path)
    graphs = tuple(_graph_for(item) for item in passages)
    craft_text = extract_prompt_eligible_craft(source_path)
    payload = {
        "record_type": "AutoresearchCorpus",
        "version": AUTORESEARCH_VERSION,
        "source_path": str(source_path),
        "source_hash": hash_file(source_path),
        "partitions": {name: [item.passage_id for item in passages if item.partition == name] for name in ("profiling", "calibration", "holdout")},
        "passages": [asdict(item) for item in passages],
        "graphs": [asdict(item) | {"graph_hash": item.graph_hash} for item in graphs],
        "affordances": [asdict(item) for item in AFFORDANCES],
        "craft_apprenticeship_text": craft_text,
        "craft_apprenticeship_hash": sha256_text(craft_text),
        "holdout_policy": "never-prompt-retrieve-bridge-or-tune",
        "compiled_at": _now(),
    }
    payload["corpus_hash"] = hash_json({key: value for key, value in payload.items() if key != "compiled_at"})
    write_json(output / "corpus.private.v1.json", payload)
    public = dict(payload)
    public["passages"] = [item.public_dict() for item in passages]
    public.pop("source_path", None)
    public.pop("craft_apprenticeship_text", None)
    write_json(output / "corpus_manifest.v1.json", public)
    return public


def compile_benchmarks(output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    cells = default_benchmarks()
    payload = {
        "record_type": "AutoresearchBenchmarkSet",
        "version": AUTORESEARCH_VERSION,
        "cells": [asdict(item) | {"cell_hash": item.cell_hash} for item in cells],
    }
    payload["benchmark_hash"] = hash_json(payload)
    write_json(output / "benchmarks.v1.json", payload)
    return payload


def campaign_init(
    *,
    campaign_dir: str | Path,
    corpus_path: str | Path,
    benchmarks_path: str | Path,
    bridge_dir: str | Path,
    project_root: str | Path,
) -> dict[str, Any]:
    root = Path(campaign_dir)
    root.mkdir(parents=True, exist_ok=True)
    recipes = round1_recipes()
    project_prose = _project_prose_documents(Path(project_root).resolve())
    payload = {
        "record_type": "AutoresearchCampaign",
        "campaign_id": root.name,
        "version": AUTORESEARCH_VERSION,
        "corpus_path": str(Path(corpus_path).resolve()),
        "corpus_hash": hash_file(Path(corpus_path)),
        "benchmarks_path": str(Path(benchmarks_path).resolve()),
        "benchmark_hash": hash_file(Path(benchmarks_path)),
        "bridge_dir": str(Path(bridge_dir).resolve()),
        # Historical project bridges remain in the anti-copy index but never
        # enter a clean-room generation prompt.
        "bridge_hashes": {},
        "clean_room_policy": {
            "frontier_role": "critic_only",
            "codex_frontier_prose_in_prompts": False,
            "project_bridge_prose_in_prompts": False,
            "literary_source_apprenticeship": True,
        },
        "project_root": str(Path(project_root).resolve()),
        "project_prose_hashes": {
            source_id: sha256_text(text)
            for source_id, text in project_prose.items()
        },
        "recipes": [asdict(item) | {"recipe_hash": item.recipe_hash} for item in recipes],
        "round_seeds": {"1": list(ROUND1_SEEDS), "2": list(ROUND2_SEEDS), "3": list(ROUND3_SEEDS)},
        "sampling": SAMPLING,
        "generation_policy": GENERATION_POLICY,
        "harness_hashes": {
            name: hash_file(Path(__file__).resolve().parent / name)
            for name in (
                "autoresearch.py",
                "anti_copy.py",
                "model_client.py",
                "shared_endpoint.py",
            )
        },
        "created_at": _now(),
    }
    payload["campaign_hash"] = hash_json({key: value for key, value in payload.items() if key != "created_at"})
    path = root / "campaign_manifest.v1.json"
    if path.exists():
        prior = json.loads(path.read_text(encoding="utf-8"))
        for key in (
            "corpus_hash",
            "benchmark_hash",
            "bridge_hashes",
            "clean_room_policy",
            "project_prose_hashes",
            "sampling",
            "generation_policy",
            "harness_hashes",
        ):
            if prior.get(key) != payload.get(key):
                raise ValueError(f"refusing to resume campaign: {key} changed")
        payload = prior
    else:
        write_json(path, payload)
    preregistration = {
        "record_type": "AutoresearchPreregistration",
        "campaign_hash": payload["campaign_hash"],
        "registered_at": payload["created_at"],
        "rounds": {
            "1": {
                "claim": "Adjacent graph-to-spicy-prose pairs, especially with a project-voice bridge, will improve heat and prose without reducing causality.",
                "falsifier": "The paired arms fail to beat the causal baseline or create copying, voice bleed, or nonsexual-control leakage.",
            },
            "2": {
                "claim": "Encoding changes instruction binding but may reduce prose naturalness or diversity.",
                "falsifier": "XML, headings, and labeled prose are indistinguishable under fixed semantic payloads and seeds.",
            },
            "3": {
                "claim": "Curated context has a quality knee; maximum context will not necessarily be best.",
                "falsifier": "Quality and mode control improve monotonically through every achievable dose without diversity loss.",
            },
        },
        "raw_before_editing": True,
        "single_axis_mutations": True,
    }
    preregistration["preregistration_hash"] = hash_json(preregistration)
    write_json(root / "preregistration.v1.json", preregistration)
    return payload


def _load_campaign(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    campaign = json.loads((root / "campaign_manifest.v1.json").read_text(encoding="utf-8"))
    corpus = json.loads(Path(campaign["corpus_path"]).read_text(encoding="utf-8"))
    benchmarks = json.loads(Path(campaign["benchmarks_path"]).read_text(encoding="utf-8"))
    if hash_file(Path(campaign["corpus_path"])) != campaign["corpus_hash"]:
        raise ValueError("corpus changed since campaign initialization")
    if hash_file(Path(campaign["benchmarks_path"])) != campaign["benchmark_hash"]:
        raise ValueError("benchmarks changed since campaign initialization")
    current_harness = {
        name: hash_file(Path(__file__).resolve().parent / name)
        for name in campaign.get("harness_hashes", {})
    }
    if current_harness != campaign.get("harness_hashes", {}):
        raise ValueError(
            "harness code changed since campaign initialization; start a new "
            "campaign version rather than mixing traces"
        )
    return campaign, corpus, benchmarks


def _append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.write(json.dumps(dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        __import__("os").fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _latest_completed(path: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if not path.is_file():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if value.get("status") == "completed":
            result[str(value["candidate_id"])] = value
    return result


def _terminal_copy_failures(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    failures: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if (
            value.get("status") == "failed"
            and value.get("error_type") == "SourceOverlapError"
        ):
            failures.add(str(value["candidate_id"]))
    return failures


def _candidate_gate(cell: BenchmarkCell, text: str, overlap: Mapping[str, Any], finish_reason: str) -> dict[str, Any]:
    words = len(text.split())
    normalized = tuple(
        match.group(0).casefold()
        for match in re.finditer(r"\b[\w’'-]+\b", text)
    )
    fourgram_counts: dict[tuple[str, ...], int] = {}
    for index in range(max(0, len(normalized) - 3)):
        shingle = normalized[index:index + 4]
        fourgram_counts[shingle] = fourgram_counts.get(shingle, 0) + 1
    max_fourgram_repetitions = max(fourgram_counts.values(), default=0)
    leaks = [item for item in CONTROL_SYNTAX if item in text]
    charge_terms = re.findall(
        r"\b(?:kiss|mouth|lip|breath|pulse|wrist|touch|skin|breast|nipple|"
        r"thigh|hip|erect|orgasm|naked|arousal|ache|wet|hard|heat|want|"
        r"desire|shiver|trembl|clench|undress)\w*\b",
        text,
        re.I,
    )
    anatomical_terms = re.findall(
        r"\b(?:breast|nipple|thigh|buttock|groin|penis|cock|vagina|vulva|"
        r"clitoris|testicle|labia)\w*\b",
        text,
        re.I,
    )
    explicit_terms = re.findall(
        r"\b(?:penis|cock|vagina|vulva|clitoris|labia|inside (?:her|him|me)|"
        r"entered (?:her|him|me)|came inside|penetrat|thrust|orgasm)\w*\b",
        text,
        re.I,
    )
    completed_action_terms = re.findall(
        r"\b(?:entered (?:her|him|me)|penetrat|thrust|orgasm|climax|"
        r"came (?:inside|against|with)|spent himself)\w*\b",
        text,
        re.I,
    )
    coercion_failures = re.findall(
        r"\b(?:ignored (?:her|his) (?:no|refusal)|would not let (?:her|him) go|"
        r"despite (?:her|his) refusal|(?:pin|pinned|holding|held) (?:her|him) "
        r"(?:down|in place)|caught (?:her|his) hands? and held|"
        r"(?:she|he) was trapped|you're not going home|you don't get to eat|"
        r"forced (?:her|him) to|push(?:ed)? (?:her|him) back down)\b",
        text,
        re.I,
    )
    uncertainty_escalations = re.findall(
        r"\b(?:I don't know|I do not know|not sure|uncertain)\b.{0,500}"
        r"\b(?:kiss(?:ed|ing)? (?:her|him) again|pulled (?:her|him) (?:close|back)|"
        r"held (?:her|him) in place|continued)\b",
        text,
        re.I | re.S,
    )
    mara_pov_drift = re.findall(
        r"\b(?:Jonah|Livia|Miriam|Adrian)\b(?:\s+\w+){0,3}\s+"
        r"(?:thought|knew|felt|wondered|realized|wanted|remembered|"
        r"understood|decided|feared|hoped)\b",
        text,
        re.I,
    ) if "close third Mara" in cell.hard_constraints else []
    stop_positions = [
        match.start()
        for match in re.finditer(
            r"\b(?:stop|stopped|wait|enough|not yet|pulled back|drew back)\b",
            text,
            re.I,
        )
    ]
    escalation_positions = [
        match.start()
        for match in re.finditer(
            r"\b(?:kiss(?:ed|ing)?|pulled (?:her|him) (?:close|back)|"
            r"pressed (?:her|him) against|pinned?)\b",
            text,
            re.I,
        )
    ]
    charged_stop = bool(stop_positions) and (
        not escalation_positions or max(stop_positions) > max(escalation_positions)
    ) and bool(
        re.search(r"\b(?:tomorrow|future|trust|next|still want|continued)\b", text, re.I)
    )
    endpoint_ok = True
    if cell.cell_id == "charged-restraint":
        endpoint_ok = charged_stop
    elif cell.cell_id.startswith("married-"):
        endpoint_ok = bool(
            re.search(r"\b(?:trust|truth|together|promise|decid|tell|tomorrow|drive)\w*\b", text, re.I)
        )
    elif cell.cell_id == "institutional-pressure-control":
        endpoint_ok = bool(
            re.search(r"\b(?:audit|record|evidence|protocol|refus|boundary|decision|report)\w*\b", text, re.I)
        )
    heat_ceiling = True
    if cell.heat_band in {"none", "charged-restraint", "open-door-nongraphic"}:
        heat_ceiling = not explicit_terms
    gates = {
        "word_band": cell.word_min <= words <= cell.word_max,
        "natural_stop": finish_reason != "length",
        "no_control_syntax": not leaks,
        "anti_copy": not overlap.get("hard_fail") and not overlap.get("unresolved_flags"),
        "non_erotic_control": cell.cell_id != "institutional-pressure-control" or len(charge_terms) <= 1,
        "heat_ceiling": heat_ceiling,
        "consent_invariant": not coercion_failures and not uncertainty_escalations,
        "pov_invariant": not mara_pov_drift,
        "endpoint_realized": endpoint_ok,
        "no_repetition_loop": max_fourgram_repetitions < 5,
    }
    diagnostics = {
        "erotic_charge_signal": len(charge_terms),
        "anatomical_specificity_signal": len(anatomical_terms),
        "explicit_action_signal": len(explicit_terms),
        "completed_intimacy_action_signal": len(completed_action_terms),
        "consent_language_signal": len(re.findall(r"\b(?:yes|ask|asked|want|choose|stop|wait)\w*\b", text, re.I)),
        "coercive_action_signal": len(coercion_failures),
        "uncertainty_escalation_signal": len(uncertainty_escalations),
        "relationship_delta_signal": len(re.findall(r"\b(?:together|trust|tomorrow|decid|tell|truth|know)\w*\b", text, re.I)),
        "pov_drift_signal": len(mara_pov_drift),
        "max_fourgram_repetitions": max_fourgram_repetitions,
    }
    return {"passed": all(gates.values()), "gates": gates, "word_count": words, "leaks": leaks, "erotic_term_count": len(charge_terms), "diagnostics": diagnostics}


def _claim_prompt_view(
    round_dir: Path,
    *,
    prompt_hash: str,
    recipe_id: str,
    cell_id: str,
) -> str | None:
    """Claim one semantic prompt view across independent runner processes.

    Repeated seeds for the same recipe are allowed.  A later context-dose arm
    rendering byte-identically for the same target is censored, rather than
    being misreported as evidence about a longer context.
    """

    registry = round_dir / "prompt_claims.jsonl"
    registry.parent.mkdir(parents=True, exist_ok=True)
    with registry.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        prior_recipe = None
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("prompt_hash") == prompt_hash and item.get("cell_id") == cell_id:
                prior_recipe = str(item["recipe_id"])
                break
        if prior_recipe is None:
            handle.seek(0, 2)
            handle.write(
                json.dumps(
                    {
                        "record_type": "AutoresearchPromptClaim",
                        "prompt_hash": prompt_hash,
                        "recipe_id": recipe_id,
                        "cell_id": cell_id,
                        "claimed_at": _now(),
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )
            handle.flush()
            __import__("os").fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return prior_recipe if prior_recipe != recipe_id else None


def extract_manuscript(raw: str) -> tuple[str, dict[str, Any]]:
    """Separate a complete prose manuscript from a base-model control suffix."""

    cut = len(raw)
    marker_used = ""
    for marker in MANUSCRIPT_STOP_MARKERS:
        position = raw.find(marker)
        if 0 <= position < cut:
            cut = position
            marker_used = marker.strip()
    manuscript = raw[:cut].strip()
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", manuscript) if item.strip()]
    if paragraphs:
        manuscript = "\n\n".join(paragraphs)
    return manuscript, {
        "raw_word_count": len(raw.split()),
        "manuscript_word_count": len(manuscript.split()),
        "suffix_removed": cut < len(raw),
        "stop_marker": marker_used,
        "removed_suffix_hash": sha256_text(raw[cut:]) if cut < len(raw) else "",
    }


def run_round(
    *,
    campaign_dir: str | Path,
    client: LlamaClient,
    admission: SharedEndpointAdmission,
    round_number: int = 1,
    max_tokens: int = 2_000,
    only_recipe: str | None = None,
    only_cell: str | None = None,
    only_seed: int | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    root = Path(campaign_dir)
    campaign, corpus, benchmarks = _load_campaign(root)
    frozen_max_tokens = int(campaign["generation_policy"]["max_completion_tokens"])
    if max_tokens != frozen_max_tokens:
        raise ValueError(
            f"completion budget drift: campaign={frozen_max_tokens}, requested={max_tokens}"
        )
    passages = tuple(SourcePassage(**item) for item in corpus["passages"])
    graphs = {item["passage_id"]: IntimacySceneGraph(**{key: tuple(value) if key in {"dialogue_act_sequence", "body_language_counterpoint", "sensory_channels", "narrative_distance_curve", "physical_logistics", "agency_actions"} else value for key, value in item.items() if key != "graph_hash"}) for item in corpus["graphs"]}
    cells = tuple(BenchmarkCell(**{key: tuple(value) if key in {"story_program", "hard_constraints"} else value for key, value in item.items() if key != "cell_hash"}) for item in benchmarks["cells"])
    if round_number == 1:
        raw_recipes = campaign["recipes"]
        seeds = ROUND1_SEEDS
    else:
        recipe_path = root / f"round-{round_number}" / "recipes.v1.json"
        if not recipe_path.is_file():
            raise ValueError(
                f"round {round_number} recipes are not frozen; complete and "
                f"decide round {round_number - 1} first"
            )
        raw_recipes = json.loads(recipe_path.read_text(encoding="utf-8"))["recipes"]
        seeds = ROUND2_SEEDS if round_number == 2 else ROUND3_SEEDS
    recipes = tuple(PromptRecipe(**{key: tuple(value) if key == "block_ids" else value for key, value in item.items() if key != "recipe_hash"}) for item in raw_recipes)
    author_docs = {item.passage_id: item.text for item in passages}
    bridge_docs = {f"bridge.{path.stem}": path.read_text(encoding="utf-8") for path in Path(campaign["bridge_dir"]).glob("*.md")}
    project_docs = _project_prose_documents(Path(campaign["project_root"]))
    if {key: sha256_text(value) for key, value in project_docs.items()} != campaign.get("project_prose_hashes", {}):
        raise ValueError("approved project prose changed since campaign initialization")
    anti_copy = AntiCopyIndex(
        author_docs | bridge_docs | project_docs,
        categories={
            **{key: "author-corpus" for key in author_docs},
            **{key: "project-bridge" for key in bridge_docs},
            **{key: "project-prose" for key in project_docs},
        },
        policy=AntiCopyPolicy(),
    )
    round_dir = root / f"round-{round_number}"
    calls = round_dir / "calls.jsonl"
    candidates_path = round_dir / "candidates.jsonl"
    completed = _latest_completed(candidates_path)
    terminal_copy_failures = _terminal_copy_failures(calls)
    produced = 0
    attempted = 0
    summary: list[dict[str, Any]] = []
    for recipe in recipes:
        if only_recipe and recipe.recipe_id != only_recipe:
            continue
        for cell in cells:
            if round_number == 2 and cell.cell_id not in {
                "married-explicit",
                "institutional-pressure-control",
            }:
                continue
            if only_cell and cell.cell_id != only_cell:
                continue
            blocks = build_recipe_blocks(recipe=recipe, cell=cell, passages=passages, graphs=graphs, project_root=Path(campaign["project_root"]), bridge_dir=Path(campaign["bridge_dir"]), craft_text=str(corpus.get("craft_apprenticeship_text", "")))
            prompt = render_prompt(blocks, recipe.encoding)
            prompt_hash = sha256_text(prompt)
            prompt_tokens = client.token_count(prompt)
            prompt_dir = round_dir / "prompts" / recipe.recipe_id
            prompt_dir.mkdir(parents=True, exist_ok=True)
            prompt_path = prompt_dir / f"{cell.cell_id}.txt"
            if prompt_path.exists() and sha256_text(prompt_path.read_text(encoding="utf-8")) != prompt_hash:
                raise ValueError(f"refusing prompt drift for {recipe.recipe_id}/{cell.cell_id}")
            atomic_write_text(prompt_path, prompt)
            block_manifest = [item.public_dict() for item in blocks]
            write_json(prompt_dir / f"{cell.cell_id}.blocks.json", {"recipe_hash": recipe.recipe_hash, "prompt_hash": prompt_hash, "prompt_tokens": prompt_tokens, "blocks": block_manifest})
            prior_recipe = _claim_prompt_view(
                round_dir,
                prompt_hash=prompt_hash,
                recipe_id=recipe.recipe_id,
                cell_id=cell.cell_id,
            )
            if round_number == 3 and prior_recipe:
                _append_jsonl(
                    round_dir / "censored.jsonl",
                    {
                        "record_type": "AutoresearchCensoredArm",
                        "recipe_id": recipe.recipe_id,
                        "cell_id": cell.cell_id,
                        "reason": "context-dose exhausted the eligible corpus and produced an identical prompt",
                        "duplicate_of_recipe": prior_recipe,
                        "prompt_hash": prompt_hash,
                        "prompt_tokens": prompt_tokens,
                        "token_target": recipe.token_target,
                        "recorded_at": _now(),
                    },
                )
                continue
            for seed in seeds:
                if only_seed is not None and seed != only_seed:
                    continue
                candidate_id = f"r{round_number}.{recipe.recipe_id}.{cell.cell_id}.{seed}"
                if candidate_id in completed:
                    summary.append(completed[candidate_id])
                    continue
                if candidate_id in terminal_copy_failures:
                    continue
                if limit is not None and attempted >= limit:
                    return {"round": round_number, "completed": len(summary), "new": produced, "stopped_at_limit": True}
                attempted += 1
                call_parameters = {
                    "seed": seed,
                    "max_tokens": max_tokens,
                    **SAMPLING,
                    "stop": list(MANUSCRIPT_STOP_MARKERS),
                }
                start = {
                    "record_type": "AutoresearchCall",
                    "call_id": candidate_id,
                    "candidate_id": candidate_id,
                    "model": str(getattr(client, "model", "local-model")),
                    "runtime": model_runtime_provenance(
                        str(getattr(client, "model", "local-model"))
                    ),
                    "status": "started",
                    "recipe_hash": recipe.recipe_hash,
                    "cell_hash": cell.cell_hash,
                    "prompt_hash": prompt_hash,
                    "prompt_path": str(prompt_path.resolve()),
                    "prompt_tokens": prompt_tokens,
                    "transport": "raw_completion",
                    "parameters": call_parameters,
                    "seed": seed,
                    "started_at": _now(),
                }
                _append_jsonl(calls, start)
                parts: list[str] = []
                def on_delta(delta: str) -> None:
                    parts.append(delta)
                    match = anti_copy.first_exact_match(
                        cell.opening_fragment + "".join(parts)
                    )
                    if match:
                        from .anti_copy import SourceOverlapError
                        raise SourceOverlapError(match)
                try:
                    with admission.acquire(owner=candidate_id, prompt_hash=prompt_hash, prompt_tokens=prompt_tokens, completion_tokens=max_tokens):
                        result = client.stream_raw(
                            prompt=prompt,
                            seed=seed,
                            max_tokens=max_tokens,
                            on_delta=on_delta,
                            stop=MANUSCRIPT_STOP_MARKERS,
                            **SAMPLING,
                        )
                    raw_completion = result.content
                    extracted, extraction = extract_manuscript(raw_completion)
                    text = (
                        cell.opening_fragment.rstrip()
                        + ("\n\n" if raw_completion[:1].isspace() else " ")
                        + extracted.lstrip()
                    ).strip()
                    raw_dir = round_dir / "raw"
                    raw_dir.mkdir(parents=True, exist_ok=True)
                    raw_path = raw_dir / f"{candidate_id}.txt"
                    atomic_write_text(raw_path, raw_completion)
                    overlap = anti_copy.check(candidate_id, text).to_dict()
                    effective_finish = "stop" if extraction["suffix_removed"] else result.finish_reason
                    gate = _candidate_gate(cell, text, overlap, effective_finish)
                    completed_at = _now()
                    completion_call = {
                        **start,
                        "status": "completed",
                        "raw_response_path": str(raw_path.resolve()),
                        "raw_response_sha256": sha256_text(raw_completion),
                        "finish_reason": result.finish_reason,
                        "usage": result.usage,
                        "timings": result.timings,
                        "cache": result.cache,
                        "completed_at": completed_at,
                    }
                    _append_jsonl(calls, completion_call)
                    artifact_authorship = proof_carrying_model_authorship(
                        artifact_id=candidate_id,
                        text=text,
                        model_id=str(getattr(client, "model", "local-model")),
                        call_id=candidate_id,
                        prompt_hash=prompt_hash,
                        seed=seed,
                        call_ledger_path=calls,
                        response_source="raw_response_file",
                        raw_response_path=raw_path,
                        derivation={
                            "operation": "autoresearch_manuscript_v1",
                            "literal_prefix": cell.opening_fragment,
                            "literal_prefix_origin": "benchmark_opening_fragment",
                            "literal_prefix_sha256": authorship_text_sha256(
                                cell.opening_fragment
                            ),
                            "stop_markers": list(MANUSCRIPT_STOP_MARKERS),
                        },
                        created_at=completed_at,
                    )
                    record = {
                        "record_type": "AutoresearchCandidate",
                        "candidate_id": candidate_id,
                        "status": "completed",
                        "campaign_hash": campaign["campaign_hash"],
                        "round": round_number,
                        "recipe_id": recipe.recipe_id,
                        "recipe_hash": recipe.recipe_hash,
                        "cell_id": cell.cell_id,
                        "cell_hash": cell.cell_hash,
                        "prompt_hash": prompt_hash,
                        "source_ids": sorted(
                            {source for block in blocks for source in block.source_ids}
                        ),
                        "seed": seed,
                        "sampling": SAMPLING,
                        "generation_policy": campaign["generation_policy"],
                        "text": text,
                        "text_hash": sha256_text(text),
                        "raw_path": str(raw_path),
                        "raw_hash": sha256_text(raw_completion),
                        "extraction": extraction,
                        "finish_reason": effective_finish,
                        "raw_finish_reason": result.finish_reason,
                        "usage": result.usage,
                        "timings": result.timings,
                        "cache": result.cache,
                        "overlap": overlap,
                        "mechanical": gate,
                        "completed_at": completed_at,
                        "artifact_authorship": artifact_authorship,
                        "review_attestations": [],
                    }
                    _append_jsonl(candidates_path, record)
                    summary.append(record)
                    produced += 1
                except Exception as exc:
                    partial = (
                        cell.opening_fragment.rstrip()
                        + ("\n\n" if parts and parts[0][:1].isspace() else " ")
                        + "".join(parts).lstrip()
                    ).strip()
                    partial_dir = round_dir / "raw_failures"
                    partial_dir.mkdir(parents=True, exist_ok=True)
                    partial_path = partial_dir / f"{candidate_id}.txt"
                    atomic_write_text(partial_path, partial)
                    _append_jsonl(calls, {**start, "status": "failed", "error_type": type(exc).__name__, "error": str(exc), "partial_path": str(partial_path), "partial_hash": sha256_text(partial), "failed_at": _now()})
                    if type(exc).__name__ != "SourceOverlapError":
                        raise
    return {"round": round_number, "completed": len(summary), "new": produced, "eligible": sum(bool(item.get("mechanical", {}).get("passed")) for item in summary), "round_dir": str(round_dir)}


# Backward-compatible name used by the first CLI implementation.
run_round1 = run_round


def _write_next_round_recipes(
    root: Path,
    round_number: int,
    promoted: Sequence[str],
) -> str | None:
    if not promoted or round_number >= 3:
        return None
    campaign = json.loads((root / "campaign_manifest.v1.json").read_text(encoding="utf-8"))
    if round_number == 1:
        parents = {
            item["recipe_id"]: PromptRecipe(
                **{
                    key: tuple(value) if key == "block_ids" else value
                    for key, value in item.items()
                    if key != "recipe_hash"
                }
            )
            for item in campaign["recipes"]
        }
        recipes = []
        for parent_id in promoted[:2]:
            parent = parents[parent_id]
            for encoding in ("headings", "xml", "labeled-prose"):
                recipes.append(
                    PromptRecipe(
                        recipe_id=f"r2.{parent.topology}.{encoding}",
                        round_number=2,
                        topology=parent.topology,
                        encoding=encoding,
                        token_target=parent.token_target,
                        named_author=parent.named_author,
                        include_bridge=parent.include_bridge,
                        block_ids=(),
                        control_density=parent.control_density,
                        runway_policy=parent.runway_policy,
                        parent_recipe_hash=parent.recipe_hash,
                        mutated_axis="encoding",
                    )
                )
    else:
        prior_path = root / "round-2" / "recipes.v1.json"
        prior = json.loads(prior_path.read_text(encoding="utf-8"))["recipes"]
        parent_item = next(item for item in prior if item["recipe_id"] == promoted[0])
        parent = PromptRecipe(
            **{
                key: tuple(value) if key == "block_ids" else value
                for key, value in parent_item.items()
                if key != "recipe_hash"
            }
        )
        recipes = [
            PromptRecipe(
                recipe_id=f"r3.{parent.topology}.{parent.encoding}.{tokens // 1000}k",
                round_number=3,
                topology=parent.topology,
                encoding=parent.encoding,
                token_target=tokens,
                named_author=parent.named_author,
                include_bridge=parent.include_bridge,
                block_ids=(),
                control_density=f"context-dose-{tokens}",
                runway_policy=parent.runway_policy,
                parent_recipe_hash=parent.recipe_hash,
                mutated_axis="context-dose",
            )
            for tokens in (6000, 12000, 24000, 48000, 64000)
        ]
    next_round = round_number + 1
    destination = root / f"round-{next_round}" / "recipes.v1.json"
    payload = {
        "record_type": "AutoresearchRecipeSet",
        "round": next_round,
        "recipes": [asdict(item) | {"recipe_hash": item.recipe_hash} for item in recipes],
    }
    payload["recipe_set_hash"] = hash_json(payload)
    if destination.exists():
        prior = json.loads(destination.read_text(encoding="utf-8"))
        if prior.get("recipe_set_hash") != payload["recipe_set_hash"]:
            raise ValueError(f"refusing to rewrite frozen round-{next_round} recipes")
    else:
        write_json(destination, payload)
    return str(destination)


def export_blind_review(campaign_dir: str | Path, round_number: int, output_dir: str | Path) -> dict[str, Any]:
    root = Path(campaign_dir)
    candidates_path = root / f"round-{round_number}" / "candidates.jsonl"
    candidates = list(_latest_completed(candidates_path).values())
    rng = random.Random(f"{root.name}:round-{round_number}:blind")
    shuffled = list(candidates)
    rng.shuffle(shuffled)
    key = {f"C{index:03d}": item["candidate_id"] for index, item in enumerate(shuffled, 1)}
    output = Path(output_dir)
    reader = output / "reader"
    internal = output / "internal"
    reader.mkdir(parents=True, exist_ok=True)
    internal.mkdir(parents=True, exist_ok=True)
    benchmark_by_id = {item.cell_id: item for item in default_benchmarks()}
    packet = []
    for blind_id, candidate_id in key.items():
        item = next(value for value in shuffled if value["candidate_id"] == candidate_id)
        cell = benchmark_by_id[item["cell_id"]]
        packet.append({"blind_id": blind_id, "target": {"label": cell.label, "heat_band": cell.heat_band, "hard_constraints": list(cell.hard_constraints)}, "text": item["text"]})
    reverse = {candidate_id: blind_id for blind_id, candidate_id in key.items()}
    groups: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for item in candidates:
        groups.setdefault((item["cell_id"], int(item["seed"])), []).append(item)
    pairs = []
    for (cell_id, seed), values in sorted(groups.items()):
        ordered = sorted(values, key=lambda item: item["recipe_id"])
        if len(ordered) < 2:
            continue
        if round_number == 1:
            anchors = [item for item in ordered if item["recipe_id"] == "r1-control"]
            comparisons = [
                (anchors[0], item)
                for item in ordered
                if anchors and item["recipe_id"] != "r1-control"
            ]
        elif round_number == 2:
            by_topology: dict[str, list[dict[str, Any]]] = {}
            for item in ordered:
                topology = item["recipe_id"].rsplit(".", 1)[0]
                by_topology.setdefault(topology, []).append(item)
            comparisons = []
            headings = []
            for topology_items in by_topology.values():
                anchor = next(
                    (item for item in topology_items if item["recipe_id"].endswith(".headings")),
                    topology_items[0],
                )
                headings.append(anchor)
                comparisons.extend((anchor, item) for item in topology_items if item is not anchor)
            if len(headings) > 1:
                comparisons.append((headings[0], headings[1]))
        else:
            anchor = next(
                (item for item in ordered if item["recipe_id"].endswith(".6k")),
                ordered[0],
            )
            comparisons = [(anchor, item) for item in ordered if item is not anchor]
        for index, (left, right) in enumerate(comparisons):
            if rng.random() < 0.5:
                left, right = right, left
            pairs.append(
                {
                    "pair_id": f"P.{cell_id}.{seed}.{index + 1:02d}",
                    "target_cell": cell_id,
                    "left": reverse[left["candidate_id"]],
                    "right": reverse[right["candidate_id"]],
                }
            )
    reader_payload = {"record_type": "BlindAutoresearchPacket", "campaign_id": root.name, "round": round_number, "rubric": list(REVIEW_AXES), "evidence_rule": "Every numeric judgment requires a contiguous exact quote.", "candidates": packet, "pairs": pairs, "pair_rule": "Choose left, right, or tie; judge the target rather than generic prettiness. Pair construction uses the preregistered round anchor, but left/right order is seeded and blind."}
    write_json(reader / "packet.json", reader_payload)
    write_json(internal / "reveal_key.json", {"record_type": "BlindRevealKey", "key": key, "packet_hash": hash_file(reader / "packet.json")})
    return {"candidate_count": len(packet), "pair_count": len(pairs), "reader_packet": str(reader / "packet.json"), "reader_packet_hash": hash_file(reader / "packet.json"), "reveal_key": str(internal / "reveal_key.json")}


def admit_reviews(campaign_dir: str | Path, round_number: int, review_file: str | Path, reviewer_id: str) -> dict[str, Any]:
    root = Path(campaign_dir)
    reveal_path = root / f"round-{round_number}" / "review" / "internal" / "reveal_key.json"
    reveal = json.loads(reveal_path.read_text(encoding="utf-8"))
    supplied = json.loads(Path(review_file).read_text(encoding="utf-8"))
    if isinstance(supplied, Mapping):
        reviews = supplied.get("candidates", [])
        pair_reviews = supplied.get("pairs", [])
    else:
        reviews = supplied
        pair_reviews = []
    if not isinstance(reviews, list) or not isinstance(pair_reviews, list):
        raise ValueError("review admission requires candidate and pair lists")
    destination = root / f"round-{round_number}" / "review" / "admitted.jsonl"
    if destination.exists():
        for line in destination.read_text(encoding="utf-8").splitlines():
            prior = json.loads(line)
            if prior.get("reviewer_id") == reviewer_id:
                raise ValueError(f"duplicate reviewer id: {reviewer_id}")
    admitted = []
    for item in reviews:
        blind_id = str(item["blind_id"])
        if blind_id not in reveal["key"]:
            raise ValueError(f"unknown blind candidate: {blind_id}")
        candidate_id = reveal["key"][blind_id]
        candidate = _latest_completed(root / f"round-{round_number}" / "candidates.jsonl")[candidate_id]
        text = candidate["text"]
        scores = item.get("scores", {})
        if not isinstance(scores, Mapping) or set(scores) != set(REVIEW_AXES):
            raise ValueError(
                f"{blind_id} must score every declared review axis exactly once"
            )
        if any(not 1 <= float(value) <= 7 for value in scores.values()):
            raise ValueError(f"{blind_id} scores must be within 1..7")
        evidence = item.get("evidence", {})
        if not isinstance(evidence, Mapping) or not evidence:
            raise ValueError(f"{blind_id} has no passage evidence")
        if set(evidence) != set(REVIEW_AXES):
            raise ValueError(f"{blind_id} requires evidence for every score axis")
        for quotes in evidence.values():
            values = [quotes] if isinstance(quotes, str) else list(quotes)
            if any(str(quote) not in text for quote in values):
                raise ValueError(f"{blind_id} contains a non-exact evidence quote")
        record = {"record_type": "BlindManuscriptReview", "reviewer_id": reviewer_id, "blind_id": blind_id, "candidate_id": candidate_id, "scores": dict(scores), "evidence": evidence, "defects": item.get("defects", []), "verdict": item.get("verdict", ""), "admitted_at": _now(), "source_review_hash": hash_file(Path(review_file))}
        _append_jsonl(destination, record)
        admitted.append(record)
    packet_path = root / f"round-{round_number}" / "review" / "reader" / "packet.json"
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    known_pairs = {item["pair_id"]: item for item in packet.get("pairs", [])}
    pair_destination = root / f"round-{round_number}" / "review" / "pairwise.jsonl"
    pair_admitted = 0
    for item in pair_reviews:
        pair_id = str(item["pair_id"])
        if pair_id not in known_pairs:
            raise ValueError(f"unknown blind pair: {pair_id}")
        choice = str(item["winner"])
        pair = known_pairs[pair_id]
        if choice not in {pair["left"], pair["right"], "tie"}:
            raise ValueError(f"invalid winner for {pair_id}")
        record = {
            "record_type": "BlindPairwiseReview",
            "reviewer_id": reviewer_id,
            "pair_id": pair_id,
            "left_candidate_id": reveal["key"][pair["left"]],
            "right_candidate_id": reveal["key"][pair["right"]],
            "winner_candidate_id": reveal["key"].get(choice) if choice != "tie" else "tie",
            "reason": str(item.get("reason", "")),
            "admitted_at": _now(),
        }
        _append_jsonl(pair_destination, record)
        pair_admitted += 1
    return {"reviewer_id": reviewer_id, "admitted": len(admitted), "pairwise_admitted": pair_admitted, "path": str(destination)}


def admit_research_review(
    campaign_dir: str | Path,
    round_number: int,
    review_file: str | Path,
    reviewer_id: str,
    role: str,
) -> dict[str, Any]:
    """Admit a post-blind prompt/trace critique with hash-linked evidence."""

    if role not in RESEARCH_REVIEW_ROLES:
        raise ValueError(f"research review role must be one of {RESEARCH_REVIEW_ROLES}")
    root = Path(campaign_dir).resolve()
    round_dir = (root / f"round-{round_number}").resolve()
    admitted_blind = round_dir / "review" / "admitted.jsonl"
    if not admitted_blind.is_file():
        raise ValueError("blind manuscript judgments must be frozen before trace review")
    payload = json.loads(Path(review_file).read_text(encoding="utf-8"))
    records = payload.get("reviews", []) if isinstance(payload, Mapping) else payload
    if not isinstance(records, list) or not records:
        raise ValueError("research review file must contain a non-empty review list")
    candidates = _latest_completed(round_dir / "candidates.jsonl")
    recipe_ids = {item["recipe_id"] for item in candidates.values()}
    destination = round_dir / "review" / "research_reviews.jsonl"
    if destination.is_file():
        for line in destination.read_text(encoding="utf-8").splitlines():
            old = json.loads(line)
            if old.get("reviewer_id") == reviewer_id and old.get("role") == role:
                raise ValueError(f"duplicate {role} reviewer id: {reviewer_id}")
    admitted: list[dict[str, Any]] = []
    for supplied in records:
        if not isinstance(supplied, Mapping):
            raise ValueError("each research review must be an object")
        missing = [field for field in RESEARCH_REVIEW_FIELDS if not supplied.get(field)]
        if missing:
            raise ValueError("research review missing fields: " + ", ".join(missing))
        recipe_id = str(supplied.get("recipe_id", ""))
        if recipe_id not in recipe_ids:
            raise ValueError(f"unknown recipe in research review: {recipe_id}")
        confidence = float(supplied["confidence"])
        if not 0 <= confidence <= 1:
            raise ValueError("research-review confidence must be within 0..1")
        manuscript_evidence = supplied.get("manuscript_evidence", [])
        if not manuscript_evidence:
            raise ValueError("research review requires exact manuscript evidence")
        for evidence in manuscript_evidence:
            candidate_id = str(evidence["candidate_id"])
            quote = str(evidence["quote"])
            if candidate_id not in candidates or quote not in candidates[candidate_id]["text"]:
                raise ValueError("research review contains unsupported manuscript evidence")
        trace_evidence = supplied.get("trace_evidence", [])
        if not trace_evidence:
            raise ValueError("research review requires hash-linked trace evidence")
        validated_traces = []
        for evidence in trace_evidence:
            artifact = Path(str(evidence["artifact_path"])).resolve()
            try:
                artifact.relative_to(round_dir)
            except ValueError as exc:
                raise ValueError("trace evidence must be inside the reviewed round") from exc
            if not artifact.is_file():
                raise ValueError(f"trace evidence does not exist: {artifact}")
            actual_hash = hash_file(artifact)
            declared_hash = str(evidence.get("artifact_hash", actual_hash))
            if declared_hash != actual_hash:
                raise ValueError(f"trace evidence hash mismatch: {artifact}")
            validated_traces.append(
                {
                    "artifact_path": str(artifact),
                    "artifact_hash": actual_hash,
                    "observation": str(evidence.get("observation", "")),
                }
            )
        record = {
            "record_type": "ResearchReview",
            "campaign_id": root.name,
            "round": round_number,
            "reviewer_id": reviewer_id,
            "role": role,
            "recipe_id": recipe_id,
            **{field: supplied[field] for field in RESEARCH_REVIEW_FIELDS},
            "manuscript_evidence": manuscript_evidence,
            "trace_evidence": validated_traces,
            "blind_reviews_frozen_hash": hash_file(admitted_blind),
            "source_review_hash": hash_file(Path(review_file)),
            "admitted_at": _now(),
        }
        record["review_hash"] = hash_json(
            {key: value for key, value in record.items() if key != "admitted_at"}
        )
        _append_jsonl(destination, record)
        admitted.append(record)
    return {
        "reviewer_id": reviewer_id,
        "role": role,
        "admitted": len(admitted),
        "path": str(destination),
        "hashes": [item["review_hash"] for item in admitted],
    }


def adjudicate_overlap_flags(
    campaign_dir: str | Path,
    round_number: int,
    client: LlamaClient,
    output: str | Path,
) -> dict[str, Any]:
    """Resolve fuzzy source-neighbor flags using a strictly local model."""

    host = (urlparse(client.base_url).hostname or "").casefold()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("raw source overlap adjudication may use only a local endpoint")
    root = Path(campaign_dir)
    campaign, corpus, _ = _load_campaign(root)
    candidates = list(
        _latest_completed(root / f"round-{round_number}" / "candidates.jsonl").values()
    )
    source_docs = {
        item["passage_id"]: item["text"] for item in corpus["passages"]
    }
    source_docs.update(
        {
            f"bridge.{path.stem}": path.read_text(encoding="utf-8")
            for path in Path(campaign["bridge_dir"]).glob("*.md")
        }
    )
    source_docs.update(_project_prose_documents(Path(campaign["project_root"])))
    index = AntiCopyIndex(source_docs)
    destination = Path(output)
    existing: set[tuple[str, str]] = set()
    if destination.is_file():
        for line in destination.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                existing.add((item["candidate_id"], item["source_id"]))
    count = 0
    for candidate in candidates:
        fuzzy = index.fuzzy_matches(candidate["text"])
        for source_id in sorted({str(item["source_id"]) for item in fuzzy}):
            if (candidate["candidate_id"], source_id) in existing:
                continue
            prompt = (
                "Decide whether the NEW DRAFT copies or closely paraphrases the "
                "LOCAL SOURCE in wording, scene choreography, or distinctive "
                "rhetorical sequence. Shared genre ideas are not copying. Return "
                "JSON only: {\"copying\":boolean,\"confidence\":0..1,"
                "\"kind\":\"none|close-paraphrase|structural-copy\",\"reason\":string}.\n\n"
                "LOCAL SOURCE:\n" + source_docs[source_id] + "\n\nNEW DRAFT:\n" + candidate["text"]
            )
            completion = client.complete(
                prompt=prompt,
                seed=1_761_003 + count * 17,
                max_tokens=512,
                temperature=0.1,
                top_p=0.9,
                min_p=0.01,
                extra={"reasoning_format": "none"},
            )
            raw = completion.content.strip()
            start, end = raw.find("{"), raw.rfind("}")
            if start < 0 or end <= start:
                raise ValueError("local overlap adjudicator returned no JSON object")
            judgment = json.loads(raw[start:end + 1])
            if not isinstance(judgment.get("copying"), bool):
                raise ValueError("local overlap judgment lacks boolean copying field")
            record = {
                "record_type": "LocalOverlapAdjudication",
                "campaign_id": root.name,
                "round": round_number,
                "candidate_id": candidate["candidate_id"],
                "candidate_hash": candidate["text_hash"],
                "source_id": source_id,
                "source_hash": sha256_text(source_docs[source_id]),
                "copying": judgment["copying"],
                "confidence": float(judgment.get("confidence", 0)),
                "kind": str(judgment.get("kind", "none")),
                "reason": str(judgment.get("reason", "")),
                "judge": client.model,
                "usage": completion.usage,
                "adjudicated_at": _now(),
            }
            _append_jsonl(destination, record)
            existing.add((candidate["candidate_id"], source_id))
            count += 1
    return {"adjudicated": count, "path": str(destination)}


def analyze_traces(campaign_dir: str | Path, round_number: int, output: str | Path) -> dict[str, Any]:
    root = Path(campaign_dir)
    candidates = list(_latest_completed(root / f"round-{round_number}" / "candidates.jsonl").values())
    campaign, corpus, _ = _load_campaign(root)
    passages = tuple(SourcePassage(**item) for item in corpus["passages"])
    source_docs = {item.passage_id: item.text for item in passages}
    bridge_docs = {
        f"bridge.{path.stem}": path.read_text(encoding="utf-8")
        for path in Path(campaign["bridge_dir"]).glob("*.md")
    }
    project_docs = _project_prose_documents(Path(campaign["project_root"]))
    postflight_index = AntiCopyIndex(source_docs | bridge_docs | project_docs)
    prior_texts: dict[str, str] = {}
    postflight: dict[str, Mapping[str, Any]] = {}
    for candidate in sorted(candidates, key=lambda item: item["candidate_id"]):
        report = postflight_index.check(
            candidate["candidate_id"],
            candidate["text"],
            prior_candidates=prior_texts,
        )
        postflight[candidate["candidate_id"]] = report.to_dict()
        prior_texts[candidate["candidate_id"]] = candidate["text"]
    adjudication_path = root / f"round-{round_number}" / "review" / "overlap_adjudications.jsonl"
    adjudications = [
        json.loads(line)
        for line in adjudication_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ] if adjudication_path.is_file() else []
    by_overlap_key = {
        (item["candidate_id"], item["source_id"]): item
        for item in adjudications
    }
    for candidate_id, raw_report in postflight.items():
        report = dict(raw_report)
        flagged_ids = {
            str(item["source_id"])
            for item in report.get("fuzzy_matches", ())
        }
        decisions = [
            by_overlap_key[(candidate_id, source_id)]
            for source_id in sorted(flagged_ids)
            if (candidate_id, source_id) in by_overlap_key
        ]
        if flagged_ids and len(decisions) == len(flagged_ids):
            report["semantic_matches"] = decisions
            report["unresolved_flags"] = False
            report["hard_fail"] = bool(report.get("exact_matches")) or any(
                bool(item["copying"]) for item in decisions
            )
        postflight[candidate_id] = report
    reviews_path = root / f"round-{round_number}" / "review" / "admitted.jsonl"
    if not reviews_path.is_file():
        raise ValueError("blind reviews must be admitted before trace analysis")
    reviews = [json.loads(line) for line in reviews_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    reviewer_ids = {item["reviewer_id"] for item in reviews}
    if len(reviewer_ids) < 2:
        raise ValueError("trace analysis requires two independent blind reviewers")
    review_coverage: dict[str, set[str]] = {}
    for review in reviews:
        review_coverage.setdefault(review["candidate_id"], set()).add(
            review["reviewer_id"]
        )
    missing_reviewers = sorted(
        item["candidate_id"]
        for item in candidates
        if len(review_coverage.get(item["candidate_id"], set())) < 2
    )
    if missing_reviewers:
        raise ValueError(
            "every candidate requires two blind reviews before trace analysis: "
            + ", ".join(missing_reviewers[:8])
        )
    pair_path = root / f"round-{round_number}" / "review" / "pairwise.jsonl"
    pair_reviews = [json.loads(line) for line in pair_path.read_text(encoding="utf-8").splitlines() if line.strip()] if pair_path.is_file() else []
    candidate_recipe = {item["candidate_id"]: item["recipe_id"] for item in candidates}
    by_recipe: dict[str, list[dict[str, Any]]] = {}
    for item in candidates:
        by_recipe.setdefault(item["recipe_id"], []).append(item)
    arms = []
    for recipe_id, items in sorted(by_recipe.items()):
        arm_reviews = [review for review in reviews if review["candidate_id"] in {item["candidate_id"] for item in items}]
        wins = losses = ties = 0
        anchor_wins = anchor_losses = anchor_ties = 0
        for pair in pair_reviews:
            left_recipe = candidate_recipe[pair["left_candidate_id"]]
            right_recipe = candidate_recipe[pair["right_candidate_id"]]
            if recipe_id not in {left_recipe, right_recipe}:
                continue
            winner = pair["winner_candidate_id"]
            if winner == "tie":
                ties += 1
            elif candidate_recipe[winner] == recipe_id:
                wins += 1
            else:
                losses += 1
            if round_number == 1 and "r1-control" in {left_recipe, right_recipe} and recipe_id != "r1-control":
                if winner == "tie":
                    anchor_ties += 1
                elif candidate_recipe[winner] == recipe_id:
                    anchor_wins += 1
                else:
                    anchor_losses += 1
        score_axes: dict[str, list[float]] = {}
        for review in arm_reviews:
            for axis, value in review.get("scores", {}).items():
                score_axes.setdefault(axis, []).append(float(value))
        comparisons = wins + losses + ties
        by_cell: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            by_cell.setdefault(item["cell_id"], []).append(item)
        heat_medians = {
            cell_id: {
                field: median(
                    float(item["mechanical"]["diagnostics"].get(field, 0))
                    for item in cell_items
                )
                for field in (
                    "erotic_charge_signal",
                    "anatomical_specificity_signal",
                    "explicit_action_signal",
                )
            }
            for cell_id, cell_items in by_cell.items()
        }
        control_charge = heat_medians.get("institutional-pressure-control", {}).get("erotic_charge_signal", 0)
        charged_charge = heat_medians.get("charged-restraint", {}).get("erotic_charge_signal")
        explicit_anatomy = heat_medians.get("married-explicit", {}).get("anatomical_specificity_signal")
        open_anatomy = heat_medians.get("married-open-door", {}).get("anatomical_specificity_signal")
        required_contrasts = []
        if charged_charge is not None:
            required_contrasts.append(charged_charge > control_charge)
        if explicit_anatomy is not None and open_anatomy is not None:
            required_contrasts.append(explicit_anatomy > open_anatomy)
        if explicit_anatomy is not None:
            required_contrasts.append(explicit_anatomy > 0)

        def shingles(value: str) -> set[tuple[str, ...]]:
            words = tuple(match.group(0).casefold() for match in re.finditer(r"\b[\w’'-]+\b", value))
            return {tuple(words[index:index + 4]) for index in range(max(0, len(words) - 3))}

        similarities = []
        for cell_items in by_cell.values():
            for left_index, left in enumerate(cell_items):
                left_set = shingles(left["text"])
                for right in cell_items[left_index + 1:]:
                    right_set = shingles(right["text"])
                    union = left_set | right_set
                    similarities.append(len(left_set & right_set) / len(union) if union else 1.0)
        unique_texts = len({item["text_hash"] for item in items})
        diversity = {
            "unique_texts": unique_texts,
            "max_within_cell_fourgram_jaccard": round(max(similarities, default=0.0), 6),
            "useful_diversity": unique_texts > 1 and max(similarities, default=0.0) < 0.85,
        }
        eligible_count = 0
        for item in items:
            noncopy_gates = {
                key: value
                for key, value in item["mechanical"]["gates"].items()
                if key != "anti_copy"
            }
            overlap_ok = not postflight[item["candidate_id"]].get("hard_fail") and not postflight[item["candidate_id"]].get("unresolved_flags")
            eligible_count += int(all(noncopy_gates.values()) and overlap_ok)
        anchor_comparisons = anchor_wins + anchor_losses + anchor_ties
        arms.append({"recipe_id": recipe_id, "candidate_count": len(items), "eligible_count": eligible_count, "finish_reasons": {reason: sum(item["finish_reason"] == reason for item in items) for reason in sorted({item["finish_reason"] for item in items})}, "median_scores": {axis: sorted(values)[len(values) // 2] for axis, values in score_axes.items() if values}, "pairwise": {"wins": wins, "losses": losses, "ties": ties, "comparisons": comparisons, "win_rate": (wins + 0.5 * ties) / comparisons if comparisons else 0.0}, "causal_baseline_pairwise": {"wins": anchor_wins, "losses": anchor_losses, "ties": anchor_ties, "comparisons": anchor_comparisons, "win_rate": (anchor_wins + 0.5 * anchor_ties) / anchor_comparisons if anchor_comparisons else 0.0}, "prompt_hashes": sorted({item["prompt_hash"] for item in items}), "source_sets": sorted({tuple(item["source_ids"]) for item in items}), "copy_failures": sum(bool(postflight[item["candidate_id"]].get("hard_fail")) for item in items), "unresolved_source_flags": sum(bool(postflight[item["candidate_id"]].get("unresolved_flags")) for item in items), "cross_candidate_match_count": sum(len(postflight[item["candidate_id"]].get("cross_candidate_matches", ())) for item in items), "control_leak_failures": sum(not item["mechanical"]["gates"]["non_erotic_control"] for item in items), "heat_band_medians": heat_medians, "heat_band_separation": bool(required_contrasts) and all(required_contrasts), "diversity": diversity})
    payload = {"record_type": "AutoresearchTraceAnalysis", "campaign_id": root.name, "round": round_number, "blind_reviews_frozen_hash": hash_file(reviews_path), "overlap_adjudications_hash": hash_file(adjudication_path) if adjudication_path.is_file() else "", "arms": arms, "limitations": ["Aggregate diagnostics do not replace close reading.", "Causal claims require a block-level prompt difference and counterexample inspection."], "created_at": _now()}
    payload["analysis_hash"] = hash_json({key: value for key, value in payload.items() if key != "created_at"})
    write_json(Path(output), payload)
    return payload


def decide_round(campaign_dir: str | Path, round_number: int, trace_analysis: str | Path, output: str | Path) -> dict[str, Any]:
    root = Path(campaign_dir)
    analysis = json.loads(Path(trace_analysis).read_text(encoding="utf-8"))
    if analysis["blind_reviews_frozen_hash"] != hash_file(root / f"round-{round_number}" / "review" / "admitted.jsonl"):
        raise ValueError("blind reviews changed after trace analysis")
    research_path = root / f"round-{round_number}" / "review" / "research_reviews.jsonl"
    if not research_path.is_file():
        raise ValueError("trace-critic and research-lead reviews are required before decision")
    research_reviews = [
        json.loads(line)
        for line in research_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    roles = {item.get("role") for item in research_reviews}
    if not set(RESEARCH_REVIEW_ROLES).issubset(roles):
        raise ValueError("both trace_critic and research_lead reviews are required")
    if any(
        item.get("blind_reviews_frozen_hash") != analysis["blind_reviews_frozen_hash"]
        for item in research_reviews
    ):
        raise ValueError("research review was not based on the frozen blind judgments")
    ranked = []
    for arm in analysis["arms"]:
        scores = arm.get("median_scores", {})
        quality = sum(float(scores.get(axis, 0)) for axis in ("romantic_pull", "heat_effectiveness", "prose_freshness", "causal_coherence", "desire_to_continue"))
        eligibility = arm["eligible_count"] / max(1, arm["candidate_count"])
        pairwise = arm.get("pairwise", {})
        pairwise_pass = int(pairwise.get("comparisons", 0)) > 0 and float(pairwise.get("win_rate", 0)) >= 0.60
        causal = arm.get("causal_baseline_pairwise", {})
        beats_causal_baseline = round_number != 1 or (
            arm["recipe_id"] != "r1-control"
            and int(causal.get("comparisons", 0)) > 0
            and float(causal.get("win_rate", 0)) >= 0.60
        )
        promotable = eligibility >= 0.75 and arm["copy_failures"] == 0 and arm["unresolved_source_flags"] == 0 and arm["control_leak_failures"] == 0 and arm.get("heat_band_separation", False) and arm.get("diversity", {}).get("useful_diversity", False) and pairwise_pass and beats_causal_baseline
        ranked.append({"recipe_id": arm["recipe_id"], "quality_index": quality, "eligibility_rate": eligibility, "pairwise_win_rate": pairwise.get("win_rate", 0.0), "causal_baseline_win_rate": causal.get("win_rate", 0.0), "beats_causal_baseline": beats_causal_baseline, "heat_band_separation": arm.get("heat_band_separation", False), "useful_diversity": arm.get("diversity", {}).get("useful_diversity", False), "promotable": promotable})
    ranked.sort(key=lambda item: (not item["promotable"], -item["quality_index"], -item["eligibility_rate"], item["recipe_id"]))
    promoted = [item["recipe_id"] for item in ranked if item["promotable"]][:2]
    tie_break_required = round_number == 2 and bool(ranked) and max(
        float(item["pairwise_win_rate"]) for item in ranked
    ) < 0.60
    payload = {"record_type": "AutoresearchRoundDecision", "campaign_id": root.name, "round": round_number, "trace_analysis_hash": hash_file(Path(trace_analysis)), "research_reviews_hash": hash_file(research_path), "ranking": ranked, "promoted": [] if tie_break_required else promoted, "no_winner": not promoted and not tie_break_required, "tie_break_required": tie_break_required, "tie_break_protocol": "two new seeds across all four benchmark cells for every Round-2 recipe" if tie_break_required else "not-triggered", "decision_rule": "75% eligibility; zero copy/unresolved/control-leak failures; correct heat-band separation; useful within-arm diversity; at least 60% blinded pairwise win rate; then blinded quality index", "created_at": _now()}
    payload["decision_hash"] = hash_json({key: value for key, value in payload.items() if key != "created_at"})
    payload["next_round_recipes"] = _write_next_round_recipes(
        root, round_number, () if tie_break_required else promoted
    )
    write_json(Path(output), payload)
    return payload


def render_report(campaign_dir: str | Path, output: str | Path) -> str:
    root = Path(campaign_dir)
    lines = [f"# Prompt Autoresearch — {root.name}", "", "Raw-output comparisons; no frontier polishing is included in prompt-arm scores.", ""]
    for round_number in (1, 2, 3):
        round_dir = root / f"round-{round_number}"
        lines.extend((f"## Round {round_number}", ""))
        candidates = _latest_completed(round_dir / "candidates.jsonl")
        lines.append(f"Completed candidates: {len(candidates)}")
        decision = round_dir / "decision.v1.json"
        if decision.is_file():
            value = json.loads(decision.read_text(encoding="utf-8"))
            lines.append("Promoted: " + (", ".join(value.get("promoted", ())) or "none"))
        else:
            lines.append("Decision: pending")
        lines.append("")
    lines.extend(("## Interpretation discipline", "", "A longer prompt wins only if blinded prose quality and mode control improve without copying, canon, agency, or non-erotic-control regressions. If no arm clears that bar, the campaign reports no winner.", ""))
    rendered = "\n".join(lines)
    atomic_write_text(Path(output), rendered)
    return rendered


def package_human_finalists(
    campaign_dir: str | Path,
    round_number: int,
    output_dir: str | Path,
    *,
    max_finalists: int = 6,
) -> dict[str, Any]:
    """Build a static, blinded human packet from the final raw winners."""

    root = Path(campaign_dir)
    round_dir = root / f"round-{round_number}"
    decision_path = round_dir / "decision.v1.json"
    if not decision_path.is_file():
        raise ValueError("a frozen round decision is required before packaging")
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    promoted = set(decision.get("promoted", ()))
    if not promoted:
        raise ValueError("the round has no promoted recipe to package")
    candidates = [
        item
        for item in _latest_completed(round_dir / "candidates.jsonl").values()
        if item["recipe_id"] in promoted and item["mechanical"]["passed"]
    ]
    review_path = round_dir / "review" / "admitted.jsonl"
    reviews = [
        json.loads(line)
        for line in review_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ] if review_path.is_file() else []
    scores: dict[str, list[float]] = {}
    for review in reviews:
        scores.setdefault(review["candidate_id"], []).append(
            sum(
                float(review["scores"][axis])
                for axis in (
                    "romantic_pull",
                    "heat_effectiveness",
                    "prose_freshness",
                    "causal_coherence",
                    "desire_to_continue",
                )
            )
        )
    candidates.sort(
        key=lambda item: (
            -(
                sum(scores.get(item["candidate_id"], ()))
                / max(1, len(scores.get(item["candidate_id"], ())))
            ),
            item["candidate_id"],
        )
    )
    candidates = candidates[:max_finalists]
    for item in candidates:
        validate_artifact_authorship(
            item.get("artifact_authorship", {}),
            text=str(item.get("text", "")),
            artifact_id=str(item.get("candidate_id", "")),
            require_model_pipeline=True,
        )
    rng = random.Random(f"{root.name}:round-{round_number}:human-finalists")
    rng.shuffle(candidates)
    labels = [chr(ord("A") + index) for index in range(len(candidates))]
    key = {label: item["candidate_id"] for label, item in zip(labels, candidates)}
    output = Path(output_dir)
    reader = output / "reader"
    internal = output / "internal"
    reader.mkdir(parents=True, exist_ok=True)
    internal.mkdir(parents=True, exist_ok=True)
    md = ["# Fiction finalists", "", "Read in any order. Judge the manuscript, not what you think produced it.", ""]
    cards = []
    for label, item in zip(labels, candidates):
        md.extend((f"## {label}", "", item["text"], ""))
        cards.append(
            f'<article class="story"><h2>Story {label}</h2><div class="prose">'
            + "".join(f"<p>{html.escape(paragraph)}</p>" for paragraph in re.split(r"\n\s*\n", item["text"]) if paragraph.strip())
            + "</div></article>"
        )
    atomic_write_text(reader / "finalists.md", "\n".join(md))
    axes = (
        "romantic pull",
        "heat",
        "coherence",
        "freshness",
        "worldview integration",
        "desire to continue",
        "suspected copying",
    )
    rating_rows = "".join(
        f'<label>{html.escape(axis.title())}<input type="number" min="1" max="7" name="{html.escape(axis.replace(" ", "_"))}"></label>'
        for axis in axes
    )
    html_doc = f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fiction finalists</title><style>
body{{font:17px/1.6 Georgia,serif;max-width:820px;margin:3rem auto;padding:0 1.2rem;color:#211d1a;background:#fbf8f2}}
.story{{margin:5rem 0;border-top:1px solid #b9aa98}}h1,h2{{font-family:system-ui,sans-serif}}.prose p{{margin:1em 0}}
.review{{padding:1.5rem;background:#fff;border:1px solid #d8cec0}}label{{display:block;margin:.6rem 0}}input{{float:right;width:4rem}}
textarea{{width:100%;min-height:6rem}}button{{padding:.8rem 1.2rem;margin-top:1rem}}
</style></head><body><h1>Fiction finalists</h1><p>Read the stories without guessing how they were made. Scores run from 1 to 7.</p>
{''.join(cards)}
<section class="review"><h2>Your response</h2><label>Reviewer code <input name="reviewer"></label>{rating_rows}
<label>Preferred story <select name="preferred">{''.join(f'<option>{label}</option>' for label in labels)}</select></label>
<label>Best or hottest passage<textarea name="best"></textarea></label><label>Where it felt false or dull<textarea name="false"></textarea></label>
<label>What should happen next?<textarea name="next"></textarea></label><button id="save">Download response</button></section>
<script>document.getElementById('save').onclick=()=>{{const q=(s)=>document.querySelector(s);const data={{package_id:{json.dumps(sha256_text(canonical_json_text(key))[:16])},reviewer:q('[name=reviewer]').value,preferred:q('[name=preferred]').value,ratings:{{}},best:q('[name=best]').value,false_or_dull:q('[name=false]').value,next:q('[name=next]').value}};document.querySelectorAll('input[type=number]').forEach(x=>data.ratings[x.name]=Number(x.value));const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{{type:'application/json'}}));a.download='fiction-review.json';a.click();}};</script>
</body></html>"""
    atomic_write_text(reader / "index.html", html_doc)
    reveal = {
        "record_type": "AutoresearchHumanRevealKey",
        "campaign_id": root.name,
        "round": round_number,
        "key": key,
        "decision_hash": hash_file(decision_path),
        "reader_hashes": {
            "html": hash_file(reader / "index.html"),
            "markdown": hash_file(reader / "finalists.md"),
        },
    }
    write_json(internal / "reveal_key.json", reveal)
    return {
        "finalist_count": len(candidates),
        "reader_html": str(reader / "index.html"),
        "reader_markdown": str(reader / "finalists.md"),
        "reveal_key": str(internal / "reveal_key.json"),
        "reader_hashes": reveal["reader_hashes"],
    }
