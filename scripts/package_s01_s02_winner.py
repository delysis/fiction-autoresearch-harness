#!/usr/bin/env python3
"""Apply the bounded S01-B repair and merge it with immutable S02."""

from __future__ import annotations

import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fiction_harness.core import hash_file, sha256_text, write_json  # noqa: E402
from fiction_harness.evaluation import (  # noqa: E402
    integrated_style_discontinuity_diagnostics,
    literary_style_diagnostics,
    word_count,
)


RUN_ROOT = PROJECT_ROOT / "03_scene_lab/runs/s01-atom-rewrite-v1"
SOURCE = RUN_ROOT / "candidates/s01-b-somatic-control.codex.v1.md"
SELECTED_ROOT = RUN_ROOT / "selected"
S01_OUTPUT = SELECTED_ROOT / "s01-b-somatic-control.codex.v2.md"
MERGED_OUTPUT = SELECTED_ROOT / "s01-s02.codex.v2.md"
S02 = (
    PROJECT_ROOT
    / "03_scene_lab/runs/s02-compute-v4.3-a4b/frontier_novelist/s02.codex.v1.md"
)
SOURCE_HASH = "8c60ef85984b5b08ebe765bde4b533c839e15bc51492b6fdf1ca1c825e80a691"
S02_HASH = "8561c609388e564f2d35edcffafec3f60969b96e003c0024241dcb3b5c5cf06e"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"expected exactly one {label} passage, found {text.count(old)}")
    return text.replace(old, new, 1)


def main() -> None:
    if hash_file(SOURCE) != SOURCE_HASH:
        raise ValueError("raw S01-B candidate changed")
    if hash_file(S02) != S02_HASH:
        raise ValueError("immutable S02 changed")
    text = SOURCE.read_text(encoding="utf-8")

    revisions = []
    old = (
        "At the hearth, Livia made a soft sound of impatience. Jonah’s mouth "
        "tilted, but his attention remained on the sensor contacts. Whatever "
        "reluctance he had displayed for the room did not extend to running its "
        "machinery."
    )
    new = (
        "At the hearth, Livia made a soft sound of impatience. Jonah’s mouth "
        "tilted, but he reseated both contacts and enabled recording before "
        "Adrian finished speaking."
    )
    text = replace_once(text, old, new, "Jonah implication")
    revisions.append(
        {
            "label": "show Jonah's implication",
            "before_hash": sha256_text(old),
            "after_hash": sha256_text(new),
        }
    )

    old = (
        "REPEAT: ARRIVAL.\n\n"
        "Jonah could see only her face; the hood concealed the words. Mara "
        "rebuilt the same instant: gravel releasing the wheels, cedar underfoot, "
        "the unopened door."
    )
    new = (
        "REPEAT: ARRIVAL.\n\n"
        "Jonah could see only her face; the hood concealed the words. Mara let "
        "one breath pass. *Jesus, keep me honest.* The prayer did not settle her "
        "pulse. It made it harder to pretend she wanted only the method.\n\n"
        "She rebuilt the same instant: gravel releasing the wheels, cedar "
        "underfoot, the unopened door."
    )
    text = replace_once(text, old, new, "prayerful attention")
    revisions.append(
        {
            "label": "make prayer causal during the control",
            "before_hash": sha256_text(old),
            "after_hash": sha256_text(new),
        }
    )

    old = (
        "“She improvised it.” Adrian’s tone remained cordial. The distinction "
        "still placed the discovery inside his institution. “Tomorrow we "
        "determine what she actually changed.”"
    )
    new = (
        "“She improvised it.” Adrian’s tone remained cordial. Miriam wrote "
        "IMPROVISED CONTROL beneath the Fulcrum header. “Tomorrow we determine "
        "what she actually changed.”"
    )
    text = replace_once(text, old, new, "institutional appropriation")
    revisions.append(
        {
            "label": "show institutional appropriation",
            "before_hash": sha256_text(old),
            "after_hash": sha256_text(new),
        }
    )

    old = (
        "Livia had gone to the side table. She stood over the bakery box with "
        "one hand on the lid.\n\n"
        "Mara rose. The blood returning evenly to her fingers made them prickle. "
        "Behind Livia, the glass wall held a dim reflection of the room: Adrian "
        "among the chairs, Jonah bending over the silver terminal, Miriam’s "
        "observer badge catching the console light.\n\n"
        "Livia looked at Mara in the glass. For the first time that evening, her "
        "face held no prepared use for what she saw.\n\n"
        "Mara thought, without moving her mouth, *Jesus, what did she see?*\n\n"
        "At the name, Livia turned.\n\n"
        "The lid slipped from her fingers and struck the box. Her eyes had "
        "widened. She stared at Mara’s left hand, then at her face.\n\n"
        "Mara looked down. Her hand hung empty beside her skirt. No gesture, no "
        "altered grip, no icing now. Her breathing had not changed until Livia "
        "turned.\n\n"
        "“What?” Mara asked.\n\n"
        "Livia pressed her lips together. A second later the social ease returned, "
        "slightly misbuttoned.\n\n"
        "“I was hoping you had another one hidden.” She opened the box. “Apparently "
        "I’m having a blood-sugar event.”\n\n"
        "She took a bun and tore it in half. One piece she kept. The other she held "
        "toward Mara.\n\n"
        "Mara accepted it."
    )
    new = (
        "Livia had gone to the side table. She stood over the bakery box with "
        "one hand on the lid when the silver terminal chimed once.\n\n"
        "Mara rose. On the pressure trace, a pale mark had appeared two seconds to "
        "the right of Miriam’s END CONTACT tick. Jonah leaned toward the screen. "
        "The cuff lay open on the table between the empty chairs.\n\n"
        "Livia saw the mark reflected in the glass and turned. The lid slipped from "
        "her fingers and struck the box. Her eyes widened as she looked from the "
        "screen to Mara’s empty left hand.\n\n"
        "“Did you touch the cuff?” Livia asked.\n\n"
        "“No.”\n\n"
        "Miriam checked her paper log. “Cuff off before the mark.”\n\n"
        "“Sensor rebound,” Jonah said.\n\n"
        "“Possible,” Miriam said.\n\n"
        "A second later Livia’s social ease returned, slightly misbuttoned. “I was "
        "hoping Mara had another one hidden.” She opened the bakery box. “Apparently "
        "the system is having a blood-sugar event.”\n\n"
        "She took a bun and tore it in half. One piece she kept. The other she held "
        "toward Mara.\n\n"
        "Mara accepted it."
    )
    text = replace_once(text, old, new, "residual anomaly")
    revisions.append(
        {
            "label": "replace psi-forward coincidence with delayed pressure evidence",
            "before_hash": sha256_text(old),
            "after_hash": sha256_text(new),
        }
    )

    s02_text = S02.read_text(encoding="utf-8").strip()
    merged = text.rstrip() + "\n\n" + s02_text + "\n"
    S01_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    S01_OUTPUT.write_text(text.rstrip() + "\n", encoding="utf-8")
    MERGED_OUTPUT.write_text(merged, encoding="utf-8")
    diagnostics = integrated_style_discontinuity_diagnostics(text, s02_text)
    write_json(SELECTED_ROOT / "integrated_style_diagnostics.v2.json", diagnostics)
    manifest = {
        "record_type": "S01S02SelectedManuscript",
        "version": "s01-s02-selected.v2",
        "selection": "s01-b-somatic-control",
        "selection_basis": (
            "two independent accept judgments; strongest repeated-target control; "
            "best sealed-telemetry and Jonah-complicity seam into immutable S02"
        ),
        "raw_s01_path": str(SOURCE.relative_to(PROJECT_ROOT)),
        "raw_s01_sha256": SOURCE_HASH,
        "revised_s01_path": str(S01_OUTPUT.relative_to(PROJECT_ROOT)),
        "revised_s01_sha256": hash_file(S01_OUTPUT),
        "immutable_s02_path": str(S02.relative_to(PROJECT_ROOT)),
        "immutable_s02_sha256": S02_HASH,
        "merged_path": str(MERGED_OUTPUT.relative_to(PROJECT_ROOT)),
        "merged_sha256": hash_file(MERGED_OUTPUT),
        "s01_words": word_count(text),
        "s02_words": word_count(s02_text),
        "merged_words": word_count(merged),
        "bounded_revisions": revisions,
        "integrated_style_diagnostics_path": str(
            (SELECTED_ROOT / "integrated_style_diagnostics.v2.json").relative_to(
                PROJECT_ROOT
            )
        ),
        "release_status": "human-appraisal-candidate-not-release",
    }
    write_json(SELECTED_ROOT / "selection_manifest.v2.json", manifest)
    s01_authorship = {
        "record_type": "ArtifactAuthorship",
        "schema_version": "artifact-authorship.v1",
        "artifact_id": "s01-b-somatic-control.codex.v2",
        "creation_kind": "codex_manual_edit",
        "creator_id": "codex-task:historical-s01-repair",
        "creator_kind": "codex_task",
        "created_at": "historical-unrecorded",
        "text_sha256": hash_file(S01_OUTPUT),
        "parents": [
            {
                "artifact_id": "s01-b-somatic-control.codex.v1",
                "text_sha256": SOURCE_HASH,
            }
        ],
        "model_pipeline_eligible": False,
        "classification": "manual editor control only",
    }
    write_json(
        S01_OUTPUT.with_suffix(S01_OUTPUT.suffix + ".authorship.json"),
        s01_authorship,
    )
    merged_authorship = {
        "record_type": "ArtifactAuthorship",
        "schema_version": "artifact-authorship.v1",
        "artifact_id": "s01-s02.codex.v2",
        "creation_kind": "deterministic_assembly",
        "creator_id": "harness:s01-s02-selected-v2",
        "creator_kind": "harness",
        "created_at": "historical-unrecorded",
        "text_sha256": hash_file(MERGED_OUTPUT),
        "parents": [
            {
                "artifact_id": "s01-b-somatic-control.codex.v2",
                "text_sha256": hash_file(S01_OUTPUT),
            },
            {
                "artifact_id": "s02-frontier-novelist-codex-v1",
                "text_sha256": S02_HASH,
            },
        ],
        "model_pipeline_eligible": False,
        "prose_added": False,
        "assembly_record_hash": sha256_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":"))
        ),
        "classification": "assembly containing manual editor controls",
    }
    write_json(
        MERGED_OUTPUT.with_suffix(MERGED_OUTPUT.suffix + ".authorship.json"),
        merged_authorship,
    )
    print(json.dumps({**manifest, "style": diagnostics}, indent=2))


if __name__ == "__main__":
    main()
