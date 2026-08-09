from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


LAB_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB_ROOT))

from fiction_harness.model_client import LlamaClient  # noqa: E402
from fiction_harness.runtime import (  # noqa: E402
    LLAMA_SERVER,
    MODEL_PROFILES,
    ModelProfile,
    TraceStore,
    build_server_command,
    model_runtime_provenance,
    preflight,
    stable_prompt,
)


class _HTTPResponse:
    def __init__(self, value: dict):
        self.body = json.dumps(value).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self) -> bytes:
        return self.body


class _SSEHTTPResponse:
    def __init__(self, events: list[dict]):
        self.lines = iter(
            [
                ("data: " + json.dumps(event) + "\n").encode()
                for event in events
            ]
        )
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True
        return None

    def readline(self) -> bytes:
        return next(self.lines, b"")


class RuntimeTests(unittest.TestCase):
    def test_31b_base_role_uses_native_completion_transport(self) -> None:
        profile = MODEL_PROFILES["base_31b_writer"]
        self.assertFalse(profile.chat_template)
        self.assertEqual(profile.alias, "gemma-4-31b-base")
        self.assertEqual(profile.context_size, 131_072)
        self.assertTrue(str(profile.model_path).endswith("gemma-4-31B-Q8_0.gguf"))

    def test_31b_full_context_profile_records_memory_tradeoff(self) -> None:
        profile = MODEL_PROFILES["base_31b_writer_full"]
        self.assertFalse(profile.chat_template)
        self.assertEqual(profile.context_size, 262_144)
        self.assertEqual(profile.cache_type, "q4_0")
        self.assertEqual(profile.gpu_layers, 40)
        self.assertEqual(
            profile.model_path, MODEL_PROFILES["base_31b_writer"].model_path
        )

    def test_runtime_provenance_resolves_alias_without_hashing_model(self) -> None:
        provenance = model_runtime_provenance(
            MODEL_PROFILES["generator"].alias,
            version="llama.cpp fixture",
        )
        self.assertEqual(
            provenance["model_blob"],
            str(MODEL_PROFILES["generator"].model_path.resolve(strict=False)),
        )
        self.assertEqual(provenance["llama_version"], "llama.cpp fixture")
        self.assertEqual(provenance["model_roles"], ["generator", "planner"])
        self.assertEqual(provenance["llama_server"], str(LLAMA_SERVER))

    def test_server_command_has_text_cache_and_single_slot_flags(self) -> None:
        profile = ModelProfile(
            role="generator",
            alias="fixture",
            model_path=Path("/tmp/fixture.gguf"),
        )
        command = build_server_command(
            profile, port=8811, server_path=Path("/tmp/llama-server")
        )
        joined = " ".join(command)
        self.assertIn("--ctx-size 65536", joined)
        self.assertIn("--parallel 1", joined)
        self.assertIn("--cont-batching", command)
        self.assertIn("--batch-size 2048", joined)
        self.assertIn("--ubatch-size 512", joined)
        self.assertIn("--cache-type-k q8_0", joined)
        self.assertIn("--cache-type-v q8_0", joined)
        self.assertIn("--cache-reuse 256", joined)
        self.assertIn("--cache-ram 0", joined)
        self.assertIn("--no-cache-idle-slots", command)
        self.assertIn("--swa-full", command)
        self.assertIn("--kv-unified", command)
        self.assertIn("--no-mmproj", command)
        self.assertIn("--offline", command)

    def test_server_command_can_expose_shared_continuous_batch_slots(self) -> None:
        profile = ModelProfile(
            role="base_writer",
            alias="fixture",
            model_path=Path("/tmp/fixture.gguf"),
            context_size=131_072,
        )
        command = build_server_command(
            profile,
            port=8097,
            server_path=Path("/tmp/llama-server"),
            parallel_slots=4,
        )
        joined = " ".join(command)
        self.assertIn("--parallel 4", joined)
        self.assertIn("--ctx-size 131072", joined)

    def test_server_command_rejects_invalid_batch_geometry(self) -> None:
        profile = ModelProfile(
            role="base_writer",
            alias="fixture",
            model_path=Path("/tmp/fixture.gguf"),
        )
        with self.assertRaises(ValueError):
            build_server_command(profile, port=8097, parallel_slots=0)
        with self.assertRaises(ValueError):
            build_server_command(
                profile, port=8097, batch_size=512, ubatch_size=1024
            )

    def test_stable_prompt_preserves_prefix_bytes(self) -> None:
        prefix = "FIRST\r\nbyte-sensitive \n"
        output = stable_prompt(prefix, "variable")
        self.assertTrue(output.startswith(prefix))
        self.assertEqual(output[: len(prefix)], prefix)

    def test_trace_store_returns_latest_completed_and_writes_scene(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = TraceStore(Path(directory))
            store.append_call({"call_id": "x", "status": "started"})
            store.append_call(
                {"call_id": "x", "status": "completed", "result": {"content": "ok"}}
            )
            self.assertEqual(
                store.completed_call("x")["result"]["content"],  # type: ignore[index]
                "ok",
            )
            store.append_candidate(
                {
                    "candidate_id": "c1",
                    "status": "completed",
                    "text": "Finished fiction.",
                }
            )
            self.assertEqual(
                (Path(directory) / "candidates" / "c1.md").read_text(),
                "Finished fiction.",
            )
            store.append_candidate(
                {
                    "candidate_id": "c1",
                    "status": "invalidated",
                    "reason": "token-cut ending",
                }
            )
            self.assertIsNone(store.completed_candidate("c1"))
            self.assertEqual(
                store.latest_candidate_record("c1")["status"],  # type: ignore[index]
                "invalidated",
            )
            self.assertIsNone(store.latest_candidate_record("missing"))

    def test_preflight_reports_missing_executable_model_and_space(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = ModelProfile(
                role="fixture", alias="missing", model_path=root / "missing.gguf"
            )
            report = preflight(
                data_path=root,
                minimum_free_gb=10**9,
                profiles=[profile],
                server_path=root / "missing-server",
            )
            self.assertFalse(report.ok)
            self.assertGreaterEqual(len(report.errors), 3)

    def test_client_parses_content_usage_and_cache(self) -> None:
        payload = {
            "model": "fixture",
            "choices": [
                {
                    "message": {"content": "scene", "reasoning_content": ""},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "prompt_tokens_details": {"cached_tokens": 80},
            },
            "timings": {"prompt_n": 20, "cache_n": 80},
        }
        with patch(
            "fiction_harness.model_client.request.urlopen",
            return_value=_HTTPResponse(payload),
        ):
            client = LlamaClient("http://localhost:1", model="fixture")
            completion = client.complete(
                prompt="hello", seed=1, max_tokens=10, temperature=0.9
            )
        self.assertEqual(completion.content, "scene")
        self.assertEqual(completion.cache["cached_tokens"], 80)
        self.assertEqual(completion.cache["cache_n"], 80)

    def test_raw_stream_closes_connection_when_guard_raises(self) -> None:
        response = _SSEHTTPResponse(
            [{"content": "first "}, {"content": "forbidden"}, {"stop": True}]
        )

        def guard(delta: str) -> None:
            if "forbidden" in delta:
                raise RuntimeError("copy")

        with patch(
            "fiction_harness.model_client.request.urlopen",
            return_value=response,
        ):
            client = LlamaClient("http://localhost:1", model="base")
            with self.assertRaisesRegex(RuntimeError, "copy"):
                client.stream_raw(
                    prompt="raw",
                    seed=1,
                    max_tokens=10,
                    on_delta=guard,
                )
        self.assertTrue(response.closed)


if __name__ == "__main__":
    unittest.main()
