"""Blind pairwise reader packets and deterministic human-feedback aggregation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import re
from statistics import median
from typing import Any, Mapping, Sequence

from .core import hash_json, sha256_text, write_json


FEEDBACK_SCHEMA_VERSION = "human-feedback.v1"
PAIRWISE_RATINGS = (
    ("romantic_pull", "Romantic pull"),
    ("heat", "Erotic heat"),
    ("character_fascination", "Character fascination"),
    ("trust", "Trust in the story"),
    ("prose_freshness", "Prose freshness"),
    ("desire_to_continue", "Desire to continue"),
    ("preachiness", "Preachiness"),
)
PAIRWISE_FREE_RESPONSES = (
    ("hottest", "Quote the best or hottest passage."),
    ("false", "Where did interest drop, or the prose feel false or over-explained?"),
    ("next", "What do you most want to happen next?"),
)
ALL_LABELS = ("A", "B", "C")
_REVIEWER_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,63}$")


@dataclass(frozen=True, slots=True)
class HumanFeedbackBrief:
    package_id: str
    source_kind: str
    response_ids: tuple[str, ...]
    coverage: Mapping[str, int]
    pairwise: Mapping[str, Any]
    rating_medians: Mapping[str, Mapping[str, float]]
    winner_label: str
    strengths: Mapping[str, tuple[str, ...]]
    defects: Mapping[str, tuple[str, ...]]
    desired_next: Mapping[str, tuple[str, ...]]
    fail_fast: bool
    created_at: str
    version: str = FEEDBACK_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.source_kind not in {"human", "bootstrap-codex"}:
            raise ValueError("source_kind must be human or bootstrap-codex")
        if not self.package_id:
            raise ValueError("package_id is required")
        if self.winner_label not in ALL_LABELS:
            raise ValueError("winner_label must be A, B, or C")
        if not self.response_ids:
            raise ValueError("at least one response or review is required")

    @property
    def feedback_brief_hash(self) -> str:
        return hash_json(asdict(self))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["record_type"] = "HumanFeedbackBrief"
        payload["feedback_brief_hash"] = self.feedback_brief_hash
        return payload

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "HumanFeedbackBrief":
        payload = dict(raw)
        payload.pop("record_type", None)
        expected_hash = str(payload.pop("feedback_brief_hash", ""))
        for key in ("response_ids",):
            payload[key] = tuple(payload.get(key, ()))
        for key in ("strengths", "defects", "desired_next"):
            payload[key] = {
                str(label): tuple(str(item) for item in values)
                for label, values in dict(payload.get(key, {})).items()
            }
        brief = cls(**payload)
        if expected_hash and expected_hash != brief.feedback_brief_hash:
            raise ValueError("HumanFeedbackBrief hash mismatch")
        return brief


def load_feedback_brief(path: str | Path) -> HumanFeedbackBrief:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise TypeError("feedback brief must be a JSON object")
    return HumanFeedbackBrief.from_dict(raw)


def _finalist_records(
    finalists: Sequence[Mapping[str, Any]],
    reveal_key: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    by_id = {
        str(item.get("candidate_id", "")): dict(item)
        for item in finalists
    }
    labels = reveal_key.get("labels")
    if not isinstance(labels, Mapping) or set(labels) != set(ALL_LABELS):
        raise ValueError("reveal key must contain exactly A, B, and C")
    output: dict[str, dict[str, Any]] = {}
    for label in ALL_LABELS:
        identity = labels[label]
        if not isinstance(identity, Mapping):
            raise TypeError(f"reveal label {label} must be an object")
        candidate_id = str(identity.get("candidate_id", ""))
        record = by_id.get(candidate_id)
        if record is None:
            raise ValueError(f"reveal key candidate is missing: {candidate_id}")
        text = str(record.get("text", ""))
        expected = str(identity.get("text_sha256", ""))
        actual = sha256_text(text)
        if expected and expected != actual:
            raise ValueError(f"finalist text hash mismatch for label {label}")
        output[label] = {
            "text": text,
            "word_count": len(text.split()),
            "candidate_id": candidate_id,
            "pipeline": str(identity.get("pipeline", "")),
            "model_role": str(identity.get("model_role", "")),
            "text_sha256": actual,
        }
    return output


def _prose_html(text: str) -> str:
    paragraphs = [
        paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()
    ]
    return "\n".join(
        f"<p>{escape(paragraph).replace(chr(10), '<br>')}</p>"
        for paragraph in paragraphs
    )


def _rating_rows(label: str) -> str:
    rows: list[str] = []
    for identifier, title in PAIRWISE_RATINGS:
        choices = "".join(
            (
                f'<label><input type="radio" name="{label}_{identifier}" '
                f'value="{value}" required> {value}</label>'
            )
            for value in range(1, 8)
        )
        rows.append(
            f'<div class="rating"><span>{escape(title)}</span>'
            f'<div class="scale">{choices}</div></div>'
        )
    return "\n".join(rows)


def _response_rows(label: str) -> str:
    return "\n".join(
        (
            f'<label class="prompt">{escape(title)}'
            f'<textarea name="{label}_{identifier}" rows="3"></textarea></label>'
        )
        for identifier, title in PAIRWISE_FREE_RESPONSES
    )


def _pair_fields(labels: Sequence[str]) -> str:
    fields: list[str] = []
    for left_index, left in enumerate(labels):
        for right in labels[left_index + 1 :]:
            fields.append(
                f'<fieldset><legend>{left} versus {right}</legend>'
                f'<label><input type="radio" name="pair_{left}_{right}" '
                f'value="{left}" required> {left}</label>'
                f'<label><input type="radio" name="pair_{left}_{right}" '
                f'value="{right}" required> {right}</label>'
                f'<label><input type="radio" name="pair_{left}_{right}" '
                f'value="tie" required> Tie</label></fieldset>'
            )
    return "\n".join(fields)


def _feedback_html(
    *,
    label_map: Mapping[str, Mapping[str, Any]],
    labels: Sequence[str],
    package_id: str,
    packet_id: str,
    title: str,
) -> str:
    articles = "\n".join(
        (
            f'<article id="finalist-{label}"><header><h2>Finalist {label}</h2>'
            f'<span>{int(label_map[label]["word_count"]):,} words</span></header>'
            f'<div class="prose">{_prose_html(str(label_map[label]["text"]))}</div>'
            f'<section><h3>Quick ratings</h3>{_rating_rows(label)}</section>'
            f'<section><h3>Reader notes</h3>{_response_rows(label)}</section>'
            "</article>"
        )
        for label in labels
    )
    nav = "".join(
        f'<a href="#finalist-{label}">{label}</a>' for label in labels
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} — Blind Reader Packet</title>
  <style>
    :root {{ --ink:#211d1b; --paper:#fbf7ef; --accent:#7b2945; --line:#d7cbb9; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:#ece4d8; font-family:Georgia,serif; line-height:1.58; }}
    nav {{ position:sticky; top:0; z-index:3; display:flex; gap:1rem; align-items:center; padding:.7rem 5vw; background:#211d1bee; color:white; }}
    nav a {{ color:#f2d8a8; font-weight:bold; text-decoration:none; }}
    nav .spacer {{ flex:1; }}
    main {{ width:min(940px,94vw); margin:2rem auto 6rem; }}
    .masthead, article, .choice {{ background:var(--paper); padding:clamp(1.2rem,4vw,3rem); margin:0 0 2rem; box-shadow:0 8px 30px #33291d1c; }}
    .masthead {{ border-top:6px solid var(--accent); }}
    h1,h2 {{ font-weight:normal; color:var(--accent); }}
    article header {{ display:flex; justify-content:space-between; align-items:baseline; border-bottom:1px solid var(--line); }}
    .prose {{ font-size:1.08rem; }}
    .rating {{ display:grid; grid-template-columns:minmax(150px,1fr) 2fr; gap:1rem; padding:.55rem 0; border-bottom:1px dotted var(--line); font-family:system-ui,sans-serif; }}
    .scale {{ display:flex; flex-wrap:wrap; gap:.55rem; }}
    .prompt {{ display:block; margin:1.1rem 0; font:600 1rem system-ui,sans-serif; }}
    textarea,input[type=text] {{ display:block; width:100%; margin-top:.4rem; padding:.7rem; border:1px solid var(--line); background:white; font:1rem Georgia,serif; }}
    fieldset {{ margin:1rem 0; border:1px solid var(--line); font-family:system-ui,sans-serif; }}
    fieldset label {{ margin-right:1.4rem; }}
    button {{ border:0; border-radius:4px; padding:.6rem .9rem; background:var(--accent); color:white; cursor:pointer; }}
    button.secondary {{ background:transparent; color:#f2d8a8; border:1px solid #f2d8a8; }}
    .status {{ font:.85rem system-ui,sans-serif; }}
    @media(max-width:650px) {{ .rating {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <nav>{nav}<span class="spacer"></span><span id="status" class="status">Responses save locally</span><button type="button" class="secondary" id="clear">Clear</button><button type="button" id="export">Export</button></nav>
  <main>
    <section class="masthead">
      <h1>{escape(title)}</h1>
      <p>Read {len(labels)} blinded finalists. Rate what is on the page, then choose which one you would rather continue reading. A higher preachiness score means more preachy, not better.</p>
      <label class="prompt">Reviewer code
        <input type="text" name="reviewer_code_display" id="reviewer-code" required pattern="[A-Za-z0-9][A-Za-z0-9_.-]{{1,63}}" placeholder="Choose a short private code">
      </label>
    </section>
    <form id="feedback" autocomplete="off">
      {articles}
      <section class="choice">
        <h2>Choose</h2>
        {_pair_fields(labels)}
        <label class="prompt">Anything the questions missed?
          <textarea name="overall_notes" rows="4"></textarea>
        </label>
      </section>
    </form>
  </main>
  <script>
  (() => {{
    const packageId = {json.dumps(package_id)};
    const packetId = {json.dumps(packet_id)};
    const labels = {json.dumps(list(labels))};
    const form = document.getElementById("feedback");
    const reviewer = document.getElementById("reviewer-code");
    const status = document.getElementById("status");
    const key = "fiction-feedback:" + packageId + ":" + packetId;
    function snapshot() {{
      const result = {{schema_version:{json.dumps(FEEDBACK_SCHEMA_VERSION)}, package_id:packageId, packet_id:packetId, reviewer_code:reviewer.value.trim(), labels:labels, saved_at:new Date().toISOString(), responses:{{}}}};
      new FormData(form).forEach((value,name) => result.responses[name]=value);
      return result;
    }}
    function save() {{ localStorage.setItem(key, JSON.stringify(snapshot())); status.textContent="Saved "+new Date().toLocaleTimeString(); }}
    function restore() {{
      const raw=localStorage.getItem(key); if(!raw) return;
      const saved=JSON.parse(raw); reviewer.value=saved.reviewer_code||"";
      Object.entries(saved.responses||{{}}).forEach(([name,value]) => {{
        const fields=form.elements[name]; if(!fields) return;
        if(fields.length && fields[0] && fields[0].type==="radio") [...fields].forEach(field => field.checked=field.value===value);
        else fields.value=value;
      }});
    }}
    form.addEventListener("input",save); reviewer.addEventListener("input",save);
    document.getElementById("clear").addEventListener("click",() => {{ form.reset(); reviewer.value=""; localStorage.removeItem(key); status.textContent="Cleared"; }});
    document.getElementById("export").addEventListener("click",() => {{
      if(!reviewer.reportValidity() || !form.reportValidity()) return;
      const data=snapshot(); const blob=new Blob([JSON.stringify(data,null,2)],{{type:"application/json"}});
      const link=document.createElement("a"); link.href=URL.createObjectURL(blob);
      link.download="fiction-feedback-"+packetId+"-"+data.reviewer_code+".json"; link.click();
      status.textContent="Responses exported"; setTimeout(() => URL.revokeObjectURL(link.href),1000);
    }});
    restore();
  }})();
  </script>
</body>
</html>
"""


def _feedback_markdown(
    *,
    label_map: Mapping[str, Mapping[str, Any]],
    labels: Sequence[str],
    package_id: str,
    packet_id: str,
    title: str,
) -> str:
    chunks = [
        f"# {title} — Blind Reader Packet",
        "",
        f"Package `{package_id}` · packet `{packet_id}`",
        "",
        "Reviewer code: ___",
    ]
    for label in labels:
        chunks.extend(["", f"## Finalist {label}", "", str(label_map[label]["text"])])
        chunks.extend(["", "### Ratings"])
        chunks.extend(f"- {title}: ___ / 7" for _, title in PAIRWISE_RATINGS)
        chunks.extend(["", "### Notes"])
        chunks.extend(f"- {title}  \n  " for _, title in PAIRWISE_FREE_RESPONSES)
    chunks.extend(["", "## Pairwise choice"])
    for left_index, left in enumerate(labels):
        for right in labels[left_index + 1 :]:
            chunks.append(f"- {left} versus {right}: ___")
    return "\n".join(chunks) + "\n"


def build_pairwise_feedback_packets(
    *,
    finalists: Sequence[Mapping[str, Any]],
    reveal_key_path: str | Path,
    out_dir: str | Path,
    title: str = "The Calibration Game",
) -> dict[str, Any]:
    reveal_key = json.loads(Path(reveal_key_path).read_text(encoding="utf-8"))
    if not isinstance(reveal_key, Mapping):
        raise TypeError("reveal key must be a JSON object")
    package_id = str(reveal_key.get("package_id", ""))
    if not package_id:
        raise ValueError("reveal key has no package_id")
    label_map = _finalist_records(finalists, reveal_key)
    output = Path(out_dir)
    reader = output / "reader"
    reader.mkdir(parents=True, exist_ok=True)
    packets = (
        ("all-three", ALL_LABELS),
        ("pair-AB", ("A", "B")),
        ("pair-AC", ("A", "C")),
        ("pair-BC", ("B", "C")),
    )
    public_files: list[Path] = []
    packet_records: list[dict[str, Any]] = []
    for packet_id, labels in packets:
        html_path = reader / f"{packet_id}.html"
        markdown_path = reader / f"{packet_id}.md"
        html_path.write_text(
            _feedback_html(
                label_map=label_map,
                labels=labels,
                package_id=package_id,
                packet_id=packet_id,
                title=title,
            ),
            encoding="utf-8",
        )
        markdown_path.write_text(
            _feedback_markdown(
                label_map=label_map,
                labels=labels,
                package_id=package_id,
                packet_id=packet_id,
                title=title,
            ),
            encoding="utf-8",
        )
        public_files.extend((html_path, markdown_path))
        packet_records.append(
            {
                "packet_id": packet_id,
                "labels": list(labels),
                "html": html_path.relative_to(output).as_posix(),
                "markdown": markdown_path.relative_to(output).as_posix(),
            }
        )
    forbidden = {
        str(entry[key])
        for entry in label_map.values()
        for key in ("candidate_id", "pipeline", "model_role")
        if str(entry.get(key, "")).strip()
        and str(entry[key]).casefold() not in {"direct", "actor", "verbalized"}
    }
    leaks = [
        {"file": str(path), "token": token}
        for path in public_files
        for token in forbidden
        if token in path.read_text(encoding="utf-8")
    ]
    if leaks:
        raise ValueError(f"blind feedback packet leaked identity: {leaks}")
    manifest = {
        "record_type": "HumanFeedbackPacketManifest",
        "schema_version": FEEDBACK_SCHEMA_VERSION,
        "package_id": package_id,
        "packets": packet_records,
        "rating_dimensions": [identifier for identifier, _ in PAIRWISE_RATINGS],
        "blind_check": {
            "passed": True,
            "checked_files": [str(path) for path in public_files],
            "leaks": [],
        },
    }
    write_json(output / "feedback_manifest.json", manifest)
    return manifest


def validate_feedback_response(
    raw: Mapping[str, Any],
    *,
    expected_package_id: str | None = None,
) -> dict[str, Any]:
    if raw.get("schema_version") != FEEDBACK_SCHEMA_VERSION:
        raise ValueError("unsupported feedback response schema")
    package_id = str(raw.get("package_id", ""))
    if expected_package_id and package_id != expected_package_id:
        raise ValueError("feedback package ID mismatch")
    reviewer_code = str(raw.get("reviewer_code", "")).strip()
    if not _REVIEWER_CODE_RE.fullmatch(reviewer_code):
        raise ValueError("invalid reviewer_code")
    labels = tuple(str(label) for label in raw.get("labels", ()))
    if len(labels) not in {2, 3} or any(label not in ALL_LABELS for label in labels):
        raise ValueError("feedback labels must contain two or three of A/B/C")
    if len(set(labels)) != len(labels):
        raise ValueError("feedback labels must be unique")
    responses = raw.get("responses")
    if not isinstance(responses, Mapping):
        raise TypeError("feedback responses must be an object")
    clean: dict[str, str] = {str(key): str(value) for key, value in responses.items()}
    for label in labels:
        for dimension, _ in PAIRWISE_RATINGS:
            key = f"{label}_{dimension}"
            try:
                value = int(clean.get(key, ""))
            except ValueError as exc:
                raise ValueError(f"{key} must be an integer from 1 to 7") from exc
            if value not in range(1, 8):
                raise ValueError(f"{key} must be an integer from 1 to 7")
    for left_index, left in enumerate(labels):
        for right in labels[left_index + 1 :]:
            key = f"pair_{left}_{right}"
            if clean.get(key) not in {left, right, "tie"}:
                raise ValueError(f"{key} must choose {left}, {right}, or tie")
    normalized = {
        "schema_version": FEEDBACK_SCHEMA_VERSION,
        "package_id": package_id,
        "packet_id": str(raw.get("packet_id", "")),
        "reviewer_code": reviewer_code,
        "labels": list(labels),
        "saved_at": str(raw.get("saved_at", "")),
        "responses": clean,
    }
    normalized["response_id"] = hash_json(normalized)
    return normalized


def _pair_key(left: str, right: str) -> str:
    return "".join(sorted((left, right)))


def _choose_winner(
    pairwise: Mapping[str, Mapping[str, Any]],
    medians: Mapping[str, Mapping[str, float]],
) -> str:
    head_to_head_wins = {label: 0 for label in ALL_LABELS}
    for stats in pairwise.values():
        winner = str(stats.get("winner", "tie"))
        if winner in head_to_head_wins:
            head_to_head_wins[winner] += 1
    condorcet = [
        label for label, wins in head_to_head_wins.items() if wins == 2
    ]
    if len(condorcet) == 1:
        return condorcet[0]
    return max(
        ALL_LABELS,
        key=lambda label: (
            float(medians.get(label, {}).get("desire_to_continue", 0)),
            float(medians.get(label, {}).get("romantic_pull", 0)),
            float(medians.get(label, {}).get("trust", 0)),
            label,
        ),
    )


def summarize_feedback(
    response_files: Sequence[str | Path],
    *,
    expected_package_id: str | None = None,
) -> HumanFeedbackBrief:
    if not response_files:
        raise ValueError("at least one response file is required")
    records: list[dict[str, Any]] = []
    reviewers: set[str] = set()
    package_id = expected_package_id or ""
    for response_file in response_files:
        raw = json.loads(Path(response_file).read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise TypeError(f"feedback response is not an object: {response_file}")
        record = validate_feedback_response(
            raw, expected_package_id=package_id or None
        )
        package_id = package_id or record["package_id"]
        reviewer = record["reviewer_code"]
        if reviewer in reviewers:
            raise ValueError(f"duplicate reviewer_code: {reviewer}")
        reviewers.add(reviewer)
        records.append(record)
    values: dict[str, dict[str, list[int]]] = {
        label: {dimension: [] for dimension, _ in PAIRWISE_RATINGS}
        for label in ALL_LABELS
    }
    comments: dict[str, dict[str, list[str]]] = {
        label: {identifier: [] for identifier, _ in PAIRWISE_FREE_RESPONSES}
        for label in ALL_LABELS
    }
    pair_votes: dict[str, dict[str, float]] = {
        key: {key[0]: 0.0, key[1]: 0.0, "tie": 0.0}
        for key in ("AB", "AC", "BC")
    }
    coverage = {key: 0 for key in ("AB", "AC", "BC")}
    for record in records:
        responses = record["responses"]
        labels = record["labels"]
        for label in labels:
            for dimension, _ in PAIRWISE_RATINGS:
                values[label][dimension].append(
                    int(responses[f"{label}_{dimension}"])
                )
            for identifier, _ in PAIRWISE_FREE_RESPONSES:
                text = responses.get(f"{label}_{identifier}", "").strip()
                if text:
                    comments[label][identifier].append(text)
        for left_index, left in enumerate(labels):
            for right in labels[left_index + 1 :]:
                key = _pair_key(left, right)
                selected = responses[f"pair_{left}_{right}"]
                coverage[key] += 1
                pair_votes[key][selected] += 1.0
    medians = {
        label: {
            dimension: float(median(items)) if items else 0.0
            for dimension, items in dimensions.items()
        }
        for label, dimensions in values.items()
    }
    pairwise: dict[str, dict[str, Any]] = {}
    for key, votes in pair_votes.items():
        left, right = key
        if votes[left] > votes[right]:
            winner = left
        elif votes[right] > votes[left]:
            winner = right
        else:
            winner = "tie"
        pairwise[key] = {"votes": votes, "winner": winner}
    winner = _choose_winner(pairwise, medians)
    fail_fast = all(
        medians[label]["desire_to_continue"] < 4
        or medians[label]["trust"] < 4
        for label in ALL_LABELS
    )
    return HumanFeedbackBrief(
        package_id=package_id,
        source_kind="human",
        response_ids=tuple(record["response_id"] for record in records),
        coverage=coverage,
        pairwise=pairwise,
        rating_medians=medians,
        winner_label=winner,
        strengths={
            label: tuple(comments[label]["hottest"]) for label in ALL_LABELS
        },
        defects={
            label: tuple(comments[label]["false"]) for label in ALL_LABELS
        },
        desired_next={
            label: tuple(comments[label]["next"]) for label in ALL_LABELS
        },
        fail_fast=fail_fast,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def bootstrap_feedback_brief(
    *,
    reviewer_files: Sequence[str | Path],
    package_id: str,
) -> HumanFeedbackBrief:
    """Create a visibly non-human brief to exercise downstream infrastructure."""

    if not reviewer_files:
        raise ValueError("bootstrap feedback requires reviewer files")
    pair_counts = {
        key: {key[0]: 0.0, key[1]: 0.0, "tie": 0.0}
        for key in ("AB", "AC", "BC")
    }
    strengths = {label: [] for label in ALL_LABELS}
    defects = {label: [] for label in ALL_LABELS}
    desired = {label: [] for label in ALL_LABELS}
    response_ids: list[str] = []
    for reviewer_file in reviewer_files:
        raw = json.loads(Path(reviewer_file).read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise TypeError("bootstrap review must be an object")
        response_ids.append(hash_json(raw))
        choices = raw.get("pairwise_choices", {})
        if isinstance(choices, Mapping):
            for raw_key, selected in choices.items():
                key = "".join(character for character in str(raw_key) if character in "ABC")
                if len(key) == 2:
                    key = _pair_key(key[0], key[1])
                    if key in pair_counts and str(selected) in pair_counts[key]:
                        pair_counts[key][str(selected)] += 1
        finalists = raw.get("finalists", {})
        if not isinstance(finalists, Mapping):
            continue
        for label in ALL_LABELS:
            item = finalists.get(label, {})
            if not isinstance(item, Mapping):
                continue
            strongest = item.get("strongest_passage")
            if isinstance(strongest, Mapping):
                text = str(strongest.get("quote", "")).strip()
            else:
                text = str(strongest or "").strip()
            if text:
                strengths[label].append(text)
            for defect in item.get("defects", ()):
                if isinstance(defect, Mapping):
                    explanation = str(defect.get("explanation", "")).strip()
                    if explanation:
                        defects[label].append(explanation)
            summary = str(item.get("summary", "")).strip()
            if summary:
                desired[label].append(
                    "Continue the demonstrated strengths while addressing: "
                    + summary
                )
    pairwise = {}
    for key, votes in pair_counts.items():
        left, right = key
        winner = (
            left
            if votes[left] > votes[right]
            else right
            if votes[right] > votes[left]
            else "tie"
        )
        pairwise[key] = {"votes": votes, "winner": winner}
    medians = {
        label: {identifier: 0.0 for identifier, _ in PAIRWISE_RATINGS}
        for label in ALL_LABELS
    }
    winner = _choose_winner(pairwise, medians)
    return HumanFeedbackBrief(
        package_id=package_id,
        source_kind="bootstrap-codex",
        response_ids=tuple(response_ids),
        coverage={key: len(reviewer_files) for key in ("AB", "AC", "BC")},
        pairwise=pairwise,
        rating_medians=medians,
        winner_label=winner,
        strengths={key: tuple(value) for key, value in strengths.items()},
        defects={key: tuple(value) for key, value in defects.items()},
        desired_next={key: tuple(value) for key, value in desired.items()},
        fail_fast=False,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
