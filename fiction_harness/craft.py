"""Versioned intimacy-craft profiles for generation and editorial evaluation.

The bundled profile distills general craft principles from Diana Gabaldon's
``I Give You My Body``.  It intentionally contains no example passages and no
instruction to imitate Gabaldon's prose style.  The goal is transferable scene
craft: emotional transaction, character-specific embodiment, selective
sensation, atmosphere, dialogue, and consequential restraint.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


PROFILE_DIR = Path(__file__).with_name("craft_profiles")
DEFAULT_PROFILE_PATH = PROFILE_DIR / "gabaldon_intimacy_v1.json"


def load_craft_profile(path: str | Path | None = None) -> dict[str, Any]:
    """Load and minimally validate a versioned craft profile."""

    profile_path = Path(path) if path else DEFAULT_PROFILE_PATH
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    required = {
        "profile_id",
        "schema_version",
        "principles",
        "generation_contract",
        "judge_diagnostics",
        "defect_taxonomy",
    }
    missing = required - set(profile)
    if missing:
        raise ValueError(f"Craft profile is missing required keys: {sorted(missing)}")
    if not profile["principles"] or not profile["generation_contract"]:
        raise ValueError("Craft profile principles and generation contract cannot be empty")
    return profile


def _lines(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value) for value in values]


def render_craft_prompt(
    profile: Mapping[str, Any] | None = None,
    *,
    mode: str = "generation",
) -> str:
    """Render a compact prompt module for generators, planners, or editors."""

    data = dict(profile or load_craft_profile())
    if mode not in {"generation", "planning", "editorial"}:
        raise ValueError(f"Unknown craft-prompt mode: {mode}")
    lines = [
        f"<INTIMACY_CRAFT_PROFILE id=\"{data['profile_id']}\" mode=\"{mode}\">",
        "Use these as scene-engineering principles, not as a prose-style imitation.",
    ]
    lines.extend(f"- {item}" for item in _lines(data["principles"]))
    contract_key = {
        "generation": "generation_contract",
        "planning": "planning_contract",
        "editorial": "editor_contract",
    }[mode]
    lines.append(f"{mode.upper()} CONTRACT")
    lines.extend(f"- {item}" for item in _lines(data.get(contract_key, ())))
    if mode in {"generation", "planning"} and isinstance(
        data.get("s01_application"), Mapping
    ):
        lines.append("S01 APPLICATION")
        for key, value in data["s01_application"].items():
            if isinstance(value, list):
                lines.append(f"- {key}: " + "; ".join(str(item) for item in value))
            else:
                lines.append(f"- {key}: {value}")
    lines.append("</INTIMACY_CRAFT_PROFILE>")
    return "\n".join(lines)


def render_judge_overlay(profile: Mapping[str, Any] | None = None) -> str:
    """Render the craft diagnostics and defect IDs for an editorial judge."""

    data = dict(profile or load_craft_profile())
    lines = [
        f"INTIMACY CRAFT OVERLAY ({data['profile_id']})",
        "These diagnostics are non-weighted unless an axis explicitly invokes them.",
    ]
    for name, diagnostic in data["judge_diagnostics"].items():
        lines.append(f"- {name}: {diagnostic}")
    lines.append("Craft defects:")
    for name, description in data["defect_taxonomy"].items():
        lines.append(f"- {name}: {description}")
    return "\n".join(lines)
