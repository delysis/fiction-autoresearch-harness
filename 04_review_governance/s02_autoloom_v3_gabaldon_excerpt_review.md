# S02 Autoloom v3 — Gabaldon-Excerpt Native-Base Checkpoint

## Verdict

Reject after sequence one. Do not generate candidates 2–8 and do not run
sequence two.

This is a fair negative result for bounded prose conditioning. The transport,
lineage, holdout isolation, and anti-copy system worked. The fiction did not.
Two short excerpts plus a derived craft profile did not make Gemma 4 31B base
an adequate novelist for this scene.

## Controlled change

Relative to native-base v2, this run kept the same:

- S01 approved manuscript prefix and S02 opening fragment;
- seed 22011;
- immutable high-entropy base plan and plan hash;
- RGO profile, feedback brief, scene, and sequence-one budget;
- Gemma 4 31B base Q8 checkpoint and native `/completion` transport.

The only substantive new variable was prose conditioning:

- two local excerpts of 109 and 119 words from two different Gabaldon novels;
- six provisional, positively rendered craft affordances;
- explicit transposition notes for contemporary American speech and Mara-only
  close-third narration;
- prompt-exemplar inclusion in the streaming and postflight anti-copy index.

The third declared book excerpt remained an untouched holdout. The base prompt
contained neither the author name nor source IDs, and it did not contain the
holdout text.

## Mechanical result

- First draft: 676 words, natural stop.
- Continuation attempt: 526 words, natural stop, rejected for packet leakage.
- Candidate status: `CandidateFailure`; zero sequences admitted.
- Exact 12-word source matches: zero.
- Fuzzy source matches: zero.
- Semantic flags: zero.
- Exact control-language four-gram matches: zero.
- Cadence-family hits: 10, or 14.79 per 1,000 words.
- Most prominent cadence defect: four `not X, but Y` constructions.
- Explanatory-gloss lead: one gloss after only two attributed dialogue turns.
- Anti-copy index hash:
  `e387f86f33bfe67f3777025cc696f5002aacf7d6ae56af74980f63d9f11917e4`.

The repair output replayed its own control packet, including the prose sentinel
and an `## Instructions` heading. The leakage gate rejected it exactly as
designed.

## Literary close read

The draft substitutes an essay about agency for a scene. Mara considers three
abstract options—leaving with Jonah, staying, and a named “third choice”—while
the narration repeatedly explains cage, battleground, game, compliance,
autonomy, winning, losing, and freedom.

The result misses the sequence's causal core:

- Livia does not perform a concrete, skillful manipulation. She offers water
  and says Mara is dehydrated.
- Livia's difficult truth is not dramatized with evidence.
- Mara's response does not cost her anything or narrow her choices.
- No locally intelligent tactic visibly backfires.
- Jonah and the watching group are inert abstractions rather than pressure.
- Sensory detail is sparse and generic despite the exemplar condition.
- The prose explicitly resolves the beat into “deep, quiet satisfaction” and
  “something close to freedom,” which is the opposite of the locked endpoint.

The Gabaldon mechanisms were not transferred. There is no consequential
speech/body-language counterpoint, no physical action whose meaning changes,
no character-specific humor or abrasion, and no selective sensory logistics.
The model copied neither wording nor craft.

## Comparison across sequence-one checkpoints

| Checkpoint | Words | Cadence hits/1k | Endpoint | Critical result |
|---|---:|---:|---|---|
| 31B-it v4.1 Verbalized | 986 | 9.13 | Weak | Causal but didactic, generic heat, model cadence |
| 31B-base v2 planned | 1,089 | 9.18 | Fail | Generic therapy dialogue, flattened Livia, head-hop |
| 31B-it v4.2 sequence-local | 960 | 15.0 | Pass | Less future leakage, worse explanatory house style |
| 31B-base v3 + excerpts | 676 | 14.79 | Fail | Abstract agency essay; exemplars did not transfer |

The central finding is not that one more prompt tweak is required. Both writer
checkpoints are currently below the prose floor in different ways. The
instruction model obeys causality better but turns the scene into a thesis. The
base model is less controllable and, even with real prose exemplars, defaults to
abstract cliché rather than high-dimensional imitation.

## Scaffolding implications

1. Keep base-model entropy upstream. Base planning produced useful causal
   variety; base prose did not produce useful sentences.
2. Stop treating a long craft dossier as a voice engine. Derived affordances
   are good for planning and judging, but they did not induce literary transfer.
3. Do not use repair to turn a failed causal opening into a compliant scene.
   Length and endpoint repair should run only after a literary checkpoint.
4. Put the next compute into selection over smaller creative units: unusual
   physical tactics, dialogue moves, objects, reversals, and sensory anchors.
   Preserve those base-generated atoms verbatim in lineage.
5. Let a stronger novelist compose from selected atoms, but forbid it from
   explaining the plan's abstractions. Judge observable action before prose
   polish and reject thesis language at the first 700–1,000 words.
6. Keep the excerpt arm as an anti-copy and prompt-position calibration, not as
   a production path. A future retry is justified only with a genuinely better
   prose checkpoint or a human-written scene runway—not more of the same Q8
   base samples.

## Durable artifacts

- Run root: `03_scene_lab/runs/s02-autoloom-v3-gabaldon-excerpts`
- Calls ledger SHA-256:
  `58cf8378cb33b663a4a1b38731f2b37b68a12912f65430b90f015e577f715fb0`
- Run configuration SHA-256:
  `8e8f28646e4ab54a837cc242d98c777c11d83badf07ea59cb0dda34c6efa41e`
- Candidate failure ledger records the packet-leak rejection and full lineage.
- No candidate or partial candidate was admitted.
