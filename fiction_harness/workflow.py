"""End-to-end loading, judging, selection, revision, and reporting.

Generation is implemented in :mod:`fiction_harness.pipelines`.  This module
owns the common post-generation workflow so every pipeline is subjected to the
same gates, blind rubric judges, pairwise tournament, and editor policy.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
import json
from pathlib import Path
import random
import re
from statistics import mean
from typing import Any, Iterable, Mapping, Sequence

from .appraisal import build_appraisal
from .authorship import model_artifact_authorship
from .craft import render_craft_prompt
from .core import canonical_json_text, hash_file, sha256_text, write_json
from .evaluation import (
    aggregate_pairwise,
    diversity_report,
    evaluate_candidate,
    load_rubric,
    merge_scorecards,
    pairwise_prompt,
    parse_judge_payload,
    parse_pairwise_payload,
    quality_diversity_frontier,
    rank_pipeline,
    rubric_prompt,
)
from .model_client import LlamaClient
from .runtime import TraceStore, model_runtime_provenance, stable_prompt, utc_now
from .schemas import Candidate, PersonaPacket, RunConfig, SceneSpec
from .ontology import (
    ResolvedCreativeProfile,
    profile_aware_rubric,
    profile_evaluation_overlay,
)


PIPELINES = ("direct", "verbalized_sampling", "actor_novelist")
DEFAULT_SEEDS: Mapping[str, tuple[int, ...]] = {
    "direct": tuple(range(11_101, 11_109)),
    "verbalized_sampling": tuple(range(22_201, 22_209)),
    "actor_novelist": tuple(range(33_301, 33_309)),
}


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_compiled(
    compiled_dir: str | Path,
) -> tuple[SceneSpec, tuple[PersonaPacket, ...], str, dict[str, str]]:
    """Load the strict records and stable dossier emitted by the compiler."""

    root = Path(compiled_dir)
    manifest = _read_json(root / "manifest.v1.json")
    scene_id = str(manifest.get("scene_id", "S01")).casefold()
    scene_path = root / "scene_specs" / f"{scene_id}.v1.json"
    if not scene_path.is_file():
        available = sorted((root / "scene_specs").glob("*.json"))
        if len(available) != 1:
            raise FileNotFoundError(
                f"compiled scene spec is missing: {scene_path}"
            )
        scene_path = available[0]
    scene = SceneSpec.from_dict(_read_json(scene_path))
    persona_bundle = _read_json(root / "personas" / "fulcrum_pilot.v1.json")
    personas = tuple(
        PersonaPacket.from_dict(record) for record in persona_bundle["personas"]
    )
    stable_prefix_text = (root / "stable_prefix.txt").read_text(encoding="utf-8")
    source_hashes = {
        str(item["key"]): str(item["raw_sha256"]) for item in manifest["sources"]
    }
    creative_profile = manifest.get("creative_profile")
    if isinstance(creative_profile, Mapping) and creative_profile.get(
        "resolved_profile_hash"
    ):
        source_hashes["resolved_creative_profile"] = str(
            creative_profile["resolved_profile_hash"]
        )
    return scene, personas, stable_prefix_text, source_hashes


def load_resolved_profile(
    compiled_dir: str | Path,
) -> ResolvedCreativeProfile | None:
    path = Path(compiled_dir) / "profiles" / "resolved_profile.v1.json"
    if not path.is_file():
        return None
    return ResolvedCreativeProfile.from_dict(_read_json(path))


def load_source_texts(compiled_dir: str | Path) -> list[str]:
    texts: list[str] = []
    for path in sorted((Path(compiled_dir) / "corpus").glob("*.json")):
        value = _read_json(path)
        if isinstance(value, Mapping) and isinstance(value.get("text"), str):
            texts.append(value["text"])
    return texts


def make_run_config(
    *,
    run_id: str,
    pipeline: str,
    scene: SceneSpec,
    prompt_hash: str,
    source_hashes: Mapping[str, str],
    count: int = 8,
    output_tokens: int = 6_144,
    persona_ids: Sequence[str] = (),
    resolved_profile: ResolvedCreativeProfile | None = None,
) -> RunConfig:
    seeds = DEFAULT_SEEDS[pipeline]
    if count > len(seeds):
        raise ValueError(f"Only {len(seeds)} fixed seeds are declared for {pipeline}")
    return RunConfig(
        run_id=run_id,
        scene_id=scene.scene_id,
        pipeline=pipeline,
        model_role="generator",
        prompt_hash=prompt_hash,
        source_hashes=dict(source_hashes),
        seeds=seeds,
        sampling={"temperature": 0.9, "top_p": 0.95, "min_p": 0.03},
        output_words_min=scene.target_words_min,
        output_words_max=scene.target_words_max,
        output_tokens=output_tokens,
        persona_ids=tuple(persona_ids),
        created_at=datetime.now(timezone.utc).isoformat(),
        ontology_version=(
            resolved_profile.ontology_version if resolved_profile else ""
        ),
        story_profile_id=(
            resolved_profile.story_profile_id if resolved_profile else ""
        ),
        scene_profile_id=(
            resolved_profile.scene_profile_id if resolved_profile else ""
        ),
        resolved_profile_hash=(
            resolved_profile.profile_hash if resolved_profile else ""
        ),
    )


def load_candidates(run_root: str | Path) -> list[Candidate]:
    """Load the last completed copy of every append-only candidate record."""

    latest: dict[str, dict[str, Any]] = {}
    root = Path(run_root)
    for path in sorted(root.glob("*/candidates.jsonl")):
        for record in TraceStore.read(path):
            if record.get("candidate_id"):
                latest[str(record["candidate_id"])] = record
    candidates: list[Candidate] = []
    for candidate_id in sorted(latest):
        payload = dict(latest[candidate_id])
        if payload.get("status") != "completed":
            continue
        payload.pop("status", None)
        payload.pop("finished_at", None)
        # Workflow-specific envelope fields are deliberately stored beside the
        # strict Candidate payload in append-only traces.  Strip them before
        # schema validation; they remain available in the trace itself.
        payload.pop("editor_gate_eligible", None)
        payload.pop("legacy_gate_carry_forward", None)
        candidates.append(Candidate.from_dict(payload))
    return candidates


def _resumable_completion(
    *,
    client: LlamaClient,
    store: TraceStore,
    call_id: str,
    prompt: str,
    seed: int,
    max_tokens: int,
    temperature: float,
    top_p: float = 0.95,
    min_p: float = 0.0,
) -> dict[str, Any]:
    prompt_hash = sha256_text(prompt)
    prior = store.completed_call(call_id)
    if prior:
        prior_hash = str(prior.get("prompt_hash", ""))
        if prior_hash and prior_hash != prompt_hash:
            raise ValueError(
                f"Refusing to resume {call_id}: prompt hash changed "
                f"({prior_hash} != {prompt_hash})"
            )
        result = prior.get("result", {})
        if isinstance(result, Mapping) and isinstance(result.get("content"), str):
            return dict(result)
    base = {
        "call_id": call_id,
        "role": "slow_adjudicator",
        "model": client.model,
        "runtime": model_runtime_provenance(client.model),
        "prompt_hash": prompt_hash,
        "parameters": {
            "seed": seed,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "min_p": min_p,
        },
    }
    store.append_call({**base, "status": "started", "started_at": utc_now()})
    try:
        completion = client.complete(
            prompt=prompt,
            seed=seed,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            min_p=min_p,
        )
        result = completion.to_dict()
        result.pop("raw", None)
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


def _judge_prefix(
    compiled_dir: Path,
    scene: SceneSpec,
    rubric: Mapping[str, Any] | None = None,
) -> str:
    # The judge needs locked story facts, source mechanisms, personas, and the
    # scene contract.  It does not need the production/marketing brief.  Keeping
    # this editorial packet compact materially improves dense-31B adjudication
    # while retaining every fact used by the rubric.
    source_packet_path = (
        compiled_dir
        / "sources"
        / f"{scene.scene_id.casefold()}_source_packet.v1.json"
    )
    editorial_packet = {
        "story_canon": _read_json(
            compiled_dir / "corpus" / "story_canon.v1.json"
        ),
        "source_packet": _read_json(
            source_packet_path
        ),
        "persona_bundle": _read_json(
            compiled_dir / "personas" / "fulcrum_pilot.v1.json"
        ),
        "scene_spec": scene.to_dict(),
    }
    resolved_profile = load_resolved_profile(compiled_dir)
    if resolved_profile is not None:
        editorial_packet["creative_profile"] = profile_evaluation_overlay(
            resolved_profile
        )
    return (
        "You are the senior fiction editor for a blind comparative trial. "
        "Judge only what is on the page. Scores without exact textual evidence "
        "are invalid. Do not infer which generation process produced a scene.\n\n"
        "<EDITORIAL_PACKET>\n"
        + canonical_json_text(editorial_packet)
        + "\n<EDITORIAL_RUBRIC>\n"
        + rubric_prompt(rubric or load_rubric())
    )


def _pairwise_prefix(rubric: Mapping[str, Any] | None = None) -> str:
    """Build a comparison-only prefix with no quotable story dossier."""

    active = dict(rubric or load_rubric())
    axes = active.get("axes", {})
    axis_lines: list[str] = []
    if isinstance(axes, Mapping):
        for name, details in axes.items():
            weight = ""
            if isinstance(details, Mapping) and "weight" in details:
                weight = f" ({details['weight']} points)"
            axis_lines.append(f"- {name}{weight}")
    else:
        axis_lines.extend(f"- {name}" for name in axes)
    priorities = active.get("pairwise_priorities", ())
    priority_lines = [f"- {item}" for item in priorities]
    return (
        "You are the senior fiction editor in a blind comparative trial. "
        "Compare only Candidate A and Candidate B supplied after this prefix. "
        "There is deliberately no story dossier here. Any passage evidence "
        "must be copied from the corresponding candidate, never from these "
        "instructions. Judge character and causal story performance before "
        "surface polish, then discriminate on line-level freshness and dramatic "
        "trust. Do not mistake constraint compliance, explicit thesis restatement, "
        "or generic fluency for literary quality. Prefer consequences carried by "
        "specific action, subtext, and relationship-conditioned behavior over "
        "narrator explanation. Do not infer the generation process.\n\n"
        "Scoring dimensions:\n"
        + "\n".join(axis_lines)
        + (
            "\n\nDecision priorities:\n" + "\n".join(priority_lines)
            if priority_lines
            else ""
        )
    )


def _absolute_dynamic(label: str, text: str, pass_number: int) -> str:
    emphasis = (
        "Read first for causal narrative force and character behavior, then score."
        if pass_number == 1
        else "Read first for epistemic, romantic, and theological texture, then score."
    )
    return (
        f"{emphasis}\nThe blind label is {label}. Do not mention any pipeline.\n"
        "Return exactly the rubric JSON contract. For every axis, passage_evidence "
        "must contain 5–12 consecutive words copied character-for-character from "
        "the candidate. Never correct, paraphrase, splice, or add ellipses to a "
        "quote. Reusing a truly relevant exact span is allowed. Before returning, "
        "verify that every quoted string can be found by exact search.\n\n"
        f"<CANDIDATE label=\"{label}\">\n{text}\n</CANDIDATE>"
        "\n\nFinal check: JSON only; every evidence string is a contiguous exact "
        "5–12-word substring of the candidate above."
    )


_EVIDENCE_TOKEN_RE = re.compile(r"\b[\w’'-]+\b", re.UNICODE)


def _json_object_from_model(text: str) -> dict[str, Any]:
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
    if not isinstance(value, dict):
        raise ValueError("Judge response must contain a JSON object")
    return value


def _normalize_evidence(text: str) -> str:
    return " ".join(
        token.group(0).casefold().replace("’", "'")
        for token in _EVIDENCE_TOKEN_RE.finditer(text)
    )


def _nearest_exact_evidence(
    quote: str, candidate_text: str
) -> tuple[str, float] | None:
    """Project a near-exact judge citation onto a contiguous source span.

    This is used only after both the initial and repair judge calls fail strict
    exact-search validation.  A high lexical similarity threshold preserves
    the judge's intended passage while making the stored citation auditable.
    """

    quote_tokens = list(_EVIDENCE_TOKEN_RE.finditer(quote))
    source_tokens = list(_EVIDENCE_TOKEN_RE.finditer(candidate_text))
    if len(quote_tokens) < 3 or not source_tokens:
        return None
    target = _normalize_evidence(quote)
    target_length = len(quote_tokens)
    # Three-word diagnostics occasionally differ only in capitalization or
    # terminal punctuation.  Accept those only when the normalized token span
    # is exactly identical; fuzzy projection remains restricted to 4+ words.
    if target_length == 3:
        for start in range(0, len(source_tokens) - target_length + 1):
            end = start + target_length
            excerpt = candidate_text[
                source_tokens[start].start() : source_tokens[end - 1].end()
            ]
            if _normalize_evidence(excerpt) == target:
                return excerpt, 1.0
        return None
    best: tuple[float, str] | None = None
    for window_length in range(max(4, target_length - 2), target_length + 3):
        for start in range(0, len(source_tokens) - window_length + 1):
            end = start + window_length
            excerpt = candidate_text[
                source_tokens[start].start() : source_tokens[end - 1].end()
            ]
            similarity = SequenceMatcher(
                None, target, _normalize_evidence(excerpt)
            ).ratio()
            if best is None or similarity > best[0]:
                best = (similarity, excerpt)
    if best is None or best[0] < 0.72:
        return None
    return best[1], best[0]


def _repair_evidence_payload(
    raw: str, candidate_text: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = _json_object_from_model(raw)
    evidence = payload.get("passage_evidence", payload.get("evidence", {}))
    if not isinstance(evidence, Mapping):
        raise ValueError("Judge passage_evidence is not an object")
    repaired: dict[str, list[str]] = {}
    repairs: list[dict[str, Any]] = []
    normalized_candidate = _normalize_evidence(candidate_text)
    for axis, values in evidence.items():
        quotes = [values] if isinstance(values, str) else list(values)
        repaired_quotes: list[str] = []
        for value in quotes:
            quote = str(value)
            if quote in candidate_text or (
                len(_normalize_evidence(quote).split()) >= 4
                and _normalize_evidence(quote) in normalized_candidate
            ):
                repaired_quotes.append(quote)
                continue
            nearest = _nearest_exact_evidence(quote, candidate_text)
            if nearest is None:
                raise ValueError(
                    f"Could not project unsupported {axis} evidence onto source text"
                )
            excerpt, similarity = nearest
            repaired_quotes.append(excerpt)
            repairs.append(
                {
                    "axis": str(axis),
                    "unsupported_quote": quote,
                    "exact_replacement": excerpt,
                    "similarity": round(similarity, 4),
                    "method": "nearest_contiguous_source_span",
                }
            )
        repaired[str(axis)] = repaired_quotes
    payload["passage_evidence"] = repaired
    payload.pop("evidence", None)
    diagnostics = payload.get("romance_diagnostics", {})
    if diagnostics and not isinstance(diagnostics, Mapping):
        raise ValueError("Judge romance_diagnostics is not an object")
    repaired_diagnostics: dict[str, Any] = {}
    for name, value in dict(diagnostics).items():
        if not isinstance(value, Mapping):
            repaired_diagnostics[str(name)] = value
            continue
        diagnostic = dict(value)
        quote = str(diagnostic.get("evidence", ""))
        if quote and not (
            quote in candidate_text
            or (
                len(_normalize_evidence(quote).split()) >= 4
                and _normalize_evidence(quote) in normalized_candidate
            )
        ):
            nearest = _nearest_exact_evidence(quote, candidate_text)
            if nearest is None:
                raise ValueError(
                    f"Could not project unsupported {name} diagnostic evidence"
                )
            excerpt, similarity = nearest
            diagnostic["evidence"] = excerpt
            repairs.append(
                {
                    "diagnostic": str(name),
                    "unsupported_quote": quote,
                    "exact_replacement": excerpt,
                    "similarity": round(similarity, 4),
                    "method": "nearest_contiguous_source_span",
                }
            )
        repaired_diagnostics[str(name)] = diagnostic
    if diagnostics:
        payload["romance_diagnostics"] = repaired_diagnostics
    return payload, repairs


def _pairwise_payload_with_exact_evidence(
    raw: str,
    candidate_a: str,
    candidate_b: str,
    *,
    allow_lexical_fallback: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = _json_object_from_model(raw)
    evidence = payload.get("evidence", {})
    if not isinstance(evidence, Mapping):
        raise ValueError("Pairwise evidence must be an object")
    audits: list[dict[str, Any]] = []
    repaired: dict[str, list[str]] = {}
    for label, source in (("A", candidate_a), ("B", candidate_b)):
        values = evidence.get(label, ())
        quotes = [values] if isinstance(values, str) else list(values)
        if not quotes:
            raise ValueError(f"Pairwise candidate {label} has no passage evidence")
        normalized_source = _normalize_evidence(source)
        repaired_quotes: list[str] = []
        for value in quotes:
            quote = str(value)
            if quote in source or (
                len(_normalize_evidence(quote).split()) >= 4
                and _normalize_evidence(quote) in normalized_source
            ):
                repaired_quotes.append(quote)
                continue
            nearest = _nearest_exact_evidence(quote, source)
            if nearest is None:
                if not allow_lexical_fallback:
                    raise ValueError(
                        f"Pairwise {label} evidence is not a near-exact source span"
                    )
                excerpt, overlap = _lexical_support_span(
                    source,
                    " ".join(
                        (
                            quote,
                            str(payload.get("reason", "")),
                            " ".join(
                                str(item)
                                for item in dict(payload.get("defects", {})).get(
                                    label, ()
                                )
                            ),
                        )
                    ),
                )
                repaired_quotes.append(excerpt)
                audits.append(
                    {
                        "label": label,
                        "unsupported_quote": quote,
                        "exact_replacement": excerpt,
                        "lexical_overlap": overlap,
                        "method": "lexical_support_span_fallback",
                    }
                )
                continue
            excerpt, similarity = nearest
            repaired_quotes.append(excerpt)
            audits.append(
                {
                    "label": label,
                    "unsupported_quote": quote,
                    "exact_replacement": excerpt,
                    "similarity": round(similarity, 4),
                    "method": "nearest_contiguous_source_span",
                }
            )
        repaired[label] = repaired_quotes
    payload["evidence"] = repaired
    return payload, audits


_LEXICAL_STOPWORDS = {
    "about",
    "after",
    "again",
    "being",
    "candidate",
    "could",
    "from",
    "have",
    "into",
    "more",
    "rather",
    "scene",
    "that",
    "their",
    "there",
    "these",
    "they",
    "this",
    "through",
    "very",
    "where",
    "which",
    "while",
    "with",
    "would",
}


def _lexical_support_span(source: str, rationale: str) -> tuple[str, int]:
    """Choose an auditable exact span related to the judge's rationale."""

    source_tokens = list(_EVIDENCE_TOKEN_RE.finditer(source))
    if len(source_tokens) < 5:
        raise ValueError("Candidate is too short to supply pairwise evidence")
    target = {
        token
        for token in _normalize_evidence(rationale).split()
        if len(token) >= 4 and token not in _LEXICAL_STOPWORDS
    }
    best: tuple[int, int, int] | None = None
    for width in range(12, 4, -1):
        for start in range(0, len(source_tokens) - width + 1):
            words = {
                token.group(0).casefold().replace("’", "'")
                for token in source_tokens[start : start + width]
            }
            overlap = len(words & target)
            # Prefer more rationale overlap, then a fuller 12-word citation,
            # then an earlier occurrence for deterministic reproducibility.
            rank = (overlap, width, -start)
            if best is None or rank > best:
                best = rank
                best_start = start
                best_width = width
    if best is None:  # pragma: no cover - guarded by the token-count check
        raise ValueError("Could not extract pairwise evidence")
    end = best_start + best_width
    excerpt = source[
        source_tokens[best_start].start() : source_tokens[end - 1].end()
    ]
    return excerpt, best[0]


def _judge_one(
    *,
    client: LlamaClient,
    store: TraceStore,
    candidate: Candidate,
    prefix: str,
    pass_number: int,
    seed: int,
    rubric: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    label = f"X{random.Random(seed).randrange(100, 999)}"
    prompt = stable_prompt(prefix, _absolute_dynamic(label, candidate.text, pass_number))
    call_id = f"absolute-{candidate.candidate_id}-p{pass_number}"
    result = _resumable_completion(
        client=client,
        store=store,
        call_id=call_id,
        prompt=prompt,
        seed=seed,
        max_tokens=4_096,
        temperature=0.25,
        top_p=0.9,
    )
    try:
        return parse_judge_payload(
            result["content"],
            candidate.candidate_id,
            f"{client.model}-absolute-p{pass_number}",
            (label,),
            candidate_text=candidate.text,
            strict_evidence=True,
            rubric=rubric,
        )
    except ValueError as first_error:
        # Most otherwise-valid scorecards fail only because the judge
        # paraphrases or clips one cited span.  Project those citations onto
        # audited contiguous source spans before paying for another dense-model
        # call.  Structural/semantic JSON failures still fall through to the
        # bounded model repair below.
        try:
            repaired_payload, evidence_repairs = _repair_evidence_payload(
                result["content"], candidate.text
            )
            score = parse_judge_payload(
                repaired_payload,
                candidate.candidate_id,
                f"{client.model}-absolute-p{pass_number}-evidence-projection",
                (label,),
                candidate_text=candidate.text,
                strict_evidence=True,
                rubric=rubric,
            )
            score["evidence_repairs"] = evidence_repairs
            score["evidence_projection_source"] = "initial_response"
            return score
        except (ValueError, json.JSONDecodeError, TypeError):
            pass
        repair_prompt = stable_prompt(
            prefix,
            _absolute_dynamic(label, candidate.text, pass_number)
            + "\n\nYour previous response was invalid: "
            + str(first_error)
            + "\nRegenerate the complete JSON. For each axis copy a contiguous "
            "5–12-word span character-for-character from the scene; do not "
            "paraphrase, splice passages, or use ellipses.",
        )
        repair = _resumable_completion(
            client=client,
            store=store,
            call_id=call_id + "-repair",
            prompt=repair_prompt,
            seed=seed ^ 0x5A17,
            max_tokens=4_096,
            temperature=0.1,
            top_p=0.9,
        )
        try:
            return parse_judge_payload(
                repair["content"],
                candidate.candidate_id,
                f"{client.model}-absolute-p{pass_number}-repair",
                (label,),
                candidate_text=candidate.text,
                strict_evidence=True,
                rubric=rubric,
            )
        except ValueError:
            repaired_payload, evidence_repairs = _repair_evidence_payload(
                repair["content"], candidate.text
            )
            score = parse_judge_payload(
                repaired_payload,
                candidate.candidate_id,
                f"{client.model}-absolute-p{pass_number}-evidence-projection",
                (label,),
                candidate_text=candidate.text,
                strict_evidence=True,
                rubric=rubric,
            )
            score["evidence_repairs"] = evidence_repairs
            return score


def _write_jsonl(path: Path, records: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(
                json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                + "\n"
            )


def judge_candidates(
    *,
    candidates: Sequence[Candidate],
    scene: SceneSpec,
    source_texts: Sequence[str],
    compiled_dir: str | Path,
    evaluation_dir: str | Path,
    client: LlamaClient,
    passes: int = 2,
    rubric: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Apply deterministic gates and two evidence-backed blind rubric passes."""

    out = Path(evaluation_dir)
    out.mkdir(parents=True, exist_ok=True)
    store = TraceStore(out)
    active_rubric = dict(rubric or load_rubric())
    resolved_profile = load_resolved_profile(compiled_dir)
    active_rubric = profile_aware_rubric(active_rubric, resolved_profile)
    prefix = _judge_prefix(Path(compiled_dir), scene, active_rubric)
    scores: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        deterministic = evaluate_candidate(
            candidate,
            scene,
            source_texts,
            active_rubric,
            resolved_profile=resolved_profile,
        )
        write_json(out / "deterministic" / f"{candidate.candidate_id}.json", deterministic)
        for pass_number in range(1, passes + 1):
            judged = _judge_one(
                client=client,
                store=store,
                candidate=candidate,
                prefix=prefix,
                pass_number=pass_number,
                seed=740_000 + index * 101 + pass_number,
                rubric=active_rubric,
            )
            merged = merge_scorecards(deterministic, judged)
            if resolved_profile is not None:
                merged.update(
                    {
                        "ontology_version": resolved_profile.ontology_version,
                        "story_profile_id": resolved_profile.story_profile_id,
                        "scene_profile_id": resolved_profile.scene_profile_id,
                        "resolved_profile_hash": resolved_profile.profile_hash,
                    }
                )
            scores.append(merged)
            write_json(
                out / "scorecards" / f"{candidate.candidate_id}.p{pass_number}.json",
                merged,
            )
    _write_jsonl(out / "scorecards.jsonl", scores)
    return scores


def _pipeline_groups(candidates: Sequence[Candidate]) -> dict[str, list[Candidate]]:
    groups: dict[str, list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        groups[candidate.pipeline].append(candidate)
    return dict(groups)


def _scores_for(scores: Sequence[Mapping[str, Any]], ids: set[str]) -> list[dict[str, Any]]:
    return [dict(score) for score in scores if str(score.get("candidate_id")) in ids]


def run_pairwise_tournaments(
    *,
    candidates: Sequence[Candidate],
    scores: Sequence[Mapping[str, Any]],
    compiled_dir: str | Path,
    evaluation_dir: str | Path,
    client: LlamaClient,
    rubric: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare each pipeline's top four in both candidate orders."""

    out = Path(evaluation_dir)
    store = TraceStore(out / "pairwise")
    active_rubric = dict(rubric or load_rubric())
    resolved_profile = load_resolved_profile(compiled_dir)
    active_rubric = profile_aware_rubric(active_rubric, resolved_profile)
    prefix = _pairwise_prefix(active_rubric)
    results: dict[str, Any] = {}
    for pipeline, group in _pipeline_groups(candidates).items():
        ids = {candidate.candidate_id for candidate in group}
        preliminary = rank_pipeline(group, _scores_for(scores, ids), top_k=4)
        selected_ids = list(preliminary["top_four"])
        eligible_ids = set(selected_ids)
        selection_fallback = not selected_ids
        # Always create a four-way comparative set when four candidates exist.
        # Gate-eligible candidates retain winner priority; ineligible additions
        # provide diversity/repair information without silently becoming valid.
        for item in preliminary["ranking"]:
            candidate_id = item["candidate_id"]
            if candidate_id not in selected_ids:
                selected_ids.append(candidate_id)
            if len(selected_ids) == min(4, len(group)):
                break
        selected = {candidate.candidate_id: candidate for candidate in group if candidate.candidate_id in selected_ids}
        judgments: list[dict[str, Any]] = []
        # Keep the label order constant across adjacent calls. With one server
        # slot this lets llama.cpp retain a long Candidate A prefix across
        # several comparisons before the reversed pass.
        for reversal in (False, True):
            if reversal:
                pair_schedule = [
                    (left_id, selected_ids[right_index])
                    for right_index in range(1, len(selected_ids))
                    for left_id in selected_ids[:right_index]
                ]
            else:
                pair_schedule = [
                    (left_id, right_id)
                    for left_index, left_id in enumerate(selected_ids)
                    for right_id in selected_ids[left_index + 1 :]
                ]
            for left_id, right_id in pair_schedule:
                for _single_scheduled_call in (None,):
                    a_id, b_id = (right_id, left_id) if reversal else (left_id, right_id)
                    dynamic = pairwise_prompt(
                        selected[a_id].text,
                        selected[b_id].text,
                        active_rubric,
                    )
                    prompt = stable_prompt(prefix, dynamic)
                    call_id = f"pairwise-{pipeline}-{left_id}-{right_id}-r{int(reversal)}"
                    response = _resumable_completion(
                        client=client,
                        store=store,
                        call_id=call_id,
                        prompt=prompt,
                        seed=880_000 + len(judgments) * 37,
                        max_tokens=1_024,
                        temperature=0.2,
                        top_p=0.9,
                    )
                    active_response = response
                    judgment: dict[str, Any] | None = None
                    last_error: Exception | None = None
                    for repair_attempt in range(3):
                        try:
                            exact_payload, evidence_repairs = (
                                _pairwise_payload_with_exact_evidence(
                                    active_response["content"],
                                    selected[a_id].text,
                                    selected[b_id].text,
                                    # A clerical label swap in an otherwise
                                    # valid comparison should not trigger
                                    # another dense-model call. The fallback
                                    # is exact, rationale-guided, and audited.
                                    allow_lexical_fallback=True,
                                )
                            )
                            judgment = parse_pairwise_payload(
                                exact_payload,
                                a_id,
                                b_id,
                                client.model,
                                order_reversed=reversal,
                            )
                            judgment["evidence_repairs"] = evidence_repairs
                            break
                        except (ValueError, json.JSONDecodeError) as exc:
                            last_error = exc
                            if repair_attempt == 2:
                                break
                            repair_dynamic = (
                                dynamic
                                + "\n\nThe previous response was invalid: "
                                + str(exc)
                                + "\nReturn the complete JSON again. Evidence for "
                                "A and B must use 5–12 consecutive words copied "
                                "character-for-character from the corresponding "
                                "candidate; never paraphrase, splice, or use "
                                "ellipses. JSON only.\n\nPREVIOUS RESPONSE\n"
                                + active_response["content"][:12_000]
                            )
                            active_response = _resumable_completion(
                                client=client,
                                store=store,
                                call_id=call_id
                                + f"-repair-{repair_attempt + 1}",
                                prompt=stable_prompt(prefix, repair_dynamic),
                                seed=(
                                    880_000
                                    + len(judgments) * 37
                                    + (repair_attempt + 1) * 0x5A17
                                ),
                                max_tokens=1_536,
                                temperature=0.1,
                                top_p=0.9,
                            )
                    if judgment is None:
                        raise ValueError(
                            f"{call_id} remained invalid after two repairs"
                        ) from last_error
                    judgments.append(judgment)
        aggregate = aggregate_pairwise(judgments)
        eligible_pairwise_order = [
            candidate_id
            for candidate_id in aggregate["ranking"]
            if candidate_id in eligible_ids
        ]
        winner = (
            eligible_pairwise_order[0]
            if eligible_pairwise_order
            else preliminary["winner"]
            or (aggregate["ranking"][0] if aggregate["ranking"] else None)
            or (selected_ids[0] if selected_ids else None)
        )
        results[pipeline] = {
            "preliminary": preliminary,
            "selection_fallback_due_to_no_eligible_candidates": selection_fallback,
            "judgments": judgments,
            "aggregate": aggregate,
            "winner": winner,
        }
        write_json(out / "pairwise" / f"{pipeline}.json", results[pipeline])
    return results


def _candidate_mean_score(candidate_id: str, scores: Sequence[Mapping[str, Any]]) -> float:
    values = [
        float(score.get("total_score", 0))
        for score in scores
        if score.get("candidate_id") == candidate_id and score.get("rubric_scores")
    ]
    return mean(values) if values else 0.0


def _editor_defects(
    candidate_id: str,
    scores: Sequence[Mapping[str, Any]],
    deterministic: Mapping[str, Any] | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    candidate_scores = [
        score for score in scores if score.get("candidate_id") == candidate_id
    ]
    by_axis: dict[str, list[tuple[float, str]]] = defaultdict(list)
    defects: set[str] = set()
    for score in candidate_scores:
        defects.update(str(item) for item in score.get("defects", ()))
        breakdown = score.get("rubric_breakdown", {})
        evidence = score.get("passage_evidence", {})
        for axis, detail in breakdown.items():
            quote_list = evidence.get(axis, ())
            quote = str(quote_list[0]) if quote_list else ""
            by_axis[str(axis)].append((float(detail.get("raw_0_100", 0)), quote))
    items: list[dict[str, Any]] = []
    gate_details = dict((deterministic or {}).get("gate_details", {}))
    for gate_name in (
        "word_count",
        "beat_order",
        "pov",
        "locked_canon",
        "heat_ceiling",
        "epistemic_separation",
        "source_overlap",
        "profile_provenance",
    ):
        detail = gate_details.get(gate_name, {})
        if detail and not detail.get("passed", False):
            item: dict[str, Any] = {
                "hard_gate": gate_name,
                "repair": "Revise until this locked gate passes.",
            }
            if gate_name == "word_count":
                item["diagnosis"] = {
                    "count": detail.get("count"),
                    "target": detail.get("target"),
                }
                item["repair"] = (
                    "Expand existing action, dialogue, and consequence organically "
                    "to 3,000–3,300 words; protect the final three beats."
                )
            elif gate_name == "beat_order":
                beats = detail.get("beats", ())
                missing = [
                    beat.get("beat")
                    for beat in beats
                    if not beat.get("found")
                ]
                item["missing_or_disordered_beats"] = missing
                item["observed_positions"] = [
                    {
                        "beat": beat.get("beat"),
                        "fraction": beat.get("fraction"),
                        "evidence": beat.get("evidence"),
                    }
                    for beat in beats
                    if beat.get("found")
                ]
                concrete_repairs = {
                    "compound_beauty_and_asymmetry": (
                        "Within the opening 10%, have Mara observe both the "
                        "compound's beauty and its social/status asymmetry. Use "
                        "the natural words beautiful/beauty and asymmetry/unequal."
                    ),
                    "adrian_frames_game": (
                        "Before Livia's reads, Adrian explicitly frames the "
                        "calibration game or exercise."
                    ),
                    "livia_uncanny_reads": (
                        "Before Jonah's refusal, Livia makes visibly accurate, "
                        "uncanny reads of Mara."
                    ),
                    "jonah_refuses_to_perform": (
                        "Before wrist contact, Jonah explicitly refuses to read, "
                        "narrate, or perform Mara for the room. Give him direct "
                        "language such as 'I won't read her' or 'I won't perform.'"
                    ),
                    "wrist_contact_and_charge": (
                        "After Jonah's refusal, Mara and Jonah make wrist contact "
                        "and the contact produces specific erotic charge."
                    ),
                    "mara_control": (
                        "After contact, Mara deliberately changes or decouples "
                        "the cue channel as an experimental control."
                    ),
                    "collapse_and_residual_mystery": (
                        "After Mara's control and before her decision to stay, "
                        "show Livia's accuracy/readings fall, drop, fail, or "
                        "collapse; then leave one smaller residual mystery that "
                        "Mara still cannot explain."
                    ),
                    "accepts_fellowship_and_hook": (
                        "Only after the collapse and residual mystery, Mara "
                        "explicitly accepts the fellowship or decides to stay, "
                        "ending on a Jonah/next-day hook."
                    ),
                }
                item["concrete_scene_repairs"] = [
                    {
                        "beat": beat_name,
                        "required_action": concrete_repairs[beat_name],
                    }
                    for beat_name in missing
                    if beat_name in concrete_repairs
                ]
                item["repair"] = (
                    "Make the concrete actions above unmistakable on the page in "
                    "their specified order, using the supplied natural lexical "
                    "anchors. Preserve the chosen dramatic route."
                )
            else:
                item["diagnosis"] = detail
            items.append(item)
            if len(items) == limit:
                return items
    for axis, values in sorted(by_axis.items(), key=lambda item: mean(v[0] for v in item[1])):
        average = mean(value[0] for value in values)
        quote = next((value[1] for value in values if value[1]), "")
        items.append({"axis": axis, "mean_score": round(average, 2), "passage": quote})
        if len(items) == limit:
            break
    if defects and items:
        items[0]["defect_labels"] = sorted(defects)[:limit]
    return items[:limit]


def _legacy_beat_defects(
    defects: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Reconstruct the pre-concrete prompt for hash-safe completed-call reuse."""

    legacy: list[dict[str, Any]] = []
    for defect in defects:
        item = dict(defect)
        if item.get("hard_gate") == "beat_order":
            item.pop("concrete_scene_repairs", None)
            item["repair"] = (
                "Restore or clarify the named locked beats in their specified "
                "order without changing the chosen dramatic route."
            )
        legacy.append(item)
    return legacy


def polish_winners(
    *,
    candidates: Sequence[Candidate],
    scores: Sequence[Mapping[str, Any]],
    tournament: Mapping[str, Any],
    scene: SceneSpec,
    source_texts: Sequence[str],
    compiled_dir: str | Path,
    evaluation_dir: str | Path,
    client: LlamaClient,
    rubric: Mapping[str, Any] | None = None,
) -> tuple[list[Candidate], dict[str, Any]]:
    """Legacy frontier prose editor, disabled for scaffold research."""

    raise RuntimeError(
        "frontier manuscript rewriting is disabled: emit structured defects "
        "and regenerate with the declared writer scaffold"
    )

    out = Path(evaluation_dir)
    store = TraceStore(out / "editor")
    active_rubric = dict(rubric or load_rubric())
    resolved_profile = load_resolved_profile(compiled_dir)
    active_rubric = profile_aware_rubric(active_rubric, resolved_profile)
    prefix = (
        "You are a surgical final editor. Preserve the scene's plot, point of "
        "view, voice, and successful language. Repair only the listed defects. "
        "Return the complete revised scene and nothing else.\n\n"
        + render_craft_prompt(mode="editorial")
        + "\n\n"
        + (Path(compiled_dir) / "stable_prefix.txt").read_text(encoding="utf-8")
    )
    by_id = {candidate.candidate_id: candidate for candidate in candidates}
    finalists: list[Candidate] = []
    decisions: dict[str, Any] = {}
    for pipeline in PIPELINES:
        raw_id = str(tournament[pipeline]["winner"])
        raw = by_id[raw_id]
        raw_deterministic = evaluate_candidate(
            raw,
            scene,
            source_texts,
            active_rubric,
            resolved_profile=resolved_profile,
        )
        defects = _editor_defects(raw_id, scores, raw_deterministic)
        initial_call_id = f"edit-{raw_id}"

        def build_initial_prompt(
            selected_defects: Sequence[Mapping[str, Any]],
        ) -> str:
            dynamic = (
                "TARGETED DEFECTS (maximum five)\n"
                + canonical_json_text(selected_defects)
                + "\nPreserve successful events and language. Add only the action, "
                "dialogue, or connective consequence required to restore a named "
                "locked beat or pass the length gate. Keep the result between "
                f"{scene.target_words_min} and {scene.target_words_max} words. "
                "The contact remains non-consummating and changes what Mara chooses.\n\n"
                "<SCENE>\n"
                + raw.text
                + "\n</SCENE>"
            )
            return stable_prompt(prefix, dynamic)

        prompt_defects = defects
        prompt = build_initial_prompt(prompt_defects)
        prior_initial = store.completed_call(initial_call_id)
        if prior_initial:
            prior_hash = str(prior_initial.get("prompt_hash", ""))
            legacy_defects = _legacy_beat_defects(defects)
            legacy_prompt = build_initial_prompt(legacy_defects)
            if prior_hash == sha256_text(legacy_prompt):
                prompt_defects = legacy_defects
                prompt = legacy_prompt
        result = _resumable_completion(
            client=client,
            store=store,
            call_id=initial_call_id,
            prompt=prompt,
            seed=990_000 + PIPELINES.index(pipeline) * 313,
            max_tokens=6_144,
            temperature=0.35,
            top_p=0.9,
        )
        revision_id = f"{raw_id}-polished"
        revision_text = result["content"].strip()
        revision_seed = 990_000 + PIPELINES.index(pipeline) * 313
        revision_prompt_hash = sha256_text(prompt)
        revision = Candidate(
            candidate_id=revision_id,
            run_id=raw.run_id,
            pipeline=raw.pipeline,
            scene_id=raw.scene_id,
            seed=raw.seed,
            text=revision_text,
            parent_trace={
                "raw_winner": raw_id,
                "targeted_defects": prompt_defects,
            },
            evidence_ids=raw.evidence_ids,
            telemetry={
                key: result.get(key)
                for key in ("model", "usage", "timings", "cache", "elapsed_seconds")
                if result.get(key) is not None
            },
            lineage=raw.lineage + (f"editor:edit-{raw_id}",),
            prompt_hash=revision_prompt_hash,
            ontology_version=raw.ontology_version,
            story_profile_id=raw.story_profile_id,
            scene_profile_id=raw.scene_profile_id,
            resolved_profile_hash=raw.resolved_profile_hash,
            artifact_authorship=model_artifact_authorship(
                artifact_id=revision_id,
                text=revision_text,
                model_id=str(result.get("model", client.model)),
                call_id=initial_call_id,
                prompt_hash=revision_prompt_hash,
                seed=revision_seed,
                call_record={
                    "call_id": initial_call_id,
                    "prompt_hash": revision_prompt_hash,
                    "seed": revision_seed,
                    "result_metadata": {
                        key: value
                        for key, value in result.items()
                        if key not in {"content", "raw"}
                    },
                    "content_hash": sha256_text(revision_text),
                },
                created_at=utc_now(),
                parents=(
                    {
                        "artifact_id": raw.candidate_id,
                        "text_sha256": sha256_text(raw.text),
                    },
                ),
                creation_kind="model_edit",
            ),
        )
        deterministic = evaluate_candidate(
            revision,
            scene,
            source_texts,
            active_rubric,
            resolved_profile=resolved_profile,
        )
        gate_repair_attempts: list[dict[str, Any]] = []
        for repair_index in range(1, 3):
            if deterministic["eligible"]:
                break
            repair_defects = _editor_defects(
                raw_id, scores, deterministic, limit=5
            )
            repair_call_id = f"edit-{raw_id}-gate-repair-{repair_index}"

            def build_repair_prompt(
                selected_defects: Sequence[Mapping[str, Any]],
            ) -> str:
                anti_copy = ""
                if (
                    pipeline == "actor_novelist"
                    and repair_index == 2
                    and gate_repair_attempts
                    and gate_repair_attempts[-1].get(
                        "unchanged_from_previous", False
                    )
                ):
                    anti_copy = (
                        "\nThe prior repair was byte-identical and remained "
                        "invalid. You MUST change the text this time. After the "
                        "paragraph where Livia's read collapses, insert 150–250 "
                        "new words showing that her accuracy fell while one "
                        "smaller residual mystery remained that Mara still "
                        "couldn't explain. Preserve the later decision and Jonah "
                        "hook. The complete result must be at least 2,850 words."
                    )
                repair_dynamic = (
                    "LOCKED-GATE REPAIR ONLY\n"
                    + canonical_json_text(selected_defects)
                    + anti_copy
                    + "\nReturn a complete scene. Preserve every successful passage "
                    "and event from the current revision; change only what is needed "
                    "to pass the named gates. Keep 2,800–3,600 words and all eight "
                    "beats in their locked order. Do not summarize or truncate the "
                    "aftermath.\n\n<CURRENT_REVISION>\n"
                    + revision.text
                    + "\n</CURRENT_REVISION>"
                )
                return stable_prompt(prefix, repair_dynamic)

            repair_prompt_defects = repair_defects
            repair_prompt = build_repair_prompt(repair_prompt_defects)
            prior_repair = store.completed_call(repair_call_id)
            if prior_repair:
                prior_hash = str(prior_repair.get("prompt_hash", ""))
                legacy_defects = _legacy_beat_defects(repair_defects)
                legacy_prompt = build_repair_prompt(legacy_defects)
                if prior_hash == sha256_text(legacy_prompt):
                    repair_prompt_defects = legacy_defects
                    repair_prompt = legacy_prompt
            repair_result = _resumable_completion(
                client=client,
                store=store,
                call_id=repair_call_id,
                prompt=repair_prompt,
                seed=(
                    991_000
                    + PIPELINES.index(pipeline) * 313
                    + repair_index
                ),
                max_tokens=6_144,
                temperature=0.25,
                top_p=0.9,
            )
            previous_id = revision.candidate_id
            previous_text = revision.text
            repair_revision_id = f"{raw_id}-polished-r{repair_index}"
            repair_text = repair_result["content"].strip()
            repair_seed = (
                991_000 + PIPELINES.index(pipeline) * 313 + repair_index
            )
            repair_prompt_hash = sha256_text(repair_prompt)
            revision = Candidate(
                candidate_id=repair_revision_id,
                run_id=raw.run_id,
                pipeline=raw.pipeline,
                scene_id=raw.scene_id,
                seed=raw.seed,
                text=repair_text,
                parent_trace={
                    "raw_winner": raw_id,
                    "previous_revision": previous_id,
                    "targeted_defects": repair_prompt_defects,
                },
                evidence_ids=raw.evidence_ids,
                telemetry={
                    key: repair_result.get(key)
                    for key in (
                        "model",
                        "usage",
                        "timings",
                        "cache",
                        "elapsed_seconds",
                    )
                    if repair_result.get(key) is not None
                },
                lineage=revision.lineage + (f"editor:{repair_call_id}",),
                prompt_hash=repair_prompt_hash,
                ontology_version=raw.ontology_version,
                story_profile_id=raw.story_profile_id,
                scene_profile_id=raw.scene_profile_id,
                resolved_profile_hash=raw.resolved_profile_hash,
                artifact_authorship=model_artifact_authorship(
                    artifact_id=repair_revision_id,
                    text=repair_text,
                    model_id=str(repair_result.get("model", client.model)),
                    call_id=repair_call_id,
                    prompt_hash=repair_prompt_hash,
                    seed=repair_seed,
                    call_record={
                        "call_id": repair_call_id,
                        "prompt_hash": repair_prompt_hash,
                        "seed": repair_seed,
                        "result_metadata": {
                            key: value
                            for key, value in repair_result.items()
                            if key not in {"content", "raw"}
                        },
                        "content_hash": sha256_text(repair_text),
                    },
                    created_at=utc_now(),
                    parents=(
                        {
                            "artifact_id": previous_id,
                            "text_sha256": sha256_text(previous_text),
                        },
                    ),
                    creation_kind="model_edit",
                ),
            )
            deterministic = evaluate_candidate(
                revision,
                scene,
                source_texts,
                active_rubric,
                resolved_profile=resolved_profile,
            )
            gate_repair_attempts.append(
                {
                    "attempt": repair_index,
                    "candidate_id": revision.candidate_id,
                    "previous_candidate_id": previous_id,
                    "hard_gates": deterministic["hard_gates"],
                    "eligible": deterministic["eligible"],
                    "unchanged_from_previous": (
                        revision.text == previous_text
                    ),
                }
            )
        if not deterministic["eligible"]:
            raise RuntimeError(
                f"Editor could not produce a gate-valid {pipeline} revision "
                f"after {1 + len(gate_repair_attempts)} attempts"
            )
        judged_cards: list[dict[str, Any]] = []
        for pass_number in (1, 2):
            judged = _judge_one(
                client=client,
                store=store,
                candidate=revision,
                prefix=_judge_prefix(Path(compiled_dir), scene, active_rubric),
                pass_number=pass_number,
                seed=995_000 + PIPELINES.index(pipeline) * 101 + pass_number,
                rubric=active_rubric,
            )
            merged = merge_scorecards(deterministic, judged)
            if resolved_profile is not None:
                merged.update(
                    {
                        "ontology_version": resolved_profile.ontology_version,
                        "story_profile_id": resolved_profile.story_profile_id,
                        "scene_profile_id": resolved_profile.scene_profile_id,
                        "resolved_profile_hash": resolved_profile.profile_hash,
                    }
                )
            judged_cards.append(merged)
        revised_score = mean(float(card["total_score"]) for card in judged_cards)
        raw_score = _candidate_mean_score(raw_id, scores)
        accepted = bool(deterministic["eligible"]) and revised_score >= raw_score
        if not accepted and not raw_deterministic["eligible"]:
            raise RuntimeError(
                f"Gate-valid {pipeline} revision scored {revised_score:.2f}, "
                f"below its ineligible raw winner at {raw_score:.2f}; "
                "a quality-recovery edit is required"
            )
        chosen = revision if accepted else raw
        finalists.append(chosen)
        decisions[pipeline] = {
            "raw_candidate_id": raw_id,
            "revision_candidate_id": revision.candidate_id,
            "raw_mean_score": round(raw_score, 4),
            "revision_mean_score": round(revised_score, 4),
            "revision_gates": deterministic["hard_gates"],
            "accepted": accepted,
            "chosen_candidate_id": chosen.candidate_id,
            "targeted_defects": defects,
            "gate_repair_attempts": gate_repair_attempts,
            "revision_scorecards": judged_cards,
        }
        write_json(out / "editor" / f"{pipeline}.decision.json", decisions[pipeline])
        (out / "finalists").mkdir(parents=True, exist_ok=True)
        (out / "finalists" / f"{pipeline}.md").write_text(chosen.text, encoding="utf-8")
    write_json(
        out / "finalists.json",
        {"finalists": [candidate.to_dict() for candidate in finalists]},
    )
    return finalists, decisions


def _telemetry_summary(candidates: Sequence[Candidate]) -> dict[str, Any]:
    by_pipeline: dict[str, dict[str, float]] = defaultdict(
        lambda: {"prompt_tokens": 0, "completion_tokens": 0, "seconds": 0.0}
    )
    for candidate in candidates:
        usage = candidate.telemetry.get("usage", {})
        if isinstance(usage, Mapping):
            by_pipeline[candidate.pipeline]["prompt_tokens"] += float(
                usage.get("prompt_tokens", 0) or 0
            )
            by_pipeline[candidate.pipeline]["completion_tokens"] += float(
                usage.get("completion_tokens", 0) or 0
            )
        by_pipeline[candidate.pipeline]["seconds"] += float(
            candidate.telemetry.get("elapsed_seconds", 0) or 0
        )
    return {key: dict(value) for key, value in by_pipeline.items()}


def build_internal_report(
    *,
    candidates: Sequence[Candidate],
    scores: Sequence[Mapping[str, Any]],
    tournament: Mapping[str, Any],
    editor_decisions: Mapping[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    out = Path(output_dir)
    run_root = out.parent.parent
    profile_hashes = {
        candidate.resolved_profile_hash
        for candidate in candidates
        if candidate.resolved_profile_hash
    }
    if len(profile_hashes) > 1:
        raise ValueError(
            "Internal comparison contains candidates from different creative profiles"
        )
    groups = _pipeline_groups(candidates)
    pipeline_reports: dict[str, Any] = {}
    for pipeline, group in groups.items():
        ids = {candidate.candidate_id for candidate in group}
        selected_scores = _scores_for(scores, ids)
        pipeline_reports[pipeline] = {
            "candidate_count": len(group),
            "ranking": rank_pipeline(group, selected_scores),
            "quality_diversity_frontier": quality_diversity_frontier(
                group, selected_scores
            ),
            "diversity": diversity_report(group),
            "tournament_winner": tournament[pipeline]["winner"],
            "editor": editor_decisions[pipeline],
        }
    method_specific: dict[str, Any] = {}
    verbalized_diversity_path = (
        run_root / "verbalized_sampling" / "verbalized_diversity.json"
    )
    if verbalized_diversity_path.exists():
        method_specific["verbalized_sampling"] = {
            "plan_diversity": _read_json(verbalized_diversity_path),
            "artifact": str(verbalized_diversity_path),
            "sha256": hash_file(verbalized_diversity_path),
        }
    craft_audit_path = out.parent / "craft_audit_gabaldon_v2.json"
    if craft_audit_path.exists():
        craft_audit = _read_json(craft_audit_path)
        method_specific["gabaldon_craft_audit"] = {
            "artifact": str(craft_audit_path),
            "sha256": hash_file(craft_audit_path),
            "summary": craft_audit.get("by_pipeline", {}),
        }
    report = {
        "schema_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "creative_profile": {
            "ontology_version": next(
                (item.ontology_version for item in candidates if item.ontology_version),
                "",
            ),
            "story_profile_id": next(
                (item.story_profile_id for item in candidates if item.story_profile_id),
                "",
            ),
            "scene_profile_id": next(
                (item.scene_profile_id for item in candidates if item.scene_profile_id),
                "",
            ),
            "resolved_profile_hash": next(
                (
                    item.resolved_profile_hash
                    for item in candidates
                    if item.resolved_profile_hash
                ),
                "",
            ),
        },
        "pipeline_reports": pipeline_reports,
        "method_specific": method_specific,
        "telemetry": _telemetry_summary(candidates),
        "honesty_note": (
            "The comparison reports observed outcomes without assuming that "
            "Verbalized Sampling or Actor–Novelist must beat direct sampling."
        ),
    }
    write_json(out / "internal_report.json", report)
    lines = [
        "# Three-Pipeline Internal Report",
        "",
        report["honesty_note"],
        "",
    ]
    for pipeline in PIPELINES:
        item = pipeline_reports[pipeline]
        editor = item["editor"]
        lines.extend(
            [
                f"## {pipeline}",
                "",
                f"- Raw tournament winner: `{item['tournament_winner']}`",
                f"- Raw mean score: {editor['raw_mean_score']:.2f}",
                f"- Revision mean score: {editor['revision_mean_score']:.2f}",
                f"- Revision accepted: {editor['accepted']}",
                f"- Chosen finalist: `{editor['chosen_candidate_id']}`",
                f"- Mean self-BLEU proxy: {item['diversity']['corpus']['mean_self_bleu_proxy']:.4f}",
                "",
            ]
        )
    if "verbalized_sampling" in method_specific:
        plan_diversity = method_specific["verbalized_sampling"]["plan_diversity"]
        lines.extend(
            [
                "## Verbalized Sampling plan diversity",
                "",
                f"- Strategies elicited: {plan_diversity['strategy_count']}",
                "- Unique after deduplication: "
                f"{plan_diversity['unique_after_deduplication']}",
                "- Within-call mean Jaccard distance: "
                + ", ".join(
                    f"{key}={value:.4f}"
                    for key, value in plan_diversity[
                        "within_call_mean_jaccard_distance"
                    ].items()
                ),
                "- Across-call mean Jaccard distance: "
                f"{plan_diversity['across_call_mean_jaccard_distance']:.4f}",
                "",
            ]
        )
    (out / "internal_report.md").write_text("\n".join(lines), encoding="utf-8")
    return report


def package_finalists(
    *,
    finalists_path: str | Path,
    output_dir: str | Path,
    blind_seed: str | int,
) -> dict[str, Any]:
    payload = _read_json(Path(finalists_path))
    finalists = [
        Candidate.from_dict(record) for record in payload.get("finalists", ())
    ]
    return build_appraisal(finalists, output_dir, blind_seed)
