# Held-out S02 meta-prompt v3 — short control, seed 881003

Verdict: reject. Boundary handling succeeded; narrative conditioning failed.

The 4,814-token prompt produced 1,268 raw words at a fixed 1,700-token
generation ceiling. The harness preserved that raw tail and selected the last
complete paragraph boundary inside the required checkpoint band, yielding a
complete 1,091-word candidate. This validates scaffold-level length control
without compression, repair prose, or asking the model to count words.

## Decisive literary and continuity failures

- The opening asserts Jonah's private intention—“She knew he was thinking
  that”—instead of keeping his mind inferentially unavailable.
- The passage enacts none of the selected causal atoms. There is no tea offered
  as care, no accurate naming of Mara's fear of being merely competent, no raw
  telemetry access grant, no overnight obligation, no Jonah “next sequence”
  complicity, and no acceptance that narrows Mara's choices.
- It violates the locked endpoint. Mara closes the session, leaves the room,
  walks away, and enters a church scene. The checkpoint had to leave her inside
  Fulcrum and less able to exit.
- It invents a different plot: a speaking optimization model, Celia, a church
  reunion, responsive lamps, and prayer over frozen buns. None follows from the
  target program.
- World status collapses toward technological/supernatural fantasy. The glass
  “ripples,” retains a fingertip mark, and appears to remember patterns; the
  system speaks with autonomous purpose; the closing prayer fills the room with
  literalized light.
- Livia's specific care and acquisitiveness disappear. Jonah is mostly a remote
  signal source. Romantic pressure never becomes reciprocal action.
- The prose contains attractive isolated images, but they are attached to the
  wrong story. “The box appeared in her palm like a blessing” and the responsive
  lighting reinforce the invented mystical register rather than the project’s
  ordinary/extraordinary ambiguity.

## What the scaffold proved

- A closed preparation block followed by a plain manuscript runway avoids the
  blank-output failure caused by an open manuscript tag.
- Stopping on attempted Markdown/XML re-entry prevents the specific dossier
  escape seen in the earlier S03 control.
- Overgenerate-and-select at complete paragraph boundaries solves checkpoint
  word count mechanically. The raw completion remains immutable for audit.
- These transport fixes do not make a 4.8K dossier steer the genuine 31B base
  model. The model still treats the runway as a loose story prior and invents a
  locally probable continuation instead of realizing the supplied event chain.

## Experimental implication

Do not spend another seed on the short prompt yet. The next arm should keep the
same target, seed, sampler, runway, boundary, extraction rule, and anti-copy
guard while adding only the three ledger-to-manuscript demonstrations. That is
the clean test of whether in-context transformation examples improve causal
obedience without instruction-model normalization.
