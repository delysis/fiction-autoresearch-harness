"""Provider-neutral frontier criticism; manuscript rewriting is disabled."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
import time
from typing import Any, Callable, Mapping, Protocol, Sequence
from urllib import error, request

from .anti_copy import AntiCopyIndex
from .author import ResolvedAuthorContext
from .core import canonical_json_text, sha256_text
from .provenance import assert_critic_only_frontier
from .schemas import Candidate


class CompletionLike(Protocol):
    content: str
    model: str


class CriticClient(Protocol):
    def complete(
        self,
        *,
        prompt: str,
        seed: int,
        max_tokens: int,
        temperature: float = ...,
        top_p: float = ...,
        min_p: float = ...,
        response_format: Mapping[str, Any] | None = ...,
        stop: Sequence[str] | None = ...,
        extra: Mapping[str, Any] | None = ...,
    ) -> CompletionLike: ...


@dataclass(frozen=True, slots=True)
class FrontierCompletion:
    content: str
    model: str
    usage: Mapping[str, Any]
    elapsed_seconds: float
    raw: Mapping[str, Any]


class OpenAICompatibleFrontierClient:
    """Minimal remote adapter; caller controls endpoint, model, and API key."""

    def __init__(
        self,
        base_url: str,
        *,
        model: str,
        api_key: str = "",
        timeout: float = 1_800,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def complete(
        self,
        *,
        prompt: str,
        seed: int,
        max_tokens: int,
        temperature: float = 0.1,
        top_p: float = 0.95,
        min_p: float = 0.0,
        response_format: Mapping[str, Any] | None = None,
        stop: Sequence[str] | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> FrontierCompletion:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "seed": seed,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
        }
        if response_format:
            payload["response_format"] = dict(response_format)
        if stop:
            payload["stop"] = list(stop)
        if extra:
            payload.update(extra)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = request.Request(
            self.base_url + "/v1/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        started = time.monotonic()
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                value = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"frontier endpoint returned HTTP {exc.code}: {detail[:1000]}"
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(
                f"could not reach frontier endpoint: {exc.reason}"
            ) from exc
        choices = value.get("choices", [])
        if not choices:
            raise RuntimeError("frontier completion contains no choices")
        message = choices[0].get("message", {})
        return FrontierCompletion(
            content=str(message.get("content", "")),
            model=str(value.get("model", self.model)),
            usage=dict(value.get("usage", {})),
            elapsed_seconds=time.monotonic() - started,
            raw=value,
        )


def _json_object(text: str) -> dict[str, Any]:
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
        raise ValueError("frontier critic must return a JSON object")
    return value


def critique_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "compliant": {"type": "boolean"},
            "defects": {
                "type": "array",
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "passage": {"type": "string"},
                        "diagnosis": {"type": "string"},
                        "repair": {"type": "string"},
                    },
                    "required": [
                        "label",
                        "passage",
                        "diagnosis",
                        "repair",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["compliant", "defects"],
        "additionalProperties": False,
    }


def detect_defects(
    client: CriticClient,
    *,
    candidate: Candidate,
    author_context: ResolvedAuthorContext,
    creative_profile: Mapping[str, Any],
    deterministic_findings: Mapping[str, Any],
    seed: int,
) -> dict[str, Any]:
    """Detect only demonstrated defects; raw books never enter this prompt."""

    prompt = (
        "Act as a refinement-oriented fiction critic. Report at most five "
        "defects that are demonstrated by the supplied deterministic findings "
        "or by an exact quoted passage. Do not request broad rewrites and do "
        "not infer source wording. Return JSON only.\n\n"
        f"CREATIVE_PROFILE:\n{canonical_json_text(creative_profile)}\n"
        f"DERIVED_AUTHOR_CONTEXT:\n"
        f"{canonical_json_text(author_context.prompt_payload)}\n"
        f"DETERMINISTIC_FINDINGS:\n"
        f"{canonical_json_text(deterministic_findings)}\n"
        f"CANDIDATE:\n{candidate.text}"
    )
    completion = client.complete(
        prompt=prompt,
        seed=seed,
        max_tokens=1_536,
        temperature=0.1,
        top_p=0.95,
        min_p=0.0,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "fiction_critique",
                "schema": critique_schema(),
            },
        },
    )
    value = _json_object(completion.content)
    assert_critic_only_frontier(value)
    defects = value.get("defects", [])
    if not isinstance(defects, list) or len(defects) > 5:
        raise ValueError("frontier critique must contain at most five defects")
    for defect in defects:
        if not isinstance(defect, Mapping):
            raise ValueError("frontier defects must be objects")
        passage = str(defect.get("passage", ""))
        if passage and passage not in candidate.text:
            raise ValueError("frontier defect passage is not an exact candidate quote")
    value["model"] = completion.model
    value["prompt_hash"] = sha256_text(prompt)
    return value


def revise_candidate(
    client: CriticClient,
    *,
    candidate: Candidate,
    critique: Mapping[str, Any],
    author_context: ResolvedAuthorContext,
    creative_profile: Mapping[str, Any],
    seed: int,
) -> tuple[str, dict[str, Any]]:
    """Disabled: frontier criticism must flow back into writer sampling."""

    raise RuntimeError(
        "frontier manuscript rewriting is disabled; compile the defects into "
        "a new declared-writer generation request"
    )

    defects = list(critique.get("defects", ()))[:5]
    if not defects:
        return candidate.text, {
            "changed": False,
            "reason": "candidate already compliant",
            "provenance": {
                key: str(getattr(candidate, key))
                for key in (
                    "resolved_profile_hash",
                    "author_profile_id",
                    "author_profile_hash",
                    "corpus_manifest_hash",
                    "transformation_map_hash",
                    "conditioning_variant",
                    "prompt_encoding",
                    "control_density",
                    "story_program_id",
                    "anti_copy_policy_version",
                    "anti_copy_index_hash",
                    "frontier_adapter",
                )
            },
        }
    prompt = (
        "Revise only the passage-specific defects. Preserve successful plot, "
        "voice, imagery, and dialogue. Do not add events, intensify heat, name "
        "the source author, or mention the profile. Return finished fiction "
        "only.\n\n"
        f"CREATIVE_PROFILE:\n{canonical_json_text(creative_profile)}\n"
        f"DERIVED_AUTHOR_CONTEXT:\n"
        f"{canonical_json_text(author_context.prompt_payload)}\n"
        f"DEFECTS:\n{canonical_json_text(defects)}\n"
        f"ORIGINAL:\n{candidate.text}"
    )
    completion = client.complete(
        prompt=prompt,
        seed=seed,
        max_tokens=max(2_048, len(candidate.text.split()) * 2),
        temperature=0.2,
        top_p=0.95,
        min_p=0.0,
    )
    return completion.content.strip(), {
        "changed": True,
        "model": completion.model,
        "prompt_hash": sha256_text(prompt),
        "defect_count": len(defects),
        "provenance": {
            key: str(getattr(candidate, key))
            for key in (
                "resolved_profile_hash",
                "author_profile_id",
                "author_profile_hash",
                "corpus_manifest_hash",
                "transformation_map_hash",
                "conditioning_variant",
                "prompt_encoding",
                "control_density",
                "story_program_id",
                "anti_copy_policy_version",
                "anti_copy_index_hash",
                "frontier_adapter",
            )
        },
    }


def decide_revision(
    *,
    original: Candidate,
    revised_text: str,
    anti_copy_index: AntiCopyIndex,
    original_total: float,
    revised_total: float,
    original_author_fidelity: float,
    revised_author_fidelity: float,
    hard_gate_check: Callable[[str], bool],
) -> dict[str, Any]:
    overlap = anti_copy_index.check(
        original.candidate_id + ".revision", revised_text
    )
    accepted = (
        hard_gate_check(revised_text)
        and not overlap.hard_fail
        and not overlap.unresolved_flags
        and revised_total >= original_total
        and revised_author_fidelity >= original_author_fidelity - 1
    )
    return {
        "accepted": accepted,
        "hard_gates_passed": hard_gate_check(revised_text),
        "original_total": original_total,
        "revised_total": revised_total,
        "original_author_fidelity": original_author_fidelity,
        "revised_author_fidelity": revised_author_fidelity,
        "overlap_report": overlap.to_dict(),
        "selected_text_hash": sha256_text(
            revised_text if accepted else original.text
        ),
    }
