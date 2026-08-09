# V4 instruction-raw smoke: close read

Candidate: `s02-compute-v4-literary-instruction_raw-instruction_raw-01`

Status: failed proof. Preserve as evidence; do not promote or polish as a
finalist.

## Runtime result

- Continuation length: 3,391 words.
- Macro lengths: 995 / 1,004 / 1,392 words.
- Sequence one and two required no length repair.
- Sequence three raw draft: 1,586 words.
- The first sequence-three sample was aborted for a protected twelve-word S01
  overlap. The alternate seed completed.
- Two low-temperature compression requests reproduced an identical 1,585-word
  response despite different prompt hashes and seeds.
- The hard-ceiling compression landed at 1,392 words but ended mid-quotation.
- The old endpoint heuristic mistook an earlier coerced `stay` and the choice to
  kiss for Mara's required free choice to continue, allowing an invalid initial
  commit. V4.1 corrects the endpoint and quotation checks.

## What improved

The causal core is materially better than the earlier S02 cluster.

- Livia is right about two difficult things: Mara is carrying grief, and Mara is
  attracted to Jonah.
- Livia's wrongness concerns jurisdiction. She converts accurate observation
  into a demand that Mara accept Livia's theory and treatment.
- Mara makes a plausible error: she complies to preserve friendship and project
  standing. Compliance supplies the room with more evidence against her.
- Mara makes the exit possible herself by standing, leaving the exercise space,
  and calling the process a polite surrender before Miriam intervenes.
- The kiss changes the story: Jonah stops because he is withholding project
  information, then exposes the mapping program.

These are genuine v4 gains. The scaffold should retain them.

## Why the prose is not publishable

The scene persistently explains its own meaning. Representative examples:

- “The care had not disappeared; it had simply become the delivery system for
  a command.”
- “She was no longer a participant in the alignment; she was the specimen.”
- “The ‘care’ was a currency, and the price of the loan was Mara's interpretive
  sovereignty.”
- “She had not just left the circle; she had called the circle into question.”

These are lucid critical summaries, not dramatic discoveries. Almost every
good action receives an abstract gloss immediately afterward.

The deterministic style diagnostic found 45 cadence-family hits:

- `not X but Y`: 15;
- `sudden`: 10;
- `felt like`: 8;
- `merely`: 5;
- `simply`: 5;
- `quiet`: 2.

The attraction is described through generic electromagnetic language—“magnetic
pull,” “physical wire,” “humming, electric certainty”—rather than details that
could belong only to Mara and Jonah.

Livia speaks in fluent therapist-antagonist exposition. Miriam's cost is asserted
as “social capital” rather than enacted. Jonah's late revelation is a useful
plot turn but arrives as a familiar secret-project monologue without a piece of
evidence. The scene contains no specifically Christian practice; Mara's decisive
interior action is the secular mantra “I am here.”

The ending is invalid: it stops after “we have to have a rule.” It provides no
shared practice, no Mara-authored next step, no local HFN, and no concrete
external evidence.

## Gate audit

The original v4 gate report correctly failed local HFN but contained three
important defects:

1. `penetrate` in “encrypted in ways that even I can't fully penetrate” caused
   a false sexual-explicitness failure.
2. An odd number of straight quotation marks was not checked.
3. The endpoint choice regex accepted an earlier coerced willingness to stay and
   Mara's choice to kiss as the required free future choice.

V4.1 fixes all three. It also removes generic terms such as `voice`, `door`, and
`light` from the concrete-hook object list; those terms made ordinary scene
texture look like evidence.

## Consequences for v4.1

- Keep the state changes but render them as plain actions and costs, not
  interpretive labels.
- Require a specifically Christian prayer or practice to change Mara's next
  observation or action.
- Shorten the mediocre accepted-S01 prose tail from 320 to 120 words; preserve
  full S01 only in the audit artifact and merged-story evaluator.
- Reduce anonymous Austen affordance conditioning from medium to light density.
- Strengthen natural-completion, free-future-choice, concrete-evidence, and
  provenance checks.
- Raise stochasticity during compression because low-temperature requests
  replayed the overlong draft byte-identically.
- Preserve this candidate and every failed call. It is an ablation result, not
  a hidden draft.
