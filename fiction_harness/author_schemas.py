"""Versioned records for author back-translation and anti-copy provenance."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Mapping

from .core import hash_json
from .schemas import (
    SCHEMA_VERSION,
    _Record,
    _mapping,
    _nonempty,
    _strings,
    _tuple_strings,
)


PARTITIONS = frozenset({"profiling", "calibration", "holdout"})
AFFORDANCE_AXES = frozenset(
    {
        "rgo_market",
        "book_architecture",
        "scene_causality",
        "intimacy_relationship",
        "character_policy",
        "relationship_behavior",
        "dialogue",
        "discourse",
        "syntax_lexis",
        "imagery_sensory",
        "reader_response",
    }
)
TRANSFORMATION_ACTIONS = frozenset(
    {"preserve", "transpose", "invert", "exclude", "evaluator-only"}
)


def _digest(name: str, value: str, *, allow_empty: bool = False) -> None:
    if not value and allow_empty:
        return
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


def _tuple_mappings(value: Any) -> tuple[Mapping[str, Any], ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise TypeError("expected a list or tuple of objects")
    result = tuple(_mapping(item) for item in value)
    return result


@dataclass(frozen=True, slots=True)
class AuthorBook(_Record):
    record_type: ClassVar[str] = "AuthorBook"

    book_id: str
    title: str
    partition: str
    text_path: str
    text_hash: str
    metadata_sources: tuple[str, ...] = ()
    publication_year: int | None = None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("book_id", "title", "partition", "text_path", "schema_version"):
            _nonempty(name, getattr(self, name))
        if self.partition not in PARTITIONS:
            raise ValueError(f"unknown corpus partition: {self.partition}")
        _digest("text_hash", self.text_hash)
        _strings("metadata_sources", self.metadata_sources)
        if self.publication_year is not None and self.publication_year < 1:
            raise ValueError("publication_year must be positive or null")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AuthorBook":
        payload = cls._payload(data)
        payload["metadata_sources"] = _tuple_strings(
            payload.get("metadata_sources", ())
        )
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class AuthorCorpusManifest(_Record):
    record_type: ClassVar[str] = "AuthorCorpusManifest"

    manifest_id: str
    author_id: str
    author_name: str
    version: str
    books: tuple[AuthorBook, ...]
    privacy_boundary: str = "local-raw-hybrid-derived"
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "manifest_id",
            "author_id",
            "author_name",
            "version",
            "privacy_boundary",
            "schema_version",
        ):
            _nonempty(name, getattr(self, name))
        if len(self.books) < 3:
            raise ValueError("author corpus requires at least three books")
        ids = [book.book_id for book in self.books]
        if len(ids) != len(set(ids)):
            raise ValueError("author book IDs must be unique")
        partitions = [book.partition for book in self.books]
        if "holdout" not in partitions:
            raise ValueError("author corpus requires an untouched holdout book")
        if partitions.count("holdout") != 1:
            raise ValueError("author corpus must contain exactly one holdout book")
        if partitions.count("profiling") < 2:
            raise ValueError("author corpus requires at least two profiling books")
        expected = partition_plan(len(self.books))
        observed = {
            partition: partitions.count(partition) for partition in PARTITIONS
        }
        if observed != expected:
            raise ValueError(
                f"partition counts do not match the {len(self.books)}-book policy: "
                f"expected {expected}, observed {observed}"
            )

    @property
    def corpus_hash(self) -> str:
        return hash_json(self.to_dict())

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AuthorCorpusManifest":
        payload = cls._payload(data)
        raw_books = payload.get("books", ())
        if not isinstance(raw_books, (list, tuple)):
            raise TypeError("books must be a list")
        payload["books"] = tuple(
            item
            if isinstance(item, AuthorBook)
            else AuthorBook.from_dict(_mapping(item))
            for item in raw_books
        )
        return cls(**payload)


def partition_plan(book_count: int) -> dict[str, int]:
    """Return the deterministic book-level split from the approved design."""

    if book_count < 3:
        raise ValueError("at least three books are required")
    if book_count == 3:
        return {"profiling": 2, "calibration": 0, "holdout": 1}
    if book_count == 4:
        return {"profiling": 2, "calibration": 1, "holdout": 1}
    return {
        "profiling": book_count - 2,
        "calibration": 1,
        "holdout": 1,
    }


@dataclass(frozen=True, slots=True)
class SourceSegment(_Record):
    record_type: ClassVar[str] = "SourceSegment"

    segment_id: str
    book_id: str
    partition: str
    location: str
    text_hash: str
    word_count: int
    rgo_coordinates: tuple[str, ...] = ()
    anti_copy_indexed: bool = True
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "segment_id",
            "book_id",
            "partition",
            "location",
            "schema_version",
        ):
            _nonempty(name, getattr(self, name))
        if self.partition not in PARTITIONS:
            raise ValueError(f"unknown corpus partition: {self.partition}")
        _digest("text_hash", self.text_hash)
        if self.word_count <= 0:
            raise ValueError("word_count must be positive")
        _strings("rgo_coordinates", self.rgo_coordinates)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SourceSegment":
        payload = cls._payload(data)
        payload["rgo_coordinates"] = _tuple_strings(
            payload.get("rgo_coordinates", ())
        )
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class SceneContentGraph(_Record):
    record_type: ClassVar[str] = "SceneContentGraph"

    graph_id: str
    source_segment_id: str
    event_sequence: tuple[str, ...]
    knowledge_changes: tuple[str, ...]
    emotional_transactions: tuple[str, ...]
    character_decisions: tuple[str, ...]
    relationship_delta: str
    intimacy_mode: str
    discourse_function: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "graph_id",
            "source_segment_id",
            "relationship_delta",
            "intimacy_mode",
            "discourse_function",
            "schema_version",
        ):
            _nonempty(name, getattr(self, name))
        for name in (
            "event_sequence",
            "knowledge_changes",
            "emotional_transactions",
            "character_decisions",
        ):
            _strings(name, getattr(self, name), allow_empty=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SceneContentGraph":
        payload = cls._payload(data)
        for key in (
            "event_sequence",
            "knowledge_changes",
            "emotional_transactions",
            "character_decisions",
        ):
            payload[key] = _tuple_strings(payload.get(key, ()))
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class AuthorAffordance(_Record):
    record_type: ClassVar[str] = "AuthorAffordance"

    affordance_id: str
    axis: str
    claim: str
    activation_conditions: tuple[str, ...]
    prevalence: float
    strength: float
    distribution: Mapping[str, float | int | str]
    evidence_refs: tuple[str, ...]
    evidence_book_ids: tuple[str, ...]
    counterevidence_refs: tuple[str, ...]
    rgo_coordinates: tuple[str, ...]
    prompt_semantics: tuple[str, ...]
    evaluator_semantics: tuple[str, ...]
    confidence: float
    scope: str = "local-tendency"
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "affordance_id",
            "axis",
            "claim",
            "scope",
            "schema_version",
        ):
            _nonempty(name, getattr(self, name))
        if self.axis not in AFFORDANCE_AXES:
            raise ValueError(f"unknown author-affordance axis: {self.axis}")
        if self.scope not in {"local-tendency", "author-signature"}:
            raise ValueError("scope must be local-tendency or author-signature")
        for name in ("prevalence", "strength", "confidence"):
            value = float(getattr(self, name))
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        for name in (
            "activation_conditions",
            "evidence_refs",
            "evidence_book_ids",
            "counterevidence_refs",
            "rgo_coordinates",
            "prompt_semantics",
            "evaluator_semantics",
        ):
            _strings(name, getattr(self, name))
        if not self.evidence_refs or not self.evidence_book_ids:
            raise ValueError("affordances require evidence references and book IDs")
        if self.scope == "author-signature" and len(set(self.evidence_book_ids)) < 2:
            raise ValueError(
                "author-signature affordances require evidence from two books"
            )
        if not isinstance(self.distribution, Mapping):
            raise TypeError("distribution must be a mapping")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AuthorAffordance":
        payload = cls._payload(data)
        for key in (
            "activation_conditions",
            "evidence_refs",
            "evidence_book_ids",
            "counterevidence_refs",
            "rgo_coordinates",
            "prompt_semantics",
            "evaluator_semantics",
        ):
            payload[key] = _tuple_strings(payload.get(key, ()))
        payload["distribution"] = _mapping(payload.get("distribution"))
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class AuthorProfile(_Record):
    record_type: ClassVar[str] = "AuthorProfile"

    profile_id: str
    author_id: str
    author_name: str
    version: str
    corpus_manifest_hash: str
    affordances: tuple[AuthorAffordance, ...]
    author_subgenre_delta: tuple[str, ...]
    distributions: Mapping[str, Any]
    negative_space: tuple[str, ...]
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "profile_id",
            "author_id",
            "author_name",
            "version",
            "schema_version",
        ):
            _nonempty(name, getattr(self, name))
        _digest("corpus_manifest_hash", self.corpus_manifest_hash)
        if not self.affordances:
            raise ValueError("author profile requires at least one affordance")
        ids = [item.affordance_id for item in self.affordances]
        if len(ids) != len(set(ids)):
            raise ValueError("author affordance IDs must be unique")
        _strings("author_subgenre_delta", self.author_subgenre_delta)
        _strings("negative_space", self.negative_space)
        if not isinstance(self.distributions, Mapping):
            raise TypeError("distributions must be a mapping")

    @property
    def profile_hash(self) -> str:
        return hash_json(self.to_dict())

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AuthorProfile":
        payload = cls._payload(data)
        raw_affordances = payload.get("affordances", ())
        if not isinstance(raw_affordances, (list, tuple)):
            raise TypeError("affordances must be a list")
        payload["affordances"] = tuple(
            item
            if isinstance(item, AuthorAffordance)
            else AuthorAffordance.from_dict(_mapping(item))
            for item in raw_affordances
        )
        payload["author_subgenre_delta"] = _tuple_strings(
            payload.get("author_subgenre_delta", ())
        )
        payload["negative_space"] = _tuple_strings(
            payload.get("negative_space", ())
        )
        payload["distributions"] = _mapping(payload.get("distributions"))
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class TransformationMap(_Record):
    record_type: ClassVar[str] = "TransformationMap"

    map_id: str
    author_profile_id: str
    version: str
    rules: Mapping[str, str]
    target_semantics: Mapping[str, tuple[str, ...]]
    target_profile_hash: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("map_id", "author_profile_id", "version", "schema_version"):
            _nonempty(name, getattr(self, name))
        _digest("target_profile_hash", self.target_profile_hash)
        if not self.rules:
            raise ValueError("transformation map requires at least one rule")
        invalid = sorted(
            action
            for action in self.rules.values()
            if action not in TRANSFORMATION_ACTIONS
        )
        if invalid:
            raise ValueError(f"unknown transformation actions: {invalid}")
        unknown_targets = sorted(set(self.target_semantics) - set(self.rules))
        if unknown_targets:
            raise ValueError(
                "target_semantics references unknown affordances: "
                + ", ".join(unknown_targets)
            )
        for affordance_id, action in self.rules.items():
            semantics = self.target_semantics.get(affordance_id, ())
            _strings(f"target_semantics[{affordance_id}]", semantics)
            if action in {"transpose", "invert"} and not semantics:
                raise ValueError(
                    f"{action} rule for {affordance_id} requires positive "
                    "target_semantics"
                )

    @property
    def map_hash(self) -> str:
        return hash_json(self.to_dict())

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TransformationMap":
        payload = cls._payload(data)
        payload["rules"] = {
            str(key): str(value)
            for key, value in _mapping(payload.get("rules")).items()
        }
        payload["target_semantics"] = {
            str(key): _tuple_strings(value)
            for key, value in _mapping(payload.get("target_semantics")).items()
        }
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class StoryProgram(_Record):
    record_type: ClassVar[str] = "StoryProgram"

    story_program_id: str
    scene_id: str
    raw_proposal: str
    compiled_program: Mapping[str, Any]
    repairs: tuple[Mapping[str, Any], ...]
    selected_coordinates: tuple[str, ...]
    lineage: tuple[str, ...]
    author_profile_hash: str
    resolved_profile_hash: str
    valid: bool = True
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "story_program_id",
            "scene_id",
            "raw_proposal",
            "schema_version",
        ):
            _nonempty(name, getattr(self, name))
        _digest("author_profile_hash", self.author_profile_hash)
        _digest("resolved_profile_hash", self.resolved_profile_hash)
        if not isinstance(self.compiled_program, Mapping):
            raise TypeError("compiled_program must be a mapping")
        _strings("selected_coordinates", self.selected_coordinates)
        _strings("lineage", self.lineage, allow_empty=False)

    @property
    def program_hash(self) -> str:
        return hash_json(self.to_dict())

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StoryProgram":
        payload = cls._payload(data)
        payload["compiled_program"] = _mapping(payload.get("compiled_program"))
        payload["repairs"] = _tuple_mappings(payload.get("repairs", ()))
        payload["selected_coordinates"] = _tuple_strings(
            payload.get("selected_coordinates", ())
        )
        payload["lineage"] = _tuple_strings(payload.get("lineage", ()))
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class OverlapReport(_Record):
    record_type: ClassVar[str] = "OverlapReport"

    candidate_id: str
    policy_version: str
    index_hash: str
    exact_matches: tuple[Mapping[str, Any], ...]
    fuzzy_matches: tuple[Mapping[str, Any], ...]
    semantic_matches: tuple[Mapping[str, Any], ...]
    cross_candidate_matches: tuple[Mapping[str, Any], ...]
    hard_fail: bool
    unresolved_flags: bool
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "candidate_id",
            "policy_version",
            "schema_version",
        ):
            _nonempty(name, getattr(self, name))
        _digest("index_hash", self.index_hash)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "OverlapReport":
        payload = cls._payload(data)
        for key in (
            "exact_matches",
            "fuzzy_matches",
            "semantic_matches",
            "cross_candidate_matches",
        ):
            payload[key] = _tuple_mappings(payload.get(key, ()))
        return cls(**payload)


def resolve_book_path(manifest_path: Path, book: AuthorBook) -> Path:
    """Resolve a book path relative to its manifest without reading it."""

    path = Path(book.text_path)
    return path if path.is_absolute() else manifest_path.parent / path
