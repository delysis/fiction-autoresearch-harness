# Author-conditioning governance

This directory holds generated manifests, copy-index metadata, calibration
results, internal scores, and reveal keys for the author back-translation
layer.

The immutable source books live under `fixtures/author_control` (public-domain
control) or a user-supplied local corpus (commercial target). Raw commercial
books do not belong here and do not cross the default remote frontier
boundary.

## Calibration sequence

1. Prompt encoding: XML, compact prose/Markdown, and canonical JSON over two
   held-out content graphs with four seeds each.
2. Control density: organic (four invariants), light (eight affordances),
   medium (twenty plus distributions), dense (forty), and raw-RAG.
3. Conditioning: none, author name, anonymous profile, named profile,
   profile plus bounded excerpts, plot/review reconstruction, and dense
   retrieval.
4. Advance the Pareto-optimal encoding and two conditioning variants to full
   S01, reusing the same eight base-generated story programs in every arm.

Every result reports the quality–diversity–copying tradeoff, including negative
results. `05_releases` remains untouched until a human accepts a candidate.
