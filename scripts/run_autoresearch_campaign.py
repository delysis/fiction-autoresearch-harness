#!/usr/bin/env python3
"""Cache-affine concurrent launcher for one frozen autoresearch round."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-dir", required=True)
    parser.add_argument("--round", type=int, choices=(1, 2, 3), required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--url", default="http://127.0.0.1:8097")
    parser.add_argument("--max-tokens", type=int, default=2000)
    args = parser.parse_args()

    root = Path(args.campaign_dir)
    campaign = json.loads(
        (root / "campaign_manifest.v1.json").read_text(encoding="utf-8")
    )
    if args.round == 1:
        recipes = [item["recipe_id"] for item in campaign["recipes"]]
    else:
        recipe_set = json.loads(
            (root / f"round-{args.round}" / "recipes.v1.json").read_text(
                encoding="utf-8"
            )
        )
        recipes = [item["recipe_id"] for item in recipe_set["recipes"]]
    benchmarks = json.loads(
        Path(campaign["benchmarks_path"]).read_text(encoding="utf-8")
    )
    cells = [item["cell_id"] for item in benchmarks["cells"]]
    if args.round == 2:
        cells = [
            item
            for item in cells
            if item in {"married-explicit", "institutional-pressure-control"}
        ]
    seeds = campaign["round_seeds"][str(args.round)]

    def run_seed(recipe: str, cell: str, seed: int) -> tuple[str, int, str]:
        command = [
            sys.executable,
            "-m",
            "fiction_harness",
            "autoresearch",
            "round",
            "run",
            "--campaign-dir",
            str(root),
            "--round",
            str(args.round),
            "--url",
            args.url,
            "--max-tokens",
            str(args.max_tokens),
            "--only-recipe",
            recipe,
            "--only-cell",
            cell,
            "--only-seed",
            str(seed),
            "--limit",
            "1",
        ]
        result = subprocess.run(
            command,
            cwd=Path(__file__).resolve().parent.parent,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        return f"{recipe}/{cell}/{seed}", result.returncode, result.stdout

    failures = []
    # Group identical prompts together. Three seeds share prefix work; prompt
    # groups themselves stay sequential to avoid cold-prefix cache thrash.
    for recipe in recipes:
        for cell in cells:
            with ThreadPoolExecutor(max_workers=min(args.workers, len(seeds))) as pool:
                futures = [pool.submit(run_seed, recipe, cell, int(seed)) for seed in seeds]
                for future in as_completed(futures):
                    coordinate, code, output = future.result()
                    print(f"[{coordinate}] exit={code}")
                    if output.strip():
                        print(output.rstrip())
                    if code:
                        failures.append(coordinate)
            if failures:
                print("Stopping after failed prompt group: " + ", ".join(failures))
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
