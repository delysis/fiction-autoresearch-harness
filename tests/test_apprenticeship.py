from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from fiction_harness.apprenticeship import (
    ApprenticeshipQuery,
    LiteraryWork,
    compile_prompt,
    compile_scene_index,
    render_retrieved_archive,
    retrieve_scenes,
)
from fiction_harness.core import hash_file


def _chapter(label: str, word: str) -> str:
    paragraphs = []
    for index in range(5):
        sentence = (
            f'"Choose and answer me," she said. He waited, touched her hand, '
            f'and considered the secret letter with love, danger, and desire. '
            f'{word} {label} {index}. '
        )
        paragraphs.append((sentence * 28).strip())
    return f"CHAPTER I\n\n" + "\n\n".join(paragraphs)


class LiteraryApprenticeshipTests(unittest.TestCase):
    def _manifest(self, root: Path) -> Path:
        works = []
        for work_id, partition, token, facets in (
            ("alpha.book", "profiling", "orchard", ["adult", "marriage", "dialogue-rich"]),
            ("beta.book", "profiling", "workshop", ["adult", "embodied-intimacy", "sensory-dense"]),
            ("gamma.book", "calibration", "calibrationsecret", ["adult"]),
            ("delta.book", "holdout", "holdoutsecret", ["adult"]),
            ("epsilon.book", "profiling", "desert", ["adult", "coercive", "counterexample"]),
        ):
            path = root / f"{work_id}.txt"
            path.write_text(_chapter(work_id, token), encoding="utf-8")
            works.append({
                "work_id": work_id,
                "title": work_id,
                "author": work_id.split(".")[0],
                "publication_year": 1920,
                "partition": partition,
                "source_url": f"local:{work_id}",
                "local_path": path.name,
                "text_hash": hash_file(path),
                "source_note": "local test fixture",
                "facets": facets,
            })
        manifest = root / "corpus_manifest.v1.json"
        manifest.write_text(json.dumps({"corpus_id": "test", "works": works}), encoding="utf-8")
        return manifest

    def test_source_record_is_plain_descriptive_metadata(self) -> None:
        work = LiteraryWork(
            work_id="rakish.book", title="Rakish", author="A", publication_year=2026,
            partition="profiling", source_url="local:x", local_path="x",
            text_hash="0" * 64, source_note="locally supplied",
        )
        self.assertEqual(work.source_note, "locally supplied")

    def test_index_retrieval_excludes_holdout_calibration_and_counterexample(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self._manifest(root)
            index = compile_scene_index(manifest, root / "index")
            query = ApprenticeshipQuery(
                query_id="q", query_text="married desire secret touch choose",
                stage="transaction", required_facets=("adult",),
                preferred_facets=("marriage", "embodied-intimacy", "sensory-dense"),
                excluded_facets=("coercive", "counterexample"),
                maximum_scenes=4, maximum_per_work=1, source_token_budget=8_000,
            )
            result = retrieve_scenes(root / "index/index_manifest.v1.json", query)
            work_ids = {item["work_id"] for item in result["selected"]}
            self.assertTrue(work_ids <= {"alpha.book", "beta.book"})
            self.assertNotIn("gamma.book", work_ids)
            self.assertNotIn("delta.book", work_ids)
            self.assertNotIn("epsilon.book", work_ids)
            self.assertLessEqual(len(result["selected"]), 2)
            self.assertEqual(index["scene_count"], 25)

    def test_compiled_prompt_is_hash_mapped_and_ends_on_exact_runway(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self._manifest(root)
            compile_scene_index(manifest, root / "index")
            index_path = root / "index/index_manifest.v1.json"
            query = ApprenticeshipQuery(
                query_id="q", query_text="love choice secret",
                stage="approach", required_facets=("adult",),
                excluded_facets=("coercive",), maximum_scenes=2,
                maximum_per_work=1, source_token_budget=8_000,
            )
            retrieval = retrieve_scenes(index_path, query)
            runway = "Prior manuscript.\n\nShe opened the door."
            compiled = compile_prompt(
                index_manifest_path=index_path, retrieval=retrieval,
                target_contract="TARGET CONTRACT\nA choice changes the relationship.",
                runway=runway, output_dir=root / "prompt",
            )
            prompt = Path(compiled["prompt_path"]).read_text(encoding="utf-8")
            self.assertTrue(prompt.endswith(runway))
            self.assertNotIn("holdoutsecret", prompt)
            self.assertNotIn("calibrationsecret", prompt)
            self.assertEqual(compiled["runway_hash"], __import__("hashlib").sha256(runway.encode()).hexdigest())
            self.assertTrue(compiled["source_text_hashes"])
            positions = [item["char_start"] for item in compiled["block_map"]]
            self.assertEqual(positions, sorted(positions))

    def test_compile_rejects_retrieval_from_another_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self._manifest(root)
            compile_scene_index(manifest, root / "index")
            index_path = root / "index/index_manifest.v1.json"
            query = ApprenticeshipQuery("q", "love", "scene")
            retrieval = retrieve_scenes(index_path, query)
            retrieval["index_hash"] = "wrong"
            with self.assertRaisesRegex(ValueError, "another literary index"):
                compile_prompt(
                    index_manifest_path=index_path, retrieval=retrieval,
                    target_contract="contract", runway="runway",
                    output_dir=root / "prompt",
                )

    def test_archive_renders_retrieved_scenes_broad_to_near(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self._manifest(root)
            compile_scene_index(manifest, root / "index")
            index_path = root / "index/index_manifest.v1.json"
            query = ApprenticeshipQuery(
                query_id="q", query_text="love touch choice",
                stage="transaction", required_facets=("adult",),
                excluded_facets=("coercive",), maximum_scenes=2,
                maximum_per_work=1, source_token_budget=8_000,
            )
            retrieval = retrieve_scenes(index_path, query)
            retrieval_path = root / "retrieval.json"
            retrieval_path.write_text(json.dumps(retrieval), encoding="utf-8")
            archive, sources = render_retrieved_archive(
                index_manifest_path=index_path, retrieval_path=retrieval_path,
            )
            self.assertEqual(len(sources), len(retrieval["selected"]))
            self.assertNotIn("holdoutsecret", archive)
            self.assertNotIn("calibrationsecret", archive)
            if len(retrieval["selected"]) == 2:
                strongest = retrieval["selected"][0]["scene_id"]
                self.assertEqual(list(sources)[-1], f"apprenticeship.{strongest}")


if __name__ == "__main__":
    unittest.main()
