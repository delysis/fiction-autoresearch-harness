"""Local exact, fuzzy, and adjudicated overlap detection for generated prose."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
import hashlib
import re
from typing import Any, Callable, Iterable, Mapping, Sequence

from .author_schemas import OverlapReport
from .core import hash_json, sha256_text


WORD_RE = re.compile(r"\b[\w’'-]+\b", re.UNICODE)


def normalized_words(text: str) -> tuple[str, ...]:
    return tuple(
        match.group(0).casefold().replace("’", "'")
        for match in WORD_RE.finditer(text)
    )


def normalized_text(text: str) -> str:
    return " ".join(normalized_words(text))


def _ngrams(tokens: Sequence[str], n: int) -> set[tuple[str, ...]]:
    if n <= 0:
        raise ValueError("n must be positive")
    return {
        tuple(tokens[index : index + n])
        for index in range(max(0, len(tokens) - n + 1))
    }


def _shingle_hash(tokens: Sequence[str]) -> str:
    return hashlib.blake2b(
        "\x1f".join(tokens).encode("utf-8"), digest_size=16
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class AntiCopyPolicy:
    version: str = "anti-copy.v1"
    exact_words: int = 12
    fuzzy_min_chars: int = 80
    fuzzy_ratio: float = 0.90
    window_words: int = 200
    containment_ngram: int = 8
    containment_threshold: float = 0.10
    cross_candidate_exact_words: int = 16
    minhash_size: int = 32

    def __post_init__(self) -> None:
        if self.exact_words < 4:
            raise ValueError("exact_words must be at least four")
        if self.fuzzy_min_chars < 20:
            raise ValueError("fuzzy_min_chars must be at least twenty")
        for name in ("fuzzy_ratio", "containment_threshold"):
            value = float(getattr(self, name))
            if not 0 < value <= 1:
                raise ValueError(f"{name} must be between zero and one")

    @property
    def policy_hash(self) -> str:
        return hash_json(asdict(self))


@dataclass(frozen=True, slots=True)
class IndexedSource:
    source_id: str
    category: str
    text_hash: str
    tokens: tuple[str, ...]
    normalized: str
    shingles_8: frozenset[tuple[str, ...]]
    minhash: tuple[int, ...]


class SourceOverlapError(RuntimeError):
    """Raised when a streaming draft completes a forbidden exact shingle."""

    def __init__(self, match: Mapping[str, Any]):
        self.match = dict(match)
        super().__init__(
            f"streamed text matched {match.get('word_count')} source words "
            f"from {match.get('source_ids')}"
        )


def _minhash(
    shingles: Iterable[tuple[str, ...]],
    *,
    size: int,
) -> tuple[int, ...]:
    values = ["\x1f".join(item).encode("utf-8") for item in shingles]
    if not values:
        return tuple((1 << 64) - 1 for _ in range(size))
    signature: list[int] = []
    for salt in range(size):
        prefix = salt.to_bytes(4, "little")
        signature.append(
            min(
                int.from_bytes(
                    hashlib.blake2b(prefix + value, digest_size=8).digest(),
                    "little",
                )
                for value in values
            )
        )
    return tuple(signature)


def _minhash_similarity(left: Sequence[int], right: Sequence[int]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    return sum(a == b for a, b in zip(left, right)) / len(left)


class AntiCopyIndex:
    """In-memory local source index with a content-derived public hash."""

    def __init__(
        self,
        documents: Mapping[str, str],
        *,
        categories: Mapping[str, str] | None = None,
        whitelist: Iterable[str] = (),
        policy: AntiCopyPolicy | None = None,
    ):
        self.policy = policy or AntiCopyPolicy()
        self._whitelist = {
            _shingle_hash(item)
            for phrase in whitelist
            for item in _ngrams(
                normalized_words(phrase), self.policy.exact_words
            )
        }
        categories = dict(categories or {})
        sources: list[IndexedSource] = []
        exact: dict[str, set[str]] = {}
        for source_id in sorted(documents):
            text = documents[source_id]
            tokens = normalized_words(text)
            shingles_5 = _ngrams(tokens, 5)
            source = IndexedSource(
                source_id=source_id,
                category=categories.get(source_id, "author-corpus"),
                text_hash=sha256_text(text),
                tokens=tokens,
                normalized=" ".join(tokens),
                shingles_8=frozenset(
                    _ngrams(tokens, self.policy.containment_ngram)
                ),
                minhash=_minhash(
                    shingles_5, size=self.policy.minhash_size
                ),
            )
            sources.append(source)
            for shingle in _ngrams(tokens, self.policy.exact_words):
                digest = _shingle_hash(shingle)
                if digest in self._whitelist:
                    continue
                exact.setdefault(digest, set()).add(source_id)
        self.sources = tuple(sources)
        self._exact = {
            digest: tuple(sorted(source_ids))
            for digest, source_ids in exact.items()
        }
        self.index_hash = hash_json(
            {
                "policy": asdict(self.policy),
                "sources": [
                    {
                        "source_id": item.source_id,
                        "category": item.category,
                        "text_hash": item.text_hash,
                    }
                    for item in self.sources
                ],
                "whitelist_hashes": sorted(self._whitelist),
            }
        )

    def manifest(self) -> dict[str, Any]:
        return {
            "record_type": "AntiCopyIndexManifest",
            "policy": asdict(self.policy),
            "index_hash": self.index_hash,
            "sources": [
                {
                    "source_id": item.source_id,
                    "category": item.category,
                    "text_hash": item.text_hash,
                    "word_count": len(item.tokens),
                }
                for item in self.sources
            ],
        }
    def exact_matches(self, text: str) -> tuple[dict[str, Any], ...]:
        tokens = normalized_words(text)
        matches: list[dict[str, Any]] = []
        seen: set[tuple[str, tuple[str, ...]]] = set()
        for index in range(max(0, len(tokens) - self.policy.exact_words + 1)):
            shingle = tokens[index : index + self.policy.exact_words]
            digest = _shingle_hash(shingle)
            source_ids = self._exact.get(digest)
            if not source_ids:
                continue
            key = (digest, source_ids)
            if key in seen:
                continue
            seen.add(key)
            matches.append(
                {
                    "source_ids": list(source_ids),
                    "candidate_word_start": index,
                    "word_count": self.policy.exact_words,
                    "shingle_hash": digest,
                }
            )
        return tuple(matches)

    def first_exact_match(self, text: str) -> dict[str, Any] | None:
        matches = self.exact_matches(text)
        return matches[0] if matches else None

    def _candidate_windows(
        self, text: str
    ) -> tuple[tuple[int, tuple[str, ...], str, tuple[int, ...]], ...]:
        tokens = normalized_words(text)
        step = max(1, self.policy.window_words // 2)
        windows: list[tuple[int, tuple[str, ...], str, tuple[int, ...]]] = []
        for start in range(0, len(tokens), step):
            window = tokens[start : start + self.policy.window_words]
            if len(window) < 8:
                continue
            normalized = " ".join(window)
            signature = _minhash(
                _ngrams(window, 5), size=self.policy.minhash_size
            )
            windows.append((start, window, normalized, signature))
            if start + self.policy.window_words >= len(tokens):
                break
        return tuple(windows)

    def fuzzy_matches(self, text: str) -> tuple[dict[str, Any], ...]:
        candidate_tokens = normalized_words(text)
        candidate_ngrams = _ngrams(
            candidate_tokens, self.policy.containment_ngram
        )
        matches: list[dict[str, Any]] = []
        for source in self.sources:
            if candidate_ngrams and source.shingles_8:
                containment = len(
                    candidate_ngrams & set(source.shingles_8)
                ) / max(1, len(candidate_ngrams))
            else:
                containment = 0.0
            if containment > self.policy.containment_threshold:
                matches.append(
                    {
                        "source_id": source.source_id,
                        "category": source.category,
                        "kind": "eight_gram_containment",
                        "score": round(containment, 6),
                        "threshold": self.policy.containment_threshold,
                    }
                )
        seen_char: set[tuple[str, int]] = set()
        for start, window_tokens, _, signature in self._candidate_windows(
            text
        ):
            ranked = sorted(
                self.sources,
                key=lambda source: (
                    -_minhash_similarity(signature, source.minhash),
                    source.source_id,
                ),
            )[:5]
            for source in ranked:
                matcher = SequenceMatcher(
                    None, window_tokens, source.tokens, autojunk=False
                )
                block = matcher.find_longest_match(
                    0,
                    len(window_tokens),
                    0,
                    len(source.tokens),
                )
                matched_chars = len(
                    " ".join(
                        window_tokens[block.a : block.a + block.size]
                    )
                )
                if matched_chars < self.policy.fuzzy_min_chars:
                    continue
                source_start = max(
                    0,
                    block.b
                    - max(0, block.a),
                )
                source_slice = source.tokens[
                    source_start : source_start + len(window_tokens)
                ]
                ratio = SequenceMatcher(
                    None, window_tokens, source_slice, autojunk=False
                ).ratio()
                key = (source.source_id, start)
                if ratio >= self.policy.fuzzy_ratio and key not in seen_char:
                    seen_char.add(key)
                    matches.append(
                        {
                            "source_id": source.source_id,
                            "category": source.category,
                            "kind": "character_window_similarity",
                            "candidate_word_start": start,
                            "matched_chars": matched_chars,
                            "score": round(ratio, 6),
                            "threshold": self.policy.fuzzy_ratio,
                        }
                    )
        return tuple(matches)

    def check(
        self,
        candidate_id: str,
        text: str,
        *,
        prior_candidates: Mapping[str, str] | None = None,
        semantic_adjudicator: Callable[
            [str, str, str], Mapping[str, Any] | None
        ]
        | None = None,
    ) -> OverlapReport:
        exact = self.exact_matches(text)
        fuzzy = self.fuzzy_matches(text)
        semantic: list[Mapping[str, Any]] = []
        flagged_source_ids = sorted(
            {
                str(item["source_id"])
                for item in fuzzy
                if item.get("source_id")
            }
        )
        sources = {item.source_id: item for item in self.sources}
        if semantic_adjudicator:
            for source_id in flagged_source_ids:
                source = sources[source_id]
                result = semantic_adjudicator(
                    text, source_id, source.normalized
                )
                if result:
                    semantic.append(dict(result))
        cross: list[Mapping[str, Any]] = []
        for other_id, other_text in sorted((prior_candidates or {}).items()):
            other_tokens = normalized_words(other_text)
            other_shingles = {
                _shingle_hash(item)
                for item in _ngrams(
                    other_tokens, self.policy.cross_candidate_exact_words
                )
            }
            candidate_shingles = {
                _shingle_hash(item)
                for item in _ngrams(
                    normalized_words(text),
                    self.policy.cross_candidate_exact_words,
                )
            }
            common = candidate_shingles & other_shingles
            if common:
                cross.append(
                    {
                        "candidate_id": other_id,
                        "word_count": self.policy.cross_candidate_exact_words,
                        "match_count": len(common),
                    }
                )
        semantic_rejected = any(
            item.get("verdict") in {"copy", "near-copy", "structural-copy"}
            for item in semantic
        )
        unresolved = bool(fuzzy) and (
            semantic_adjudicator is None
            or len(semantic) < len(flagged_source_ids)
        )
        return OverlapReport(
            candidate_id=candidate_id,
            policy_version=self.policy.version,
            index_hash=self.index_hash,
            exact_matches=exact,
            fuzzy_matches=fuzzy,
            semantic_matches=tuple(semantic),
            cross_candidate_matches=tuple(cross),
            hard_fail=bool(exact) or semantic_rejected,
            unresolved_flags=unresolved,
        )


def build_anti_copy_index(
    *,
    author_documents: Mapping[str, str],
    prompt_exemplars: Mapping[str, str] | None = None,
    project_sources: Mapping[str, str] | None = None,
    whitelist: Iterable[str] = (),
    policy: AntiCopyPolicy | None = None,
) -> AntiCopyIndex:
    """Build one index with explicit source classes and no silent overwrites."""

    collections = (
        ("author-corpus", author_documents),
        ("prompt-exemplar", prompt_exemplars or {}),
        ("project-source", project_sources or {}),
    )
    documents: dict[str, str] = {}
    categories: dict[str, str] = {}
    for category, values in collections:
        for source_id, text in values.items():
            if source_id in documents:
                raise ValueError(f"duplicate anti-copy source ID: {source_id}")
            documents[str(source_id)] = str(text)
            categories[str(source_id)] = category
    if not documents:
        raise ValueError("anti-copy index requires at least one document")
    return AntiCopyIndex(
        documents,
        categories=categories,
        whitelist=whitelist,
        policy=policy,
    )


class StreamingNgramGuard:
    """Incremental guard suitable for a server-sent-event completion."""

    def __init__(self, index: AntiCopyIndex):
        self.index = index
        self.text = ""
        self._last_token_count = 0

    def feed(self, delta: str) -> None:
        self.text += delta
        token_count = len(normalized_words(self.text))
        if token_count < self.index.policy.exact_words:
            return
        # Scan only after a new normalized word completes. The complete scan is
        # deliberately simple and deterministic; generation is still cancelled
        # at the first forbidden 12-word sequence.
        if token_count == self._last_token_count:
            return
        self._last_token_count = token_count
        match = self.index.first_exact_match(self.text)
        if match:
            raise SourceOverlapError(match)
