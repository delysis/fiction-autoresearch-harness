#!/usr/bin/env python3
"""Validate the first stronger-novelist boundary sample and atom fidelity."""

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
from fiction_harness.continuation import (  # noqa: E402
    S02_MACRO_SEQUENCES,
    _sequence_endpoint_satisfied,
)
from fiction_harness.core import hash_file, write_json  # noqa: E402
from fiction_harness.evaluation import (  # noqa: E402
    literary_style_diagnostics,
    word_count,
)


RUN_ROOT = PROJECT_ROOT / "03_scene_lab/runs/s02-compute-v4.3-a4b"
ARM_ROOT = RUN_ROOT / "verbalized_to_instruction"
SAMPLE_ROOT = RUN_ROOT / "frontier_novelist"


def main() -> None:
    atom_artifact = json.loads(
        (ARM_ROOT / "dramatic_atoms.seq1.v1.json").read_text(encoding="utf-8")
    )
    bundle = AtomBundle.from_dict(atom_artifact["bundle"])
    sample_path = SAMPLE_ROOT / "seq1.codex.v1.md"
    text = sample_path.read_text(encoding="utf-8")
    report = AtomRealizationReport(
        candidate_id="s02-frontier-novelist-seq1-codex-v1",
        bundle_hash=bundle.bundle_hash,
        per_atom=(
            AtomRealization(
                atom_id="s02-a4b-22063-tea",
                status="realized",
                action_evidence="She poured. The tea smelled of toasted rice.",
                consequence_evidence=(
                    "Mara accepted it before she could decide whether acceptance "
                    "was wise"
                ),
            ),
            AtomRealization(
                atom_id="s02-a4b-22063-unremarkable",
                status="realized",
                action_evidence=(
                    "The other version is that you crossed the country to discover "
                    "you were exceptional"
                ),
                consequence_evidence="That’s a bold interpretation for a Tuesday.",
            ),
            AtomRealization(
                atom_id="s02-a4b-22063-access",
                status="realized",
                action_evidence="TEMPORARY REVIEW ACCESS: RAW ALIGNMENT TELEMETRY",
                consequence_evidence="REVIEW NOTES DUE BEFORE EXPIRATION.",
            ),
            AtomRealization(
                atom_id="s02-a4b-22023-jonah-complicity",
                status="realized",
                action_evidence="The sequence is ready,” Jonah said.",
                consequence_evidence=(
                    "On his monitor, the button that would load the next run "
                    "remained gray."
                ),
            ),
            AtomRealization(
                atom_id="s02-a4b-22063-accept",
                status="realized",
                action_evidence="Mara touched ACCEPT.",
                consequence_evidence="The terminal beside Jonah chimed.",
            ),
            AtomRealization(
                atom_id="s02-a4b-22063-cooling-tea",
                status="realized",
                action_evidence="Mara folded her hands in her lap.",
                consequence_evidence=(
                    "The tea cooled between her wrists while her name glowed on "
                    "three screens."
                ),
            ),
        ),
        endpoint_status=(
            "pass"
            if _sequence_endpoint_satisfied(S02_MACRO_SEQUENCES[0], text)
            else "fail"
        ),
        invented_conflicts=(),
        judge_id="codex-primary-plus-two-independent-readers.v1",
    )
    validate_atom_realization_report(
        candidate_text=text,
        bundle=bundle,
        report=report,
    )
    diagnostics = literary_style_diagnostics(text)
    output = {
        "record_type": "FrontierNovelistSequenceEvaluation",
        "version": "frontier-novelist-seq-eval.v1",
        "candidate_sha256": hash_file(sample_path),
        "word_count": word_count(text),
        "word_range": [
            S02_MACRO_SEQUENCES[0].minimum_words,
            S02_MACRO_SEQUENCES[0].maximum_words,
        ],
        "mechanical_eligible": (
            S02_MACRO_SEQUENCES[0].minimum_words
            <= word_count(text)
            <= S02_MACRO_SEQUENCES[0].maximum_words
            and report.endpoint_status == "pass"
        ),
        "atom_realization": report.to_dict(),
        "literary_style": diagnostics,
        "independent_review_disposition": "accept_with_surgical_revision_completed",
        "forward_obligations": [
            "Seq2 must notice that supposedly raw access already includes observer annotations.",
            "A concrete Christian practice must cause Mara's changed action in Seq2.",
            "Jonah's complicity or institutional role must cost him something observable.",
            "The privacy breach and Livia's sponsor liability must have later consequences.",
        ],
    }
    target = SAMPLE_ROOT / "seq1.codex.v1.evaluation.json"
    write_json(target, output)
    print(target)


if __name__ == "__main__":
    main()
