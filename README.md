# Juicy Chastity Fiction Lab

This directory is the durable local mirror of the project workspace. Its folder
numbers match the Google Drive project structure.

## Current state

**Research-integrity reset (2026-08-07):** earlier prose-quality claims are
historical, not current scaffold evidence. The audit found Codex/frontier prose
artifacts, experiments conditioned on that prose, and legacy self-attested
model provenance. No historical file was altered or deleted. See
`04_review_governance/provenance/repository_provenance_audit.v1.md`.

New promotion is fail-closed: a candidate must resolve against an independent
completed-call ledger, reconstruct exactly from the preserved raw response, and
pass an exact replay using the recorded prompt, runtime, sampler, and seed.
Codex/frontier models are critic-only in scaffold research; the former direct
manuscript editor paths now stop with an error. `05_releases` remains empty.

- Project brief v0.3 is published as a native Google Doc and filed in Drive.
- Week 1 source retrieval is complete: 20 MPC canon anchors and 10
  Leverage/social-influence case dynamics.
- The first three pilot scenes have generation-ready scene cards.
- A working story canon and a seeded source-transformation log are ready.
- The four Week 1 assets are published as native Google Docs in their matching
  Drive folders.
- Native readback, structure checks, source-link normalization, PDF export, and
  page-by-page visual QA are complete.
- The S01 three-pipeline experiment is complete: 24 raw candidates, three
  gate-valid finalists, two independent blind reviews, and a working A/B/C
  reader packet. These are preserved historical results, not v2-verified
  scaffold evidence.
- Both blind reviewers ranked Actor–Novelist first, Verbalized Sampling second,
  and Direct best-of-N third. `05_releases` remains empty until a human accepts
  a finalist.
- The inherited S01 has now been rebuilt at the observable-atom boundary. Three
  seeded, causally distinct rewrites passed all gates; candidate B received two
  accepting reads and was merged with immutable S02 for blinded human
  appraisal. This is an appraisal candidate, not a release.

## Workspace map

| Folder | Purpose | Current artifact |
|---|---|---|
| `00_project_brief` | Approved scope and production architecture | Project Brief v0.3 |
| `01_source_library` | Theological anchors and case dynamics | 30-card Source Card Deck v0.1 |
| `02_storyworld_canon` | Continuity, cast, metaphysics, romance, practices | Story Canon Ledger v0.1 |
| `03_scene_lab` | Scene specifications and candidate production | Pilot Scene Cards S01–S03 v0.1 |
| `04_review_governance` | Provenance, transformation, review decisions | Source Transformation Log v0.1 |
| `05_releases` | Accepted scenes and publication candidates | Empty until a scene passes review |

## Drive workspace

- [Project root](https://drive.google.com/drive/folders/1VAR4966fHb_jSRMp3GqKgeL31bvwE-4x)
- [Native Project Brief v0.3](https://docs.google.com/document/d/1MKSb4nRQP9nt0oWB29rRmvmDXNzGcuyCH5z9EFNwqNE/edit)
- [Source Card Deck v0.1](https://docs.google.com/document/d/1SrXEmYDxdg0olad3jRirdcsKs7mo0p8FvEr-GcF6ZgU/edit)
- [Story Canon Ledger v0.1](https://docs.google.com/document/d/1g4QqleWNH5pD74A2wXTyoKlo41_2O1I1OO4X62JkYMk/edit)
- [Pilot Scene Cards S01–S03 v0.1](https://docs.google.com/document/d/1BkWiwl7NWSjIlneKeTf90yQ8pE24izywY87GZ5MABII/edit)
- [Source Transformation Log v0.1](https://docs.google.com/document/d/19ieBaFpdr6eCzMzQJs4xkr7UuJMbvFdpybHdedMyj5I/edit)
- [00 Project Brief](https://drive.google.com/drive/folders/1c2xOgm1EhtUJ-2e6-UKl-95iHGE3YhoM)
- [01 Source Library](https://drive.google.com/drive/folders/13i-9k_09RMuHnkVJK3vGmTbpDWt6fWzX)
- [02 Storyworld & Canon](https://drive.google.com/drive/folders/1oBfDDnEyXncwKWROUj8mz_Ics807V1jC)
- [03 Scene Lab](https://drive.google.com/drive/folders/1zpIeXKTs1Grz3-EQ7ieutif-9nRmqXvB)
- [04 Review & Governance](https://drive.google.com/drive/folders/1SsR02LbL0olPEGyYsyKhqEk2phgftwpe)
- [05 Releases](https://drive.google.com/drive/folders/1fyw-xnAGz_7kPl4VEPOojpFlVjYWK7iq)

## First three scenes

1. **S01 — The Calibration Game:** entrance, enchantment, muscle-reading,
   partial debunking, and the first romantic recognition.
2. **S02 — The Doorway Rule:** a late-night interpretive pressure session,
   the protagonist's first clean refusal, and chastity as intensified
   attention.
3. **S03 — The Alignment Vigil:** public crisis, competing supernatural and
   psychological explanations, evidence discipline, prayer, confession, and
   institutional transformation.

## Local Gemma 4 fiction harness

`fiction_harness` implements the controlled S01 comparison:

1. Direct stochastic best-of-N.
2. Verbalized Sampling at the plan/beat level.
3. Actor–Novelist behavioral traces, E4B validation, and prose realization.

The harness uses the cached Q8 Gemma 4 models through
`/Users/george/llama.cpp/build/bin/llama-server`. Calls, plans, traces,
candidates, scores, and lineages are append-only and resumable. The compiled
project dossier remains byte-stable at the front of generation prompts.

Verify the integrity boundary:

```bash
python3 -m fiction_harness provenance audit
python3 -m fiction_harness provenance verify CANDIDATES.jsonl \
  --candidate-id CANDIDATE_ID --without-replay
python3 -m fiction_harness provenance replay CANDIDATES.jsonl \
  --candidate-id CANDIDATE_ID --url http://127.0.0.1:8097
python3 -m fiction_harness provenance verify CANDIDATES.jsonl \
  --candidate-id CANDIDATE_ID
```

`--without-replay` is diagnostic only and can never promote a candidate.

Run from this directory:

```bash
python3 -m fiction_harness preflight
python3 -m fiction_harness compile
python3 -m fiction_harness serve generator
python3 -m fiction_harness serve fast_judge
python3 -m fiction_harness run all
python3 -m fiction_harness serve editor
python3 -m fiction_harness evaluate --judge-passes 1
python3 -m fiction_harness package
```

The servers must run outside a restricted sandbox for Metal access. Only one
slot is used. Gemma 4’s full-size SWA cache is enabled so repeated stable
prefixes can reuse their in-slot KV state. The separate RAM-resident idle-slot
cache is disabled because it can strand a disconnected non-streaming request;
hidden reasoning is disabled so requested JSON/prose receives the entire
completion budget.

### Intimacy craft profile

The harness includes `gabaldon-intimacy-v1`, a transferable craft distillation
of Diana Gabaldon's *I Give You My Body*. It stores no example passages and
does not ask models to imitate Gabaldon's prose. It treats S01 as a non-sex sex
scene: dialogue, body language, atmosphere, selective sensation, and costly
restraint conduct a changing emotional transaction.

The profile is injected into all future generation runs. Direct generation,
Verbalized Sampling, and Actor–Novelist prompts now require character-specific
desire, a coherent sensory triad, active atmosphere, controlled narrative
distance, and a measurable relationship delta.

The completed v1 experiment remains reproducible with its original rubric.
Use the opt-in v2 rubric for a fresh evaluation or run the model-free craft
audit over preserved candidates:

```bash
python3 -m fiction_harness craft-audit \
  --output 04_review_governance/intimacy_craft_audit_v1.json

python3 -m fiction_harness evaluate \
  --rubric gabaldon-v2 \
  --evaluation-dir 03_scene_lab/runs/s01-comparison-v2/evaluation
```

### Romance Generation Ontology

RGO v1 is the harness's versioned creative-control vocabulary. Its 111
coordinates use one romance browse spine plus independent facets for contract,
genre, architecture, external plot, series design, tropes, relationship,
archetypes, consent, heat, intimacy craft, darkness, world, faith, narration,
tone, and market metadata. Heat, consent, and darkness are deliberately
independent.

The broad catalog describes commercial-romance possibilities. The inherited
`juicy-chastity.v1` → `fulcrum-pilot.v1` → `fulcrum-s01.v1` profile chain
selects the exact project and scene contract. Thema 1.6 and BISAC 2025 codes
are versioned release mappings only; they are excluded from model prompts.

Browse and validate:

```bash
python3 -m fiction_harness ontology list --namespace trope
python3 -m fiction_harness ontology show trope.charged-restraint
python3 -m fiction_harness profile validate
python3 -m fiction_harness profile resolve \
  --output 04_review_governance/fulcrum_s01_resolved_profile.v1.json
```

Compile an ontology-enabled S01 dossier without touching the original
`s01-v1` compilation:

```bash
python3 -m fiction_harness compile \
  --profile fiction_harness/profiles/stories/fulcrum_pilot.v1.json \
  --scene-profile fiction_harness/profiles/scenes/s01.v1.json
```

That command defaults to `03_scene_lab/compiled/s01-v2-ontology`. The resolved
profile hash is recorded in the compilation manifest, every run configuration,
candidate, scorecard, and internal report. Resume is refused if the prompt or
profile hash changes. Use a new run root for the controlled ontology ablation:

```bash
python3 -m fiction_harness run all \
  --compiled 03_scene_lab/compiled/s01-v2-ontology \
  --run-root 03_scene_lab/runs/s01-ontology-comparison-v1 \
  --run-id s01-ontology-comparison-v1
```

Key outputs:

- `03_scene_lab/compiled/s01-v1`: versioned canon, source, scene, persona, and
  stable-prefix artifacts.
- `03_scene_lab/compiled/s01-v2-ontology`: the same trusted corpus plus the
  resolved RGO creative profile; the v1 directory remains untouched.
- `03_scene_lab/runs/s01-comparison-v1`: the 24-candidate controlled run.
- `.../evaluation/finalists`: one accepted finalist from each pipeline.
- `.../appraisal/reader/index.html`: blind A/B/C human appraisal.
- `.../internal/reveal_key.json`: the separately stored A/B/C reveal key.
- `.../evaluation/internal`: scores, costs, diversity, pipeline comparison,
  and the completion audit.
- `.../evaluation/subagent_reviews`: two blind scorecards and their
  evidence-backed adjudication.

`05_releases` remains untouched until a human accepts a finalist.

The preserved raw run also records an important negative result: only 7/8
Direct, 1/8 Verbalized Sampling, and 0/8 Actor–Novelist drafts landed inside
the requested word-count window without editing. The common editor repaired
the selected winners; it did not rewrite the other raw candidates, preserving
the comparison rather than concealing under-length generations.

### Compute-scaled S02 comparison

The successor experiment removes word-count compliance as a model-arm
confound. Every candidate is generated in three macro-sequences with measured
word budgets. The controller dynamically reserves feasible space for all
remaining sequences. An early stop triggers a resumable continuation of the
current sequence; overflow triggers up to three increasingly conservative
local compressions with distinct seeds. The final ending is withheld until the first two sequence
ledgers are complete. A token-capped passage must also end naturally and realize
its required endpoint; otherwise a bounded tail-replacement pass completes the
ending. A candidate cannot commit outside 2,800–3,600 words.

Three v4.1 primary pipelines share the same bounded story state, a factual S01
end-state bridge plus immutable prefix hash, and the same pacing controller:

1. `instruction_raw`: 31B instruction checkpoint over native completion with
   its learned Gemma turn envelope supplied explicitly.
2. `verbalized_to_instruction`: two instruction-model Verbalized Sampling
   distributions, two reversed-order blind 31B plan judgments, and a
   quality-first causal-diversity selection. The complete selected plans remain
   locked; the writer receives a deterministic concrete-event view without a
   model compiler or the planner's thesis-like summary fields.
3. `native_base_with_base31_plan`: diverse causal plans sampled by the genuine
   31B base checkpoint and passed unchanged to the same checkpoint for native
   manuscript continuation, with no chat tokens or instruction template.

Diagnostic ablations realize the exact locked 31B-base plans with the
instruction writer (`base31_plan_to_instruction`), compare raw and chat
transport, and test unplanned native-base prose. This separates the value of a
plan from the value of the checkpoint that realizes it.

The model-proposed Verbalized Sampling probabilities are preserved as
selection weights and explicitly reported as uncalibrated. The old
`raw_organic` and `hybrid_base_program` labels remain supported only for
reproducing completed v1 artifacts.

```bash
python3 -m fiction_harness serve editor
python3 -m fiction_harness continuation verbalize
python3 -m fiction_harness continuation rank-verbalized

python3 -m fiction_harness serve raw_writer
python3 -m fiction_harness continuation run instruction_raw
python3 -m fiction_harness continuation run verbalized_to_instruction

python3 -m fiction_harness serve base_31b_writer
python3 -m fiction_harness continuation propose \
  --mode base31_plan_to_instruction
python3 -m fiction_harness continuation run native_base_with_base31_plan

python3 -m fiction_harness serve raw_writer
python3 -m fiction_harness continuation run base31_plan_to_instruction

python3 -m fiction_harness continuation gate
python3 -m fiction_harness serve fast_judge
python3 -m fiction_harness continuation evaluate --phase score \
  --judge-role fast_judge --judge-url http://127.0.0.1:8093

python3 -m fiction_harness serve editor
python3 -m fiction_harness continuation evaluate --phase tournament
python3 -m fiction_harness continuation evaluate --phase edit
python3 -m fiction_harness continuation evaluate --phase revision-score \
  --judge-role fast_judge --judge-url http://127.0.0.1:8093
python3 -m fiction_harness continuation evaluate --phase finalize
python3 -m fiction_harness continuation package
```

### Author back-translation and anti-copy layer

The author-conditioning layer treats a writer as a graph of reusable craft
mechanisms, not a bag of quotations. Its eleven independent axes cover market
geometry, architecture, scene causality, intimacy, character policy,
relationship-conditioned behavior, dialogue, discourse, syntax, imagery, and
reader response. A claim becomes an author-level signature only when at least
two profiling books support it.

The first control is Jane Austen:

- Profiling: *Pride and Prejudice*, *Emma*, *Sense and Sensibility*
- Calibration: *Mansfield Park*
- Untouched holdout: *Persuasion*

All five texts are local public-domain Project Gutenberg editions. The holdout
is structurally rejected by segmentation, retrieval, profile compilation, and
prompt construction. Normal generation receives derived obligations without
source excerpts. A transformation map preserves mechanisms such as
relationship-specific behavior and delayed recontextualization, transposes
social machinery into Fulcrum's contemporary setting, and leaves low-level
Austen syntax evaluator-only.

Three genuine base checkpoints are available through raw llama.cpp completion:

- `base_ideator`: Gemma 4 E2B base Q8
- `base_writer`: Gemma 4 E4B base Q8
- `base_31b_writer`: Gemma 4 31B base Q8

They do not use chat completion or a chat template. Legacy E2B proposals may
still be compiled for artifact reproduction. In the v4.1 comparison, selected
31B-base and Verbalized Sampling plans are frozen in immutable, versioned
manifests. No instruction-model compiler may improve or replace their ideas;
the novelist sees only a deterministic event-field projection that withholds
abstract `epistemic_turn`, `romantic_engine`, and `relationship_delta` labels.
A paired instruction-writer arm receives the exact same
locked 31B-base plan, separating plan quality from checkpoint and transport
effects.

```bash
python3 -m fiction_harness author manifest validate
python3 -m fiction_harness author profile validate
python3 -m fiction_harness author profile resolve \
  --conditioning-variant anonymous-profile \
  --prompt-encoding xml \
  --control-density medium
python3 -m fiction_harness author anti-copy build \
  --output 04_review_governance/author_conditioning/austen_anti_copy_index.v1.json
python3 -m fiction_harness author experiment-plan
python3 -m fiction_harness serve base_ideator
python3 -m fiction_harness serve base_writer
```

The anti-copy index scans every generated delta. A normalized exact
twelve-word author-source match closes the streaming connection immediately;
llama.cpp then cancels the active slot. Postflight checks remain authoritative
for exact, fuzzy, semantic-adjudicated, prompt/source, and cross-candidate
overlap. N-gram speculative decoding is disabled for these runs; ordinary
prompt/KV caching remains enabled.

The author evaluator keeps style intensity, canon preservation, naturalness,
romance/intimacy effectiveness, RGO/Gabaldon fulfillment, coherence, Christian
transformation, and novelty as separate axes. A beautiful but copied or
canon-breaking scene cannot average its way back into eligibility. Frontier
models receive derived profiles, new drafts, and passage-specific defect
reports only; raw commercial books and source-neighbor adjudication stay local.

The first bounded commercial-excerpt ablation is preserved under
`03_scene_lab/runs/s02-autoloom-v3-gabaldon-excerpts/`. It used two local
109/119-word excerpts from different Gabaldon novels, an untouched third-book
holdout, the same frozen 31B-base plan as the prior control, and source-aware
streaming anti-copy checks. It is a clean negative result: zero source overlap,
but abstract agency exposition, no causal antagonist move or protagonist
backfire, the wrong sequence endpoint, and packet leakage during length repair.
See `04_review_governance/s02_autoloom_v3_gabaldon_excerpt_review.md`. The
current recommendation is to keep base-model entropy upstream in plans and
micro-beat atoms, not use this checkpoint as the production novelist.

The completed 26B-A4B sequence-one best-of-eight under
`03_scene_lab/runs/s02-compute-v4.3-a4b/` confirms that boundary. Sampling found
a materially better causal mechanism but not production prose. The harness now
has an immutable `DramaticAtom` / `AtomBundle` layer, weighted atom selection,
separate editorial-overlay hashes, action-versus-consequence realization
evidence, and event-role distance so low n-gram overlap cannot masquerade as
structural diversity. The novelist projection withholds donor prose,
probabilities, scores, model identity, and future beats.

A stronger-novelist boundary sample realized the selected atom bundle into a
2,857-word S02 continuation. It passes every deterministic gate and two
independent literary reviews. This artifact is explicitly labeled as a Codex
agent boundary sample, not a local llama.cpp call. See
`04_review_governance/s02_frontier_novelist_v1_review.md`. S02 alone is ready
for blinded human appraisal, not release; `05_releases` remains untouched.

The preserved 5,832-word S01–S02 merge at
`03_scene_lab/runs/s02-compute-v4.3-a4b/frontier_novelist/s01-s02.codex.v1.md`
is a diagnostic artifact, not an appraisal manuscript. Its inherited S01
prefix was held for the atom-boundary rewrite documented below.

An independent integrated read adds an important qualification: S02 itself is
ready for human appraisal, while the merged story retains a pronounced style
seam from the older S01 prefix. The harness now emits a non-gating sectional
style-discontinuity diagnostic; the inherited prefix measures 12.77 cadence
family hits per thousand words versus 0.70 in S02. See
`04_review_governance/s01_s02_integrated_independent_review.md`. At that review
boundary, the prescribed next step was an atom-boundary rewrite of S01 while
preserving S02 byte-for-byte.

That production step is complete under
`03_scene_lab/runs/s01-atom-rewrite-v1/`. Thirty wording-neutral observable
atoms were partitioned across three scene phases, then three sparse bundles
were selected with fixed stochastic seeds. The novelist packets exposed canon,
endpoint, and actions while withholding donor prose, model identity,
probabilities, scores, and evaluator labels. All three 2,809–3,027-word S01
rewrites pass the deterministic gates and have exact action-and-consequence
evidence for all twelve selected atoms.

Two independent reads accepted candidate B. Four bounded repairs produced the
3,009-word selected S01 at
`03_scene_lab/runs/s01-atom-rewrite-v1/selected/s01-b-somatic-control.codex.v2.md`.
Its cadence-family rate is 1.66 per thousand words versus 0.70 in immutable
S02, reducing the old absolute seam from 12.07 to 0.96. The 5,866-word merged
human-appraisal candidate is
`03_scene_lab/runs/s01-atom-rewrite-v1/selected/s01-s02.codex.v2.md`.

Open the blind three-S01 comparison at
`03_scene_lab/runs/s01-atom-rewrite-v1/appraisal/s01_blind/reader/index.html`
and the complete selected story at
`03_scene_lab/runs/s01-atom-rewrite-v1/appraisal/integrated_story/reader/index.html`.
Both save responses locally and export JSON; automated leak checks pass. The
selection decision and residual human questions are recorded in
`04_review_governance/s01_atom_rewrite_v1_selection.md`. Current validation is
178 tests; immutable S02 retains SHA-256
`8561c609388e564f2d35edcffafec3f60969b96e003c0024241dcb3b5c5cf06e`,
and `05_releases` remains untouched.

### S02 proof-story human appraisal

The completed bootstrap run is at
`03_scene_lab/runs/s02-proof-v1-bootstrap/`. It contains twelve preserved S02
continuations, twenty-four exact-evidence scorecards, reversed-label
tournaments, rejected full-rewrite edits, three minimally repaired complete
proof stories, two independent blind Codex reviews, and balanced human-reader
packets.

The three anonymous stories are 6,309–6,499 words. They pass the preserved
legacy mechanical and anti-copy checks, but are deliberately labeled
`provisional_human_appraisal`: all three dense-model full rewrites failed a
hard gate, scalar revision scores declined, and both blind readers found the
fiction developmental rather than release-ready. Both readers chose anonymous
finalist B as the best base for revision.

Open the all-three packet locally at
`03_scene_lab/runs/s02-proof-v1-bootstrap/appraisal/reader/index.html`, or give
friends the balanced A/B, A/C, and B/C packets under
`appraisal/balanced_pairs/reader/`. The reveal key, generation identities, and
machine scores remain outside every reader directory. `05_releases` remains
empty.

### Prompt autoresearch

The next prompt-engineering campaign is isolated under
`03_scene_lab/runs/prompt-autoresearch-v14-cleanroom/`. Its control contains
structured RGO/canon instructions but no manuscript exemplar. Experimental
arms test actual intimacy-prose conditioning, adjacent scene-graph/prose pairs,
anonymous versus named author conditioning, contrastive back-translation,
prompt encoding, and context dose. Historical project-voice bridges remain in
the anti-copy index but cannot enter prompts until independently generated and
verified by the v2 provenance path.

V12 is a preserved one-call integrity pilot. Its 1,187-word control missed the
word band, passed the other mechanical gates, and reproduced exactly only after
the KV slot was cold. The first warm-cache replay mismatch remains recorded;
the replay command now erases idle slot state before issuing a witness call.

```bash
python3 -m fiction_harness autoresearch corpus compile
python3 -m fiction_harness autoresearch benchmark compile
python3 -m fiction_harness autoresearch campaign init
python3 -m fiction_harness autoresearch round run --round 1
python3 -m fiction_harness autoresearch review export --round 1
python3 -m fiction_harness autoresearch review admit --round 1 \
  --reviewer-id reviewer-a --review-file review-a.json
python3 -m fiction_harness autoresearch traces analyze --round 1
python3 -m fiction_harness autoresearch review admit-research --round 1 \
  --role trace_critic --reviewer-id trace-a --review-file trace-a.json
python3 -m fiction_harness autoresearch review admit-research --round 1 \
  --role research_lead --reviewer-id lead-a --review-file lead-a.json
python3 -m fiction_harness autoresearch decide --round 1
```

The source compiler recovers thirteen numbered examples from the locally
supplied craft book. *Drums of Autumn* is calibration-only and *A Breath of
Snow and Ashes* is a complete holdout; those partitions measure prompt changes
rather than condition them. Corpus manifests record identities, locations,
and hashes. Whatever prose is selected for a prompt enters the anti-copy index.

The literary apprenticeship path can index any supplied local or fetched
source set, retrieve scene-sized prose by lexical match plus craft geometry,
and bind the frozen retrieval directly into an autoloom campaign:

```bash
python3 -m fiction_harness apprenticeship index \
  --manifest data/apprenticeship/CORPUS/corpus_manifest.v1.json \
  --output data/apprenticeship/CORPUS/index
python3 -m fiction_harness apprenticeship retrieve \
  --index data/apprenticeship/CORPUS/index/index_manifest.v1.json \
  --query fixtures/apprenticeship/queries/married-explicit-transaction.v1.json \
  --output data/apprenticeship/CORPUS/retrieval.json
python3 -m fiction_harness autoloom init \
  --campaign-dir 03_scene_lab/runs/NEW-CAMPAIGN \
  --apprenticeship-index data/apprenticeship/CORPUS/index/index_manifest.v1.json \
  --apprenticeship-retrieval data/apprenticeship/CORPUS/retrieval.json
```

Retrieved scenes are ordered broad-to-near before the existing project bridge;
the final prompt bytes remain the live manuscript runway. Source identity is
metadata, not a content gate. Calibration/holdout exclusion preserves the
experiment, and anti-copy decides whether generated prose is admissible.

Round 1 freezes eight topologies and 96 seed/target combinations before
inference. Round 2 is generated from the admitted Round 1 decision and changes
only encoding. Round 3 changes only context dose. Raw scenes are judged before
editing; blind scores are frozen before trace analysis. Every source-copy
abort preserves the partial output as a failed experimental trace. Decisions
require both a hash-linked trace critique and a separate research-lead review;
these happen only after blind manuscript scores are frozen. The full suite
currently contains 292 passing tests.
