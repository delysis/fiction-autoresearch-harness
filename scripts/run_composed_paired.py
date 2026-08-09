#!/usr/bin/env python3
"""Run the three-movement paired-ICL realization prototype."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fiction_harness.composed_realization import run_composed_realization  # noqa: E402
from fiction_harness.model_client import LlamaClient  # noqa: E402
from fiction_harness.runtime import MODEL_PROFILES  # noqa: E402
from fiction_harness.shared_endpoint import SharedEndpointAdmission  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=ROOT / "03_scene_lab/runs/s02-paired-composed-production-v9",
    )
    parser.add_argument("--url", default="http://127.0.0.1:8097")
    parser.add_argument("--attempts-per-segment", type=int, default=4)
    parser.add_argument("--max-tokens", type=int, default=750)
    parser.add_argument("--seed-start", type=int, default=914_001)
    parser.add_argument(
        "--slot-id",
        type=int,
        default=0,
        help="Pin the cache-affine composed sequence to one llama.cpp slot.",
    )
    parser.add_argument("--reference-arm", default="paired-icl-16k")
    parser.add_argument("--archive-case-count", type=int, default=1)
    parser.add_argument(
        "--demonstration-profile",
        choices=(
            "heterogeneous-public-domain-v1",
            "s01-variants-v1",
            "mixed-heterogeneous-project-nearest-v1",
        ),
        default="s01-variants-v1",
    )
    parser.add_argument(
        "--stop-after-segments",
        type=int,
        choices=(1, 2, 3),
        help="Commit a resumable checkpoint after this many selected segments.",
    )
    parser.add_argument(
        "--promotion-manifest",
        type=Path,
        help="Hash-locked promoted parent movements to import before generation.",
    )
    parser.add_argument(
        "--collect-next-segment-pool",
        action="store_true",
        help="Generate every attempt for the first missing segment and stop before selection.",
    )
    args = parser.parse_args()
    attempts = args.attempts_per_segment * 3
    seeds = [args.seed_start + 18 * index for index in range(attempts)]
    client = LlamaClient(
        args.url,
        model=MODEL_PROFILES["base_31b_writer"].alias,
        timeout=7_200,
    )
    if not client.health():
        raise RuntimeError("shared 31B base endpoint is not healthy")
    result = run_composed_realization(
        ROOT,
        args.run_dir.resolve(),
        client=client,
        seeds=seeds,
        attempts_per_segment=args.attempts_per_segment,
        maximum_new_tokens=args.max_tokens,
        admission=SharedEndpointAdmission(),
        slot_id=args.slot_id,
        reference_arm_id=args.reference_arm,
        stop_after_segments=args.stop_after_segments,
        archive_case_count=args.archive_case_count,
        demonstration_profile=args.demonstration_profile,
        promotion_manifest_path=(
            args.promotion_manifest.resolve() if args.promotion_manifest else None
        ),
        collect_next_segment_pool=args.collect_next_segment_pool,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
