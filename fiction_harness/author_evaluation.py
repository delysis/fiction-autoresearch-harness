"""Author-aware diagnostics that remain separate from the literary rubric."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
import re
from statistics import mean, pstdev
from typing import Any, Mapping, Sequence

from .anti_copy import normalized_words
from .author import ResolvedAuthorContext
from .author_schemas import AuthorProfile, OverlapReport
from .core import canonical_json_text


AUTHOR_EVALUATION_AXES = (
    "author_style_intensity",
    "content_canon_preservation",
    "naturalness_prose_quality",
    "romance_intimacy_effectiveness",
    "rgo_gabaldon_fulfillment",
    "story_coherence",
    "christian_transformation_coherence",
    "novelty",
)
AUTHOR_DEFECT_LABELS = frozenset(
    {
        "author_profile_generic",
        "author_surface_cosplay",
        "author_mechanism_missing",
        "content_drift",
        "canon_drift",
        "unnatural_control_artifact",
        "romance_engine_missing",
        "intimacy_craft_mismatch",
        "christian_transformation_detachable",
        "exact_source_overlap",
        "fuzzy_source_overlap",
        "semantic_source_overlap",
        "cross_candidate_collapse",
        "unsupported_evidence",
    }
)
FUNCTION_WORDS = (
    "a",
    "an",
    "and",
    "as",
    "at",
    "but",
    "by",
    "for",
    "from",
    "if",
    "in",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "was",
    "with",
)
SENTENCE_RE = re.compile(r"(?<=[.!?])(?:[\"”’']+)?\s+")
DIALOGUE_RE = re.compile(r"[“\"]([^”\"]+)[”\"]")


@dataclass(frozen=True, slots=True)
class AuthorJudgeResult:
    candidate_id: str
    judge_id: str
    scores: Mapping[str, float]
    evidence: Mapping[str, tuple[str, ...]]
    defects: tuple[str, ...]
    copy_suspicion: bool
    notes: str
    provenance: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        missing = set(AUTHOR_EVALUATION_AXES) - set(self.scores)
        unknown = set(self.scores) - set(AUTHOR_EVALUATION_AXES)
        if missing or unknown:
            raise ValueError(
                f"author judgment axes mismatch: missing={sorted(missing)}, "
                f"unknown={sorted(unknown)}"
            )
        for axis, value in self.scores.items():
            if not 0 <= float(value) <= 10:
                raise ValueError(f"{axis} must score between 0 and 10")
        invalid = set(self.defects) - AUTHOR_DEFECT_LABELS
        if invalid:
            raise ValueError(f"unknown author-evaluation defects: {sorted(invalid)}")

    @property
    def mean_score(self) -> float:
        return round(mean(float(value) for value in self.scores.values()), 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_type": "AuthorJudgeResult",
            "candidate_id": self.candidate_id,
            "judge_id": self.judge_id,
            "scores": dict(self.scores),
            "evidence": {
                axis: list(quotes) for axis, quotes in self.evidence.items()
            },
            "defects": list(self.defects),
            "copy_suspicion": self.copy_suspicion,
            "notes": self.notes,
            "mean_score": self.mean_score,
            "provenance": dict(self.provenance),
        }


def surface_style_metrics(text: str) -> dict[str, Any]:
    """Return transparent low-level diagnostics, not an authorship verdict."""

    words = normalized_words(text)
    sentences = [
        normalized_words(item)
        for item in SENTENCE_RE.split(text.strip())
        if normalized_words(item)
    ]
    paragraphs = [
        normalized_words(item)
        for item in re.split(r"\n\s*\n", text)
        if normalized_words(item)
    ]
    sentence_lengths = [len(item) for item in sentences]
    paragraph_lengths = [len(item) for item in paragraphs]
    dialogue_words = sum(
        len(normalized_words(match.group(1))) for match in DIALOGUE_RE.finditer(text)
    )
    total = max(1, len(words))
    word_counts = {word: words.count(word) for word in FUNCTION_WORDS}
    return {
        "word_count": len(words),
        "sentence_count": len(sentences),
        "mean_sentence_words": round(mean(sentence_lengths), 4)
        if sentence_lengths
        else 0.0,
        "sentence_length_stddev": round(pstdev(sentence_lengths), 4)
        if len(sentence_lengths) > 1
        else 0.0,
        "mean_paragraph_words": round(mean(paragraph_lengths), 4)
        if paragraph_lengths
        else 0.0,
        "dialogue_word_ratio": round(dialogue_words / total, 6),
        "semicolon_per_1000": round(text.count(";") / total * 1000, 4),
        "dash_per_1000": round(
            (text.count("—") + text.count("–")) / total * 1000, 4
        ),
        "question_per_1000": round(text.count("?") / total * 1000, 4),
        "exclamation_per_1000": round(text.count("!") / total * 1000, 4),
        "function_word_rates": {
            word: round(count / total, 6)
            for word, count in sorted(word_counts.items())
        },
    }


def distribution_diagnostics(
    text: str,
    profile: AuthorProfile,
) -> dict[str, Any]:
    """Compare declared numeric distributions without collapsing to one score."""

    observed = surface_style_metrics(text)
    comparisons: dict[str, Any] = {}
    for key, expected_value in sorted(profile.distributions.items()):
        if key not in observed or not isinstance(expected_value, Mapping):
            continue
        target = expected_value.get("mean")
        tolerance = expected_value.get("tolerance", expected_value.get("stddev"))
        if not isinstance(target, (int, float)) or not isinstance(
            tolerance, (int, float)
        ):
            continue
        actual = observed[key]
        if not isinstance(actual, (int, float)):
            continue
        scale = max(float(tolerance), 1e-9)
        z_distance = abs(float(actual) - float(target)) / scale
        comparisons[key] = {
            "observed": actual,
            "target": float(target),
            "tolerance": float(tolerance),
            "distance_in_tolerances": round(z_distance, 4),
            "within_tolerance": z_distance <= 1,
        }
    return {"observed": observed, "comparisons": comparisons}


def author_judge_prompt(
    *,
    candidate_id: str,
    candidate_text: str,
    author_context: ResolvedAuthorContext,
    creative_profile: Mapping[str, Any],
) -> str:
    """Build a derived-profile-only evidence judge prompt."""

    contract = {
        "axes": list(AUTHOR_EVALUATION_AXES),
        "score_range": "0-10 independently; do not compensate one axis with another",
        "evidence": (
            "For every axis, copy one or two contiguous 5-20-word passages "
            "character-for-character from the candidate."
        ),
        "defect_labels": sorted(AUTHOR_DEFECT_LABELS),
        "copy_rule": (
            "Do not claim copying from resemblance alone. Set copy_suspicion only "
            "for striking phrase or event-sequence resemblance; mechanical overlap "
            "results remain authoritative."
        ),
    }
    payload = {
        "candidate_id": candidate_id,
        "derived_author_profile": author_context.prompt_payload,
        "creative_profile": creative_profile,
        "contract": contract,
    }
    return (
        "Evaluate the new scene against the derived mechanisms. Distinguish "
        "mechanism fidelity from superficial diction, and author intensity from "
        "naturalness, canon preservation, and novelty. The source books are not "
        "available and must not be inferred or quoted. Return one JSON object with "
        "candidate_id, scores, evidence, defects, copy_suspicion, and notes.\n\n"
        f"CONTROL:\n{canonical_json_text(payload)}\n"
        f"CANDIDATE:\n{candidate_text}"
    )


def _extract_json_object(text: str) -> Mapping[str, Any]:
    cleaned = text.strip()
    fenced = re.search(
        r"```(?:json)?\s*(\{.*\})\s*```",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if fenced:
        cleaned = fenced.group(1)
    else:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start : end + 1]
    value = json.loads(cleaned)
    if not isinstance(value, Mapping):
        raise TypeError("author judge response must be a JSON object")
    return value


def parse_author_judgment(
    raw: str | Mapping[str, Any],
    *,
    candidate_id: str,
    candidate_text: str,
    judge_id: str,
    provenance: Mapping[str, str] | None = None,
) -> AuthorJudgeResult:
    payload = dict(raw) if isinstance(raw, Mapping) else dict(_extract_json_object(raw))
    if str(payload.get("candidate_id", candidate_id)) != candidate_id:
        raise ValueError("author judge returned the wrong candidate ID")
    raw_scores = payload.get("scores")
    raw_evidence = payload.get("evidence")
    if not isinstance(raw_scores, Mapping) or not isinstance(raw_evidence, Mapping):
        raise ValueError("author judge requires scores and evidence objects")
    evidence: dict[str, tuple[str, ...]] = {}
    for axis in AUTHOR_EVALUATION_AXES:
        values = raw_evidence.get(axis, ())
        if isinstance(values, str):
            values = (values,)
        if not isinstance(values, (list, tuple)) or not values:
            raise ValueError(f"missing passage evidence for {axis}")
        quotes = tuple(str(value) for value in values)
        if any(quote not in candidate_text for quote in quotes):
            raise ValueError(f"unsupported passage evidence for {axis}")
        evidence[axis] = quotes
    return AuthorJudgeResult(
        candidate_id=candidate_id,
        judge_id=judge_id,
        scores={axis: float(raw_scores[axis]) for axis in AUTHOR_EVALUATION_AXES},
        evidence=evidence,
        defects=tuple(str(item) for item in payload.get("defects", ())),
        copy_suspicion=bool(payload.get("copy_suspicion", False)),
        notes=str(payload.get("notes", "")),
        provenance=dict(provenance or {}),
    )


def novelty_diagnostics(report: OverlapReport) -> dict[str, Any]:
    return {
        "passed": not report.hard_fail and not report.unresolved_flags,
        "exact_match_count": len(report.exact_matches),
        "fuzzy_match_count": len(report.fuzzy_matches),
        "semantic_match_count": len(report.semantic_matches),
        "cross_candidate_match_count": len(report.cross_candidate_matches),
        "hard_fail": report.hard_fail,
        "unresolved_flags": report.unresolved_flags,
    }


def pareto_frontier(
    records: Sequence[Mapping[str, Any]],
    *,
    maximize: Sequence[str],
    minimize: Sequence[str] = (),
) -> tuple[Mapping[str, Any], ...]:
    """Return non-dominated records with deterministic ordering."""

    frontier: list[Mapping[str, Any]] = []
    for candidate in records:
        dominated = False
        for other in records:
            if other is candidate:
                continue
            no_worse = all(float(other[key]) >= float(candidate[key]) for key in maximize)
            no_worse = no_worse and all(
                float(other[key]) <= float(candidate[key]) for key in minimize
            )
            strictly_better = any(
                float(other[key]) > float(candidate[key]) for key in maximize
            ) or any(float(other[key]) < float(candidate[key]) for key in minimize)
            if no_worse and strictly_better:
                dominated = True
                break
        if not dominated:
            frontier.append(candidate)
    return tuple(
        sorted(
            frontier,
            key=lambda item: (
                -sum(float(item[key]) for key in maximize),
                sum(float(item[key]) for key in minimize),
                str(item.get("candidate_id", item.get("arm_id", ""))),
            ),
        )
    )
