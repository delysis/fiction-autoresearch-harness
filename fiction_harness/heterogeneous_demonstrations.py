"""Hash-locked heterogeneous ledger-to-prose apprenticeship examples."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .core import sha256_text
from .evaluation import word_count
from .meta_prompting import Demonstration


@dataclass(frozen=True, slots=True)
class HeterogeneousDemoSpec:
    demonstration_id: str
    source_path: str
    source_hash: str
    start_marker: str
    end_marker: str
    excerpt_hash: str
    ledger: str


SPECS = (
    HeterogeneousDemoSpec(
        demonstration_id="austen-confidence-as-leverage",
        source_path=(
            "03_scene_lab/runs/s02-base-meta-prompt-v3/sources/"
            "sense_and_sensibility.chapter-024.txt"
        ),
        source_hash="2a416ba0f9e76bed5d1e5e977b5010a4557b813af647bba73d385dbbf55e901c",
        start_marker="Lucy went on.",
        end_marker="Elinor thought it wisest to make no answer to this,",
        excerpt_hash="e0d47cea20356e4bccf4ee36db813246fc718036f8cc45112c511d4da41b9f5c",
        ledger="""Phase: confidence becomes leverage
1. Given: One woman has disclosed a secret engagement to another.
   Action (confidante, listener): The confidante lists minute behavioral evidence and presents jealousy as proof that she could not be deceived.
   Visible response: The listener outwardly grants the account while privately recognizing that it proves less than claimed.
   What changes: Intimacy becomes a contest over whose interpretation will govern.
2. Given: The engagement is blocked by money and family authority.
   Action (listener, confidante): The listener asks what concrete course exists besides indefinite waiting.
   Visible response: The confidante frames delay as selfless protection of her beloved.
   What changes: A practical question exposes the self-interest concealed inside a virtuous account.
3. Given: The confidante has made self-sacrifice her moral defense.
   Action (listener): The listener adds that the delay also protects the confidante herself.
   Visible response: The confidante looks at her and falls silent.
   What changes: One precise observation punctures the prepared story without producing a confession.
4. Given: The listener belongs to a family with patronage the couple might use.
   Action (confidante, listener): The confidante proposes that the listener secure a position for the man and calls her a party concerned.
   Visible response: The listener explains why her influence is unnecessary or ineffective.
   What changes: Apparent trust becomes an attempt to recruit the listener into material complicity.
5. Given: The listener has declined the practical favor.
   Action (confidante, listener): The confidante threatens to dissolve the engagement and asks the listener to advise it, promising to obey.
   Visible response: The listener refuses the compliment because it assigns her intolerable power over two other people.
   What changes: Refusal preserves the listener's agency and denies the confidante a way to outsource responsibility.
Local stopping state: The confidante insists that neutrality makes the listener's judgment valuable; the listener answers with silence rather than accepting the role.""",
    ),
    HeterogeneousDemoSpec(
        demonstration_id="austen-object-confession",
        source_path=(
            "03_scene_lab/runs/s02-base-meta-prompt-v3/sources/"
            "emma.chapter-040.txt"
        ),
        source_hash="cf22268e70833feb0d7013deb65183477b3e3bf8713a6eaea866f7dbec6a27c3",
        start_marker="A very few days had passed after this adventure,",
        end_marker="“And when,” thought Emma,",
        excerpt_hash="6d070337e15957141f9b2f0aa263ce9875d25472f36af2965743d687a130dc8e",
        ledger="""Phase: an object externalizes a private attachment
1. Given: A young woman wants her trusted friend to witness that an attachment is over.
   Action (visitor, friend): She arrives with a wrapped parcel and asks to make a confession.
   Visible response: The friend expects an important disclosure but cannot guess what the parcel contains.
   What changes: A private emotional claim is placed under observable test.
2. Given: The visitor once preserved trivial remnants associated with the man.
   Action (visitor): She unwraps a small box, names each worthless object, and reconstructs the encounter that made it precious.
   Visible response: The friend remembers her own unnoticed manipulation inside those events and becomes ashamed.
   What changes: Concrete objects reveal both the visitor's attachment and the friend's causal responsibility.
3. Given: The visitor says she has become rational and detached.
   Action (visitor, friend): She burns the relics in the friend's presence despite one object's possible practical use.
   Visible response: Destruction gives the claim of change a bodily, irreversible action.
   What changes: The former attachment loses its material shrine, though its replacement remains unknown.
4. Given: The friend knows the old attachment has ended but wants a new romantic story to begin.
   Action (friend): She privately predicts a particular successor without asking enough questions.
   Visible response: The visitor offers no confirming evidence.
   What changes: Accurate observation of change becomes a potentially false interpretation of its meaning.
Local stopping state: The objects are destroyed; the old attachment has ended; the friend's confident theory about what comes next remains untested.""",
    ),
    HeterogeneousDemoSpec(
        demonstration_id="austen-teasing-to-commitment",
        source_path=(
            "03_scene_lab/runs/s02-base-meta-prompt-v3/sources/"
            "pride_and_prejudice.chapter-058.txt"
        ),
        source_hash="90e36639fd4dd7a8c05aa478dde237cc7032e133e1015b56eeb9739422563233",
        start_marker="Elizabeth’s spirits soon rising to playfulness again,",
        end_marker="“I am more likely to want time than courage, Elizabeth.",
        excerpt_hash="fbdb741f36895a885dac25b90ec335c10eedcacaa62c67c22324370878cf6afd",
        ledger="""Phase: attraction is made discussable through teasing
1. Given: A couple's attachment is now mutually acknowledged.
   Action (woman, man): She asks him to explain when and why he first fell in love.
   Visible response: He cannot name an instant and says he discovered himself already in the middle of it.
   What changes: Desire becomes shared subject matter without becoming mechanically explicable.
2. Given: Their courtship included disagreement and wounded pride.
   Action (woman, man): She teasingly proposes that her incivility and independence attracted him; he answers by naming the liveliness of her mind.
   Visible response: Each converts a former source of conflict into a valued trait without denying the conflict.
   What changes: Retrospective interpretation increases intimacy while preserving friction and humor.
3. Given: Both delayed speaking plainly.
   Action (woman, man): She presses him about his reserve; he says her gravity gave no encouragement and that stronger feeling made speech harder.
   Visible response: She admits her own embarrassment and accepts the answer while continuing to tease.
   What changes: Mutual restraint is reclassified from indifference to costly feeling.
4. Given: A hostile relative tried to separate them.
   Action (man): He explains that the interference removed his doubts and caused him to seek a definite answer.
   Visible response: Opposition becomes information and prompts chosen action rather than melodramatic destiny.
   What changes: The couple can identify how uncertainty became commitment.
5. Given: Their private understanding creates a public obligation.
   Action (woman, man): She asks whether he will tell the hostile relative; he asks for paper and commits to write immediately.
   Visible response: Playful retrospective talk produces a concrete future act.
   What changes: Romantic recognition alters what he is willing to do in the social world.
Local stopping state: Attraction has been explored through reciprocal teasing, and the man begins the socially costly letter their commitment requires.""",
    ),
)


def _extract(source: str, spec: HeterogeneousDemoSpec) -> str:
    try:
        start = source.index(spec.start_marker)
        marker_end = source.index(spec.end_marker, start) + len(spec.end_marker)
    except ValueError as exc:
        raise ValueError(
            f"demonstration boundary changed: {spec.demonstration_id}"
        ) from exc
    paragraph_end = source.find("\n\n", marker_end)
    end = paragraph_end if paragraph_end >= 0 else len(source)
    return source[start:end].strip()


def load_heterogeneous_demonstrations(
    project_root: str | Path,
) -> tuple[Demonstration, ...]:
    root = Path(project_root)
    values: list[Demonstration] = []
    for spec in SPECS:
        path = root / spec.source_path
        source = path.read_text(encoding="utf-8")
        if sha256_text(source) != spec.source_hash:
            raise ValueError(f"source changed: {spec.demonstration_id}")
        excerpt = _extract(source, spec)
        if sha256_text(excerpt) != spec.excerpt_hash:
            raise ValueError(f"excerpt changed: {spec.demonstration_id}")
        values.append(
            Demonstration.create(
                spec.demonstration_id,
                spec.ledger,
                excerpt,
                {
                    "source_path": spec.source_path,
                    "source_hash": spec.source_hash,
                    "excerpt_hash": spec.excerpt_hash,
                    "excerpt_words": word_count(excerpt),
                    "provenance": "public-domain author scene with human-authored content-neutral ledger",
                },
            )
        )
    return tuple(values)


def heterogeneous_demonstration_manifest(project_root: str | Path) -> dict[str, Any]:
    return {
        "record_type": "HeterogeneousDemonstrationManifest",
        "version": "heterogeneous-paired-demos.v1",
        "demonstrations": [asdict(item) for item in load_heterogeneous_demonstrations(project_root)],
    }
