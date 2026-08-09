#!/usr/bin/env python3
"""Append runtime provenance attestations to completed historical calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fiction_harness.runtime import (
    TraceStore,
    model_runtime_provenance,
    utc_now,
)


def attest(root: Path) -> dict[str, Any]:
    files = sorted(root.rglob("calls.jsonl"))
    appended = 0
    skipped = 0
    unresolved: list[dict[str, str]] = []
    by_file: dict[str, int] = {}
    for calls_path in files:
        records = TraceStore.read(calls_path)
        attested = {
            str(record.get("call_id", ""))
            for record in records
            if record.get("status") == "runtime_attestation"
        }
        completed: dict[str, dict[str, Any]] = {}
        for record in records:
            call_id = str(record.get("call_id", ""))
            if call_id and record.get("status") == "completed":
                completed[call_id] = record
        added_here = 0
        for call_id, record in sorted(completed.items()):
            if call_id in attested:
                skipped += 1
                continue
            model = str(record.get("model", ""))
            runtime = model_runtime_provenance(model)
            if not runtime["model_blob"] or not runtime["llama_version"]:
                unresolved.append(
                    {
                        "calls_path": str(calls_path),
                        "call_id": call_id,
                        "model": model,
                    }
                )
            TraceStore._append(
                calls_path,
                {
                    "attested_at": utc_now(),
                    "call_id": call_id,
                    "model": model,
                    "prompt_hash": str(record.get("prompt_hash", "")),
                    "runtime": runtime,
                    "status": "runtime_attestation",
                },
            )
            appended += 1
            added_here += 1
        by_file[str(calls_path)] = added_here
    return {
        "root": str(root),
        "call_files": len(files),
        "appended": appended,
        "already_attested": skipped,
        "unresolved": unresolved,
        "by_file": by_file,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_root", type=Path)
    args = parser.parse_args()
    print(json.dumps(attest(args.run_root), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
