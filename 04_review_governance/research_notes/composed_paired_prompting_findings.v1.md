# Composed Paired Prompting Findings v1

## Result

The held-out S02 experiment produced an 885-word human-appraisal candidate from
Gemma 4 31B base-model material without treating a long prompt as a monolithic
instruction. The successful scaffold factored story control, prose sampling,
endpoint selection, and literary editing into separate interfaces. All source
drafts, selected movements, manifests, and the stitched child remain preserved.

The central finding is that **context capacity is not steering bandwidth**.
Prompts from roughly 5K through 77K tokens produced meaningfully different
distributions, but more tokens did not monotonically improve fidelity or prose.
The useful question is not how much context fits. It is which transformation the
nearest examples demonstrate, which concrete state touches the manuscript
runway, and where entropy is allowed.

## What the prompt experiments established

### 1. A base model learns operations from paired examples, not rule volume

The best causal control came from adjacent pairs of:

```text
wording-neutral event ledger
→ manuscript passage that realizes that ledger
```

An abstract contract could name the intended events, but the base model often
treated those names as themes and substituted generic therapeutic dialogue.
Paired examples demonstrated the missing operation: turn an observable causal
graph into bodies, objects, dialogue acts, and changed choices.

The pairing must be visible and local. Separating all plans from all prose, or
burying the live ledger under a large archive, weakened the mapping.

### 2. The nearest example controls the house distribution

V7 used one nearby project-specific S01 mapping. Two of four draws contained a
recoverable pressure movement; seed 916001 supplied the accepted parent. V8
replaced it with three heterogeneous public-domain mappings. Those examples
reduced S01-specific mimicry but produced zero editorially promotable draws.

Heterogeneous mappings can teach causal affordances, but they did not by
themselves transfer voice, roles, or local ontology into Fulcrum. Conversely,
three alternate realizations of the same S01 scene overfit the calibration and
sensor-anomaly prior. A production curriculum should therefore factor the jobs:

- heterogeneous examples for the transformation operator;
- one nearby project mapping or prose anchor nearest the target;
- the live target ledger and runway last.

That mixed curriculum remains an ablation worth running. It is not required to
preserve the successful production result.

### 3. Backtranslation works when it names observable state

V9 supplied an accepted pressure parent but described the next movement with
abstract coordinates such as gift, access, and complicity. Across four draws,
the model substituted physical doors, room keys, laptop possession, easy exit,
or generic permission. None was promotable.

V10 backtranslated the same causal move into a visible interface state:

- a tablet permission panel;
- RAW TELEMETRY;
- MARA VALE;
- EXPIRES 06:00;
- status PENDING;
- Jonah's hands still and visible;
- explicit exclusions for doors, room access, acceptance, exit, and time jump.

That isolated change yielded the accepted seed-918109 parent. The lesson is not
that every story should contain interface labels. It is that planning language
must be compiled into concrete objects, permissions, body positions, and
not-yet-happened actions before it reaches the base model.

### 4. Use long context for a curated apprenticeship, not a warehouse

A 63K prose archive changed rhythm, subtext, and embodiment but overwhelmed
canon and the event graph. A combined long causal-and-prose prompt did not
reliably compose both gains. A 77K prompt was expensive and still yielded a
poor continuation. The 262K model context remains useful for a deliberately
curated apprenticeship, but unused capacity is not a defect.

Every included block should have one declared job: teach an operation, anchor a
project distribution, lock state, or provide a prose runway. If two blocks
teach conflicting scene priors, additional examples can lower effective
control even while increasing nominal evidence.

### 5. Put entropy in candidate pools and observable atoms

Native stochastic draws were valuable. Identical prompts and nonzero seeds
produced different causal possibilities, including successes hidden inside
otherwise invalid completions. Verbalized Sampling remains useful upstream for
diverse plans and atom bundles, but diversity must be measured in event roles,
dialogue tactics, objects, and consequences—not only n-gram distance.

The scaffold should not select the first mechanically valid draw. It should
preserve a bounded pool, extract every eligible endpoint, and compare the
survivors for character truth and productive difference. Determinism belongs in
hashing, gates, manifests, and reproducible selection over the entropic pool.

### 6. Length is an assembly property

Whole-scene word-count prompting was unreliable. The successful approach made
length structural:

- allocate a local band by the causal workload of each movement;
- stop at a clean paragraph boundary before the next movement;
- join hash-locked accepted parents;
- evaluate the assembled total;
- use a sparse stitch edit to remove seam echoes without adding plot.

The V10 success was initially hidden because a 270-word local minimum was eight
words too high. Micro-movement limits are diagnostic constraints, not genre
truth. They must not silently discard a complete causal unit that yields the
correct assembled scene length.

### 7. Endpoint-aware selection recovers useful base-model work

Base completions often reach the requested endpoint and then continue into the
next beat, an exit, a time jump, or scaffold replay. Judging only the whole raw
completion turns a good parent into a false failure. The extractor now tests
every complete paragraph boundary and retains the latest locally eligible
prefix.

This requires segment-specific gates. The final action movement did not need
three lines of dialogue; it needed ACCEPT, Jonah's resumed participation, Mara
still seated, and no exit or time jump. Semantic regressions now cover equivalent
evidence such as Jonah returning to the traces and the room resuming motion.

### 8. Mechanical validity and literary validity are different stages

Several candidates passed or nearly passed atom gates while remaining bad
fiction: role reversal, polished diagnostic monologues, silent-moral-lamp
Jonah, generic therapeutic summary, premature reassurance, or invented canon.
Hard gates are admission criteria, not a literary selector.

The winning V12 assembly passed causally but exposed its seams through repeated
phrases, duplicated permission exposition, and ambiguous PENDING/granted state.
A sparse frontier stitch edit preserved the accepted atoms and best lines while
rewriting connective language. The child then passed the same causal,
anti-copy, repetition, and cadence checks. The immutable base assembly remains
available as evidence; the editor did not overwrite it.

### 9. Anti-copy needs two separate boundaries

Protected prose comprises source books, demonstrations, canonical project
prose, and held-out prose. The mutable generation envelope is not indexed as a
single source because it contains the intentional manuscript runway; doing so
created false plagiarism failures for natural continuation.

Prompt-packet leakage is a separate hard gate. Both raw selections and edited
children are checked for control markers, repeated source language, and
signature passage reuse.

### 10. Runtime geometry changes the economic optimum

On the M4 Max, the dense Q8 model is memory-bandwidth limited. Four warm short
draws reached 1.50 times serial completion throughput, but cold production waves
with separate large prefills achieved a much smaller gain. The shared endpoint
therefore uses four 32K slots with both per-request and aggregate admission.
Candidate pools from one prompt family should be issued together when memory
allows; independent tasks no longer need to hand the entire server back and
forth.

## Production architecture

The recommended pipeline is:

1. **Story-program sampling.** Use native stochastic sampling and Verbalized
   Sampling to propose diverse causal moves, relationship tactics, objects, and
   reversals.
2. **Conservative compilation.** Convert selected proposals into observable
   ledgers and invalid coordinates while preserving unusual valid ideas and
   their provenance.
3. **Paired causal apprenticeship.** Supply a small heterogeneous operator
   curriculum plus one nearest project anchor; keep each ledger adjacent to its
   realized prose.
4. **Concrete manuscript runway.** End the prompt with current bodies, objects,
   permissions, withheld information, and the exact unresolved pressure, then
   continue directly in manuscript mode.
5. **Bounded stochastic movements.** Draw several seeds per causal movement;
   preserve all raws and stop before later beats.
6. **Endpoint-aware admission.** Search complete paragraph boundaries for the
   latest segment-specific valid prefix; reject canon, role, source, leakage,
   POV, and future-event failures.
7. **Editorial parent review.** Promote only movements that work as fiction,
   not merely as atom containers. Freeze each parent in a hash-locked manifest.
8. **Sparse literary stitch.** Give the stronger novelist/editor the accepted
   manuscript, immutable atoms, endpoint, and a short defect list—never donor
   scores, pipeline labels, or a broad invitation to rewrite the plot.
9. **Fresh verification.** Re-run causal, canon, anti-copy, repetition, cadence,
   and exact-evidence checks on the child.
10. **Blind human appraisal.** Release nothing until readers judge attraction,
    pressure, character truth, prayer integration, prose freshness, and desire
    to continue.

## Current production result

The V12 immutable assembly is 875 words. Its separate sparse stitch child is
885 words, covers all six target atoms, contains no forbidden future event,
prompt-packet leakage, duplicate paragraph or 50-word window, or exact 12-word
match against 41 protected sources or the held-out accepted S02. Its automated
cadence-family diagnostic is 2.2599 hits per thousand words. Independent close
reads accept it for human appraisal, not release.

The next informative experiment is not a still-longer prompt. It is a matched
mixed-curriculum ablation—heterogeneous operator examples plus one nearest
project anchor—followed by a blinded human comparison against the current V12
child.
