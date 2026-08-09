# S02 literary pipeline v4

## Why v4 exists

The v3 proof established that the macro length controller works, but it also
showed that all writer arms were being pulled into nearly the same scene. The
chief attractor was not sampling temperature. It was an overdetermined scene
card, repeated evaluator language in the prose prompt, a compiler that replaced
plan novelty with its own preferred solution, and mechanical gates that rewarded
the same scripted beats.

V4 treats word count as infrastructure and spends inference diversity on causal
choices that matter to a reader.

## Generation context

The immutable audit artifact still contains the complete accepted S01 text,
reader feedback, source identifiers, resolved creative profile, and all hashes.
The generation view is intentionally smaller:

- a factual S01 end-state bridge plus the immutable accepted-prefix hash;
- close-third POV, genre, relationship, world-status, and heat limits;
- character invariants and relationship-specific behavior;
- observable mechanisms without their prescribed dramatic uses;
- nine state changes, expressed without preferred dialogue or exact staging;
- a light-density anonymous, corpus-derived Austen affordance profile
  transformed for the S02 creative profile, with no source prose excerpts.

The accepted S01 prose is retained in the audit packet but omitted from the
generation prompt because its recurrent cadence was contaminating new prose. The full
S01 remains available for audit and merged-story evaluation but cannot dominate
the generation cadence.

## Required causal variation

Every planned arm must make independent decisions about:

1. what Livia perceives correctly;
2. the plausible error Mara makes and its cost;
3. the action by which Mara creates an exit;
4. the institutional cost Miriam accepts to protect that exit;
5. Jonah's cost, compromised motive, prior failure, or repair;
6. Fulcrum's concrete response;
7. the observable fact that remains unexplained.

Programs are compared by normalized causal roles and ordered events, not just
word or phrase overlap. Near-duplicates are rejected before prose realization.
A batch-level report identifies collapsed roles and event sequences.

## Locked plan contract

Selected plans are written to versioned `locked_plan_set.vN.json` artifacts. The manifest contains
the exact plan bytes, seed, source, plan hash, author-context lineage, creative
profile hash, and a hash of the complete plan set. The prose runner recomputes
these hashes and refuses conflicting or mutable records. Candidate resume also
refuses a changed plan.

The 31B-base and Verbalized Sampling paths reject and resample invalid plans.
They do not send selected plans through the instruction compiler. Before the
Verbalized v2 lock, two blind 31B judgments see opposite label orders and score
dramatic causality, character truth, costly agency, romantic voltage,
epistemic restraint, and prose affordance. Quality orders the eligible pool;
causal diversity then removes convergent survivors. The full Verbalized JSON is
preserved byte-for-byte in provenance. The writer sees a deterministic view of
its concrete events and costs, while abstract planning conclusions remain
available to evaluation but cannot leak into prose as thesis sentences.

## Experimental arms

The primary planning-source ablation uses one 31B-it raw writer:

- no plan;
- a locked Verbalized Sampling plan;
- a locked genuine 31B-base plan.

The writer-checkpoint/transport ablation uses the frozen 31B-base plan set:

- 31B-it raw completion;
- 31B-it chat transport with the same semantic request;
- genuine 31B-base native completion.

An unplanned native-base arm remains exploratory. The old E2B-base plus
instruction-compiler arm remains a historical control, not the primary claim.

Raw and chat render one canonical sequence request. Only the endpoint envelope
differs. Native base generation receives the same factual state bridge, locked
packet, and causal program, then begins a clean S02 manuscript continuation
without chat tokens or a duplicated prose tail.

## Length and completion

Each scene is generated as three bounded macro sequences. The controller
reserves the later sequence minima, measures every response, performs local
continuation or compression when necessary, and cannot commit outside
2,800–3,600 continuation words. A candidate also cannot commit with an
unfinished sentence, unbalanced quotation, missing stopping kiss, or absent
romantic continuation choice.

## V4 deterministic gates

The old literal requirements for a loaded phrase, three seconds of silence,
and a named doorway rule have been removed. The hard checks now look for state:

- Livia provides concrete care and gets a difficult perception partly right;
- she overclaims what that truth entitles her to do;
- Mara makes a consequential error;
- bodily evidence retains more than one live explanation;
- attention or prayer restores judgment without emotional blankness;
- Mara creates the exit before Miriam protects it at a cost;
- Jonah walks with her and exposes a cost, failure, or repair;
- the mutually chosen kiss stops while desired in character-specific language;
- a concrete unresolved object, record, signal, or observation drives S03.

These gates test presence and order, not literary merit. Literary selection is
separate.

## Literary diagnostics

The common evaluator now reports, without pretending that heuristics are human
judgment:

- repeated cadence families across a batch;
- immediate narrator gloss after strong dialogue or action;
- dialogue-voice convergence between sufficiently sampled named speakers;
- causal-program overconvergence;
- ordinary overlap, opening similarity, beat strategy, dialogue acts, and event
  sequence diversity.

These diagnostics use continuation text when available, so the shared accepted
S01 prefix cannot manufacture an apparent house style.

All v4 scorecards carry project profile, author profile, corpus, transformation
map, conditioning, plan, anti-copy index, model runtime, prompt, and accepted
prefix lineage. Evaluation hard-fails if declared v4 provenance is incomplete.

S02 uses `s02-proof-story-v1`, not the S01 calibration-game rubric. Its
instructional axis tests accurate care becoming interpretive capture, a
specifically Christian practice yielding one next act, Mara-authored exit
agency, concrete protector/lover costs, and teaching through consequence. Its
pacing follows the three S02 macro-sequences. Its defect taxonomy names Livia
flattening, Miriam-as-rescuer, frictionless Jonah, nominal costs, external
bailouts, instant institutional reform, paranormal confirmation, alliance
shortcuts, and interpretive codas. Historical S02 scores produced under the S01
rubric remain audit artifacts and are not comparable to new scores.

## Interpretation rule

No result may be described as a base-model comparison unless the trace resolves
to the genuine `gemma-4-31b-base` blob. The `gemma-4-31b-raw` alias is the 31B
instruction checkpoint over raw transport. Verbalized Sampling is judged on
the plan actually sampled, not on a compiler's substitute. Results are reported
even when direct sampling wins.

The v4.1 evaluator stores the full continuation-only literary diagnostic and
shows the judge a compact set of counts plus exact examples. The judge must
account for cadence repetition, redundant post-dialogue gloss, and converging
speaker language on the prose-and-voice axis without treating a regex match as
an automatic fault. Conspicuous patterns also become passage-specific leads for
the surgical editor. This addresses the bootstrap evaluator's tendency to give
fluent but templated prose scores in the nineties.

Absolute rubric scoring is continuation-only. The accepted S01 is identical
across candidates, and bootstrap timing showed that loading it into every
scalar judgment roughly doubled cost while the judge compressed visibly
different drafts into a narrow score band. Whole-proof-story judgment is
therefore reserved for the reversed-order pairwise survivor tournament and the
blind human packet.

The staged CLI permits the E4B fast judge to screen all eligible continuations.
The 31B editor remains mandatory for reversed-order survivor tournaments and
the surgical edit; a model-free `finalize` phase accepts or rejects the stored
revision comparisons. This reallocates slow-model compute from false-precision
scalar scoring to candidate sampling and actual pairwise decisions.

Within each pipeline, three survivors advance by screened quality and a fourth
advances as the highest-diversity wildcard. The two reversed-order semifinals
compare S02 alone; the reversed-order final compares the complete S01+S02 proof
stories. Order disagreement falls back transparently to the stored screen score
instead of being silently averaged away.
