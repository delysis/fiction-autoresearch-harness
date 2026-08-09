from __future__ import annotations

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


LAB_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB_ROOT))

from fiction_harness.compiler import (  # noqa: E402
    compile_trusted_sources,
    parse_scene_spec,
    parse_source_cards,
)
from fiction_harness.core import hash_file, sha256_text  # noqa: E402
from fiction_harness.schemas import PersonaPacket, SceneSpec  # noqa: E402


class CompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scene_read = (
            LAB_ROOT / "bridge/trusted-read-scenes-v01/document-text.md"
        ).read_text(encoding="utf-8")
        cls.canon_read = (
            LAB_ROOT / "bridge/trusted-read-canon-v01/document-text.md"
        ).read_text(encoding="utf-8")
        cls.source_read = (
            LAB_ROOT / "bridge/trusted-read-source-v01/document-text.md"
        ).read_text(encoding="utf-8")

    def test_s01_scene_card_parses_without_rekeying(self) -> None:
        scene = parse_scene_spec(self.scene_read, self.canon_read)
        self.assertIsInstance(scene, SceneSpec)
        self.assertEqual(scene.scene_id, "S01")
        self.assertEqual(scene.title, "The Calibration Game")
        self.assertEqual((scene.target_words_min, scene.target_words_max), (2800, 3600))
        self.assertEqual(len(scene.beat_map), 8)
        self.assertEqual(
            scene.source_ids,
            ("MPC-01", "MPC-05", "MPC-07", "LEV-01", "LEV-02", "LEV-06"),
        )
        self.assertIn("central couple does not consummate", scene.heat_ceiling)

    def test_s02_scene_card_parses_with_continuation_beats(self) -> None:
        scene = parse_scene_spec(self.scene_read, self.canon_read, "S02")
        self.assertEqual(scene.scene_id, "S02")
        self.assertEqual(scene.title, "The Doorway Rule")
        self.assertEqual(len(scene.beat_map), 9)
        self.assertIn("a no is data or a decision", scene.turn)
        self.assertIn("walks Mara home", scene.aftermath)
        self.assertEqual(len(scene.pacing_targets), 7)
        self.assertIn("MPC-11", scene.source_ids)
        self.assertIn("LEV-07", scene.source_ids)

    def test_all_source_cards_and_s01_packet_ids_exist(self) -> None:
        cards = parse_source_cards(self.source_read)
        self.assertEqual(len(cards), 30)
        self.assertIn("signals", cards["LEV-01"]["evidence_or_dynamic"].lower())
        self.assertEqual(cards["MPC-01"]["role"], "CANON")
        scene = parse_scene_spec(self.scene_read, self.canon_read)
        self.assertFalse(set(scene.source_ids) - set(cards))

    def test_compile_is_reproducible_and_manifest_is_complete(self) -> None:
        with TemporaryDirectory() as first_dir, TemporaryDirectory() as second_dir:
            first = compile_trusted_sources(LAB_ROOT, first_dir)
            second = compile_trusted_sources(LAB_ROOT, second_dir)
            self.assertEqual(first.manifest_hash, second.manifest_hash)
            self.assertEqual(first.stable_prefix_hash, second.stable_prefix_hash)
            self.assertEqual(
                first.stable_prefix_path.read_bytes(),
                second.stable_prefix_path.read_bytes(),
            )

            manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["scene_id"], "S01")
            self.assertEqual(len(manifest["sources"]), 4)
            for artifact in manifest["artifacts"]:
                path = first.output_dir / artifact["path"]
                self.assertTrue(path.is_file())
                self.assertEqual(hash_file(path), artifact["sha256"])

            prefix = first.stable_prefix_path.read_text(encoding="utf-8")
            self.assertEqual(sha256_text(prefix), manifest["stable_prefix_sha256"])
            self.assertLess(prefix.index("@@SECTION project_brief"), prefix.index("@@SECTION story_canon"))
            self.assertLess(prefix.index("@@SECTION story_canon"), prefix.index("@@SECTION source_packet"))

    def test_compiled_personas_are_valid_and_fictional_fixture_is_complete(self) -> None:
        with TemporaryDirectory() as output_dir:
            result = compile_trusted_sources(LAB_ROOT, output_dir)
            bundle = json.loads(result.persona_path.read_text(encoding="utf-8"))
            personas = [PersonaPacket.from_dict(item) for item in bundle["personas"]]
            self.assertEqual(
                {persona.persona_id for persona in personas},
                {"mara_vale", "livia_sloane", "jonah_reed"},
            )
            self.assertTrue(all(persona.age is not None and persona.age >= 18 for persona in personas))

    def test_manifest_changes_when_source_text_changes(self) -> None:
        """The pure content hash catches a change without mutating the corpus."""

        original = parse_scene_spec(self.scene_read, self.canon_read)
        changed = parse_scene_spec(
            self.scene_read.replace(
                "At sunset, Mara arrives",
                "At twilight, Mara arrives",
                1,
            ),
            self.canon_read,
        )
        self.assertNotEqual(original.opening_image, changed.opening_image)
        self.assertNotEqual(
            sha256_text(original.opening_image),
            sha256_text(changed.opening_image),
        )


if __name__ == "__main__":
    unittest.main()
