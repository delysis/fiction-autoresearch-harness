# Intimacy Craft Distillation v1

## Purpose

This document turns the transferable craft principles in Diana Gabaldon's
*I Give You My Body* into generation, planning, evaluation, editing, and human
appraisal machinery for the Fiction Lab.

It is a conceptual distillation, not a style imitation. The harness stores no
example passages from the book and never asks a model to sound like Gabaldon.

## The governing idea

The most useful correction is simple:

> An intimate scene is an emotional transaction rendered through dialogue,
> expression, action, selective sensation, and consequence.

Physical desire makes the reader attend. It does not, by itself, give the scene
content. The content is what the characters offer, request, conceal, refuse,
misunderstand, recognize, or become able to choose.

For this project, heat should be treated as a product rather than a quota:

`heat ≈ character specificity × emotional exchange × embodied attention × consequence × imaginative space`

If any factor approaches zero, adding more body description is usually
counterproductive.

## S01: the correct intimacy mode

“The Calibration Game” is a **non-sex sex scene with premarital tension**.
Its erotic action is distributed across three relational movements:

1. Fulcrum offers beauty, belonging, and interpretive pressure. Mara offers
   curiosity while withholding surrender.
2. Livia turns wrist contact into a bid for authority and possession. Mara
   answers through attraction, experimental control, and retained freedom.
3. Jonah refuses to perform access to Mara and later recognizes what she did.
   His restraint costs status and becomes more attractive than display.

The scene succeeds when Mara ends both more attracted and more free. If desire
makes her less observant, or if restraint merely stops momentum, the project’s
central erotic-theological claim has failed on the page.

## Scene design card

Every intimate or intimacy-adjacent scene should answer these before prose:

- **Intimacy mode:** consummated, non-consummated contact, non-sex sex scene,
  premarital tension, aftermath, or invisible/offstage intimacy.
- **Opening emotional offer:** what the point-of-view character risks, wants,
  or asks without necessarily saying so.
- **Counteroffer:** what the other person gives, withholds, or misreads.
- **Ending state:** the exact feeling, trust, vulnerability, or freedom that
  has changed.
- **Attraction filter:** what this character notices, in what order, and why
  those signals matter to this body and history.
- **Dialogue-act sequence:** tease, probe, evade, invite, refuse, confess,
  reassure, challenge, recognize, or repair.
- **Body-language counterpoint:** where physical behavior contradicts,
  intensifies, or complicates the words.
- **Sensory triad:** three coherent channels selected for meaning, not
  five-sense coverage.
- **Atmospheric pressure:** how setting, weather, witnesses, clothing, sound,
  privacy, or objects alter behavior.
- **Distance plan:** the one detail that deserves a close-up and what the
  narration should omit or leave to imagination.
- **Physical logic:** enough spatial continuity to understand the action
  without clinical choreography.
- **Relationship delta:** a precise `before -> after`.

## Prompting rules

### Direct generation

The direct prompt names the emotional transaction and intimacy mode, then asks
the model to prove them through dialogue, expression, action, and consequence.
It asks for a coherent sensory triad, not “use all five senses,” and focuses
narrative closeness around the wrist detail whose meaning changes.

### Verbalized Sampling

Plan diversity now varies:

- emotional purpose;
- character-specific attraction;
- dialogue/body-language structure;
- sensory design;
- atmospheric pressure;
- narrative distance;
- relationship outcome.

This prevents “diversity” from collapsing into different props, jokes, or room
layouts around the same generic escalation.

At least two proposed strategies must make Jonah’s restraint the hottest
action. At least two must make public observation or atmosphere carry pressure.

### Actor–Novelist

The Actor must produce the full scene design card before prose. The fast
validator rejects traces missing any craft field. The Novelist must realize
the chosen trace without turning it into explanatory prose or silently
replacing restraint with conventional escalation.

### Editing

The editor protects successful emotional transactions before line polish. It
repairs a mechanical passage by adding emotional action or cutting unnecessary
choreography—not by adding euphemisms. It intensifies scenes through dialogue,
atmosphere, implication, and changed choice before increasing explicitness.

## Evaluation

The 100-point rubric retains the original seven axes and weights so results
remain comparable. Version 2 deepens the anchors rather than smuggling in a new
objective.

The decisive additions are:

- `heat_with_agency` now requires a specific emotional exchange,
  character-specific attention, dialogue/body counterpoint, consequential
  contact, and productive restraint;
- `prose_and_voice` now evaluates sensory selection, atmosphere, narrative
  distance, and freedom from clinical choreography or ornate euphemism;
- `theological_coherence` asks whether chastity enlarges perception, delight,
  agency, and future possibility;
- `instructional_fidelity` asks whether the wrist control is physically
  intelligible and learned through embodied consequence;
- `epistemic_texture` asks whether attraction sharpens rather than overrules
  inquiry.

Model judges report four to six decision-relevant craft diagnostics with exact
passage evidence. Scores without supported passages remain invalid.

## Pairwise selection priorities

When comparing two otherwise competent scenes:

1. Prefer the clearer and more consequential emotional transaction.
2. Prefer character-specific desire over generic heat.
3. Prefer selective sensation and active atmosphere over sensory quantity.
4. Prefer restraint that increases pressure over restraint that ends it.
5. Prefer contact that changes knowledge or relationship over prettier
   description.
6. Canon and agency outrank craft polish when they conflict.

## Defect taxonomy

The new high-value labels are:

- `lust_as_emotion`
- `mechanics_without_emotion`
- `clinical_inventory`
- `ornate_euphemism`
- `disembodied_dialogue`
- `silent_choreography`
- `sensory_checklist`
- `atmospheric_vacuum`
- `static_contact`
- `generic_attraction`
- `restraint_without_tension`
- `distance_monotony`
- `unearned_lyricism`
- `repeated_intimacy_template`
- `logistics_failure`
- `emotion_without_consequence`

These labels should accumulate adjudicated examples. Over time, those examples
become the most valuable few-shot material for both judges and targeted
editors.

## Human appraisal

Blind readers now rate:

- romantic pull;
- specificity of the emotional exchange;
- embodied charge;
- whether restraint intensifies desire;
- suspense, character fascination, trust, prose freshness, clarity, desire to
  continue, and preachiness.

They are also asked:

- what each character wanted from the contact and what the other gave;
- where restraint or omission intensified the scene and where it deflated it;
- what changed;
- what teaching they inferred;
- which passage was hottest;
- which passage felt false or over-explained;
- which line remained memorable.

This distinguishes “I liked it” from the mechanism that produced the response.

## Current 24-scene audit

The deterministic v2 audit shows that all three existing arms already cover
the broad surface requirements: dialogue, multiple senses, atmosphere,
consequential contact, restraint, and forward relationship pressure are
present in every candidate.

That is a coverage result, not a quality verdict. The direct arm contains more
words and slightly more body action; the Actor–Novelist arm has the highest
normalized atmosphere, dialogue, and emotional-marker density; the Verbalized
arm is leanest on those surface measures. Character specificity, emotional
quality, distance control, and physical intelligibility remain deliberately
reserved for evidence-backed editorial and human judgment.

The detailed, candidate-level audit lives in
`04_review_governance/intimacy_craft_audit_v1.json`.

## Future married-intimacy scenes

The same system supports married sex without making “chaste” mean tepid:

- define the emotional purpose of this encounter in the marriage now;
- vary distance, atmosphere, initiative, humor, vulnerability, and aftermath;
- treat familiarity as narrative leverage rather than an excuse to repeat a
  physical template;
- let trust permit greater specificity while keeping sensation selective;
- make the scene change the marriage, plot, or spiritual action;
- use invisible/offstage intimacy when aftermath and reader imagination are
  stronger than explicit narration.

The result should be hotter because character, freedom, history, and meaning
have accumulated—not because the prose performs a longer inventory.
