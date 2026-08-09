"""Deterministic experimental designs for author-conditioned generation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import product
from typing import Any, Mapping, Sequence

from .author import CONDITIONING_VARIANTS, CONTROL_DENSITY_LIMITS, PROMPT_ENCODINGS
from .core import hash_json


CALIBRATION_ENCODINGS = ("xml", "markdown", "json")
CALIBRATION_DENSITIES = ("organic", "light", "medium", "dense", "raw-rag")
CALIBRATION_CONDITIONING = (
    "none",
    "name-only",
    "anonymous-profile",
    "named-profile",
    "profile-sparse-exemplars",
    "plot-review-nshot",
    "dense-retrieval",
)


@dataclass(frozen=True, slots=True)
class ExperimentArm:
    arm_id: str
    phase: str
    prompt_encoding: str
    control_density: str
    conditioning_variant: str
    graph_id: str
    seed: int
    word_target: int
    shared_story_program_set: str

    def __post_init__(self) -> None:
        if self.prompt_encoding not in PROMPT_ENCODINGS:
            raise ValueError(f"unknown prompt encoding: {self.prompt_encoding}")
        if self.control_density not in CONTROL_DENSITY_LIMITS:
            raise ValueError(f"unknown control density: {self.control_density}")
        if self.conditioning_variant not in CONDITIONING_VARIANTS:
            raise ValueError(
                f"unknown conditioning variant: {self.conditioning_variant}"
            )
        if self.word_target <= 0:
            raise ValueError("word_target must be positive")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AuthorExperimentManifest:
    experiment_id: str
    version: str
    ontology_profile_hash: str
    author_profile_hash: str
    corpus_manifest_hash: str
    transformation_map_hash: str
    anti_copy_index_hash: str
    story_program_ids: tuple[str, ...]
    arms: tuple[ExperimentArm, ...]
    seeds: tuple[int, ...]
    holdout_policy: str = "never-prompt-retrieve-compile-or-tune"
    remote_boundary: str = "derived-profile-new-draft-defect-report-only"

    def __post_init__(self) -> None:
        for name in (
            "ontology_profile_hash",
            "author_profile_hash",
            "corpus_manifest_hash",
            "transformation_map_hash",
            "anti_copy_index_hash",
        ):
            value = getattr(self, name)
            if len(value) != 64:
                raise ValueError(f"{name} must be a SHA-256 digest")
        if len(set(self.story_program_ids)) != len(self.story_program_ids):
            raise ValueError("story program IDs must be unique")
        if not self.arms:
            raise ValueError("experiment manifest requires arms")

    @property
    def manifest_hash(self) -> str:
        return hash_json(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_type": "AuthorExperimentManifest",
            "experiment_id": self.experiment_id,
            "version": self.version,
            "ontology_profile_hash": self.ontology_profile_hash,
            "author_profile_hash": self.author_profile_hash,
            "corpus_manifest_hash": self.corpus_manifest_hash,
            "transformation_map_hash": self.transformation_map_hash,
            "anti_copy_index_hash": self.anti_copy_index_hash,
            "story_program_ids": list(self.story_program_ids),
            "arms": [arm.to_dict() for arm in self.arms],
            "seeds": list(self.seeds),
            "holdout_policy": self.holdout_policy,
            "remote_boundary": self.remote_boundary,
        }


def calibration_design(
    *,
    graph_ids: Sequence[str],
    seeds: Sequence[int],
    winning_encoding: str = "xml",
) -> tuple[ExperimentArm, ...]:
    if len(graph_ids) != 2:
        raise ValueError("encoding calibration requires exactly two content graphs")
    if len(seeds) != 4:
        raise ValueError("encoding calibration requires exactly four seeds")
    if winning_encoding not in CALIBRATION_ENCODINGS:
        raise ValueError("winning_encoding must be xml, markdown, or json")
    arms: list[ExperimentArm] = []
    for encoding, graph_id, seed in product(
        CALIBRATION_ENCODINGS, graph_ids, seeds
    ):
        arms.append(
            ExperimentArm(
                arm_id=f"encoding.{encoding}.{graph_id}.{seed}",
                phase="prompt-encoding",
                prompt_encoding=encoding,
                control_density="medium",
                conditioning_variant="anonymous-profile",
                graph_id=graph_id,
                seed=int(seed),
                word_target=900,
                shared_story_program_set=f"calibration.{graph_id}",
            )
        )
    for density in CALIBRATION_DENSITIES:
        for graph_id, seed in product(graph_ids, seeds):
            variant = "raw-rag" if density == "raw-rag" else "anonymous-profile"
            arms.append(
                ExperimentArm(
                    arm_id=f"density.{density}.{graph_id}.{seed}",
                    phase="control-density",
                    prompt_encoding=winning_encoding,
                    control_density=density,
                    conditioning_variant=variant,
                    graph_id=graph_id,
                    seed=int(seed),
                    word_target=900,
                    shared_story_program_set=f"calibration.{graph_id}",
                )
            )
    for variant in CALIBRATION_CONDITIONING:
        for graph_id, seed in product(graph_ids, seeds):
            density = "dense" if variant == "dense-retrieval" else "medium"
            arms.append(
                ExperimentArm(
                    arm_id=f"conditioning.{variant}.{graph_id}.{seed}",
                    phase="author-conditioning",
                    prompt_encoding=winning_encoding,
                    control_density=density,
                    conditioning_variant=variant,
                    graph_id=graph_id,
                    seed=int(seed),
                    word_target=900,
                    shared_story_program_set=f"calibration.{graph_id}",
                )
            )
    return tuple(arms)


def full_s01_design(
    *,
    winning_encoding: str,
    winning_variants: Sequence[str],
    story_program_ids: Sequence[str],
    seeds: Sequence[int],
) -> tuple[ExperimentArm, ...]:
    if len(winning_variants) != 2:
        raise ValueError("advance exactly two author-conditioning variants")
    if len(story_program_ids) != 8:
        raise ValueError("full S01 comparison requires eight shared story programs")
    if len(seeds) != 8:
        raise ValueError("full S01 comparison requires eight fixed seeds")
    variants = tuple(winning_variants) + ("none",)
    arms: list[ExperimentArm] = []
    for variant in variants:
        for index, (program_id, seed) in enumerate(
            zip(story_program_ids, seeds), 1
        ):
            arms.append(
                ExperimentArm(
                    arm_id=f"s01.base.{variant}.{index:02d}",
                    phase="full-s01",
                    prompt_encoding=winning_encoding,
                    control_density="medium",
                    conditioning_variant=variant,
                    graph_id="s01",
                    seed=int(seed),
                    word_target=3200,
                    shared_story_program_set=program_id,
                )
            )
    for index, (program_id, seed) in enumerate(zip(story_program_ids, seeds), 1):
        arms.append(
            ExperimentArm(
                arm_id=f"s01.instruction-control.{index:02d}",
                phase="full-s01-instruction-control",
                prompt_encoding=winning_encoding,
                control_density="organic",
                conditioning_variant="none",
                graph_id="s01",
                seed=int(seed),
                word_target=3200,
                shared_story_program_set=program_id,
            )
        )
    return tuple(arms)


def verify_shared_story_programs(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Detect plot confounding across conditioning arms."""

    by_key: dict[tuple[str, int], set[str]] = {}
    for record in records:
        key = (str(record["graph_id"]), int(record["seed"]))
        by_key.setdefault(key, set()).add(
            str(record["shared_story_program_set"])
        )
    violations = [
        {"graph_id": graph, "seed": seed, "program_sets": sorted(values)}
        for (graph, seed), values in sorted(by_key.items())
        if len(values) != 1
    ]
    return {
        "passed": not violations,
        "comparisons": len(by_key),
        "violations": violations,
    }
