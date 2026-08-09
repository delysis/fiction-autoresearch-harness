# Native-base candidate 1 scaffold failure

Status: preserved diagnostic; no candidate committed; candidate 2 never started.

The first native-base calibration did not test the intended continuation
hypothesis. Its prompt ended with `## Manuscript\nMara`, while the accepted S01
scene appeared only as a factual state bridge. The whole S02 beat ledger and
story program were visible during sequence 1. When the 622-word draft fell
short, both continuation calls began replaying the serialized control packet;
the compression call then reproduced the original 623-word draft and the
controller failed the 875-word sequence floor.

Durable call results:

- Draft: 622 words, natural stop, generic and prematurely resolves the session.
- Continue 1: 206 words, serialized packet replay.
- Continue 2: 339 words, a mid-packet XML/affordance fragment.
- Compression: 623 words, natural stop, still outside the 875–1,100 range.

The trace is retained as evidence about prompt construction, not evidence that
Gemma 4 31B base cannot write fiction. The corrected experiment starts in
`s02-autoloom-v2` and adds a real S01 prose runway, sequence-local causal
projection, exact-manuscript-tail continuation prompts, and hard packet-leakage
rejection.

Integrity:

- `calls.jsonl` SHA-256:
  `dc8d57b457cf485119dc539dc78758d5555758913b5b9a5c60c33d414f860962`
- Controller error-log SHA-256 at boundary:
  `692a7db1d3d4bad9b38c2bc529b1256706b7e73260c55bd5c350b6407e83bfce`
