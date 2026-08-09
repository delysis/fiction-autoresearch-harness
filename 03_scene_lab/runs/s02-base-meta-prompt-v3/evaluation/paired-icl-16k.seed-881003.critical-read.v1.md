# Held-out S02 meta-prompt v3 — paired ICL, seed 881003

Verdict: promising underlength failure; replicate this arm.

The 19,748-token prompt added three event-ledger→finished-manuscript pairs to
the otherwise fixed target, seed, sampler, canonical runway, boundary, and
anti-copy policy. The raw base model produced a complete 534-word movement and
stopped before the 875-word checkpoint minimum, so no candidate was committed.

## Material improvement over the short control

The short control enacted 0/6 target occurrences and left the scene for an
invented church plot. The paired arm enacts all six occurrences, in causal order:

1. Livia slides a ceramic carafe to depleted Mara; Mara drinks the tea.
2. Livia accurately identifies Mara's desire for the data to prove she is
   exceptional and belongs.
3. Livia offers overnight access, turning recognition into work and obligation.
4. Jonah says, “The next sequence is ready,” participating rather than rescuing.
5. Mara accepts the access on the tablet.
6. Livia turns back to the monitor while the tea cools and the session continues.

This is the cleanest evidence so far that base-model steering improves when the
prompt demonstrates the transformation from sparse causal ledger to manuscript,
rather than merely stating a larger contract or providing abstract craft advice.

## Why it is not yet good fiction

- It contradicts the fixed runway immediately: “Adrian had left forty minutes
  before the promised end” does not continue a session already twenty-three
  minutes past its promised end.
- It is roughly half the requested development. Each occurrence follows the
  prior one almost as soon as it becomes legible, leaving no room for status
  pressure to accumulate or for Mara's plausible coping policy to backfire.
- Several lines are syntactically or semantically thin: “Mara was not”; “The
  control was already decided”; “You’re worried about what the lie might prove.”
- The vulnerability becomes too explicit too quickly. “I want the data to be
  dense enough to prove I belong” states the interior conclusion rather than
  letting Livia's accuracy and Mara's deflection expose it through action.
- Jonah is present but barely dramatized. His water, slowed drinking, and mutual
  noticing are promising, yet his complicity costs him nothing visible.
- Romantic heat is minimal. Livia receives one charged eyelash image, while the
  Mara–Jonah dyad never changes distance, touch, trust, or desire.
- The final line paraphrases the atom packet closely. It is not an exact source
  copy, but the realization remains scaffold-shaped rather than fully owned.

## Next decision

Run at least one different paired-ICL seed before changing its prompt. The arm
has crossed the causal-adherence threshold on its first draw; the open question
is whether its compression and flatness are seed-level variance or a stable
property of using three alternate S01 demonstrations. Continue the raw-prose and
combined arms on the same first seed as planned, but do not interpret more tokens
as an automatic advance unless they preserve this 6/6 causal control and improve
dramatic dwell, character specificity, and heat.
