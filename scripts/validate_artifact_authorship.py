#!/usr/bin/env python3
"""Validate a prose artifact's authorship record and promotion eligibility."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fiction_harness.authorship import validate_artifact_authorship  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", type=Path, required=True)
    parser.add_argument("--authorship", type=Path, required=True)
    parser.add_argument("--artifact-id", default="")
    parser.add_argument("--require-model-pipeline", action="store_true")
    args = parser.parse_args()
    record = json.loads(args.authorship.read_text(encoding="utf-8"))
    normalized = validate_artifact_authorship(
        record,
        text=args.text.read_text(encoding="utf-8"),
        artifact_id=args.artifact_id,
        require_model_pipeline=args.require_model_pipeline,
    )
    print(
        json.dumps(
            {
                "valid": True,
                "artifact_id": normalized["artifact_id"],
                "creation_kind": normalized["creation_kind"],
                "model_pipeline_eligible": normalized[
                    "model_pipeline_eligible"
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
