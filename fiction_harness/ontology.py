"""Versioned, faceted Romance Generation Ontology (RGO).

RGO is deliberately an internal creative-control vocabulary.  Retail
classifications are attached as versioned mappings, never used as generation
semantics.  Profiles are resolved before inference so every downstream
artifact can carry one deterministic profile hash.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
import copy
import json
from pathlib import Path
from typing import Any, ClassVar, Iterable, Mapping, Sequence

from .core import canonical_json_text, hash_json, to_plain_data, write_json
from .schemas import SCHEMA_VERSION


ONTOLOGY_RECORD_VERSION = "rgo-records.v1"
DEFAULT_ONTOLOGY_PATH = (
    Path(__file__).with_name("ontology_data") / "romance_generation_ontology.v1.json"
)
DEFAULT_STORY_PROFILE_PATH = (
    Path(__file__).with_name("profiles") / "stories" / "fulcrum_pilot.v1.json"
)
DEFAULT_SCENE_PROFILE_PATH = (
    Path(__file__).with_name("profiles") / "scenes" / "s01.v1.json"
)

PROFILE_DEFECTS = (
    "missing_required_coordinate",
    "profile_contradiction",
    "trope_presence_without_engine",
    "heat_target_miss",
    "heat_ceiling_violation",
    "consent_mode_mismatch",
    "relationship_delta_missing",
    "world_status_collapse",
    "intimacy_mode_mismatch",
)

PROTECTED_NAMESPACES = {"contract", "consent", "relationship"}
SCENE_OVERRIDE_NAMESPACES = {"heat", "intimacy-craft", "trope", "tone", "world"}


def _nonempty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _tuple_strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise TypeError("expected a list or tuple of strings")
    result = tuple(value)
    if any(not isinstance(item, str) for item in result):
        raise TypeError("expected a list or tuple of strings")
    return result


def _tuple_mappings(value: Any) -> tuple[dict[str, Any], ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise TypeError("expected a list or tuple of mappings")
    result: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise TypeError("expected a list or tuple of mappings")
        result.append({str(key): entry for key, entry in item.items()})
    return tuple(result)


def _ordered_union(*collections: Iterable[str]) -> tuple[str, ...]:
    ordered: dict[str, None] = {}
    for collection in collections:
        for item in collection:
            ordered[str(item)] = None
    return tuple(ordered)


class _StrictRecord:
    record_type: ClassVar[str]

    def to_dict(self) -> dict[str, Any]:
        value = to_plain_data(self)
        value["record_type"] = self.record_type
        return value

    @classmethod
    def _payload(cls, data: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(data)
        record_type = payload.pop("record_type", cls.record_type)
        if record_type != cls.record_type:
            raise ValueError(
                f"expected record_type {cls.record_type!r}, got {record_type!r}"
            )
        allowed = {field.name for field in fields(cls)}
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise ValueError(
                f"unknown {cls.record_type} fields: {', '.join(unknown)}"
            )
        return payload


@dataclass(frozen=True, slots=True)
class OntologyNode(_StrictRecord):
    record_type: ClassVar[str] = "OntologyNode"

    id: str
    namespace: str
    label: str
    description: str
    parents: tuple[str, ...] = ()
    prompt_semantics: tuple[str, ...] = ()
    evaluation_semantics: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()
    excludes: tuple[str, ...] = ()
    implies: tuple[str, ...] = ()
    external_mappings: tuple[Mapping[str, Any], ...] = ()
    attributes: Mapping[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        for name in ("id", "namespace", "label", "description"):
            _nonempty(name, getattr(self, name))
        if not self.id.startswith(self.namespace + "."):
            raise ValueError(
                f"node {self.id!r} must begin with namespace {self.namespace!r}"
            )
        for name in (
            "parents",
            "prompt_semantics",
            "evaluation_semantics",
            "requires",
            "excludes",
            "implies",
        ):
            value = getattr(self, name)
            if not isinstance(value, tuple) or any(
                not isinstance(item, str) for item in value
            ):
                raise TypeError(f"{name} must be a tuple of strings")
        if self.attributes is None:
            object.__setattr__(self, "attributes", {})
        if not isinstance(self.attributes, Mapping):
            raise TypeError("attributes must be a mapping")
        for mapping in self.external_mappings:
            for key in ("scheme", "version", "code", "label"):
                _nonempty(f"external_mappings.{key}", str(mapping.get(key, "")))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "OntologyNode":
        payload = cls._payload(data)
        for key in (
            "parents",
            "prompt_semantics",
            "evaluation_semantics",
            "requires",
            "excludes",
            "implies",
        ):
            payload[key] = _tuple_strings(payload.get(key))
        payload["external_mappings"] = _tuple_mappings(
            payload.get("external_mappings")
        )
        attributes = payload.get("attributes", {})
        if not isinstance(attributes, Mapping):
            raise TypeError("attributes must be a mapping")
        payload["attributes"] = dict(attributes)
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class StoryProfile(_StrictRecord):
    record_type: ClassVar[str] = "StoryProfile"

    profile_id: str
    ontology_version: str
    primary_genre: str = ""
    secondary_genres: tuple[str, ...] = ()
    contract: str = ""
    coordinates: tuple[str, ...] = ()
    required: tuple[str, ...] = ()
    preferred: tuple[str, ...] = ()
    prohibited: tuple[str, ...] = ()
    heat_ceiling: str = ""
    relationship_trajectory: str = ""
    extends: str = ""
    version: str = "1"
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("profile_id", "ontology_version", "version", "schema_version"):
            _nonempty(name, getattr(self, name))
        for name in (
            "secondary_genres",
            "coordinates",
            "required",
            "preferred",
            "prohibited",
        ):
            value = getattr(self, name)
            if not isinstance(value, tuple) or any(
                not isinstance(item, str) for item in value
            ):
                raise TypeError(f"{name} must be a tuple of strings")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StoryProfile":
        payload = cls._payload(data)
        for key in (
            "secondary_genres",
            "coordinates",
            "required",
            "preferred",
            "prohibited",
        ):
            payload[key] = _tuple_strings(payload.get(key))
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class SceneCreativeProfile(_StrictRecord):
    record_type: ClassVar[str] = "SceneCreativeProfile"

    scene_profile_id: str
    story_profile_id: str
    ontology_version: str
    scene_id: str
    coordinates: tuple[str, ...] = ()
    required: tuple[str, ...] = ()
    preferred: tuple[str, ...] = ()
    prohibited: tuple[str, ...] = ()
    remove_coordinates: tuple[str, ...] = ()
    heat_target: str = ""
    intimacy_modes: tuple[str, ...] = ()
    manifested_tropes: tuple[str, ...] = ()
    pacing: tuple[str, ...] = ()
    tone: tuple[str, ...] = ()
    atmosphere: str = ""
    relationship_result: str = ""
    version: str = "1"
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "scene_profile_id",
            "story_profile_id",
            "ontology_version",
            "scene_id",
            "version",
            "schema_version",
        ):
            _nonempty(name, getattr(self, name))
        for name in (
            "coordinates",
            "required",
            "preferred",
            "prohibited",
            "remove_coordinates",
            "intimacy_modes",
            "manifested_tropes",
            "pacing",
            "tone",
        ):
            value = getattr(self, name)
            if not isinstance(value, tuple) or any(
                not isinstance(item, str) for item in value
            ):
                raise TypeError(f"{name} must be a tuple of strings")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SceneCreativeProfile":
        payload = cls._payload(data)
        for key in (
            "coordinates",
            "required",
            "preferred",
            "prohibited",
            "remove_coordinates",
            "intimacy_modes",
            "manifested_tropes",
            "pacing",
            "tone",
        ):
            payload[key] = _tuple_strings(payload.get(key))
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class ResolvedCreativeProfile(_StrictRecord):
    record_type: ClassVar[str] = "ResolvedCreativeProfile"

    profile_id: str
    story_profile_id: str
    scene_profile_id: str
    scene_id: str
    ontology_version: str
    ontology_hash: str
    primary_genre: str
    secondary_genres: tuple[str, ...]
    contract: str
    selected_coordinates: tuple[str, ...]
    required: tuple[str, ...]
    preferred: tuple[str, ...]
    prohibited: tuple[str, ...]
    heat_ceiling: str
    heat_target: str
    relationship_trajectory: str
    relationship_result: str
    prompt_obligations: tuple[str, ...]
    evaluation_obligations: tuple[str, ...]
    external_mappings: tuple[Mapping[str, Any], ...]
    pacing: tuple[str, ...]
    atmosphere: str
    profile_hash: str
    warnings: tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "profile_id",
            "story_profile_id",
            "scene_id",
            "ontology_version",
            "ontology_hash",
            "primary_genre",
            "contract",
            "heat_ceiling",
            "relationship_trajectory",
            "profile_hash",
            "schema_version",
        ):
            _nonempty(name, getattr(self, name))
        if len(self.ontology_hash) != 64 or len(self.profile_hash) != 64:
            raise ValueError("ontology_hash and profile_hash must be SHA-256 digests")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ResolvedCreativeProfile":
        payload = cls._payload(data)
        for key in (
            "secondary_genres",
            "selected_coordinates",
            "required",
            "preferred",
            "prohibited",
            "prompt_obligations",
            "evaluation_obligations",
            "pacing",
            "warnings",
        ):
            payload[key] = _tuple_strings(payload.get(key))
        payload["external_mappings"] = _tuple_mappings(
            payload.get("external_mappings")
        )
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class OntologyCatalog:
    ontology_id: str
    version: str
    namespaces: Mapping[str, Mapping[str, Any]]
    defaults: tuple[str, ...]
    nodes: Mapping[str, OntologyNode]
    ontology_hash: str

    def node(self, node_id: str) -> OntologyNode:
        try:
            return self.nodes[node_id]
        except KeyError as exc:
            raise ValueError(f"unknown RGO coordinate: {node_id}") from exc


def _validate_catalog(catalog: OntologyCatalog) -> None:
    node_ids = set(catalog.nodes)
    namespaces = set(catalog.namespaces)
    for node in catalog.nodes.values():
        if node.namespace not in namespaces:
            raise ValueError(
                f"node {node.id} uses undeclared namespace {node.namespace}"
            )
        for relation in (*node.parents, *node.requires, *node.excludes, *node.implies):
            if relation not in node_ids:
                raise ValueError(f"node {node.id} references unknown node {relation}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise ValueError(f"ontology parent cycle includes {node_id}")
        if node_id in visited:
            return
        visiting.add(node_id)
        for parent in catalog.nodes[node_id].parents:
            visit(parent)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in sorted(node_ids):
        visit(node_id)
    for default in catalog.defaults:
        catalog.node(default)


def load_ontology(path: str | Path = DEFAULT_ONTOLOGY_PATH) -> OntologyCatalog:
    source = Path(path)
    data = json.loads(source.read_text(encoding="utf-8"))
    allowed = {"ontology_id", "version", "namespaces", "defaults", "nodes"}
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ValueError(f"unknown ontology fields: {', '.join(unknown)}")
    _nonempty("ontology_id", str(data.get("ontology_id", "")))
    _nonempty("version", str(data.get("version", "")))
    namespaces = data.get("namespaces")
    if not isinstance(namespaces, Mapping) or not namespaces:
        raise ValueError("ontology namespaces must be a non-empty mapping")
    raw_nodes = data.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise ValueError("ontology nodes must be a non-empty array")
    parsed = [OntologyNode.from_dict(item) for item in raw_nodes]
    ids = [node.id for node in parsed]
    if len(set(ids)) != len(ids):
        duplicate = next(node_id for node_id in ids if ids.count(node_id) > 1)
        raise ValueError(f"duplicate ontology node ID: {duplicate}")
    canonical = {
        "ontology_id": data["ontology_id"],
        "version": data["version"],
        "namespaces": data["namespaces"],
        "defaults": data.get("defaults", []),
        "nodes": [node.to_dict() for node in parsed],
    }
    catalog = OntologyCatalog(
        ontology_id=str(data["ontology_id"]),
        version=str(data["version"]),
        namespaces={
            str(key): dict(value) for key, value in namespaces.items()
        },
        defaults=_tuple_strings(data.get("defaults")),
        nodes={node.id: node for node in parsed},
        ontology_hash=hash_json(canonical),
    )
    _validate_catalog(catalog)
    return catalog


def _read_story_profile_layer(
    path: Path, *, seen: set[Path] | None = None
) -> tuple[StoryProfile, ...]:
    resolved = path.resolve()
    active = set(seen or ())
    if resolved in active:
        raise ValueError(f"story-profile inheritance cycle includes {resolved}")
    active.add(resolved)
    profile = StoryProfile.from_dict(
        json.loads(resolved.read_text(encoding="utf-8"))
    )
    if not profile.extends:
        return (profile,)
    base = (resolved.parent / profile.extends).resolve()
    if not base.is_file():
        raise FileNotFoundError(base)
    return (*_read_story_profile_layer(base, seen=active), profile)


def load_story_profile(path: str | Path) -> tuple[StoryProfile, ...]:
    return _read_story_profile_layer(Path(path))


def load_scene_profile(path: str | Path) -> SceneCreativeProfile:
    return SceneCreativeProfile.from_dict(
        json.loads(Path(path).read_text(encoding="utf-8"))
    )


def _merge_story_layers(layers: Sequence[StoryProfile]) -> StoryProfile:
    if not layers:
        raise ValueError("at least one story profile layer is required")
    ontology_versions = {layer.ontology_version for layer in layers}
    if len(ontology_versions) != 1:
        raise ValueError("story profile layers use different ontology versions")
    leaf = layers[-1]

    def scalar(name: str) -> str:
        return next(
            (
                str(getattr(layer, name))
                for layer in reversed(layers)
                if str(getattr(layer, name)).strip()
            ),
            "",
        )

    return StoryProfile(
        profile_id=leaf.profile_id,
        ontology_version=leaf.ontology_version,
        primary_genre=scalar("primary_genre"),
        secondary_genres=_ordered_union(
            *(layer.secondary_genres for layer in layers)
        ),
        contract=scalar("contract"),
        coordinates=_ordered_union(*(layer.coordinates for layer in layers)),
        required=_ordered_union(*(layer.required for layer in layers)),
        preferred=_ordered_union(*(layer.preferred for layer in layers)),
        prohibited=_ordered_union(*(layer.prohibited for layer in layers)),
        heat_ceiling=scalar("heat_ceiling"),
        relationship_trajectory=scalar("relationship_trajectory"),
        extends="",
        version=leaf.version,
    )


def _ancestor_ids(catalog: OntologyCatalog, node_id: str) -> set[str]:
    result: set[str] = set()
    stack = list(catalog.node(node_id).parents)
    while stack:
        parent = stack.pop()
        if parent in result:
            continue
        result.add(parent)
        stack.extend(catalog.node(parent).parents)
    return result


def _semantic_nodes(
    catalog: OntologyCatalog, selected: Sequence[str]
) -> list[OntologyNode]:
    ordered: list[OntologyNode] = []
    seen: set[str] = set()

    def add(node_id: str) -> None:
        for parent in catalog.node(node_id).parents:
            add(parent)
        if node_id not in seen:
            ordered.append(catalog.node(node_id))
            seen.add(node_id)

    for coordinate in selected:
        add(coordinate)
    return ordered


def _closure(catalog: OntologyCatalog, coordinates: Iterable[str]) -> tuple[str, ...]:
    result = list(dict.fromkeys(coordinates))
    index = 0
    while index < len(result):
        node = catalog.node(result[index])
        for related in (*node.requires, *node.implies):
            if related not in result:
                result.append(related)
        index += 1
    return tuple(result)


def _validate_cardinality(
    catalog: OntologyCatalog, selected: Sequence[str]
) -> None:
    counts: dict[str, int] = {}
    for node_id in selected:
        namespace = catalog.node(node_id).namespace
        counts[namespace] = counts.get(namespace, 0) + 1
    for namespace, rules in catalog.namespaces.items():
        minimum = int(rules.get("min", 0))
        maximum = rules.get("max")
        observed = counts.get(namespace, 0)
        if observed < minimum:
            raise ValueError(
                f"namespace {namespace} requires at least {minimum} selection(s)"
            )
        if maximum is not None and observed > int(maximum):
            raise ValueError(
                f"namespace {namespace} allows at most {maximum} selection(s)"
            )


def resolve_profiles(
    catalog: OntologyCatalog,
    story_layers: Sequence[StoryProfile],
    scene: SceneCreativeProfile | None = None,
) -> ResolvedCreativeProfile:
    story = _merge_story_layers(story_layers)
    if story.ontology_version != catalog.version:
        raise ValueError(
            f"story profile expects {story.ontology_version}, catalog is {catalog.version}"
        )
    if scene is not None:
        if scene.ontology_version != catalog.version:
            raise ValueError("scene profile and ontology versions differ")
        if scene.story_profile_id != story.profile_id:
            raise ValueError(
                "scene profile story_profile_id does not match resolved story profile"
            )

    for field_name in (
        "primary_genre",
        "contract",
        "heat_ceiling",
        "relationship_trajectory",
    ):
        _nonempty(f"resolved story {field_name}", getattr(story, field_name))

    story_selected = _ordered_union(
        catalog.defaults,
        (story.primary_genre,),
        story.secondary_genres,
        (story.contract, story.heat_ceiling, story.relationship_trajectory),
        story.coordinates,
    )
    for coordinate in story_selected:
        catalog.node(coordinate)

    if scene is not None:
        for coordinate in scene.remove_coordinates:
            node = catalog.node(coordinate)
            if (
                node.namespace in PROTECTED_NAMESPACES
                or coordinate in {
                    story.primary_genre,
                    story.contract,
                    story.heat_ceiling,
                    story.relationship_trajectory,
                }
            ):
                raise ValueError(
                    f"scene profile may not remove protected coordinate {coordinate}"
                )
        retained = tuple(
            coordinate
            for coordinate in story_selected
            if coordinate not in set(scene.remove_coordinates)
        )
        additions = _ordered_union(
            scene.coordinates,
            (scene.heat_target,) if scene.heat_target else (),
            scene.intimacy_modes,
            scene.manifested_tropes,
            scene.tone,
        )
        for coordinate in additions:
            node = catalog.node(coordinate)
            if node.namespace not in SCENE_OVERRIDE_NAMESPACES:
                raise ValueError(
                    f"scene profile may not add {node.namespace} coordinate {coordinate}"
                )
        selected = _closure(catalog, _ordered_union(retained, additions))
    else:
        selected = _closure(catalog, story_selected)

    required = _ordered_union(
        story.required, scene.required if scene is not None else ()
    )
    preferred = _ordered_union(
        story.preferred, scene.preferred if scene is not None else ()
    )
    prohibited = _ordered_union(
        story.prohibited, scene.prohibited if scene is not None else ()
    )
    for collection_name, collection in (
        ("required", required),
        ("preferred", preferred),
        ("prohibited", prohibited),
    ):
        for coordinate in collection:
            try:
                catalog.node(coordinate)
            except ValueError as exc:
                raise ValueError(
                    f"{collection_name} contains {coordinate}: {exc}"
                ) from exc

    missing_required = sorted(set(required) - set(selected))
    if missing_required:
        raise ValueError(
            f"required coordinates are not selected: {', '.join(missing_required)}"
        )
    forbidden = sorted(set(selected) & set(prohibited))
    if forbidden:
        raise ValueError(
            f"selected coordinates are prohibited: {', '.join(forbidden)}"
        )
    for coordinate in selected:
        conflicts = set(catalog.node(coordinate).excludes) & set(selected)
        if conflicts:
            raise ValueError(
                f"{coordinate} excludes selected coordinate(s): "
                + ", ".join(sorted(conflicts))
            )
    for coordinate in selected:
        ancestors = _ancestor_ids(catalog, coordinate)
        redundant = ancestors & set(selected)
        if redundant:
            raise ValueError(
                f"redundant ancestor and descendant selected: "
                f"{coordinate} with {', '.join(sorted(redundant))}"
            )
    _validate_cardinality(catalog, selected)

    heat_ceiling = catalog.node(story.heat_ceiling)
    if heat_ceiling.namespace != "heat":
        raise ValueError("story heat_ceiling must be a heat coordinate")
    heat_target_id = scene.heat_target if scene is not None else ""
    if heat_target_id:
        heat_target = catalog.node(heat_target_id)
        if heat_target.namespace != "heat":
            raise ValueError("scene heat_target must be a heat coordinate")
        ceiling_rank = int(heat_ceiling.attributes.get("heat_rank", -1))
        target_rank = int(heat_target.attributes.get("heat_rank", -1))
        if min(ceiling_rank, target_rank) < 0:
            raise ValueError("heat ceiling and target require heat_rank attributes")
        if target_rank > ceiling_rank:
            raise ValueError(
                f"scene heat target {heat_target_id} exceeds {story.heat_ceiling}"
            )

    semantic_nodes = _semantic_nodes(catalog, selected)
    prompt_obligations = _ordered_union(
        *(
            node.prompt_semantics
            for node in semantic_nodes
            if node.namespace != "market"
        )
    )
    evaluation_obligations = _ordered_union(
        *(
            node.evaluation_semantics
            for node in semantic_nodes
            if node.namespace != "market"
        )
    )
    external_mappings: list[Mapping[str, Any]] = []
    seen_mappings: set[tuple[str, str, str]] = set()
    for node in semantic_nodes:
        for mapping in node.external_mappings:
            key = (
                str(mapping["scheme"]),
                str(mapping["version"]),
                str(mapping["code"]),
            )
            if key not in seen_mappings:
                external_mappings.append(dict(mapping))
                seen_mappings.add(key)

    payload = {
        "profile_id": f"{story.profile_id}:{scene.scene_profile_id if scene else 'story'}",
        "story_profile_id": story.profile_id,
        "scene_profile_id": scene.scene_profile_id if scene else "",
        "scene_id": scene.scene_id if scene else "STORY",
        "ontology_version": catalog.version,
        "ontology_hash": catalog.ontology_hash,
        "primary_genre": story.primary_genre,
        "secondary_genres": list(story.secondary_genres),
        "contract": story.contract,
        "selected_coordinates": list(selected),
        "required": list(required),
        "preferred": list(preferred),
        "prohibited": list(prohibited),
        "heat_ceiling": story.heat_ceiling,
        "heat_target": heat_target_id,
        "relationship_trajectory": story.relationship_trajectory,
        "relationship_result": scene.relationship_result if scene else "",
        "prompt_obligations": list(prompt_obligations),
        "evaluation_obligations": list(evaluation_obligations),
        "external_mappings": list(external_mappings),
        "pacing": list(scene.pacing if scene else ()),
        "atmosphere": scene.atmosphere if scene else "",
        "warnings": [],
        "schema_version": SCHEMA_VERSION,
    }
    profile_hash = hash_json(payload)
    return ResolvedCreativeProfile.from_dict(
        {
            **payload,
            "record_type": ResolvedCreativeProfile.record_type,
            "profile_hash": profile_hash,
        }
    )


def resolve_profile_files(
    *,
    ontology_path: str | Path = DEFAULT_ONTOLOGY_PATH,
    story_profile_path: str | Path = DEFAULT_STORY_PROFILE_PATH,
    scene_profile_path: str | Path | None = DEFAULT_SCENE_PROFILE_PATH,
) -> tuple[OntologyCatalog, ResolvedCreativeProfile]:
    catalog = load_ontology(ontology_path)
    layers = load_story_profile(story_profile_path)
    scene = load_scene_profile(scene_profile_path) if scene_profile_path else None
    return catalog, resolve_profiles(catalog, layers, scene)


def profile_prompt_text(profile: ResolvedCreativeProfile) -> str:
    """Render positive creative obligations without retail metadata."""

    payload = {
        "creative_contract": {
            "primary_genre": profile.primary_genre,
            "secondary_genres": list(profile.secondary_genres),
            "contract": profile.contract,
            "relationship_trajectory": profile.relationship_trajectory,
            "relationship_result_for_this_scene": profile.relationship_result,
            "heat_ceiling": profile.heat_ceiling,
            "heat_target": profile.heat_target,
        },
        "selected_coordinates": list(profile.selected_coordinates),
        "required_coordinates": list(profile.required),
        "preferred_coordinates": list(profile.preferred),
        "positive_scene_obligations": list(profile.prompt_obligations),
        "pacing": list(profile.pacing),
        "atmosphere": profile.atmosphere,
        "instruction": (
            "Realize these coordinates through causal action, attention, dialogue, "
            "and choice. Do not name the ontology or retail categories in the prose."
        ),
    }
    return "<RESOLVED_CREATIVE_PROFILE>\n" + canonical_json_text(payload)


def profile_evaluation_overlay(profile: ResolvedCreativeProfile) -> dict[str, Any]:
    return {
        "profile_id": profile.profile_id,
        "profile_hash": profile.profile_hash,
        "required_coordinates": list(profile.required),
        "preferred_coordinates": list(profile.preferred),
        "heat_ceiling": profile.heat_ceiling,
        "heat_target": profile.heat_target,
        "relationship_result": profile.relationship_result,
        "evaluation_obligations": list(profile.evaluation_obligations),
        "defect_taxonomy": list(PROFILE_DEFECTS),
    }


def profile_aware_rubric(
    rubric: Mapping[str, Any],
    profile: ResolvedCreativeProfile | None,
) -> dict[str, Any]:
    result = copy.deepcopy(dict(rubric))
    if profile is None:
        return result
    taxonomy = list(result.get("defect_taxonomy", ()))
    result["defect_taxonomy"] = list(dict.fromkeys((*taxonomy, *PROFILE_DEFECTS)))
    diagnostics = dict(result.get("romance_diagnostics", {}))
    diagnostics.update(
        {
            "required_coordinates": (
                "Do the required profile coordinates operate causally on the page?"
            ),
            "trope_engines": (
                "Do selected tropes change action, knowledge, desire, or future possibility?"
            ),
            "heat_consent_darkness": (
                "Do heat, consent, and darkness independently match the resolved profile?"
            ),
            "profile_relationship_delta": (
                "Does the relationship end in the profile's specified scene result?"
            ),
            "profile_intimacy_mode": (
                "Does contact follow the selected intimacy mode and change the story?"
            ),
            "profile_world_status": (
                "Does the scene preserve the selected world and supernatural status?"
            ),
            "profile_faith_causality": (
                "Do selected faith coordinates act through character, freedom, and consequence?"
            ),
        }
    )
    result["romance_diagnostics"] = diagnostics
    result["profile_overlay"] = profile_evaluation_overlay(profile)
    priorities = list(result.get("pairwise_priorities", ()))
    priorities.extend(
        [
            "Prefer causal realization of required creative coordinates over merely naming or signaling a trope.",
            "Treat the resolved heat target, consent mode, relationship result, intimacy mode, and world status as independent constraints.",
        ]
    )
    result["pairwise_priorities"] = list(dict.fromkeys(priorities))
    return result


def write_resolved_profile(
    path: str | Path, profile: ResolvedCreativeProfile
) -> None:
    write_json(path, profile.to_dict())
