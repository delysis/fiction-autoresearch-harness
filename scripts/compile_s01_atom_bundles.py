#!/usr/bin/env python3
"""Freeze a wording-neutral S01 atom pool and three seeded scene packets."""

from __future__ import annotations

import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fiction_harness.atoms import (  # noqa: E402
    AtomBundle,
    DramaticAtom,
    atom_role_distance,
    render_scene_novelist_packet,
    select_atoms_weighted_without_replacement,
)
from fiction_harness.core import hash_file, hash_json, sha256_text, write_json  # noqa: E402


RUN_ROOT = PROJECT_ROOT / "03_scene_lab/runs/s01-atom-rewrite-v1"
SOURCE_ROOT = PROJECT_ROOT / "03_scene_lab/runs/s01-comparison-v1"
POOL_OUTPUT = RUN_ROOT / "atoms/s01_dramatic_atom_pool.v1.json"
BUNDLES_OUTPUT = RUN_ROOT / "atoms/s01_seeded_bundles.v1.json"
PACKET_ROOT = RUN_ROOT / "novelist_packets"

DONORS = {
    "final-direct": SOURCE_ROOT / "evaluation/finalists/direct.md",
    "final-verbalized": SOURCE_ROOT / "evaluation/finalists/verbalized_sampling.md",
    "final-actor": SOURCE_ROOT / "evaluation/finalists/actor_novelist.md",
    "raw-direct-04": SOURCE_ROOT
    / "direct/candidates/s01-comparison-v1-direct-direct-04.md",
    "raw-direct-08": SOURCE_ROOT
    / "direct/candidates/s01-comparison-v1-direct-direct-08.md",
    "raw-direct-01": SOURCE_ROOT
    / "direct/candidates/s01-comparison-v1-direct-direct-01.md",
    "raw-verbalized-08": SOURCE_ROOT
    / "verbalized_sampling/candidates/s01-comparison-v1-verbalized_sampling-verbalized-08.md",
    "raw-actor-06": SOURCE_ROOT
    / "actor_novelist/candidates/s01-comparison-v1-actor_novelist-actor-novelist-06.md",
}

SOURCE_CALLS = {
    "final-direct": "s01-comparison-v1-direct-direct-05-generate",
    "final-verbalized": "s01-comparison-v1-verbalized_sampling-verbalized-03-polished-r2",
    "final-actor": "s01-comparison-v1-actor_novelist-actor-novelist-05-polished-r2",
    "raw-direct-04": "s01-comparison-v1-direct-direct-04-generate",
    "raw-direct-08": "s01-comparison-v1-direct-direct-08-generate",
    "raw-direct-01": "s01-comparison-v1-direct-direct-01-generate",
    "raw-verbalized-08": "s01-comparison-v1-verbalized_sampling-verbalized-08-realize",
    "raw-actor-06": "s01-comparison-v1-actor_novelist-actor-novelist-06-novelist",
}


def make_atom(
    donor_texts: dict[str, str],
    *,
    donor: str,
    atom_id: str,
    phase: str,
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
    donor_text = donor_texts[donor]
    if source_span not in donor_text:
        raise ValueError(f"source span for {atom_id} is absent from {donor}")
    return DramaticAtom(
        atom_id=atom_id,
        scene_id="S01",
        sequence_id=phase,
        kind=kind,
        participants=participants,
        setup_fact=setup,
        observable_move=move,
        observable_response=response,
        local_constraint_change=change,
        required_entities=entities,
        source_call_id=SOURCE_CALLS[donor],
        source_text_hash=sha256_text(donor_text),
        source_span=source_span,
        proposed_probability=probability,
    )


def atom_pool(donor_texts: dict[str, str]) -> tuple[DramaticAtom, ...]:
    a = lambda **kwargs: make_atom(donor_texts, **kwargs)
    return (
        # Phase 1: arrival and status.
        a(
            donor="final-direct", atom_id="s01-arr-01", phase="arrival-status",
            kind="object", participants=("Mara",),
            setup="Mara arrives alone at sunset with everything she brought in one suitcase.",
            move="She carries a hard-sided suitcase and a bakery box from her church.",
            response="The homemade food looks conspicuous against the compound's controlled welcome.",
            change="Her attempt at hospitality becomes the first object available for public interpretation.",
            entities=("hard-sided suitcase", "church bakery box"),
            source_span="a bakery box from her church’s fellowship hall—sourdough and cardamom buns—and her single, hard-sided suitcase",
            probability=0.083,
        ),
        a(
            donor="raw-actor-06", atom_id="s01-arr-02", phase="arrival-status",
            kind="social_move", participants=("Adrian", "Mara"),
            setup="Mara offers the bakery box on arrival.",
            move="Adrian takes it with conspicuous care instead of reaching for her suitcase.",
            response="Mara follows him inside still carrying her own luggage.",
            change="The welcome flatters her values while quietly establishing who performs service.",
            entities=("bakery box", "suitcase"),
            source_span="He led her toward the pavilion, where the evening's welcome ritual was already beginning.",
            probability=0.052,
        ),
        a(
            donor="final-direct", atom_id="s01-arr-03", phase="arrival-status",
            kind="speech_act", participants=("Mara", "Adrian"),
            setup="Adrian praises Mara's punctual arrival.",
            move="Mara raises the box and jokes that she brought something not synthesized.",
            response="Adrian calls authenticity rare and immediately folds the gift into Fulcrum's vocabulary.",
            change="Her joke earns attention but shows how quickly the institution can appropriate her terms.",
            entities=("bakery box",),
            source_span='"And I brought something that isn\'t synthesized."',
            probability=0.057,
        ),
        a(
            donor="final-actor", atom_id="s01-arr-04", phase="arrival-status",
            kind="observable_reaction", participants=("Mara", "Fulcrum fellows"),
            setup="The fellows are already seated around the fire.",
            move="Mara notices relaxed bodies near the center and rigid bodies at the edge.",
            response="Several people track her while others lower their eyes to tablets or the floor.",
            change="Before introductions, she can see that attention itself allocates rank.",
            entities=("fire pit", "tablets", "peripheral seats"),
            source_span="There was a hierarchy of seating that functioned like a silent liturgy.",
            probability=0.069,
        ),
        a(
            donor="final-direct", atom_id="s01-arr-05", phase="arrival-status",
            kind="speech_act", participants=("Adrian", "Fulcrum fellows"),
            setup="Adrian brings Mara into the ongoing welcome circle.",
            move="He says alignment begins with what people communicate before speech.",
            response="The room treats the claim as the premise of the evening's game.",
            change="Ordinary observation is placed inside a high-status experimental frame.",
            entities=("welcome circle",),
            source_span="begins by learning how much we already communicate without the clumsy interference of speech",
            probability=0.078,
        ),
        a(
            donor="final-verbalized", atom_id="s01-arr-06", phase="arrival-status",
            kind="social_move", participants=("Livia", "Mara"),
            setup="Mara still has the bakery box pressed against her ribs.",
            move="Livia calls the box a shield in front of the circle.",
            response="Mara tightens her grip and corrects Livia: it is an offering.",
            change="Livia turns hospitality into evidence; Mara answers without surrendering the object's meaning.",
            entities=("bakery box",),
            source_span='"It’s not a shield," Mara said, tightening her grip on the box. "It’s an offering.',
            probability=0.076,
        ),
        a(
            donor="raw-verbalized-08", atom_id="s01-arr-07", phase="arrival-status",
            kind="speech_act", participants=("Livia", "Mara"),
            setup="Livia watches Mara brace under the room's attention.",
            move="Livia names Mara's fear that being seen will reveal she is wanting.",
            response="Mara's prepared explanation dies before she can deliver it.",
            change="The read lands accurately enough to make public resistance costly.",
            entities=("Mara's unfinished explanation",),
            source_span='afraid of being seen," Livia said.',
            probability=0.081,
        ),
        a(
            donor="raw-actor-06", atom_id="s01-arr-08", phase="arrival-status",
            kind="speech_act", participants=("Livia", "Mara"),
            setup="Mara claims she is present only to observe.",
            move="Livia says Mara came to learn whether she can be seen without losing herself.",
            response="The room waits for Mara to deny the loneliness Livia adds to the read.",
            change="Livia's genuine accuracy becomes inseparable from her decision to expose it publicly.",
            entities=("silent circle",),
            source_span="here to see if you can be seen without losing yourself.",
            probability=0.062,
        ),
        a(
            donor="final-verbalized", atom_id="s01-arr-09", phase="arrival-status",
            kind="countermove", participants=("Jonah", "Livia", "Mara"),
            setup="Livia asks Jonah to give the room a read of Mara.",
            move="Jonah explicitly refuses to read or perform Mara for the group.",
            response="He creates a silence in which Mara is not required to explain herself.",
            change="His refusal costs him participation in the room's central status display and makes him legible to Mara.",
            entities=("public circle",),
            source_span='"I won\'t read her," Jonah said',
            probability=0.089,
        ),
        a(
            donor="final-direct", atom_id="s01-arr-10", phase="arrival-status",
            kind="speech_act", participants=("Jonah", "Livia", "Mara"),
            setup="Livia's first demonstration leaves the circle hushed.",
            move="Jonah offers a mundane alternative explanation involving a missing attachment.",
            response="The room's held tension breaks and Mara locates the speaker.",
            change="A joke makes epistemic humility socially available without denying Livia's skill.",
            entities=("missing attachment",),
            source_span='"Or maybe he just realized he forgot to attach the file."',
            probability=0.054,
        ),

        # Phase 2: calibration and contact.
        a(
            donor="raw-direct-08", atom_id="s01-cal-01", phase="calibration-contact",
            kind="romantic_action", participants=("Jonah", "Mara"),
            setup="Adrian assigns Jonah to facilitate Mara's tactile calibration.",
            move="Jonah asks Mara's permission before touching her wrist.",
            response="Mara notices that a routine question changes the quality of the whole exercise.",
            change="Contact begins as her choice rather than the room's entitlement.",
            entities=("Mara's wrist",),
            source_span='"May I?" Jonah asked.',
            probability=0.091,
        ),
        a(
            donor="final-direct", atom_id="s01-cal-02", phase="calibration-contact",
            kind="speech_act", participants=("Jonah", "Mara"),
            setup="The pairs are choosing who sends and who receives.",
            move="Jonah quietly asks whether Mara wants to be the signal.",
            response="She must choose a role while the room waits.",
            change="His private question gives her a sliver of control inside a public task.",
            entities=("signal role", "receiver role"),
            source_span='"Do you want to be the Signal?" Jonah asked quietly.',
            probability=0.064,
        ),
        a(
            donor="final-direct", atom_id="s01-cal-03", phase="calibration-contact",
            kind="sensory_anchor", participants=("Jonah", "Mara"),
            setup="Mara closes her eyes with Jonah's hand around her wrist.",
            move="She notices his skin's scent, the room's low sound, and his thumb over her artery.",
            response="Her pulse accelerates beneath the steady pressure.",
            change="Attraction narrows and sharpens attention before it threatens judgment.",
            entities=("salt and sage scent", "radial artery", "room murmur"),
            source_span="The scent of Jonah’s skin—something like salt and dried sage.",
            probability=0.085,
        ),
        a(
            donor="raw-verbalized-08", atom_id="s01-cal-04", phase="calibration-contact",
            kind="observable_reaction", participants=("Mara", "Jonah"),
            setup="Jonah offers a steady tactile rhythm.",
            move="Mara feels an urge to lean closer and surrender to it.",
            response="She recognizes the urge before acting on it.",
            change="Desire becomes evidence she must include without allowing it to decide the experiment.",
            entities=("Jonah's breathing", "Mara's forward movement"),
            source_span="the overwhelming urge to lean forward, to close the distance",
            probability=0.066,
        ),
        a(
            donor="final-direct", atom_id="s01-cal-05", phase="calibration-contact",
            kind="observable_reaction", participants=("Mara", "Jonah"),
            setup="Mara attends to small changes beneath Jonah's elbow.",
            move="She identifies fatigue and the strain of someone holding a door shut.",
            response="Jonah's public ease drops for a moment when she says enough to show she noticed.",
            change="Mara demonstrates real perceptual skill, making the exercise more than a fraud exposure.",
            entities=("Jonah's forearm", "door image"),
            source_span="the exhaustion of someone who had been holding a door shut for a very long time",
            probability=0.074,
        ),
        a(
            donor="raw-actor-06", atom_id="s01-cal-06", phase="calibration-contact",
            kind="romantic_action", participants=("Jonah", "Mara"),
            setup="Mara's accurate response exposes something private in Jonah.",
            move="Jonah starts a joke, stops, and lets the private recognition remain unperformed.",
            response="Mara sees his restraint cost him an easy recovery of status.",
            change="Their attraction acquires a private fact neither converts into spectacle.",
            entities=("unfinished joke",),
            source_span="the joke died on his lips. He chose restraint instead.",
            probability=0.079,
        ),
        a(
            donor="final-direct", atom_id="s01-cal-07", phase="calibration-contact",
            kind="social_move", participants=("Livia", "Mara", "Jonah"),
            setup="Mara and Jonah have just shared an accurate private read.",
            move="Livia praises Mara's result loudly enough to make the circle claim it.",
            response="Jonah pulls back and Mara becomes aware of the audience again.",
            change="The room converts intimacy into status data, giving Mara a reason to test the channel.",
            entities=("public praise", "wrist contact"),
            source_span='"Impressive," Livia’s voice drifted over them',
            probability=0.071,
        ),
        a(
            donor="raw-verbalized-08", atom_id="s01-cal-08", phase="calibration-contact",
            kind="mystery_observation", participants=("Mara", "Jonah", "Livia"),
            setup="Livia calls the pair synchronized while Jonah holds Mara's wrist.",
            move="Mara notices Jonah's thumb tracing a tiny arc and Livia nodding in time.",
            response="She watches the timing repeat before drawing a conclusion.",
            change="A possible side channel becomes testable instead of merely suspicious.",
            entities=("thumb arc", "Livia's nod"),
            source_span="Livia, watching from the edge of the circle, was nodding in perfect time with that movement.",
            probability=0.094,
        ),
        a(
            donor="final-direct", atom_id="s01-cal-09", phase="calibration-contact",
            kind="mystery_observation", participants=("Mara", "Livia", "Jonah"),
            setup="Livia continues narrating the dyad from outside it.",
            move="Mara catches Livia watching Mara's reaction to Jonah rather than Jonah alone.",
            response="She separates the bodily response from Livia's claim about its meaning.",
            change="The observer's influence becomes part of the mechanism under examination.",
            entities=("Mara's pupils", "Livia's gaze"),
            source_span="Livia wasn't just reading Jonah; she was watching the way *Mara* reacted to Jonah.",
            probability=0.073,
        ),
        a(
            donor="final-actor", atom_id="s01-cal-10", phase="calibration-contact",
            kind="countermove", participants=("Mara", "Jonah"),
            setup="The room expects Mara to produce the state Livia has named.",
            move="Mara changes her intended state while keeping the physical contact.",
            response="Jonah's eyes widen although his grip stays steady.",
            change="The dyad now contains a private experimental control the audience does not know about.",
            entities=("unchanged grip", "changed internal state"),
            source_span="His grip didn't change, but his eyes widened by a fraction of a millimeter.",
            probability=0.082,
        ),

        # Phase 3: counter-test and residual mystery.
        a(
            donor="final-actor", atom_id="s01-ctr-01", phase="counter-test-mystery",
            kind="countermove", participants=("Mara",),
            setup="Mara has identified at least one cue channel.",
            move="She changes posture and breath while keeping her hand in place.",
            response="The expected relationship between her felt state and visible signal breaks.",
            change="Livia must either revise the read or overclaim beyond the available observation.",
            entities=("breath rhythm", "posture"),
            source_span="She changed the frequency of her breath, making it shallow and rhythmic",
            probability=0.093,
        ),
        a(
            donor="final-direct", atom_id="s01-ctr-02", phase="counter-test-mystery",
            kind="countermove", participants=("Mara", "Jonah"),
            setup="Mara can expose the mechanism or alter it silently.",
            move="She increases wrist contact while decoupling her internal state from the outward cues.",
            response="The pair remains physically close while the informational channel degrades.",
            change="Her control tests the method without turning Jonah or Livia into public trophies.",
            entities=("wrist contact", "decoupled cue"),
            source_span="she leaned in slightly, increasing the surface area of the contact",
            probability=0.061,
        ),
        a(
            donor="final-actor", atom_id="s01-ctr-03", phase="counter-test-mystery",
            kind="speech_act", participants=("Jonah", "Livia", "Mara"),
            setup="Livia asks Jonah when Mara's assigned state clicks into place.",
            move="Jonah reports that it did not click; it went quiet.",
            response="The circle has to register a failed prediction instead of a mystical success.",
            change="Jonah corroborates Mara's control at a small public cost to the demonstration.",
            entities=("failed click",),
            source_span='"It didn\'t click," Jonah said',
            probability=0.088,
        ),
        a(
            donor="final-actor", atom_id="s01-ctr-04", phase="counter-test-mystery",
            kind="observable_reaction", participants=("Livia", "Mara"),
            setup="Mara has changed the signal without announcing the control.",
            move="Livia confidently calls the signal jagged and the tension rising.",
            response="Jonah's report contradicts her in front of the room.",
            change="Her accurate-read aura partially collapses through a concrete mismatch.",
            entities=("jagged prediction", "quiet report"),
            source_span='"The tension is rising," Livia narrated',
            probability=0.067,
        ),
        a(
            donor="final-actor", atom_id="s01-ctr-05", phase="counter-test-mystery",
            kind="social_move", participants=("Livia", "Mara"),
            setup="The read has failed publicly.",
            move="Livia reframes the miss as Mara blocking or refusing to be seen.",
            response="Mara does not defend herself or supply the missing explanation.",
            change="The exercise reveals how interpretation can protect itself from disconfirmation.",
            entities=("blocking accusation",),
            source_span='blocking. You\'re trying to hide something.',
            probability=0.078,
        ),
        a(
            donor="final-actor", atom_id="s01-ctr-06", phase="counter-test-mystery",
            kind="constraint_change", participants=("Adrian", "Mara", "Livia"),
            setup="The room has witnessed the miss and Livia's recovery attempt.",
            move="Adrian calls the result a deviation and watches the group's reaction.",
            response="Nobody knows whether Mara has failed or produced a more interesting result.",
            change="Mara's status becomes uncertain rather than simply victorious.",
            entities=("deviation", "group reaction"),
            source_span='"An interesting deviation," Adrian said',
            probability=0.059,
        ),
        a(
            donor="raw-verbalized-08", atom_id="s01-ctr-07", phase="counter-test-mystery",
            kind="sensory_anchor", participants=("Mara", "Jonah"),
            setup="The exercise ends and Jonah releases Mara's wrist.",
            move="The loss of contact feels like a drop in temperature.",
            response="Warmth remains at the exact place his hand had been.",
            change="The method can be doubted while the attraction remains bodily undeniable.",
            entities=("phantom warmth", "cooling room"),
            source_span="The loss of contact was like a sudden drop in temperature.",
            probability=0.073,
        ),
        a(
            donor="final-actor", atom_id="s01-ctr-08", phase="counter-test-mystery",
            kind="mystery_observation", participants=("Livia", "Mara"),
            setup="The observable cue channel has failed and Livia turns away.",
            move="Livia looks back at Mara with genuine startled recognition.",
            response="Mara cannot locate a cue that explains the reaction.",
            change="A smaller anomaly survives the partial collapse without confirming its cause.",
            entities=("Livia's startled look",),
            source_span="they had been wide with a genuine, startled recognition",
            probability=0.086,
        ),
        a(
            donor="final-actor", atom_id="s01-ctr-09", phase="counter-test-mystery",
            kind="romantic_action", participants=("Jonah", "Mara"),
            setup="The room remains unsure whether Mara failed the exercise.",
            move="Jonah gives Mara a private acknowledgment that he recognized her control.",
            response="He does not explain her aloud or claim alliance in front of the room.",
            change="Their first romantic progress is shared perception plus restraint, not confession or touch after the task.",
            entities=("private acknowledgment",),
            source_span="He knew what she had done. He knew she hadn't failed the task",
            probability=0.084,
        ),
        a(
            donor="raw-direct-01", atom_id="s01-ctr-10", phase="counter-test-mystery",
            kind="constraint_change", participants=("Mara", "Fulcrum fellows"),
            setup="The calibration circle is breaking up around the unopened church gift.",
            move="Mara chooses to stay and redirects the room toward opening and eating what she brought.",
            response="The bakery box becomes shared food instead of a symbol the room can keep interpreting.",
            change="She enters the fellowship through one concrete act she authors, with her curiosity about Jonah and the method unresolved.",
            entities=("opened bakery box", "accepted fellowship place"),
            source_span='"I think," Mara said, her voice clear and resonant in the quiet room, "that we should probably eat. I brought something."',
            probability=0.077,
        ),
    )


def select_phase_bundle(
    atoms_by_id: dict[str, DramaticAtom],
    *,
    bundle_id: str,
    phase: str,
    required_ids: tuple[str, ...],
    optional_pool_ids: tuple[str, ...],
    optional_count: int,
    seed: int,
    source_pool_hash: str,
    selection_policy_hash: str,
    overlay: str,
) -> AtomBundle:
    selected_optional = select_atoms_weighted_without_replacement(
        tuple(atoms_by_id[atom_id] for atom_id in optional_pool_ids),
        count=optional_count,
        seed=seed,
    )
    optional_ids = tuple(atom.atom_id for atom in selected_optional)
    ordered_ids = tuple(
        atom.atom_id
        for atom in atoms_by_id.values()
        if atom.atom_id in set(required_ids) | set(optional_ids)
    )
    return AtomBundle(
        bundle_id=bundle_id,
        scene_id="S01",
        sequence_id=phase,
        ordered_atom_ids=ordered_ids,
        required_atom_ids=required_ids,
        optional_atom_ids=optional_ids,
        source_pool_hash=source_pool_hash,
        selection_policy_hash=selection_policy_hash,
        editorial_overlay=overlay,
        editorial_overlay_hash=sha256_text(overlay),
    )


def main() -> None:
    donor_texts = {key: path.read_text(encoding="utf-8") for key, path in DONORS.items()}
    atoms = atom_pool(donor_texts)
    atoms_by_id = {atom.atom_id: atom for atom in atoms}
    if len(atoms_by_id) != 30:
        raise ValueError("S01 pool must contain exactly thirty unique atoms")

    donor_manifest = {
        key: {"path": str(path.relative_to(PROJECT_ROOT)), "sha256": hash_file(path)}
        for key, path in DONORS.items()
    }
    source_pool_hash = hash_json(donor_manifest)
    policy = {
        "version": "s01-seeded-sparse-selection.v1",
        "method": "required causal anchors plus weighted stochastic choice without replacement",
        "seeds": [41017, 41031, 41047],
        "phase_order": ["arrival-status", "calibration-contact", "counter-test-mystery"],
        "candidate_count": 3,
        "atoms_per_phase": 4,
        "maximum_atom_reuse_across_candidates": "allowed only for locked causal anchors",
    }
    policy_hash = hash_json(policy)
    overlay = (
        "Introduce Miriam once as the cohort observer logging from a side console, "
        "with an observer badge, without making her central. End the arrival night "
        "with Mara freely accepting her fellowship place, the bakery box opened, "
        "Jonah's role in Fulcrum still unknown, no kiss or private walk, and the "
        "calibration's ordinary mechanism partially explained while one concrete "
        "observation remains unresolved. The next chapter begins four nights later."
    )

    specs = (
        {
            "id": "s01-bundle-a-gift-status",
            "seed": 41017,
            "phases": (
                ("arrival-status", ("s01-arr-01", "s01-arr-06"), ("s01-arr-03", "s01-arr-04", "s01-arr-05", "s01-arr-09", "s01-arr-10")),
                ("calibration-contact", ("s01-cal-01", "s01-cal-09"), ("s01-cal-03", "s01-cal-05", "s01-cal-06", "s01-cal-07", "s01-cal-10")),
                ("counter-test-mystery", ("s01-ctr-02", "s01-ctr-03"), ("s01-ctr-05", "s01-ctr-06", "s01-ctr-07", "s01-ctr-08", "s01-ctr-10")),
            ),
        },
        {
            "id": "s01-bundle-b-somatic-control",
            "seed": 41031,
            "phases": (
                ("arrival-status", ("s01-arr-01", "s01-arr-07"), ("s01-arr-02", "s01-arr-04", "s01-arr-05", "s01-arr-09", "s01-arr-10")),
                ("calibration-contact", ("s01-cal-01", "s01-cal-03"), ("s01-cal-04", "s01-cal-05", "s01-cal-06", "s01-cal-08", "s01-cal-10")),
                ("counter-test-mystery", ("s01-ctr-01", "s01-ctr-08"), ("s01-ctr-03", "s01-ctr-04", "s01-ctr-06", "s01-ctr-07", "s01-ctr-09")),
            ),
        },
        {
            "id": "s01-bundle-c-method-audit",
            "seed": 41047,
            "phases": (
                ("arrival-status", ("s01-arr-04", "s01-arr-09"), ("s01-arr-01", "s01-arr-03", "s01-arr-05", "s01-arr-06", "s01-arr-08")),
                ("calibration-contact", ("s01-cal-02", "s01-cal-08"), ("s01-cal-03", "s01-cal-05", "s01-cal-06", "s01-cal-07", "s01-cal-09")),
                ("counter-test-mystery", ("s01-ctr-01", "s01-ctr-05"), ("s01-ctr-03", "s01-ctr-06", "s01-ctr-07", "s01-ctr-09", "s01-ctr-10")),
            ),
        },
    )

    bundle_sets = []
    packets = []
    for spec in specs:
        phase_bundles = []
        for phase_index, (phase, required_ids, optional_ids) in enumerate(spec["phases"]):
            phase_bundles.append(
                select_phase_bundle(
                    atoms_by_id,
                    bundle_id=f"{spec['id']}-{phase}.v1",
                    phase=phase,
                    required_ids=required_ids,
                    optional_pool_ids=optional_ids,
                    optional_count=2,
                    seed=int(spec["seed"]) + phase_index,
                    source_pool_hash=source_pool_hash,
                    selection_policy_hash=policy_hash,
                    overlay=overlay,
                )
            )
        packet = render_scene_novelist_packet(
            opening_runway="No inherited prose. Begin at the locked sunset arrival image.",
            current_state={
                "time": "sunset on Mara's first day",
                "location": "Fulcrum's redwood compound and main pavilion",
                "prior_action": "Mara has just arrived alone with one suitcase and food from church",
            },
            character_invariants={
                "Mara": "adult, sheltered, technically competent, dryly funny, observant before interpretive certainty; desire may sharpen attention but never settles meaning",
                "Livia": "genuinely skilled, sensuous, funny, acquisitive, and capable of hurt; care and status hunger coexist",
                "Jonah": "adult hardware researcher, implicated in Fulcrum, playful when it costs little; attraction begins in specific restraint, never as moral perfection",
                "Adrian": "polished founder who makes status and method feel like hospitality",
                "Miriam": "adult cohort observer; neutral posture, exact notes, observer badge; introduced once without emphasis",
            },
            scene_contract={
                "title": "The Calibration Game",
                "pov": "close third-person Mara only",
                "opening_image": "At sunset Mara arrives with one hard-sided suitcase and a bakery box from church.",
                "romantic_shape": "attraction and impediment arrive together; wrist contact changes knowledge; no kiss",
                "epistemic_shape": "observation, interpretation, and mechanism stay separable; cue-channel control matters; a smaller anomaly remains",
                "faith": "embodied discipline may change Mara's attention or timing; no detachable explanation",
                "heat": "high embodied attention without graphic anatomy or consummation",
                "prose": "concrete action, subtext, selective sensation, fresh rhythm; no abstract coda or after-action gloss",
            },
            word_range=(2800, 3300),
            endpoint=overlay,
            phase_bundles=tuple(phase_bundles),
            atoms=atoms_by_id,
        )
        packet["packet_hash"] = hash_json(packet)
        packet_path = PACKET_ROOT / f"{spec['id']}.novelist_packet.v1.json"
        write_json(packet_path, packet)
        packets.append(
            {
                "bundle_set_id": spec["id"],
                "seed": spec["seed"],
                "packet_path": str(packet_path.relative_to(PROJECT_ROOT)),
                "packet_hash": packet["packet_hash"],
            }
        )
        bundle_sets.append(
            {
                "bundle_set_id": spec["id"],
                "seed": spec["seed"],
                "phase_bundles": [bundle.to_dict() for bundle in phase_bundles],
            }
        )

    distances = {}
    for left_index, left in enumerate(bundle_sets):
        left_bundles = [AtomBundle.from_dict(value) for value in left["phase_bundles"]]
        for right in bundle_sets[left_index + 1 :]:
            right_bundles = [AtomBundle.from_dict(value) for value in right["phase_bundles"]]
            distances[f"{left['bundle_set_id']}__{right['bundle_set_id']}"] = [
                atom_role_distance(a_bundle, b_bundle, atoms=atoms_by_id)
                for a_bundle, b_bundle in zip(left_bundles, right_bundles)
            ]

    write_json(
        POOL_OUTPUT,
        {
            "record_type": "DramaticAtomPool",
            "version": "s01-dramatic-atoms.v1",
            "scene_id": "S01",
            "source_pool_hash": source_pool_hash,
            "donors": donor_manifest,
            "atoms": [atom.to_dict() for atom in atoms],
        },
    )
    write_json(
        BUNDLES_OUTPUT,
        {
            "record_type": "SeededAtomBundleSet",
            "version": "s01-seeded-bundles.v1",
            "scene_id": "S01",
            "source_pool_hash": source_pool_hash,
            "selection_policy": policy,
            "selection_policy_hash": policy_hash,
            "editorial_overlay": overlay,
            "editorial_overlay_hash": sha256_text(overlay),
            "bundle_sets": bundle_sets,
            "event_role_distances_by_phase": distances,
            "novelist_packets": packets,
        },
    )
    print(
        json.dumps(
            {
                "atoms": len(atoms),
                "bundle_sets": len(bundle_sets),
                "pool_sha256": hash_file(POOL_OUTPUT),
                "bundles_sha256": hash_file(BUNDLES_OUTPUT),
                "packets": packets,
                "event_role_distances_by_phase": distances,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
