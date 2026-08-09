#!/usr/bin/env python3
"""Compile the reviewed v4.3 sequence-one donor pool into a sparse atom bundle."""

from __future__ import annotations

import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fiction_harness.atoms import AtomBundle, DramaticAtom, render_novelist_packet
from fiction_harness.continuation import S02_MACRO_SEQUENCES
from fiction_harness.core import hash_file, hash_json, sha256_text, write_json


RUN_ROOT = PROJECT_ROOT / "03_scene_lab/runs/s02-compute-v4.3-a4b"
ARM_ROOT = RUN_ROOT / "verbalized_to_instruction"
OUTPUT = ARM_ROOT / "dramatic_atoms.seq1.v1.json"
PACKET_OUTPUT = ARM_ROOT / "novelist_packet.seq1.v1.json"


def load_pool() -> dict[int, dict[str, object]]:
    records = [
        json.loads(line)
        for line in (ARM_ROOT / "candidates.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]
    partials = {
        int(record["seed"]): record
        for record in records
        if record.get("status") == "partial"
    }
    if len(partials) != 8:
        raise ValueError(f"expected eight durable checkpoints, found {len(partials)}")
    return partials


def make_atom(
    pool: dict[int, dict[str, object]],
    *,
    seed: int,
    atom_id: str,
    kind: str,
    participants: tuple[str, ...],
    setup: str,
    move: str,
    response: str,
    change: str,
    entities: tuple[str, ...],
    source_span: str,
    probability: float,
) -> DramaticAtom:
    donor = pool[seed]
    donor_text = str(donor["continuation_text"])
    if source_span not in donor_text:
        raise ValueError(f"source span for {atom_id} is not verbatim in seed {seed}")
    return DramaticAtom(
        atom_id=atom_id,
        scene_id="S02",
        sequence_id="s02-seq-1-trap",
        kind=kind,
        participants=participants,
        setup_fact=setup,
        observable_move=move,
        observable_response=response,
        local_constraint_change=change,
        required_entities=entities,
        source_call_id=str(donor["call_ids"][0]),
        source_text_hash=sha256_text(donor_text),
        source_span=source_span,
        proposed_probability=probability,
    )


def main() -> None:
    pool = load_pool()
    atoms = (
        make_atom(
            pool,
            seed=22063,
            atom_id="s02-a4b-22063-tea",
            kind="object",
            participants=("Livia", "Mara"),
            setup="Mara is depleted after the alignment session and has concealed it.",
            move="Livia pours amber tea from a ceramic carafe and slides it to Mara.",
            response="Mara accepts the warm cup instead of creating distance.",
            change="The accepted care makes Livia's next professional favor harder to refuse.",
            entities=("ceramic carafe", "amber tea"),
            source_span=(
                "She reached for a small, ceramic carafe on the low table between "
                "them, pouring a stream of amber tea into a cup she slid toward Mara."
            ),
            probability=0.061,
        ),
        make_atom(
            pool,
            seed=22063,
            atom_id="s02-a4b-22063-unremarkable",
            kind="speech_act",
            participants=("Livia", "Mara"),
            setup="Mara tries to attribute her strain to data density.",
            move=(
                "Livia names Mara's fear that close inspection will show she is "
                "competent but not exceptional."
            ),
            response="Mara answers with a dry joke that restores only a little distance.",
            change="Livia now has an accurate vulnerability she can attach to status and work.",
            entities=("Mara's dry joke",),
            source_span=(
                '"That’s a very bold interpretation," Mara said, attempting to '
                'reclaim the high ground of intellectual distance. "A bit dramatic '
                'for a Tuesday evening, don\'t you think?"'
            ),
            probability=0.047,
        ),
        make_atom(
            pool,
            seed=22063,
            atom_id="s02-a4b-22063-access",
            kind="social_move",
            participants=("Livia", "Mara"),
            setup="Livia has accurately named Mara's hunger to be exceptional.",
            move=(
                "Livia grants Mara overnight access to raw telemetry as apparent "
                "recognition and opportunity."
            ),
            response="Mara freezes before treating the grant as a professional courtesy.",
            change=(
                "The flattering gift converts Mara's insecurity into surveillance, "
                "status pressure, and unpaid overnight work."
            ),
            entities=("overnight diagnostic", "raw telemetry access"),
            source_span=(
                '"Perhaps. But since you\'re so concerned with the integrity of the '
                "project, I've taken the liberty of updating your access permissions "
                'for the overnight diagnostic. I thought you might want to review the '
                'raw telemetry while it’s fresh. It would be a shame to lose that... '
                'drive of yours."'
            ),
            probability=0.032,
        ),
        make_atom(
            pool,
            seed=22023,
            atom_id="s02-a4b-22023-jonah-complicity",
            kind="observable_reaction",
            participants=("Jonah", "Mara"),
            setup="Mara has signaled that she will keep working to protect her standing.",
            move="Jonah stops typing, leaves his hands still, and says the next sequence is ready.",
            response="Mara receives participation rather than rescue or moral reassurance.",
            change="Jonah becomes visibly complicit in continuing the session.",
            entities=("Jonah's motionless hands",),
            source_span=(
                '"The sequence is ready, then," Jonah said. His voice was low, '
                "devoid of the teasing irony he had used earlier, and it carried a "
                "weight that made Mara’s skin prickle."
            ),
            probability=0.026,
        ),
        make_atom(
            pool,
            seed=22063,
            atom_id="s02-a4b-22063-accept",
            kind="countermove",
            participants=("Mara", "Livia"),
            setup="Mara sees that refusal could be read as lack of commitment.",
            move="Mara taps the shared interface to accept the overnight access.",
            response="Livia turns back to the primary monitor without celebrating.",
            change="Mara remains in the room with an additional obligation recorded under her name.",
            entities=("shared interface", "confirmation icon"),
            source_span=(
                '"Thank you, Livia," Mara said, her voice sounding thin to her own '
                "ears. She reached out and tapped the confirmation icon on the "
                "shared interface, accepting the administrative hand-off."
            ),
            probability=0.019,
        ),
        make_atom(
            pool,
            seed=22063,
            atom_id="s02-a4b-22063-cooling-tea",
            kind="sensory_anchor",
            participants=("Mara",),
            setup="The access acceptance is complete and the session remains underway.",
            move="Mara folds her hands in her lap while the tea cools untouched.",
            response="The room continues around her without granting an exit.",
            change="The sequence ends with Mara still inside and less able to leave.",
            entities=("cooling tea",),
            source_span=(
                "Mara sat perfectly still, her hands folded in her lap, her tea "
                "growing cold, trapped by a kindness that had functioned exactly "
                "like a tether."
            ),
            probability=0.017,
        ),
    )

    source_pool_hash = hash_file(ARM_ROOT / "candidates.jsonl")
    overlay = (
        "Retain the administrative access transaction and Jonah's complicity. "
        "The novelist must supply mixed motives, attraction, and all sentences; "
        "no donor wording is authorized for reuse."
    )
    selection_policy = {
        "version": "s02-atom-selection.v1",
        "criteria": (
            "canon_and_endpoint",
            "filmable_causality",
            "mixed_motive_character_fit",
            "sparse_chain_coherence",
            "diversity",
        ),
        "maximum_atoms": 6,
    }
    bundle = AtomBundle(
        bundle_id="s02-seq1-debt-of-kindness.v1",
        scene_id="S02",
        sequence_id="s02-seq-1-trap",
        ordered_atom_ids=tuple(atom.atom_id for atom in atoms),
        required_atom_ids=tuple(atom.atom_id for atom in atoms[:5]),
        optional_atom_ids=(atoms[5].atom_id,),
        source_pool_hash=source_pool_hash,
        selection_policy_hash=hash_json(selection_policy),
        editorial_overlay=overlay,
        editorial_overlay_hash=sha256_text(overlay),
    )
    artifact = {
        "record_type": "DramaticAtomPool",
        "version": "dramatic-atoms.v1",
        "source_candidate_ledger_hash": source_pool_hash,
        "selection_policy": selection_policy,
        "atoms": [atom.to_dict() for atom in atoms],
        "bundle": bundle.to_dict(),
    }
    write_json(OUTPUT, artifact)

    compact = json.loads(
        (RUN_ROOT / "context/compact_context.v1.json").read_text(encoding="utf-8")
    )
    prefix_tail = str(compact["approved_prefix"]["full_text"])[-6_000:]
    packet = render_novelist_packet(
        manuscript_tail=prefix_tail,
        current_state={
            "location": "Fulcrum alignment lab",
            "session_state": "underway after the S01 calibration",
            "pov": "Mara, close third person",
        },
        character_invariants={
            "Mara": "sheltered, technically competent, dryly funny, wants Livia's respect",
            "Livia": "genuinely perceptive and caring; acquisitive about access to Mara",
            "Jonah": "attracted, observant, implicated in Fulcrum, not a moral oracle",
        },
        word_range=(
            S02_MACRO_SEQUENCES[0].minimum_words,
            S02_MACRO_SEQUENCES[0].maximum_words,
        ),
        endpoint=S02_MACRO_SEQUENCES[0].endpoint,
        bundle=bundle,
        atoms={atom.atom_id: atom for atom in atoms},
    )
    packet["packet_hash"] = hash_json(packet)
    write_json(PACKET_OUTPUT, packet)

    print(OUTPUT)
    print(PACKET_OUTPUT)


if __name__ == "__main__":
    main()
