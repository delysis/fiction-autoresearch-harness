# Independent cold read — S02 base meta-prompt v3

## Verdict formed before opening the accepted S02 holdout

- **Short-control 4k: reject outright. Do not continue, compress, or repair.**
- **Paired-ICL 16k: failed as a deliverable, succeeded as a prior signal. Replicate it in a small controlled batch.**

The short-control sample occasionally produces an eerie sentence, but it ignores the requested causal scene. The 534-word paired sample enacts nearly the whole trap with far better economy and control. It is not itself an appraisal candidate, and one sample is not evidence that the arm reliably works.

## Comparison

| Axis | Short-control 4k | Paired-ICL raw, 534 words |
|---|---|---|
| Causal adherence | **Failure.** It performs none of the six target atoms, closes the session, sends Mara away, and previews the walk home—the exact forbidden future. The church/Celia/frozen-bun excursion is a different chapter. | **Strong skeleton.** Tea is accepted; Livia accurately finds the status wound; access is offered; Jonah prepares the next sequence; Mara accepts; Livia returns to the monitor; the tea cools while work continues. The professional gift becoming obligation is visible, though surveillance and deadline costs are under-specified. |
| Character truth | First sentence asserts Jonah's thoughts through Mara, then Jonah becomes a remote interface. Livia is an ominous abstraction. Mara loses her technical specificity and behaves as a dream-protagonist pulled by symbols. | Mara's dry defense and her admission that she wants proof of belonging are credible, though “belong” softens the sharper fear of being merely competent. Livia's pre-emptive care and refusal to celebrate acceptance are good acquisitive-care behavior; “As many times as you ask” is too therapeutically generous. Jonah's complicity is shown through timing rather than moral commentary. |
| Heat | Almost none. Assertions about Livia's dress and remembered fingers do not alter a live choice. | Low but functional. Livia's attention and Jonah's reciprocal noticing put pressure on Mara's choice, but the scene has more status intimacy than romantic charge. This is sufficient for a sequence-one fragment, not for a whole S02. |
| Prose | Some attractive uncanny surfaces—responsive-looking lamps, remembered glass—but the prose becomes portentous, dislocated, and causally arbitrary. The length stop leaves it stranded after 1,091 candidate words. | Much cleaner and more dramatic. Concrete objects carry pressure: warm handle, pre-poured tea, blinking light, shared tablet. Weak lines remain: “Mara was not” is mannered; “noticed him notice that she noticed” is cute machinery; the reflected-smile sentence is unclear. |
| Continuity | Hard break. Fulcrum's residential setting turns into a walk home; the completed exit violates the stopping state; Celia and the church scene arrive without support; new “model” and responsive architecture displace the established experiment. | Broadly continuous with S01. The supplied four-night runway, ongoing late session, raw-access bargain, and Jonah at the console all fit. Adrian leaving before the promised end is plausible but inert. No new canon contradiction is introduced. |

## Holdout comparison

After locking the verdict above, I read the accepted S02. It confirms rather than changes the ranking.

The accepted scene shows what the paired fragment has found and what it still lacks. Both understand the core causal mechanism: care makes an accurate status wound easier to exploit; privileged data access then turns that wound into labor and continued exposure; Jonah participates instead of rescuing Mara. The accepted S02 makes every link costlier and more legible through the expiring permission window, review deadline, sponsor liability, countdown, observer annotations, and Jonah's operator role. Its Livia is simultaneously tired, funny, perceptive, generous, and predatory. Its Mara wants method, distinction, Livia's regard, and Jonah at once. The paired sample has the same load-bearing beams but not that density of motive or consequence.

The accepted prose also has a much higher dramatic floor. It lets objects and interfaces specify the trap, keeps jokes character-specific, and turns attraction into contested information. The paired fragment is promising chiefly because it does **not** imitate the holdout's language while independently recovering its causal architecture.

## Replication decision

**Yes: the 534-word paired result warrants replication, not promotion.** Run a small multi-seed batch before spending on the larger context arms.

Recommended acceptance test:

1. Generate at least four independent paired-ICL seeds with identical prompts and sampling settings.
2. Preserve natural endings. Do not automatically length-repair a 500–850-word result if all six events form a complete causal sequence; evaluate scene density separately from plot completion.
3. Require the professional favor to acquire at least two concrete costs—deadline, surveillance, record ownership, status exposure, or continued labor—not merely “overnight access.”
4. Require Livia's accurate perception and overclaim to remain distinct, Jonah's complicity to be an action, and Mara's acceptance to narrow a visibly available alternative.
5. Reject any sample that leaves the room, resolves the session, invents a future/church sequence, or substitutes symbolic uncanniness for the requested event chain.

If only one of five paired samples clears those tests, treat this result as a lucky draw. If two or more do, paired ICL has earned a full-scene trial. The short-control arm has not.
