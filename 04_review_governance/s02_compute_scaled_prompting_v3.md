# S02 Compute-Scaled Prompting and Evaluation v3

## Design claim

The main quality lever is inference compute over a strong, correctly prompted
model. Scaffolding should make constraints cheap and reliable, expose useful
latent alternatives, and preserve provenance. It should not repeatedly
summarize the story, ask models to repair preventable bookkeeping failures, or
replace prose judgment with elaborate agent theater.

## Shared prompt state

Every clean comparison arm receives the same stable prefix:

- the complete accepted S01 manuscript, byte-for-byte;
- locked story and relationship state;
- S02 desire, obstacle, turn, aftermath, pressure ladder, and nine beats;
- compact character invariants and relationship dynamics;
- mechanism cards reduced to dramatic use rather than source exposition;
- reader feedback on what to preserve, avoid, and develop;
- the selected heat, pacing, atmosphere, and craft obligations.

The prefix is about 5,000 words, well inside the 64K context window. It remains
at the beginning of every call so llama.cpp can reuse its KV cache. Only the
selected plan, already-written S02 prose, current beat ledger, endpoint, and
word ledger vary afterward.

## Length controller

S02 is generated as three causal macro-sequences:

1. Care becomes a trap: 875–1,100 words.
2. The room discovers it has no category for no: 875–1,100 words.
3. Exit, restraint, and the doorway rule: 1,100–1,400 words.

Before each sequence, the harness intersects its local range with the space
needed to keep the whole 2,800–3,600-word scene feasible. It then counts the
actual words. An undershoot continues from the existing last sentence; an
overflow receives up to three local compression passes, with distinct seeds,
an explicit deletion ledger, and increasing safety headroom. The final
romantic resolution is withheld from the first two
calls. A candidate cannot commit outside the hard scene range. The model
therefore writes toward reachable local endpoints instead of guessing how
much of a 3,000-word scene remains. A length-capped sequence must still end at
a natural boundary and realize its required endpoint; otherwise the harness
replaces a bounded tail and rechecks both conditions. Every raw draft remains
in JSONL.

## Clean comparison arms

### Instruction stochastic baseline

Gemma 4 31B-it receives the shared state and identical realization
instructions. Seeds and sampling randomness vary; instructions do not. The raw
completion endpoint uses Gemma's learned turn envelope explicitly.

### Verbalized Sampling to instruction prose

The same 31B-it checkpoint produces two independent distributions of eight
materially distinct strategies. Every stated probability must be positive and
below 0.10. The harness parses, normalizes, deduplicates, and samples four plans
without replacement using a fixed seed. Plans are compiled into bounded causal
programs, then realized by the same instruction writer and length controller as
the baseline. Both within-call and across-call diversity are retained.

### 31B base backtranslation to instruction prose

The genuine Gemma 4 31B base checkpoint sees the full accepted S01 as an
implicit demonstration in a document-continuation prompt. It backtranslates the
demonstration into latent scene logic: attention, rhythm, subtext, causal
pressure, restraint, and several distinct S02 executions. It is told not to
quote the manuscript. Selected base plans pass byte-identically into the 31B-it
writer; there is no instruction-model compiler between them.

This arm asks whether the base model's broader continuation distribution
contains useful plans that instruction tuning suppresses while retaining the
instruction model's strength at controlled realization.

### Native 31B base prose

The same genuine 31B base checkpoint writes the three prose sequences directly.
It receives a manuscript-preparation document followed by `## Manuscript` and
the prose written so far. It receives no role tokens, chat template, or
instruction-model turn grammar. This is the fair test of the base checkpoint on
its native next-token objective.

### Secondary controls

The chat endpoint versus raw instruction endpoint is a transport control. The
earlier E2B-base-plan arm is retained as a model-size ablation. Compact-tail
calibration runs remain in a separate run directory and never enter the
full-context ranking.

## Why backtranslation is an ablation, not dogma

Backtranslation can recover tacit regularities that an explicit craft rubric
misses, but it can also amplify accidental defects or imitate surface language.
The experiment therefore records the recovered plan, runs source-overlap gates,
and compares it against native stochastic and Verbalized plans. It earns a
place in the final system only if it improves held-out prose under blind human
appraisal.

## Selection

Hard gates cover immutable continuity, word bands, ordered beats, Mara POV,
heat ceiling, chosen stopping kiss, local romantic HFN with open institutional
mystery, provenance, and source overlap. Eligible candidates receive
evidence-quoted rubric judgments in randomized and reversed label order.
Pairwise tournaments select within-arm winners. The same targeted editor sees
at most five passage-specific defects and no pipeline identity. A revision is
accepted only if it remains gate-clean and improves the evidence-backed score.

The human packet contains three randomized finalists and no model, pipeline,
score, or cost information. The internal report preserves the reveal key,
prompt hashes, model blobs, seeds, cache telemetry, repair counts, diversity
diagnostics, and quality–diversity frontier.
