"""Stable wire records shared by generation, evaluation, and packaging."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any, ClassVar, Mapping, TypeVar

from .core import to_plain_data


SCHEMA_VERSION = "fiction-harness.v1"
T = TypeVar("T", bound="_Record")


def _nonempty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _strings(name: str, value: tuple[str, ...], *, allow_empty: bool = True) -> None:
    if not isinstance(value, tuple) or any(not isinstance(item, str) for item in value):
        raise TypeError(f"{name} must be a tuple of strings")
    if not allow_empty and not value:
        raise ValueError(f"{name} must not be empty")


def _tuple_strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise TypeError("expected a list or tuple of strings")
    result = tuple(value)
    if any(not isinstance(item, str) for item in result):
        raise TypeError("expected a list or tuple of strings")
    return result


def _mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError("expected a mapping")
    return {str(key): item for key, item in value.items()}


def _validate_author_lineage(record_name: str, values: Mapping[str, str]) -> None:
    populated = {key: value for key, value in values.items() if value}
    if not populated:
        return
    required = (
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
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise ValueError(
            f"{record_name} author lineage fields must be supplied together; "
            f"missing {', '.join(missing)}"
        )
    for key in (
        "author_profile_hash",
        "corpus_manifest_hash",
        "transformation_map_hash",
        "anti_copy_index_hash",
    ):
        value = values[key]
        if len(value) != 64:
            raise ValueError(f"{record_name} {key} must be a SHA-256 digest")


def _validate_continuation_lineage(
    record_name: str, values: Mapping[str, str]
) -> None:
    populated = {key: value for key, value in values.items() if value}
    if not populated:
        return
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise ValueError(
            f"{record_name} continuation lineage fields must be supplied "
            f"together; missing {', '.join(missing)}"
        )
    for key in ("approved_prefix_hash", "feedback_brief_hash"):
        if len(values[key]) != 64:
            raise ValueError(f"{record_name} {key} must be a SHA-256 digest")


class _Record:
    """Mixin implementing a strict, versioned JSON boundary."""

    record_type: ClassVar[str]

    def to_dict(self) -> dict[str, Any]:
        data = to_plain_data(self)
        data["record_type"] = self.record_type
        return data

    @classmethod
    def _payload(cls: type[T], data: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(data)
        record_type = payload.pop("record_type", cls.record_type)
        if record_type != cls.record_type:
            raise ValueError(f"expected record_type {cls.record_type!r}, got {record_type!r}")
        allowed = {field.name for field in fields(cls)}
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise ValueError(f"unknown {cls.record_type} fields: {', '.join(unknown)}")
        return payload


@dataclass(frozen=True, slots=True)
class SceneSpec(_Record):
    record_type: ClassVar[str] = "SceneSpec"

    scene_id: str
    title: str
    function: str
    pov: str
    target_words_min: int
    target_words_max: int
    opening_image: str
    desire: str
    obstacle: str
    pressure_ladder: tuple[str, ...]
    turn: str
    aftermath: str
    teaching_payload: str
    source_ids: tuple[str, ...]
    beat_map: tuple[str, ...]
    continuity_facts: tuple[str, ...]
    heat_ceiling: str
    pacing_targets: tuple[str, ...] = ()
    version: str = "1"
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "scene_id",
            "title",
            "function",
            "pov",
            "opening_image",
            "desire",
            "obstacle",
            "turn",
            "aftermath",
            "teaching_payload",
            "heat_ceiling",
            "version",
            "schema_version",
        ):
            _nonempty(name, getattr(self, name))
        if self.target_words_min <= 0 or self.target_words_max < self.target_words_min:
            raise ValueError("target word range must be positive and ordered")
        _strings("pressure_ladder", self.pressure_ladder, allow_empty=False)
        _strings("source_ids", self.source_ids, allow_empty=False)
        _strings("beat_map", self.beat_map, allow_empty=False)
        _strings("continuity_facts", self.continuity_facts)
        _strings("pacing_targets", self.pacing_targets)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SceneSpec":
        payload = cls._payload(data)
        for key in (
            "pressure_ladder",
            "source_ids",
            "beat_map",
            "continuity_facts",
            "pacing_targets",
        ):
            if key in payload:
                payload[key] = _tuple_strings(payload[key])
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class PersonaPacket(_Record):
    record_type: ClassVar[str] = "PersonaPacket"

    persona_id: str
    name: str
    version: str
    role: str
    age: int | None
    invariants: tuple[str, ...]
    false_beliefs: tuple[str, ...]
    attention_habits: tuple[str, ...]
    relationship_variants: Mapping[str, tuple[str, ...]]
    contradictions: tuple[str, ...] = ()
    dialogue_exemplars: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("persona_id", "name", "version", "role", "schema_version"):
            _nonempty(name, getattr(self, name))
        if self.age is not None and (not isinstance(self.age, int) or self.age < 18):
            raise ValueError("persona age must be an integer of at least 18 or null")
        _strings("invariants", self.invariants, allow_empty=False)
        _strings("false_beliefs", self.false_beliefs)
        _strings("attention_habits", self.attention_habits)
        _strings("contradictions", self.contradictions)
        _strings("dialogue_exemplars", self.dialogue_exemplars)
        _strings("source_ids", self.source_ids)
        if not isinstance(self.relationship_variants, Mapping):
            raise TypeError("relationship_variants must be a mapping")
        for relation, traits in self.relationship_variants.items():
            _nonempty("relationship_variants key", relation)
            _strings(f"relationship_variants[{relation}]", traits)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PersonaPacket":
        payload = cls._payload(data)
        for key in (
            "invariants",
            "false_beliefs",
            "attention_habits",
            "contradictions",
            "dialogue_exemplars",
            "source_ids",
        ):
            if key in payload:
                payload[key] = _tuple_strings(payload[key])
        relations = _mapping(payload.get("relationship_variants", {}))
        payload["relationship_variants"] = {
            key: _tuple_strings(value) for key, value in relations.items()
        }
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class RunConfig(_Record):
    record_type: ClassVar[str] = "RunConfig"

    run_id: str
    scene_id: str
    pipeline: str
    model_role: str
    prompt_hash: str
    source_hashes: Mapping[str, str]
    seeds: tuple[int, ...]
    sampling: Mapping[str, float | int | bool]
    output_words_min: int
    output_words_max: int
    output_tokens: int
    persona_ids: tuple[str, ...] = ()
    created_at: str = ""
    ontology_version: str = ""
    story_profile_id: str = ""
    scene_profile_id: str = ""
    resolved_profile_hash: str = ""
    author_profile_id: str = ""
    author_profile_hash: str = ""
    corpus_manifest_hash: str = ""
    transformation_map_hash: str = ""
    conditioning_variant: str = ""
    prompt_encoding: str = ""
    control_density: str = ""
    story_program_id: str = ""
    anti_copy_policy_version: str = ""
    anti_copy_index_hash: str = ""
    frontier_adapter: str = ""
    approved_prefix_id: str = ""
    approved_prefix_hash: str = ""
    feedback_brief_hash: str = ""
    generation_mode: str = ""
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "run_id",
            "scene_id",
            "pipeline",
            "model_role",
            "prompt_hash",
            "schema_version",
        ):
            _nonempty(name, getattr(self, name))
        if not self.seeds or any(not isinstance(seed, int) for seed in self.seeds):
            raise ValueError("seeds must contain at least one integer")
        if len(set(self.seeds)) != len(self.seeds):
            raise ValueError("seeds must be unique")
        if self.output_words_min <= 0 or self.output_words_max < self.output_words_min:
            raise ValueError("output word range must be positive and ordered")
        if self.output_tokens <= 0:
            raise ValueError("output_tokens must be positive")
        if not isinstance(self.source_hashes, Mapping) or not self.source_hashes:
            raise ValueError("source_hashes must be a non-empty mapping")
        if any(not isinstance(value, str) or len(value) != 64 for value in self.source_hashes.values()):
            raise ValueError("source_hashes values must be SHA-256 hex digests")
        _strings("persona_ids", self.persona_ids)
        if self.resolved_profile_hash and len(self.resolved_profile_hash) != 64:
            raise ValueError("resolved_profile_hash must be empty or a SHA-256 digest")
        provenance = (
            self.ontology_version,
            self.story_profile_id,
            self.scene_profile_id,
            self.resolved_profile_hash,
        )
        if any(provenance) and not all(provenance):
            raise ValueError(
                "ontology_version, story_profile_id, scene_profile_id, and "
                "resolved_profile_hash must be supplied together"
            )
        _validate_author_lineage(
            "run config",
            {
                key: getattr(self, key)
                for key in (
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
        )
        _validate_continuation_lineage(
            "run config",
            {
                key: getattr(self, key)
                for key in (
                    "approved_prefix_id",
                    "approved_prefix_hash",
                    "feedback_brief_hash",
                    "generation_mode",
                )
            },
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RunConfig":
        payload = cls._payload(data)
        payload["seeds"] = tuple(payload.get("seeds", ()))
        payload["persona_ids"] = _tuple_strings(payload.get("persona_ids", ()))
        payload["source_hashes"] = {
            str(key): str(value) for key, value in _mapping(payload.get("source_hashes")).items()
        }
        payload["sampling"] = _mapping(payload.get("sampling"))
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class Candidate(_Record):
    record_type: ClassVar[str] = "Candidate"

    candidate_id: str
    run_id: str
    pipeline: str
    scene_id: str
    seed: int
    text: str
    parent_trace: Mapping[str, Any]
    evidence_ids: tuple[str, ...]
    telemetry: Mapping[str, Any]
    lineage: tuple[str, ...]
    prompt_hash: str
    completed: bool = True
    ontology_version: str = ""
    story_profile_id: str = ""
    scene_profile_id: str = ""
    resolved_profile_hash: str = ""
    author_profile_id: str = ""
    author_profile_hash: str = ""
    corpus_manifest_hash: str = ""
    transformation_map_hash: str = ""
    conditioning_variant: str = ""
    prompt_encoding: str = ""
    control_density: str = ""
    story_program_id: str = ""
    anti_copy_policy_version: str = ""
    anti_copy_index_hash: str = ""
    frontier_adapter: str = ""
    approved_prefix_id: str = ""
    approved_prefix_hash: str = ""
    feedback_brief_hash: str = ""
    generation_mode: str = ""
    continuation_text: str = ""
    artifact_authorship: Mapping[str, Any] = field(default_factory=dict)
    review_attestations: tuple[Mapping[str, Any], ...] = ()
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "candidate_id",
            "run_id",
            "pipeline",
            "scene_id",
            "prompt_hash",
            "schema_version",
        ):
            _nonempty(name, getattr(self, name))
        if not isinstance(self.seed, int):
            raise TypeError("seed must be an integer")
        if not isinstance(self.text, str):
            raise TypeError("text must be a string")
        _strings("evidence_ids", self.evidence_ids)
        _strings("lineage", self.lineage)
        if not isinstance(self.parent_trace, Mapping) or not isinstance(self.telemetry, Mapping):
            raise TypeError("parent_trace and telemetry must be mappings")
        if not isinstance(self.artifact_authorship, Mapping):
            raise TypeError("artifact_authorship must be a mapping")
        if not isinstance(self.review_attestations, tuple) or any(
            not isinstance(item, Mapping) for item in self.review_attestations
        ):
            raise TypeError("review_attestations must be a tuple of mappings")
        if self.resolved_profile_hash and len(self.resolved_profile_hash) != 64:
            raise ValueError("resolved_profile_hash must be empty or a SHA-256 digest")
        provenance = (
            self.ontology_version,
            self.story_profile_id,
            self.scene_profile_id,
            self.resolved_profile_hash,
        )
        if any(provenance) and not all(provenance):
            raise ValueError(
                "candidate ontology provenance fields must be supplied together"
            )
        _validate_author_lineage(
            "candidate",
            {
                key: getattr(self, key)
                for key in (
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
        )
        _validate_continuation_lineage(
            "candidate",
            {
                key: getattr(self, key)
                for key in (
                    "approved_prefix_id",
                    "approved_prefix_hash",
                    "feedback_brief_hash",
                    "generation_mode",
                )
            },
        )
        if self.continuation_text and not self.approved_prefix_hash:
            raise ValueError(
                "candidate continuation_text requires continuation lineage"
            )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Candidate":
        payload = cls._payload(data)
        payload["evidence_ids"] = _tuple_strings(payload.get("evidence_ids", ()))
        payload["lineage"] = _tuple_strings(payload.get("lineage", ()))
        payload["parent_trace"] = _mapping(payload.get("parent_trace"))
        payload["telemetry"] = _mapping(payload.get("telemetry"))
        payload["artifact_authorship"] = _mapping(
            payload.get("artifact_authorship")
        )
        reviews = payload.get("review_attestations", ())
        if not isinstance(reviews, (list, tuple)):
            raise TypeError("review_attestations must be a list or tuple")
        payload["review_attestations"] = tuple(_mapping(item) for item in reviews)
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class ScoreCard(_Record):
    record_type: ClassVar[str] = "ScoreCard"

    candidate_id: str
    judge_id: str
    label_order: tuple[str, ...]
    hard_gates: Mapping[str, bool]
    rubric_scores: Mapping[str, float]
    passage_evidence: Mapping[str, tuple[str, ...]]
    defects: tuple[str, ...]
    romance_diagnostics: Mapping[str, float | bool | str]
    total_score: float
    eligible: bool
    ontology_version: str = ""
    story_profile_id: str = ""
    scene_profile_id: str = ""
    resolved_profile_hash: str = ""
    author_profile_id: str = ""
    author_profile_hash: str = ""
    corpus_manifest_hash: str = ""
    transformation_map_hash: str = ""
    conditioning_variant: str = ""
    prompt_encoding: str = ""
    control_density: str = ""
    story_program_id: str = ""
    anti_copy_policy_version: str = ""
    anti_copy_index_hash: str = ""
    frontier_adapter: str = ""
    approved_prefix_id: str = ""
    approved_prefix_hash: str = ""
    feedback_brief_hash: str = ""
    generation_mode: str = ""
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("candidate_id", "judge_id", "schema_version"):
            _nonempty(name, getattr(self, name))
        _strings("label_order", self.label_order)
        _strings("defects", self.defects)
        if any(not isinstance(value, bool) for value in self.hard_gates.values()):
            raise TypeError("hard_gates values must be booleans")
        if any(not isinstance(value, (int, float)) for value in self.rubric_scores.values()):
            raise TypeError("rubric_scores values must be numeric")
        if not 0 <= float(self.total_score) <= 100:
            raise ValueError("total_score must be between 0 and 100")
        for axis, excerpts in self.passage_evidence.items():
            _strings(f"passage_evidence[{axis}]", excerpts)
        if self.resolved_profile_hash and len(self.resolved_profile_hash) != 64:
            raise ValueError("resolved_profile_hash must be empty or a SHA-256 digest")
        provenance = (
            self.ontology_version,
            self.story_profile_id,
            self.scene_profile_id,
            self.resolved_profile_hash,
        )
        if any(provenance) and not all(provenance):
            raise ValueError(
                "scorecard ontology provenance fields must be supplied together"
            )
        _validate_author_lineage(
            "scorecard",
            {
                key: getattr(self, key)
                for key in (
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
        )
        _validate_continuation_lineage(
            "scorecard",
            {
                key: getattr(self, key)
                for key in (
                    "approved_prefix_id",
                    "approved_prefix_hash",
                    "feedback_brief_hash",
                    "generation_mode",
                )
            },
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ScoreCard":
        payload = cls._payload(data)
        payload["label_order"] = _tuple_strings(payload.get("label_order", ()))
        payload["defects"] = _tuple_strings(payload.get("defects", ()))
        payload["hard_gates"] = {
            str(key): value for key, value in _mapping(payload.get("hard_gates")).items()
        }
        payload["rubric_scores"] = {
            str(key): float(value)
            for key, value in _mapping(payload.get("rubric_scores")).items()
        }
        payload["passage_evidence"] = {
            str(key): _tuple_strings(value)
            for key, value in _mapping(payload.get("passage_evidence")).items()
        }
        payload["romance_diagnostics"] = _mapping(payload.get("romance_diagnostics"))
        return cls(**payload)
