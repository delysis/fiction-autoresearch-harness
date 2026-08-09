"""Author-corpus validation, back-translation compilation, and prompt views."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence
from xml.sax.saxutils import escape as xml_escape

from .author_schemas import (
    AFFORDANCE_AXES,
    AuthorAffordance,
    AuthorCorpusManifest,
    AuthorProfile,
    SceneContentGraph,
    SourceSegment,
    TransformationMap,
    resolve_book_path,
)
from .core import canonical_json_text, hash_file, hash_json, sha256_text


PROMPT_ENCODINGS = frozenset({"xml", "markdown", "json"})
CONTROL_DENSITY_LIMITS = {
    "organic": 4,
    "light": 8,
    "medium": 20,
    "dense": 40,
    "raw-rag": 0,
}
CONDITIONING_VARIANTS = frozenset(
    {
        "none",
        "name-only",
        "anonymous-profile",
        "named-profile",
        "profile-sparse-exemplars",
        "plot-review-nshot",
        "dense-retrieval",
        "raw-rag",
    }
)
CHAPTER_HEADING = re.compile(
    r"(?im)^(?:chapter|book|part|volume)\s+"
    r"(?:[0-9ivxlcdm]+|[a-z][\w -]{0,60})[.\]]?\s*$"
)


@dataclass(frozen=True, slots=True)
class CorpusValidation:
    manifest_hash: str
    book_count: int
    partition_counts: Mapping[str, int]
    verified_paths: tuple[str, ...]
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_hash": self.manifest_hash,
            "book_count": self.book_count,
            "partition_counts": dict(self.partition_counts),
            "verified_paths": list(self.verified_paths),
            "errors": list(self.errors),
            "valid": self.valid,
        }


@dataclass(frozen=True, slots=True)
class ResolvedAuthorContext:
    author_profile_id: str
    author_profile_hash: str
    corpus_manifest_hash: str
    transformation_map_hash: str
    conditioning_variant: str
    prompt_encoding: str
    control_density: str
    author_name: str
    selected_affordance_ids: tuple[str, ...]
    prompt_payload: Mapping[str, Any]

    @property
    def context_hash(self) -> str:
        return hash_json(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "author_profile_id": self.author_profile_id,
            "author_profile_hash": self.author_profile_hash,
            "corpus_manifest_hash": self.corpus_manifest_hash,
            "transformation_map_hash": self.transformation_map_hash,
            "conditioning_variant": self.conditioning_variant,
            "prompt_encoding": self.prompt_encoding,
            "control_density": self.control_density,
            "author_name": self.author_name,
            "selected_affordance_ids": list(self.selected_affordance_ids),
            "prompt_payload": self.prompt_payload,
        }


def load_corpus_manifest(path: str | Path) -> AuthorCorpusManifest:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise TypeError("author corpus manifest must be a JSON object")
    return AuthorCorpusManifest.from_dict(value)


def load_author_profile(path: str | Path) -> AuthorProfile:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise TypeError("author profile must be a JSON object")
    return AuthorProfile.from_dict(value)


def load_transformation_map(path: str | Path) -> TransformationMap:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise TypeError("transformation map must be a JSON object")
    return TransformationMap.from_dict(value)


def validate_corpus_files(
    manifest_path: str | Path,
    *,
    permit_holdout_read: bool = False,
) -> CorpusValidation:
    """Verify declared files and hashes without returning source contents."""

    manifest_file = Path(manifest_path)
    manifest = load_corpus_manifest(manifest_file)
    errors: list[str] = []
    verified: list[str] = []
    counts = {partition: 0 for partition in ("profiling", "calibration", "holdout")}
    for book in manifest.books:
        counts[book.partition] += 1
        path = resolve_book_path(manifest_file, book)
        if not path.is_file():
            errors.append(f"missing book file: {path}")
            continue
        if book.partition == "holdout" and not permit_holdout_read:
            verified.append(f"{path} (existence only; holdout unread)")
            continue
        observed = hash_file(path)
        if observed != book.text_hash:
            errors.append(
                f"hash mismatch for {book.book_id}: {observed} != {book.text_hash}"
            )
            continue
        verified.append(str(path))
    return CorpusValidation(
        manifest_hash=manifest.corpus_hash,
        book_count=len(manifest.books),
        partition_counts=counts,
        verified_paths=tuple(verified),
        errors=tuple(errors),
    )


def _segment_text(text: str) -> list[tuple[str, str]]:
    """Split a book into deterministic chapter-like segments."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    matches = list(CHAPTER_HEADING.finditer(normalized))
    if not matches:
        words = normalized.split()
        return [
            (
                f"word-window-{start // 2500 + 1:04d}",
                " ".join(words[start : start + 2500]),
            )
            for start in range(0, len(words), 2500)
            if words[start : start + 2500]
        ]
    segments: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(normalized)
        body = normalized[match.start() : end].strip()
        if body:
            segments.append((match.group(0).strip(), body))
    return segments


def compile_source_segments(
    manifest_path: str | Path,
    *,
    partitions: Sequence[str] = ("profiling", "calibration"),
) -> tuple[tuple[SourceSegment, str], ...]:
    """Read the requested experiment partitions and pair records with local text."""

    forbidden = set(partitions) - {"profiling", "calibration"}
    if forbidden:
        raise ValueError(
            "holdout material cannot enter author compilation: "
            + ", ".join(sorted(forbidden))
        )
    manifest_file = Path(manifest_path)
    manifest = load_corpus_manifest(manifest_file)
    output: list[tuple[SourceSegment, str]] = []
    for book in manifest.books:
        if book.partition not in partitions:
            continue
        path = resolve_book_path(manifest_file, book)
        if hash_file(path) != book.text_hash:
            raise ValueError(f"source hash mismatch for {book.book_id}")
        text = path.read_text(encoding="utf-8")
        for index, (location, segment_text) in enumerate(_segment_text(text), 1):
            output.append(
                (
                    SourceSegment(
                        segment_id=f"{book.book_id}.segment-{index:04d}",
                        book_id=book.book_id,
                        partition=book.partition,
                        location=location,
                        text_hash=sha256_text(segment_text),
                        word_count=len(segment_text.split()),
                    ),
                    segment_text,
                )
            )
    return tuple(output)


def validate_profile_against_manifest(
    profile: AuthorProfile,
    manifest: AuthorCorpusManifest,
) -> None:
    if profile.author_id != manifest.author_id:
        raise ValueError("author profile and corpus manifest identify different authors")
    if profile.corpus_manifest_hash != manifest.corpus_hash:
        raise ValueError("author profile was compiled from a different corpus manifest")
    allowed_books = {
        book.book_id for book in manifest.books if book.partition != "holdout"
    }
    holdout_books = {
        book.book_id for book in manifest.books if book.partition == "holdout"
    }
    for affordance in profile.affordances:
        evidence = set(affordance.evidence_book_ids)
        leaked = evidence & holdout_books
        if leaked:
            raise ValueError(
                f"holdout leakage in {affordance.affordance_id}: {sorted(leaked)}"
            )
        unknown = evidence - allowed_books
        if unknown:
            raise ValueError(
                f"unknown evidence books in {affordance.affordance_id}: "
                f"{sorted(unknown)}"
            )


def validate_affordance_provenance(
    profile: AuthorProfile,
    *,
    source_segments: Sequence[SourceSegment],
    known_rgo_coordinates: Iterable[str] = (),
) -> None:
    """Resolve evidence locations and optional RGO links before prompting."""

    segment_ids = {segment.segment_id for segment in source_segments}
    known_rgo = set(known_rgo_coordinates)
    for affordance in profile.affordances:
        unresolved = sorted(
            (
                set(affordance.evidence_refs)
                | set(affordance.counterevidence_refs)
            )
            - segment_ids
        )
        if unresolved:
            raise ValueError(
                f"unresolved evidence references in {affordance.affordance_id}: "
                f"{unresolved}"
            )
        if known_rgo:
            unknown_rgo = sorted(
                set(affordance.rgo_coordinates) - known_rgo
            )
            if unknown_rgo:
                raise ValueError(
                    f"unknown RGO links in {affordance.affordance_id}: "
                    f"{unknown_rgo}"
                )


def validate_transformation_map(
    profile: AuthorProfile,
    transformation: TransformationMap,
    *,
    target_profile_hash: str | None = None,
) -> None:
    if transformation.author_profile_id != profile.profile_id:
        raise ValueError("transformation map targets a different author profile")
    if (
        target_profile_hash is not None
        and transformation.target_profile_hash != target_profile_hash
    ):
        raise ValueError(
            "transformation map targets a different creative profile: "
            f"{transformation.target_profile_hash} != {target_profile_hash}"
        )
    expected = {item.affordance_id for item in profile.affordances}
    observed = set(transformation.rules)
    if expected != observed:
        missing = sorted(expected - observed)
        unknown = sorted(observed - expected)
        raise ValueError(
            f"transformation rules must cover the profile exactly; "
            f"missing={missing}, unknown={unknown}"
        )


def select_affordances(
    profile: AuthorProfile,
    transformation: TransformationMap,
    *,
    control_density: str,
) -> tuple[AuthorAffordance, ...]:
    if control_density not in CONTROL_DENSITY_LIMITS:
        raise ValueError(f"unknown control density: {control_density}")
    limit = CONTROL_DENSITY_LIMITS[control_density]
    if not limit:
        return ()
    usable = [
        item
        for item in profile.affordances
        if transformation.rules[item.affordance_id]
        not in {"exclude", "evaluator-only"}
    ]
    # Ensure broad coverage before filling by strength. This prevents syntax
    # claims from crowding out scene or relationship mechanics.
    ordered = sorted(
        usable,
        key=lambda item: (
            item.axis,
            -int(item.scope == "author-signature"),
            -item.strength,
            -item.confidence,
            item.affordance_id,
        ),
    )
    representatives: list[AuthorAffordance] = []
    used_axes: set[str] = set()
    for item in ordered:
        if item.axis not in used_axes:
            representatives.append(item)
            used_axes.add(item.axis)
        if len(representatives) == limit:
            return tuple(representatives)
    remainder = sorted(
        (item for item in usable if item not in representatives),
        key=lambda item: (
            -int(item.scope == "author-signature"),
            -item.strength,
            -item.confidence,
            -item.prevalence,
            item.affordance_id,
        ),
    )
    return tuple((representatives + remainder)[:limit])


def resolve_author_context(
    profile: AuthorProfile,
    transformation: TransformationMap,
    *,
    corpus_manifest_hash: str,
    conditioning_variant: str = "anonymous-profile",
    prompt_encoding: str = "xml",
    control_density: str = "medium",
    conditioning_material: Sequence[Mapping[str, Any]] = (),
) -> ResolvedAuthorContext:
    if conditioning_variant not in CONDITIONING_VARIANTS:
        raise ValueError(f"unknown conditioning variant: {conditioning_variant}")
    if prompt_encoding not in PROMPT_ENCODINGS:
        raise ValueError(f"unknown prompt encoding: {prompt_encoding}")
    validate_transformation_map(profile, transformation)
    materials = tuple(dict(item) for item in conditioning_material)
    material_variants = {
        "profile-sparse-exemplars",
        "plot-review-nshot",
        "dense-retrieval",
        "raw-rag",
    }
    if conditioning_variant in material_variants and not materials:
        raise ValueError(
            f"{conditioning_variant} requires explicit conditioning material"
        )
    if conditioning_variant not in material_variants and materials:
        raise ValueError(
            f"{conditioning_variant} does not admit source conditioning material"
        )
    if conditioning_variant == "profile-sparse-exemplars":
        if len(materials) > 3:
            raise ValueError("sparse exemplar conditioning permits at most three excerpts")
        for item in materials:
            text = str(item.get("text", ""))
            if not text or len(text.split()) > 120:
                raise ValueError(
                    "each sparse exemplar must contain 1-120 words"
                )
    if conditioning_variant == "plot-review-nshot" and len(materials) > 5:
        raise ValueError("plot/review n-shot conditioning permits at most five books")
    if conditioning_variant in {"dense-retrieval", "raw-rag"}:
        words = sum(
            len(str(item.get("text", "")).split()) for item in materials
        )
        if words > 24_000:
            raise ValueError("dense retrieval material exceeds 24,000 words")
    selected = (
        ()
        if conditioning_variant in {"none", "name-only"}
        else select_affordances(
            profile, transformation, control_density=control_density
        )
    )
    affordance_payload: list[dict[str, Any]] = []
    for item in selected:
        action = transformation.rules[item.affordance_id]
        semantics = transformation.target_semantics.get(item.affordance_id)
        if not semantics:
            semantics = item.prompt_semantics
        affordance_payload.append(
            {
                "id": item.affordance_id,
                "axis": item.axis,
                "activation_conditions": list(item.activation_conditions),
                "strength": item.strength,
                "distribution": dict(item.distribution),
                "creative_obligations": list(semantics),
            }
        )
    include_name = conditioning_variant in {
        "name-only",
        "named-profile",
        "profile-sparse-exemplars",
        "plot-review-nshot",
        "dense-retrieval",
        "raw-rag",
    }
    payload = {
        "profile_id": profile.profile_id,
        "author_label": profile.author_name if include_name else "AUTHOR_TARGET",
        "conditioning_variant": conditioning_variant,
        "author_subgenre_delta": list(profile.author_subgenre_delta),
        "affordances": affordance_payload,
        "distributions": dict(profile.distributions),
        "negative_space": list(profile.negative_space),
    }
    if materials:
        payload["conditioning_material"] = list(materials)
    if conditioning_variant == "none":
        payload = {
            "conditioning_variant": "none",
            "affordances": [],
        }
    elif conditioning_variant == "name-only":
        payload = {
            "conditioning_variant": "name-only",
            "author_label": profile.author_name,
            "affordances": [],
        }
    return ResolvedAuthorContext(
        author_profile_id=profile.profile_id,
        author_profile_hash=profile.profile_hash,
        corpus_manifest_hash=corpus_manifest_hash,
        transformation_map_hash=transformation.map_hash,
        conditioning_variant=conditioning_variant,
        prompt_encoding=prompt_encoding,
        control_density=control_density,
        author_name=profile.author_name if include_name else "AUTHOR_TARGET",
        selected_affordance_ids=tuple(item.affordance_id for item in selected),
        prompt_payload=payload,
    )


def _xml_value(name: str, value: Any, *, indent: str = "  ") -> str:
    if isinstance(value, Mapping):
        lines = [f"<{name}>"]
        for key in sorted(value):
            lines.append(
                indent
                + _xml_value(
                    re.sub(r"[^a-zA-Z0-9_.-]", "_", str(key)),
                    value[key],
                    indent=indent,
                ).replace("\n", "\n" + indent)
            )
        lines.append(f"</{name}>")
        return "\n".join(lines)
    if isinstance(value, (list, tuple)):
        lines = [f"<{name}>"]
        for item in value:
            lines.append(
                indent
                + _xml_value("item", item, indent=indent).replace(
                    "\n", "\n" + indent
                )
            )
        lines.append(f"</{name}>")
        return "\n".join(lines)
    if value is None:
        return f"<{name}/>"
    if isinstance(value, bool):
        text = "true" if value else "false"
    else:
        text = str(value)
    return f"<{name}>{xml_escape(text, {'\"': '&quot;'})}</{name}>"


def render_prompt_payload(payload: Mapping[str, Any], encoding: str) -> str:
    """Render one canonical payload into a deterministic model-facing view."""

    if encoding not in PROMPT_ENCODINGS:
        raise ValueError(f"unknown prompt encoding: {encoding}")
    if encoding == "json":
        return canonical_json_text(payload).rstrip()
    if encoding == "xml":
        return _xml_value("author_conditioning", payload)
    lines = ["## Author conditioning"]
    for key in sorted(payload):
        value = payload[key]
        if isinstance(value, (Mapping, list, tuple)):
            lines.append(f"\n### {key}\n")
            lines.append(canonical_json_text(value).rstrip())
        else:
            lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def render_base_writer_prompt(
    *,
    creative_profile: Mapping[str, Any],
    gabaldon_profile: Mapping[str, Any],
    author_context: ResolvedAuthorContext,
    story_canon: Mapping[str, Any],
    scene_input: Mapping[str, Any],
) -> tuple[str, str]:
    """Return cache-stable prefix and variable suffix for raw base completion."""

    encoding = author_context.prompt_encoding
    creative_view = (
        {
            "contract": creative_profile.get("contract"),
            "primary_genre": creative_profile.get("primary_genre"),
            "secondary_genres": creative_profile.get("secondary_genres", ()),
            "positive_scene_obligations": creative_profile.get(
                "prompt_obligations", ()
            ),
            "heat_target": creative_profile.get("heat_target"),
            "heat_ceiling": creative_profile.get("heat_ceiling"),
            "relationship_result": creative_profile.get(
                "relationship_result"
            ),
            "pacing": creative_profile.get("pacing", ()),
            "atmosphere": creative_profile.get("atmosphere", ()),
        }
        if "prompt_obligations" in creative_profile
        else creative_profile
    )
    gabaldon_view = (
        {
            "principles": gabaldon_profile.get("principles", ()),
            "generation_contract": gabaldon_profile.get(
                "generation_contract", ()
            ),
            "scene_application": gabaldon_profile.get(
                "s01_application", {}
            ),
        }
        if "generation_contract" in gabaldon_profile
        else gabaldon_profile
    )
    canon_view = (
        {"canon_text": story_canon["text"]}
        if isinstance(story_canon.get("text"), str)
        else story_canon
    )
    stable_payload = {
        "creative_profile": creative_view,
        "gabaldon_intimacy_profile": gabaldon_view,
        "author_affordances": author_context.prompt_payload,
        "story_canon": canon_view,
    }
    lead = draft_lead(scene_input)
    if encoding == "xml":
        prefix = (
            '<fiction_program version="1">\n'
            + "\n".join(
                "  "
                + _xml_value(name, value).replace("\n", "\n  ")
                for name, value in stable_payload.items()
            )
            + "\n</fiction_program>"
        )
        dynamic = (
            "<scene_input>\n"
            + _xml_value("scene", scene_input).replace("\n", "\n  ")
            + "\n</scene_input>\n"
            "<draft_prose format=\"fiction-only\" metadata=\"forbidden\">\n"
            + lead
        )
        return prefix, dynamic
    prefix = render_prompt_payload(stable_payload, encoding)
    if encoding == "json":
        dynamic = (
            canonical_json_text({"scene_input": scene_input}).rstrip()
            + "\n\nDRAFT PROSE ONLY — NO SCHEMA OR METADATA:\n"
            + lead
        )
    else:
        dynamic = (
            "## Scene input\n\n"
            + canonical_json_text(scene_input).rstrip()
            + "\n\n## Draft prose only — no schema or metadata\n\n"
            + lead
        )
    return prefix, dynamic


def draft_lead(scene_input: Mapping[str, Any]) -> str:
    supplied = str(scene_input.get("prose_lead", "")).strip()
    if supplied:
        return supplied.rstrip() + "\n\n"
    scene = scene_input.get("scene", {})
    if isinstance(scene, Mapping):
        opening = str(scene.get("opening_image", "")).strip()
        if opening:
            # Scene specifications use present-tense summaries. Convert only
            # the first common summary verb. Keep the seed shorter than the
            # anti-copy policy's twelve-word hard-fail span: it should put the
            # base model into prose mode without copying a canon sentence into
            # the candidate.
            opening = re.sub(r"\barrives\b", "arrived", opening, count=1)
            opening = re.split(
                r"\b(?:carrying|holding|bringing)\b",
                opening,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0].strip()
            words = opening.rstrip(".").split()
            if len(words) >= 12:
                opening = " ".join(words[:10])
            return opening.rstrip(".") + ".\n\n"
        pov = str(scene.get("pov", "")).strip()
        if pov:
            return pov + " "
    return ""


def build_scene_graph_extraction_prompt(
    segment: SourceSegment,
    text: str,
) -> str:
    if segment.partition == "holdout":
        raise ValueError("holdout source cannot enter a back-translation prompt")
    return (
        "Back-translate the source scene into content-neutral causal structure. "
        "Do not imitate or evaluate its prose. Return a SceneContentGraph JSON "
        "object containing event_sequence, knowledge_changes, emotional_transactions, "
        "character_decisions, relationship_delta, intimacy_mode, and "
        "discourse_function.\n\n"
        f"SOURCE_SEGMENT_ID: {segment.segment_id}\n"
        f"SOURCE_TEXT:\n{text}"
    )


def build_affordance_contrast_prompt(
    graph: SceneContentGraph,
    author_text: str,
    generic_reconstruction: str,
) -> str:
    return (
        "Compare the author scene with the generic reconstruction of the same "
        "content graph. Extract only reusable author deltas, not plot facts or "
        "quotable wording. Classify each finding under one approved axis and "
        "ground it in source locations. Return AuthorAffordance JSON records.\n\n"
        f"APPROVED_AXES: {', '.join(sorted(AFFORDANCE_AXES))}\n"
        f"CONTENT_GRAPH:\n{canonical_json_text(graph.to_dict())}\n"
        f"AUTHOR_SCENE:\n{author_text}\n\n"
        f"GENERIC_RECONSTRUCTION:\n{generic_reconstruction}"
    )


def build_profile(
    *,
    profile_id: str,
    author_id: str,
    author_name: str,
    version: str,
    corpus_manifest_hash: str,
    affordances: Iterable[AuthorAffordance],
    author_subgenre_delta: Sequence[str] = (),
    distributions: Mapping[str, Any] | None = None,
    negative_space: Sequence[str] = (),
) -> AuthorProfile:
    """Normalize affordance scope and construct a deterministic profile."""

    normalized: list[AuthorAffordance] = []
    for item in affordances:
        desired_scope = (
            "author-signature"
            if len(set(item.evidence_book_ids)) >= 2
            else "local-tendency"
        )
        if item.scope != desired_scope:
            payload = item.to_dict()
            payload["scope"] = desired_scope
            normalized.append(AuthorAffordance.from_dict(payload))
        else:
            normalized.append(item)
    return AuthorProfile(
        profile_id=profile_id,
        author_id=author_id,
        author_name=author_name,
        version=version,
        corpus_manifest_hash=corpus_manifest_hash,
        affordances=tuple(
            sorted(normalized, key=lambda item: item.affordance_id)
        ),
        author_subgenre_delta=tuple(author_subgenre_delta),
        distributions=dict(distributions or {}),
        negative_space=tuple(negative_space),
    )
