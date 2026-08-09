# Paired ledger→manuscript ICL: four-seed finding

The 19,748-token paired prompt establishes a real steering effect on the native
Gemma 4 31B base checkpoint, but not a literary solution.

| Seed | Raw words | Causal atoms | Scaffold result | Literary verdict |
|---:|---:|---:|---|---|
| 881003 | 534 | 6/6 | Underlength failure | Compressed, flat, weak Jonah/heat |
| 881019 | 941 | 5/6 | 940-word candidate | Clean cadence; chronology, Jonah, and romance fail |
| 881041 | 1,235 | 0/6 | Loop hard-failure | Repeated meeting block; wrong scene |
| 881063 | 414 | 6/6 | Underlength failure | Clean causal synopsis; almost no dwell or heat |

Three of four draws realize at least five of six locked occurrences; two realize
all six exactly. The same-seed short control realized none. That is sufficient
to keep paired scaffold→prose demonstrations in the pipeline.

It is not sufficient to keep single-call whole-movement realization as the
production writer. The stable failure is compression: the model treats the
event ledger as a short causal transformation and often reaches the endpoint in
400–550 words. Post-hoc continuation would add material after the scene has
already resolved. The next scaffold should distribute the same atoms over three
pre-endpoint movements, generate each under a local causal contract, preserve
state between them, and let the final movement alone reach “access accepted;
session continues.” Word count then emerges from bounded composition rather
than a prose-level request or a repair pass.

The runtime finding is equally clear. Once one 19,748-token prefix was warm,
later seeds required one prompt token and decoded at about 4.83 tokens/second.
Submitting three cold copies simultaneously was dominated by redundant prefill;
cache-affine sequential seeds are the correct schedule for a prompt family,
while distinct warmed families may share other slots.
