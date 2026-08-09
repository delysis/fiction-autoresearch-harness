#!/usr/bin/env python3
"""Create blind S01 comparison and integrated-story appraisal packets."""

from __future__ import annotations

import html
import json
from pathlib import Path
import random
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fiction_harness.core import hash_file, write_json  # noqa: E402
from fiction_harness.authorship import validate_artifact_authorship  # noqa: E402


RUN_ROOT = PROJECT_ROOT / "03_scene_lab/runs/s01-atom-rewrite-v1"
APPRAISAL_ROOT = RUN_ROOT / "appraisal"
SELECTION_MANIFEST = RUN_ROOT / "selected/selection_manifest.v2.json"
BLIND_SEED = 51703

S01_FILES = {
    "candidate-a": RUN_ROOT / "candidates/s01-a-gift-status.codex.v1.md",
    "candidate-b": RUN_ROOT / "selected/s01-b-somatic-control.codex.v2.md",
    "candidate-c": RUN_ROOT / "candidates/s01-c-method-audit.codex.v1.md",
}

DIMENSIONS = (
    "romantic pull",
    "suspense",
    "character fascination",
    "trust",
    "prose freshness",
    "clarity",
    "desire to continue",
    "preachiness",
)

QUESTIONS = (
    "What happened and what changed?",
    "What teaching, if any, did you infer?",
    "Which passage felt hottest?",
    "Which passage felt false, generic, or over-explained?",
    "Quote the line you most remember.",
)


def rating_fields(prefix: str) -> str:
    options = '<option value="">—</option>' + "".join(
        f'<option value="{value}">{value}</option>' for value in range(1, 8)
    )
    return "".join(
        (
            f'<label>{html.escape(name.title())}'
            f'<select name="{prefix}-{name.replace(" ", "_")}">{options}</select>'
            "</label>"
        )
        for name in DIMENSIONS
    )


def free_fields(prefix: str) -> str:
    return "".join(
        (
            f'<label class="wide">{html.escape(question)}'
            f'<textarea name="{prefix}-q{index}" rows="3"></textarea></label>'
        )
        for index, question in enumerate(QUESTIONS, 1)
    )


def page(title: str, intro: str, body: str, storage_key: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: light; --ink:#24211d; --paper:#fbf7ef; --accent:#744f3a; --line:#d7c9b9; }}
body {{ margin:0; background:#eee7dc; color:var(--ink); font:18px/1.65 Georgia,serif; }}
main {{ max-width:900px; margin:0 auto; padding:3rem 5vw 6rem; background:var(--paper); box-shadow:0 0 40px #5b49331f; }}
h1,h2,h3 {{ line-height:1.15; }} h1 {{ font-size:2.3rem; }} h2 {{ margin-top:3rem; border-top:1px solid var(--line); padding-top:2rem; }}
.intro {{ font-size:1.05rem; color:#554b42; }} .story {{ white-space:pre-wrap; }}
details {{ margin:2rem 0; }} summary {{ cursor:pointer; font-weight:bold; font-size:1.25rem; }}
.form-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:1rem; }}
label {{ display:flex; flex-direction:column; gap:.35rem; font:15px/1.35 system-ui,sans-serif; }}
select,textarea,input {{ font:16px system-ui,sans-serif; padding:.55rem; border:1px solid var(--line); border-radius:6px; background:white; }}
.wide {{ grid-column:1/-1; }} .pair {{ display:flex; gap:1rem; flex-wrap:wrap; margin:.5rem 0 1.25rem; font:16px system-ui,sans-serif; }}
.pair label {{ display:inline-flex; flex-direction:row; align-items:center; }} button {{ margin-top:1.5rem; padding:.8rem 1.2rem; border:0; border-radius:6px; background:var(--accent); color:white; font-weight:bold; cursor:pointer; }}
.status {{ font:14px system-ui,sans-serif; color:#655; margin-left:1rem; }}
</style></head><body><main><h1>{html.escape(title)}</h1><p class="intro">{html.escape(intro)}</p>
<form id="appraisal">{body}<button type="button" id="export">Export responses</button><span class="status" id="status">Saved locally</span></form>
<script>
const form=document.getElementById('appraisal'), key={json.dumps(storage_key)};
const saved=JSON.parse(localStorage.getItem(key)||'{{}}');
for(const el of form.elements){{if(!el.name)continue;if(el.type==='radio')el.checked=saved[el.name]===el.value;else if(saved[el.name]!==undefined)el.value=saved[el.name];}}
function collect(){{const out={{}};for(const el of form.elements){{if(!el.name)continue;if(el.type==='radio'){{if(el.checked)out[el.name]=el.value;}}else out[el.name]=el.value;}}return out;}}
form.addEventListener('input',()=>{{localStorage.setItem(key,JSON.stringify(collect()));document.getElementById('status').textContent='Saved locally';}});
document.getElementById('export').addEventListener('click',()=>{{const data={{packet:key,exported_at:new Date().toISOString(),responses:collect()}};const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{{type:'application/json'}}));a.download=key+'-responses.json';a.click();URL.revokeObjectURL(a.href);}});
</script></main></body></html>"""


def main() -> None:
    # This historical packager predated typed authorship.  Fail closed rather
    # than silently turning manually edited files into apparent model winners.
    for identity, path in S01_FILES.items():
        sidecar = path.with_suffix(path.suffix + ".authorship.json")
        if not sidecar.is_file():
            raise ValueError(
                f"{identity} lacks required authorship sidecar {sidecar}; "
                "untraced appraisal packaging is disabled"
            )
        validate_artifact_authorship(
            json.loads(sidecar.read_text(encoding="utf-8")),
            text=path.read_text(encoding="utf-8"),
            require_model_pipeline=True,
        )
    selection = json.loads(SELECTION_MANIFEST.read_text(encoding="utf-8"))
    for path_key in ("revised_s01_path", "immutable_s02_path", "merged_path"):
        path = PROJECT_ROOT / selection[path_key]
        expected = selection[path_key.replace("path", "sha256")]
        if hash_file(path) != expected:
            raise ValueError(f"selection artifact hash changed: {path_key}")

    identities = list(S01_FILES)
    random.Random(BLIND_SEED).shuffle(identities)
    label_to_identity = dict(zip(("A", "B", "C"), identities))
    blind_sections = []
    blind_markdown = ["# S01 blind appraisal", ""]
    for label, identity in label_to_identity.items():
        text = S01_FILES[identity].read_text(encoding="utf-8").strip()
        blind_sections.append(
            f'<details><summary>Story {label}</summary><article class="story">{html.escape(text)}</article></details>'
            f'<h3>Story {label} ratings</h3><div class="form-grid">{rating_fields(label)}{free_fields(label)}</div>'
        )
        blind_markdown.extend((f"## Story {label}", "", text, ""))
    pairwise = []
    for left, right in (("A", "B"), ("A", "C"), ("B", "C")):
        name = f"pair-{left}{right}"
        pairwise.append(
            f'<p>Which do you prefer: {left} or {right}?</p><div class="pair">'
            f'<label><input type="radio" name="{name}" value="{left}"> {left}</label>'
            f'<label><input type="radio" name="{name}" value="{right}"> {right}</label>'
            f'<label><input type="radio" name="{name}" value="tie"> Tie</label></div>'
        )
    blind_body = "".join(blind_sections) + "<h2>Pairwise choices</h2>" + "".join(pairwise)
    blind_body += (
        '<label class="wide">Overall first choice<select name="overall">'
        '<option value="">—</option><option>A</option><option>B</option><option>C</option></select></label>'
    )
    blind_reader = APPRAISAL_ROOT / "s01_blind/reader"
    blind_reader.mkdir(parents=True, exist_ok=True)
    (blind_reader / "index.html").write_text(
        page(
            "The Calibration Game — blind comparison",
            "Read all three versions before ranking. Labels contain no production information. Responses remain in this browser until you export them.",
            blind_body,
            "s01-atom-rewrite-blind-v1",
        ),
        encoding="utf-8",
    )
    (blind_reader / "reader_packet.md").write_text(
        "\n".join(blind_markdown), encoding="utf-8"
    )

    merged_path = PROJECT_ROOT / selection["merged_path"]
    merged_text = merged_path.read_text(encoding="utf-8").strip()
    integrated_body = (
        f'<article class="story">{html.escape(merged_text)}</article>'
        f'<h2>Reader response</h2><div class="form-grid">{rating_fields("story")}{free_fields("story")}</div>'
    )
    integrated_reader = APPRAISAL_ROOT / "integrated_story/reader"
    integrated_reader.mkdir(parents=True, exist_ok=True)
    (integrated_reader / "index.html").write_text(
        page(
            "The Calibration Game / The Doorway Rule",
            "Read the complete two-scene story once before rating it. Responses remain in this browser until you export them.",
            integrated_body,
            "s01-s02-integrated-v2",
        ),
        encoding="utf-8",
    )
    (integrated_reader / "reader_packet.md").write_text(
        "# The Calibration Game / The Doorway Rule\n\n" + merged_text + "\n",
        encoding="utf-8",
    )

    forbidden = (
        "gift-status",
        "somatic-control",
        "method-audit",
        "codex",
        "pipeline",
        "bundle",
        "gemma",
        "llama.cpp",
        "total_score",
    )
    leaks = []
    for root in (blind_reader, integrated_reader):
        for path in root.iterdir():
            lower = path.read_text(encoding="utf-8").casefold()
            for token in forbidden:
                if token in lower:
                    leaks.append({"path": str(path), "token": token})
    if leaks:
        raise ValueError(f"reader identity leak: {leaks}")

    internal_root = APPRAISAL_ROOT / "internal"
    write_json(
        internal_root / "reveal_key.v1.json",
        {
            "version": "s01-atom-rewrite-blind-key.v1",
            "seed": BLIND_SEED,
            "labels": {
                label: {
                    "identity": identity,
                    "path": str(S01_FILES[identity].relative_to(PROJECT_ROOT)),
                    "sha256": hash_file(S01_FILES[identity]),
                }
                for label, identity in label_to_identity.items()
            },
        },
    )
    manifest = {
        "version": "s01-atom-appraisal.v1",
        "blind_reader": str((blind_reader / "index.html").relative_to(PROJECT_ROOT)),
        "integrated_reader": str((integrated_reader / "index.html").relative_to(PROJECT_ROOT)),
        "reveal_key": str((internal_root / "reveal_key.v1.json").relative_to(PROJECT_ROOT)),
        "identity_leaks": leaks,
        "selected_story_sha256": hash_file(merged_path),
        "release_status": "human-appraisal-candidate-not-release",
    }
    write_json(APPRAISAL_ROOT / "appraisal_manifest.v1.json", manifest)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
