"""Provenance-rich retrieval and long-context apprenticeship prompt compiler.

The compiler treats a base-model prompt as a deliberately sampled literary
distribution.  It retrieves complete scene-like passages by both content and
craft geometry, packs them under an explicit token budget, and preserves a
plain manuscript runway as the final bytes of the prompt.
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterable, Mapping, Sequence
from urllib.request import Request, urlopen

from .core import atomic_write_text, hash_file, hash_json, sha256_text, write_json


APPRENTICESHIP_VERSION = "literary-apprenticeship.v1"
ALLOWED_PARTITIONS = frozenset({"profiling", "calibration", "holdout"})
WORD_RE = re.compile(r"\b[\w’'-]+\b", re.UNICODE)


ROMANCE_TERMS = re.compile(
    r"\b(?:love|desire|want|kiss|touch|marry|marriage|husband|wife|lover|"
    r"jealous|admire|attract|embrace|mouth|breast|thigh|body|naked|bed|"
    r"tender|passion|pleasure|refus|consent|choose|wait)\w*\b", re.I
)
CONFLICT_TERMS = re.compile(
    r"\b(?:refus|deny|argu|angry|fear|risk|threat|demand|secret|lie|"
    r"betray|choice|decid|must|cannot|won't|wouldn't|danger|pressure)\w*\b",
    re.I,
)
AGENCY_TERMS = re.compile(
    r"\b(?:ask|answer|choose|decid|stop|wait|allow|invite|offer|refus|"
    r"agree|guide|direct|leave|stay|take|give|open|close)\w*\b", re.I
)
INTIMACY_ACTION_TERMS = re.compile(
    r"\b(?:kiss|touch|caress|stroke|embrace|mouth|lip|tongue|skin|naked|"
    r"undress|breast|nipple|thigh|hip|waist|lover|desire|arous|pleasure|"
    r"bed|held her|held him|inside|enter|climax|orgasm)\w*\b", re.I
)
EXPLICIT_INTIMACY_TERMS = re.compile(
    r"\b(?:cock|penis|clitoris|vulva|nipple|breast|penetrat|thrust|"
    r"orgasm|climax|spent himself|inside (?:her|him)|entered (?:her|him))\w*\b",
    re.I,
)
INHERITED_WORK_FACETS = frozenset({
    "adult", "coercive", "counterexample", "psychological-romance",
    "romantic-comedy", "social-constraint", "forbidden-attraction",
})
SENSORY_PATTERNS = {
    "touch": re.compile(r"\b(?:touch|skin|hand|finger|pressure|rough|smooth|warm|cold)\w*\b", re.I),
    "sound": re.compile(r"\b(?:hear|sound|voice|breath|whisper|cry|laugh|silence)\w*\b", re.I),
    "sight": re.compile(r"\b(?:see|saw|look|watch|light|dark|colour|color|bright)\w*\b", re.I),
    "smell": re.compile(r"\b(?:smell|scent|perfume|smoke|salt|sweat)\w*\b", re.I),
    "taste": re.compile(r"\b(?:taste|tongue|mouth|lip|sweet|bitter|salt)\w*\b", re.I),
}


def _words(text: str) -> tuple[str, ...]:
    return tuple(match.group(0).casefold().replace("’", "'") for match in WORD_RE.finditer(text))


def _approx_tokens(text: str) -> int:
    # Stable conservative estimate for English prose. Runtime admission still
    # uses the actual tokenizer before inference.
    return max(1, math.ceil(len(_words(text)) * 1.36))


@dataclass(frozen=True, slots=True)
class LiteraryWork:
    work_id: str
    title: str
    author: str
    publication_year: int
    partition: str
    source_url: str
    local_path: str
    text_hash: str
    source_note: str = ""
    facets: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.partition not in ALLOWED_PARTITIONS:
            raise ValueError(f"invalid literary partition: {self.partition}")
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]+", self.work_id):
            raise ValueError(f"invalid work_id: {self.work_id}")


@dataclass(frozen=True, slots=True)
class SceneFeatures:
    dialogue_ratio: float
    romance_density: float
    conflict_density: float
    agency_density: float
    sensory_channels: int
    interiority_density: float
    intimacy_action_density: float
    explicit_intimacy_density: float
    sentence_length_mean: float
    sentence_length_variation: float

    def vector(self) -> tuple[float, ...]:
        return (
            self.dialogue_ratio,
            self.romance_density,
            self.conflict_density,
            self.agency_density,
            self.sensory_channels / 5.0,
            self.interiority_density,
            min(self.intimacy_action_density / 0.03, 1.0),
            min(self.explicit_intimacy_density / 0.012, 1.0),
            min(self.sentence_length_mean / 30.0, 1.0),
            min(self.sentence_length_variation / 20.0, 1.0),
        )


@dataclass(frozen=True, slots=True)
class LiteraryScene:
    scene_id: str
    work_id: str
    author: str
    title: str
    chapter_index: int
    scene_index: int
    partition: str
    source_url: str
    text: str
    text_hash: str
    word_count: int
    token_estimate: int
    facets: tuple[str, ...]
    features: SceneFeatures


@dataclass(frozen=True, slots=True)
class ApprenticeshipQuery:
    query_id: str
    query_text: str
    stage: str
    required_facets: tuple[str, ...] = ()
    preferred_facets: tuple[str, ...] = ()
    excluded_facets: tuple[str, ...] = ()
    included_authors: tuple[str, ...] = ()
    desired_features: Mapping[str, float] | None = None
    maximum_scenes: int = 8
    maximum_per_work: int = 2
    source_token_budget: int = 24_000
    mmr_lambda: float = 0.72
    minimum_stage_heat: float = 0.0


def _strip_gutenberg(text: str) -> str:
    start = re.search(r"\*\*\* START OF (?:THE |THIS )?PROJECT GUTENBERG EBOOK.*?\*\*\*", text, re.I)
    end = re.search(r"\*\*\* END OF (?:THE |THIS )?PROJECT GUTENBERG EBOOK.*?\*\*\*", text, re.I)
    left = start.end() if start else 0
    right = end.start() if end else len(text)
    return text[left:right].strip()


def _chapter_blocks(text: str) -> tuple[str, ...]:
    body = _strip_gutenberg(text)
    marker = re.compile(
        r"(?im)^(?:CHAPTER|BOOK)\s+(?:[IVXLCDM]+|\d+|[A-Z][A-Z '-]{2,})\.?\s*$"
    )
    starts = list(marker.finditer(body))
    if not starts:
        return (body,)
    blocks: list[str] = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(body)
        block = body[match.start():end].strip()
        if len(_words(block)) >= 300:
            blocks.append(block)
    return tuple(blocks) or (body,)


def _scene_chunks(chapter: str, minimum_words: int = 300, maximum_words: int = 950) -> tuple[str, ...]:
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", chapter) if len(_words(item)) >= 3]
    chunks: list[str] = []
    current: list[str] = []
    count = 0
    for paragraph in paragraphs:
        size = len(_words(paragraph))
        if current and count + size > maximum_words:
            if count >= minimum_words:
                chunks.append("\n\n".join(current))
            # Preserve one paragraph of local discourse context without
            # creating identical windows.
            current = current[-1:] if current and len(_words(current[-1])) < 220 else []
            count = sum(len(_words(item)) for item in current)
        current.append(paragraph)
        count += size
    if count >= minimum_words:
        chunks.append("\n\n".join(current))
    return tuple(chunks)


def _features(text: str) -> SceneFeatures:
    words = _words(text)
    n = max(1, len(words))
    sentences = [
        len(_words(item)) for item in re.split(r"(?<=[.!?])(?:[\"”’']?\s+)", text)
        if _words(item)
    ]
    mean = sum(sentences) / max(1, len(sentences))
    variation = math.sqrt(
        sum((item - mean) ** 2 for item in sentences) / max(1, len(sentences))
    )
    dialogue_words = sum(
        len(_words(item)) for item in re.findall(r'["“](.*?)["”]', text, re.S)
    )
    interior = len(re.findall(
        r"\b(?:thought|wondered|remembered|knew|felt|imagined|supposed|"
        r"wished|feared|hoped|understood)\w*\b", text, re.I
    ))
    return SceneFeatures(
        dialogue_ratio=round(min(dialogue_words / n, 1.0), 6),
        romance_density=round(len(ROMANCE_TERMS.findall(text)) / n, 6),
        conflict_density=round(len(CONFLICT_TERMS.findall(text)) / n, 6),
        agency_density=round(len(AGENCY_TERMS.findall(text)) / n, 6),
        sensory_channels=sum(bool(pattern.search(text)) for pattern in SENSORY_PATTERNS.values()),
        interiority_density=round(interior / n, 6),
        intimacy_action_density=round(len(INTIMACY_ACTION_TERMS.findall(text)) / n, 6),
        explicit_intimacy_density=round(len(EXPLICIT_INTIMACY_TERMS.findall(text)) / n, 6),
        sentence_length_mean=round(mean, 6),
        sentence_length_variation=round(variation, 6),
    )


def _inferred_facets(text: str, features: SceneFeatures) -> tuple[str, ...]:
    facets: set[str] = set()
    if features.dialogue_ratio >= 0.18:
        facets.add("dialogue-rich")
    if features.romance_density >= 0.012:
        facets.add("romantic-charge")
    if features.conflict_density >= 0.010:
        facets.add("interpersonal-pressure")
    if features.agency_density >= 0.018:
        facets.add("choice-and-agency")
    if features.sensory_channels >= 4:
        facets.add("sensory-dense")
    if features.interiority_density >= 0.008:
        facets.add("interior")
    if features.intimacy_action_density >= 0.006:
        facets.add("embodied-intimacy")
    if features.explicit_intimacy_density >= 0.0015:
        facets.add("explicit-intimacy")
    if re.search(r"\b(?:marry|marriage|husband|wife)\w*\b", text, re.I):
        facets.add("marriage")
    if re.search(r"\b(?:secret|evidence|letter|key|document|report|danger|escape)\w*\b", text, re.I):
        facets.add("plot-coupled")
    return tuple(sorted(facets))


def load_corpus_manifest(path: str | Path) -> tuple[dict[str, Any], tuple[LiteraryWork, ...]]:
    manifest_path = Path(path).resolve()
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    works: list[LiteraryWork] = []
    for item in value.get("works", ()):
        record = dict(item)
        record["facets"] = tuple(record.get("facets", ()))
        local = Path(record["local_path"])
        if not local.is_absolute():
            local = manifest_path.parent / local
        record["local_path"] = str(local.resolve())
        work = LiteraryWork(**record)
        if not Path(work.local_path).is_file():
            raise FileNotFoundError(f"literary source missing: {work.local_path}")
        if hash_file(Path(work.local_path)) != work.text_hash:
            raise ValueError(f"literary source hash mismatch: {work.work_id}")
        works.append(work)
    if not works:
        raise ValueError("literary corpus manifest has no works")
    return value, tuple(works)


def fetch_declared_sources(spec_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    """Fetch a source set and preserve its identity, location, and hashes."""

    spec_file = Path(spec_path).resolve()
    spec = json.loads(spec_file.read_text(encoding="utf-8"))
    root = Path(output_dir).resolve()
    books = root / "books"
    books.mkdir(parents=True, exist_ok=True)
    works: list[dict[str, Any]] = []
    for item in spec.get("works", ()):
        url = str(item["source_url"])
        request = Request(url, headers={"User-Agent": "fiction-harness/1.0 (local research)"})
        with urlopen(request, timeout=90) as response:
            text = response.read().decode("utf-8", errors="replace")
        if len(_words(text)) < 5_000:
            raise ValueError(f"downloaded source is implausibly short: {item['work_id']}")
        path = books / f"{item['work_id']}.txt"
        atomic_write_text(path, text)
        record = dict(item)
        record["local_path"] = str(path.relative_to(root))
        record["text_hash"] = hash_file(path)
        record["facets"] = list(record.get("facets", ()))
        works.append(record)
    manifest = {
        "record_type": "LiteraryApprenticeshipCorpus",
        "version": APPRENTICESHIP_VERSION,
        "corpus_id": spec["corpus_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_spec": str(spec_file),
        "source_spec_hash": hash_file(spec_file),
        "works": works,
    }
    manifest["corpus_hash"] = hash_json({key: value for key, value in manifest.items() if key != "created_at"})
    write_json(root / "corpus_manifest.v1.json", manifest)
    return manifest


def compile_scene_index(manifest_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    manifest, works = load_corpus_manifest(manifest_path)
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    db_path = output / "literary_scenes.v1.sqlite"
    if db_path.exists():
        db_path.unlink()
    counts: dict[str, int] = {}
    scene_hashes: dict[str, str] = {}
    with closing(sqlite3.connect(db_path)) as connection:
        connection.executescript(
            """
            CREATE TABLE scenes (
              scene_id TEXT PRIMARY KEY, work_id TEXT, author TEXT, title TEXT,
              chapter_index INTEGER, scene_index INTEGER, partition_name TEXT,
              source_url TEXT, text_hash TEXT, word_count INTEGER,
              token_estimate INTEGER, facets_json TEXT, features_json TEXT, text_value TEXT
            );
            CREATE VIRTUAL TABLE scene_fts USING fts5(scene_id UNINDEXED, text_value);
            """
        )
        for work in works:
            text = Path(work.local_path).read_text(encoding="utf-8", errors="replace")
            scene_number = 0
            for chapter_index, chapter in enumerate(_chapter_blocks(text), 1):
                for local_index, chunk in enumerate(_scene_chunks(chapter), 1):
                    scene_number += 1
                    features = _features(chunk)
                    inherited = set(work.facets) & INHERITED_WORK_FACETS
                    facets = tuple(sorted(inherited | set(_inferred_facets(chunk, features))))
                    scene_id = f"{work.work_id}.c{chapter_index:03d}.s{local_index:03d}"
                    scene = LiteraryScene(
                        scene_id=scene_id, work_id=work.work_id, author=work.author,
                        title=work.title, chapter_index=chapter_index,
                        scene_index=local_index, partition=work.partition,
                        source_url=work.source_url,
                        text=chunk, text_hash=sha256_text(chunk),
                        word_count=len(_words(chunk)), token_estimate=_approx_tokens(chunk),
                        facets=facets, features=features,
                    )
                    connection.execute(
                        "INSERT INTO scenes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            scene.scene_id, scene.work_id, scene.author, scene.title,
                            scene.chapter_index, scene.scene_index, scene.partition,
                            scene.source_url, scene.text_hash,
                            scene.word_count, scene.token_estimate,
                            json.dumps(scene.facets), json.dumps(asdict(scene.features)),
                            scene.text,
                        ),
                    )
                    connection.execute(
                        "INSERT INTO scene_fts(scene_id,text_value) VALUES (?,?)",
                        (scene.scene_id, scene.text),
                    )
                    scene_hashes[scene_id] = scene.text_hash
            counts[work.work_id] = scene_number
        connection.commit()
    index_manifest = {
        "record_type": "LiterarySceneIndex",
        "version": APPRENTICESHIP_VERSION,
        "corpus_manifest": str(Path(manifest_path).resolve()),
        "corpus_manifest_hash": hash_file(Path(manifest_path).resolve()),
        "corpus_hash": manifest.get("corpus_hash", ""),
        "database": str(db_path),
        "work_scene_counts": counts,
        "scene_count": sum(counts.values()),
        "scene_hash_root": hash_json(scene_hashes),
        "partition_protocol": "profiling for prompts; calibration and holdout for measurement",
    }
    index_manifest["index_hash"] = hash_json(index_manifest)
    write_json(output / "index_manifest.v1.json", index_manifest)
    return index_manifest


def load_query(path: str | Path) -> ApprenticeshipQuery:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    return ApprenticeshipQuery(**{
        key: tuple(item) if key in {
            "required_facets", "preferred_facets", "excluded_facets", "included_authors"
        } else item
        for key, item in value.items()
    })


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    denominator = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return numerator / denominator if denominator else 0.0


def _jaccard(left: str, right: str) -> float:
    a, b = set(_words(left)), set(_words(right))
    return len(a & b) / max(1, len(a | b))


def _row_scene(row: sqlite3.Row) -> LiteraryScene:
    feature_values = json.loads(row["features_json"])
    return LiteraryScene(
        scene_id=row["scene_id"], work_id=row["work_id"], author=row["author"],
        title=row["title"], chapter_index=row["chapter_index"],
        scene_index=row["scene_index"], partition=row["partition_name"],
        source_url=row["source_url"],
        text=row["text_value"], text_hash=row["text_hash"],
        word_count=row["word_count"], token_estimate=row["token_estimate"],
        facets=tuple(json.loads(row["facets_json"])),
        features=SceneFeatures(**feature_values),
    )


def retrieve_scenes(index_manifest_path: str | Path, query: ApprenticeshipQuery) -> dict[str, Any]:
    index_manifest = json.loads(Path(index_manifest_path).read_text(encoding="utf-8"))
    db_path = Path(index_manifest["database"])
    tokens = [item for item in _words(query.query_text) if len(item) > 2][:28]
    lexical_raw: dict[str, float] = {}
    with closing(sqlite3.connect(db_path)) as connection:
        connection.row_factory = sqlite3.Row
        if tokens:
            expression = " OR ".join('"' + item.replace('"', '') + '"' for item in tokens)
            try:
                for row in connection.execute(
                    "SELECT scene_id,bm25(scene_fts) AS rank FROM scene_fts WHERE scene_fts MATCH ? LIMIT 250",
                    (expression,),
                ):
                    lexical_raw[str(row["scene_id"])] = -float(row["rank"])
            except sqlite3.OperationalError:
                lexical_raw = {}
        rows = list(connection.execute(
            "SELECT * FROM scenes WHERE partition_name='profiling'"
        ))
    if lexical_raw:
        low, high = min(lexical_raw.values()), max(lexical_raw.values())
        spread = high - low
        lexical = {
            key: ((value - low) / spread if spread > 1e-12 else 1.0)
            for key, value in lexical_raw.items()
        }
    else:
        lexical = {}
    desired = query.desired_features or {}
    desired_vector = (
        float(desired.get("dialogue_ratio", 0.28)),
        float(desired.get("romance_density", 0.018)),
        float(desired.get("conflict_density", 0.014)),
        float(desired.get("agency_density", 0.022)),
        float(desired.get("sensory_channels", 4.0)) / 5.0,
        float(desired.get("interiority_density", 0.010)),
        min(float(desired.get("intimacy_action_density", 0.012)) / 0.03, 1.0),
        min(float(desired.get("explicit_intimacy_density", 0.003)) / 0.012, 1.0),
        float(desired.get("sentence_length_mean", 18.0)) / 30.0,
        float(desired.get("sentence_length_variation", 11.0)) / 20.0,
    )
    candidates: list[dict[str, Any]] = []
    for row in rows:
        scene = _row_scene(row)
        if query.included_authors and scene.author not in query.included_authors:
            continue
        facets = set(scene.facets)
        if set(query.required_facets) - facets or set(query.excluded_facets) & facets:
            continue
        lexical_score = lexical.get(scene.scene_id, 0.0)
        facet_score = len(set(query.preferred_facets) & facets) / max(1, len(query.preferred_facets))
        geometry_score = _cosine(scene.features.vector(), desired_vector)
        # Slightly prefer scene-sized exemplars over chapter-sized dumps.
        size_score = max(0.0, 1.0 - abs(scene.word_count - 750) / 850)
        intimacy_score = min(scene.features.intimacy_action_density / 0.025, 1.0)
        explicit_score = min(scene.features.explicit_intimacy_density / 0.008, 1.0)
        stage_heat = 0.7 * intimacy_score + 0.3 * explicit_score if "transaction" in query.stage else intimacy_score
        if stage_heat < query.minimum_stage_heat:
            continue
        base_score = (
            0.28 * lexical_score + 0.20 * facet_score + 0.27 * geometry_score
            + 0.07 * size_score + 0.18 * stage_heat
        )
        candidates.append({"scene": scene, "base_score": base_score, "components": {
            "lexical": round(lexical_score, 6), "facet": round(facet_score, 6),
            "craft_geometry": round(geometry_score, 6), "size": round(size_score, 6),
            "stage_heat": round(stage_heat, 6),
        }})
    candidates.sort(key=lambda item: (-item["base_score"], item["scene"].scene_id))
    selected: list[dict[str, Any]] = []
    work_counts: dict[str, int] = {}
    remaining = query.source_token_budget
    while candidates and len(selected) < query.maximum_scenes:
        best_index = None
        best_value = -1e9
        for index, item in enumerate(candidates):
            scene = item["scene"]
            if scene.token_estimate > remaining:
                continue
            if work_counts.get(scene.work_id, 0) >= query.maximum_per_work:
                continue
            redundancy = max((_jaccard(scene.text, prior["scene"].text) for prior in selected), default=0.0)
            author_bonus = 0.06 if all(scene.author != prior["scene"].author for prior in selected) else 0.0
            value = query.mmr_lambda * item["base_score"] - (1.0 - query.mmr_lambda) * redundancy + author_bonus
            if value > best_value:
                best_index, best_value = index, value
        if best_index is None:
            break
        item = candidates.pop(best_index)
        scene = item["scene"]
        item["mmr_score"] = round(best_value, 6)
        selected.append(item)
        work_counts[scene.work_id] = work_counts.get(scene.work_id, 0) + 1
        remaining -= scene.token_estimate
    records = []
    for rank, item in enumerate(selected, 1):
        scene = item["scene"]
        records.append({
            "rank": rank, "scene_id": scene.scene_id, "work_id": scene.work_id,
            "author": scene.author, "title": scene.title,
            "text_hash": scene.text_hash, "word_count": scene.word_count,
            "token_estimate": scene.token_estimate, "facets": list(scene.facets),
            "features": asdict(scene.features), "score_components": item["components"],
            "base_score": round(item["base_score"], 6), "mmr_score": item["mmr_score"],
        })
    payload = {
        "record_type": "LiteraryRetrievalResult", "version": APPRENTICESHIP_VERSION,
        "index_hash": index_manifest["index_hash"], "query": asdict(query),
        "selected": records, "selected_token_estimate": sum(item["token_estimate"] for item in records),
        "unused_source_tokens": remaining,
        "selection_method": "fts5-bm25+craft-geometry+facets+mmr+work-cap",
    }
    payload["retrieval_hash"] = hash_json(payload)
    return payload


def compile_prompt(
    *, index_manifest_path: str | Path, retrieval: Mapping[str, Any],
    target_contract: str, runway: str, output_dir: str | Path,
) -> dict[str, Any]:
    index_manifest = json.loads(Path(index_manifest_path).read_text(encoding="utf-8"))
    if retrieval.get("index_hash") != index_manifest.get("index_hash"):
        raise ValueError("retrieval result belongs to another literary index")
    scenes: list[LiteraryScene] = []
    with closing(sqlite3.connect(index_manifest["database"])) as connection:
        connection.row_factory = sqlite3.Row
        for item in retrieval["selected"]:
            row = connection.execute(
                "SELECT * FROM scenes WHERE scene_id=?", (item["scene_id"],)
            ).fetchone()
            if row is None:
                raise ValueError(f"retrieved scene disappeared: {item['scene_id']}")
            scene = _row_scene(row)
            if scene.partition != "profiling":
                raise ValueError(f"non-profiling scene entered prompt: {scene.scene_id}")
            if scene.text_hash != item["text_hash"]:
                raise ValueError(f"retrieved scene hash mismatch: {scene.scene_id}")
            scenes.append(scene)
    # Lowest relevance first, highest relevance nearest the target.
    scenes.reverse()
    blocks: list[tuple[str, str, str, tuple[str, ...]]] = [
        (
            "apprenticeship.convention", "control",
            "LITERARY APPRENTICESHIP ARCHIVE\n"
            "The reference scenes teach distributions of attention, dialogue, bodily action, "
            "syntax, and causal intimacy. Continue the new manuscript; do not quote, summarize, "
            "name, or transplant the reference characters or events.", (),
        )
    ]
    for index, scene in enumerate(scenes, 1):
        blocks.append((
            f"source.{scene.scene_id}", "source-prose",
            f"REFERENCE SCENE {index}\n{scene.text.strip()}\nEND REFERENCE SCENE {index}",
            (scene.scene_id,),
        ))
    blocks.append(("target.contract", "target-control", target_contract.strip(), ()))
    rendered: list[str] = []
    block_map: list[dict[str, Any]] = []
    cursor = 0
    for block_id, role, text, source_ids in blocks:
        if rendered:
            cursor += 2
        start = cursor
        rendered.append(text)
        cursor += len(text)
        block_map.append({
            "block_id": block_id, "role": role, "char_start": start,
            "char_end": cursor, "text_hash": sha256_text(text),
            "token_estimate": _approx_tokens(text), "source_ids": list(source_ids),
        })
    prefix = "\n\n".join(rendered) + "\n\nMANUSCRIPT\n"
    prompt = prefix + runway
    if not prompt.endswith(runway):
        raise AssertionError("apprenticeship prompt must end on exact manuscript runway")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    prompt_path = output / "prompt.v1.txt"
    atomic_write_text(prompt_path, prompt)
    manifest = {
        "record_type": "CompiledLiteraryApprenticeshipPrompt",
        "version": APPRENTICESHIP_VERSION,
        "index_hash": index_manifest["index_hash"],
        "retrieval_hash": retrieval["retrieval_hash"],
        "prompt_path": str(prompt_path), "prompt_hash": sha256_text(prompt),
        "prompt_token_estimate": _approx_tokens(prompt),
        "stable_prefix_hash": sha256_text(prefix),
        "runway_hash": sha256_text(runway), "runway_words": len(_words(runway)),
        "block_map": block_map,
        "source_scene_ids": [scene.scene_id for scene in scenes],
        "source_text_hashes": {scene.scene_id: scene.text_hash for scene in scenes},
        "ordering": "broad-to-near; highest retrieval score nearest target",
        "boundary_policy": "last bytes are exact plain manuscript prose",
        "anti_copy_policy": "all selected source scene hashes enter generation anti-copy index",
    }
    manifest["compiled_prompt_hash"] = hash_json(manifest)
    write_json(output / "prompt_manifest.v1.json", manifest)
    return manifest


def render_retrieved_archive(
    *, index_manifest_path: str | Path, retrieval_path: str | Path,
) -> tuple[str, dict[str, str]]:
    """Render a frozen retrieval result for insertion before the target runway.

    The returned source mapping is deliberately the same text placed in the
    prompt so the caller can add every exemplar to its ordinary anti-copy
    index.  Partitions are experiment boundaries: calibration and holdout
    material cannot leak into the prompt used to measure them.
    """

    index_manifest = json.loads(Path(index_manifest_path).read_text(encoding="utf-8"))
    retrieval = json.loads(Path(retrieval_path).read_text(encoding="utf-8"))
    if retrieval.get("index_hash") != index_manifest.get("index_hash"):
        raise ValueError("retrieval result belongs to another literary index")
    scenes: list[LiteraryScene] = []
    with closing(sqlite3.connect(index_manifest["database"])) as connection:
        connection.row_factory = sqlite3.Row
        for item in retrieval.get("selected", ()):
            row = connection.execute(
                "SELECT * FROM scenes WHERE scene_id=?", (item["scene_id"],)
            ).fetchone()
            if row is None:
                raise ValueError(f"retrieved scene disappeared: {item['scene_id']}")
            scene = _row_scene(row)
            if scene.partition != "profiling":
                raise ValueError(f"non-profiling scene entered prompt: {scene.scene_id}")
            if scene.text_hash != item["text_hash"]:
                raise ValueError(f"retrieved scene hash mismatch: {scene.scene_id}")
            scenes.append(scene)
    scenes.reverse()  # strongest retrieval is nearest the target material
    chunks = [
        "RETRIEVED LITERARY APPRENTICESHIP\n"
        "Absorb these scenes as demonstrations of attention, dialogue, bodily "
        "action, rhythm, and causal intimacy. Continue the new manuscript in "
        "its own people and circumstances; do not repeat source wording."
    ]
    sources: dict[str, str] = {}
    for number, scene in enumerate(scenes, 1):
        source_id = f"apprenticeship.{scene.scene_id}"
        sources[source_id] = scene.text
        chunks.append(
            f"APPRENTICESHIP SCENE {number}\n{scene.text.strip()}\n"
            f"END APPRENTICESHIP SCENE {number}"
        )
    return "\n\n".join(chunks), sources
