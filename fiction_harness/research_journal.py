"""Append-only, evidence-linked research journal for fiction experiments."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence

from .core import atomic_write_text, hash_json


JOURNAL_SCHEMA_VERSION = "fiction-research-note.v1"
NOTE_STATUSES = frozenset({"observation", "inference", "decision"})
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class EvidenceArtifact:
    artifact: str
    sha256: str

    def __post_init__(self) -> None:
        if not self.artifact.strip():
            raise ValueError("evidence artifact path cannot be empty")
        if not SHA256_RE.fullmatch(self.sha256):
            raise ValueError("evidence hash must be a lowercase SHA-256 digest")

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ResearchNote:
    note_id: str
    created_at: str
    status: str
    claim: str
    evidence: tuple[EvidenceArtifact, ...]
    limitations: tuple[str, ...]
    next_test: str
    arm: str | None = None
    seed: int | None = None

    def __post_init__(self) -> None:
        if not re.fullmatch(r"rn-[a-z0-9][a-z0-9._-]{2,79}", self.note_id):
            raise ValueError("note_id must match rn-[a-z0-9][a-z0-9._-]{2,79}")
        if self.status not in NOTE_STATUSES:
            raise ValueError(
                "status must be one of: " + ", ".join(sorted(NOTE_STATUSES))
            )
        if not self.claim.strip():
            raise ValueError("claim cannot be empty")
        if not self.evidence:
            raise ValueError("at least one evidence artifact is required")
        if not self.next_test.strip():
            raise ValueError("next_test cannot be empty")
        if self.arm is not None and not self.arm.strip():
            raise ValueError("arm cannot be blank")

    def payload(self) -> dict[str, Any]:
        return {
            "record_type": "ResearchNote",
            "schema_version": JOURNAL_SCHEMA_VERSION,
            "note_id": self.note_id,
            "created_at": self.created_at,
            "status": self.status,
            "claim": self.claim.strip(),
            "evidence": [item.to_dict() for item in self.evidence],
            "arm": self.arm,
            "seed": self.seed,
            "limitations": [item.strip() for item in self.limitations if item.strip()],
            "next_test": self.next_test.strip(),
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self.payload()
        payload["note_hash"] = hash_json(payload)
        return payload

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ResearchNote":
        if value.get("record_type") != "ResearchNote":
            raise ValueError("journal record_type must be ResearchNote")
        if value.get("schema_version") != JOURNAL_SCHEMA_VERSION:
            raise ValueError("unsupported research-note schema version")
        evidence = tuple(
            EvidenceArtifact(
                artifact=str(item["artifact"]), sha256=str(item["sha256"])
            )
            for item in value.get("evidence", ())
        )
        note = cls(
            note_id=str(value["note_id"]),
            created_at=str(value["created_at"]),
            status=str(value["status"]),
            claim=str(value["claim"]),
            evidence=evidence,
            arm=str(value["arm"]) if value.get("arm") is not None else None,
            seed=int(value["seed"]) if value.get("seed") is not None else None,
            limitations=tuple(str(item) for item in value.get("limitations", ())),
            next_test=str(value["next_test"]),
        )
        expected = note.to_dict()["note_hash"]
        if value.get("note_hash") != expected:
            raise ValueError(f"research note hash mismatch: {note.note_id}")
        return note


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def evidence_from_paths(
    paths: Sequence[str | Path], *, project_root: str | Path | None = None
) -> tuple[EvidenceArtifact, ...]:
    root = Path(project_root).resolve() if project_root is not None else None
    records: list[EvidenceArtifact] = []
    for supplied in paths:
        path = Path(supplied).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"evidence artifact does not exist: {path}")
        if root is not None:
            try:
                stored = str(path.relative_to(root))
            except ValueError:
                stored = str(path)
        else:
            stored = str(path)
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        records.append(EvidenceArtifact(artifact=stored, sha256=digest.hexdigest()))
    return tuple(records)


def _parse_line(line: str, *, line_number: int) -> ResearchNote:
    try:
        value = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid journal JSON on line {line_number}") from exc
    if not isinstance(value, Mapping):
        raise ValueError(f"journal line {line_number} must be a JSON object")
    return ResearchNote.from_dict(value)


def read_journal(path: str | Path) -> tuple[ResearchNote, ...]:
    journal = Path(path)
    if not journal.exists():
        return ()
    notes: list[ResearchNote] = []
    seen: set[str] = set()
    for line_number, line in enumerate(
        journal.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        note = _parse_line(line, line_number=line_number)
        if note.note_id in seen:
            raise ValueError(f"duplicate research note id: {note.note_id}")
        seen.add(note.note_id)
        notes.append(note)
    return tuple(notes)


def append_note(path: str | Path, note: ResearchNote) -> dict[str, Any]:
    """Append one hash-validated record while holding an exclusive file lock."""

    journal = Path(path)
    journal.parent.mkdir(parents=True, exist_ok=True)
    record = note.to_dict()
    serialized = json.dumps(
        record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    with journal.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        existing = [
            _parse_line(line, line_number=index)
            for index, line in enumerate(handle.read().splitlines(), 1)
            if line.strip()
        ]
        if any(item.note_id == note.note_id for item in existing):
            raise ValueError(f"duplicate research note id: {note.note_id}")
        handle.seek(0, 2)
        handle.write(serialized + "\n")
        handle.flush()
        __import__("os").fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return record


def _md(text: str) -> str:
    return text.replace("\r", " ").replace("\n", " ").strip()


def render_markdown(notes: Iterable[ResearchNote]) -> str:
    values = tuple(notes)
    lines = [
        "# Fiction Harness Research Journal",
        "",
        "Append-only observations, inferences, and decisions. Every claim links "
        "to hash-addressed evidence; later notes supersede rather than rewrite "
        "earlier ones.",
        "",
        f"Entries: {len(values)}",
        "",
    ]
    for note in values:
        coordinate = ""
        if note.arm is not None:
            coordinate = f" · arm `{note.arm}`"
        if note.seed is not None:
            coordinate += f" · seed `{note.seed}`"
        lines.extend(
            (
                f"## {note.note_id}",
                "",
                f"**{note.status.title()}** · `{note.created_at}`{coordinate}",
                "",
                _md(note.claim),
                "",
                "Evidence:",
                "",
            )
        )
        for item in note.evidence:
            lines.append(f"- `{item.artifact}` — `{item.sha256}`")
        lines.extend(("", "Limitations:", ""))
        if note.limitations:
            lines.extend(f"- {_md(item)}" for item in note.limitations)
        else:
            lines.append("- None recorded.")
        lines.extend(
            (
                "",
                "Next test:",
                "",
                _md(note.next_test),
                "",
                f"Record hash: `{note.to_dict()['note_hash']}`",
                "",
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def render_journal(journal: str | Path, output: str | Path) -> str:
    rendered = render_markdown(read_journal(journal))
    atomic_write_text(Path(output), rendered)
    return rendered
