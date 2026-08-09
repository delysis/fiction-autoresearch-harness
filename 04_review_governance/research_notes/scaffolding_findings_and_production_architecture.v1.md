# Scaffolding Findings and Production Architecture v1

## Executive finding

The native Gemma 4 31B base model is useful as a distributional engine, but it
does not turn a large heterogeneous context into a single coherent control
surface. Different kinds of conditioning reliably move different properties:

| Conditioning | Reliable gain | Reliable failure |
|---|---|---|
| Short contract and prose runway | Organic sampling | Weak target-event control |
| Paired event-ledger → finished-scene demonstrations (~19.7K tokens) | Causal event realization | Compression, low dwell, weak romance |
| Broad dialogue-rich prose library (~63.3K tokens) | Rhythm, subtext, embodiment, erotic charge | Canon and event-graph collapse |
| Paired demonstrations + broad prose in one ~62.6K prompt | Some local pressure and props | Neither causal fidelity nor prose quality composes reliably |
| Concrete 124-word manuscript-state runway | Time/place/social-state continuity | Does not itself guarantee target events |
| Three bounded causal submovements | Structural length and endpoint control | Needs human-grade parent review before child generation |

The production design should therefore **factor the control problem across
stages**, not maximize undifferentiated context length.

## Recommended autoloom

### 1. Sample story possibilities with real entropy

Use a native base model at high-diversity sampling to propose premises, causal
moves, character errors, reversals, objects, and dialogue tactics. Preserve the
raw proposals. Selection may be reproducible, but it must operate over a seeded
stochastic pool; deterministic selection is not a substitute for generation
entropy.

The instruction-model compiler may repair schemas and incompatible ontology
coordinates. It may not replace a strange valid proposal with the house plan.
Every compiled field must point back to the raw proposal span it formalizes.

### 2. Backtranslate the selected program into paired demonstrations

The most effective current control is not an abstract rule list. It is a small
set of examples pairing:

```text
content-neutral event ledger
→ finished manuscript that enacts the ledger
```

This teaches the base model what it means to turn a causal graph into fiction.
In the held-out S02 test, three of four paired-ICL seeds realized at least five
of six required occurrences; the same-seed short control realized none.

### 3. Backtranslate locked state into manuscript prose

Before each generated movement, render current state as 100–150 words of
concrete manuscript:

- who is physically present;
- where each body and salient object is;
- what has and has not happened;
- what remains materially possible;
- what information is still inaccessible;
- the exact pressure active at the boundary.

This runway is scaffold-authored prose with explicit provenance. It counts
toward the scene budget. It is not credited to the model and is not itself a
plagiarism source.

### 4. Realize one causal movement at a time

Generate three pre-endpoint movements rather than one whole scene:

1. pressure and vulnerability;
2. gift and complicity;
3. choice and trap.

Allocate words by causal workload, not equal thirds. Each child request begins
only after its parent passes:

- required observable events;
- chronology, setting, and POV continuity;
- no premature later event;
- dialogue and embodied-action minimums;
- clean paragraph boundary;
- source-overlap and packet-leakage gates;
- a human-grade literary checkpoint.

This makes length an architectural property. It avoids padding after the model
has already resolved the scene.

### 5. Apply literary distribution downstream

Do not restore a 30K–60K raw-prose archive to the causal drafting call. It
repeatedly overpowered local contracts. Instead, transform an already valid
causal draft at a separate novelist/editor boundary using:

- a small number of scene-relevant craft affordances;
- sparse content-neutral style examples;
- the Gabaldon intimacy profile;
- no more than five demonstrated defects;
- an immutable event/relationship delta.

Accept the literary revision only when causality, canon, novelty, and the
human-prioritized axes survive. Preserve both versions.

### 6. Rank only compliant work

Mechanical screening precedes expensive criticism. Eligible candidates enter
evidence-backed pairwise ranking on independent axes:

- causal coherence;
- character truth;
- romance and heat;
- prose freshness;
- epistemic texture;
- faith integration;
- novelty;
- diversity contribution.

A beautiful canon failure is research evidence, not a finalist.

## Context policy

Long context is a budgeted affordance rather than a virtue.

- About 20K paired ICL currently earns its cost through replicated causal
  control.
- About 63K raw prose earns a measurable prose-distribution effect but not
  enough control to generate deliverable scenes directly.
- Combining the two naively does not add their benefits.
- The 128K arm is not justified until sparse/staged conditioning plateaus.
- Prompt families should be sampled cache-affinely: warm one prefix, then draw
  its seed pool. Distinct warm families may use separate shared slots.
- Every live call leases both one slot and its declared prompt-plus-maximum-
  completion tokens from the aggregate context budget.

## Anti-copy boundary

The source index protects books, demonstrations, canonical project prose, and
held-out prose. The mutable generation envelope is not indexed wholesale,
because it contains the intentional manuscript runway and would make natural
continuation look like plagiarism.

Planning-packet leakage is a separate hard gate. Every completed and edited
candidate is rechecked from scratch. A source-overlap failure regenerates from
the causal movement; no editor receives the matched source wording.

## Immediate promotion criterion

The bounded composed scaffold advances only if at least one pressure candidate:

1. stays inside the active late session;
2. dramatizes tea as both care and pressure;
3. lets Livia expose the exceptionality vulnerability through an earned read;
4. gives Mara a characteristic coping move that changes Livia's response;
5. preserves Livia's genuine care and acquisitiveness simultaneously;
6. remains live fiction rather than a therapy summary;
7. ends before access is offered;
8. passes novelty, POV, packet-leakage, and repetition checks.

Only then should the gift/complicity child be generated.
