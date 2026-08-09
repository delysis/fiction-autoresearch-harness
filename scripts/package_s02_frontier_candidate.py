#!/usr/bin/env python3
"""Package and gate the reviewed Codex novelist S02 boundary candidate."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fiction_harness.cli import _continuation_anti_copy_index  # noqa: E402
from fiction_harness.continuation import (  # noqa: E402
    ApprovedPrefix,
    S02_MACRO_SEQUENCES,
    continuation_gates,
    literary_scene_spec,
    load_s02_compilation,
)
from fiction_harness.core import hash_file, sha256_text, write_json  # noqa: E402
from fiction_harness.evaluation import (  # noqa: E402
    integrated_style_discontinuity_diagnostics,
    literary_style_diagnostics,
    word_count,
)
from fiction_harness.schemas import Candidate  # noqa: E402


RUN_ROOT = PROJECT_ROOT / "03_scene_lab/runs/s02-compute-v4.3-a4b"
ARM_ROOT = RUN_ROOT / "verbalized_to_instruction"
SAMPLE_ROOT = RUN_ROOT / "frontier_novelist"
COMPILED_ROOT = PROJECT_ROOT / "03_scene_lab/compiled/s02-v1-ontology"


def main() -> None:
    compact = json.loads(
        (RUN_ROOT / "context/compact_context.v1.json").read_text(encoding="utf-8")
    )
    config = json.loads((ARM_ROOT / "run_config.json").read_text(encoding="utf-8"))
    atom_artifact = json.loads(
        (ARM_ROOT / "dramatic_atoms.seq1.v1.json").read_text(encoding="utf-8")
    )
    sequence_texts = [
        (SAMPLE_ROOT / f"seq{index}.codex.v1.md").read_text(encoding="utf-8").strip()
        for index in (1, 2, 3)
    ]
    continuation = "\n\n".join(sequence_texts).strip()
    approved_data = compact["approved_prefix"]
    approved = ApprovedPrefix(
        label="B",
        candidate_id=str(approved_data["id"]).split(":", 1)[-1],
        text=str(approved_data["full_text"]),
        text_hash=str(approved_data["hash"]),
    )
    source_scene, _, _, _ = load_s02_compilation(COMPILED_ROOT)
    scene = literary_scene_spec(source_scene)
    anti_copy_index = _continuation_anti_copy_index(
        COMPILED_ROOT,
        approved_prefix_id=approved.approved_prefix_id,
        approved_prefix_text=approved.text,
    )
    merged = approved.text.rstrip() + "\n\n" + continuation
    bundle = atom_artifact["bundle"]
    candidate = Candidate(
        candidate_id="s02-frontier-novelist-codex-v1",
        run_id="s02-compute-v4.3-a4b-frontier-novelist",
        pipeline="frontier_novelist",
        scene_id="S02",
        seed=22063,
        text=merged,
        continuation_text=continuation,
        parent_trace={
            "macro_sequences": [
                {
                    **asdict(sequence),
                    "actual_words": word_count(text),
                }
                for sequence, text in zip(S02_MACRO_SEQUENCES, sequence_texts)
            ],
            "atom_bundle_id": bundle["bundle_id"],
            "atom_bundle_hash": bundle["bundle_hash"],
            "source_atom_pool_hash": bundle["source_pool_hash"],
            "novelist_boundary": "codex-agent-manual-boundary.v1",
        },
        evidence_ids=tuple(scene.source_ids),
        telemetry={
            "model": "codex-agent",
            "model_role": "frontier_novelist",
            "continuation_words": word_count(continuation),
            "merged_words": word_count(merged),
        },
        lineage=(
            "artifact:dramatic_atoms.seq1.v1.json",
            "artifact:novelist_packet.seq1.v1.json",
            "review:historical-independence-claim-unverified",
        ),
        prompt_hash=str(
            json.loads(
                (ARM_ROOT / "novelist_packet.seq1.v1.json").read_text(
                    encoding="utf-8"
                )
            )["packet_hash"]
        ),
        ontology_version=str(config["ontology_version"]),
        story_profile_id=str(config["story_profile_id"]),
        scene_profile_id=str(config["scene_profile_id"]),
        resolved_profile_hash=str(config["resolved_profile_hash"]),
        author_profile_id=str(config["author_profile_id"]),
        author_profile_hash=str(config["author_profile_hash"]),
        corpus_manifest_hash=str(config["corpus_manifest_hash"]),
        transformation_map_hash=str(config["transformation_map_hash"]),
        conditioning_variant=str(config["conditioning_variant"]),
        prompt_encoding=str(config["prompt_encoding"]),
        control_density=str(config["control_density"]),
        story_program_id=str(bundle["bundle_id"]),
        anti_copy_policy_version=anti_copy_index.policy.version,
        anti_copy_index_hash=anti_copy_index.index_hash,
        frontier_adapter="codex-agent-manual-boundary.v1",
        approved_prefix_id=approved.approved_prefix_id,
        approved_prefix_hash=approved.text_hash,
        feedback_brief_hash=str(config["feedback_brief_hash"]),
        generation_mode="frontier_novelist",
        artifact_authorship={
            "record_type": "ArtifactAuthorship",
            "schema_version": "artifact-authorship.v1",
            "artifact_id": "s02-frontier-novelist-codex-v1",
            "creation_kind": "codex_manual_edit",
            "creator_id": "codex-task:historical-unrecorded",
            "creator_kind": "codex_task",
            "created_at": "historical-unrecorded",
            "text_sha256": sha256_text(merged),
            "parents": [
                {
                    "artifact_id": approved.approved_prefix_id,
                    "text_sha256": approved.text_hash,
                }
            ],
            "model_pipeline_eligible": False,
            "classification": "manual editor control only",
        },
    )
    gates = continuation_gates(
        candidate,
        scene=scene,
        approved_prefix=approved,
        anti_copy_index=anti_copy_index,
    )
    write_json(SAMPLE_ROOT / "candidate.codex.v1.json", candidate.to_dict())
    write_json(SAMPLE_ROOT / "gates.codex.v1.json", gates)
    write_json(
        SAMPLE_ROOT / "literary_diagnostics.codex.v1.json",
        literary_style_diagnostics(continuation),
    )
    integrated_diagnostics = integrated_style_discontinuity_diagnostics(
        approved.text,
        continuation,
    )
    write_json(
        SAMPLE_ROOT / "integrated_literary_diagnostics.codex.v1.json",
        integrated_diagnostics,
    )
    (SAMPLE_ROOT / "s02.codex.v1.md").write_text(
        continuation + "\n", encoding="utf-8"
    )
    (SAMPLE_ROOT / "s01-s02.codex.v1.md").write_text(
        merged + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "eligible": gates["eligible"],
                "continuation_words": word_count(continuation),
                "merged_words": word_count(merged),
                "candidate_sha256": hash_file(SAMPLE_ROOT / "s02.codex.v1.md"),
                "failed_gates": [
                    name
                    for name, value in gates["gates"].items()
                    if not value["passed"]
                ],
                "possible_style_discontinuity": integrated_diagnostics[
                    "possible_style_discontinuity"
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
