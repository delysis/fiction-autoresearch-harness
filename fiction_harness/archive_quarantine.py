"""Fail-closed export path for the archived fiction harness.

This module deliberately does not import the generation runtime.  It uses only
the Python standard library and moves historical bytes in one direction:
repository -> content-verified export -> Loom diagnostic manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile
from typing import Any, Mapping, Sequence


ARCHIVE_STATUS_SCHEMA = "fiction-harness-archive-status.v1"
EXPORT_SCHEMA = "fiction-historical-export.v1"
LOOM_IMPORT_SCHEMA = "loom-diagnostic-import.v1"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATUS_PATH = PROJECT_ROOT / "ARCHIVE_STATUS.json"


class ArchiveViolation(ValueError):
    """An archival operation failed a confinement or integrity check."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _relative_id(value: str, *, label: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ArchiveViolation(f"{label} must be a confined relative identifier")
    return path


def _under(root: Path, candidate: Path, *, label: str) -> Path:
    resolved_root = root.resolve(strict=True)
    resolved = candidate.resolve(strict=True)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ArchiveViolation(f"{label} escapes its trusted root") from exc
    return resolved


def _reject_symlink_components(root: Path, relative: PurePosixPath) -> Path:
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ArchiveViolation(f"symbolic link forbidden in historical path: {relative}")
    return current


def _historical_files(dataset_root: Path) -> list[tuple[PurePosixPath, Path]]:
    found: list[tuple[PurePosixPath, Path]] = []
    pending: list[tuple[PurePosixPath, Path]] = [(PurePosixPath(), dataset_root)]
    while pending:
        prefix, directory = pending.pop()
        with os.scandir(directory) as entries:
            ordered = sorted(entries, key=lambda item: item.name)
        for entry in reversed(ordered):
            relative = prefix / entry.name
            if entry.is_symlink():
                raise ArchiveViolation(f"symbolic link forbidden in historical path: {relative}")
            if entry.is_dir(follow_symlinks=False):
                pending.append((relative, Path(entry.path)))
            elif entry.is_file(follow_symlinks=False):
                found.append((relative, Path(entry.path)))
            else:
                raise ArchiveViolation(f"non-regular historical path is forbidden: {relative}")
    return sorted(found, key=lambda item: item[0].as_posix())


def _validated_sha(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ArchiveViolation("audited base SHA must be 40 lowercase hexadecimal characters")
    return value


def load_archive_status(path: str | Path = STATUS_PATH) -> dict[str, Any]:
    status_path = Path(path)
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArchiveViolation("archive status is absent or invalid") from exc
    required = {
        "schema_version": ARCHIVE_STATUS_SCHEMA,
        "status": "archived_quarantine",
        "active_release_train": False,
        "promotion_eligible": False,
    }
    if not isinstance(status, dict) or any(status.get(key) != value for key, value in required.items()):
        raise ArchiveViolation("archive status is not fail-closed")
    _validated_sha(str(status.get("audited_base_sha", "")))
    datasets = status.get("historical_datasets")
    if not isinstance(datasets, dict) or not datasets:
        raise ArchiveViolation("archive status lacks trusted historical dataset IDs")
    for dataset_id, relative in datasets.items():
        _relative_id(str(dataset_id), label="dataset ID")
        _relative_id(str(relative), label=f"dataset root for {dataset_id}")
    return status


def export_historical_datasets(
    *,
    repository_root: str | Path,
    output_root: str | Path,
    dataset_roots: Mapping[str, str],
    selected_dataset_ids: Sequence[str],
    audited_base_sha: str,
) -> dict[str, Any]:
    """Copy trusted historical datasets into a deterministic hashed envelope."""

    source_root = Path(repository_root).resolve(strict=True)
    requested_output = Path(output_root)
    output_parent = requested_output.parent.resolve(strict=True)
    output = output_parent / requested_output.name
    if output.exists() or output.is_symlink():
        raise ArchiveViolation("export output must not already exist")
    try:
        output_parent.relative_to(source_root)
    except ValueError:
        pass
    else:
        raise ArchiveViolation("export output must be outside the archived repository")

    selected = tuple(sorted(set(selected_dataset_ids)))
    if not selected:
        raise ArchiveViolation("at least one trusted dataset ID is required")
    unknown = [dataset_id for dataset_id in selected if dataset_id not in dataset_roots]
    if unknown:
        raise ArchiveViolation(f"unknown dataset ID: {unknown[0]}")
    base_sha = _validated_sha(audited_base_sha)

    resolved_datasets: list[tuple[str, Path]] = []
    for dataset_id in selected:
        _relative_id(dataset_id, label="dataset ID")
        relative = _relative_id(str(dataset_roots[dataset_id]), label="dataset root")
        candidate = _reject_symlink_components(source_root, relative)
        resolved = _under(source_root, candidate, label=f"dataset {dataset_id}")
        if not resolved.is_dir():
            raise ArchiveViolation(f"trusted dataset is not a directory: {dataset_id}")
        resolved_datasets.append((dataset_id, resolved))

    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output_parent))
    try:
        records: list[dict[str, Any]] = []
        for dataset_id, dataset_root in resolved_datasets:
            for relative, source in _historical_files(dataset_root):
                data = source.read_bytes()
                target = staging / dataset_id / Path(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                records.append(
                    {
                        "bytes": len(data),
                        "dataset_id": dataset_id,
                        "path": relative.as_posix(),
                        "sha256": _sha256(data),
                    }
                )
        payload = {
            "schema_version": EXPORT_SCHEMA,
            "use": "historical_diagnostics_only",
            "promotion_eligible": False,
            "audited_base_sha": base_sha,
            "dataset_ids": list(selected),
            "files": records,
        }
        envelope = {
            "payload": payload,
            "payload_sha256": _sha256(_canonical_bytes(payload)),
        }
        (staging / "manifest.json").write_bytes(_canonical_bytes(envelope) + b"\n")
        os.replace(staging, output)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return envelope


def _read_export_manifest(export_root: Path) -> tuple[dict[str, Any], str]:
    manifest = _reject_symlink_components(export_root, PurePosixPath("manifest.json"))
    manifest = _under(export_root, manifest, label="export manifest")
    try:
        envelope = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArchiveViolation("historical export manifest is invalid") from exc
    if not isinstance(envelope, dict) or not isinstance(envelope.get("payload"), dict):
        raise ArchiveViolation("historical export envelope is invalid")
    payload = envelope["payload"]
    observed = _sha256(_canonical_bytes(payload))
    if envelope.get("payload_sha256") != observed:
        raise ArchiveViolation("historical export manifest hash mismatch")
    if (
        payload.get("schema_version") != EXPORT_SCHEMA
        or payload.get("use") != "historical_diagnostics_only"
        or payload.get("promotion_eligible") is not False
    ):
        raise ArchiveViolation("historical export is not diagnostic-only")
    _validated_sha(str(payload.get("audited_base_sha", "")))
    return payload, observed


def import_loom_diagnostics(*, export_root: str | Path, output_path: str | Path) -> dict[str, Any]:
    """Verify an export and create a one-way, non-promotable Loom manifest."""

    root = Path(export_root).resolve(strict=True)
    requested_output = Path(output_path)
    output_parent = requested_output.parent.resolve(strict=True)
    output = output_parent / requested_output.name
    if output.exists() or output.is_symlink():
        raise ArchiveViolation("Loom diagnostic output must not already exist")
    try:
        output_parent.relative_to(root)
    except ValueError:
        pass
    else:
        raise ArchiveViolation("Loom diagnostic output must be outside the historical export")
    payload, manifest_hash = _read_export_manifest(root)
    dataset_ids = payload.get("dataset_ids")
    records = payload.get("files")
    if not isinstance(dataset_ids, list) or not all(isinstance(item, str) for item in dataset_ids):
        raise ArchiveViolation("historical export has invalid dataset IDs")
    if not isinstance(records, list):
        raise ArchiveViolation("historical export has invalid file records")

    imported: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise ArchiveViolation("historical export has an invalid file record")
        dataset_id = str(record.get("dataset_id", ""))
        if dataset_id not in dataset_ids:
            raise ArchiveViolation("historical export file uses an undeclared dataset ID")
        _relative_id(dataset_id, label="dataset ID")
        relative = _relative_id(str(record.get("path", "")), label="historical file ID")
        combined = PurePosixPath(dataset_id) / relative
        source_id = combined.as_posix()
        if source_id in seen:
            raise ArchiveViolation("historical export contains a duplicate source ID")
        seen.add(source_id)
        source = _reject_symlink_components(root, combined)
        source = _under(root, source, label=source_id)
        if not source.is_file():
            raise ArchiveViolation(f"historical export file is absent: {source_id}")
        data = source.read_bytes()
        if record.get("bytes") != len(data) or record.get("sha256") != _sha256(data):
            raise ArchiveViolation(f"historical export file hash mismatch: {source_id}")
        imported.append(
            {
                "bytes": len(data),
                "sha256": _sha256(data),
                "source_id": source_id,
            }
        )

    result = {
        "schema_version": LOOM_IMPORT_SCHEMA,
        "use": "diagnostic_only",
        "promotion_eligible": False,
        "source_repository": "delysis/fiction-autoresearch-harness",
        "source_base_sha": payload["audited_base_sha"],
        "source_manifest_sha256": manifest_hash,
        "files": imported,
    }
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(_canonical_bytes(result) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, output)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return result


def _parser(status: Mapping[str, Any]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Archived fiction-harness diagnostic exporter")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="Print the fail-closed archival status")
    export = commands.add_parser("export", help="Export trusted historical datasets")
    export.add_argument("--output", type=Path, required=True)
    export.add_argument(
        "--dataset",
        action="append",
        choices=sorted(status["historical_datasets"]),
        dest="datasets",
        help="Trusted dataset ID; repeat to select more (default: all)",
    )
    loom = commands.add_parser("loom-import", help="Build a verified Loom diagnostic manifest")
    loom.add_argument("--export", type=Path, required=True, dest="export_root")
    loom.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        status = load_archive_status()
        args = _parser(status).parse_args(argv)
        if args.command == "status":
            print(json.dumps(status, indent=2, sort_keys=True))
        elif args.command == "export":
            datasets = args.datasets or sorted(status["historical_datasets"])
            envelope = export_historical_datasets(
                repository_root=PROJECT_ROOT,
                output_root=args.output,
                dataset_roots=status["historical_datasets"],
                selected_dataset_ids=datasets,
                audited_base_sha=status["audited_base_sha"],
            )
            print(envelope["payload_sha256"])
        elif args.command == "loom-import":
            imported = import_loom_diagnostics(
                export_root=args.export_root,
                output_path=args.output,
            )
            print(imported["source_manifest_sha256"])
        return 0
    except ArchiveViolation as exc:
        print(f"ArchiveViolation: {exc}", file=sys.stderr)
        return 2
