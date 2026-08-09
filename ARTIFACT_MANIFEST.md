# Artifact Manifest

Generated 2026-07-24 in the local project workspace.

| Artifact | SHA-256 | Verification |
|---|---|---|
| `00_project_brief/Juicy Chastity Fiction Lab — Project Brief v0.3.docx` | `75bf3aa7e3023a7ced5b6c80c35d9cf8a4057f23ceaf1cf1484d7740c6d4792b` | Ten-page local render inspected; native Google Doc structure and tables verified; native PDF export succeeded |
| `01_source_library/Source Card Deck — 20 MPC + 10 Leverage Dynamics v0.1.docx` | `dc6df5f7f7afd0b4dc309cc864a0cd8bd19d704e7fc034d0badba9cb7459f83e` | Ten-page final render inspected; source hyperlinks present; cards kept together across pagination |
| `02_storyworld_canon/Story Canon Ledger — Fulcrum Pilot v0.1.docx` | `f95cf767f77f9025e1ac3e289c585c48af07625639abcba2d8dae05545a3b9b2` | Three-page render inspected; cast, story law, epistemology, romance invariants, practices, and open decisions present |
| `03_scene_lab/Pilot Scene Cards — S01-S03 v0.1.docx` | `e5d641a089014f6aee8d725394049989364bea9b1ebb178df69715968b8b155f` | Three-page render inspected; numbering restarts for each scene; all source packets and continuity facts present |
| `04_review_governance/Source Transformation Log v0.1.docx` | `b6352428c3d281da6b98490f5697d672804e66d49d9f3c43622547309b71dfe3` | Two-page render inspected; rows do not split; six seeded entries plus eight blank rows present |

## Source coverage

- MPC corpus: 382 documents and 8,336 blocks available in the local read-only
  Alexandria database.
- Selected MPC anchors: 20.
- Selected Leverage/social-influence case dynamics: 10.
- Drive case collection inspected: 14 direct source files.
- Pilot retrieval packets assembled: 3.

## Drive publication state

| Artifact | Drive state | Native Google Doc |
|---|---|---|
| Project Brief v0.3 | Published and verified in `00 Project Brief` | [Open](https://docs.google.com/document/d/1MKSb4nRQP9nt0oWB29rRmvmDXNzGcuyCH5z9EFNwqNE/edit) |
| Source Card Deck v0.1 | Published and verified in `01 Source Library`; 20 MPC cards, 10 Leverage cards, 30 tables, and two native Google resource chips; ten-page native PDF visually inspected | [Open](https://docs.google.com/document/d/1SrXEmYDxdg0olad3jRirdcsKs7mo0p8FvEr-GcF6ZgU/edit) |
| Story Canon Ledger v0.1 | Published and verified in `02 Storyworld & Canon`; five tables and all eight sections present; three-page native PDF visually inspected | [Open](https://docs.google.com/document/d/1g4QqleWNH5pD74A2wXTyoKlo41_2O1I1OO4X62JkYMk/edit) |
| Pilot Scene Cards v0.1 | Published and verified in `03 Scene Lab`; S01–S03 and three scene tables present; three-page native PDF visually inspected | [Open](https://docs.google.com/document/d/1BkWiwl7NWSjIlneKeTf90yQ8pE24izywY87GZ5MABII/edit) |
| Source Transformation Log v0.1 | Published and verified in `04 Review & Governance`; six seeded entries plus eight blank rows present; two-page native PDF visually inspected | [Open](https://docs.google.com/document/d/19ieBaFpdr6eCzMzQJs4xkr7UuJMbvFdpybHdedMyj5I/edit) |

## S02 proof-story bootstrap

Run root: `03_scene_lab/runs/s02-proof-v1-bootstrap/`

| Artifact | Verification |
|---|---|
| `evaluation/tournament.json` | Three four-candidate brackets completed with reversed label order; every final exposed order disagreement and used the declared screen-score tie-break |
| `evaluation/editor/rejected_full_rewrites/` | All three common 31B full rewrites preserved after introducing length, beat-order, or local-HFN failures |
| `evaluation/finalists.json` | Three complete 6,309–6,499-word stories; provisional human-appraisal status; preserved legacy hard-gate carry-forward and full anti-copy recheck recorded |
| `evaluation/internal/blind_review_1.md` | Independent anonymous read; ranking B > C > A |
| `evaluation/internal/blind_review_2.md` | Independent anonymous read; ranking B > A > C |
| `evaluation/internal/critical_assessment.md` | Integrated fiction, judge-calibration, editing, and scaffold assessment with concrete next revision prescription |
| `appraisal/reader/index.html` | All-three static reader packet; local response persistence and JSON export; automated blind check passed |
| `appraisal/balanced_pairs/reader/` | Balanced A/B, A/C, B/C, and all-three HTML/Markdown packets; no scaffold, model, score, or reveal metadata |

Validation at handoff: 157 unit/integration tests pass; all package files exist;
the reader manifest reports no identity leaks; `05_releases` contains no files.

## Native-base prose-conditioning checkpoint

Run root: `03_scene_lab/runs/s02-autoloom-v3-gabaldon-excerpts/`

| Artifact | Verification |
|---|---|
| `context/context_manifest.v1.json` | Two profiling excerpts; third-book holdout excluded; profile/context hashes recorded |
| `native_base_with_base31_plan/calls.jsonl` | One completed 676-word draft plus one completed but packet-leaking continuation; SHA-256 `58cf8378cb33b663a4a1b38731f2b37b68a12912f65430b90f015e577f715fb0` |
| `native_base_with_base31_plan/candidates.jsonl` | Durable `CandidateFailure`; no sequence or candidate admitted |
| `04_review_governance/s02_autoloom_v3_gabaldon_excerpt_review.md` | Critical comparison against prior base and instruction sequence-one checkpoints |

Current validation: 168 unit/integration tests pass. Both 31B launch agents
were removed after the checkpoint; ports 8096 and 8097 had zero listeners and
clients at handback.

## S02 A4B pool and stronger-novelist boundary

Run root: `03_scene_lab/runs/s02-compute-v4.3-a4b/`

| Artifact | Verification |
|---|---|
| `verbalized_to_instruction/candidates.jsonl` | Eight durable 995–1,063-word A4B sequence-one checkpoints; no sequence two generated; seed 22063 selected as causal donor |
| `verbalized_to_instruction/dramatic_atoms.seq1.v1.json` | Six immutable source-backed occurrences and one separately hashed editorial overlay; SHA-256 `d334fd83ca3a2b883fed78c8ea10fd9c1088d36a249801fe73e7809a618afa69` |
| `verbalized_to_instruction/novelist_packet.seq1.v1.json` | Sparse packet excludes donor prose, probabilities, scores, model identity, and future beats; SHA-256 `1c52262a8c2cb4f0537a7e3d8202b7dc36990bcb65763f22ed8c69d1990ce435` |
| `frontier_novelist/s02.codex.v1.md` | 2,857-word S02 continuation accepted by two independent Codex readers; all deterministic gates pass; SHA-256 `8561c609388e564f2d35edcffafec3f60969b96e003c0024241dcb3b5c5cf06e` |
| `frontier_novelist/s01-s02.codex.v1.md` | Held 5,832-word diagnostic merge with byte-identical inherited S01 prefix; not approved for appraisal pending S01 atom-boundary rewrite; SHA-256 `161db907e28c9d324b26ad6668cfffe696e68934332dadae1b9329ea94c14fe8` |
| `frontier_novelist/integrated_literary_diagnostics.codex.v1.json` | Non-gating sectional comparison flags the inherited S01/S02 style seam: 12.77 versus 0.70 cadence-family hits per thousand; SHA-256 `5cd603424a43e3cb8c570b2f9ba4795373b37380143ff0c6bdaddb272544f499` |
| `04_review_governance/s02_frontier_novelist_v1_review.md` | Integrated distributional result, independent-review findings, residual risks, and provenance |
| `04_review_governance/s01_s02_integrated_independent_review.md` | Independent split disposition: S02 accepted for human appraisal; merged story held for atom-boundary S01 rewrite |

Current validation: 177 unit/integration tests pass. All local model services
were removed at the pool boundary; ports 8091, 8096, and 8097 had zero clients
or listeners at handback. `05_releases` remains untouched.

## S01 atom-boundary rewrite and selected appraisal manuscript

Run root: `03_scene_lab/runs/s01-atom-rewrite-v1/`

| Artifact | Verification |
|---|---|
| `atoms/s01_dramatic_atom_pool.v1.json` | Thirty wording-neutral observable atoms, ten in each of three phases; SHA-256 `56012a38a781f1176dc95cd1adaf2f4b102ff3955b2e14ac42e3a0e2d6db4596` |
| `atoms/s01_seeded_bundles.v1.json` | Three sparse twelve-atom bundles chosen with seeds 41017, 41031, and 41047; event-role distance 0.666667–1.0; SHA-256 `61d02b58a7aedd6bf13b36b438e10a4a2561c8dd60337ff1e64f5fafb899755d` |
| `novelist_packets/` | Three canon-and-endpoint packets; donor prose, source spans, scores, probabilities, model identity, and evaluator labels excluded |
| `candidates/` | Three preserved S01 rewrites at 2,840, 3,027, and 2,809 words; all deterministic gates pass and all selected atoms have exact action/consequence evidence |
| `selected/s01-b-somatic-control.codex.v2.md` | Selected 3,009-word S01 after four bounded repairs and two accepting reads; SHA-256 `44b123c0f6fa57b101edd553b9d36e3ed7c2c767f17aaad77f3b2837d47583ce` |
| `selected/s01-s02.codex.v2.md` | 5,866-word integrated human-appraisal candidate; S02 byte-identical to frozen source; SHA-256 `d4bb6004702ee51924ad1e9c5809839b31ddd0fc03c104cf4318f9afc5f9dd51` |
| `evaluation/deterministic_summary.v1.json` | Word count, ordered beats, POV, canon, heat, epistemic separation, anti-copy, packet-leakage, ending, endpoint, and S02 compatibility all pass; S01/S02 cadence-rate delta is 0.96 |
| `evaluation/atom_fidelity_summary.v1.json` | Twelve of twelve selected atoms realized in every candidate and selected v2, each with separate exact action and consequence evidence |
| `evaluation/cold_reads/reviewer_atom_Bv2_acceptance.md` | Independent final acceptance of selected S01 plus immutable S02; recommends no further regeneration |
| `appraisal/s01_blind/reader/index.html` | Anonymous three-S01 comparison with pairwise rankings, seven-point ratings, local persistence, and JSON export |
| `appraisal/integrated_story/reader/index.html` | Complete selected story packet; identity-leak scan passes |
| `04_review_governance/s01_atom_rewrite_v1_selection.md` | Final selection rationale, bounded-repair record, residual human questions, and canonical hashes |

Current validation: 178 unit/integration tests pass. Immutable S02 remains
SHA-256 `8561c609388e564f2d35edcffafec3f60969b96e003c0024241dcb3b5c5cf06e`.
The new merged manuscript is ready for blinded human appraisal, not release;
`05_releases` remains untouched.
