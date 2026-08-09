# Autoloom Prompt Findings v1

## Research claim

A base model should be conditioned by a textual artifact distribution, not
treated as an instruction-following clerk.  Story-program entropy, prose
entropy, repetition control, and closure are separate control surfaces.

## Durable observations

1. The old ledger baseline produced 0 mechanically eligible scenes in its
   first ten completed draws.  It frequently overran or stopped short, repeated
   generic phrases, and treated a numerical word band as weak metadata.
2. A compact planner prompt with abstract directions produced generic plans
   (hidden injury, household task, simple objects).  Raising temperature did
   not substitute for a concrete proposal distribution.
3. Recasting the planner prompt as an archive of vivid prior loom draws caused
   direct transfer of concrete causal objects and actions: a prosthetic grip
   failure, wax-sealed evidence, an earthquake exposing a marked coin, and a
   flickering-light memory mechanism.
4. The planner continued elaborating after four usable proposals.  Streaming
   cancellation at the fourth complete proposal reduced waste from 1,400
   generated tokens to roughly 493 on the observed draw.  This is a runtime
   stop problem, not a prose-instruction problem.
5. A raw-spice prompt with two eligible explicit source scenes plus a
   near-target project bridge produced a 1,336-word, cap-truncated scene.  It
   was phrase-novel and loop-free but generic, structurally derivative of the
   bridge, and unfinished.
6. The near-target bridge was confounded with the benchmark: both involved
   encrypted evidence, dangerous separation, withheld operational truth, and
   married reconciliation.  It was replaced with a 958-word violin-workshop
   scene retaining the intimacy mode but changing the external causal world.
7. With that orthogonal bridge, documentary target encoding, a learned scene
   sentinel, and the same seed/program, the first form-only draw stopped
   naturally at 910 words.  It was loop-free and copy-clean.  It nevertheless
   failed the explicit heat target: no anatomical specificity or completed
   intimacy.
8. The detailed sampled plan for that draw specified a prosthetic grip and
   charged objects but no sexual causal engine.  The base writer followed the
   detailed plan rather than the broad `explicit` label.  Therefore heat must
   be represented in the sampled program itself, not left as metadata.

## Decisions

- Retain true entropy at both program and prose stages.
- Select programs with seeded novelty-weighted sampling without replacement;
  never use deterministic top-1 as the diversity mechanism.
- Preserve raw proposals.  Do not use an instruction compiler to normalize
  their oddity before prose.
- Teach closure extensionally with several complete scene forms and an exact
  sentinel.  Keep a token cap as a safety boundary, not the desired ending.
- Use llama.cpp DRY sampling to suppress long repetition while leaving normal
  short motifs available.
- Curate positive exemplars by rhetorical role.  Counterexamples are evaluator
  evidence, not positive generation demonstrations.
- Keep bridge examples mode-matched but externally orthogonal to the target.
- Add `MODE ENGINE` to every sampled story program.  Explicit programs must
  name both sexual escalation and visible agency; nonsexual programs must
  state that bodily attention remains non-erotic.
- Treat heat floors separately from safety ceilings.  An explicit calibration
  candidate must contain anatomical specificity, completed consensual
  intimacy, and visible agency; mere absence of prohibited content is failure.
- Freeze raw best-of-N candidates before any instruction/frontier critique or
  bounded repair.

## Next falsifiable tests

1. Four prose seeds on the orthogonal form-only prompt: does at least one
   naturally complete draw realize explicit intimacy, or does the detailed
   nonsexual plan suppress heat across the distribution?
2. Re-sample programs with `MODE ENGINE`, then hold those programs and seeds
   fixed across form-only, raw-spice, and graph-to-prose apprenticeship arms.
3. Promote only if multiple samples combine natural closure, the requested
   heat band, causal relationship change, prose freshness, and copy novelty.
4. If mode-engine programs still fail, test sequence-level scene forms
   (pressure/disclosure, intimacy transaction, aftermath/decision) before
   adding more context.  This distinguishes form-length failure from context
   insufficiency.
