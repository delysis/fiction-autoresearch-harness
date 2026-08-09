"""Deterministic semantic-diversity analysis for story programs.

The module deliberately works one level above prose.  It compares causal
events and six story-role decisions rather than character names, phrasing, or
n-grams.  It is intended as a cheap rejection layer between program sampling
and expensive realization.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Any, Iterable, Mapping, Sequence, TypeAlias


ProgramValue: TypeAlias = str | Mapping[str, Any]


class SemanticRole(StrEnum):
    """Causal decisions that should vary across a batch of story programs."""

    ANTAGONIST_TRUTH = "antagonist_truth"
    PROTAGONIST_ERROR = "protagonist_error"
    EXIT_AGENCY = "exit_agency"
    LOVER_COST = "lover_cost"
    INSTITUTIONAL_CONSEQUENCE = "institutional_consequence"
    UNCANNY_REMAINDER = "uncanny_remainder"


SEMANTIC_ROLES = tuple(SemanticRole)


@dataclass(frozen=True, slots=True)
class EventSignature:
    """A normalized event, retaining position but no source wording."""

    position: int
    atoms: tuple[str, ...]
    actor: str = ""


@dataclass(frozen=True, slots=True)
class RoleSignature:
    """Normalized atoms for the six batch-diversity roles."""

    antagonist_truth: tuple[str, ...] = ()
    protagonist_error: tuple[str, ...] = ()
    exit_agency: tuple[str, ...] = ()
    lover_cost: tuple[str, ...] = ()
    institutional_consequence: tuple[str, ...] = ()
    uncanny_remainder: tuple[str, ...] = ()

    def get(self, role: SemanticRole | str) -> tuple[str, ...]:
        """Return one role using either an enum or its stable wire name."""

        return getattr(self, SemanticRole(role).value)

    def items(self) -> tuple[tuple[SemanticRole, tuple[str, ...]], ...]:
        return tuple((role, self.get(role)) for role in SEMANTIC_ROLES)


@dataclass(frozen=True, slots=True)
class CausalSignature:
    """Normalized causal representation of one story program."""

    program_id: str
    events: tuple[EventSignature, ...]
    roles: RoleSignature
    endpoint: tuple[str, ...]
    source_format: str


@dataclass(frozen=True, slots=True)
class SimilarityBreakdown:
    """Pairwise similarity on independent causal axes, in the range 0..1."""

    left_id: str
    right_id: str
    event_similarity: float
    role_similarity: float
    endpoint_similarity: float
    overall_similarity: float
    matching_roles: tuple[SemanticRole, ...]


@dataclass(frozen=True, slots=True)
class DuplicateRejection:
    candidate_id: str
    matched_id: str
    similarity: SimilarityBreakdown
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SelectionResult:
    """Deterministic greedy selection plus explainable rejections."""

    selected: tuple[CausalSignature, ...]
    rejected: tuple[DuplicateRejection, ...]

    @property
    def selected_ids(self) -> tuple[str, ...]:
        return tuple(item.program_id for item in self.selected)


@dataclass(frozen=True, slots=True)
class BatchConvergence:
    """Diagnostics indicating whether a program batch has collapsed."""

    overconverged: bool
    pairwise: tuple[SimilarityBreakdown, ...]
    near_duplicate_pairs: tuple[SimilarityBreakdown, ...]
    collapsed_roles: tuple[SemanticRole, ...]
    mean_overall_similarity: float
    maximum_overall_similarity: float
    near_duplicate_fraction: float
    reasons: tuple[str, ...]


_KEY_RE = re.compile(r"[^a-z0-9]+")
_WORD_RE = re.compile(r"[a-z][a-z'-]*")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def _key(value: object) -> str:
    return _KEY_RE.sub("_", str(value).casefold()).strip("_")


_ROLE_ALIASES: dict[str, SemanticRole] = {
    "antagonist_truth": SemanticRole.ANTAGONIST_TRUTH,
    "antagonist_is_right_about": SemanticRole.ANTAGONIST_TRUTH,
    "what_antagonist_gets_right": SemanticRole.ANTAGONIST_TRUTH,
    "what_livia_gets_right": SemanticRole.ANTAGONIST_TRUTH,
    "difficult_truth_livia_sees": SemanticRole.ANTAGONIST_TRUTH,
    "livia_s_difficult_truth": SemanticRole.ANTAGONIST_TRUTH,
    "livia_truth": SemanticRole.ANTAGONIST_TRUTH,
    "protagonist_error": SemanticRole.PROTAGONIST_ERROR,
    "protagonist_is_wrong_about": SemanticRole.PROTAGONIST_ERROR,
    "what_protagonist_gets_wrong": SemanticRole.PROTAGONIST_ERROR,
    "what_mara_gets_wrong": SemanticRole.PROTAGONIST_ERROR,
    "mara_s_error": SemanticRole.PROTAGONIST_ERROR,
    "mara_error": SemanticRole.PROTAGONIST_ERROR,
    "exit_agency": SemanticRole.EXIT_AGENCY,
    "who_enables_the_exit": SemanticRole.EXIT_AGENCY,
    "who_creates_the_exit": SemanticRole.EXIT_AGENCY,
    "mara_s_exit_causing_action": SemanticRole.EXIT_AGENCY,
    "exit": SemanticRole.EXIT_AGENCY,
    "lover_cost": SemanticRole.LOVER_COST,
    "what_the_lover_risks": SemanticRole.LOVER_COST,
    "what_jonah_risks": SemanticRole.LOVER_COST,
    "jonah_s_cost_or_needed_repair": SemanticRole.LOVER_COST,
    "jonah_cost": SemanticRole.LOVER_COST,
    "institutional_consequence": SemanticRole.INSTITUTIONAL_CONSEQUENCE,
    "institutional_response": SemanticRole.INSTITUTIONAL_CONSEQUENCE,
    "institutional_cost": SemanticRole.INSTITUTIONAL_CONSEQUENCE,
    "miriam_s_institutional_cost": SemanticRole.INSTITUTIONAL_CONSEQUENCE,
    "consequence_for_fulcrum": SemanticRole.INSTITUTIONAL_CONSEQUENCE,
    "consequence": SemanticRole.INSTITUTIONAL_CONSEQUENCE,
    "uncanny_remainder": SemanticRole.UNCANNY_REMAINDER,
    "residual_mystery": SemanticRole.UNCANNY_REMAINDER,
    "unexplained_remainder": SemanticRole.UNCANNY_REMAINDER,
    "concrete_unexplained_observation": SemanticRole.UNCANNY_REMAINDER,
    "mystery": SemanticRole.UNCANNY_REMAINDER,
}

_EVENT_KEYS = {
    "events",
    "event_sequence",
    "event_sequencing",
    "event_chain",
    "causal_events",
    "beats",
    "beat_map",
    "plot",
    "causal_sequence",
    "story_events",
}
_ENDPOINT_KEYS = {
    "endpoint",
    "ending",
    "aftermath",
    "outcome",
    "relationship_delta",
    "final_state",
    "hook",
}
_ROLE_CONTAINER_KEYS = {
    "roles",
    "causal_roles",
    "semantic_roles",
    "diversity_roles",
    "causal_dimensions",
}


# Ordered from specific to general.  These are semantic labels, not substitute
# phrases used to rewrite prose.  A phrase can produce more than one atom.
_CONCEPT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(pattern, re.IGNORECASE))
    for name, pattern in (
        ("accurate_observation", r"(?:\b(?:right|correct|accurate(?:ly)?|truly)\b.*\b(?:see|read|notice|perceiv|observ|recogn)|\b(?:is|was|gets?) right\b)"),
        ("antagonist_mistaken", r"\b(?:antagonist|livia|facilitator).{0,30}\b(?:wrong|mistaken|misreads?|inaccurate|sees? nothing)"),
        ("protagonist_correct", r"\b(?:protagonist|mara|heroine).{0,30}\b(?:correct|right|understands? every|makes? no (?:mistake|error))"),
        ("longing_belonging", r"\b(?:long|hunger|want|crav|need|desire).{0,35}\b(?:belong|accept|inside|included|community|home)"),
        ("approval_hunger", r"\b(?:approval|validation|admiration|liked|chosen)\b"),
        ("intimacy_hunger", r"\b(?:intimacy|touch|desire|attraction|kiss|closeness|wanted)\b"),
        ("uncertainty", r"\b(?:uncertain|unsure|doubt|confus|ambigu)"),
        ("no_requires_proof", r"(?:\b(?:no|refusal|boundary).{0,30}\b(?:proof|explain|justify|earn|evidence)|\b(?:proof|evidence|justification).{0,30}\b(?:no|refusal|boundary))"),
        ("authority_knows_best", r"\b(?:leader|authority|mentor|institution).{0,30}\b(?:knows? best|more than|defer|trust)"),
        ("self_doubt", r"\b(?:distrusts?|doubts?|second-guesses?).{0,20}\b(?:herself|himself|themself|own)"),
        ("overinterpretation", r"\b(?:overinterpret|mistakes?|confuses?|equates?|treats?).{0,30}\b(?:signal|feeling|uncertainty|attraction|observation|data)"),
        ("self_authored_exit", r"\b(?:protagonist|mara|she|he|they).{0,35}\b(?:leaves?|walks? out|opens? the door|ends? the session|exits?|refuses?)"),
        ("mentor_rescue", r"\b(?:mentor|miriam|teacher|senior|older woman).{0,35}\b(?:opens?|interrupts?|rescues?|ends?|orders?|escorts?)"),
        ("lover_rescue", r"\b(?:lover|jonah|love interest|boyfriend|partner).{0,35}\b(?:opens?|interrupts?|rescues?|ends?|escorts?|leads?)"),
        ("ally_enabled_exit", r"\b(?:friend|ally|student|peer|witness).{0,35}\b(?:opens?|interrupts?|rescues?|ends?|escorts?|supports?)"),
        ("negotiated_exit", r"\b(?:mutual|together|collective|group|vote|agreement|negotiat).{0,25}\b(?:exit|leave|door|end|stop)"),
        ("social_status_cost", r"\b(?:status|standing|prestige|popular|rank|social capital|credibility)\b"),
        ("belonging_cost", r"\b(?:ostrac|exclu|banish|cast out|loses? (?:his|her|their) place|(?:loses?|sacrifices?|risks?).{0,24}(?:community|belonging))\b"),
        ("reputation_cost", r"\b(?:reputation|rumou?r|gossip|slander|branded|labelled|labeled)\b"),
        ("material_cost", r"\b(?:job|money|funding|housing|scholarship|expelled|fired|career)\b"),
        ("desire_deferred", r"\b(?:does not|doesn't|refuses? to|foregoes?|delays?|waits?|withholds?).{0,30}\b(?:kiss|touch|sex|desire|romance|claim)"),
        ("relationship_risk", r"\b(?:risks?|costs?|loses?|endangers?).{0,25}\b(?:relationship|trust|friendship|mara|protagonist|beloved)"),
        ("no_lover_cost", r"\b(?:lover|jonah|beloved).{0,30}\b(?:no cost|risks? nothing|loses? nothing|pays? no price)"),
        ("institution_retaliates", r"\b(?:institution|academy|school|group|leadership|fulcrum).{0,40}\b(?:retaliat|punish|sanction|expel|threat|disciplin|blacklist)"),
        ("institution_reinterprets", r"\b(?:institution|academy|school|group|leadership|fulcrum).{0,45}\b(?:reframe|reinterpret|spin|absorbs?|explains? away|patholog)"),
        ("institution_reforms", r"\b(?:institution|academy|school|group|leadership|fulcrum).{0,40}\b(?:reform|change|apolog|investigat|new rule|policy)"),
        ("institution_splits", r"\b(?:institution|academy|school|group|leadership|fulcrum|students?).{0,40}\b(?:split|faction|divide|take sides|fracture)"),
        ("no_institutional_consequence", r"\b(?:institution|academy|school|group|leadership|fulcrum).{0,35}\b(?:does nothing|no consequence|unchanged|ignores?)"),
        ("authority_intervenes", r"\b(?:authority|mentor|miriam|teacher|leader).{0,35}\b(?:interven|overrule|stop|halt|opens?)"),
        ("unexplained_knowledge", r"\b(?:knows?|names?|predicts?|describes?).{0,35}\b(?:could not|couldn't|impossible|never told|hidden|unseen|unknown)"),
        ("impossible_prediction", r"\b(?:prediction|forecast|prophecy|foretell).{0,35}\b(?:true|correct|happens?|fulfilled)"),
        ("residual_bodily_sensation", r"\b(?:prickle|chill|pressure|heat|pulse|sensation|gooseflesh).{0,35}\b(?:remain|linger|unexplained|without|after)"),
        ("cue_channel_control", r"\b(?:cue|channel|posture|timbre|muscle|voice|body language).{0,35}\b(?:control|mask|block|remove|blind|test)"),
        ("coincidence", r"\b(?:coincidence|chance|accident|random)\b"),
        ("no_uncanny_remainder", r"\b(?:nothing|none|fully|entirely|all).{0,25}\b(?:unexplained|mysterious|uncanny|remainder|explained)"),
        ("arrival", r"\b(?:arrives?|enters?|comes? to|walks? in)\b"),
        ("interpretive_claim", r"\b(?:interprets?|diagnoses?|claims?|tells? .{0,20} (?:means?|really))\b"),
        ("challenge", r"\b(?:challenges?|questions?|confronts?|objects?|pushes? back)\b"),
        ("experiment", r"\b(?:experiment|test|control condition|trial|calibrat)\b"),
        ("contact", r"\b(?:touch|wrist|hand|embrace|kiss|contact)\b"),
        ("boundary", r"\b(?:boundary|refusal|says? no|declines?|stop rule)\b"),
        ("intervention", r"\b(?:interrupts?|intervenes?|steps? in|opens? the door)\b"),
        ("departure", r"\b(?:leaves?|exits?|walks? (?:out|home|away)|departs?)\b"),
        ("romantic_turn", r"\b(?:kiss|confess|attraction|romantic|desire)\b"),
        ("consequence", r"\b(?:consequence|cost|punish|aftermath|fallout)\b"),
    )
)

_TOKEN_CANON = {
    "academy": "institution",
    "school": "institution",
    "fulcrum": "institution",
    "organization": "institution",
    "organisation": "institution",
    "livia": "antagonist",
    "facilitator": "antagonist",
    "mara": "protagonist",
    "heroine": "protagonist",
    "jonah": "lover",
    "boyfriend": "lover",
    "beloved": "lover",
    "miriam": "mentor",
    "depart": "leave",
    "departing": "leave",
    "exits": "leave",
    "exit": "leave",
    "leaves": "leave",
    "refuses": "refuse",
    "refusal": "refuse",
    "declines": "refuse",
    "correctly": "accurate",
    "rightly": "accurate",
    "notices": "notice",
    "observes": "notice",
    "perceives": "notice",
    "risks": "risk",
    "costs": "cost",
    "punishes": "punish",
    "retaliates": "retaliate",
}

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "because", "been", "being",
    "but", "by", "can", "could", "did", "do", "does", "for", "from", "had",
    "has", "have", "he", "her", "hers", "him", "his", "how", "i", "if", "in",
    "into", "is", "it", "its", "of", "on", "or", "our", "she", "so", "that",
    "the", "their", "them", "then", "they", "this", "to", "too", "was", "we",
    "were", "what", "when", "where", "which", "while", "who", "why", "will",
    "with", "would", "you", "your", "about", "after", "before", "through",
    "gets", "thing", "something", "story", "scene", "event", "beat",
}


def _values_as_text(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Mapping):
        # Preserve actor/action/result order for structured beats.
        preferred = ("actor", "action", "object", "result", "outcome", "description")
        bits = [str(value[key]) for key in preferred if key in value and value[key] is not None]
        if not bits:
            bits = [str(item) for item in value.values() if not isinstance(item, (list, dict))]
        return (" ".join(bits),) if bits else ()
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        result: list[str] = []
        for item in value:
            result.extend(_values_as_text(item))
        return tuple(result)
    return (str(value),)


def _semantic_atoms(text: str, *, max_keywords: int = 8) -> tuple[str, ...]:
    normalized = " ".join(text.casefold().replace("’", "'").split())
    concepts = {f"c:{name}" for name, pattern in _CONCEPT_PATTERNS if pattern.search(normalized)}
    tokens: list[str] = []
    for token in _WORD_RE.findall(normalized):
        token = token.strip("'-")
        if len(token) < 3 or token in _STOPWORDS:
            continue
        canonical = _TOKEN_CANON.get(token, token)
        if canonical not in tokens:
            tokens.append(canonical)
    # Concepts dominate comparisons. Keywords make novel, concrete events
    # distinguishable without turning this into an n-gram metric.
    return tuple(sorted(concepts)) + tuple(f"k:{token}" for token in tokens[:max_keywords])


def _actor(text: str) -> str:
    lowered = text.casefold()
    for name, role in (
        ("mara", "protagonist"),
        ("protagonist", "protagonist"),
        ("livia", "antagonist"),
        ("antagonist", "antagonist"),
        ("jonah", "lover"),
        ("lover", "lover"),
        ("miriam", "mentor"),
        ("mentor", "mentor"),
        ("institution", "institution"),
        ("academy", "institution"),
        ("group", "group"),
    ):
        if re.search(rf"\b{re.escape(name)}\b", lowered):
            return role
    return ""


def _structured_sections(program: Mapping[str, Any]) -> tuple[dict[SemanticRole, list[str]], list[str], list[str]]:
    roles = {role: [] for role in SEMANTIC_ROLES}
    events: list[str] = []
    endpoints: list[str] = []

    def visit(mapping: Mapping[str, Any], *, nested: bool = False) -> None:
        for raw_key, value in mapping.items():
            key = _key(raw_key)
            role = _ROLE_ALIASES.get(key)
            if role is not None:
                roles[role].extend(_values_as_text(value))
            elif key in _EVENT_KEYS:
                events.extend(_values_as_text(value))
            elif key in _ENDPOINT_KEYS:
                endpoints.extend(_values_as_text(value))
            elif key in _ROLE_CONTAINER_KEYS and isinstance(value, Mapping):
                visit(value, nested=True)
            elif not nested and isinstance(value, Mapping) and key in {"program", "story_program", "causal_program"}:
                visit(value, nested=True)

    visit(program)
    return roles, events, endpoints


def _freeform_sections(text: str) -> tuple[dict[SemanticRole, list[str]], list[str], list[str]]:
    roles = {role: [] for role in SEMANTIC_ROLES}
    events: list[str] = []
    endpoints: list[str] = []
    current: SemanticRole | str | None = None
    unclassified: list[str] = []
    heading = re.compile(
        r"^\s*(?:[-*+]\s*)?(?:\*\*)?([A-Za-z][A-Za-z _/-]{1,48})(?:\*\*)?\s*:\s*(.*)$"
    )
    for raw_line in text.splitlines():
        line = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", raw_line).strip()
        if not line:
            continue
        matched = heading.match(line)
        if matched:
            key, remainder = _key(matched.group(1)), matched.group(2).strip()
            if key in _ROLE_ALIASES:
                current = _ROLE_ALIASES[key]
                if remainder:
                    roles[current].append(remainder)
                continue
            if key in _EVENT_KEYS:
                current = "events"
                if remainder:
                    events.append(remainder)
                continue
            if key in _ENDPOINT_KEYS:
                current = "endpoint"
                if remainder:
                    endpoints.append(remainder)
                continue
        # Markdown heading without a colon.
        naked_key = _key(re.sub(r"^#+\s*|\*\*", "", line))
        if naked_key in _ROLE_ALIASES:
            current = _ROLE_ALIASES[naked_key]
            continue
        if naked_key in _EVENT_KEYS:
            current = "events"
            continue
        if naked_key in _ENDPOINT_KEYS:
            current = "endpoint"
            continue
        if isinstance(current, SemanticRole):
            roles[current].append(line)
        elif current == "events":
            events.append(line)
        elif current == "endpoint":
            endpoints.append(line)
        else:
            unclassified.append(line)

    # With no explicit event section, sentences are still usable causal beats.
    if not events:
        event_source = " ".join(unclassified)
        events = [part.strip() for part in _SENTENCE_RE.split(event_source) if part.strip()]
    if not endpoints and events:
        endpoints.append(events[-1])

    # Classify explicit causal sentences even when authors did not use headings.
    joined = unclassified + events
    cue_patterns: dict[SemanticRole, re.Pattern[str]] = {
        SemanticRole.ANTAGONIST_TRUTH: re.compile(r"\b(?:antagonist|livia).{0,35}\b(?:right|correct|accurate|truly sees)", re.I),
        SemanticRole.PROTAGONIST_ERROR: re.compile(r"\b(?:protagonist|mara).{0,35}\b(?:wrong|mistake|misread|believes|assumes)", re.I),
        SemanticRole.EXIT_AGENCY: re.compile(r"\b(?:exit|leave|door|ends? the session|walks? out)\b", re.I),
        SemanticRole.LOVER_COST: re.compile(r"\b(?:lover|jonah).{0,30}\b(?:cost|risk|lose|sacrifice|forgo|refuse)", re.I),
        SemanticRole.INSTITUTIONAL_CONSEQUENCE: re.compile(r"\b(?:institution|academy|fulcrum|leadership|group).{0,40}\b(?:respond|punish|reframe|change|split|retaliat)", re.I),
        SemanticRole.UNCANNY_REMAINDER: re.compile(r"\b(?:uncanny|unexplained|mystery|impossible|couldn't know|lingering)\b", re.I),
    }
    for sentence in joined:
        for role, pattern in cue_patterns.items():
            if not roles[role] and pattern.search(sentence):
                roles[role].append(sentence)
    return roles, events, endpoints


def extract_causal_signature(
    program: ProgramValue,
    *,
    program_id: str | None = None,
) -> CausalSignature:
    """Extract a normalized signature from JSON-like or free-form programs.

    Structured role fields are preferred. Free-form programs can use ordinary
    Markdown headings (for example ``Antagonist truth: ...``), but exact
    wording is not required.
    """

    if isinstance(program, Mapping):
        roles_text, event_text, endpoint_text = _structured_sections(program)
        inferred_id = str(program.get("program_id") or program.get("id") or "program")
        source_format = "structured"
    elif isinstance(program, str):
        roles_text, event_text, endpoint_text = _freeform_sections(program)
        inferred_id = "program"
        source_format = "freeform"
    else:
        raise TypeError("program must be a string or mapping")
    identifier = (program_id or inferred_id).strip()
    if not identifier:
        raise ValueError("program_id must not be empty")

    role_values: dict[str, tuple[str, ...]] = {}
    for role in SEMANTIC_ROLES:
        text = " ".join(roles_text[role])
        role_values[role.value] = _semantic_atoms(text) if text else ()
    role_signature = RoleSignature(**role_values)

    events = tuple(
        EventSignature(
            position=index,
            atoms=_semantic_atoms(text, max_keywords=10),
            actor=_actor(text),
        )
        for index, text in enumerate(event_text)
        if text.strip()
    )
    endpoint = _semantic_atoms(" ".join(endpoint_text), max_keywords=12)
    if not endpoint and events:
        endpoint = events[-1].atoms
    return CausalSignature(
        program_id=identifier,
        events=events,
        roles=role_signature,
        endpoint=endpoint,
        source_format=source_format,
    )


def extract_signatures(programs: Sequence[ProgramValue]) -> tuple[CausalSignature, ...]:
    """Extract a deterministically identified batch of signatures."""

    signatures: list[CausalSignature] = []
    seen: set[str] = set()
    for index, program in enumerate(programs, 1):
        inferred = ""
        if isinstance(program, Mapping):
            inferred = str(program.get("program_id") or program.get("id") or "")
        identifier = inferred or f"program-{index:03d}"
        if identifier in seen:
            raise ValueError(f"duplicate program_id: {identifier}")
        seen.add(identifier)
        signatures.append(extract_causal_signature(program, program_id=identifier))
    return tuple(signatures)


def _weighted_jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    a, b = set(left), set(right)
    if not a or not b:
        return 0.0
    concepts_a = {atom for atom in a if atom.startswith("c:")}
    concepts_b = {atom for atom in b if atom.startswith("c:")}
    keywords_a = a - concepts_a
    keywords_b = b - concepts_b

    def jaccard(one: set[str], two: set[str]) -> float:
        return len(one & two) / len(one | two) if one and two else 0.0

    keyword_score = jaccard(keywords_a, keywords_b)
    if concepts_a and concepts_b:
        # A paraphrase often adds a second, compatible concept.  Overlap
        # coefficient recognizes the shared causal core; Jaccard still makes
        # materially different elaborations less than identical.
        concept_overlap = len(concepts_a & concepts_b) / min(
            len(concepts_a), len(concepts_b)
        )
        concept_jaccard = jaccard(concepts_a, concepts_b)
        return 0.70 * concept_overlap + 0.20 * concept_jaccard + 0.10 * keyword_score
    # Unknown concrete events remain comparable, but cannot look as certain as
    # a match supported by the semantic ontology.
    return 0.55 * keyword_score


def _event_match(left: EventSignature, right: EventSignature) -> float:
    atom_score = _weighted_jaccard(left.atoms, right.atoms)
    if left.actor and right.actor:
        actor_score = 1.0 if left.actor == right.actor else 0.0
        return 0.8 * atom_score + 0.2 * actor_score
    return atom_score


def _event_similarity(left: Sequence[EventSignature], right: Sequence[EventSignature]) -> float:
    if not left or not right:
        return 0.0
    # Soft sequence alignment: LCS admits wording/beat-count differences while
    # retaining causal order. Coverage catches reordered copies.
    rows, cols = len(left) + 1, len(right) + 1
    table = [[0.0] * cols for _ in range(rows)]
    for i, event_left in enumerate(left, 1):
        for j, event_right in enumerate(right, 1):
            match = _event_match(event_left, event_right)
            diagonal = table[i - 1][j - 1] + match if match >= 0.34 else 0.0
            table[i][j] = max(table[i - 1][j], table[i][j - 1], diagonal)
    ordered = table[-1][-1] / max(len(left), len(right))
    forward = sum(max(_event_match(item, other) for other in right) for item in left) / len(left)
    reverse = sum(max(_event_match(item, other) for other in left) for item in right) / len(right)
    coverage = (forward + reverse) / 2
    return min(1.0, 0.7 * ordered + 0.3 * coverage)


def compare_signatures(left: CausalSignature, right: CausalSignature) -> SimilarityBreakdown:
    """Compare causal events, semantic roles, and final state independently."""

    role_scores: list[float] = []
    matching: list[SemanticRole] = []
    for role in SEMANTIC_ROLES:
        a, b = left.roles.get(role), right.roles.get(role)
        if not a and not b:
            continue
        score = _weighted_jaccard(a, b)
        role_scores.append(score)
        if score >= 0.72:
            matching.append(role)
    role_similarity = sum(role_scores) / len(role_scores) if role_scores else 0.0
    event_similarity = _event_similarity(left.events, right.events)
    endpoint_similarity = _weighted_jaccard(left.endpoint, right.endpoint)
    # Causal role decisions intentionally outweigh surface event resemblance.
    overall = 0.35 * event_similarity + 0.50 * role_similarity + 0.15 * endpoint_similarity
    return SimilarityBreakdown(
        left_id=left.program_id,
        right_id=right.program_id,
        event_similarity=round(event_similarity, 6),
        role_similarity=round(role_similarity, 6),
        endpoint_similarity=round(endpoint_similarity, 6),
        overall_similarity=round(overall, 6),
        matching_roles=tuple(matching),
    )


def pairwise_similarities(signatures: Sequence[CausalSignature]) -> tuple[SimilarityBreakdown, ...]:
    return tuple(
        compare_signatures(signatures[left], signatures[right])
        for left in range(len(signatures))
        for right in range(left + 1, len(signatures))
    )


def _coerce_signatures(
    programs: Sequence[ProgramValue | CausalSignature],
) -> tuple[CausalSignature, ...]:
    signatures: list[CausalSignature] = []
    seen: set[str] = set()
    for index, item in enumerate(programs, 1):
        if isinstance(item, CausalSignature):
            signature = item
        else:
            inferred = ""
            if isinstance(item, Mapping):
                inferred = str(item.get("program_id") or item.get("id") or "")
            signature = extract_causal_signature(
                item,
                program_id=inferred or f"program-{index:03d}",
            )
        if signature.program_id in seen:
            raise ValueError(f"duplicate program_id: {signature.program_id}")
        seen.add(signature.program_id)
        signatures.append(signature)
    return tuple(signatures)


def _duplicate_reasons(
    similarity: SimilarityBreakdown,
    *,
    near_duplicate_threshold: float,
    role_threshold: float,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if similarity.overall_similarity >= near_duplicate_threshold:
        reasons.append("overall causal signature is a near duplicate")
    if similarity.role_similarity >= role_threshold and len(similarity.matching_roles) >= 3:
        reasons.append("three or more causal roles repeat")
    if similarity.event_similarity >= 0.88 and similarity.endpoint_similarity >= 0.72:
        reasons.append("event sequence and endpoint repeat")
    return tuple(reasons)


def select_diverse_programs(
    programs: Sequence[ProgramValue | CausalSignature],
    *,
    limit: int | None = None,
    near_duplicate_threshold: float = 0.76,
    role_threshold: float = 0.82,
) -> SelectionResult:
    """Greedily retain the first causally distinct programs.

    Input order is the priority order (for example, an upstream quality rank),
    making the result deterministic and easy to audit.
    """

    if limit is not None and limit < 1:
        raise ValueError("limit must be positive or None")
    if not 0 <= near_duplicate_threshold <= 1 or not 0 <= role_threshold <= 1:
        raise ValueError("similarity thresholds must be in the range 0..1")
    signatures = _coerce_signatures(programs)

    selected: list[CausalSignature] = []
    rejected: list[DuplicateRejection] = []
    for candidate in signatures:
        if limit is not None and len(selected) >= limit:
            break
        collisions: list[tuple[SimilarityBreakdown, tuple[str, ...]]] = []
        for incumbent in selected:
            similarity = compare_signatures(candidate, incumbent)
            reasons = _duplicate_reasons(
                similarity,
                near_duplicate_threshold=near_duplicate_threshold,
                role_threshold=role_threshold,
            )
            if reasons:
                collisions.append((similarity, reasons))
        if collisions:
            similarity, reasons = max(
                collisions, key=lambda item: item[0].overall_similarity
            )
            rejected.append(
                DuplicateRejection(
                    candidate_id=candidate.program_id,
                    matched_id=similarity.right_id,
                    similarity=similarity,
                    reasons=reasons,
                )
            )
        else:
            selected.append(candidate)
    return SelectionResult(tuple(selected), tuple(rejected))


def analyze_batch_convergence(
    programs: Sequence[ProgramValue | CausalSignature],
    *,
    near_duplicate_threshold: float = 0.76,
    role_threshold: float = 0.82,
    duplicate_fraction_threshold: float = 0.40,
    mean_similarity_threshold: float = 0.62,
) -> BatchConvergence:
    """Report batch-level collapse without rejecting high-quality novelty."""

    if any(not 0 <= value <= 1 for value in (
        near_duplicate_threshold,
        role_threshold,
        duplicate_fraction_threshold,
        mean_similarity_threshold,
    )):
        raise ValueError("thresholds must be in the range 0..1")
    signatures = _coerce_signatures(programs)
    pairs = pairwise_similarities(signatures)
    duplicates = tuple(
        pair for pair in pairs
        if _duplicate_reasons(
            pair,
            near_duplicate_threshold=near_duplicate_threshold,
            role_threshold=role_threshold,
        )
    )
    mean = sum(pair.overall_similarity for pair in pairs) / len(pairs) if pairs else 0.0
    maximum = max((pair.overall_similarity for pair in pairs), default=0.0)
    duplicate_fraction = len(duplicates) / len(pairs) if pairs else 0.0

    collapsed: list[SemanticRole] = []
    if len(signatures) >= 3:
        for role in SEMANTIC_ROLES:
            comparisons: list[float] = []
            for left in range(len(signatures)):
                for right in range(left + 1, len(signatures)):
                    a = signatures[left].roles.get(role)
                    b = signatures[right].roles.get(role)
                    if a or b:
                        comparisons.append(_weighted_jaccard(a, b))
            if comparisons and sum(score >= role_threshold for score in comparisons) / len(comparisons) >= 0.60:
                collapsed.append(role)

    reasons: list[str] = []
    if duplicate_fraction >= duplicate_fraction_threshold and pairs:
        reasons.append("too many pairwise causal near-duplicates")
    if mean >= mean_similarity_threshold and pairs:
        reasons.append("mean causal similarity is too high")
    if len(collapsed) >= 3:
        reasons.append("three or more semantic roles have collapsed")
    return BatchConvergence(
        overconverged=bool(reasons),
        pairwise=pairs,
        near_duplicate_pairs=duplicates,
        collapsed_roles=tuple(collapsed),
        mean_overall_similarity=round(mean, 6),
        maximum_overall_similarity=round(maximum, 6),
        near_duplicate_fraction=round(duplicate_fraction, 6),
        reasons=tuple(reasons),
    )


# Compact aliases for callers that already use "detect" and "signature" as
# nouns in pipeline code.
causal_signature = extract_causal_signature
detect_overconvergence = analyze_batch_convergence


__all__ = [
    "BatchConvergence",
    "CausalSignature",
    "DuplicateRejection",
    "EventSignature",
    "ProgramValue",
    "RoleSignature",
    "SEMANTIC_ROLES",
    "SelectionResult",
    "SemanticRole",
    "SimilarityBreakdown",
    "analyze_batch_convergence",
    "causal_signature",
    "compare_signatures",
    "detect_overconvergence",
    "extract_causal_signature",
    "extract_signatures",
    "pairwise_similarities",
    "select_diverse_programs",
]
