from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr

from fiction_harness.archive_quarantine import (
    ArchiveViolation,
    export_historical_datasets,
    import_loom_diagnostics,
    load_archive_status,
)
from fiction_harness.cli import main as legacy_main


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ArchiveQuarantineTests(unittest.TestCase):
    def test_repository_status_is_fail_closed(self) -> None:
        status = load_archive_status()
        self.assertEqual(status["status"], "archived_quarantine")
        self.assertFalse(status["active_release_train"])
        self.assertFalse(status["promotion_eligible"])
        self.assertEqual(
            status["audited_base_sha"],
            "67b6222347e8ddc675f2bfde68ea260bc78764a4",
        )
        release = json.loads(
            (Path(__file__).resolve().parent.parent / "RELEASE_TRAIN.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertFalse(release["active"])
        self.assertEqual(release["promotion_authority"], "none")

    def test_legacy_generation_cli_is_disabled(self) -> None:
        error = io.StringIO()
        with redirect_stderr(error):
            code = legacy_main(["run", "all"])
        self.assertEqual(code, 78)
        self.assertIn("legacy generation and promotion CLI is disabled", error.getvalue())

    def test_export_uses_trusted_dataset_ids_and_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repository"
            (root / "history").mkdir(parents=True)
            (root / "history" / "record.json").write_text(
                '{"historical":true}\n', encoding="utf-8"
            )
            output = Path(temporary) / "export"
            envelope = export_historical_datasets(
                repository_root=root,
                output_root=output,
                dataset_roots={"history": "history"},
                selected_dataset_ids=("history",),
                audited_base_sha="a" * 40,
            )

            payload = envelope["payload"]
            self.assertEqual(payload["use"], "historical_diagnostics_only")
            self.assertFalse(payload["promotion_eligible"])
            self.assertEqual(
                payload["files"],
                [
                    {
                        "bytes": 20,
                        "dataset_id": "history",
                        "path": "record.json",
                        "sha256": _sha256(b'{"historical":true}\n'),
                    }
                ],
            )
            self.assertFalse(Path(payload["files"][0]["path"]).is_absolute())
            self.assertEqual(
                (output / "history" / "record.json").read_bytes(),
                b'{"historical":true}\n',
            )

    def test_export_rejects_unknown_id_and_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repository"
            (root / "history").mkdir(parents=True)
            outside = Path(temporary) / "outside.txt"
            outside.write_text("outside", encoding="utf-8")
            (root / "history" / "escape").symlink_to(outside)

            with self.assertRaisesRegex(ArchiveViolation, "unknown dataset"):
                export_historical_datasets(
                    repository_root=root,
                    output_root=Path(temporary) / "unknown",
                    dataset_roots={"history": "history"},
                    selected_dataset_ids=("artifact-selected-path",),
                    audited_base_sha="a" * 40,
                )
            with self.assertRaisesRegex(ArchiveViolation, "symbolic link"):
                export_historical_datasets(
                    repository_root=root,
                    output_root=Path(temporary) / "escaped",
                    dataset_roots={"history": "history"},
                    selected_dataset_ids=("history",),
                    audited_base_sha="a" * 40,
                )

    def test_loom_import_verifies_bytes_and_carries_no_promotion_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repository"
            (root / "history").mkdir(parents=True)
            (root / "history" / "record.txt").write_text("record\n", encoding="utf-8")
            export_root = Path(temporary) / "export"
            export_historical_datasets(
                repository_root=root,
                output_root=export_root,
                dataset_roots={"history": "history"},
                selected_dataset_ids=("history",),
                audited_base_sha="a" * 40,
            )

            output = Path(temporary) / "loom-import.json"
            imported = import_loom_diagnostics(export_root=export_root, output_path=output)
            self.assertEqual(imported["schema_version"], "loom-diagnostic-import.v1")
            self.assertEqual(imported["use"], "diagnostic_only")
            self.assertFalse(imported["promotion_eligible"])
            self.assertEqual(imported["files"][0]["source_id"], "history/record.txt")
            self.assertNotIn(str(root), output.read_text(encoding="utf-8"))

            (export_root / "history" / "record.txt").write_text("tampered\n", encoding="utf-8")
            with self.assertRaisesRegex(ArchiveViolation, "hash mismatch"):
                import_loom_diagnostics(
                    export_root=export_root,
                    output_path=Path(temporary) / "tampered.json",
                )

    def test_loom_output_cannot_mutate_the_verified_export(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repository"
            (root / "history").mkdir(parents=True)
            (root / "history" / "record.txt").write_text("record\n", encoding="utf-8")
            export_root = Path(temporary) / "export"
            export_historical_datasets(
                repository_root=root,
                output_root=export_root,
                dataset_roots={"history": "history"},
                selected_dataset_ids=("history",),
                audited_base_sha="a" * 40,
            )
            with self.assertRaisesRegex(ArchiveViolation, "outside the historical export"):
                import_loom_diagnostics(
                    export_root=export_root,
                    output_path=export_root / "loom.json",
                )

    def test_manifest_hash_is_checked_before_loom_import(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "export"
            root.mkdir()
            payload = {
                "schema_version": "fiction-historical-export.v1",
                "use": "historical_diagnostics_only",
                "promotion_eligible": False,
                "audited_base_sha": "a" * 40,
                "dataset_ids": [],
                "files": [],
            }
            (root / "manifest.json").write_text(
                json.dumps({"payload": payload, "payload_sha256": "0" * 64}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ArchiveViolation, "manifest hash mismatch"):
                import_loom_diagnostics(
                    export_root=root,
                    output_path=Path(temporary) / "loom.json",
                )


if __name__ == "__main__":
    unittest.main()
