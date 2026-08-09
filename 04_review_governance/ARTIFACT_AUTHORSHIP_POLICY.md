# Artifact authorship and research-integrity policy

The research question is whether the declared scaffold and writer model produced
the prose. A candidate is evidence only when that claim is mechanically
verifiable.

## Eligible scaffold prose

An eligible candidate must carry `artifact-authorship.v2` and pass all three
checks:

1. Its call ID resolves uniquely in an independent append-only `calls.jsonl`.
2. Its exact manuscript bytes reconstruct from the preserved raw response using
   one declared deterministic derivation.
3. An exact replay with the recorded prompt bytes, model, sampler, and seed
   reproduces the raw-response hash.

Replay is performed with all idle KV slots erased. A warm-prefix replay is not
accepted as a substitute: the first live v2 pilot demonstrated that warm versus
cold evaluation can diverge under high-entropy sampling despite an identical
seed.

The call ledger preserves prompt bytes, transport, parameters, runtime identity,
raw response, and completion metadata. A candidate-side hash that cannot be
resolved against this evidence is self-attestation, not provenance.

## Frontier/Codex role

Frontier and Codex models are critics in scaffold research. They may score,
quote evidence, identify defects, propose one-axis prompt mutations, and state
predictions and falsifiers. They may not write, rewrite, stitch, paraphrase, or
complete manuscript prose.

A repair is a new draw from the declared writer scaffold. It receives structured
defects, acquires a new call identity and seed, and must pass provenance and
anti-copy checks from scratch.

Direct frontier or human prose may be kept as an explicitly separate product
edit or historical control. It cannot support claims about the scaffold.

## Clean-room experiments

New capability trials do not use Codex/frontier-authored manuscript prose as a
runway, exemplar, target, or holdout. Story state enters as structured canon and
scene programs. Declared literary source corpora may supply apprenticeship
prose; anti-copy enforcement applies to every source and generated candidate.

## Historical artifacts

`artifact-authorship.v1` records and existing Codex/frontier manuscript files
remain intact for audit. They are historical-only and cannot be silently
upgraded. Any experiment conditioned on those files must disclose that fact and
cannot be used as clean-room end-to-end evidence.

Official appraisal fails closed unless all finalists pass v2 ledger resolution,
exact derivation, and replay verification.
