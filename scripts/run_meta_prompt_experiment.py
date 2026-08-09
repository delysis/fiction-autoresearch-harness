#!/usr/bin/env python3
"""Compile, run, or evaluate the 31B native-base meta-prompt experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fiction_harness.meta_prompting import (  # noqa: E402
    DEFAULT_SEEDS,
    compile_meta_prompt_experiment,
    evaluate_meta_prompt_outputs,
    measure_meta_prompt_contexts,
    run_meta_prompt_experiment,
)
from fiction_harness.model_client import LlamaClient  # noqa: E402
from fiction_harness.runtime import MODEL_PROFILES  # noqa: E402
from fiction_harness.shared_endpoint import SharedEndpointAdmission  # noqa: E402


DEFAULT_RUN = PROJECT_ROOT / "03_scene_lab/runs/s02-base-meta-prompt-v3"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("compile", "measure", "run", "evaluate"))
    parser.add_argument("--run-dir", default=str(DEFAULT_RUN))
    parser.add_argument("--url", default="http://127.0.0.1:8097")
    parser.add_argument("--arms", nargs="*", default=[])
    parser.add_argument("--seeds", nargs="*", type=int, default=[])
    parser.add_argument("--max-tokens", type=int, default=1500)
    parser.add_argument("--server-context-tokens", type=int, default=131072)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--no-admission", action="store_true")
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    if args.command == "compile":
        result = compile_meta_prompt_experiment(PROJECT_ROOT, run_dir)
    elif args.command in {"measure", "run"}:
        manifest = json.loads(
            (run_dir / "experiment_manifest.v1.json").read_text(encoding="utf-8")
        )
        arms = args.arms or [item["arm_id"] for item in manifest["arms"]]
        seeds = args.seeds or list(DEFAULT_SEEDS)
        client = LlamaClient(
            args.url,
            model=MODEL_PROFILES["base_31b_writer"].alias,
            timeout=7_200,
        )
        if not client.health():
            raise RuntimeError(f"31B base server is not healthy: {args.url}")
        if args.command == "measure":
            result = measure_meta_prompt_contexts(
                PROJECT_ROOT,
                run_dir,
                client=client,
                maximum_new_tokens=args.max_tokens,
                server_context_tokens=args.server_context_tokens,
            )
        else:
            result = run_meta_prompt_experiment(
                PROJECT_ROOT,
                run_dir,
                client=client,
                arm_ids=arms,
                seeds=seeds,
                maximum_new_tokens=args.max_tokens,
                server_context_tokens=args.server_context_tokens,
                concurrency=args.concurrency,
                admission=None if args.no_admission else SharedEndpointAdmission(),
            )
    else:
        result = evaluate_meta_prompt_outputs(PROJECT_ROOT, run_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
