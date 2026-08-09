#!/usr/bin/env python3
"""Record exact action/consequence evidence for every selected S01 atom."""

from __future__ import annotations

import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fiction_harness.atoms import (  # noqa: E402
    AtomBundle,
    AtomRealization,
    AtomRealizationReport,
    validate_atom_realization_report,
)
from fiction_harness.core import write_json  # noqa: E402


RUN_ROOT = PROJECT_ROOT / "03_scene_lab/runs/s01-atom-rewrite-v1"

FILES = {
    "s01-bundle-a-gift-status": RUN_ROOT / "candidates/s01-a-gift-status.codex.v1.md",
    "s01-bundle-b-somatic-control": RUN_ROOT / "candidates/s01-b-somatic-control.codex.v1.md",
    "s01-bundle-c-method-audit": RUN_ROOT / "candidates/s01-c-method-audit.codex.v1.md",
}

EVIDENCE = {
    "s01-bundle-a-gift-status": {
        "s01-arr-01": ("bakery box braced against the passenger door", "The box slid when she stopped."),
        "s01-arr-03": ("I brought something that wasn’t synthesized.", "Even rarer."),
        "s01-arr-06": ("You brought a shield", "It’s an offering."),
        "s01-arr-10": ("Or he forgot the attachment.", "The stillness broke in several places at once."),
        "s01-cal-01": ("May I put this on you?", "The question was ordinary. In the circle, it was almost disruptive."),
        "s01-cal-06": ("Jonah drew breath for a joke.", "Then he let the breath out through his nose."),
        "s01-cal-07": ("There she is", "Heads turned."),
        "s01-cal-09": ("Her gaze was not on Mara’s face.", "Mara’s response to Jonah."),
        "s01-ctr-02": ("Instead she slid her wrist farther into Jonah’s hand.", "His fingers opened to accommodate her."),
        "s01-ctr-03": ("It went quiet.", "The circle lost its rhythm."),
        "s01-ctr-06": ("A deviation", "No one applauded."),
        "s01-ctr-10": ("Mara set her suitcase beside the bench and took the bakery box", "The circle obeyed badly."),
    },
    "s01-bundle-b-somatic-control": {
        "s01-arr-01": ("The bakery box rode on her forearm.", "She kept turning that side toward her skirt."),
        "s01-arr-02": ("Adrian received it with both hands", "Her suitcase remained in the gravel."),
        "s01-arr-07": ("You planned for us to condescend to you", "The prepared answer vanished."),
        "s01-arr-09": ("No performance.", "the laugh ended without anyone deciding to end it."),
        "s01-cal-01": ("May I?", "In the listening room it altered the air."),
        "s01-cal-03": ("He smelled faintly of unscented soap", "The pulse trace on the terminal climbed."),
        "s01-cal-04": ("The desire arrived as a practical suggestion", "She kept her shoulders where they were."),
        "s01-cal-08": ("His thumb began a small motion", "Livia’s chin dipped at the same point."),
        "s01-ctr-01": ("REPEAT: ARRIVAL.", "She’s testing departure now."),
        "s01-ctr-06": ("A deviation", "We preserve the run."),
        "s01-ctr-08": ("Jesus, what did she see?", "At the name, Livia turned."),
        "s01-ctr-09": ("Jonah was replaying the pressure trace.", "he tapped two fingers once against the metal case"),
    },
    "s01-bundle-c-method-audit": {
        "s01-arr-03": ("I brought something that wasn’t synthesized.", "We’ve been discussing the value of unmanufactured signals."),
        "s01-arr-04": ("Four people occupied the broad cushions nearest it", "three others sat upright with tablets on their knees."),
        "s01-arr-05": ("Alignment begins before agreement.", "The people nearest the fire laughed first."),
        "s01-arr-09": ("No,” Jonah said.", "Adrian watched Jonah for one beat longer than anyone else did."),
        "s01-cal-02": ("Signal or receiver?", "Receiver first."),
        "s01-cal-03": ("She smelled solder on his cuff and cardamom on her own skin.", "The line on Miriam’s monitor jumped."),
        "s01-cal-05": ("the exhaustion of holding a thing shut", "Jonah’s easy expression failed"),
        "s01-cal-08": ("Jonah’s thumb moved in a small arc below it.", "Livia’s fractional nod."),
        "s01-ctr-01": ("She drew one deeper breath, dropped her shoulders", "she’s making the signal harder."),
        "s01-ctr-05": ("Because she blocked the channel.", "Mara could have explained the breath"),
        "s01-ctr-09": ("he touched two fingers to the inside of his own wrist", "Recognition, or warning."),
        "s01-ctr-10": ("we should eat. I brought something.", "Mara took it with cardamom on her fingers."),
    },
}


def main() -> None:
    bundle_artifact = json.loads(
        (RUN_ROOT / "atoms/s01_seeded_bundles.v1.json").read_text(encoding="utf-8")
    )
    summaries = []
    for bundle_set in bundle_artifact["bundle_sets"]:
        bundle_set_id = bundle_set["bundle_set_id"]
        candidate_path = FILES[bundle_set_id]
        text = candidate_path.read_text(encoding="utf-8")
        candidate_id = candidate_path.stem
        per_phase = []
        for bundle_value in bundle_set["phase_bundles"]:
            bundle = AtomBundle.from_dict(bundle_value)
            realizations = tuple(
                AtomRealization(
                    atom_id=atom_id,
                    status="realized",
                    action_evidence=EVIDENCE[bundle_set_id][atom_id][0],
                    consequence_evidence=EVIDENCE[bundle_set_id][atom_id][1],
                )
                for atom_id in bundle.ordered_atom_ids
            )
            report = AtomRealizationReport(
                candidate_id=candidate_id,
                bundle_hash=bundle.bundle_hash,
                per_atom=realizations,
                endpoint_status="pass",
                invented_conflicts=(),
                judge_id="primary-exact-evidence-review.v1",
            )
            validate_atom_realization_report(
                candidate_text=text,
                bundle=bundle,
                report=report,
            )
            output = (
                RUN_ROOT
                / "evaluation/atom_fidelity"
                / f"{candidate_id}.{bundle.sequence_id}.json"
            )
            write_json(output, report.to_dict())
            per_phase.append(
                {
                    "phase_id": bundle.sequence_id,
                    "bundle_hash": bundle.bundle_hash,
                    "report_path": str(output.relative_to(PROJECT_ROOT)),
                    "realized": len(realizations),
                }
            )
        summaries.append(
            {
                "candidate_id": candidate_id,
                "bundle_set_id": bundle_set_id,
                "phases": per_phase,
                "all_selected_atoms_realized": True,
            }
        )

    selected_path = RUN_ROOT / "selected/s01-b-somatic-control.codex.v2.md"
    if selected_path.exists():
        bundle_set = next(
            value
            for value in bundle_artifact["bundle_sets"]
            if value["bundle_set_id"] == "s01-bundle-b-somatic-control"
        )
        selected_text = selected_path.read_text(encoding="utf-8")
        selected_evidence = dict(EVIDENCE["s01-bundle-b-somatic-control"])
        selected_evidence["s01-ctr-08"] = (
            "a pale mark had appeared two seconds to the right",
            "Her eyes widened as she looked from the screen to Mara’s empty left hand.",
        )
        per_phase = []
        for bundle_value in bundle_set["phase_bundles"]:
            bundle = AtomBundle.from_dict(bundle_value)
            realizations = tuple(
                AtomRealization(
                    atom_id=atom_id,
                    status="realized",
                    action_evidence=selected_evidence[atom_id][0],
                    consequence_evidence=selected_evidence[atom_id][1],
                )
                for atom_id in bundle.ordered_atom_ids
            )
            report = AtomRealizationReport(
                candidate_id=selected_path.stem,
                bundle_hash=bundle.bundle_hash,
                per_atom=realizations,
                endpoint_status="pass",
                invented_conflicts=(),
                judge_id="primary-exact-evidence-review.v1",
            )
            validate_atom_realization_report(
                candidate_text=selected_text,
                bundle=bundle,
                report=report,
            )
            output = (
                RUN_ROOT
                / "evaluation/atom_fidelity"
                / f"{selected_path.stem}.{bundle.sequence_id}.json"
            )
            write_json(output, report.to_dict())
            per_phase.append(
                {
                    "phase_id": bundle.sequence_id,
                    "bundle_hash": bundle.bundle_hash,
                    "report_path": str(output.relative_to(PROJECT_ROOT)),
                    "realized": len(realizations),
                }
            )
        summaries.append(
            {
                "candidate_id": selected_path.stem,
                "bundle_set_id": bundle_set["bundle_set_id"],
                "phases": per_phase,
                "all_selected_atoms_realized": True,
                "bounded_revision_of": FILES[bundle_set["bundle_set_id"]].stem,
            }
        )
    write_json(
        RUN_ROOT / "evaluation/atom_fidelity_summary.v1.json",
        {
            "record_type": "S01AtomFidelitySummary",
            "version": "s01-atom-fidelity.v1",
            "judge_id": "primary-exact-evidence-review.v1",
            "candidates": summaries,
        },
    )
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()
