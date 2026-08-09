"""Compile the trusted project reads into deterministic generation artifacts."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping
from xml.etree import ElementTree
from zipfile import ZipFile

from .core import (
    atomic_write_text,
    canonical_json_text,
    hash_file,
    hash_json,
    sha256_text,
    stable_prefix,
    write_json,
)
from .schemas import PersonaPacket, SCHEMA_VERSION, SceneSpec
from .ontology import (
    ResolvedCreativeProfile,
    load_ontology,
    load_scene_profile,
    load_story_profile,
    profile_prompt_text,
    resolve_profiles,
    write_resolved_profile,
)


COMPILER_VERSION = "trusted-read-compiler.v1"
DEFAULT_CONFIG = Path("config/compilation.v1.json")
_BLOCK_RE = re.compile(r"^\[(P\d+)\s*\|[^\]]+\]\n(.*?)(?=^\[P\d+\s*\||\Z)", re.M | re.S)
_CARD_HEADING_RE = re.compile(r"^((?:MPC|LEV)-\d{2})\s+—\s+(.+)$")
_SOURCE_ID_RE = re.compile(r"\b(?:MPC|LEV)-\d{2}\b")
_SCENE_HEADING_RE = re.compile(r"^(S\d{2})\s+—\s+(.+)$")
_DOCX_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@dataclass(frozen=True, slots=True)
class CompilationResult:
    output_dir: Path
    manifest_path: Path
    stable_prefix_path: Path
    scene_path: Path
    persona_path: Path
    source_packet_path: Path
    manifest_hash: str
    stable_prefix_hash: str
    resolved_profile_path: Path | None = None


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _trusted_blocks(text: str) -> list[str]:
    """Extract visible paragraph contents from a trusted-read Markdown file."""

    blocks: list[str] = []
    for match in _BLOCK_RE.finditer(text.replace("\r\n", "\n").replace("\r", "\n")):
        value = match.group(2).strip()
        if value and value != "⟦EMPTY PARAGRAPH⟧":
            blocks.append(value)
    if not blocks:
        raise ValueError("trusted-read document contains no paragraph blocks")
    return blocks


def _read_docx_text(path: Path) -> str:
    """Extract DOCX paragraph text in document order using only the stdlib."""

    with ZipFile(path) as archive:
        document_xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(document_xml)
    paragraphs: list[str] = []
    for paragraph in root.iter(f"{_DOCX_NS}p"):
        fragments: list[str] = []
        for node in paragraph.iter():
            if node.tag == f"{_DOCX_NS}t" and node.text:
                fragments.append(node.text)
            elif node.tag == f"{_DOCX_NS}tab":
                fragments.append("\t")
            elif node.tag in {f"{_DOCX_NS}br", f"{_DOCX_NS}cr"}:
                fragments.append("\n")
        text = "".join(fragments).strip()
        if text:
            paragraphs.append(text)
    if not paragraphs:
        raise ValueError(f"DOCX has no readable paragraphs: {path}")
    return "\n\n".join(paragraphs) + "\n"


def _document_text(path: Path, source_format: str) -> str:
    if source_format == "trusted-read-markdown":
        raw = path.read_text(encoding="utf-8")
        return "\n\n".join(_trusted_blocks(raw)) + "\n"
    if source_format == "docx":
        return _read_docx_text(path)
    if source_format in {"markdown", "text"}:
        return path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    raise ValueError(f"unsupported source format: {source_format}")


def _corpus_artifact(
    *,
    project_root: Path,
    document_key: str,
    source_path: Path,
    source_format: str,
    title: str,
) -> dict[str, Any]:
    text = _document_text(source_path, source_format)
    return {
        "artifact_type": "TrustedDocument",
        "schema_version": SCHEMA_VERSION,
        "compiler_version": COMPILER_VERSION,
        "document_key": document_key,
        "title": title,
        "source_path": source_path.relative_to(project_root).as_posix(),
        "source_format": source_format,
        "raw_sha256": hash_file(source_path),
        "text_sha256": sha256_text(text),
        "text": text,
    }


def _find_after(blocks: list[str], label: str, start: int, stop: int) -> str:
    for index in range(start, stop - 1):
        if blocks[index] == label:
            return blocks[index + 1]
    raise ValueError(f"missing scene-card field: {label}")


def parse_scene_spec(scene_text: str, canon_text: str, scene_id: str = "S01") -> SceneSpec:
    """Parse a scene card while retaining its source and continuity constraints."""

    blocks = _trusted_blocks(scene_text)
    heading_index = next(
        (
            index
            for index, block in enumerate(blocks)
            if (match := _SCENE_HEADING_RE.match(block)) and match.group(1) == scene_id
        ),
        None,
    )
    if heading_index is None:
        raise ValueError(f"scene {scene_id} not found")
    heading_match = _SCENE_HEADING_RE.match(blocks[heading_index])
    assert heading_match is not None
    stop = next(
        (
            index
            for index in range(heading_index + 1, len(blocks))
            if _SCENE_HEADING_RE.match(blocks[index])
        ),
        len(blocks),
    )
    metadata = blocks[heading_index + 1]
    metadata_match = re.search(
        r"Function:\s*(.*?)\s*•\s*POV:\s*(.*?)\s*•\s*Target length:\s*"
        r"([\d,]+)[–-]([\d,]+)\s+words",
        metadata,
    )
    if metadata_match is None:
        raise ValueError(f"could not parse scene metadata: {metadata}")

    beat_heading = blocks.index("Beat map", heading_index, stop)
    continuity_heading = blocks.index("Continuity facts created or tested", beat_heading, stop)
    beat_map = tuple(
        match.group(1).strip()
        for block in blocks[beat_heading + 1 : continuity_heading]
        if (match := re.match(r"^\d+\.\s*(.+)$", block))
    )
    continuity = tuple(blocks[continuity_heading + 1 : stop])
    pressure = tuple(
        item.strip()
        for item in re.split(r"\s*→\s*", _find_after(blocks, "Pressure ladder", heading_index, beat_heading))
        if item.strip()
    )
    source_ids = tuple(
        _SOURCE_ID_RE.findall(_find_after(blocks, "Source packet", heading_index, beat_heading))
    )

    canon_blocks = _trusted_blocks(canon_text)
    heat_ceiling = next(
        (
            block
            for block in canon_blocks
            if block.startswith("Maximum on-page erotic charge without graphic sex acts")
        ),
        None,
    )
    if heat_ceiling is None:
        raise ValueError("working heat ceiling was not found in the canon")

    default_pacing = {
        "S01": (
            "0–10% arrival and hook",
            "10–25% Fulcrum enchantment",
            "25–45% Livia's uncanny reads",
            "45–65% wrist-contact exercise and erotic charge",
            "65–82% Mara's control",
            "82–94% partial collapse and residual mystery",
            "94–100% Jonah's recognition, Mara's decision, and chapter hook",
        ),
        "S02": (
            "0–10% exhausted late-night care",
            "10–30% observation slides into interpretation",
            "30–50% explanations and loaded prompts tighten the trap",
            "50–68% romantic triangulation and project threat",
            "68–82% Mara's silence and clean question",
            "82–92% Miriam opens the exit",
            "92–100% Jonah's restrained walk home and doorway rule",
        ),
        "S03": (
            "0–12% vigil beauty and technical urgency",
            "12–35% incompatible observations accumulate",
            "35–58% shared image becomes accusation",
            "58–76% Mara builds the observation ledger",
            "76–90% witnesses, confession, and protocol break",
            "90–100% public remainder and transformed institution",
        ),
    }
    return SceneSpec(
        scene_id=scene_id,
        title=heading_match.group(2).strip(),
        function=metadata_match.group(1).strip(),
        pov=metadata_match.group(2).strip(),
        target_words_min=int(metadata_match.group(3).replace(",", "")),
        target_words_max=int(metadata_match.group(4).replace(",", "")),
        opening_image=_find_after(blocks, "Opening image", heading_index, beat_heading),
        desire=_find_after(blocks, "Desire", heading_index, beat_heading),
        obstacle=_find_after(blocks, "Obstacle", heading_index, beat_heading),
        pressure_ladder=pressure,
        turn=_find_after(blocks, "Turn", heading_index, beat_heading),
        aftermath=_find_after(blocks, "Aftermath", heading_index, beat_heading),
        teaching_payload=_find_after(blocks, "Teaching payload", heading_index, beat_heading),
        source_ids=source_ids,
        beat_map=beat_map,
        continuity_facts=continuity,
        heat_ceiling=heat_ceiling,
        pacing_targets=default_pacing.get(scene_id, ()),
    )


def parse_source_cards(source_text: str) -> dict[str, dict[str, Any]]:
    """Parse all MPC and LEV source cards from the trusted-read deck."""

    blocks = _trusted_blocks(source_text)
    headings = [
        (index, match.group(1), match.group(2).strip())
        for index, block in enumerate(blocks)
        if (match := _CARD_HEADING_RE.match(block))
    ]
    cards: dict[str, dict[str, Any]] = {}
    labels = {"Role", "Evidence", "Extracted dynamic", "Dramatic use", "Transformation", "Source"}
    for position, (start, source_id, title) in enumerate(headings):
        stop = headings[position + 1][0] if position + 1 < len(headings) else len(blocks)
        values: dict[str, str] = {}
        for index in range(start + 1, stop - 1):
            label = blocks[index]
            if label in labels:
                values[label] = blocks[index + 1]
        mechanism = values.get("Evidence") or values.get("Extracted dynamic")
        if not mechanism:
            raise ValueError(f"{source_id} has no evidence or extracted dynamic")
        cards[source_id] = {
            "source_id": source_id,
            "title": title,
            "role": values.get("Role", ""),
            "evidence_or_dynamic": mechanism,
            "dramatic_use": values.get("Dramatic use", ""),
            "transformation": values.get("Transformation", ""),
            "source": values.get("Source", ""),
        }
    if len(cards) != 30:
        raise ValueError(f"expected 30 source cards, found {len(cards)}")
    return cards


def _load_personas(path: Path) -> tuple[PersonaPacket, ...]:
    raw = _read_json(path)
    records = raw.get("personas") if isinstance(raw, Mapping) else None
    if not isinstance(records, list) or not records:
        raise ValueError("persona fixture must contain a non-empty personas array")
    personas = tuple(PersonaPacket.from_dict(record) for record in records)
    identifiers = [persona.persona_id for persona in personas]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("persona fixture contains duplicate persona IDs")
    return personas


def _artifact_entry(output_dir: Path, path: Path) -> dict[str, str]:
    return {
        "path": path.relative_to(output_dir).as_posix(),
        "sha256": hash_file(path),
    }


def compile_trusted_sources(
    project_root: str | Path,
    output_dir: str | Path,
    *,
    config_path: str | Path | None = None,
    ontology_path: str | Path | None = None,
    story_profile_path: str | Path | None = None,
    scene_profile_path: str | Path | None = None,
) -> CompilationResult:
    """Compile one selected scene and its generation corpus into JSON artifacts.

    ``output_dir`` may be safely reused: deterministic artifacts are atomically
    replaced, while unrelated files are left untouched.
    """

    root = Path(project_root).resolve()
    destination = Path(output_dir).resolve()
    selected_config = Path(config_path).resolve() if config_path else root / DEFAULT_CONFIG
    config = _read_json(selected_config)
    if config.get("compiler_version") != COMPILER_VERSION:
        raise ValueError(
            f"config compiler_version must be {COMPILER_VERSION!r}; "
            f"got {config.get('compiler_version')!r}"
        )

    corpus: dict[str, dict[str, Any]] = {}
    for source in config["documents"]:
        source_path = root / source["path"]
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        artifact = _corpus_artifact(
            project_root=root,
            document_key=source["key"],
            source_path=source_path,
            source_format=source["format"],
            title=source["title"],
        )
        corpus[source["key"]] = artifact

    scene_raw = (root / config["scene_trusted_read"]).read_text(encoding="utf-8")
    canon_raw = (root / config["canon_trusted_read"]).read_text(encoding="utf-8")
    source_raw = (root / config["source_trusted_read"]).read_text(encoding="utf-8")
    scene = parse_scene_spec(scene_raw, canon_raw, config["scene_id"])
    overrides = config.get("scene_overrides", {})
    if overrides:
        if not isinstance(overrides, Mapping):
            raise TypeError("scene_overrides must be an object")
        allowed_overrides = {
            "target_words_min",
            "target_words_max",
            "pacing_targets",
            "continuity_facts_append",
        }
        unknown_overrides = sorted(set(overrides) - allowed_overrides)
        if unknown_overrides:
            raise ValueError(
                "unknown scene_overrides: " + ", ".join(unknown_overrides)
            )
        continuity = scene.continuity_facts + tuple(
            str(item)
            for item in overrides.get("continuity_facts_append", ())
        )
        scene = replace(
            scene,
            target_words_min=int(
                overrides.get("target_words_min", scene.target_words_min)
            ),
            target_words_max=int(
                overrides.get("target_words_max", scene.target_words_max)
            ),
            pacing_targets=tuple(
                str(item)
                for item in overrides.get(
                    "pacing_targets", scene.pacing_targets
                )
            ),
            continuity_facts=continuity,
        )
    all_cards = parse_source_cards(source_raw)
    missing_ids = [source_id for source_id in scene.source_ids if source_id not in all_cards]
    if missing_ids:
        raise ValueError(f"scene references unknown source IDs: {', '.join(missing_ids)}")
    source_packet = {
        "artifact_type": "SourcePacket",
        "schema_version": SCHEMA_VERSION,
        "compiler_version": COMPILER_VERSION,
        "scene_id": scene.scene_id,
        "source_ids": list(scene.source_ids),
        "cards": [all_cards[source_id] for source_id in scene.source_ids],
    }
    source_packet["packet_hash"] = hash_json(source_packet)

    resolved_profile: ResolvedCreativeProfile | None = None
    resolved_profile_path: Path | None = None
    if scene_profile_path is not None and story_profile_path is None:
        raise ValueError("scene_profile_path requires story_profile_path")
    if story_profile_path is not None:
        if ontology_path is None:
            raise ValueError("story_profile_path requires ontology_path")
        catalog = load_ontology(ontology_path)
        story_layers = load_story_profile(story_profile_path)
        creative_scene = (
            load_scene_profile(scene_profile_path)
            if scene_profile_path is not None
            else None
        )
        resolved_profile = resolve_profiles(catalog, story_layers, creative_scene)
        if resolved_profile.scene_id not in {"STORY", scene.scene_id}:
            raise ValueError(
                f"resolved profile is for {resolved_profile.scene_id}, "
                f"compiled scene is {scene.scene_id}"
            )

    personas = _load_personas(root / config["persona_fixture"])
    persona_bundle = {
        "artifact_type": "PersonaBundle",
        "schema_version": SCHEMA_VERSION,
        "compiler_version": COMPILER_VERSION,
        "personas": [persona.to_dict() for persona in personas],
    }
    persona_bundle["bundle_hash"] = hash_json(persona_bundle)

    corpus_dir = destination / "corpus"
    corpus_paths: list[Path] = []
    for key, artifact in sorted(corpus.items()):
        path = corpus_dir / f"{key}.v1.json"
        write_json(path, artifact)
        corpus_paths.append(path)
    scene_path = destination / "scene_specs" / f"{scene.scene_id.lower()}.v1.json"
    persona_path = destination / "personas" / "fulcrum_pilot.v1.json"
    source_packet_path = (
        destination
        / "sources"
        / f"{scene.scene_id.lower()}_source_packet.v1.json"
    )
    write_json(scene_path, scene.to_dict())
    write_json(persona_path, persona_bundle)
    write_json(source_packet_path, source_packet)

    prompt_sections: list[tuple[str, str]] = []
    if resolved_profile is not None:
        resolved_profile_path = (
            destination / "profiles" / "resolved_profile.v1.json"
        )
        write_resolved_profile(resolved_profile_path, resolved_profile)
        prompt_sections.append(
            ("resolved_creative_profile", profile_prompt_text(resolved_profile))
        )
    prompt_sections.extend([
        ("project_brief", corpus["project_brief"]["text"]),
        ("story_canon", corpus["story_canon"]["text"]),
        ("source_packet", canonical_json_text(source_packet)),
        ("persona_bundle", canonical_json_text(persona_bundle)),
        ("scene_spec", canonical_json_text(scene.to_dict())),
    ])
    prefix_text = stable_prefix(prompt_sections)
    prefix_path = destination / "stable_prefix.txt"
    atomic_write_text(prefix_path, prefix_text)

    artifact_paths = [
        *corpus_paths,
        scene_path,
        persona_path,
        source_packet_path,
        prefix_path,
    ]
    if resolved_profile_path is not None:
        artifact_paths.append(resolved_profile_path)
    source_entries = [
        {
            "key": key,
            "path": artifact["source_path"],
            "raw_sha256": artifact["raw_sha256"],
            "text_sha256": artifact["text_sha256"],
        }
        for key, artifact in sorted(corpus.items())
    ]
    manifest = {
        "artifact_type": "CompilationManifest",
        "schema_version": SCHEMA_VERSION,
        "compiler_version": COMPILER_VERSION,
        "scene_id": scene.scene_id,
        "config_path": selected_config.relative_to(root).as_posix(),
        "config_sha256": hash_file(selected_config),
        "sources": source_entries,
        "artifacts": [_artifact_entry(destination, path) for path in artifact_paths],
        "stable_prefix_sha256": sha256_text(prefix_text),
    }
    if resolved_profile is not None:
        manifest["creative_profile"] = {
            "ontology_version": resolved_profile.ontology_version,
            "ontology_hash": resolved_profile.ontology_hash,
            "story_profile_id": resolved_profile.story_profile_id,
            "scene_profile_id": resolved_profile.scene_profile_id,
            "resolved_profile_hash": resolved_profile.profile_hash,
            "resolved_profile_path": resolved_profile_path.relative_to(
                destination
            ).as_posix(),
        }
    manifest["manifest_hash"] = hash_json(manifest)
    manifest_path = destination / "manifest.v1.json"
    write_json(manifest_path, manifest)
    return CompilationResult(
        output_dir=destination,
        manifest_path=manifest_path,
        stable_prefix_path=prefix_path,
        scene_path=scene_path,
        persona_path=persona_path,
        source_packet_path=source_packet_path,
        manifest_hash=manifest["manifest_hash"],
        stable_prefix_hash=manifest["stable_prefix_sha256"],
        resolved_profile_path=resolved_profile_path,
    )
