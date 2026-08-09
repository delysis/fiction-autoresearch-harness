# Autoloom V19 — Critical Manuscript and Trace Review

Date: 2026-08-03  
Status: raw scaffold calibration complete; direct-edit counterfactual quarantined

## Outcome

The staged 31B-base loom now produces a usable causal skeleton for an explicit married-intimacy scene. It does not yet produce consistently finished, publishable prose.

The selected raw scene is 974 words. It passes the word band, consent, POV, endpoint, anti-copy, and explicitness gates, but fails the explicit heat floor because the prose jumps from clitoral touch to “Afterward.” A 942-word Codex direct edit demonstrates one possible repair but is not scaffold output and provides no evidence that Gemma can produce the improvement.

This is a useful pipeline diagnosis. The direct edit is quarantined as an evaluator-only counterfactual and must not be promoted or shown as a competing model finalist.

## Close read: raw base finalist

### What works

- The broken drive is present before intimacy and remains causally active afterward.
- Esther initiates, changes pace, and repeatedly controls the terms of contact.
- Simon's restraint is enacted through waiting and following rather than described only as virtue.
- “Tell me before I ask” and “Which decision are we making together now?” establish a compact marital conflict.
- The second drive changes the story state, so the intimacy is not detachable decoration.

### What fails

- A manuscript-boundary collision joins dialogue directly to the next sentence.
- Several lines are abstract relationship-policy summaries rather than things these two people would say under pressure.
- Physical positions become difficult to reconstruct during the transition into intercourse.
- Repetitions of breathing, watching, waiting, and changing create a procedural cadence.
- The prose elides the central completion and substitutes “Afterward,” despite the target being explicit married intimacy.
- The final “My decision” regresses from negotiated partnership to unilateral control without dramatizing that as a deliberate rupture.

The raw scene's best quality is not sentence-level voice. It is that erotic action, information asymmetry, and operational risk occupy the same causal mechanism.

## Counterfactual repair specification (not a model result)

### What improves

- Simon's unilateral choice is concrete: he rerouted the courier before Esther could countermand him.
- The line “You chose which of us was allowed to be frightened” makes the emotional injury specific.
- Bodily geometry and stop/go decisions are legible.
- The polling drive interrupts and intensifies the sexual transaction instead of ending it.
- Completion is dramatized through Esther's hand over Simon's and his waiting for her nod.
- “My contingency. / Our exit.” converts the second drive into a negotiated relationship delta.

### What remains weak

- The dialogue is highly compressed and occasionally too polished for spontaneous marital conflict.
- Esther and Simon are legible archetypes before they are fully particular people.
- The click pattern is an effective thriller device but slightly schematic.
- The scene is hot through control, attention, and interruption more than through lush sensory abundance. It is closer to erotic spy fiction than to Gabaldon's full-bodied emotional amplitude.
- The edit improves competence and closure, but its very efficiency risks sanding away some base-model strangeness.

The counterfactual is not eligible for blind human comparison. Each improvement below must be translated into a prompt or scaffold mutation and demonstrated in fresh Gemma output.

## Trace-level findings

### Prompt variables with demonstrated causal effect

1. **Removing intermediate end markers** changed word-band compliance from chronic early stopping to eight complete in-band transaction checkpoints out of nine usable draws.
2. **Placing the strongest mode-matched source passage nearest the target** moved samples from forensic inspection toward causally active intimacy.
3. **Sampling a transaction latent before prose** diversified offer, counteroffer, consent turn, physical logic, disclosure, and plot payment.
4. **Ending on the accumulated manuscript** prevented control-packet leakage and made continuation coherent.
5. **Nonzero-temperature prose plus stochastic quality–distance selection** preserved reproducibility without replacing generation entropy with greedy selection.

### Prompt variables not yet vindicated

- Larger context by itself has not improved prose.
- More ledger fields have not reliably improved voice.
- The contemporary bridge may be teaching the project's explanatory cadence as strongly as it teaches continuity.
- A single nearest spicy source scene can improve mechanics while narrowing rhythm and imagery.
- Mechanical heat signals cannot distinguish genuinely transporting prose from anatomically compliant prose.

## Next preregistered scaffold mutation

Hold the selected causal program, transaction latent, seed manifest, sampler, word bands, and source-nearest topology fixed. Change one axis only: the project-nearest apprenticeship example.

Compare three anonymous bridge variants:

1. **Current bridge:** the existing contemporary project voice.
2. **Concrete-subtext bridge:** the same event graph rewritten so every relational fact appears through action, interruption, misdirection, or sensory response; no abstract relationship diagnosis.
3. **Amplitude bridge:** the same graph with longer sensory arcs, more sentence-length variation, and desire changing perception before it changes action.

Generate at least four fresh Gemma transaction realizations per bridge. No direct-edited prose may enter generation, evaluation, or comparison. Promote only if more than one raw model sample improves blind heat, prose freshness, and character fascination without losing causal coherence or novelty.

### Prediction

The concrete-subtext bridge will reduce therapy-summary dialogue and procedural cadence. The amplitude bridge will increase heat and sensory immersion but may blur the thriller mechanism or exceed the word band.

### Falsifier

If neither bridge changes the observed prose defects across four or more seeds, the dominant style prior is upstream in the accepted runway/source archive or intrinsic to this 31B-base checkpoint. The next experiment should then change the runway voice or model—not add more control structure.

## Evidence

- Raw finalist: `03_scene_lab/runs/base-autoloom-v19/staged/finalists.v1.json`
- Edited child: `03_scene_lab/runs/base-autoloom-v19/final/frontier-edited-child.v1.md`
- Revision and gate record: `03_scene_lab/runs/base-autoloom-v19/final/revision_record.v1.json`
- Prompt findings: `04_review_governance/research_notes/autoloom_prompt_findings.v3.md`

## Subsequent scaffold-only test

V21 projected the five defects back into the Gemma transaction prompt and generated a fresh raw pool. V22 corrected a completion-detector false positive and replayed that pool without inference. The corrected result is zero eligible transactions out of six complete checkpoints. The mutation improved explicit control binding but not manuscript quality sufficiently; it is preserved as a negative result under `03_scene_lab/runs/base-autoloom-v22`.
