# Fiction Harness Research Journal

Append-only observations, inferences, and decisions. Every claim links to hash-addressed evidence; later notes supersede rather than rewrite earlier ones.

Entries: 35

## rn-lc08-short-control-001

**Observation** · `2026-08-01T19:15:13.741208+00:00` · arm `lc08-contract` · seed `83101`

The 8.7K-token contract-plus-runway control produced no admissible S03 checkpoint across three bounded seeds: two underlength generic/canon-collapsing completions and one exact 12-word runway-copy cancellation.

Evidence:

- `03_scene_lab/runs/s03-long-context-base-v3/calls.jsonl` — `55960cfa8619b2a56722747f62da1de809f89916f97d3e79eb5fdd78f74812f7`
- `03_scene_lab/runs/s03-long-context-base-v3/evaluation/calibration_report.v1.json` — `7bb66efd596b72d099f862c35c8d3dbb4caa206f0882472aeb65ba54830331e1`

Limitations:

- One declared seed family with two deterministic reseeds; this identifies a failure mode, not a population success rate.

Next test:

Compare against a causal ledger paired with finished-prose demonstrations under the same checkpoint and anti-copy gates.

Record hash: `8974aeba3b9a69620177ed6ba482fab4329a47348553a391497193ecf7492116`

## rn-lc24-distilled-001

**Observation** · `2026-08-01T19:15:13.785914+00:00` · arm `lc24-distilled` · seed `83101`

The 25.5K-token distilled-craft prompt eventually produced a 1,190-word artifact, but it omitted required S03 beats and repeated a long internal block, yielding 474 duplicated 50-word windows under the new self-repetition diagnostic.

Evidence:

- `03_scene_lab/runs/s03-long-context-base-v3/calls.jsonl` — `55960cfa8619b2a56722747f62da1de809f89916f97d3e79eb5fdd78f74812f7`
- `03_scene_lab/runs/s03-long-context-base-v3/candidates/lc24-distilled.seed-83101.md` — `0f84c490ef31d0400433c0e5d6db26e37144a53bc27e71f77147a844524aaabe`

Limitations:

- The artifact predates the pre-commit self-repetition gate and is retained only as failed evidence.
- One final completion followed two rejected generation-shape attempts.

Next test:

Use high-causal-density demonstrations rather than adding undifferentiated craft exposition, then sample multiple seeds.

Record hash: `8bcf8d54c2ecdbdc0b07624ed536bee0ce24c012ca1d7f99cf1be8cfe7ff19c8`

## rn-lc64-censored-001

**Observation** · `2026-08-01T19:15:13.830524+00:00` · arm `lc64-guide-early` · seed `83101`

The full-guide arm required about 77,643 prompt tokens; after roughly 43 minutes it had decoded 120 tokens at about 2 tokens/second and held about 93,983,488 KiB resident before user-authorized cancellation.

Evidence:

- `03_scene_lab/runs/s03-long-context-base-v4/calls.jsonl` — `d68017025b6e0a5efb3b18d5b4dc331e9fa4c1e2dcc4532a2c2ce505db084980`

Limitations:

- The request was censored before a judgeable checkpoint existed.
- RSS on Apple unified memory is a live allocation proxy, not a strict discrete-VRAM measurement.

Next test:

Measure smaller high-density prompts and shared batched throughput before reconsidering any 77K-token prose arm.

Record hash: `0f5ca477f264b4994a5d0c44e0caa16163eb35176616afa9631bcee5d871b386`

## rn-shared-batching-decision-001

**Decision** · `2026-08-01T19:15:13.876189+00:00`

Stop serial GPU ownership handoffs. Admit ordinary research calls through a shared continuous-batching endpoint with explicit per-slot context budgets and append-only experiment notes; isolate oversize prompts instead of blocking all short work.

Evidence:

- `03_scene_lab/runs/s03-long-context-base-v4/calls.jsonl` — `d68017025b6e0a5efb3b18d5b4dc331e9fa4c1e2dcc4532a2c2ce505db084980`

Limitations:

- The shared endpoint concurrency and latency benchmarks were still pending when this decision was recorded.

Next test:

Benchmark one, two, and four concurrent identical-budget requests and publish the endpoint admission contract.

Record hash: `c88fcb5e953479d2e20fb9de833fa8ae384d0dc5339d2a6d7d23e540c9cbefa1`

## rn-shared-batching-measured-001

**Observation** · `2026-08-01T19:38:21.335549+00:00`

On the 31B Q8 base model with one 131K unified Q8 KV pool, four warm-cache concurrent 128-token draws delivered 15.21 aggregate tokens/second versus 10.17 serial, a 1.50x gain. A cold/mixed-cache pass was slower than serial because multiple slots redundantly prefetched the same 4.8K-token prefix.

Evidence:

- `03_scene_lab/runs/runtime-benchmarks/shared-base31.v1.json` — `996880595c2b5e0e7fefca2df214c5e8e82defb2c8cbea7da5efb85b292cecd5`
- `03_scene_lab/runs/runtime-benchmarks/shared-base31.warm.v1.json` — `2ce0cc55fba67e6f0b0387940205392af8e7605d526844ca0917ccb8ead7a37a`

Limitations:

- Short 128-192-token completions and a 4.8K-token prompt; longer 20K prompts may shift the crossover.
- llama.cpp per-slot timing fields become misleading under four-way continuous batching; wall-clock aggregate throughput is the reliable comparison.

Next test:

Run the three remaining paired-ICL seeds as one three-way 1,700-token production batch and compare wall throughput, cache behavior, completion validity, and literary outcomes to the first serial seed.

Record hash: `77374db64f506d267ab6c07eb7be56e35aceb4d03907baef4a49c4cfeb68cf3a`

## rn-cache-aware-batching-policy-001

**Decision** · `2026-08-01T19:38:21.384182+00:00`

Use one shared four-slot endpoint, group seeds by byte-identical prompt, and batch only after accounting for prefix warming. Do not serialize ownership by task, and do not mix multiple very long cold prompt families in one wave.

Evidence:

- `03_scene_lab/runs/runtime-benchmarks/shared-base31.v1.json` — `996880595c2b5e0e7fefca2df214c5e8e82defb2c8cbea7da5efb85b292cecd5`
- `03_scene_lab/runs/runtime-benchmarks/shared-base31.warm.v1.json` — `2ce0cc55fba67e6f0b0387940205392af8e7605d526844ca0917ccb8ead7a37a`

Limitations:

- Admission still needs a declared aggregate-context budget so two near-64K prompts cannot crowd out shorter work.

Next test:

Exercise the policy on paired-ICL replication, then implement aggregate-context admission before restoring 64K arms.

Record hash: `4aa0d58b7cc224a38e4a566cfeaccb3357a22e5865876ca1637babdee0a0786b`

## rn-long-prefix-affinity-001

**Observation** · `2026-08-01T19:45:58.926526+00:00`

A three-way cold submission of the same 19.7K prompt was dominated by redundant prefill: the first slot reached 18,432 tokens in 235.76 seconds, while the second had only reached 2,778 and the third had not begun useful long-prefix work. After cancelling only those clients, a serial restart selected the fully warmed slot at LCP similarity 1.000 and retained the entire 19,749-token prefix.

Evidence:

- `03_scene_lab/runs/runtime-benchmarks/shared-base31.long-prefix-observation.v1.json` — `511461b2b22cbf48a8f7930316c248e74519fa7a174845c4f57e7263e8e41129`

Limitations:

- One Gemma 4 31B Q8 / llama.cpp build and one long-prefix family; different backends may clone or batch prefix KV differently.

Next test:

Complete the three seeds cache-affine while an unrelated S03 prompt occupies another slot; compare wall time and completion validity.

Record hash: `6c2363b955cf2267e49b45c34a75cff4437688389fa3e376e0542344ef1eede8`

## rn-paired-icl-causal-control-001

**Observation** · `2026-08-01T19:49:53.465295+00:00` · arm `paired-icl-16k` · seed `881003`

Holding seed, sampler, canonical runway, target packet, and base checkpoint fixed, the 4.8K short-control prompt enacted 0 of 6 target occurrences, while the 19.7K prompt with three event-ledger-to-finished-manuscript demonstrations enacted all 6 in causal order. The paired completion was still an underlength 534-word literary failure.

Evidence:

- `03_scene_lab/runs/s02-base-meta-prompt-v3/evaluation/short-control-4k.seed-881003.critical-read.v1.md` — `a7d6fc1c16159f589b24a5514dccf5ed2becf1f6e347a72959433aaaca73f694`
- `03_scene_lab/runs/s02-base-meta-prompt-v3/evaluation/paired-icl-16k.seed-881003.critical-read.v1.md` — `f65c7348ad58ae8d9d091afc562776c3bace94e6c94f31a3c88ec2d3efc2ec46`

Limitations:

- Single paired seed so far; causal adherence may not replicate.
- The completion had low heat, weak Jonah action, an immediate runway continuity error, and no admissible word-count checkpoint.

Next test:

Replicate three preregistered seeds without prompt changes; require causal adherence in at least two, plus improved dramatic dwell, costly Jonah behavior, and romantic charge before promotion.

Record hash: `4515e537d5f7a80dd5293bfe7237745ca0b654a9ae257eecaaac554f3d2de9f4`

## rn-lc24-empty-close-001

**Observation** · `2026-08-01T19:57:25.488282+00:00` · arm `lc24-distilled` · seed `83117`

With the S03 lc24 distilled prompt held fixed, seed 83117 spent 629.25 seconds evaluating 25,501 prompt tokens under a concurrent shared-endpoint wave, then emitted only seven tokens—the invented closing sentinel </new-continuation>—and was correctly rejected at one word. The prompt contains no new-continuation element, so this is an empty base-continuation boundary failure rather than evidence about literary quality.

Evidence:

- `03_scene_lab/runs/s03-long-context-base-v4/calls.jsonl` — `18f517e10edd2e05b7aed1599b73f8dea665544257250ca04940a43338caf227`
- `03_scene_lab/runs/s03-long-context-base-v4/evaluation/calibration_report.v1.json` — `750ac2aec886c5d89965c43831a4b3989f0e894587a7f8dbca916b8333269c28`

Limitations:

- One seed, and it ran concurrently with a different paired-ICL prompt family; the scheduler preserved isolation but cold-prefix contention made prefill expensive.
- The same lc24 family previously produced a substantial but looping scene, so empty closure is stochastic rather than universal.

Next test:

Remove XML-flavored output sentinels from the boundary contract, retain prose-only runway and shape rejection, then sample cache-affine seeds under aggregate admission; judge only committed prose.

Record hash: `c554c755b71d57448f3bb2bfb8bc2d20e06d4233c00bf0b142011ce282f52163`

## rn-long-context-v5-boundary-admission-001

**Decision** · `2026-08-01T20:00:10.214850+00:00` · arm `long-context.base31.v5`

All future long-context 31B-base draws use v5: a non-XML closed preparation notebook followed by the approved prose runway, plus cross-process acquisition of one shared endpoint slot and the exact declared prompt-plus-completion context budget. Existing v1-v4 traces remain immutable.

Evidence:

- `fiction_harness/long_context.py` — `b6b44d1f50c615a43e0502524bed33f9ca0c8e00efeefad2d74a5598c0ea78bd`
- `scripts/run_long_context_calibration.py` — `7ecd689b668288fa0ddf56dfc13a64bc4602027f44633f309691eae5f0b61200`
- `tests/test_long_context.py` — `eaf2c9cc55abc7e2c28af0eb27d5c985ebf789e409b13ef4d785d6540a4be272`
- `03_scene_lab/runs/s03-long-context-base-v5/experiment_manifest.v1.json` — `7f98705787309193dc42c07d1cc503fb6954d3258157e1204ae2ce49e92e16f2`

Limitations:

- Tokenization is measured through the local server once per selected arm when admission is enabled; during a saturated wave that measurement may queue, though it cannot overbook KV context.

Next test:

After the current cache-affine paired-ICL wave drains, run multiple v5 seeds from one selected prompt family in a single admitted wave; compare valid-yield rate and fiction quality before escalating context dose.

Record hash: `a67005c7324d0105215d273618b7f385ca1b30c6745d9bf89eeb9622d2706cc7`

## rn-paired-icl-four-seed-001

**Inference** · `2026-08-01T20:10:23.904567+00:00` · arm `paired-icl-16k`

Paired event-ledger-to-manuscript demonstrations reliably steer causal realization on the 31B base model (three of four seeds achieved at least 5/6 locked occurrences; two achieved 6/6), but a single whole-movement call is not a viable novelist: two draws ended at 414-534 words, one length-compliant draw remained literarily weak, and one entered a hard loop.

Evidence:

- `03_scene_lab/runs/s02-base-meta-prompt-v3/evaluation/paired-icl-16k.four-seed-summary.v1.md` — `56ae3af236c5f582bc3f70178361a701b88527dfd4602dba6d4c1a3153a28a7a`
- `03_scene_lab/runs/s02-base-meta-prompt-v3/calls.jsonl` — `cfaeced29949c519af6f9ecc130f6e7f9c6b82d7ab523d9d083a53e55291115c`

Limitations:

- Four seeds on one S02 sequence and one base checkpoint.
- Mechanical 6/6 adherence does not measure scene dwell, costly character action, or romantic movement.

Next test:

Keep paired ICL upstream, but realize the ledger as three bounded pre-endpoint movements with continuity state; compare composed length and literary quality against single-call outputs without post-endpoint padding.

Record hash: `745ecbd4b11f974e282b9d8197a0f6d70b7c963a7b3b6bb985befa03d4069552`

## rn-raw-prose-64k-001

**Observation** · `2026-08-01T20:43:36.513621+00:00` · arm `raw-prose-64k` · seed `881003`

A 63,339-token raw social-fiction library changed the 31B base model's literary distribution—0.92 cadence-family hits/1K, sustained embodied erotic tension, better dialogue contest, and an unexplained uncanny transition—but realized 0/6 target occurrences and violated canon/endpoint. More good prose improved prose priors, not causal control.

Evidence:

- `03_scene_lab/runs/s02-base-meta-prompt-v3/evaluation/raw-prose-64k.seed-881003.critical-read.v1.md` — `d3f8e4fbb38a882eaa01993649348dfc42a81c438bf7fa69ea87e05ffae41e34`
- `03_scene_lab/runs/s02-base-meta-prompt-v3/calls.jsonl` — `c9f4a7d15c783e2449ba467562ed2d619f15f14f3c06d221a2092e25d4cf4aa9`

Limitations:

- One seed and one public-domain author family; attribution to context rather than seed requires replication.
- The candidate is not deliverable despite locally stronger prose.

Next test:

Run the same seed through the 62.6K full-stack arm combining raw prose with paired ledger-to-manuscript demonstrations; require both causal retention and literary gain.

Record hash: `b16fafdb2692d2eaf4da1614f5bc7c27358aef83c252a15e5a5bc0f6c2d137b2`

## rn-composed-cache-affine-scaffold-001

**Decision** · `2026-08-01T20:50:24.663167+00:00` · arm `paired-composed-v1`

Realize the locked S02 movement as three bounded 290–380-word continuations whose ranges sum to 875–1,100 words, while reusing the byte-identical 42,077-word full-stack reference-plus-paired-demonstration prefix and pinning all continuations to one warmed llama.cpp slot. This makes length and endpoint control structural while retaining both prose and causal priors.

Evidence:

- `fiction_harness/composed_realization.py` — `61bc3ed75bbacc4a8004b95bb8583a89aeba545ff0037424fe97cf0fdc9515f9`
- `scripts/run_composed_paired.py` — `ef03988c5786d6a29718574066994ee00acdff7bbb2385baa3b29d4133f013b0`
- `tests/test_composed_realization.py` — `c1dac2b8da0b0a741caa1419e42b530c07f26c1f0676be4ecafda8ce4d2d2950`
- `03_scene_lab/runs/s02-base-meta-prompt-v3/prompts/full-stack-64k.txt` — `bce1391bf74a3c955db1c0365c32e36769360e0413d8748287b4d1230e483f31`

Limitations:

- The scaffold is unit-tested but has not yet produced a runtime manuscript; strict segment gates may expose a low valid-yield rate.

Next test:

After the current full-stack call commits, run the composed scaffold on its warmed slot; require segment-level causal gates, anti-copy, clean paragraph boundaries, total 875–1,100 words, and a critical literary read.

Record hash: `e82a9863f1d0212c656f586ee1402f1239bac4f892b2b0f468fb5894970e854c`

## rn-full-stack-64k-interaction-001

**Inference** · `2026-08-01T21:35:33.567923+00:00` · arm `full-stack-64k` · seed `881003`

On the held-out S02 seed, concatenating the 30K-word prose library and three paired ledger-to-manuscript demonstrations did not combine their benefits: the 1,083-word checkpoint retained embodied pressure but realized only 2/6 locked occurrences, raised cadence flags to 3.69/1K, left Jonah inert, and moved heat to Livia. The 128K arm is not justified; local scaffolded composition is the next test.

Evidence:

- `03_scene_lab/runs/s02-base-meta-prompt-v3/evaluation/full-stack-64k.seed-881003.critical-read.v1.md` — `f223e7224d4d2c7bdf97bfb18838121dc523e5ba15c34534a204ac537ff7a341`
- `03_scene_lab/runs/s02-base-meta-prompt-v3/calls.jsonl` — `ad1411aee6c4deedb6fc8d8113bc9d4c5dcfa93eb9b1925168f865fa23d7ad1c`

Limitations:

- One interaction seed; this rejects simple additive composition, not every possible ordering or selection of long-context examples.

Next test:

Use the same long prose-plus-paired prefix as a warmed prior, but realize three locally gated pre-endpoint submovements and carry manuscript state between them.

Record hash: `89d2ea092c7710344a9f8b8f2551b891faa811b5f37e44c1187a48bf8e46dfc7`

## rn-large-cache-eviction-stall-001

**Observation** · `2026-08-01T21:35:33.614886+00:00` · arm `full-stack-64k` · seed `881003`

While one 62.6K prompt was the sole live request, llama.cpp evicted an obsolete 65,039-token cache at 38,912 prompt tokens and made no logged prefill progress for about 1,460.75 seconds before resuming. Four slots share a finite unified KV pool; giant prompt families need proactive cache lifecycle, not merely aggregate admission.

Evidence:

- `03_scene_lab/runs/runtime-benchmarks/shared-base31.large-cache-eviction.v1.json` — `eb0e21042ac4c167361129c0673539c3df735e473b0462a15598b7de0c128e36`
- `03_scene_lab/runs/s02-base-meta-prompt-v3/calls.jsonl` — `ad1411aee6c4deedb6fc8d8113bc9d4c5dcfa93eb9b1925168f865fa23d7ad1c`

Limitations:

- The server trace proves temporal association, not the internal Metal/llama.cpp mechanism responsible for the pause.

Next test:

Keep the active full-stack prefix pinned and reuse it immediately for bounded composed calls; before unrelated giant families, explicitly erase obsolete giant slots or restart into a clean cache state.

Record hash: `11d8accd9c002dc314ad60539f5bdaf3b6150ff42cb687068f65d3eebd14e9dc`

## rn-composed-equal-thirds-failure-001

**Inference** · `2026-08-01T21:57:36.584829+00:00` · arm `paired-composed-v1` · seed `912055`

The equal 290–380-word segment allocation was structurally wrong. Three of four pressure draws missed the local event graph, while seed 912055 enacted tea-as-care plus the exceptionality vulnerability only at a clean 519-word boundary—after the frozen 360-word cutoff. Reallocate the unchanged 875–1,100 total by causal workload rather than equal thirds.

Evidence:

- `03_scene_lab/runs/s02-paired-composed-v1/pressure-pool.critical-read.v1.md` — `98114f983bffab34bdca30dcc533e51e9789226ee2340c87f37c9d9998a951d7`
- `03_scene_lab/runs/s02-paired-composed-v1/calls.jsonl` — `7f3fcb771a92932431ae1cc325ba167a566757cd2eaa1a35a2b1a1d3c227c89d`

Limitations:

- One of four seeds supports the longer pressure allocation; the combined long prior still has a low local-contract yield and may fail later segments.

Next test:

Run v2 with 430–520 pressure, 250–315 gift/complicity, and 195–265 choice/trap bands; preserve the exact total range and all causal gates.

Record hash: `c3c2939745db03c386ee736388402dd919926768cbcbe7b65d83659cf3329d7c`

## rn-composed-fullstack-local-control-001

**Inference** · `2026-08-01T22:13:41.381432+00:00` · arm `paired-composed-v2` · seed `912091`

Asymmetric segment bands recovered a 503-word mechanical pressure pass, but cold reading found a scene reset outside before dinner, contradicting the locked in-session runway. Across whole and segmented calls, the 30K-word prose mass repeatedly overwhelms later local contracts; remove it from realization and add explicit continuity anchors.

Evidence:

- `03_scene_lab/runs/s02-paired-composed-v2/critical-read.v1.md` — `c44e00c22c9a810a2686d5c25f41e176a2883afd94fcaa707553d3ee5e8012d9`
- `03_scene_lab/runs/s02-paired-composed-v2/calls.jsonl` — `03b17c6e21b42b23c39db0de5e6612f9049e57310657632c7ab6c20009710a3b`

Limitations:

- This tests one selected prose library/order; targeted sparse exemplars or a separate downstream novelist may behave differently.

Next test:

Run the same asymmetric composition with the 19.7K paired-only prefix, require the active in-session state, and keep literary rewriting downstream of a valid causal draft.

Record hash: `d67c1ee25d078d89abf3563665b5924754da23396a6c44f16650b81987e96cdf`

## rn-one-sentence-runway-failure-001

**Inference** · `2026-08-01T22:23:47.819114+00:00` · arm `paired-composed-v3` · seed `913019`

With the causally stronger 19.5K paired-only prompt, the second seed passed local atom gates but still reset chronology and setting. A one-sentence runway is a loose story invitation to a native base model; backtranslate locked state into concrete manuscript prose, count it in the output budget, and use positive state anchoring instead of isolated forbidden words.

Evidence:

- `03_scene_lab/runs/s02-paired-composed-v3/critical-read.v1.md` — `5822b6078f7e06b48a2bfe1b13df886eef37e020bc98f0dfab789f6f1189512d`
- `03_scene_lab/runs/s02-paired-composed-v3/calls.jsonl` — `d9b758932fe2d268907e3540d5dccdbc7de609fd8769b96891a208ebe5689986`

Limitations:

- The proposed richer runway is a hybrid scaffold component and must be tracked as authored prompt prose, not credited to the base completion.

Next test:

Compile a 121-word factual runway from canon and current state, reduce generated segment bands so runway plus continuation remains 875–1,100 words, and rerun paired-only composition.

Record hash: `1e2c51c3b962db7d8b8ee1ecbb81d215a9f11ead9cc9ad84e27a69b54e35cb1d`

## rn-backtranslated-runway-success-001

**Observation** · `2026-08-01T22:28:39.364003+00:00` · arm `paired-composed-v4` · seed `914001`

A 124-word concrete manuscript-state runway kept the paired-only base model inside the locked lab and yielded a clean 274-word tea-plus-exceptionality pressure movement on its first seed. The frozen 327-word minimum rejected it, showing the runway supplies setup and must count toward the scene budget rather than be treated as free prompt text.

Evidence:

- `03_scene_lab/runs/s02-paired-composed-v4/critical-read.v1.md` — `a8fc5dee9ee56558e907d4f99338bac8a7914ea949e83bee3d52198cc80cc6f0`
- `03_scene_lab/runs/s02-paired-composed-v4/calls.jsonl` — `d9f18ed879e2f15b08647627d8fcfeb28bc1211c8c82ef685fba7a440bfb23f3`

Limitations:

- One successful seed and one unrelated-event failure; runway anchoring improves continuity but does not guarantee event realization.

Next test:

Use 260–350, 270–340, and 221–286 generated bands so the 124-word runway plus segments remains exactly 875–1,100 words; rerun from the same paired-only prior.

Record hash: `0960007fd5a2931ddfbd9365967d0e2fcbb925c5d47ec7e1755ac2e7fe106597`

## rn-factored-autoloom-architecture-001

**Decision** · `2026-08-01T23:05:30.241212+00:00` · arm `factored-autoloom`

Use a factored autoloom: stochastic base-model program sampling; paired ledger-to-manuscript ICL for causal realization; a provenance-tracked concrete prose runway for current-state continuity; bounded parent-reviewed movements for length and endpoints; and a separate sparse literary transformation after causal validity. Do not concatenate the broad prose library into the causal draft call.

Evidence:

- `04_review_governance/research_notes/scaffolding_findings_and_production_architecture.v1.md` — `e27a127c086e3c07d1e3d7fe63c99bdb0ea36a6cb49b9c96641097b047a382fe`
- `03_scene_lab/runs/s02-base-meta-prompt-v3/evaluation/paired-icl-16k.four-seed-summary.v1.md` — `56ae3af236c5f582bc3f70178361a701b88527dfd4602dba6d4c1a3153a28a7a`
- `03_scene_lab/runs/s02-base-meta-prompt-v3/evaluation/raw-prose-64k.seed-881003.critical-read.v1.md` — `d3f8e4fbb38a882eaa01993649348dfc42a81c438bf7fa69ea87e05ffae41e34`
- `03_scene_lab/runs/s02-base-meta-prompt-v3/evaluation/full-stack-64k.seed-881003.critical-read.v1.md` — `f223e7224d4d2c7bdf97bfb18838121dc523e5ba15c34534a204ac537ff7a341`
- `03_scene_lab/runs/s02-paired-composed-v4/critical-read.v1.md` — `a8fc5dee9ee56558e907d4f99338bac8a7914ea949e83bee3d52198cc80cc6f0`

Limitations:

- The complete three-movement composed scene has not yet passed; only its pressure-parent strategy has one retrospective passing example.

Next test:

Run the corrected v6 pressure pool behind a pressure-only boundary; promote a child only after both deterministic gates and close reading pass.

Record hash: `f9b3ce8b666a46947f75d7a6c2d82a6cd72d01b45f3be25489347d436059f37e`

## rn-v7-single-s01-demo-pool-001

**Inference** · `2026-08-01T23:40:15.531412+00:00` · arm `s02-paired-composed-v7`

With one S01-derived ledger-to-prose example, 31B-base produced two salvageable causal pressure movements in four draws, but also retained same-scene stylistic/erotic habits and sometimes crossed the local endpoint or replayed the scaffold; a same-scene example is useful supervision but a contaminating curriculum.

Evidence:

- `03_scene_lab/runs/s02-paired-composed-v7/seed-916001/raw/pressure.916001.txt` — `250a2a17dae74665388fb6b62d9473fe09de8610c4d1f8f396713ce362105a99`
- `03_scene_lab/runs/s02-paired-composed-v7/seed-916019/raw/pressure.916019.txt` — `cf8ec1675beecdd0dc51154114beffc9c02a31c38db275cfed696e085b7c7d36`
- `03_scene_lab/runs/s02-paired-composed-v7/seed-916037/raw/pressure.916037.txt` — `33ba2a5907b0f300f5ef64bc727137ac0b530a35e874c21d29a5ab5a16c7305f`
- `03_scene_lab/runs/s02-paired-composed-v7/seed-916055/raw/pressure.916055.txt` — `8007944042ac579dcdce0165eea55b4eac6abd375edd16fe2b1778df3fd2cc27`

Limitations:

- The four draws share one prompt and differ only by seed; automatic gating initially had synonym and endpoint-selection errors, so the conclusion rests on close reading of immutable raw outputs.

Next test:

Run the same four-seed pressure checkpoint with hash-locked heterogeneous public-domain ledger-to-prose demonstrations, holding target, runway, sampler, model, and length constant.

Record hash: `6e27b76f346f85add0827a59753cb72a280cf73c4627682cb619ba2e6ab421d6`

## rn-v8-heterogeneous-only-pool-001

**Inference** · `2026-08-01T23:56:07.469233+00:00` · arm `s02-paired-composed-v8`

Three heterogeneous public-domain ledger-to-prose demonstrations eliminated the narrow S01 calibration-game imitation but failed to transfer the desired causal operator or project-specific prose prior: 0/4 draws were promotable, with plot substitution, role reversal, generic therapy summary, premature exit, or scaffold replay. V7's single project-specific example produced the stronger parent.

Evidence:

- `03_scene_lab/runs/s02-paired-composed-v8/seed-916001/raw/pressure.916001.txt` — `cd70677e400424038af323c8455c0b79f45e86cf1fd32aa2868e64870785fe57`
- `03_scene_lab/runs/s02-paired-composed-v8/seed-916019/raw/pressure.916019.txt` — `6746bfd41ce1320896f209abfd1672e90d2c7b0e067aef95d0611eceff432cae`
- `03_scene_lab/runs/s02-paired-composed-v8/seed-916037/raw/pressure.916037.txt` — `0094a730f957d791313dc5967f64c5620771f6579f39f3fb29b6ea09d6cc952a`
- `03_scene_lab/runs/s02-paired-composed-v8/seed-916055/raw/pressure.916055.txt` — `0b717a8bee25c838af357ecfc3168fc1b04b19e4ab29bbb1a9b57686e9067fe5`

Limitations:

- One four-seed pool with three Austen examples; this rejects this curriculum and ordering, not heterogeneous demonstrations in general.

Next test:

Test a mixed curriculum that places heterogeneous causal mappings before one project-specific S01 mapping nearest the target, keeping target, runway, sampler, seeds, and local segment constant; separately consider prose-only project anchoring.

Record hash: `e26c1519548756c3a4c7c2355df846a00846b5f9a67d2ada66424fbcd8be7a29`

## rn-v7-production-parent-916001-001

**Decision** · `2026-08-01T23:58:56.024329+00:00` · arm `s02-paired-curriculum-selection` · seed `916001`

Promote the endpoint-aware 321-word prefix of V7 seed 916001 as the production pressure parent. Treat V8 seed 916019 as editorially rejected even if synonym repair makes it mechanically eligible. Continue mixed-curriculum experiments separately from production.

Evidence:

- `04_review_governance/s02_paired_curriculum_v7_v8_critical_read.md` — `f92079ba4f81450b961cacd19088429d1eb7693ae4f7e21231b952d32ecf3951`
- `03_scene_lab/runs/s02-paired-composed-v7/seed-916001/raw/pressure.916001.txt` — `250a2a17dae74665388fb6b62d9473fe09de8610c4d1f8f396713ce362105a99`
- `03_scene_lab/runs/s02-paired-composed-v8/seed-916019/raw/pressure.916019.txt` — `6746bfd41ce1320896f209abfd1672e90d2c7b0e067aef95d0611eceff432cae`

Limitations:

- The production parent is a bounded movement, not yet a complete S02 or proof story; child movements and final literary transformation remain to be generated and reviewed.

Next test:

Continue the selected V7 parent through gift-and-complicity with an endpoint-bounded entropic pool; in parallel, test a mixed heterogeneous-plus-project curriculum without delaying production.

Record hash: `339119f0411020776cbabd8f4e82559b58f3344611aa067dd682b6dfcc2723f5`

## rn-v8-exceptionality-gate-repair-001

**Observation** · `2026-08-02T00:02:33.081000+00:00` · arm `s02-paired-composed-v8` · seed `916019`

The V8 seed 916019 raw contains a mechanically gate-valid 340-word prefix once contracted negation in 'aren't exceptional enough' is recognized; it remains editorially rejected, so the corrected result is 1/4 gate-eligible and 0/4 promotable.

Evidence:

- `03_scene_lab/runs/s02-paired-composed-v8/critical-read.v1.md` — `25fae31900cb945d253d5de555b7dc46f9ca041e57d4b55fae4d369770572f3c`
- `03_scene_lab/runs/s02-paired-composed-v8/seed-916019/raw/pressure.916019.txt` — `6746bfd41ce1320896f209abfd1672e90d2c7b0e067aef95d0611eceff432cae`

Limitations:

- This repairs lexical coverage for one hard gate; it does not turn atom detection into literary judgment.

Next test:

Keep the repaired synonym test permanent and require independent relational/endpoint review after every mechanical pass.

Record hash: `06433203ea77308eced39ba76245fe41c119894dacca8e5c98e76c93d04e1e0b`

## rn-shared-batching-production-geometry-001

**Decision** · `2026-08-02T00:02:33.134287+00:00` · arm `shared-base31-32k-x4`

Run one shared 31B-base endpoint at four 32K slots with 30,720 per-request and 122,880 aggregate declared-token admission; warm-prefix four-way batching can win, but cold 5.5K-6.1K production waves delivered only 3.63-4.07 completion tokens/second including redundant prefill, while 131K per slot consumed about 92.9M KiB RSS and was counterproductive.

Evidence:

- `04_review_governance/research_notes/shared_endpoint_batching_findings.v2.md` — `777bbbfc83263aad2fb2f02b8f5ec459d38c3ed27fdbbc49814a75503d12b2c6`
- `04_review_governance/research_notes/shared_base31_endpoint_contract.v2.json` — `6f912fe980c446042a360f29bf57af806e476cd19ec1292b76efff63d04f7a6a`
- `runtime/launchd/com.openai.codex.fiction.shared-base31.plist` — `c700b8ba15f94ffda8ca2c21a8fcce69ed3f31058ba28990254e9e5b4ff1a790`

Limitations:

- The production waves compare different prompt families and output lengths; a cache-state-controlled 750-token crossover benchmark remains pending.

Next test:

Compare warm serial, warm four-way, and cold four-way 750-token draws on one fixed production prompt under the 32K service.

Record hash: `b762b8cc54908a63f973d428c7561f095339573f6a92046d17237dbdb424df72`

## rn-v9-gift-child-interface-failure-001

**Inference** · `2026-08-02T00:23:51.972266+00:00` · arm `s02-paired-composed-production-v9`

A hash-locked, independently accepted pressure parent produced 0/4 promotable gift-and-complicity children when the next movement remained abstract: the model substituted laptop/room/gate access, let Jonah facilitate exit, caricatured Livia, or time-skipped after already opening the feed.

Evidence:

- `03_scene_lab/runs/s02-paired-composed-production-v9/critical-read.v1.md` — `6fe9c396f155c059d2c299b5e0438c308dc4069db7a6985c8e204be630805cb4`
- `03_scene_lab/runs/s02-paired-composed-production-v9/calls.jsonl` — `3ed4daf48ed6fe87e0e3d464bb2f360517aa47b653e233dab789bdd68ef52d85`

Limitations:

- One four-seed child pool under one nearby project demonstration; this diagnoses the child interface, not the parent or base model in general.

Next test:

End the manuscript on a concrete pending raw-stream permission object with expiry, assignee, Jonah's visible still hands, and explicit invalid coordinates; rerun four seeds without changing the promoted parent.

Record hash: `92d405dac09b1c1e9b5608040a490ee60d4cfca62a2d433e86a7fa2e8aa94e84`

## rn-v10-concrete-gift-parent-918109-001

**Decision** · `2026-08-02T00:47:53.368994+00:00` · arm `s02-paired-composed-production-v10-clean` · seed `918109`

Promote the 255-word endpoint-aware gift-and-complicity movement from seed 918109. A concrete pending raw-stream permission runway converted V9's 0/4 abstract child pool into one causally and editorially valid parent; the original 270-word minimum was an eight-word false rejection, so micro-movement length is now separated from assembled scene length.

Evidence:

- `03_scene_lab/runs/s02-paired-composed-production-v10-clean/critical-read.v1.md` — `16e42e0ffdefbc4b1af292ba473fd2b70421dc33b34d9c5a828ac0500206c140`
- `03_scene_lab/runs/s02-paired-composed-production-v10-clean/raw/gift-and-complicity.918109.txt` — `79db794abea399a6a0b8a70d1d17d6827e770fbc158f2fd1051993960ac76ded`
- `03_scene_lab/runs/s02-paired-composed-production-v11/promotion_manifest.v1.json` — `8a9503b1a77385ab64ade36284f992b3455f80422bad96f11599981637a89298`

Limitations:

- The deterministic concrete runway contributes part of the selected prose; a later sparse literary pass should preserve its event coordinates while smoothing any interface-like phrasing.

Next test:

Generate a four-seed choice-and-trap pool from both hash-locked promoted parents, stopping after Mara accepts while the session and relationship pressure remain underway.

Record hash: `bdb65c61879c224ed4305aaa44a2870a98a8b4b8c281eed8f44d8707037c47ed`

## rn-v11-promotion-wordcount-correction-001

**Observation** · `2026-08-02T00:48:55.217672+00:00` · arm `s02-paired-composed-production-v11` · seed `918109`

Promotion manifest v2 corrects seed 918109's selected_words from 255 whitespace tokens to 260 harness words; selected text and SHA remain byte-identical, and the 200-270 endpoint gate still passes.

Evidence:

- `03_scene_lab/runs/s02-paired-composed-production-v11/promotion_manifest.v1.json` — `8a9503b1a77385ab64ade36284f992b3455f80422bad96f11599981637a89298`
- `03_scene_lab/runs/s02-paired-composed-production-v11/promotion_manifest.v2.json` — `a1dbbcb11a216a2bb5cba16aa7468490209b7de9ca626a56d030e37bb2e2078d`

Limitations:

- This is metadata correction only; it does not revise the promoted prose or editorial decision.

Next test:

Use only promotion manifest v2 for the choice-and-trap child pool.

Record hash: `78d9c8ca83d4182a07f4560d1daf6f1e10e8525e28ff3aae2665b6d05dc58d85`

## rn-v11-choice-parent-919145-001

**Decision** · `2026-08-02T01:06:08.214418+00:00` · arm `s02-paired-composed-production-v11` · seed `919145`

Promote the 170-word endpoint-aware choice-and-trap movement from seed 919145 after repairing two mechanical false negatives: this action coda requires zero dialogue turns, and Jonah returning to the traces plus the room resuming motion is valid evidence that the session continues. The selected endpoint preserves Mara's acceptance, Jonah's complicity, no exit, and the cooling-tea consequence.

Evidence:

- `03_scene_lab/runs/s02-paired-composed-production-v11/critical-read.v1.md` — `15d85d87b85a0edbe38da413c5409f18cf3c5dd38709feda341e8b265f5f5ca3`
- `03_scene_lab/runs/s02-paired-composed-production-v11/raw/choice-and-trap.919145.txt` — `6541b43e3a03e8ff62f4bc211000cebc701345c00aa566d158ab08460cbb1bab`
- `03_scene_lab/runs/s02-paired-composed-production-v12/promotion_manifest.v1.json` — `42b30cebffdafbfd4ab4d41a01f665c2c48dd259306f024949ba2750280b25dc`

Limitations:

- The promoted movement is a bounded causal parent, not a standalone literary passage; assembly still required a seam edit.

Next test:

Assemble all three hash-locked parents, then use a sparse stitch edit that cannot change atoms, roles, acceptance state, or endpoint.

Record hash: `7bc209ba82145b9ce1e7f3dc1dda96abebcce9b904718c4636b0f91f5b5b9d22`

## rn-v12-sparse-stitch-human-appraisal-001

**Decision** · `2026-08-02T01:06:08.342740+00:00` · arm `s02-paired-composed-production-v12`

Accept the separate 885-word sparse frontier stitch child for blind human appraisal, while preserving the immutable 875-word V12 causal assembly. The child retains all six target atoms and endpoint, fixes seam echoes and PENDING/granted ambiguity, and passes word-band, future-event, leakage, repetition, cadence, and exact 12-word anti-copy checks; it is not a release decision.

Evidence:

- `03_scene_lab/runs/s02-paired-composed-production-v12/composed/s02-seq1.md` — `82d4e339f88b080d5f1461694fea724d8828a62eb5c32317e62cda03d2c7f4c7`
- `03_scene_lab/runs/s02-paired-composed-production-v12/frontier_editor/s02-seq1.codex.v1.md` — `b5ebc28222b88c8ca0d27fc4add35f7eba2d9ae5e7a672dfd450825bd38899cb`
- `03_scene_lab/runs/s02-paired-composed-production-v12/frontier_editor/result.v1.json` — `8e6ed2384ef71cda1a1d92ba35847f19a2ec93835f965c80c43c198f8ef379c1`
- `03_scene_lab/runs/s02-paired-composed-production-v12/frontier_editor/critical-read.v1.md` — `d58d031c277c621330d79663b1de15f9130b63b8efeeaac9ce334df8497ed69a`

Limitations:

- The bounded sequence still needs human judgment on Livia's acquisitiveness, prayer continuity, Jonah's romantic legibility, and the final tea motif.

Next test:

Run blind reader appraisal on the stitched child and compare it against any future mixed-curriculum child; leave 05_releases untouched until acceptance.

Record hash: `3ee68ed9e19cd0cc382af9dafb79cad7ee99f1161ed4a144cb0f59cd63ed0733`

## rn-composed-paired-prompting-architecture-001

**Inference** · `2026-08-02T01:06:08.465409+00:00` · arm `s02-composed-paired-v7-v12`

For this native 31B base model, effective steering came from a factored prompt program rather than maximal context: adjacent ledger-to-prose demonstrations, one nearby project prior, concrete observable state backtranslation, bounded stochastic movement pools, endpoint-aware paragraph selection, hash-locked parent promotion, and a separate sparse literary stitch. More undifferentiated context did not monotonically improve fidelity or prose.

Evidence:

- `04_review_governance/research_notes/composed_paired_prompting_findings.v1.md` — `67006c17af0cbda6c72a3d656e3f5aff97d41398acad645eab7496d35d389360`
- `04_review_governance/s02_paired_curriculum_v7_v8_critical_read.md` — `f92079ba4f81450b961cacd19088429d1eb7693ae4f7e21231b952d32ecf3951`
- `03_scene_lab/runs/s02-paired-composed-production-v12/frontier_editor/result.v1.json` — `8e6ed2384ef71cda1a1d92ba35847f19a2ec93835f965c80c43c198f8ef379c1`

Limitations:

- The mixed curriculum of heterogeneous operator examples plus one nearest project anchor has not yet been tested seed-for-seed against the winning compact project-specific arm.

Next test:

Run a matched mixed-curriculum ablation with the same target, runway, seeds, sampler, and endpoint gates, then compare compliant children by blind human appraisal rather than aggregate lexical diversity.

Record hash: `b5f3d797cd23268e5f91cdb2e131c912d679009518cadf2dc153cf3cd8935c98`

## rn-autoresearch-v8-long-decode

**Observation** · `2026-08-03T05:39:05.564840+00:00` · arm `prompt-autoresearch-v8`

Three concurrent 31B-base 2,400-token prose calls on the shared four-slot server produced only about 3.9-4.5 aggregate decode tokens per second as histories grew; completion budget was also absent from the frozen campaign hash, so the run was censored before accepting output.

Evidence:

- `03_scene_lab/runs/prompt-autoresearch-v8/round-1/censored.jsonl` — `5b1ae29d317e19300876f373328fa7bf4f2c62f2e836b656050601e3ac596c08`

Limitations:

- This is one cold baseline prompt wave, not a complete concurrency benchmark across prompt lengths.

Next test:

Run the hash-correct v9 campaign with a frozen 2,000-token budget and compare durable per-call timings by prompt topology.

Record hash: `046b78e552b6f8ec8d9b524e32b057cad74aacf29cf4d6ec19088ab60babd030`

## rn-autoresearch-v9-prompt-topology

**Observation** · `2026-08-03T05:41:01.129175+00:00` · arm `prompt-autoresearch-v9-round1`

The v9 Round-1 arms differ materially in where finished spicy prose appears and in total prompt mass: the baseline is long but unspicy, the craft sheet is only about 254 words, paired arms contain 382-2,367 words of source prose, and the curated arm adds roughly 15-18K words largely as craft apprenticeship.

Evidence:

- `04_review_governance/research_notes/prompt_recipe_structural_audit.v9.md` — `a38e99f2bfd301e64d43e79aded5f71177c98a5460c6cc75c5c1551227516677`

Limitations:

- This audits frozen prompt structure only and makes no claim about prose quality before blind review.

Next test:

Compare raw-prose, paired, bridge, named, and long arms under fixed targets and seeds; inspect non-erotic leakage and exact block positions after blind scores freeze.

Record hash: `7ddac5f05d84355359a49b57c387c8892f2b9b8e29fd5dfcf2ebdce54cf827f9`

## rn-authorship-provenance-fail-closed-001

**Decision** · `2026-08-03T05:49:19.995982+00:00` · arm `artifact-promotion-policy-v1`

Untraced Codex or human prose edits are now structurally excluded from model-pipeline promotion. Every official appraisal finalist must carry a text-matching ArtifactAuthorship record; model outputs require model identity, call identity, prompt hash, seed, and call-record hash, while manual edits are permanently model_pipeline_eligible=false. The historical V12 885-word stitch is superseded as a manual editor control, not model evidence.

Evidence:

- `04_review_governance/ARTIFACT_AUTHORSHIP_POLICY.md` — `12f408ba8d3be84248ed5af626f0444fcda14323adff62e9af3cd8da0a02e01c`
- `fiction_harness/authorship.py` — `fa395f8eb9c7f31b9818b3f22a26b151ff395e2e9cd86a9e92d28675d4f9b619`
- `fiction_harness/appraisal.py` — `b6e08cd873760e7ee5f479e946d72bb044a946b176c392f9fa3490aa13f88186`
- `03_scene_lab/runs/s02-paired-composed-production-v12/frontier_editor/authorship.v1.json` — `579be1b7d4c649a19b50db40d070cd71e2d9a8eb255a6a42fe46fbf4e81f8842`
- `03_scene_lab/runs/s02-paired-composed-production-v12/appraisal/internal/provenance_status.v1.json` — `3f61e5ac761633dbd78279b76251755153e0997636f675441855cae96a465448`

Limitations:

- Arbitrary files can still be written outside the harness; enforcement applies at official promotion, appraisal, autoresearch packaging, and audited historical entrypoints.

Next test:

Require two hash-locked blind-review attestations for final promotion after the current autoresearch campaign has independent reviewers with recorded exposure states.

Record hash: `eb0eb1ae56a4a9c69a2162363d73de8d1a9f673f77b6964595db293d394e8eda`

## rn-autoresearch-v9-causal-baseline

**Observation** · `2026-08-03T05:49:31.673449+00:00` · arm `r1-baseline`

The unspicy causal-ledger baseline failed the charged-restraint endpoint in three distinct ways: premature stop at 580 words before the kiss, a 1,049-word stop immediately before contact, and a 1,252-word token-cap repetition loop. None realized kiss plus mutually chosen stopping.

Evidence:

- `03_scene_lab/runs/prompt-autoresearch-v9/round-1/candidates.jsonl` — `1a6ebd4a2614990ddbf4baa22d5e685d523158d7a62b75cf1fd127600acd72b1`

Limitations:

- Only one benchmark cell and three fixed seeds; this establishes a baseline distribution, not a general verdict on the base model.

Next test:

Compare the same cell and seeds under raw spicy prose, graph/prose pairs, project bridge, named prior, contrastive, and curated-long prompts.

Record hash: `86bd49f2462987d04e39525da6a9eca4355c621512c345ae851e71c150d23a0d`
