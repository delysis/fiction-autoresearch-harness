# S02 Paired-Curriculum Critical Read — V7 versus V8

Date: 2026-08-01  
Scope: pressure movement only; four matched seeds per arm  
Model: local Gemma 4 31B base, Q8  
Control: identical target ledger, manuscript runway, sampler, local word band, and seeds

## Decision

Retain V7 seed `916001` as the production parent. Do not promote a V8
checkpoint, even if later synonym repairs make one mechanically eligible.

V7 used one project-specific S01 ledger-to-prose mapping. V8 replaced that
mapping with three hash-locked, public-domain Austen mappings. The heterogeneous
archive removed some same-scene mimicry, but it also removed the project-specific
causal and tonal prior. On this matched pool it did not teach a sufficiently
portable ledger-to-prose operator.

The next prompt experiment should factor the two jobs:

1. Use heterogeneous examples to teach causal transformation.
2. Put one project-specific mapping or a prose-only project anchor nearest the
   target.

The useful V7 parent should proceed independently; experimental curriculum work
must not block production.

## Seed-by-seed findings

| Arm | Seed | Mechanical interpretation | Editorial judgment |
|---|---:|---|---|
| V7, one S01 mapping | 916001 | A 321-word gate-valid prefix exists before the premature telemetry-key paragraph. | **Promote.** Sharp exchange-rate banter, a real competence wound, Mara's humor changes Livia's response, zero detected cadence-family hits. A few generic somatic phrases remain, but the movement is alive and causally correct. |
| V7, one S01 mapping | 916019 | A 302-word gate-valid prefix exists before scaffold replay. | Reserve only. Correct tea and exceptionality pressure, but imports S01 wrist-contact/room-listening habits and scores 6.62 cadence-family hits per thousand words. |
| V7, one S01 mapping | 916037 | No valid pressure prefix; telemetry access arrives before the local endpoint. | Reject. It skips directly into the next causal movement and makes the interaction flatter. |
| V7, one S01 mapping | 916055 | No valid prefix; generated `END CASE 2`. | Reject. A long therapeutic explanation replaces interaction, and Mara's coping move does not materially alter Livia's next action. |
| V8, three heterogeneous mappings | 916001 | No required pressure movement in band. | Reject. Substitutes an unexplained signal/attack plot, changes the scene's ontology, and lets Jonah terminate the session. |
| V8, three heterogeneous mappings | 916019 | May become mechanically eligible after synonym coverage is fixed. | **Still reject.** Starts near the target, then makes Livia touch Mara's knee and neck, reverses who requests telemetry, and begins packing up the session. Surface atom presence does not rescue role or endpoint violations. |
| V8, three heterogeneous mappings | 916037 | No valid endpoint; leaves the lab. | Reject. Generic therapeutic summary, contradictory reassurance that Mara is exceptional, head-on-the-page desire inventory, and a completed exit. |
| V8, three heterogeneous mappings | 916055 | Too short before prompt replay. | Reject. Hallucinates Swiss ancestry, skin color, and wife imagery without story support, then emits the next case packet. |

## What the comparison establishes

### Adjacency beats indiscriminate context volume

The strong V7 draw came from a compact prompt whose nearest example shared the
project's character and scene grammar. V8 contained more causally varied
examples, but those examples were farther from the target distribution. The
model did not reliably infer the abstract operation and then reinstantiate it
in Fulcrum.

This complements the earlier long-context results: a 63K-token prose library
improved texture but lost target causality, while a 64K combined stack retained
only part of the scene program. Context capacity is not the same as useful
conditioning bandwidth.

### Mechanical gates must find endpoints, not merely judge whole completions

V7 seed `916001` reached the requested local endpoint and then continued into
the next movement. A selector that evaluates only the longest in-band prefix
throws away the successful parent. The corrected policy should inspect every
complete paragraph boundary and retain the last prefix that satisfies the local
gate.

### Passing atoms is necessary but not sufficient

V8 seed `916019` demonstrates the converse error. A synonym repair can make its
tea/exceptionality atoms visible, but the scene still violates roles, spatial
pressure, and intimacy judgment. Hard gates provide admission; they are not a
literary selector.

### Base-model diversity remains useful

Identical instructions and four nonzero seeds produced materially different
causal and stylistic outcomes. The experiment did not use temperature zero or
a deterministic winner generator. Determinism is confined to provenance,
validation, and reproducible selection over an entropic candidate pool.

## Production recommendation

Use a factored autoloom:

1. Sample story programs and causal movements with entropy.
2. Compile only invariants and invalid coordinates; never normalize unusual
   valid ideas into a house plan.
3. Realize bounded movements with one nearby project mapping and a concrete
   manuscript runway.
4. Select the last gate-valid paragraph boundary, then perform human/editorial
   parent review.
5. Apply any broad author/prose conditioning as a separate, sparse literary
   transformation that is forbidden to change events, roles, consent, or the
   local endpoint.
6. Re-run anti-copy, causal, and literary evaluation after transformation and
   rank only compliant variants.

This preserves the base model's distributional breadth while keeping the
instruct/frontier layer in the role of critic, repairer, and selector—not
launderer of every draft into the same competent house style.
