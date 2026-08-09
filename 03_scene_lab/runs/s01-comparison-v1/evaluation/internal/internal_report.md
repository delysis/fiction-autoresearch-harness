# Three-Pipeline Internal Report

The comparison reports observed outcomes without assuming that Verbalized Sampling or Actor–Novelist must beat direct sampling.

## direct

- Raw tournament winner: `s01-comparison-v1-direct-direct-05`
- Raw mean score: 87.65
- Revision mean score: 87.55
- Revision accepted: False
- Chosen finalist: `s01-comparison-v1-direct-direct-05`
- Mean self-BLEU proxy: 0.0231

## verbalized_sampling

- Raw tournament winner: `s01-comparison-v1-verbalized_sampling-verbalized-03`
- Raw mean score: 87.65
- Revision mean score: 89.75
- Revision accepted: True
- Chosen finalist: `s01-comparison-v1-verbalized_sampling-verbalized-03-polished-r2`
- Mean self-BLEU proxy: 0.0206

## actor_novelist

- Raw tournament winner: `s01-comparison-v1-actor_novelist-actor-novelist-05`
- Raw mean score: 87.45
- Revision mean score: 87.65
- Revision accepted: True
- Chosen finalist: `s01-comparison-v1-actor_novelist-actor-novelist-05-polished-r2`
- Mean self-BLEU proxy: 0.0192

## Verbalized Sampling plan diversity

- Strategies elicited: 16
- Unique after deduplication: 16
- Within-call mean Jaccard distance: s01-comparison-v1-verbalized_sampling-vs-distribution-1=0.7731, s01-comparison-v1-verbalized_sampling-vs-distribution-2=0.8039
- Across-call mean Jaccard distance: 0.8115

## Independent blind review

Two independent reviewers, given only finalists A/B/C and the anchored rubric, both ranked **B > C > A** and agreed on all three pairwise choices.

| Blind label | Mean score | Pipeline revealed afterward |
|---|---:|---|
| B | 79.60 | Actor–Novelist |
| C | 78.15 | Verbalized Sampling |
| A | 68.55 | Direct best-of-N |

No corresponding axis scores differed by more than 2.0 points, so primary score substitution was unnecessary. The Actor–Novelist finalist won the blind reviews; the Verbalized Sampling finalist retained the highest post-edit machine score. Full evidence and reasoning are in `../subagent_reviews/adjudication.md`.
