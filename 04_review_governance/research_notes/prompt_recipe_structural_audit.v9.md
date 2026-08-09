# Prompt Recipe Structural Audit — v9 Round 1

This audit reads the frozen v9 semantic blocks before manuscript generation. Counts are approximate whitespace-delimited words; the live trace records exact Gemma tokenizer counts.

| Recipe | Charged restraint | Open-door married | Explicit married | Non-erotic control | Finished-prose conditioning |
|---|---:|---:|---:|---:|---|
| Causal baseline | 3,695 | 3,695 | 3,695 | 3,701 | none |
| Derived craft sheet | 254 | 254 | 254 | 260 | none |
| Raw spicy prose | 499 | 2,492 | 1,744 | 2,498 | 382–2,367 words |
| Graph/prose pairs | 645 | 2,971 | 2,076 | 2,977 | 382–2,367 words |
| Pairs + project bridge | 1,596 | 4,058 | 3,168 | 3,928 | 1,304–3,425 words |
| Named pairs + bridge | 1,601 | 4,065 | 3,170 | 3,935 | 1,309–3,432 words |
| Contrastive apprenticeship | 1,743 | 4,518 | 3,476 | 4,388 | 1,304–3,425 words |
| Curated long context | 15,597 | 18,059 | 17,169 | 17,929 | 1,304–3,425 words plus craft context |

Every recipe ends in the same order:

1. Reusable apprenticeship blocks.
2. The target program and hard constraints.
3. A plain-prose opening runway as the final bytes.

The project bridge is immediately before the target program. Named and anonymous pair-plus-bridge prompts differ only in attribution labels. The married open-door and explicit targets share their first three causal beats and opening fragment; their heat and anatomical-specificity coordinates differ.

## Critical interpretation

This is not a clean “more tokens” ladder in Round 1, nor should it be read as one. It is a topology screen. The derived craft-sheet arm is extremely sparse, while the baseline is long but contains no spicy finished prose. The paired charged-restraint arm has only one eligible commercial source passage because calibration and holdout isolation take precedence over filling a nominal context budget. The long arm is genuinely much longer, but most of its added material is craft-book apprenticeship rather than additional matched scene pairs.

Consequently:

- A craft-sheet loss cannot establish that abstraction never works; it may establish that six concise affordances are an insufficient apprenticeship.
- A long-context win must be localized through trace review because it combines context dose with additional documentary craft material.
- The cleanest causal comparisons are raw prose versus adjacent graph/prose pairs, paired versus paired-plus-bridge, and anonymous versus named paired-plus-bridge.
- The non-erotic cell is indispensable: most source passages fed to that arm are sensually adjacent, so leakage is a real test rather than an easy negative control.

No inference about manuscript quality is made here; blind prose judgments must freeze before this topology audit enters promotion decisions.
