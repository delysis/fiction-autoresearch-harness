#!/usr/bin/env python3
"""Run deterministic and literary diagnostics over the three S01 rewrites."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fiction_harness.core import hash_file, write_json  # noqa: E402
from fiction_harness.evaluation import (  # noqa: E402
    evaluate_candidate,
    integrated_style_discontinuity_diagnostics,
    word_count,
)


RUN_ROOT = PROJECT_ROOT / "03_scene_lab/runs/s01-atom-rewrite-v1"
CANDIDATE_ROOT = RUN_ROOT / "candidates"
EVALUATION_ROOT = RUN_ROOT / "evaluation"
COMPILED_SCENE = (
    PROJECT_ROOT / "03_scene_lab/compiled/s01-v2-ontology/scene_specs/s01.v1.json"
)
POOL_PATH = RUN_ROOT / "atoms/s01_dramatic_atom_pool.v1.json"
S02_PATH = (
    PROJECT_ROOT
    / "03_scene_lab/runs/s02-compute-v4.3-a4b/frontier_novelist/s02.codex.v1.md"
)
LOCKED_S02_HASH = "8561c609388e564f2d35edcffafec3f60969b96e003c0024241dcb3b5c5cf06e"

CANDIDATES = {
    "s01-a-gift-status": CANDIDATE_ROOT / "s01-a-gift-status.codex.v1.md",
    "s01-b-somatic-control": CANDIDATE_ROOT / "s01-b-somatic-control.codex.v1.md",
    "s01-c-method-audit": CANDIDATE_ROOT / "s01-c-method-audit.codex.v1.md",
    "s01-b-somatic-control-v2": RUN_ROOT
    / "selected/s01-b-somatic-control.codex.v2.md",
}


def extra_gates(text: str) -> dict[str, dict[str, object]]:
    lower = text.casefold()
    leakage = [
        token
        for token in (
            "atom_id",
            "scene_contract",
            "constraint_change",
            "s01-arr-",
            "s01-cal-",
            "s01-ctr-",
            "novelist packet",
        )
        if token in lower
    ]
    ending = text.rstrip()
    completion = bool(ending) and ending[-1] in '.!?…””\'"'
    endpoint_checks = {
        "chooses_fellowship": bool(
            re.search(
                r"\b(?:accept place|fellows[’'] house|room (?:key|credential)|"
                r"if you[’']re staying|tomorrow)\b",
                text,
                re.IGNORECASE,
            )
        ),
        "food_becomes_action": bool(
            re.search(r"\b(?:open|opened|lifted)\b.{0,180}\bbakery box\b|\bbakery box\b.{0,180}\b(?:open|opened|eat|ate|buns?)\b", text, re.IGNORECASE | re.DOTALL)
        ),
        "no_kiss": not bool(re.search(r"\bkiss(?:ed|es|ing)?\b", text, re.IGNORECASE)),
    }
    continuity_checks = {
        "wrist_stream_recorded": bool(
            re.search(r"\b(?:record|stream|trace)\w*\b", text, re.IGNORECASE)
            and re.search(r"\bwrist\b", text, re.IGNORECASE)
        ),
        "jonah_hardware_role": bool(
            re.search(r"\bJonah\b.{0,500}\b(?:hardware|sensor|terminal|security)\b", text, re.IGNORECASE | re.DOTALL)
        ),
        "timed_wrist_pressure": bool(
            re.search(r"\bthumb\b.{0,260}\b(?:pulse|peak|trace|pressure|arc)\b", text, re.IGNORECASE | re.DOTALL)
        ),
        "livia_miss_survives": bool(
            re.search(r"\bLivia\b.{0,700}\b(?:wrong|miss|blocked|deviation|quiet|dropped|gone)\b", text, re.IGNORECASE | re.DOTALL)
        ),
        "miriam_observer_seeded": bool(
            re.search(r"\bMiriam\b.{0,240}\b(?:observer|badge|console|log)\b", text, re.IGNORECASE | re.DOTALL)
            or re.search(r"\b(?:observer|badge|console|log)\b.{0,240}\bMiriam\b", text, re.IGNORECASE | re.DOTALL)
        ),
        "no_premature_raw_access": not bool(
            re.search(r"\bMara\b.{0,180}\b(?:receives|gets|has|accepts)\b.{0,100}\braw (?:review |telemetry )?access\b", text, re.IGNORECASE | re.DOTALL)
        ),
    }
    return {
        "packet_leakage": {"passed": not leakage, "matches": leakage},
        "complete_ending": {"passed": completion},
        "locked_endpoint": {
            "passed": all(endpoint_checks.values()),
            "checks": endpoint_checks,
        },
        "frozen_s02_compatibility": {
            "passed": all(continuity_checks.values()),
            "checks": continuity_checks,
        },
    }


def main() -> None:
    if hash_file(S02_PATH) != LOCKED_S02_HASH:
        raise ValueError("immutable S02 hash changed")
    scene = json.loads(COMPILED_SCENE.read_text(encoding="utf-8"))
    scene.update(
        {
            "target_words_min": 2800,
            "target_words_max": 3300,
            "pov": "Mara",
            "beat_markers": {
                "arrival_object": [r"\bsuitcase\b.{0,1200}\b(?:bakery box|buns?)\b", r"\b(?:bakery box|buns?)\b.{0,1200}\bsuitcase\b"],
                "status_blocking": [r"\b(?:hearth|fire|couch|bench|chairs?)\b.{0,1600}\b(?:circle|room|fellows?|people)\b"],
                "livia_accurate_read": [r"\bLivia\b.{0,1200}\b(?:father|afraid|want|arriv|seen|email)\w*\b"],
                "jonah_refusal": [r"\bJonah\b.{0,800}\b(?:No|No performance|won't read|refus|Ask her)\b"],
                "wrist_charge": [r"\bwrist\b.{0,700}\b(?:pulse|thumb|pressure|heat|skin)\b"],
                "mara_control": [r"\b(?:control|alter expression|changed the memory|dropped her shoulders|increased the contact|kept the bolt|different story)\b"],
                "public_miss": [r"\b(?:deviation|went quiet|blocked|dropped it|gone|wrong)\b"],
                "chosen_endpoint": [r"\b(?:ACCEPT PLACE|fellows[’'] house|room (?:key|credential)|if you[’']re staying)\b"],
            },
            "forbidden_claims": {
                "confirmed_supernatural": r"\b(?:proved|confirmed|certainly)\b.{0,60}\b(?:telepathy|supernatural|demon|magic)\b",
                "premature_romance": r"\b(?:love of her life|soulmate|marry him|in love with Jonah)\b",
            },
        }
    )
    pool = json.loads(POOL_PATH.read_text(encoding="utf-8"))
    source_texts = [
        (PROJECT_ROOT / donor["path"]).read_text(encoding="utf-8")
        for donor in pool["donors"].values()
    ]
    s02_text = S02_PATH.read_text(encoding="utf-8")
    summary = {
        "record_type": "S01AtomRewriteDeterministicSummary",
        "version": "s01-atom-rewrite-evaluation.v1",
        "immutable_s02_sha256": LOCKED_S02_HASH,
        "candidates": [],
    }
    for candidate_id, path in CANDIDATES.items():
        if not path.exists():
            raise FileNotFoundError(path)
        text = path.read_text(encoding="utf-8")
        report = evaluate_candidate(
            {"candidate_id": candidate_id, "text": text},
            scene,
            source_texts=source_texts,
        )
        extras = extra_gates(text)
        report["gate_details"].update(extras)
        report["hard_gates"].update(
            {name: bool(detail["passed"]) for name, detail in extras.items()}
        )
        report["eligible"] = all(report["hard_gates"].values())
        report["candidate_path"] = str(path.relative_to(PROJECT_ROOT))
        report["candidate_sha256"] = hash_file(path)
        report["integrated_s02_style_diagnostics"] = (
            integrated_style_discontinuity_diagnostics(text, s02_text)
        )
        output = EVALUATION_ROOT / "deterministic" / f"{candidate_id}.json"
        write_json(output, report)
        summary["candidates"].append(
            {
                "candidate_id": candidate_id,
                "path": str(path.relative_to(PROJECT_ROOT)),
                "sha256": hash_file(path),
                "words": word_count(text),
                "eligible": report["eligible"],
                "failed_gates": [
                    name for name, passed in report["hard_gates"].items() if not passed
                ],
                "cadence_hits_per_1000": report["literary_diagnostics"]["cadence_families"]["hits_per_1000_words"],
                "possible_explanatory_glosses": report["literary_diagnostics"]["explanatory_gloss"]["possible_explanatory_glosses"],
                "s01_s02_absolute_cadence_rate_difference": report[
                    "integrated_s02_style_diagnostics"
                ]["cadence_delta_per_1000_words"],
                "possible_s01_s02_style_discontinuity": report[
                    "integrated_s02_style_diagnostics"
                ]["possible_style_discontinuity"],
            }
        )
    write_json(EVALUATION_ROOT / "deterministic_summary.v1.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
