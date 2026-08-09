"""Deterministic serialization, hashing, and append-only persistence helpers."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable, Mapping


def to_plain_data(value: Any) -> Any:
    """Convert supported records into JSON-compatible data.

    Mapping keys are stringified and sorted later by ``canonical_json_*``.
    Tuples intentionally become arrays so dataclass records have a stable wire
    representation independent of their in-memory immutability.
    """

    if is_dataclass(value) and not isinstance(value, type):
        return to_plain_data(asdict(value))
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, Mapping):
        return {str(key): to_plain_data(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [to_plain_data(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"cannot serialize {type(value).__name__} to canonical JSON")


def canonical_json_text(value: Any) -> str:
    """Return the canonical, human-readable JSON representation of ``value``."""

    return json.dumps(
        to_plain_data(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        indent=2,
        separators=(",", ": "),
    ) + "\n"


def canonical_json_bytes(value: Any) -> bytes:
    """Return canonical UTF-8 JSON bytes."""

    return canonical_json_text(value).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def hash_json(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def hash_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def stable_prefix(
    sections: Mapping[str, str] | Iterable[tuple[str, str]],
    *,
    format_version: str = "stable-prefix.v1",
) -> str:
    """Serialize named prompt sections without introducing volatile metadata.

    A mapping is sorted by key. An ordered iterable preserves its supplied
    order. The explicit length makes section boundaries unambiguous even when
    source text itself contains headings.
    """

    if isinstance(sections, Mapping):
        items = sorted(sections.items())
    else:
        items = list(sections)
    chunks = [f"@@FORMAT {format_version}\n"]
    for name, text in items:
        if not name or "\n" in name:
            raise ValueError("stable-prefix section names must be non-empty single lines")
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").rstrip() + "\n"
        length = len(normalized.encode("utf-8"))
        chunks.append(f"@@SECTION {name} {length}\n")
        chunks.append(normalized)
        chunks.append(f"@@END {name}\n")
    return "".join(chunks)


def stable_prefix_hash(
    sections: Mapping[str, str] | Iterable[tuple[str, str]],
    *,
    format_version: str = "stable-prefix.v1",
) -> str:
    return sha256_text(stable_prefix(sections, format_version=format_version))


def atomic_write_text(path: str | Path, text: str) -> None:
    """Atomically replace ``path`` with UTF-8 text."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def write_json(path: str | Path, value: Any) -> None:
    atomic_write_text(path, canonical_json_text(value))


def append_jsonl(path: str | Path, value: Any) -> None:
    """Append one compact canonical JSON record and flush it to disk."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        to_plain_data(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    with destination.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())
