#!/usr/bin/env python3
"""Measure aggregate native-base throughput at increasing request concurrency."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fiction_harness.core import sha256_text, write_json  # noqa: E402
from fiction_harness.model_client import LlamaClient  # noqa: E402
from fiction_harness.runtime import MODEL_PROFILES  # noqa: E402


DEFAULT_PROMPT = (
    PROJECT_ROOT
    / "03_scene_lab/runs/s02-base-meta-prompt-v3/prompts/short-control-4k.txt"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "03_scene_lab/runs/runtime-benchmarks/shared-base31.v1.json"
)


def _one(
    *,
    url: str,
    prompt: str,
    seed: int,
    maximum_new_tokens: int,
    timeout: float,
) -> dict[str, object]:
    client = LlamaClient(
        url,
        model=MODEL_PROFILES["base_31b_writer"].alias,
        timeout=timeout,
    )
    result = client.complete_raw(
        prompt=prompt,
        seed=seed,
        max_tokens=maximum_new_tokens,
        temperature=0.95,
        top_p=0.97,
        min_p=0.02,
        xtc_probability=0.08,
        stop=("\n#", "\n<"),
    )
    completion_tokens = int(result.usage.get("completion_tokens", 0) or 0)
    return {
        "seed": seed,
        "completion_tokens": completion_tokens,
        "elapsed_seconds": result.elapsed_seconds,
        "tokens_per_second": (
            completion_tokens / result.elapsed_seconds
            if result.elapsed_seconds > 0
            else 0.0
        ),
        "finish_reason": result.finish_reason,
        "timings": result.timings,
        "cache": result.cache,
        "content_hash": sha256_text(result.content),
    }


def benchmark_level(
    *,
    url: str,
    prompt: str,
    seeds: list[int],
    concurrency: int,
    maximum_new_tokens: int,
    timeout: float,
) -> dict[str, object]:
    started = time.monotonic()
    records: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(
                _one,
                url=url,
                prompt=prompt,
                seed=seed,
                maximum_new_tokens=maximum_new_tokens,
                timeout=timeout,
            )
            for seed in seeds
        ]
        for future in as_completed(futures):
            records.append(future.result())
    wall = time.monotonic() - started
    records.sort(key=lambda item: int(item["seed"]))
    total_tokens = sum(int(item["completion_tokens"]) for item in records)
    return {
        "concurrency": concurrency,
        "requests": len(records),
        "wall_seconds": wall,
        "total_completion_tokens": total_tokens,
        "aggregate_tokens_per_second": total_tokens / wall if wall > 0 else 0.0,
        "mean_request_seconds": statistics.fmean(
            float(item["elapsed_seconds"]) for item in records
        ),
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8097")
    parser.add_argument("--prompt", default=str(DEFAULT_PROMPT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--concurrency", nargs="+", type=int, default=[1, 2, 4])
    parser.add_argument("--requests", type=int, default=4)
    parser.add_argument("--max-tokens", type=int, default=192)
    parser.add_argument("--timeout", type=float, default=3600.0)
    args = parser.parse_args()
    if args.requests < 1 or any(value < 1 for value in args.concurrency):
        raise ValueError("requests and concurrency must be positive")
    prompt_path = Path(args.prompt)
    prompt = prompt_path.read_text(encoding="utf-8")
    health = LlamaClient(
        args.url,
        model=MODEL_PROFILES["base_31b_writer"].alias,
        timeout=30,
    )
    if not health.health():
        raise RuntimeError(f"shared endpoint is not healthy: {args.url}")
    seeds = [990_001 + 18 * index for index in range(args.requests)]
    levels = [
        benchmark_level(
            url=args.url,
            prompt=prompt,
            seeds=seeds,
            concurrency=value,
            maximum_new_tokens=args.max_tokens,
            timeout=args.timeout,
        )
        for value in args.concurrency
    ]
    baseline = float(levels[0]["aggregate_tokens_per_second"])
    for level in levels:
        level["throughput_gain_vs_first"] = (
            float(level["aggregate_tokens_per_second"]) / baseline
            if baseline > 0
            else 0.0
        )
    result = {
        "record_type": "SharedEndpointBenchmark",
        "version": "shared-base31.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": args.url,
        "server_contract": {
            "model": MODEL_PROFILES["base_31b_writer"].alias,
            "trained_context_tokens": 262_144,
            "allocated_context_tokens": 131_072,
            "parallel_slots": 4,
            "continuous_batching": True,
            "kv_cache": "q8_0",
            "gpu_layers": "all",
            "unified_kv": True,
        },
        "prompt_path": str(prompt_path),
        "prompt_hash": sha256_text(prompt),
        "maximum_new_tokens": args.max_tokens,
        "same_seeds_at_every_level": seeds,
        "levels": levels,
    }
    write_json(Path(args.output), result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
