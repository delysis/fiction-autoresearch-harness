#!/usr/bin/env python3
"""Compile, run, or evaluate the native-31B long-context calibration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fiction_harness.long_context import (  # noqa: E402
    build_long_context_anti_copy_index,
    compile_experiment,
    evaluate_experiment,
    run_experiment,
)
from fiction_harness.model_client import LlamaClient  # noqa: E402
from fiction_harness.runtime import MODEL_PROFILES  # noqa: E402
from fiction_harness.shared_endpoint import SharedEndpointAdmission  # noqa: E402


DEFAULT_RUN = ROOT / "03_scene_lab/runs/s03-long-context-base-v5"
DEFAULT_MANUSCRIPT = (
    ROOT / "03_scene_lab/runs/s01-atom-rewrite-v1/selected/s01-s02.codex.v2.md"
)
DEFAULT_GUIDE = Path(
    "/Users/george/.codex/attachments/d88a67cd-a639-4fba-80d6-b30acc0a4d22/pasted-text.txt"
)
DEFAULT_CRAFT = ROOT / "04_review_governance/gabaldon_intimacy_craft_distillation_v1.md"


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("phase", choices=("compile", "run", "evaluate", "all"))
    value.add_argument("--run-root", type=Path, default=DEFAULT_RUN)
    value.add_argument("--manuscript", type=Path, default=DEFAULT_MANUSCRIPT)
    value.add_argument("--guide", type=Path, default=DEFAULT_GUIDE)
    value.add_argument("--craft", type=Path, default=DEFAULT_CRAFT)
    value.add_argument("--server-url", default="http://127.0.0.1:8097")
    value.add_argument(
        "--model-role",
        choices=("base_31b_writer", "base_31b_writer_full"),
        default="base_31b_writer",
    )
    value.add_argument("--seed", action="append", type=int, default=None)
    value.add_argument("--arm", action="append", default=None)
    value.add_argument("--max-new-candidates", type=int)
    value.add_argument("--max-retries", type=int, default=2)
    value.add_argument("--max-tokens", type=int, default=1700)
    value.add_argument("--timeout", type=float, default=3600)
    value.add_argument("--no-admission", action="store_true")
    return value


def main() -> int:
    args = parser().parse_args()
    if args.phase in {"compile", "all"}:
        result = compile_experiment(
            run_root=args.run_root,
            manuscript_path=args.manuscript,
            guide_path=args.guide,
            craft_distillation_path=args.craft,
        )
        print(json.dumps({"manifest_hash": result["manifest_hash"], "arms": len(result["arms"])}, indent=2))
    if args.phase in {"run", "all"}:
        manuscript = args.manuscript.read_text(encoding="utf-8")
        guide = args.guide.read_text(encoding="utf-8")
        anti_copy = build_long_context_anti_copy_index(
            manuscript=manuscript,
            guide_text=guide,
            extra_sources={"craft-distillation": args.craft.read_text(encoding="utf-8")},
        )
        client = LlamaClient(
            args.server_url,
            model=MODEL_PROFILES[args.model_role].alias,
            timeout=args.timeout,
        )
        if not client.health():
            raise RuntimeError("31B-base server is not healthy")
        records = run_experiment(
            client=client,
            run_root=args.run_root,
            seeds=tuple(args.seed or (83101,)),
            anti_copy_index=anti_copy,
            max_tokens=args.max_tokens,
            arm_ids=tuple(args.arm or ()),
            max_new_candidates=args.max_new_candidates,
            max_retries=args.max_retries,
            admission=None if args.no_admission else SharedEndpointAdmission(),
        )
        print(json.dumps({"completed": len(records), "candidate_ids": [item["candidate_id"] for item in records]}, indent=2))
    if args.phase in {"evaluate", "all"}:
        report = evaluate_experiment(run_root=args.run_root)
        print(json.dumps({"candidate_count": report["candidate_count"], "output": str(args.run_root / "evaluation/calibration_report.v1.json")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
