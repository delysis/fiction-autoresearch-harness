# S01 comparison completion audit

The three-pipeline prototype run is complete and ready for human appraisal. The harness has **85 passing tests**, 24 preserved raw candidates, three gate-valid finalists, complete generation/evaluation lineage, and 113 append-only runtime attestations resolving every completed call to its llama.cpp build and local GGUF blob.

## Honest result

Raw generation did not fully obey the requested length target:

| Pipeline | Raw candidates | 2,800–3,600 words | Passed every hard gate |
|---|---:|---:|---:|
| Direct best-of-N | 8 | 7 | 1 |
| Verbalized Sampling | 8 | 1 | 0 |
| Actor–Novelist | 8 | 0 | 0 |

The raw outputs remain untouched for experimental honesty. The shared editor repaired only the selected Verbalized Sampling and Actor–Novelist winners; Direct's valid raw winner was retained because its proposed revision scored slightly lower. All three delivered finalists pass every hard gate.

## Selection result

| Pipeline | Final machine score | Blind-review result |
|---|---:|---|
| Direct | 87.65 | A, third |
| Verbalized Sampling | 89.75 | C, second |
| Actor–Novelist | 87.65 | B, first |

Both independent blind reviewers ranked **B > C > A** and agreed on every pairwise choice. All 42 axis citations and all 29 defect citations are exact passages. No axis disagreement crossed the two-point adjudication threshold.

This is a useful nontrivial result: the highest machine score did not win the independent blind reading. Actor–Novelist produced the preferred finalist; Verbalized Sampling produced the most diverse elicited plan pool and the highest post-edit machine score, but not the blind-review winner.

## Appraisal and release state

The blind HTML packet opens locally, autosaves and restores responses, exports JSON, and provides an explicit reset control. The smoke-test responses were cleared. The reveal key is stored outside the reader directory, and the blind-leak check passes.

`05_releases` remains untouched pending actual human acceptance.
