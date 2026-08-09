"""Deterministic and model-assisted evaluation for fiction candidates.

The deterministic layer deliberately reports inspectable evidence.  It catches
mechanical violations and produces diagnostics for semantic questions; it does
not pretend that regular expressions can replace an editorial judge.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, is_dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import random
import re
from statistics import mean
from typing import Any, Iterable, Mapping, Sequence


RUBRIC_PATH = Path(__file__).with_name("rubrics") / "s01_romance_v1.json"
GABALDON_RUBRIC_PATH = (
    Path(__file__).with_name("rubrics") / "s01_romance_v2_gabaldon.json"
)
S02_RUBRIC_PATH = (
    Path(__file__).with_name("rubrics") / "s02_proof_story_v1.json"
)
WORD_RE = re.compile(r"\b[\w’'-]+\b", re.UNICODE)
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

S01_BEAT_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "compound_beauty_and_asymmetry",
        (
            r"\b(?:compound|redwoods?)\b.{0,1200}\b(?:asymmetr|hierarch|studied casual|curat)",
            r"\b(?:asymmetr|hierarch|studied casual|curat)\w*\b.{0,1200}\b(?:compound|redwoods?)\b",
        ),
    ),
    (
        "adrian_frames_game",
        (
            r"\bAdrian\b.{0,700}\b(?:calibration|without words|nonverbal|game)\b",
            r"\b(?:calibration|without words|nonverbal)\b.{0,700}\bAdrian\b",
        ),
    ),
    (
        "livia_uncanny_reads",
        (
            r"\bLivia\b.{0,700}\b(?:read|guess|uncanny|accur|know)\w*\b",
            r"\b(?:read|uncanny|accur)\w*\b.{0,700}\bLivia\b",
        ),
    ),
    (
        "jonah_refuses_to_perform",
        (
            r"\bJonah\b.{0,700}\b(?:refus|won't|wouldn't|not (?:tell|narrate|perform|read)|without taking)\w*\b",
            r"\b(?:refus|wouldn't|won't)\w*\b.{0,700}\bJonah\b",
        ),
    ),
    (
        "wrist_contact_and_charge",
        (
            r"\b(?:wrist|fingertips?)\b.{0,500}\b(?:touch|contact|pressure|jolt|heat|pulse)\w*\b",
            r"\b(?:touch|contact|pressure|jolt|heat|pulse)\w*\b.{0,500}\b(?:wrist|fingertips?)\b",
        ),
    ),
    (
        "mara_control",
        (
            r"\bMara\b.{0,900}\b(?:control|decoupl|changed? the (?:cue|channel|signal)|still point)\w*\b",
            r"\b(?:control|decoupl|cue[- ]channel|changed? the (?:cue|channel|signal)|still point)\w*\b.{0,900}\bMara\b",
        ),
    ),
    (
        "collapse_and_residual_mystery",
        (
            r"\b(?:accuracy|read|readings?|guesses?)\b.{0,700}\b(?:fell|fall|drop|collapse|failed|wrong|plummet|fray)\w*\b",
            r"\b(?:smaller.{0,80}mystery|mystery remained|something remained|still couldn't explain|residual)\b",
        ),
    ),
    (
        "accepts_fellowship_and_hook",
        (
            r"\b(?:accept|accepted|stay|staying|decision|decided)\w*\b.{0,700}\b(?:fellowship|tomorrow|Fulcrum|Jonah)\b",
            r"\b(?:fellowship|tomorrow)\b.{0,700}\b(?:accept|stay|decision|decided)\w*\b",
            r"\b(?:Fulcrum|Jonah)\b.{0,1200}\b(?:accept|stay|staying|decision|decided)\w*\b",
            r"\b(?:wasn't|was not) leaving\b.{0,500}\b(?:stay|staying)\w*\b",
        ),
    ),
)

PACING_MARKERS: Mapping[str, tuple[str, ...]] = {
    "arrival_and_hook": (r"\barriv", r"\bsuitcase\b", r"\bbakery box\b"),
    "fulcrum_enchantment": (r"\bFulcrum\b", r"\bcompound\b", r"\bbeautiful", r"\bredwood"),
    "livia_uncanny_reads": (r"\bLivia\b.{0,100}\bread", r"\bread\b.{0,100}\bLivia\b"),
    "wrist_contact_and_charge": (r"\bwrist\b", r"\berotic\b", r"\bjolt\b"),
    "mara_control": (r"\bcontrol\b", r"\bcue channel\b", r"\bchanges? the (?:channel|signal|cue)"),
    "collapse_and_residual_mystery": (r"\baccuracy\b.{0,100}\b(?:fall|fell|drop)", r"\bsmaller mystery\b", r"\bpartially collaps"),
    "jonah_recognition_and_hook": (r"\bJonah\b.{0,100}\b(?:recogn|underst|saw)", r"\baccept(?:s|ed)? the fellowship\b"),
}

EXPLICIT_PATTERNS: tuple[tuple[str, str], ...] = (
    ("genital_description", r"\b(?:penis|vagina|vulva|clitoris|labia|testicles?|scrotum|genitals?)\b"),
    ("graphic_sex_act", r"\b(?:penetrat(?:e|ed|ion)|oral sex|anal sex|masturbat(?:e|ed|ion)|orgasm(?:ed|ing)?|ejaculat(?:e|ed|ion))\b"),
    ("consummation", r"\b(?:consummat(?:e|ed|ion)|had sex|made love|slept together|came inside)\b"),
)

SENSORY_PATTERNS: Mapping[str, tuple[str, ...]] = {
    "sight": (r"\blook(?:ed|ing|s)?\b", r"\bsee\b", r"\bsaw\b", r"\blight\b", r"\bcolor\b"),
    "sound": (r"\bhear(?:d|ing)?\b", r"\bsound\b", r"\bvoice\b", r"\bwhisper", r"\blaugh"),
    "touch": (r"\btouch", r"\bwrist\b", r"\bskin\b", r"\bwarm", r"\bpressure\b"),
    "smell": (r"\bsmell", r"\bscent\b", r"\bfragrant", r"\bcedar\b"),
    "taste": (r"\btaste", r"\bsweet\b", r"\bsalt\b", r"\bcoffee\b", r"\btea\b"),
}

COGNITION_RE = re.compile(
    r"\b(?:thought|knew|felt|wondered|realized|wanted|remembered|noticed|understood|decided|feared|hoped)\b",
    re.IGNORECASE,
)
UNCERTAINTY_RE = re.compile(r"\b(?:maybe|perhaps|possibly|could|might|seemed|as if|or else|uncertain|didn't know)\b", re.IGNORECASE)
OBSERVATION_RE = re.compile(r"\b(?:saw|heard|felt|noticed|watched|observed|voice|posture|wrist|breath|gaze)\b", re.IGNORECASE)
MECHANISM_RE = re.compile(r"\b(?:cue|channel|signal|control|accuracy|test|changed|variable|partner)\b", re.IGNORECASE)

# These patterns are intentionally narrow.  They identify surface habits worth
# showing to an editor; they are not proof that a sentence is bad or
# machine-written.
CADENCE_FAMILIES: Mapping[str, tuple[str, ...]] = {
    "not_x_but_y": (
        r"\b(?:not|wasn't|weren't|isn't|aren't|didn't|doesn't)\b"
        r"[^.!?\n]{0,110}\bbut\b[^.!?\n]{1,110}",
    ),
    "felt_like": (r"\bfelt like\b", r"\bfeels like\b"),
    "profound": (r"\bprofound(?:ly)?\b",),
    "sudden": (r"\bsudden(?:ly)?\b",),
    "quiet": (r"\bquiet(?:ly)?\b",),
    "merely": (r"\bmerely\b",),
    "simply": (r"\bsimply\b",),
    "interpretive_coda": (
        r"\b(?:Mara|she)\s+(?:realized|understood|knew)\b",
        r"\b(?:Mara|she)\s+had\s+(?:found|learned|discovered)\b",
        r"\bfor the first time\b",
        r"\b(?:Mara|she)\s+(?:was|felt)\s+no longer\b",
    ),
}

QUOTE_RE = re.compile(r'“([^”\n]{2,})”|"([^"\n]{2,})"')
SPEECH_VERBS = (
    "said|asked|replied|answered|whispered|murmured|called|added|"
    "continued|observed|offered|told|insisted|admitted|suggested|"
    "warned|promised|joked"
)
SPEAKER_NAME = r"[A-Z][A-Za-z’'-]+(?:\s+[A-Z][A-Za-z’'-]+)?"
SPEAKER_BEFORE_RE = re.compile(
    rf"\b(?P<speaker>{SPEAKER_NAME})\s+(?:{SPEECH_VERBS})"
    r"(?:\s+[^\n“\"]{0,45})?[,:—-]?\s*$"
)
SPEAKER_AFTER_RE = re.compile(
    rf"^\s*[,.—-]?\s*(?P<speaker>{SPEAKER_NAME})\s+(?:{SPEECH_VERBS})\b"
)

DIALOGUE_STOPWORDS = {
    "and", "are", "but", "can", "could", "did", "does", "for", "from",
    "had", "has", "have", "her", "here", "him", "his", "how", "into",
    "its", "just", "not", "now", "our", "out", "she", "should", "that",
    "the", "their", "them", "then", "there", "they", "this", "was", "were",
    "what", "when", "where", "which", "who", "why", "will", "with", "would",
    "you", "your", "about", "because", "been", "being", "come", "don't",
    "get", "got", "i'm", "i've", "it's", "like", "me", "my", "no", "of",
    "on", "or", "so", "to", "up", "we", "yes",
}


def _record(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "to_dict"):
        result = value.to_dict()
        if isinstance(result, Mapping):
            return dict(result)
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    raise TypeError(f"Expected a mapping-like record, got {type(value).__name__}")


def load_rubric(path: str | Path | None = None) -> dict[str, Any]:
    """Load and validate the versioned rubric."""
    rubric_path = Path(path) if path else RUBRIC_PATH
    rubric = json.loads(rubric_path.read_text(encoding="utf-8"))
    axes = rubric.get("axes", {})
    if not axes or sum(float(axis["weight"]) for axis in axes.values()) != 100:
        raise ValueError("Rubric axes must exist and have weights summing to 100")
    required_anchors = {"0", "25", "50", "75", "100"}
    for name, axis in axes.items():
        if set(axis.get("anchors", {})) != required_anchors:
            raise ValueError(f"Rubric axis {name!r} must define 0/25/50/75/100 anchors")
    return rubric


def rubric_prompt(rubric: Mapping[str, Any] | None = None) -> str:
    """Render the judge-facing rubric and strict JSON response contract."""
    data = dict(rubric or load_rubric())
    chunks = [
        "Score the candidate independently on every axis from 0 to 100.",
        "Use the anchors, quote at least one exact passage per axis, and assign defect IDs only from the taxonomy.",
        "Do not reward prose quality on a fidelity axis. Return JSON only.",
        (
            "Calibrate strictly: 50 is a competent draft needing ordinary "
            "revision; 75 is strong publishable execution; 90 is rare and "
            "requires exceptional line- and scene-level control; 100 means no "
            "meaningful improvement is visible. Constraint compliance alone "
            "does not justify a high literary score."
        ),
    ]
    for name, axis in data["axes"].items():
        chunks.append(f"\n{name} (weight {axis['weight']}):")
        chunks.extend(f"- {criterion}" for criterion in axis["criteria"])
        chunks.extend(f"  {level}: {text}" for level, text in axis["anchors"].items())
    diagnostics = {
        **dict(data.get("romance_diagnostics", {})),
        **dict(data.get("intimacy_diagnostics", {})),
    }
    if diagnostics:
        chunks.append(
            "\nNon-weighted diagnostics (report the 4–6 most decision-relevant; "
            "a failed diagnostic is useful evidence, not an automatic gate):"
        )
        chunks.extend(f"- {name}: {description}" for name, description in diagnostics.items())
    profile_overlay = data.get("profile_overlay")
    if isinstance(profile_overlay, Mapping):
        chunks.append(
            "\nResolved creative-profile diagnostic overlay. These are "
            "evidence-backed scene obligations, not additional weighted axes:"
        )
        chunks.append(json.dumps(profile_overlay, ensure_ascii=False, sort_keys=True))
    chunks.append("\nAllowed defects: " + ", ".join(data["defect_taxonomy"]))
    chunks.append(
        '\nJSON: {"score_scale":"raw_0_100","rubric_scores":{"axis":0},'
        '"passage_evidence":{"axis":["exact quote"]},"defects":["defect_id"],'
        '"romance_diagnostics":{"diagnostic_id":{"passed":true,"evidence":"exact quote",'
        '"note":"brief reason"}},'
        '"summary":"brief editorial judgment"}'
    )
    return "\n".join(chunks)


def words(text: str) -> list[str]:
    return [token.lower().replace("’", "'") for token in WORD_RE.findall(text)]


def word_count(text: str) -> int:
    return len(words(text))


def _evidence_window(text: str, start: int, end: int, radius: int = 70) -> str:
    """Return compact, whitespace-normalized evidence around a match."""

    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return " ".join(text[left:right].split())


def cadence_family_diagnostics(text: str) -> dict[str, Any]:
    """Count a small set of inspectable prose-cadence families.

    The result is descriptive, not a quality score.  A ``not X but Y`` turn can
    be exactly right once and monotonous eight times; this function exposes the
    repetition and leaves that decision to an editor.
    """

    count = max(1, word_count(text))
    families: dict[str, Any] = {}
    total = 0
    for name, patterns in CADENCE_FAMILIES.items():
        matches: list[dict[str, Any]] = []
        occupied: list[tuple[int, int]] = []
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                # Multiple patterns in one family should not double-count the
                # same phrase if the family is extended later.
                span = match.span()
                if any(span[0] < old_end and old_start < span[1] for old_start, old_end in occupied):
                    continue
                occupied.append(span)
                matches.append(
                    {
                        "match": " ".join(match.group(0).split()),
                        "position": match.start(),
                        "evidence": _evidence_window(text, *span),
                    }
                )
        matches.sort(key=lambda item: item["position"])
        family_count = len(matches)
        total += family_count
        families[name] = {
            "count": family_count,
            "per_1000_words": round(family_count / count * 1000, 4),
            "evidence": matches[:8],
        }
    return {
        "heuristic": True,
        "interpretation": (
            "Surface-form repetition diagnostic only; occurrences are not "
            "automatically defects or evidence of model authorship."
        ),
        "word_count": word_count(text),
        "total_family_hits": total,
        "hits_per_1000_words": round(total / count * 1000, 4),
        "families": families,
    }


def _quoted_passages(text: str) -> list[dict[str, Any]]:
    passages: list[dict[str, Any]] = []
    for match in QUOTE_RE.finditer(text):
        quote = match.group(1) if match.group(1) is not None else match.group(2)
        passages.append({"text": quote, "start": match.start(), "end": match.end()})
    return passages


def explanatory_gloss_diagnostics(text: str) -> dict[str, Any]:
    """Estimate how often narration immediately explains quoted dialogue.

    This is deliberately a high-precision-ish cue detector, not semantic
    entailment.  It flags nearby phrases such as ``which meant`` or a narrated
    ``not X but Y`` restatement; an editor must decide whether the gloss is
    useful, redundant, ironic, or wrong.
    """

    passages = _quoted_passages(text)
    explicit_gloss = re.compile(
        r"\b(?:which (?:meant|was to say)|meaning|in other words|"
        r"the point was|what (?:she|he|they) (?:meant|was saying)|"
        r"(?:Mara|she|he|they) (?:understood|knew|realized))\b",
        re.IGNORECASE,
    )
    contrastive_recast = re.compile(
        r"\b(?:it|that|this)\s+(?:was|is|wasn't|isn't)\b"
        r"[^.!?\n]{0,100}\b(?:but|instead|really|merely|simply)\b",
        re.IGNORECASE,
    )
    hits: list[dict[str, Any]] = []
    for index, passage in enumerate(passages):
        next_start = passages[index + 1]["start"] if index + 1 < len(passages) else len(text)
        after_end = min(next_start, passage["end"] + 320)
        narration = text[passage["end"]:after_end]
        cue = explicit_gloss.search(narration) or contrastive_recast.search(narration)
        if not cue:
            continue
        quote_terms = {
            token for token in words(str(passage["text"]))
            if len(token) >= 4 and token not in DIALOGUE_STOPWORDS
        }
        narration_terms = {
            token for token in words(narration)
            if len(token) >= 4 and token not in DIALOGUE_STOPWORDS
        }
        hits.append(
            {
                "quote": str(passage["text"])[:180],
                "narration": " ".join(narration.split())[:260],
                "cue": cue.group(0),
                "shared_content_terms": sorted(quote_terms & narration_terms)[:12],
                "position": passage["start"],
            }
        )
    denominator = len(passages)
    return {
        "heuristic": True,
        "interpretation": (
            "Lexical cue diagnostic for immediate explanatory narration; it "
            "does not determine whether an explanation is artistically warranted."
        ),
        "quoted_passages": denominator,
        "possible_explanatory_glosses": len(hits),
        "glosses_per_100_dialogue_passages": round(
            len(hits) / denominator * 100, 4
        ) if denominator else 0.0,
        "evidence": hits[:12],
    }


def _speaker_for_passage(text: str, start: int, end: int) -> str | None:
    before = text[max(0, start - 140):start]
    after = text[end:min(len(text), end + 100)]
    before_match = SPEAKER_BEFORE_RE.search(before)
    if before_match:
        return before_match.group("speaker")
    after_match = SPEAKER_AFTER_RE.search(after)
    if after_match:
        return after_match.group("speaker")
    return None


def dialogue_voice_diagnostics(
    text: str,
    *,
    minimum_dialogue_words: int = 20,
    minimum_turns: int = 2,
) -> dict[str, Any]:
    """Compare surface dialogue vocabularies for explicitly attributed speakers.

    Attribution is intentionally conservative: unattributed alternating dialogue
    is omitted rather than guessed.  Vocabulary overlap can reveal a useful
    warning, but cannot measure syntax, worldview, subtext, or performance.
    """

    by_speaker: dict[str, list[str]] = defaultdict(list)
    turns: Counter[str] = Counter()
    unattributed = 0
    for passage in _quoted_passages(text):
        speaker = _speaker_for_passage(text, int(passage["start"]), int(passage["end"]))
        if not speaker:
            unattributed += 1
            continue
        turns[speaker] += 1
        by_speaker[speaker].extend(words(str(passage["text"])))

    sampled = {
        speaker: tokens
        for speaker, tokens in by_speaker.items()
        if len(tokens) >= minimum_dialogue_words and turns[speaker] >= minimum_turns
    }
    names = {
        token.lower()
        for speaker in by_speaker
        for token in words(speaker)
    }
    vocabularies = {
        speaker: {
            token for token in tokens
            if len(token) >= 3 and token not in DIALOGUE_STOPWORDS and token not in names
        }
        for speaker, tokens in sampled.items()
    }
    frequencies = {
        speaker: Counter(
            token for token in tokens
            if len(token) >= 3 and token not in names
        )
        for speaker, tokens in sampled.items()
    }
    pairwise: list[dict[str, Any]] = []
    speakers = sorted(vocabularies)
    for left_index, left in enumerate(speakers):
        left_vocab = vocabularies[left]
        for right in speakers[left_index + 1:]:
            right_vocab = vocabularies[right]
            shared = left_vocab & right_vocab
            smaller = min(len(left_vocab), len(right_vocab))
            vocabulary = set(frequencies[left]) | set(frequencies[right])
            dot = sum(frequencies[left][token] * frequencies[right][token] for token in vocabulary)
            left_norm = math.sqrt(sum(value * value for value in frequencies[left].values()))
            right_norm = math.sqrt(sum(value * value for value in frequencies[right].values()))
            cosine = dot / (left_norm * right_norm) if left_norm and right_norm else 0.0
            pairwise.append(
                {
                    "left": left,
                    "right": right,
                    "vocabulary_jaccard": round(_jaccard(left_vocab, right_vocab), 6),
                    "shared_over_smaller_vocabulary": round(
                        len(shared) / smaller, 6
                    ) if smaller else 0.0,
                    "unigram_frequency_cosine": round(cosine, 6),
                    "shared_terms": sorted(shared)[:20],
                }
            )
    overlap_values = [item["shared_over_smaller_vocabulary"] for item in pairwise]
    cosine_values = [item["unigram_frequency_cosine"] for item in pairwise]
    mean_overlap = mean(overlap_values) if overlap_values else None
    mean_cosine = mean(cosine_values) if cosine_values else None
    return {
        "heuristic": True,
        "interpretation": (
            "Surface vocabulary overlap among explicitly attributed, sufficiently "
            "sampled speakers. It omits unattributed speech and does not measure "
            "syntax, subtext, or character truth."
        ),
        "attributed_speakers": {
            speaker: {
                "turns": turns[speaker],
                "dialogue_words": len(tokens),
                "content_vocabulary_size": len(vocabularies.get(speaker, set())),
                "sufficiently_sampled": speaker in sampled,
            }
            for speaker, tokens in sorted(by_speaker.items())
        },
        "unattributed_passages": unattributed,
        "minimum_dialogue_words": minimum_dialogue_words,
        "minimum_turns": minimum_turns,
        "comparable_speaker_count": len(sampled),
        "pairwise": pairwise,
        "mean_shared_over_smaller_vocabulary": (
            round(mean_overlap, 6) if mean_overlap is not None else None
        ),
        "mean_unigram_frequency_cosine": (
            round(mean_cosine, 6) if mean_cosine is not None else None
        ),
        "possible_voice_indistinctness": (
            (mean_overlap >= 0.5 or (mean_cosine is not None and mean_cosine >= 0.8))
            if mean_overlap is not None else None
        ),
    }


def literary_style_diagnostics(text: str) -> dict[str, Any]:
    """Collect deterministic literary warnings without turning them into gates."""

    return {
        "heuristic": True,
        "interpretation": (
            "Editorial leads only. These diagnostics do not affect eligibility "
            "or claim to identify model-written prose."
        ),
        "cadence_families": cadence_family_diagnostics(text),
        "explanatory_gloss": explanatory_gloss_diagnostics(text),
        "dialogue_voice": dialogue_voice_diagnostics(text),
    }


def integrated_style_discontinuity_diagnostics(
    prefix_text: str,
    continuation_text: str,
    *,
    cadence_delta_threshold: float = 5.0,
    cadence_ratio_threshold: float = 2.0,
) -> dict[str, Any]:
    """Compare an immutable prefix with newly generated continuation prose.

    Continuation experiments often evaluate only the new text, correctly
    avoiding a shared-prefix confound during candidate selection.  Once a
    continuation is packaged as one story, however, a much weaker inherited
    prefix can create an audible author/style seam.  This report makes that
    sectional mismatch visible without turning a surface heuristic into a
    hard gate.
    """

    prefix = literary_style_diagnostics(prefix_text)
    continuation = literary_style_diagnostics(continuation_text)
    prefix_rate = float(prefix["cadence_families"]["hits_per_1000_words"])
    continuation_rate = float(
        continuation["cadence_families"]["hits_per_1000_words"]
    )
    higher = max(prefix_rate, continuation_rate)
    lower = min(prefix_rate, continuation_rate)
    delta = abs(prefix_rate - continuation_rate)
    ratio = None if lower == 0 else higher / lower
    ratio_exceeded = (
        higher > 0
        if ratio is None
        else ratio >= cadence_ratio_threshold
    )
    possible_discontinuity = (
        delta >= cadence_delta_threshold and ratio_exceeded
    )
    direction = "balanced"
    if prefix_rate > continuation_rate:
        direction = "prefix_higher"
    elif continuation_rate > prefix_rate:
        direction = "continuation_higher"
    return {
        "heuristic": True,
        "interpretation": (
            "Sectional surface-style comparison for editorial review only. "
            "A flag does not prove different authorship or poor prose, but a "
            "large same-POV shift should be read in the merged manuscript."
        ),
        "thresholds": {
            "cadence_delta_per_1000_words": cadence_delta_threshold,
            "cadence_rate_ratio": cadence_ratio_threshold,
        },
        "prefix": prefix,
        "continuation": continuation,
        "cadence_delta_per_1000_words": round(delta, 4),
        "cadence_rate_ratio": round(ratio, 4) if ratio is not None else None,
        "direction": direction,
        "possible_style_discontinuity": possible_discontinuity,
    }


def batch_literary_style_diagnostics(
    candidates: Sequence[Mapping[str, Any] | Any],
) -> dict[str, Any]:
    """Expose cadence convergence and per-candidate style warnings in a batch.

    Continuation records are compared on ``continuation_text`` so a shared,
    accepted prefix cannot manufacture a house-style finding.
    """

    records = [_record(candidate) for candidate in candidates]
    per_candidate: dict[str, Any] = {}
    family_totals: Counter[str] = Counter()
    family_candidates: dict[str, list[str]] = defaultdict(list)
    family_rates: dict[str, list[float]] = defaultdict(list)
    family_evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, record in enumerate(records):
        candidate_id = str(record.get("candidate_id", index))
        continuation = record.get("continuation_text", "")
        selected_text = (
            str(continuation)
            if isinstance(continuation, str) and continuation.strip()
            else str(record.get("text", ""))
        )
        diagnostics = literary_style_diagnostics(selected_text)
        cadence = diagnostics["cadence_families"]
        gloss = diagnostics["explanatory_gloss"]
        voice = diagnostics["dialogue_voice"]
        per_candidate[candidate_id] = {
            "cadence_total_hits": cadence["total_family_hits"],
            "cadence_hits_per_1000_words": cadence["hits_per_1000_words"],
            "cadence_family_counts": {
                name: values["count"]
                for name, values in cadence["families"].items()
            },
            "possible_explanatory_glosses": gloss["possible_explanatory_glosses"],
            "glosses_per_100_dialogue_passages": gloss[
                "glosses_per_100_dialogue_passages"
            ],
            "comparable_dialogue_speakers": voice["comparable_speaker_count"],
            "mean_dialogue_vocabulary_overlap": voice[
                "mean_shared_over_smaller_vocabulary"
            ],
            "mean_dialogue_unigram_cosine": voice[
                "mean_unigram_frequency_cosine"
            ],
            "possible_voice_indistinctness": voice[
                "possible_voice_indistinctness"
            ],
        }
        for family, values in diagnostics["cadence_families"]["families"].items():
            count = int(values["count"])
            family_totals[family] += count
            family_rates[family].append(float(values["per_1000_words"]))
            if count:
                family_candidates[family].append(candidate_id)
                for evidence in values["evidence"][:2]:
                    family_evidence[family].append(
                        {"candidate_id": candidate_id, **evidence}
                    )

    candidate_count = len(records)
    families: dict[str, Any] = {}
    for family in CADENCE_FAMILIES:
        affected = family_candidates[family]
        prevalence = len(affected) / candidate_count if candidate_count else 0.0
        total = family_totals[family]
        families[family] = {
            "total_count": total,
            "candidate_prevalence": round(prevalence, 6),
            "candidates_with_hits": affected,
            "mean_hits_per_1000_words": round(
                mean(family_rates[family]), 6
            ) if family_rates[family] else 0.0,
            "repeated_across_batch": (
                candidate_count >= 2 and prevalence >= 0.5 and total >= 2
            ),
            "evidence": family_evidence[family][:12],
        }
    return {
        "heuristic": True,
        "interpretation": (
            "Batch-level surface convergence diagnostic. Shared cadence can be "
            "intentional house style; the flag is a prompt for comparative reading."
        ),
        "candidate_count": candidate_count,
        "text_scope": "continuation_text_when_available_otherwise_text",
        "cadence_families": families,
        "per_candidate": per_candidate,
    }


def _first_pattern_position(text: str, patterns: Sequence[str]) -> tuple[int | None, str | None]:
    matches: list[tuple[int, str]] = []
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            matches.append((match.start(), match.group(0)[:160]))
    return min(matches, default=(None, None), key=lambda item: item[0] if item[0] is not None else math.inf)


def _extract_beat_markers(scene: Mapping[str, Any]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    configured = scene.get("beat_markers")
    if isinstance(configured, Mapping):
        return tuple((str(name), tuple(str(p) for p in patterns)) for name, patterns in configured.items())
    scene_id = str(scene.get("scene_id", "")).upper()
    if scene_id == "S01" or "calibration" in str(scene.get("title", "")).lower():
        return S01_BEAT_MARKERS
    beat_map = scene.get("beat_map", ())
    derived: list[tuple[str, tuple[str, ...]]] = []
    for index, beat in enumerate(beat_map):
        text = str(beat.get("text", beat.get("description", ""))) if isinstance(beat, Mapping) else str(beat)
        significant = [re.escape(token) for token in words(text) if len(token) >= 6][:4]
        derived.append((f"beat_{index + 1}", tuple(rf"\b{token}" for token in significant)))
    return tuple(derived)


def _gate(name: str, passed: bool, **details: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), **details}


def _word_count_gate(text: str, scene: Mapping[str, Any]) -> dict[str, Any]:
    count = word_count(text)
    minimum = int(scene.get("target_words_min", scene.get("word_count_min", 2800)))
    maximum = int(scene.get("target_words_max", scene.get("word_count_max", 3600)))
    tolerance = int(scene.get("word_count_diagnostic_tolerance", 200))
    if count < minimum:
        diagnostic = "slightly_short" if count >= minimum - tolerance else "materially_short"
    elif count > maximum:
        diagnostic = "slightly_long" if count <= maximum + tolerance else "materially_long"
    else:
        diagnostic = "in_range"
    return _gate(
        "word_count",
        minimum <= count <= maximum,
        count=count,
        target=[minimum, maximum],
        diagnostic=diagnostic,
    )


def _pov_gate(text: str, scene: Mapping[str, Any]) -> dict[str, Any]:
    pov = str(scene.get("pov", "Mara"))
    if pov.lower() not in {"mara", "mara vale", "mara with tightly limited witness inserts"}:
        return _gate("pov", True, pov=pov, diagnostic="unsupported_pov_not_mechanically_checked")
    suspicious: list[str] = []
    other_mind = re.compile(
        r"\b(?:Livia|Jonah|Adrian|Miriam)\b"
        r"(?:\s+\w+){0,3}\s+"
        r"(?:thought|knew|felt|wondered|realized|wanted|remembered|"
        r"understood|decided|feared|hoped)\b",
        re.IGNORECASE,
    )
    for paragraph in (p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()):
        if other_mind.search(paragraph) and not re.search(r'["“”]', paragraph):
            suspicious.append(" ".join(paragraph.split())[:240])
    limit = int(scene.get("max_suspicious_pov_paragraphs", 1))
    return _gate("pov", len(suspicious) <= limit, pov=pov, suspicious_paragraphs=suspicious[:6], threshold=limit)


def _beat_gate(text: str, scene: Mapping[str, Any]) -> dict[str, Any]:
    markers = _extract_beat_markers(scene)
    findings: list[dict[str, Any]] = []
    positions: list[int] = []
    cursor = 0
    for name, patterns in markers:
        relative_position, excerpt = _first_pattern_position(text[cursor:], patterns)
        position = cursor + relative_position if relative_position is not None else None
        findings.append(
            {
                "beat": name,
                "found": position is not None,
                "position": position,
                "fraction": round(position / max(1, len(text)), 4) if position is not None else None,
                "evidence": excerpt,
            }
        )
        if position is not None:
            positions.append(position)
            cursor = position + max(1, len(excerpt or ""))
    all_found = bool(markers) and all(item["found"] for item in findings)
    ordered = len(positions) == len(findings)
    return _gate("beat_order", all_found and ordered, all_found=all_found, ordered=ordered, beats=findings)


def _explicitness_gate(text: str) -> dict[str, Any]:
    hits: list[dict[str, str]] = []
    for label, pattern in EXPLICIT_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            hits.append({"category": label, "match": match.group(0), "context": text[max(0, match.start() - 45):match.end() + 45]})
    return _gate("heat_ceiling", not hits, matches=hits[:20])


def _epistemic_gate(text: str) -> dict[str, Any]:
    observations = len(OBSERVATION_RE.findall(text))
    uncertainty = len(UNCERTAINTY_RE.findall(text))
    mechanism = len(MECHANISM_RE.findall(text))
    passed = observations >= 3 and uncertainty >= 2 and mechanism >= 3
    return _gate(
        "epistemic_separation",
        passed,
        observation_markers=observations,
        uncertainty_markers=uncertainty,
        mechanism_markers=mechanism,
        thresholds={"observation": 3, "uncertainty": 2, "mechanism": 3},
    )


def _canon_gate(text: str, scene: Mapping[str, Any]) -> dict[str, Any]:
    contradictions: list[dict[str, str]] = []
    for character, locked_age in (("Mara", 22), ("Jonah", 24), ("Livia", 23)):
        age_pattern = rf"\b{character}(?:\s+\w+)?\b.{{0,24}}\b(\d{{1,2}})[- ]year[- ]old\b"
        for match in re.finditer(age_pattern, text, re.IGNORECASE):
            observed_age = int(match.group(1))
            if observed_age != locked_age:
                contradictions.append({"rule": f"{character.lower()}_age", "evidence": match.group(0)})
    checks: list[tuple[str, str]] = []
    configured = scene.get("forbidden_claims", ())
    if isinstance(configured, Mapping):
        checks.extend((str(label), str(pattern)) for label, pattern in configured.items())
    else:
        checks.extend((f"forbidden_{index}", str(pattern)) for index, pattern in enumerate(configured))
    for label, pattern in checks:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            contradictions.append({"rule": label, "evidence": match.group(0)})
    return _gate("locked_canon", not contradictions, contradictions=contradictions)


def _ngrams(tokens: Sequence[str], n: int) -> set[tuple[str, ...]]:
    if n <= 0 or len(tokens) < n:
        return set()
    return {tuple(tokens[index:index + n]) for index in range(len(tokens) - n + 1)}


def _longest_source_match(candidate_tokens: Sequence[str], source_tokens: Sequence[str], cap: int = 80) -> tuple[int, str]:
    if not candidate_tokens or not source_tokens:
        return 0, ""
    source_positions: dict[str, list[int]] = defaultdict(list)
    for index, token in enumerate(source_tokens):
        source_positions[token].append(index)
    best_length = 0
    best_start = 0
    for candidate_index, token in enumerate(candidate_tokens):
        for source_index in source_positions.get(token, ())[:64]:
            length = 0
            while (
                length < cap
                and candidate_index + length < len(candidate_tokens)
                and source_index + length < len(source_tokens)
                and candidate_tokens[candidate_index + length] == source_tokens[source_index + length]
            ):
                length += 1
            if length > best_length:
                best_length = length
                best_start = candidate_index
            if best_length >= cap:
                break
    return best_length, " ".join(candidate_tokens[best_start:best_start + best_length])


def _source_overlap_gate(text: str, source_texts: Sequence[str], scene: Mapping[str, Any]) -> dict[str, Any]:
    candidate_tokens = words(text)
    threshold = int(scene.get("max_exact_source_span_words", 18))
    ngram_threshold = float(scene.get("max_source_8gram_jaccard", 0.12))
    candidate_8 = _ngrams(candidate_tokens, 8)
    findings: list[dict[str, Any]] = []
    for index, source in enumerate(source_texts):
        source_tokens = words(str(source))
        length, excerpt = _longest_source_match(candidate_tokens, source_tokens)
        source_8 = _ngrams(source_tokens, 8)
        union = candidate_8 | source_8
        jaccard = len(candidate_8 & source_8) / len(union) if union else 0.0
        if length >= threshold or jaccard > ngram_threshold:
            findings.append(
                {
                    "source_index": index,
                    "longest_exact_span_words": length,
                    "exact_excerpt": excerpt,
                    "eight_gram_jaccard": round(jaccard, 6),
                }
            )
    return _gate(
        "source_overlap",
        not findings,
        suspicious_sources=findings,
        thresholds={"exact_span_words": threshold, "eight_gram_jaccard": ngram_threshold},
    )


def pacing_diagnostics(text: str, rubric: Mapping[str, Any] | None = None) -> dict[str, Any]:
    data = dict(rubric or load_rubric())
    targets = data.get("pacing_targets", ())
    diagnostics: dict[str, Any] = {}
    for target in targets:
        name = str(target["beat"])
        position, excerpt = _first_pattern_position(text, PACING_MARKERS.get(name, ()))
        fraction = position / max(1, len(text)) if position is not None else None
        within = fraction is not None and float(target["start"]) <= fraction <= float(target["end"])
        diagnostics[name] = {
            "found": position is not None,
            "within_target": within,
            "position_fraction": round(fraction, 4) if fraction is not None else None,
            "target": [target["start"], target["end"]],
            "evidence": excerpt,
        }
    return diagnostics


def romance_diagnostics(text: str, rubric: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return non-weighted, inspectable romance/intimacy craft diagnostics."""
    data = dict(rubric or load_rubric())
    lower = text.lower()
    sensory = {
        channel: sum(len(re.findall(pattern, text, re.IGNORECASE)) for pattern in patterns)
        for channel, patterns in SENSORY_PATTERNS.items()
    }
    active_senses = [channel for channel, count in sensory.items() if count]
    wrist = bool(re.search(r"\bwrist\b|\btouch|\bcontact\b", lower))
    control_after_contact = False
    contact_match = re.search(r"\bwrist\b|\btouch|\bcontact\b", lower)
    if contact_match:
        control_after_contact = bool(MECHANISM_RE.search(text[contact_match.end():]))
    attraction = bool(re.search(r"\b(?:attract|desir|want|heat|jolt|aware of (?:him|her)|beautiful|handsome)\w*\b", lower))
    impediment = bool(re.search(r"\b(?:refus|limit|not yet|couldn't|wouldn't|boundary|audience|pressure|obstacle)\w*\b", lower))
    dialogue = text.count('"') + text.count("“") >= 4
    future_delta = bool(re.search(r"\b(?:stay|fellowship|tomorrow|again|next|decision|accept)\w*\b", lower))
    restraint = bool(re.search(r"\b(?:wait|refus|restraint|did not|didn't|without taking|gave her room)\b", lower))
    competence = bool(re.search(r"\b(?:noticed|detected|control|accuracy|cue|channel|invented|tested)\b", lower))
    definitions = data.get("romance_diagnostics", {})

    def item(name: str, passed: bool | None, evidence: Any) -> dict[str, Any]:
        return {"passed": passed, "description": definitions.get(name, ""), "evidence": evidence}

    result = {
        "attraction_and_impediment": item("attraction_and_impediment", attraction and impediment, {"attraction": attraction, "impediment": impediment}),
        "relationship_delta": item("relationship_delta", future_delta and attraction, {"future_or_choice_marker": future_delta}),
        "competence_and_restraint": item("competence_and_restraint", competence and restraint, {"competence": competence, "restraint": restraint}),
        "romance_turn": item("romance_turn", attraction and impediment and future_delta, {"recognition": attraction, "impediment": impediment, "future_question": future_delta}),
        "trope_execution": item("trope_execution", None, "Requires comparative editorial judgment."),
        "character_before_mechanics": item("character_before_mechanics", None, "Requires editorial judgment of emphasis and consequence."),
        "selective_senses": item("selective_senses", len(active_senses) >= 3, {"active_channels": active_senses, "counts": sensory}),
        "dialogue_and_atmosphere": item("dialogue_and_atmosphere", dialogue and len(active_senses) >= 2, {"dialogue_present": dialogue, "active_channels": active_senses}),
        "contact_changes_story": item("contact_changes_story", wrist and control_after_contact, {"contact_present": wrist, "mechanism_after_contact": control_after_contact}),
        "pacing": pacing_diagnostics(text, data),
    }
    result["intimacy_craft"] = intimacy_craft_diagnostics(text, data)
    return result


def intimacy_craft_diagnostics(
    text: str, rubric: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Inspect transferable intimacy craft without pretending to replace an editor."""

    data = dict(rubric or load_rubric())
    definitions = data.get("intimacy_diagnostics", {})
    lower = text.casefold()
    sensory = {
        channel: sum(
            len(re.findall(pattern, text, re.IGNORECASE)) for pattern in patterns
        )
        for channel, patterns in SENSORY_PATTERNS.items()
    }
    active_senses = [channel for channel, count in sensory.items() if count]
    dialogue_turns = len(
        re.findall(r'(?:“[^”]{2,}”|"[^"\n]{2,}")', text, re.DOTALL)
    )
    body_actions = len(
        re.findall(
            r"\b(?:turned|moved|held|touched|watched|looked|stepped|"
            r"leaned|drew|lifted|lowered|offered|withdrew|released|"
            r"paused|smiled|laughed|flinched|breathed)\b",
            lower,
        )
    )
    emotional_markers = len(
        re.findall(
            r"\b(?:trust|fear|uncertain|curious|tender|anger|shame|"
            r"relief|delight|amused|vulnerab|hope|want|desir|attract|"
            r"recogn|respect|refus|freedom|choice)\w*\b",
            lower,
        )
    )
    atmosphere_markers = len(
        re.findall(
            r"\b(?:room|compound|redwood|window|door|table|fire|light|"
            r"shadow|air|night|heat|cold|cedar|tea|coffee|fabric|"
            r"crowd|watch|silence|music|wind|rain)\w*\b",
            lower,
        )
    )
    contact = re.search(r"\b(?:wrist|touch|contact|fingertip|pressure)\w*\b", lower)
    consequence = (
        bool(
            re.search(
                r"\b(?:know|underst|decid|choose|choice|trust|doubt|"
                r"control|signal|cue|stay|leave|again|tomorrow|fellowship|"
                r"recogn)\w*\b",
                text[contact.end() :] if contact else "",
                re.IGNORECASE,
            )
        )
        if contact
        else False
    )
    restraint = bool(
        re.search(
            r"\b(?:refus|wait|restraint|did not|didn't|without taking|"
            r"gave her room|stepped back|withdrew)\w*\b",
            lower,
        )
    )
    future_pressure = bool(
        re.search(
            r"\b(?:stay|leave|fellowship|tomorrow|again|next|decision|"
            r"decided|accept|question|possibil)\w*\b",
            lower,
        )
    )

    def item(name: str, passed: bool | None, evidence: Any) -> dict[str, Any]:
        return {
            "passed": passed,
            "description": definitions.get(name, ""),
            "evidence": evidence,
        }

    return {
        "emotional_transaction": item(
            "emotional_transaction",
            dialogue_turns >= 3 and emotional_markers >= 4 and future_pressure,
            {
                "dialogue_turns": dialogue_turns,
                "emotional_or_relational_markers": emotional_markers,
                "forward_consequence": future_pressure,
            },
        ),
        "character_specific_desire": item(
            "character_specific_desire",
            None,
            "Requires editorial judgment of attention and attraction filters.",
        ),
        "dialogue_body_counterpoint": item(
            "dialogue_body_counterpoint",
            dialogue_turns >= 3 and body_actions >= 6,
            {"dialogue_turns": dialogue_turns, "body_actions": body_actions},
        ),
        "sensory_triage": item(
            "sensory_triage",
            len(active_senses) >= 3,
            {"active_channels": active_senses, "counts": sensory},
        ),
        "atmospheric_participation": item(
            "atmospheric_participation",
            atmosphere_markers >= 5 and len(active_senses) >= 2,
            {
                "atmosphere_markers": atmosphere_markers,
                "active_channels": active_senses,
            },
        ),
        "consequential_contact": item(
            "consequential_contact",
            bool(contact) and consequence,
            {"contact_present": bool(contact), "consequence_after_contact": consequence},
        ),
        "productive_restraint": item(
            "productive_restraint",
            restraint and future_pressure,
            {"restraint_present": restraint, "forward_pressure": future_pressure},
        ),
        "distance_control": item(
            "distance_control",
            None,
            "Requires editorial judgment of emphasis, omission, and scene distance.",
        ),
        "physical_intelligibility": item(
            "physical_intelligibility",
            None,
            "Requires editorial judgment of spatial and bodily continuity.",
        ),
        "relationship_delta": item(
            "relationship_delta",
            consequence and future_pressure,
            {
                "contact_consequence": consequence,
                "forward_pressure": future_pressure,
            },
        ),
    }


def detect_defects(
    text: str,
    gate_details: Mapping[str, Mapping[str, Any]] | None = None,
    romance: Mapping[str, Any] | None = None,
) -> list[str]:
    defects: set[str] = set()
    gates = gate_details or {}
    romance_data = romance or {}
    if gates.get("pov", {}).get("passed") is False:
        defects.add("pov_drift")
    if gates.get("source_overlap", {}).get("passed") is False:
        defects.add("source_parroting")
    if gates.get("epistemic_separation", {}).get("passed") is False:
        if UNCERTAINTY_RE.search(text):
            defects.add("fake_ambiguity")
        else:
            defects.add("mindreading_inflation")
    body_phrases = re.findall(
        r"\b(?:her pulse (?:jumped|quickened)|her breath (?:caught|hitched)|heat (?:pooled|curled)|electric(?:ity)? (?:shot|ran)|she released a breath)\b",
        text,
        re.IGNORECASE,
    )
    if len(body_phrases) >= 4:
        defects.add("repetitive_body_shorthand")
    sermon_paragraphs = 0
    for paragraph in re.split(r"\n\s*\n", text):
        if word_count(paragraph) >= 120 and not re.search(r'["“”]', paragraph):
            abstract = len(re.findall(r"\b(?:truth|virtue|desire|freedom|responsibility|goodness|alignment|epistemic)\b", paragraph, re.IGNORECASE))
            action = len(re.findall(r"\b(?:walked|turned|touched|looked|said|asked|moved|held|watched)\b", paragraph, re.IGNORECASE))
            if abstract >= 5 and action <= 1:
                sermon_paragraphs += 1
    if sermon_paragraphs:
        defects.add("sermon_insertion")
    heat_change = romance_data.get("contact_changes_story", {})
    if heat_change and heat_change.get("passed") is False:
        if re.search(r"\b(?:attract|desir|heat|jolt|touch|wrist)\w*\b", text, re.IGNORECASE):
            defects.add("heat_without_consequence")
    craft = romance_data.get("intimacy_craft", {})
    if craft:
        atmosphere = craft.get("atmospheric_participation", {})
        if atmosphere.get("passed") is False:
            defects.add("atmospheric_vacuum")
        contact = craft.get("consequential_contact", {})
        if contact.get("evidence", {}).get("contact_present") and contact.get("passed") is False:
            defects.add("static_contact")
        counterpoint = craft.get("dialogue_body_counterpoint", {})
        counter_evidence = counterpoint.get("evidence", {})
        if (
            counterpoint.get("passed") is False
            and counter_evidence.get("dialogue_turns", 0) >= 8
            and counter_evidence.get("body_actions", 0) < 6
        ):
            defects.add("disembodied_dialogue")
        productive = craft.get("productive_restraint", {})
        if (
            productive.get("evidence", {}).get("restraint_present")
            and productive.get("passed") is False
        ):
            defects.add("restraint_without_tension")
        emotional = craft.get("emotional_transaction", {})
        emotional_evidence = emotional.get("evidence", {})
        arousal_markers = len(
            re.findall(
                r"\b(?:lust|arous|desir|heat|hunger|ache|electric|jolt)\w*\b",
                text,
                re.IGNORECASE,
            )
        )
        if (
            arousal_markers >= 5
            and emotional_evidence.get("emotional_or_relational_markers", 0) < 4
        ):
            defects.add("lust_as_emotion")
    euphemisms = re.findall(
        r"\b(?:aching core|secret place|tender petals?|womanly center|"
        r"velvet sheath|hard length|throbbing member|pearled nub)\b",
        text,
        re.IGNORECASE,
    )
    if euphemisms:
        defects.add("ornate_euphemism")
    for paragraph in re.split(r"\n\s*\n", text):
        body_nouns = re.findall(
            r"\b(?:eyes?|mouth|lips?|tongue|neck|shoulders?|chest|"
            r"breasts?|arms?|hands?|fingers?|waist|hips?|thighs?|"
            r"legs?|knees?|feet|skin|wrist)\b",
            paragraph,
            re.IGNORECASE,
        )
        if len(body_nouns) >= 14 and word_count(paragraph) <= 180:
            defects.add("clinical_inventory")
            break
    return sorted(defects)


def evaluate_candidate(
    candidate: Mapping[str, Any] | Any,
    scene_spec: Mapping[str, Any] | Any,
    source_texts: Sequence[str] | None = None,
    rubric: Mapping[str, Any] | None = None,
    resolved_profile: Mapping[str, Any] | Any | None = None,
) -> dict[str, Any]:
    """Run deterministic gates and diagnostics, returning a ScoreCard-shaped dict."""
    candidate_data = _record(candidate)
    scene = _record(scene_spec)
    text = str(candidate_data.get("text", ""))
    sources = [str(source) for source in (source_texts or ())]
    profile = _record(resolved_profile) if resolved_profile is not None else None
    gate_list = [
        _word_count_gate(text, scene),
        _pov_gate(text, scene),
        _beat_gate(text, scene),
        _canon_gate(text, scene),
        _explicitness_gate(text),
        _epistemic_gate(text),
        _source_overlap_gate(text, sources, scene),
    ]
    if profile is not None:
        expected_hash = str(profile.get("profile_hash", ""))
        observed_hash = str(candidate_data.get("resolved_profile_hash", ""))
        gate_list.append(
            _gate(
                "profile_provenance",
                bool(expected_hash) and observed_hash == expected_hash,
                expected_profile_hash=expected_hash,
                observed_profile_hash=observed_hash,
            )
        )
    gate_details = {gate["name"]: gate for gate in gate_list}
    gate_bools = {name: bool(detail["passed"]) for name, detail in gate_details.items()}
    romance = romance_diagnostics(text, rubric)
    literary = literary_style_diagnostics(text)
    defects = detect_defects(text, gate_details, romance)
    result = {
        "schema_version": "1.0",
        "candidate_id": str(candidate_data.get("candidate_id", candidate_data.get("id", ""))),
        "judge_id": "deterministic-v1",
        "label_order": [],
        "hard_gates": gate_bools,
        "gate_details": gate_details,
        "rubric_scores": {},
        "rubric_breakdown": {},
        "passage_evidence": {},
        "defects": defects,
        "romance_diagnostics": romance,
        "literary_diagnostics": literary,
        "total_score": 0.0,
        "eligible": all(gate_bools.values()),
        "text_sha256": sha256(text.encode("utf-8")).hexdigest(),
    }
    if profile is not None:
        result.update(
            {
                "ontology_version": str(profile.get("ontology_version", "")),
                "story_profile_id": str(profile.get("story_profile_id", "")),
                "scene_profile_id": str(profile.get("scene_profile_id", "")),
                "resolved_profile_hash": str(profile.get("profile_hash", "")),
            }
        )
        result["profile_diagnostics"] = {
            "required_coordinates": list(profile.get("required", ())),
            "preferred_coordinates": list(profile.get("preferred", ())),
            "heat_ceiling": profile.get("heat_ceiling", ""),
            "heat_target": profile.get("heat_target", ""),
            "relationship_result": profile.get("relationship_result", ""),
            "semantic_judgment_required": True,
        }
    return result


def _extract_json(raw: str) -> Mapping[str, Any]:
    cleaned = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.IGNORECASE | re.DOTALL)
    if fenced:
        cleaned = fenced.group(1)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Judge response contains no JSON object")
        value = json.loads(cleaned[start:end + 1])
    if not isinstance(value, Mapping):
        raise ValueError("Judge response must be a JSON object")
    return value


def _quote_is_supported(quote: str, candidate_text: str) -> bool:
    if not quote.strip() or not candidate_text:
        return False
    if quote in candidate_text:
        return True
    normalized_quote = " ".join(words(quote))
    normalized_text = " ".join(words(candidate_text))
    return len(normalized_quote.split()) >= 4 and normalized_quote in normalized_text


def parse_judge_payload(
    raw: str | Mapping[str, Any],
    candidate_id: str,
    judge_id: str,
    label_order: Sequence[str] = (),
    *,
    candidate_text: str = "",
    strict_evidence: bool = True,
    rubric: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Parse, validate, and weight an absolute rubric judgment."""
    payload = _extract_json(raw) if isinstance(raw, str) else dict(raw)
    data = dict(rubric or load_rubric())
    axes = data["axes"]
    supplied = payload.get("rubric_scores", payload.get("scores", {}))
    if not isinstance(supplied, Mapping):
        raise ValueError("rubric_scores must be an object")
    missing = set(axes) - set(supplied)
    unknown = set(supplied) - set(axes)
    if missing or unknown:
        raise ValueError(f"Rubric score axes mismatch; missing={sorted(missing)}, unknown={sorted(unknown)}")
    evidence = payload.get("passage_evidence", payload.get("evidence", {}))
    if not isinstance(evidence, Mapping):
        raise ValueError("passage_evidence must be an object")
    scale = str(payload.get("score_scale", "raw_0_100"))
    breakdown: dict[str, Any] = {}
    weighted: dict[str, float] = {}
    validated_evidence: dict[str, list[str]] = {}
    for name, axis in axes.items():
        score = float(supplied[name])
        weight = float(axis["weight"])
        if scale in {"weighted", "axis_points"}:
            if not 0 <= score <= weight:
                raise ValueError(f"Weighted score for {name} must be between 0 and {weight}")
            raw_score = score / weight * 100 if weight else 0
            weighted_score = score
        else:
            if not 0 <= score <= 100:
                raise ValueError(f"Raw score for {name} must be between 0 and 100")
            raw_score = score
            weighted_score = score / 100 * weight
        quotes_value = evidence.get(name, ())
        quotes = [str(quotes_value)] if isinstance(quotes_value, str) else [str(item) for item in quotes_value]
        if strict_evidence and not quotes:
            raise ValueError(f"Judge score for {name} has no passage evidence")
        if strict_evidence and candidate_text:
            unsupported = [quote for quote in quotes if not _quote_is_supported(quote, candidate_text)]
            if unsupported:
                raise ValueError(f"Evidence for {name} is not present in the candidate: {unsupported[0]!r}")
        validated_evidence[name] = quotes
        weighted[name] = round(weighted_score, 4)
        breakdown[name] = {"raw_0_100": round(raw_score, 4), "weighted_points": round(weighted_score, 4), "weight": weight}
    taxonomy = set(data.get("defect_taxonomy", {}))
    defects = [str(item) for item in payload.get("defects", ())]
    invalid_defects = sorted(set(defects) - taxonomy)
    if invalid_defects:
        raise ValueError(f"Unknown defect IDs: {invalid_defects}")
    diagnostic_payload = payload.get("romance_diagnostics", {})
    if diagnostic_payload and not isinstance(diagnostic_payload, Mapping):
        raise ValueError("romance_diagnostics must be an object")
    allowed_diagnostics = set(data.get("romance_diagnostics", {})) | set(
        data.get("intimacy_diagnostics", {})
    )
    validated_diagnostics: dict[str, Any] = {}
    for name, value in dict(diagnostic_payload).items():
        if name not in allowed_diagnostics:
            raise ValueError(f"Unknown romance/intimacy diagnostic ID: {name}")
        if not isinstance(value, Mapping):
            raise ValueError(f"Diagnostic {name} must be an object")
        passed = value.get("passed")
        if passed not in (True, False, None):
            raise ValueError(f"Diagnostic {name} passed must be true, false, or null")
        evidence_quote = str(value.get("evidence", ""))
        if strict_evidence and evidence_quote and candidate_text:
            if not _quote_is_supported(evidence_quote, candidate_text):
                raise ValueError(
                    f"Diagnostic evidence for {name} is not present in the candidate"
                )
        validated_diagnostics[str(name)] = {
            "passed": passed,
            "evidence": evidence_quote,
            "note": str(value.get("note", "")),
        }
    return {
        "schema_version": "1.0",
        "candidate_id": str(candidate_id),
        "judge_id": str(judge_id),
        "label_order": [str(item) for item in label_order],
        "hard_gates": {},
        "rubric_scores": weighted,
        "rubric_breakdown": breakdown,
        "passage_evidence": validated_evidence,
        "defects": sorted(set(defects)),
        "romance_diagnostics": validated_diagnostics,
        "total_score": round(sum(weighted.values()), 4),
        "eligible": True,
        "summary": str(payload.get("summary", "")),
    }


def merge_scorecards(deterministic: Mapping[str, Any], judged: Mapping[str, Any]) -> dict[str, Any]:
    """Combine mechanical gates with one validated editorial judgment."""
    result = dict(judged)
    result["hard_gates"] = dict(deterministic.get("hard_gates", {}))
    result["gate_details"] = dict(deterministic.get("gate_details", {}))
    result["eligible"] = all(result["hard_gates"].values()) and bool(judged.get("eligible", True))
    result["defects"] = sorted(set(deterministic.get("defects", ())) | set(judged.get("defects", ())))
    romance = dict(deterministic.get("romance_diagnostics", {}))
    romance.update(judged.get("romance_diagnostics", {}))
    result["romance_diagnostics"] = romance
    result["literary_diagnostics"] = dict(
        deterministic.get("literary_diagnostics", {})
    )
    result["text_sha256"] = deterministic.get("text_sha256", "")
    return result


def scorecard_wire_payload(score: Mapping[str, Any] | Any) -> dict[str, Any]:
    """Project a rich evaluation result onto the strict ``ScoreCard`` wire type."""
    record = _record(score)
    required = {
        "candidate_id",
        "judge_id",
        "label_order",
        "hard_gates",
        "rubric_scores",
        "passage_evidence",
        "defects",
        "romance_diagnostics",
        "total_score",
        "eligible",
    }
    missing = required - set(record)
    if missing:
        raise ValueError(f"Cannot form ScoreCard payload; missing={sorted(missing)}")
    try:
        from .schemas import SCHEMA_VERSION
    except ImportError:  # pragma: no cover - supports direct file execution
        SCHEMA_VERSION = "fiction-harness.v1"
    result = {
        "record_type": "ScoreCard",
        "candidate_id": str(record["candidate_id"]),
        "judge_id": str(record["judge_id"]),
        "label_order": [str(item) for item in record["label_order"]],
        "hard_gates": {str(key): bool(value) for key, value in dict(record["hard_gates"]).items()},
        "rubric_scores": {str(key): float(value) for key, value in dict(record["rubric_scores"]).items()},
        "passage_evidence": {
            str(key): [str(item) for item in value]
            for key, value in dict(record["passage_evidence"]).items()
        },
        "defects": [str(item) for item in record["defects"]],
        "romance_diagnostics": dict(record["romance_diagnostics"]),
        "total_score": float(record["total_score"]),
        "eligible": bool(record["eligible"]),
        "schema_version": SCHEMA_VERSION,
    }
    for key in (
        "ontology_version",
        "story_profile_id",
        "scene_profile_id",
        "resolved_profile_hash",
    ):
        if record.get(key):
            result[key] = str(record[key])
    return result


def pairwise_prompt(candidate_a: str, candidate_b: str, rubric: Mapping[str, Any] | None = None) -> str:
    data = dict(rubric or load_rubric())
    axis_names = ", ".join(data["axes"])
    priorities = data.get("pairwise_priorities", ())
    priority_text = (
        "\nDecision priorities:\n"
        + "\n".join(f"- {priority}" for priority in priorities)
        if priorities
        else ""
    )
    return (
        "Compare the two candidates blind. Judge character/story fidelity before line polish. "
        "Return JSON only. Ties are allowed when evidence is genuinely balanced. "
        "For evidence, copy 5–12 consecutive words character-for-character from "
        "each corresponding candidate. Never quote the dossier, paraphrase, "
        "splice passages, or use ellipses. Before returning, verify every evidence "
        "string by exact search in Candidate A or B respectively.\n"
        f"Axes: {axis_names}\n"
        f"{priority_text}\n"
        'JSON: {"winner":"A|B|TIE","confidence":0.0,"axis_winners":{"axis":"A|B|TIE"},'
        '"evidence":{"A":["exact quote"],"B":["exact quote"]},"defects":{"A":["defect_id"],"B":["defect_id"]},'
        '"reason":"brief comparative explanation"}\n\n'
        f"CANDIDATE A\n{candidate_a}\n\nCANDIDATE B\n{candidate_b}"
    )


def parse_pairwise_payload(
    raw: str | Mapping[str, Any],
    candidate_a_id: str,
    candidate_b_id: str,
    judge_id: str,
    *,
    order_reversed: bool = False,
) -> dict[str, Any]:
    payload = _extract_json(raw) if isinstance(raw, str) else dict(raw)
    winner = str(payload.get("winner", "")).upper()
    if winner not in {"A", "B", "TIE"}:
        raise ValueError("Pairwise winner must be A, B, or TIE")
    confidence = float(payload.get("confidence", 0.5))
    if not 0 <= confidence <= 1:
        raise ValueError("Pairwise confidence must be in [0, 1]")
    canonical = "tie"
    if winner == "A":
        canonical = str(candidate_a_id)
    elif winner == "B":
        canonical = str(candidate_b_id)
    return {
        "candidate_a_id": str(candidate_a_id),
        "candidate_b_id": str(candidate_b_id),
        "judge_id": str(judge_id),
        "label_order": [str(candidate_a_id), str(candidate_b_id)],
        "order_reversed": bool(order_reversed),
        "winner_label": winner,
        "winner_id": canonical,
        "confidence": confidence,
        "axis_winners": payload.get("axis_winners", {}),
        "evidence": payload.get("evidence", {}),
        "defects": payload.get("defects", {}),
        "reason": str(payload.get("reason", "")),
    }


def aggregate_pairwise(judgments: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate pairwise results, exposing order disagreements instead of hiding them."""
    points: Counter[str] = Counter()
    matches: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for judgment in judgments:
        a = str(judgment["candidate_a_id"])
        b = str(judgment["candidate_b_id"])
        key = tuple(sorted((a, b)))
        matches[key].append(judgment)
        winner = str(judgment.get("winner_id", "tie"))
        if winner == "tie":
            points[a] += 0.5
            points[b] += 0.5
        else:
            points[winner] += 1.0
            loser = b if winner == a else a
            points[loser] += 0.0
    disagreements: list[dict[str, Any]] = []
    for pair, pair_judgments in matches.items():
        winners = {str(item.get("winner_id", "tie")) for item in pair_judgments}
        if len(winners) > 1:
            disagreements.append({"pair": list(pair), "winners": sorted(winners), "judgment_count": len(pair_judgments)})
    ranking = sorted(points, key=lambda candidate_id: (-points[candidate_id], candidate_id))
    return {"points": dict(points), "ranking": ranking, "order_disagreements": disagreements, "pair_count": len(matches)}


def _jaccard(left: set[Any], right: set[Any]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def _trace_features(candidate: Mapping[str, Any], key: str) -> set[str]:
    values: list[Any] = []
    parent = candidate.get("parent_trace")
    lineage = candidate.get("lineage")
    for container in (parent, lineage):
        if isinstance(container, Mapping) and key in container:
            value = container[key]
            values.extend(value if isinstance(value, (list, tuple, set)) else [value])
    return {str(value).strip().lower() for value in values if str(value).strip()}


def diversity_report(candidates: Sequence[Mapping[str, Any] | Any]) -> dict[str, Any]:
    records = [_record(candidate) for candidate in candidates]
    tokenized = {
        str(record.get("candidate_id", index)): words(
            str(record.get("continuation_text", ""))
            if isinstance(record.get("continuation_text"), str)
            and str(record.get("continuation_text", "")).strip()
            else str(record.get("text", ""))
        )
        for index, record in enumerate(records)
    }
    pairs: list[dict[str, Any]] = []
    similarities_by_id: dict[str, list[float]] = defaultdict(list)
    for left_index, left in enumerate(records):
        left_id = str(left.get("candidate_id", left_index))
        left_tokens = tokenized[left_id]
        for right_index in range(left_index + 1, len(records)):
            right = records[right_index]
            right_id = str(right.get("candidate_id", right_index))
            right_tokens = tokenized[right_id]
            unigram = _jaccard(set(left_tokens), set(right_tokens))
            trigram = _jaccard(_ngrams(left_tokens, 3), _ngrams(right_tokens, 3))
            fivegram = _jaccard(_ngrams(left_tokens, 5), _ngrams(right_tokens, 5))
            opening = _jaccard(_ngrams(left_tokens[:120], 3), _ngrams(right_tokens[:120], 3))
            self_bleu_proxy = mean((trigram, fivegram))
            pairs.append(
                {
                    "left": left_id,
                    "right": right_id,
                    "unigram_jaccard": round(unigram, 6),
                    "trigram_jaccard": round(trigram, 6),
                    "fivegram_jaccard": round(fivegram, 6),
                    "opening_trigram_jaccard": round(opening, 6),
                    "self_bleu_proxy": round(self_bleu_proxy, 6),
                }
            )
            similarities_by_id[left_id].append(self_bleu_proxy)
            similarities_by_id[right_id].append(self_bleu_proxy)
    per_candidate = {
        candidate_id: {
            "mean_similarity": round(mean(values), 6) if values else 0.0,
            "diversity_contribution": round(1 - mean(values), 6) if values else 1.0,
        }
        for candidate_id, values in similarities_by_id.items()
    }
    for candidate_id in tokenized:
        per_candidate.setdefault(candidate_id, {"mean_similarity": 0.0, "diversity_contribution": 1.0})
    strategies = set()
    dialogue_acts = set()
    event_sequences = set()
    for record in records:
        strategies |= _trace_features(record, "strategy")
        dialogue_acts |= _trace_features(record, "dialogue_acts")
        event_sequences |= _trace_features(record, "event_sequence")
    return {
        "candidate_count": len(records),
        "text_scope": "continuation_text_when_available_otherwise_text",
        "pair_count": len(pairs),
        "pairs": pairs,
        "corpus": {
            "mean_self_bleu_proxy": round(mean(item["self_bleu_proxy"] for item in pairs), 6) if pairs else 0.0,
            "mean_opening_similarity": round(mean(item["opening_trigram_jaccard"] for item in pairs), 6) if pairs else 0.0,
            "unique_strategies": len(strategies),
            "unique_dialogue_acts": len(dialogue_acts),
            "unique_event_sequences": len(event_sequences),
        },
        "per_candidate": per_candidate,
        "literary_style_diagnostics": batch_literary_style_diagnostics(records),
    }


def _scorecard_records(scores: Sequence[Mapping[str, Any] | Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for score in scores:
        record = _record(score)
        grouped[str(record.get("candidate_id", ""))].append(record)
    return grouped


def rank_pipeline(
    candidates: Sequence[Mapping[str, Any] | Any],
    scores: Sequence[Mapping[str, Any] | Any],
    *,
    top_k: int = 4,
    diversity_weight: float = 5.0,
) -> dict[str, Any]:
    """Rank a pipeline by eligibility, calibrated score, then diversity contribution."""
    records = [_record(candidate) for candidate in candidates]
    grouped_scores = _scorecard_records(scores)
    diversity = diversity_report(records)
    ranking: list[dict[str, Any]] = []
    for index, candidate in enumerate(records):
        candidate_id = str(candidate.get("candidate_id", index))
        candidate_scores = grouped_scores.get(candidate_id, [])
        editorial_scores = [float(score.get("total_score", 0)) for score in candidate_scores if score.get("rubric_scores")]
        eligibility_votes = [bool(score.get("eligible", False)) for score in candidate_scores if score.get("hard_gates")]
        eligible = all(eligibility_votes) if eligibility_votes else False
        average_score = mean(editorial_scores) if editorial_scores else 0.0
        diversity_contribution = float(diversity["per_candidate"][candidate_id]["diversity_contribution"])
        selection_score = average_score + diversity_weight * diversity_contribution
        ranking.append(
            {
                "candidate_id": candidate_id,
                "eligible": eligible,
                "mean_editorial_score": round(average_score, 4),
                "judge_count": len(editorial_scores),
                "diversity_contribution": round(diversity_contribution, 6),
                "selection_score": round(selection_score, 4),
            }
        )
    ranking.sort(key=lambda item: (not item["eligible"], -item["selection_score"], item["candidate_id"]))
    eligible_ranking = [item for item in ranking if item["eligible"]]
    selected = eligible_ranking[:top_k]
    return {
        "ranking": ranking,
        "top_four": [item["candidate_id"] for item in selected],
        "winner": selected[0]["candidate_id"] if selected else None,
        "diversity": diversity,
        "selection_policy": {"top_k": top_k, "diversity_weight": diversity_weight, "ineligible_candidates_rank_last": True},
    }


def quality_diversity_frontier(
    candidates: Sequence[Mapping[str, Any] | Any],
    scores: Sequence[Mapping[str, Any] | Any],
) -> list[dict[str, Any]]:
    """Return the non-dominated quality/diversity candidates."""
    ranked = rank_pipeline(candidates, scores)["ranking"]
    eligible = [item for item in ranked if item["eligible"]]
    frontier: list[dict[str, Any]] = []
    for item in eligible:
        dominated = any(
            other["candidate_id"] != item["candidate_id"]
            and other["mean_editorial_score"] >= item["mean_editorial_score"]
            and other["diversity_contribution"] >= item["diversity_contribution"]
            and (
                other["mean_editorial_score"] > item["mean_editorial_score"]
                or other["diversity_contribution"] > item["diversity_contribution"]
            )
            for other in eligible
        )
        if not dominated:
            frontier.append(item)
    return sorted(frontier, key=lambda item: (-item["mean_editorial_score"], -item["diversity_contribution"]))


def stable_blind_order(candidate_ids: Iterable[str], seed: str | int) -> list[str]:
    """Shared deterministic shuffle helper for evaluation and appraisal."""
    ordered = sorted(str(candidate_id) for candidate_id in candidate_ids)
    random.Random(str(seed)).shuffle(ordered)
    return ordered
