"""Create a blinded, static human-appraisal package."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import random
from typing import Any, Mapping, Sequence

from .authorship import validate_artifact_authorship, validate_review_attestations


LABELS = ("A", "B", "C")
RATING_DIMENSIONS = (
    ("author_resemblance", "Resemblance to the declared craft target"),
    ("romantic_pull", "Romantic pull"),
    ("heat", "Erotic heat"),
    ("emotional_exchange", "Specific emotional exchange"),
    ("embodied_charge", "Embodied charge"),
    ("productive_restraint", "Restraint intensifies desire"),
    ("suspense", "Suspense"),
    ("character_fascination", "Character fascination"),
    ("trust", "Trust in the story"),
    ("prose_freshness", "Prose freshness"),
    ("clarity", "Clarity"),
    ("worldview_integration", "Worldview integration"),
    ("desire_to_continue", "Desire to continue"),
    ("suspected_copying", "Suspicion of source copying"),
    ("preachiness", "Preachiness"),
)
FREE_RESPONSE_PROMPTS = (
    ("change", "What happened and what changed?"),
    (
        "exchange",
        "What did each character want from the contact, and what did the other give?",
    ),
    (
        "restraint",
        "Where did restraint or omission intensify the scene—and where did it deflate it?",
    ),
    ("teaching", "What teaching, if any, did you infer?"),
    ("hottest", "Which passage felt hottest?"),
    ("false", "Which passage felt false, generic, or over-explained?"),
    ("memorable", "Quote the line you most remember."),
)


def _record(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "to_dict"):
        result = value.to_dict()
        if isinstance(result, Mapping):
            return dict(result)
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    raise TypeError(f"Expected a mapping-like finalist, got {type(value).__name__}")


def _safe_slug(value: str) -> str:
    return "".join(character if character.isalnum() or character in "-_" else "-" for character in value).strip("-") or "finalist"


def blind_label_map(finalists: Sequence[Mapping[str, Any] | Any], blind_seed: str | int) -> dict[str, dict[str, Any]]:
    """Assign A/B/C deterministically without exposing identity in the reader view."""
    records = [_record(finalist) for finalist in finalists]
    if len(records) != 3:
        raise ValueError(f"Human appraisal requires exactly three finalists, received {len(records)}")
    identifiers = [str(record.get("candidate_id", record.get("id", ""))) for record in records]
    if any(not identifier for identifier in identifiers) or len(set(identifiers)) != 3:
        raise ValueError("Every finalist must have a distinct non-empty candidate_id")
    shuffled = list(records)
    random.Random(str(blind_seed)).shuffle(shuffled)
    return {
        label: {
            "candidate_id": str(record.get("candidate_id", record.get("id", ""))),
            "pipeline": str(record.get("pipeline", "")),
            "model_role": str(record.get("model_role", record.get("telemetry", {}).get("model_role", "")))
            if isinstance(record.get("telemetry", {}), Mapping)
            else str(record.get("model_role", "")),
            "text": str(record.get("text", "")),
            "text_sha256": sha256(str(record.get("text", "")).encode("utf-8")).hexdigest(),
            "word_count": len(str(record.get("text", "")).split()),
            "ontology_version": str(record.get("ontology_version", "")),
            "story_profile_id": str(record.get("story_profile_id", "")),
            "scene_profile_id": str(record.get("scene_profile_id", "")),
            "resolved_profile_hash": str(
                record.get("resolved_profile_hash", "")
            ),
            "author_profile_id": str(record.get("author_profile_id", "")),
            "author_profile_hash": str(record.get("author_profile_hash", "")),
            "corpus_manifest_hash": str(record.get("corpus_manifest_hash", "")),
            "transformation_map_hash": str(
                record.get("transformation_map_hash", "")
            ),
            "conditioning_variant": str(
                record.get("conditioning_variant", "")
            ),
            "prompt_encoding": str(record.get("prompt_encoding", "")),
            "control_density": str(record.get("control_density", "")),
            "story_program_id": str(record.get("story_program_id", "")),
            "anti_copy_policy_version": str(
                record.get("anti_copy_policy_version", "")
            ),
            "anti_copy_index_hash": str(
                record.get("anti_copy_index_hash", "")
            ),
            "frontier_adapter": str(record.get("frontier_adapter", "")),
            "approved_prefix_id": str(record.get("approved_prefix_id", "")),
            "approved_prefix_hash": str(
                record.get("approved_prefix_hash", "")
            ),
            "feedback_brief_hash": str(
                record.get("feedback_brief_hash", "")
            ),
            "generation_mode": str(record.get("generation_mode", "")),
        }
        for label, record in zip(LABELS, shuffled)
    }


def _prose_html(text: str) -> str:
    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    if not paragraphs:
        paragraphs = [text]
    return "\n".join(f"<p>{escape(paragraph).replace(chr(10), '<br>')}</p>" for paragraph in paragraphs)


def _rating_rows(label: str) -> str:
    rows = []
    for dimension_id, dimension_label in RATING_DIMENSIONS:
        options = "".join(
            f'<label class="score"><input type="radio" name="{label}_{dimension_id}" value="{score}" required> {score}</label>'
            for score in range(1, 8)
        )
        rows.append(f'<div class="rating-row"><span>{escape(dimension_label)}</span><div class="scale">{options}</div></div>')
    return "\n".join(rows)


def _free_response_rows(label: str) -> str:
    return "\n".join(
        f'<label class="prompt">{escape(prompt)}<textarea name="{label}_{prompt_id}" rows="3"></textarea></label>'
        for prompt_id, prompt in FREE_RESPONSE_PROMPTS
    )


def _html_document(label_map: Mapping[str, Mapping[str, Any]], package_id: str) -> str:
    comparisons = (("A", "B"), ("A", "C"), ("B", "C"))
    comparison_html = "\n".join(
        (
            f'<fieldset><legend>{left} versus {right}</legend>'
            f'<label><input type="radio" name="pair_{left}_{right}" value="{left}" required> {left}</label>'
            f'<label><input type="radio" name="pair_{left}_{right}" value="{right}" required> {right}</label>'
            f'<label><input type="radio" name="pair_{left}_{right}" value="tie" required> Tie</label>'
            "</fieldset>"
        )
        for left, right in comparisons
    )
    candidate_sections = "\n".join(
        (
            f'<article id="candidate-{label}"><header><h2>Finalist {label}</h2>'
            f'<span>{entry["word_count"]:,} words</span></header>'
            f'<div class="prose">{_prose_html(str(entry["text"]))}</div>'
            f'<section class="ratings"><h3>Ratings for {label}</h3>{_rating_rows(label)}</section>'
            f'<section class="responses"><h3>Reader notes for {label}</h3>{_free_response_rows(label)}</section>'
            "</article>"
        )
        for label, entry in label_map.items()
    )
    dimension_legend = " · ".join(f"{label}" for _, label in RATING_DIMENSIONS)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>The Calibration Game — Blind Appraisal</title>
  <style>
    :root {{ --ink:#211d1b; --paper:#fbf7ef; --accent:#7b2945; --gold:#b88435; --line:#d7cbb9; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:#ece4d8; font-family:Georgia, "Times New Roman", serif; line-height:1.58; }}
    nav {{ position:sticky; top:0; z-index:5; display:flex; gap:1rem; align-items:center; padding:.65rem 5vw; background:#211d1bee; color:white; }}
    nav a {{ color:#f2d8a8; text-decoration:none; font-weight:bold; }}
    nav .spacer {{ flex:1; }}
    button {{ border:0; border-radius:4px; padding:.6rem .9rem; background:var(--accent); color:white; cursor:pointer; }}
    button.secondary {{ background:transparent; border:1px solid #f2d8a8; color:#f2d8a8; }}
    main {{ width:min(980px, 94vw); margin:2rem auto 6rem; }}
    .masthead {{ padding:2.3rem; background:var(--paper); border-top:6px solid var(--accent); box-shadow:0 8px 30px #33291d1c; }}
    .masthead h1 {{ margin:0; font-size:clamp(2rem, 5vw, 3.5rem); font-weight:normal; }}
    .eyebrow {{ color:var(--accent); text-transform:uppercase; letter-spacing:.14em; font:700 .75rem system-ui,sans-serif; }}
    .instructions {{ border-left:3px solid var(--gold); padding-left:1rem; }}
    article {{ margin-top:2rem; padding:clamp(1.2rem,4vw,3.5rem); background:var(--paper); box-shadow:0 8px 30px #33291d1c; }}
    article header {{ display:flex; justify-content:space-between; align-items:baseline; border-bottom:1px solid var(--line); }}
    article h2 {{ font-size:2rem; font-weight:normal; color:var(--accent); }}
    article h3 {{ margin-top:2rem; font:700 1rem system-ui,sans-serif; text-transform:uppercase; letter-spacing:.08em; }}
    .prose {{ font-size:1.08rem; }}
    .prose p {{ margin:0 0 1em; }}
    .rating-row {{ display:grid; grid-template-columns:minmax(150px,1fr) 2fr; gap:1rem; padding:.55rem 0; border-bottom:1px dotted var(--line); font-family:system-ui,sans-serif; }}
    .scale {{ display:flex; flex-wrap:wrap; gap:.65rem; }}
    .score {{ white-space:nowrap; }}
    .prompt {{ display:block; margin:1.2rem 0; font-family:system-ui,sans-serif; font-weight:600; }}
    textarea {{ display:block; width:100%; margin-top:.4rem; border:1px solid var(--line); background:white; padding:.7rem; font:1rem Georgia,serif; }}
    .comparison {{ margin-top:2rem; padding:2rem; background:var(--paper); }}
    fieldset {{ margin:1rem 0; border:1px solid var(--line); font-family:system-ui,sans-serif; }}
    fieldset label {{ margin-right:1.5rem; }}
    .status {{ font: .85rem system-ui,sans-serif; color:#f3dcc0; }}
    footer {{ margin-top:2rem; font: .9rem system-ui,sans-serif; color:#62594f; }}
    @media (max-width:650px) {{ .rating-row {{ grid-template-columns:1fr; }} nav .title {{ display:none; }} }}
    @media print {{ nav, button {{ display:none; }} body {{ background:white; }} article,.masthead,.comparison {{ box-shadow:none; break-inside:avoid; }} }}
  </style>
</head>
<body>
  <nav>
    <span class="title">Blind appraisal</span>
    <a href="#candidate-A">A</a><a href="#candidate-B">B</a><a href="#candidate-C">C</a><a href="#comparisons">Compare</a>
    <span class="spacer"></span><span class="status" id="status">Responses save in this browser</span>
    <button type="button" class="secondary" id="clear">Clear responses</button>
    <button type="button" id="export">Export responses</button>
  </nav>
  <main>
    <section class="masthead">
      <div class="eyebrow">The Calibration Game · blind reader packet</div>
      <h1>Three ways into the redwoods</h1>
      <p class="instructions">Read all three finalists before choosing between them. Score what is actually on the page. A high “preachiness” rating means more preachy, not better. Your entries save locally as you type; export the JSON when you finish.</p>
      <p><strong>Rating dimensions:</strong> {escape(dimension_legend)}</p>
    </section>
    <form id="appraisal" autocomplete="off">
      {candidate_sections}
      <section class="comparison" id="comparisons">
        <h2>Pairwise choices</h2>
        <p>Which complete scene would you rather continue reading?</p>
        {comparison_html}
        <label class="prompt">Overall ranking (best to least strong)
          <input name="overall_ranking" placeholder="e.g. B, A, C" pattern="[ABCabc, >-]+" style="display:block;width:100%;padding:.7rem;margin-top:.4rem">
        </label>
        <label class="prompt">Anything the ratings missed?
          <textarea name="overall_notes" rows="5"></textarea>
        </label>
      </section>
    </form>
    <footer>Package <code>{escape(package_id)}</code>. No authorship or generation information is included in this reader file.</footer>
  </main>
  <script>
  (() => {{
    const packageId = {json.dumps(package_id)};
    const key = "fiction-appraisal:" + packageId;
    const form = document.getElementById("appraisal");
    const status = document.getElementById("status");
    function snapshot() {{
      const result = {{package_id: packageId, saved_at: new Date().toISOString(), responses: {{}}}};
      new FormData(form).forEach((value, name) => result.responses[name] = value);
      return result;
    }}
    function save() {{
      localStorage.setItem(key, JSON.stringify(snapshot()));
      status.textContent = "Saved " + new Date().toLocaleTimeString();
    }}
    function restore() {{
      const raw = localStorage.getItem(key); if (!raw) return;
      const saved = JSON.parse(raw).responses || {{}};
      Object.entries(saved).forEach(([name, value]) => {{
        const fields = form.elements[name]; if (!fields) return;
        if (fields.length && fields[0] && fields[0].type === "radio") {{
          [...fields].forEach(field => field.checked = field.value === value);
        }} else {{ fields.value = value; }}
      }});
      status.textContent = "Restored saved responses";
    }}
    form.addEventListener("input", save);
    document.getElementById("clear").addEventListener("click", () => {{
      form.reset();
      localStorage.removeItem(key);
      status.textContent = "Responses cleared";
    }});
    document.getElementById("export").addEventListener("click", () => {{
      save();
      const blob = new Blob([JSON.stringify(snapshot(), null, 2)], {{type:"application/json"}});
      const link = document.createElement("a"); link.href = URL.createObjectURL(blob);
      link.download = "calibration-game-appraisal-" + packageId + ".json"; link.click();
      status.textContent = "Responses exported";
      setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    }});
    restore();
  }})();
  </script>
</body>
</html>
"""


def _markdown_document(label_map: Mapping[str, Mapping[str, Any]], package_id: str) -> str:
    chunks = [
        "# The Calibration Game — Blind Appraisal",
        "",
        f"Package `{package_id}`",
        "",
        "Read all three finalists before scoring. Use 1–7 for each rating. For preachiness, 7 means more preachy.",
    ]
    for label, entry in label_map.items():
        chunks.extend(["", f"## Finalist {label}", "", str(entry["text"]), "", f"### Ratings for {label}", ""])
        chunks.extend(f"- {dimension_label}: ___ / 7" for _, dimension_label in RATING_DIMENSIONS)
        chunks.extend(["", f"### Reader notes for {label}", ""])
        chunks.extend(f"- {prompt}  \n  " for _, prompt in FREE_RESPONSE_PROMPTS)
    chunks.extend(
        [
            "",
            "## Pairwise choices",
            "",
            "- A versus B: ___",
            "- A versus C: ___",
            "- B versus C: ___",
            "- Overall ranking: ___",
            "- Anything the ratings missed?  ",
            "  ",
        ]
    )
    return "\n".join(chunks)


def _forbidden_reader_tokens(label_map: Mapping[str, Mapping[str, Any]]) -> set[str]:
    forbidden: set[str] = set()
    # A pipeline field may use a short prose word such as ``direct``.  Treating
    # that value as a literal forbidden substring makes ordinary fiction fail
    # the blind check ("her direct gaze", "a direct question").  Exact
    # candidate IDs and namespaced implementation identifiers remain forbidden;
    # only these deliberately generic aliases are exempted.
    generic_pipeline_aliases = {"direct", "native", "actor", "verbalized"}
    for entry in label_map.values():
        candidate_id = str(entry.get("candidate_id", "")).strip()
        pipeline = str(entry.get("pipeline", "")).strip()
        model_role = str(entry.get("model_role", "")).strip()
        ontology_version = str(entry.get("ontology_version", "")).strip()
        story_profile_id = str(entry.get("story_profile_id", "")).strip()
        scene_profile_id = str(entry.get("scene_profile_id", "")).strip()
        profile_hash = str(entry.get("resolved_profile_hash", "")).strip()
        if candidate_id:
            forbidden.add(candidate_id)
        if (
            pipeline
            and len(pipeline) >= 6
            and pipeline.casefold() not in generic_pipeline_aliases
        ):
            forbidden.add(pipeline)
        if model_role and len(model_role) >= 6:
            forbidden.add(model_role)
        for token in (
            ontology_version,
            story_profile_id,
            scene_profile_id,
            profile_hash,
            str(entry.get("author_profile_id", "")).strip(),
            str(entry.get("author_profile_hash", "")).strip(),
            str(entry.get("corpus_manifest_hash", "")).strip(),
            str(entry.get("transformation_map_hash", "")).strip(),
            str(entry.get("conditioning_variant", "")).strip(),
            str(entry.get("prompt_encoding", "")).strip(),
            str(entry.get("control_density", "")).strip(),
            str(entry.get("story_program_id", "")).strip(),
            str(entry.get("anti_copy_policy_version", "")).strip(),
            str(entry.get("anti_copy_index_hash", "")).strip(),
            str(entry.get("frontier_adapter", "")).strip(),
            str(entry.get("approved_prefix_id", "")).strip(),
            str(entry.get("approved_prefix_hash", "")).strip(),
            str(entry.get("feedback_brief_hash", "")).strip(),
            str(entry.get("generation_mode", "")).strip(),
        ):
            if token and len(token) >= 6:
                forbidden.add(token)
    return forbidden


def verify_blind_package(
    reader_files: Sequence[str | Path],
    label_map: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Check that reader artifacts do not expose candidate or pipeline identity."""
    leaks: list[dict[str, str]] = []
    forbidden = _forbidden_reader_tokens(label_map)
    for file_path in reader_files:
        path = Path(file_path)
        content = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token and token in content:
                leaks.append({"file": str(path), "token": token})
    return {"passed": not leaks, "leaks": leaks, "checked_files": [str(Path(path)) for path in reader_files]}


def build_appraisal(
    finalists: Sequence[Mapping[str, Any] | Any],
    out_dir: str | Path,
    blind_seed: str | int,
    *,
    require_model_pipeline: bool = True,
    minimum_independent_reviews: int = 0,
) -> dict[str, Any]:
    """Build reader-only HTML/Markdown and a separately stored reveal key."""
    provenance_by_id: dict[str, dict[str, Any]] = {}
    reviews_by_id: dict[str, dict[str, Any]] = {}
    for finalist in finalists:
        record = _record(finalist)
        candidate_id = str(record.get("candidate_id", record.get("id", "")))
        authorship = validate_artifact_authorship(
            record.get("artifact_authorship", {}),
            text=str(record.get("text", "")),
            artifact_id=candidate_id,
            require_model_pipeline=require_model_pipeline,
        )
        provenance_by_id[candidate_id] = authorship
        reviews_by_id[candidate_id] = validate_review_attestations(
            tuple(record.get("review_attestations", ())),
            creator_id=str(authorship["creator_id"]),
            minimum_independent=minimum_independent_reviews,
        )
    output = Path(out_dir)
    reader_dir = output / "reader"
    reader_dir.mkdir(parents=True, exist_ok=True)
    internal_dir = output.parent / "internal"
    internal_dir.mkdir(parents=True, exist_ok=True)

    label_map = blind_label_map(finalists, blind_seed)
    public_basis = "|".join(f"{label}:{entry['text_sha256']}" for label, entry in label_map.items())
    package_id = sha256(public_basis.encode("utf-8")).hexdigest()[:12]
    html_path = reader_dir / "index.html"
    markdown_path = reader_dir / "reader_packet.md"
    html_path.write_text(_html_document(label_map, package_id), encoding="utf-8")
    markdown_path.write_text(_markdown_document(label_map, package_id), encoding="utf-8")

    reveal_key = {
        "schema_version": "1.0",
        "package_id": package_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "blind_seed_sha256": sha256(str(blind_seed).encode("utf-8")).hexdigest(),
        "labels": {
            label: {
                "candidate_id": entry["candidate_id"],
                "pipeline": entry["pipeline"],
                "model_role": entry["model_role"],
                "text_sha256": entry["text_sha256"],
                "artifact_authorship": provenance_by_id[entry["candidate_id"]],
                "review_attestations": reviews_by_id[entry["candidate_id"]],
            }
            for label, entry in label_map.items()
        },
    }
    reveal_path = internal_dir / "reveal_key.json"
    reveal_path.write_text(json.dumps(reveal_key, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    blind_check = verify_blind_package((html_path, markdown_path), label_map)
    if not blind_check["passed"]:
        raise ValueError(f"Blind package leaks hidden identity: {blind_check['leaks']}")
    manifest = {
        "schema_version": "1.0",
        "package_id": package_id,
        "reader_html": str(html_path),
        "reader_markdown": str(markdown_path),
        "reveal_key": str(reveal_path),
        "blind_check": blind_check,
        "labels": list(LABELS),
        "response_storage": "browser_local_storage_with_json_export",
    }
    manifest_path = output / "appraisal_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest["manifest"] = str(manifest_path)
    return manifest


def build_internal_report(
    finalists: Sequence[Mapping[str, Any] | Any],
    out_dir: str | Path,
    *,
    scorecards: Sequence[Mapping[str, Any] | Any] = (),
    diversity_reports: Mapping[str, Any] | None = None,
    generation_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist the unblinded comparison kept out of the human reader packet."""
    records = [_record(finalist) for finalist in finalists]
    score_records = [_record(score) for score in scorecards]
    scores_by_candidate: dict[str, list[dict[str, Any]]] = {}
    for score in score_records:
        scores_by_candidate.setdefault(str(score.get("candidate_id", "")), []).append(score)
    rows: list[dict[str, Any]] = []
    for record in records:
        candidate_id = str(record.get("candidate_id", record.get("id", "")))
        attached = scores_by_candidate.get(candidate_id, [])
        numeric = [float(score.get("total_score", 0)) for score in attached if score.get("rubric_scores")]
        rows.append(
            {
                "candidate_id": candidate_id,
                "pipeline": str(record.get("pipeline", "")),
                "text_sha256": sha256(str(record.get("text", "")).encode("utf-8")).hexdigest(),
                "word_count": len(str(record.get("text", "")).split()),
                "mean_score": round(sum(numeric) / len(numeric), 4) if numeric else None,
                "judge_count": len(numeric),
                "eligible": all(bool(score.get("eligible", False)) for score in attached) if attached else None,
                "defects": sorted({str(defect) for score in attached for defect in score.get("defects", ())}),
            }
        )
    payload = {
        "schema_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "finalists": rows,
        "scorecards": score_records,
        "diversity_reports": dict(diversity_reports or {}),
        "generation_summary": dict(generation_summary or {}),
    }
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "pipeline_comparison.json"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown_lines = [
        "# Internal Pipeline Comparison",
        "",
        "This unblinded report is intentionally separate from the reader packet.",
        "",
        "| Candidate | Pipeline | Words | Mean score | Judges | Eligible | Defects |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for row in rows:
        score_text = "—" if row["mean_score"] is None else f"{row['mean_score']:.2f}"
        eligible_text = "—" if row["eligible"] is None else ("yes" if row["eligible"] else "no")
        markdown_lines.append(
            f"| {row['candidate_id']} | {row['pipeline']} | {row['word_count']} | "
            f"{score_text} | {row['judge_count']} | {eligible_text} | {', '.join(row['defects']) or '—'} |"
        )
    markdown_lines.extend(
        [
            "",
            "## Generation summary",
            "",
            "```json",
            json.dumps(payload["generation_summary"], indent=2, ensure_ascii=False),
            "```",
            "",
            "## Diversity and ablations",
            "",
            "```json",
            json.dumps(payload["diversity_reports"], indent=2, ensure_ascii=False),
            "```",
            "",
        ]
    )
    markdown_path = output / "internal_report.md"
    markdown_path.write_text("\n".join(markdown_lines), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(markdown_path), "finalist_count": len(rows)}
