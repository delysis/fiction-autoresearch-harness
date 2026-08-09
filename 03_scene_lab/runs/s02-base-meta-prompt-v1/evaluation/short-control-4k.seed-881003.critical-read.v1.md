# Held-out S02 meta-prompt experiment — short control, seed 881003

Verdict: reject. This is a useful baseline failure, not a manuscript candidate.

The 4,781-token prompt produced 1,092 words from the 31B base model at the
fixed 1,500-token ceiling. The output ends mid-sentence. The original trace
called the finish a stop because this llama.cpp streaming build did not expose
`stopped_limit`; the client now infers a length stop when the generated-token
count equals the ceiling. The stored raw candidate and call record are not
rewritten.

## What worked

- The prose stayed in close Mara perspective.
- It produced active dialogue rather than an explanatory essay.
- It did not copy twelve consecutive words from the canonical S01, project
  demonstrations, or reference library.
- Several physical objects are usable in isolation: compost, a refrigerator
  door, blackberries, and Jonah keeping his hands on the handles.
- Surface cadence diagnostics are much cleaner than the earlier Gemma-family
  failures. This confirms that low cadence counts alone do not establish scene
  quality.

## Decisive failures

- It ignores the supplied opening and current state. Instead of continuing an
  overlong alignment session, it jumps to a later morning after a paper critique
  and after the team has left.
- It enacts none of the six target occurrences: no tea as care, no accurate
  naming of Mara's fear of being merely competent, no raw-telemetry access, no
  overnight obligation, no explicit next-sequence complicity from Jonah, and no
  acceptance that leaves Mara less able to exit.
- The causal engine is invented and muddy. Jonah asks about a paper, then says he
  is “verifying the process of trust”; Mara and Livia argue about “the process”
  without a stable referent. The scene repeatedly names abstractions instead of
  making choices change the available action.
- Jonah and Livia are flattened. Jonah becomes evasive and vaguely penitent;
  Livia becomes an even-voiced interpretive counselor. Neither displays the
  specific mixture of skill, appetite, care, restraint, and complicity required
  by the story.
- There is virtually no romantic charge. The refrigerator-door blocking could
  have become spatially and erotically meaningful, but the passage uses it as a
  confusing trust metaphor.
- The output is incomplete and therefore cannot satisfy the checkpoint endpoint.

## Evaluation correction triggered by this read

The first mechanical screen falsely credited three atoms because it matched
`ordinary` in “ordinary sweater,” `ready` inside “already,” and the historical
word `session` despite “the session ended.” Those lexical shortcuts are now
replaced with phrase- and state-sensitive checks. The candidate's corrected
target coverage is 0/6, not 3/6. Completion integrity and prompt-control replay
are also explicit gates for every subsequent arm.

## Experimental implication

The short dossier is not enough to make this base checkpoint honor a local
causal program, even when the prompt ends on a strong canonical manuscript
runway. The next useful comparison is the paired ledger-to-manuscript arm. If
that arm preserves the target chain while remaining fresh, it will support the
hypothesis that base models need demonstrations of the transformation—not more
rules. If it fails similarly, raw prose dose alone is unlikely to repair causal
control, and the experiment should advance the combined arms only as an
explicit test of that possibility.
