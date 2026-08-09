# Composed paired-only v3 — critical read

Verdict: paired demonstrations improve causal yield, but a one-sentence
manuscript runway does not lock scene continuity for the native base model.

V3 removed the 30K-word prose library and used the 19.5K-token paired-only
prompt. Cold prefill took 178.5 seconds at 109 tokens/second; the warm second
seed evaluated one prompt token and decoded at 7.39 tokens/second. Seed 913019
produced a 505-word mechanical pressure pass on the second draw.

The pass is invalid on close reading. The fixed opening says an alignment
session is already twenty-three minutes past its promised end. The completion
instead opens in an “open pavilion” after Adrian has left, while fellows move
toward kitchens and apartments and Mara's suitcase sits beside the couch. Tea
and the fear of being good-but-not-exceptional occur, but in a new social and
temporal state. The gift-segment request was cancelled during prefill rather
than allowed to continue the wrong story.

The first seed also invents a fifth predictive-model run and a public score
comparison. It remains inside a room but changes the experiment, chronology,
and status situation. Its mention of “outside” as a view through a window also
shows why isolated forbidden-word gates are inferior to positive state
anchoring.

## Scaffold implication

The prompt currently ends with one factual sentence. A base model treats that
as a loose opening invitation and samples a plausible new scene from the much
larger preceding story distribution. Backtranslate the locked state into a
short concrete manuscript runway: who remains, where each body is, what screens
are live, what has not happened, and what material constraint is still active.
This is prose state, not a second instruction block.

Count the runway as part of the 875–1,100-word movement and include it in the
final artifact. Then shorten the generated segment bands by the runway word
count. Preserve paired demonstrations as the realization prior; do not restore
the raw prose mass.
