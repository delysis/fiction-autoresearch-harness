# Critical Assessment — S02 Proof-Story Bootstrap

## Bottom line

The run proves that the harness can produce complete, coherent, consent-safe
romantic-suspense episodes with resumable local inference, deterministic length
control, exact-evidence evaluation, and effective anti-copy interruption. It
does not yet prove that any scaffold reliably produces compelling fiction.

The raw stories are readable and structurally competent. Their strongest idea
is genuinely strong: Fulcrum's coercive interpretive attention and Jonah's
erotic restraint are two answers to the same question—who owns the meaning of
Mara's desire? This lets teaching, suspense, and romantic heat share one causal
engine.

The execution is still recognizably model-made. Characters repeatedly explain
the scene's governing idea after their behavior has already shown it. Livia is
too often reduced to polished coercion, Miriam arrives as a doctrinal rescue,
Jonah is frictionlessly correct, and Mara becomes implausibly lucid under
exhaustion. The kiss is usually generic abstract heat rather than a specific
encounter between these two bodies and personalities. The Christian content is
mostly a vocabulary of dignity, freedom, and restraint rather than a causally
particular Christian imagination.

These are suitable blind-review prototypes after targeted editing. They are not
release-ready stories.

## What works

- The central dramatic mechanism is legible: accurate observation does not
  confer interpretive or coercive authority.
- Mara wins by changing the available choices, not by winning an argument.
- Restraint changes attraction and trust rather than merely signaling virtue.
- The doorway rule gives chastity a positive dramatic function: it preserves
  desire while making continued intimacy freshly chosen.
- The S01→S02 shape creates a real local arc while leaving the institution open
  for serial suspense.
- POV, heat ceiling, physical stopping, word count, continuity, and anti-copy
  constraints are handled reliably by the mechanical layer.

## What does not yet work

### The prose explains its own effects

The dominant cadence is action or dialogue followed by an abstract gloss:
silence becomes a wall, restraint becomes a catalyst, a boundary becomes an
architecture, and being seen is contrasted with being mapped or captured. The
reader is rarely trusted to make the final inference.

The batch diagnostics confirm that this is a shared house style rather than an
isolated weak draft. Every candidate in every arm uses the `not X but Y`,
`simply`, `sudden`, `felt like`, and `quiet` cadence families. Across four
continuations, `not X but Y` appears 46 times in the planned arm, 40 times in
the raw-completion arm, and 38 times in the chat-direct arm. The upstream
scaffolds therefore produce less stylistic separation than their labels imply.

### Character positions dominate character life

Livia embodies acquisitive interpretation, Miriam embodies clean authority,
and Jonah embodies agency-preserving restraint. Their positions are coherent,
but they are insufficiently mixed with appetite, error, embarrassment, humor,
self-interest, or costly contradiction. Mara's conceptual fluency also rises
exactly when fatigue and social pressure should make her messier.

### The intimacy is correct before it is hot

The scenes understand consent and stopping. They rely too heavily on stock
signals—electric contact, cedar/ozone/cold air, darkened eyes, charged space,
and generic explosions of suppressed feeling. Character-specific sensory
selection, awkwardness, involuntary response, dialogue, and social risk should
carry more of the heat.

### The mystery advances weakly

The episode confirms that Fulcrum is controlling, but it seldom supplies a
concrete anomaly, object, record, cost, or institutional counter-move that
changes the reader's model of the larger plot. “The mystery remains” is not a
hook by itself.

### The faith transformation is generic

Freedom, dignity, responsibility, and integrated desire are compatible with the
project's theology, but they are not uniquely Christian. Later drafts need
faith to change perception and action through particular practices,
relationships, images, or commitments—not detachable religious explanation.

## What the scaffold comparison actually compares

This bootstrap does **not** rerun the old Direct vs Verbalized Sampling vs
Actor–Novelist S01 study. Its three artifact modes canonicalize to:

1. `chat_direct`: Gemma 4 31B-it through the chat interface.
2. `instruction_raw` (artifact label `raw_organic`): the same instruction
   checkpoint used as a raw-completion writer.
3. `base_program_to_instruction` (artifact label `hybrid_base_program`): cheap
   base-generated programs compiled and realized by the 31B instruction
   writer.

All three share the same compact context, macro-sequence controller, scene
contract, and dominant 31B realization prior. The common prompt therefore
explains more of their prose than the upstream scaffold differences do.

## Scaffolding findings

### Keep

- The immutable approved-prefix hash and strict resume lineage.
- The three-sequence length controller with recoverable continuation and local
  compression; do not suppress EOS globally.
- Streaming 12-word source-overlap interruption plus full postflight recheck.
- Hard gates for mechanically reliable requirements.
- Append-only calls, candidates, repairs, and exact-passage evidence.
- Best-of-N generation followed by successive halving.

### Change

1. **Shorten the prose prompt.** Give the writer current continuity, character
   pressures, a small set of causal invariants, heat/consent boundaries, and a
   concrete endpoint. Keep ontology research and production rationale out of
   the next-token context.
2. **Preserve a proposal's novelty kernel.** The base-program compiler currently
   sanitizes unusual proposals into nearly identical plans. Record the proposal's
   indispensable surprising choice and reject compilations that remove it.
3. **Select on event and discourse diversity before prose.** Cluster proposed
   programs by event sequence, information change, dialogue acts, relationship
   delta, and ending mechanism. Do not spend four realizations on the same
   causal skeleton.
4. **Add cross-candidate semantic and rhetorical deduplication.** Source n-gram
   protection prevents plagiarism, but it cannot detect twelve new scenes that
   all use the same architecture/freedom/data-point rhetoric.
5. **Use adversarial defect detection before scalar scoring.** The 31B judge
   routinely assigns low-90s scores and zero defects to prose with obvious
   clichés and flattened characterization. Use specialist critics that must
   identify the strongest failure, then use pairwise comparison among a small
   survivor set.
6. **Spend dense-model context late.** Score continuations cheaply first. Load
   the whole S01+S02 story only for finalists, where beginning-to-ending closure
   matters.
7. **Edit locally where possible.** A full 3,000-word rewrite risks replacing
   successful language and reintroducing the house style. Prefer passage- or
   beat-bounded edits, followed by continuity repair and full anti-copy checks.
8. **Treat hundred-point deltas below several points as noise.** The observed
   score compression does not support claims that one scaffold wins by less
   than a point.

## Concrete controller defect found and fixed

The sequence endpoint controller and final `local_hfn` gate used different
predicates. The controller accepted vague mentions of Fulcrum or tomorrow,
while the hard gate required an explicit free choice such as staying,
returning, or “next time.” This allowed eleven of twelve raw candidates to
commit and then fail the downstream gate. Both stages now share the stricter
predicate, with a regression test; preserved candidates remain unchanged.

## Recommended next experiment

Use one compact prompt and the corrected shared controller. Sample many cheap
story programs, select 8–12 causally distinct programs, and give each one direct
31B chat and 31B raw realizations. Add a small unplanned-organic arm. Reject
mechanical failures and semantic duplicates. Ask adversarial critics for the
single worst defect, then pairwise-rank perhaps six survivors. Let humans—not
the 100-point judge—decide whether planning or raw continuation earns its cost.

Only after that baseline produces stories people actively want to continue
should author back-translation be introduced as a held-out, anti-copy-checked
conditioning ablation.

## Final tournament, editing, and blind-review addendum

The reversed-label tournaments did not establish stable model preferences.
Every pipeline final split when its A/B order was reversed, so screen-score
tie-breaks selected the raw winners. The hundred-point judge also compressed
nearly every draft into the high-eighties or low-nineties. Those scores are
useful as traceable diagnostics, not as evidence of publishable quality.

The common 31B full-rewrite editor failed as a production component. All three
rewrites introduced mechanical failures: lost or reordered S02 beats, excess
length, or a missing local HFN/hook. They were rejected and preserved under
`editor/rejected_full_rewrites/`. Minimal ending-only repairs were then applied
to the untouched tournament winners to make Mara's free return and a concrete
residual anomaly explicit. The repaired stories pass the preserved legacy hard
gates and anti-copy checks, but their new scalar scores fell; they are therefore
marked `provisional_human_appraisal`, not machine-accepted releases.

Two independent blind readers both chose **B**, the
`base_program_to_instruction` finalist, over A and C. One ranked C second for
its embodied kiss and louder uncanny hook; the other ranked A second for its
cleaner access-log anomaly and lower sermon density. No scored axis differed by
more than two points, so no special adjudication was required.

The consensus developmental prescription is specific:

1. Start from B.
2. Remove roughly 25–33% of the explanatory late-session prose.
3. Preserve Mara's physical initiation and Jonah's plain wrist-rhythm answer.
4. Give Jonah a desire, mistake, or institutional stake that makes restraint
   costly and makes his earlier silence morally ambiguous.
5. Give Livia one humane, accurate motive or perception that survives Mara's
   refusal.
6. Let Mara open the door or otherwise finish more of her own escape before
   Miriam acts.
7. Replace general spiritual diction with one concrete Christian practice,
   relationship, memory, or commitment that causes Mara's choice.
8. Use A's cleaner access-log anomaly, tied directly to Jonah's hardware role,
   as the next plot engine.

This is the shortest route from a successful harness demonstration to a story
worth testing for genuine reader appetite.
