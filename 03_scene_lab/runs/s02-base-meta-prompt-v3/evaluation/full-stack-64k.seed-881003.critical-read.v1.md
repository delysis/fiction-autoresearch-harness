# Held-out S02 meta-prompt v3 — full stack, seed 881003

Verdict: the two useful prompt priors do not compose in one whole-movement
completion; reject the prose and do not run the 128K arm.

The 62,610-token native-base prompt combined roughly 30,000 words of selected
social-fiction prose with the three event-ledger→finished-manuscript
demonstrations. Model, seed, sampler, target, canonical runway, extraction, and
anti-copy policy were held fixed. The model produced 1,110 raw words and a
complete 1,083-word checkpoint with no exact source reuse, head-hop, or hard
loop. The result is not an interaction win.

## What survived from each prior

- From the causal demonstrations, the passage retains a warm ceramic cup of
  amber tea, telemetry, an access form, and a session that resists ending.
- From the prose library, it gains more dialogue, physical proximity, and some
  locally embodied pressure: Livia's skirt touches Mara's calf; Mara braces her
  back against the table; the cup leaves a dark ring in the oil.
- Several exchanges are compact enough to play as action rather than sermon:
  “You refused the other ways out”; “I didn't say it was yours”; “Because I can
  see your methods. You can't see mine.”

These are component-level gains, not a successful scene.

## Decisive causal and character failures

- Only two of six locked occurrences are present under the deterministic
  screen: tea as care and telemetry access. The access has already happened
  before the passage—Mara “had typed her first name in the overnight access
  form”—so the required flattering gift, hesitation, choice, and recorded
  obligation cannot unfold causally on the page.
- Livia never exposes Mara's fear of being competent but unexceptional. Instead
  Mara announces generalized fear and desire, and Livia replies with a polished
  villain thesis: “You needed to be afraid of something ... I merely noticed
  it.” This destroys her required mixture of genuine skill, care, humor, and
  acquisition.
- Jonah remains a nearly motionless moral lamp. He contributes “She stopped
  the arc” but never performs the socially costly next-sequence act and never
  becomes Mara's romantic counterpressure.
- Erotic energy again migrates to Livia. The skirt-to-calf contact and physical
  crowding sharpen Livia's dominance while Mara and Jonah undergo no change in
  distance, trust, knowledge, or desire.
- The group becomes an implausible coercive chorus: six people laugh, advance
  until two men are within smelling distance, wait repeatedly, and “exhale
  through its nose.” Institutional pressure turns into a literalized hive body.
- The local endpoint is not achieved. Mara accepts no access on the interface;
  Jonah does not make the next sequence ready; the tea becomes warm again
  rather than cooling untouched; and the final sentence says the moment is
  over rather than leaving Mara more durably implicated in continuing work.

## Prose diagnosis

The mechanical cadence screen rises to 3.69 flagged constructions per thousand
words, worse than the raw-prose arm's 0.92. More important than that count is a
new repetition family the proxy misses: “The room waited” or an equivalent
appears again and again until the room becomes an explanatory actor. “Mara
could have” counterfactual branches also substitute narrated options for actual
choice. The passage is less generic than the paired-only outputs, but it is
still scaffold-shaped and over-explicit.

## Experimental interpretation

The ablation is now clear. Paired ledger→manuscript demonstrations strongly
raise event-graph adherence but compress the movement. A large raw-prose
library improves cadence, subtext, embodied contact, and ambiguity but erases
the event graph. Concatenating both into one long prompt does not add those
effects: this seed falls to 2/6 target occurrences and retains neither the raw
arm's clean cadence nor the paired arm's causal order.

Do not spend another long cold prefill on the 128K arm. Move composition into
the scaffold: keep the common prose-plus-paired reference prefix, partition the
event graph into three bounded pre-endpoint submovements, carry manuscript
state forward, and require each submovement's observable causal change before
advancing. This tests whether local contracts can recover control without
discarding the better prose prior.
