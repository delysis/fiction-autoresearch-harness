# Shared 31B-base endpoint: corrected batching findings

## Executive result

Continuous batching works, but “four slots” is not by itself a throughput win
on this M4 Max. The profitable regime is **small per-slot context plus already
warm, byte-identical prefixes**. Four cold long prompts can lose badly to warm
serial sampling because they repeat prefill work and enlarge active KV state.

The production endpoint is now one shared four-slot server at 32,768 tokens per
slot, with cross-process admission capped at 30,720 declared tokens per request
and 122,880 tokens in aggregate. Controllers no longer pass exclusive ownership
back and forth for ordinary calls.

## What the measurements say

### Short warm-prefix benchmark

On the earlier 4.8K-token prompt, four 128-token draws with a warm 4,814-token
prefix completed at 15.21 aggregate completion tokens/second versus 10.17 for
the four serial draws, a 1.50x wall-clock gain. This establishes that Metal and
llama.cpp can exploit batching when prefill is almost entirely reused.

### Cold production waves at 32K per slot

V7 submitted four identical 5,516-token prompts cold and produced 2,460
completion tokens in about 678.6 seconds of batch wall time: 3.63 completion
tokens/second including prefill. V8 submitted four identical 6,078-token
prompts cold and produced 2,864 completion tokens in about 703.7 seconds: 4.07
completion tokens/second including prefill.

The four calls did not share one prefix prefill. V7 recorded zero cache reuse
for every slot; V8 reused only 28 tokens on three slots. Per-request decode
rates varied from roughly 1.0 to 2.0 tokens/second while requests overlapped.
Brief higher aggregate decode bursts did not overcome four redundant prefills.

### Oversized slot geometry

Launching four slots with `--ctx-size 131072` gave each slot 131,072 tokens,
reserving roughly a 524K-token KV geometry rather than treating 131K as a shared
aggregate budget. The process resident set was about 92.9 million KiB and the
machine approached its swap limit. Aggregate generation slowed below the
useful serial regime. Those four requests were cancelled and retained only as
censored runtime evidence.

After relaunching at 32,768 tokens per slot, the idle 31B server resident set is
about 24.6 million KiB, roughly one quarter of the oversized configuration, and
four-way execution is stable.

## Scheduling policy

1. Keep one shared endpoint; do not serialize work by task ownership.
2. Admit at most four live calls, each no larger than 30,720 declared prompt +
   completion tokens, with 122,880 aggregate declared tokens.
3. Prefer sequential or staged sampling when one prefix is already warm. Cache
   affinity can dominate nominal batching on a memory-bandwidth-limited dense
   model.
4. Batch genuinely concurrent work when prompts are short or already cached,
   and compare wall-clock aggregate throughput rather than summing llama.cpp's
   per-slot rates.
5. Do not revive the 64K/128K prose arms on this four-slot service. A future
   long-context arm needs a separately sized endpoint or one slot.
6. Preserve prompt family, cache state, slot geometry, and prefill/decode timing
   in every benchmark. “Tokens per second” without those fields is not portable.

## Next runtime experiment

Benchmark one production-sized prompt under three controlled cache conditions:
warm serial, warm four-way, and cold four-way, all on the current 32K service.
Use 750-token completions and repeated seeds. This will locate the actual
batching crossover without confounding prompt design with server geometry.
