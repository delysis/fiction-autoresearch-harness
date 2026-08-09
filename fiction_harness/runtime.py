"""Local llama.cpp runtime management and append-only run tracing.

The runtime deliberately uses only the Python standard library.  It can be used
by the CLI, tests, and notebooks without installing a service framework.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
from typing import Any, Iterable, Mapping


LLAMA_SERVER = Path("/Users/george/llama.cpp/build/bin/llama-server")
HF_ROOT = Path("/Users/george/.cache/huggingface/hub")


@dataclass(frozen=True, slots=True)
class ModelProfile:
    """Exact local model role used by the fiction harness."""

    role: str
    alias: str
    model_path: Path
    context_size: int = 65_536
    cache_type: str = "q8_0"
    chat_template: bool = True
    gpu_layers: str | int = "all"


BASE_MODEL_ROOT = Path("/Users/george/.cache/fiction-harness/models")
BASE_MODEL_SNAPSHOTS = {
    "base_ideator": HF_ROOT
    / "models--google--gemma-4-E2B"
    / "snapshots"
    / "9d53598892698e981fc42f78b0f8c005cecd63ca",
    "base_writer": HF_ROOT
    / "models--google--gemma-4-E4B"
    / "snapshots"
    / "4f1d4434cda8f2fc5188e9c8060a081b8fd5eb39",
    "base_31b_writer": HF_ROOT
    / "models--ggml-org--gemma-4-31B-GGUF"
    / "snapshots"
    / "7056174770082d10607fc2e31ef39216b291c0bf",
}


MODEL_PROFILES: dict[str, ModelProfile] = {
    "base_ideator": ModelProfile(
        role="base_ideator",
        alias="gemma-4-e2b-base",
        model_path=BASE_MODEL_ROOT / "gemma-4-E2B-base-Q8_0.gguf",
        chat_template=False,
    ),
    "base_writer": ModelProfile(
        role="base_writer",
        alias="gemma-4-e4b-base",
        model_path=BASE_MODEL_ROOT / "gemma-4-E4B-base-Q8_0.gguf",
        chat_template=False,
    ),
    "base_31b_writer": ModelProfile(
        role="base_31b_writer",
        alias="gemma-4-31b-base",
        model_path=BASE_MODEL_SNAPSHOTS["base_31b_writer"]
        / "gemma-4-31B-Q8_0.gguf",
        context_size=131_072,
        chat_template=False,
    ),
    "base_31b_writer_full": ModelProfile(
        role="base_31b_writer_full",
        alias="gemma-4-31b-base-full",
        model_path=BASE_MODEL_SNAPSHOTS["base_31b_writer"]
        / "gemma-4-31B-Q8_0.gguf",
        # The GGUF declares a native 262,144-token training context. Full-window
        # Q8 KV exceeds the M4 Max's Metal allocation, so this explicit profile
        # trades only KV precision and partial offload for the trained ceiling.
        context_size=262_144,
        cache_type="q4_0",
        chat_template=False,
        # Leave enough Metal headroom for the full-window KV and compute
        # buffers. The remaining transformer layers run from unified CPU
        # memory; shorter-context profiles retain full GPU offload.
        gpu_layers=40,
    ),
    "generator": ModelProfile(
        role="generator",
        alias="gemma-4-26b-a4b",
        model_path=HF_ROOT
        / "models--ggml-org--gemma-4-26B-A4B-it-GGUF"
        / "snapshots"
        / "ae4d537a6345467d1c86bb5cc0d4505ff3ebe0f3"
        / "gemma-4-26B-A4B-it-Q8_0.gguf",
    ),
    "planner": ModelProfile(
        role="planner",
        alias="gemma-4-26b-a4b",
        model_path=HF_ROOT
        / "models--ggml-org--gemma-4-26B-A4B-it-GGUF"
        / "snapshots"
        / "ae4d537a6345467d1c86bb5cc0d4505ff3ebe0f3"
        / "gemma-4-26B-A4B-it-Q8_0.gguf",
    ),
    "editor": ModelProfile(
        role="editor",
        alias="gemma-4-31b",
        model_path=HF_ROOT
        / "models--ggml-org--gemma-4-31B-it-GGUF"
        / "snapshots"
        / "fb5801c702a472691c6eba168f28af79a076fbe9"
        / "gemma-4-31B-it-Q8_0.gguf",
    ),
    "raw_writer": ModelProfile(
        role="raw_writer",
        alias="gemma-4-31b-raw",
        model_path=HF_ROOT
        / "models--ggml-org--gemma-4-31B-it-GGUF"
        / "snapshots"
        / "fb5801c702a472691c6eba168f28af79a076fbe9"
        / "gemma-4-31B-it-Q8_0.gguf",
        chat_template=False,
    ),
    "fast_judge": ModelProfile(
        role="fast_judge",
        alias="gemma-4-e4b",
        model_path=HF_ROOT
        / "models--ggml-org--gemma-4-E4B-it-GGUF"
        / "snapshots"
        / "2714b5519c6c3516b1000e7c5e1eba998dfe1fe8"
        / "gemma-4-E4B-it-Q8_0.gguf",
    ),
}


REDUNDANT_MODEL_COPIES: tuple[tuple[Path, Path], ...] = (
    (
        Path("/Users/george/.llamabarn/gemma-4-E4B-it-Q8_0.gguf"),
        MODEL_PROFILES["fast_judge"].model_path,
    ),
    (
        Path("/Users/george/.llamabarn/gemma-4-31B-it-Q8_0.gguf"),
        MODEL_PROFILES["editor"].model_path,
    ),
    (
        Path("/Users/george/.llamabarn/mmproj-gemma-4-E4B-it-bf16.gguf"),
        HF_ROOT
        / "models--ggml-org--gemma-4-E4B-it-GGUF"
        / "snapshots"
        / "2714b5519c6c3516b1000e7c5e1eba998dfe1fe8"
        / "mmproj-gemma-4-E4B-it-bf16.gguf",
    ),
    (
        Path("/Users/george/.llamabarn/mmproj-gemma-4-31B-it-bf16.gguf"),
        HF_ROOT
        / "models--ggml-org--gemma-4-31B-it-GGUF"
        / "snapshots"
        / "fb5801c702a472691c6eba168f28af79a076fbe9"
        / "mmproj-gemma-4-31B-it-bf16.gguf",
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    """Serialize records deterministically for stable prompts and hashes."""

    if hasattr(value, "to_dict"):
        value = value.to_dict()
    elif is_dataclass(value):
        value = asdict(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


@lru_cache(maxsize=16)
def cached_sha256_file(path_value: str) -> str:
    path = Path(path_value)
    return sha256_file(path) if path.is_file() else ""


def persistent_sha256_file(path_value: str) -> str:
    """Cache a full large-file digest by resolved path, size, and mtime."""

    path = Path(path_value)
    if not path.is_file():
        return ""
    stat = path.stat()
    key = str(path.resolve())
    cache_path = Path("/Users/george/.cache/fiction-harness/sha256-cache-v1.json")
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cache = {}
    record = cache.get(key, {}) if isinstance(cache, dict) else {}
    if (
        record.get("size") == stat.st_size
        and record.get("mtime_ns") == stat.st_mtime_ns
        and isinstance(record.get("sha256"), str)
        and len(record["sha256"]) == 64
    ):
        return record["sha256"]
    digest = sha256_file(path)
    if not isinstance(cache, dict):
        cache = {}
    cache[key] = {
        "size": stat.st_size, "mtime_ns": stat.st_mtime_ns,
        "sha256": digest,
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache_path.with_suffix(cache_path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(cache, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, cache_path)
    return digest


@lru_cache(maxsize=16)
def sampled_file_fingerprint(path_value: str) -> str:
    """Cheap stable identity for very large local model blobs.

    Exact replay is the behavioral witness.  This fingerprint additionally
    binds the call to size plus the first, middle, and final 4 MiB of the GGUF
    without rereading a 30+ GB file for every candidate.
    """

    path = Path(path_value)
    if not path.is_file():
        return ""
    size = path.stat().st_size
    chunk = 4 * 1024 * 1024
    positions = (0, max(0, size // 2 - chunk // 2), max(0, size - chunk))
    digest = hashlib.sha256(str(size).encode("ascii"))
    with path.open("rb") as handle:
        for position in positions:
            handle.seek(position)
            digest.update(handle.read(chunk))
    return digest.hexdigest()


@lru_cache(maxsize=4)
def llama_server_version(server_path: str = str(LLAMA_SERVER)) -> str:
    """Return the local llama.cpp build string once per executable path."""

    path = Path(server_path)
    if not path.is_file() or not os.access(path, os.X_OK):
        return ""
    try:
        result = subprocess.run(
            [str(path), "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (result.stdout or result.stderr).strip()


def model_runtime_provenance(
    model_alias: str,
    *,
    server_path: Path = LLAMA_SERVER,
    version: str | None = None,
) -> dict[str, Any]:
    """Resolve a served alias to its local model blob and runtime build."""

    matches = tuple(
        profile for profile in MODEL_PROFILES.values() if profile.alias == model_alias
    )
    if not matches:
        return {
            "model_alias": model_alias,
            "model_blob": "",
            "model_size_bytes": 0,
            "model_roles": [],
            "llama_server": "",
            "llama_version": "",
            "model_blob_sha256": "",
            "model_blob_sample_sha256": "",
            "llama_server_sha256": "",
        }
    profile = matches[0]
    path = profile.model_path
    return {
        "model_alias": model_alias,
        "model_blob": str(path.resolve(strict=False)),
        "model_size_bytes": path.stat().st_size if path.is_file() else 0,
        "model_blob_sha256": persistent_sha256_file(str(path)),
        "model_blob_sample_sha256": sampled_file_fingerprint(str(path)),
        "model_roles": sorted(profile.role for profile in matches),
        "llama_server": str(server_path.resolve(strict=False)),
        "llama_server_sha256": cached_sha256_file(str(server_path)),
        "llama_version": (
            llama_server_version(str(server_path)) if version is None else version
        ),
    }


def stable_prompt(prefix: str, dynamic: str) -> str:
    """Append variable content without changing a single prefix byte."""

    if not prefix:
        raise ValueError("stable prompt prefix must not be empty")
    if not dynamic:
        raise ValueError("dynamic prompt section must not be empty")
    return prefix + "\n\n<SCENE_VARIABLE_INPUT>\n" + dynamic.strip() + "\n"


def choose_open_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def build_server_command(
    profile: ModelProfile,
    *,
    port: int,
    host: str = "127.0.0.1",
    server_path: Path = LLAMA_SERVER,
    parallel_slots: int = 1,
    batch_size: int = 2_048,
    ubatch_size: int = 512,
) -> list[str]:
    """Return the exact text-only llama-server command for a model role."""

    if parallel_slots < 1:
        raise ValueError("parallel_slots must be positive")
    if not 0 < ubatch_size <= batch_size:
        raise ValueError("require 0 < ubatch_size <= batch_size")

    command = [
        str(server_path),
        "--model",
        str(profile.model_path),
        "--alias",
        profile.alias,
        "--host",
        host,
        "--port",
        str(port),
        "--ctx-size",
        str(profile.context_size),
        "--parallel",
        str(parallel_slots),
        "--cont-batching",
        "--batch-size",
        str(batch_size),
        "--ubatch-size",
        str(ubatch_size),
        "--gpu-layers",
        str(profile.gpu_layers),
        "--flash-attn",
        "on",
        "--cache-type-k",
        profile.cache_type,
        "--cache-type-v",
        profile.cache_type,
        "--swa-full",
        "--kv-unified",
        # Keep in-slot KV prompt reuse, but disable the newer RAM-resident
        # idle-slot cache. With one slot and long non-streaming requests, that
        # cache can retain an orphaned task across client disconnects and stop
        # the server from reading the next request.
        "--cache-ram",
        "0",
        "--no-cache-idle-slots",
        "--cache-prompt",
        "--cache-reuse",
        "256",
        "--no-mmproj",
        "--no-ui",
        "--metrics",
        "--offline",
    ]
    if profile.chat_template:
        insert_at = command.index("--cache-prompt")
        command[insert_at:insert_at] = ["--jinja", "--reasoning", "off"]
    return command


def build_base_conversion_command(
    role: str,
    *,
    python_path: Path,
    converter_path: Path = Path(
        "/Users/george/llama.cpp/convert_hf_to_gguf.py"
    ),
) -> list[str]:
    """Return the exact conversion command without creating any files."""

    if role not in BASE_MODEL_SNAPSHOTS:
        raise ValueError(f"{role} is not a convertible base-model role")
    return [
        str(python_path),
        str(converter_path),
        str(BASE_MODEL_SNAPSHOTS[role]),
        "--outfile",
        str(MODEL_PROFILES[role].model_path),
        "--outtype",
        "q8_0",
    ]


@dataclass(frozen=True, slots=True)
class DuplicateCheck:
    redundant_path: str
    canonical_path: str
    redundant_exists: bool
    redundant_is_symlink: bool
    canonical_exists: bool
    same_size: bool
    byte_identical: bool | None
    reclaimable_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def verify_redundant_copies(*, full_hash: bool = False) -> list[DuplicateCheck]:
    """Inspect duplicate model files without modifying either copy.

    A full hash is intentionally opt-in because the two pairs total about 40 GB.
    Size equality is reported separately and must not be treated as approval to
    delete anything.
    """

    checks: list[DuplicateCheck] = []
    for redundant, canonical in REDUNDANT_MODEL_COPIES:
        redundant_exists = redundant.is_file()
        redundant_is_symlink = redundant.is_symlink()
        canonical_exists = canonical.is_file()
        same_size = (
            redundant_exists
            and canonical_exists
            and redundant.stat().st_size == canonical.stat().st_size
        )
        identical: bool | None = None
        if full_hash and same_size:
            identical = sha256_file(redundant) == sha256_file(canonical)
        checks.append(
            DuplicateCheck(
                redundant_path=str(redundant),
                canonical_path=str(canonical),
                redundant_exists=redundant_exists,
                redundant_is_symlink=redundant_is_symlink,
                canonical_exists=canonical_exists,
                same_size=bool(same_size),
                byte_identical=identical,
                reclaimable_bytes=(
                    redundant.stat().st_size
                    if same_size and not redundant_is_symlink
                    else 0
                ),
            )
        )
    return checks


@dataclass(frozen=True, slots=True)
class PreflightReport:
    ok: bool
    server_path: str
    llama_version: str
    free_bytes: int
    required_free_bytes: int
    models: dict[str, dict[str, Any]]
    duplicate_checks: tuple[dict[str, Any], ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def preflight(
    *,
    data_path: Path,
    minimum_free_gb: float = 5.0,
    profiles: Iterable[ModelProfile] | None = None,
    full_duplicate_hash: bool = False,
    server_path: Path = LLAMA_SERVER,
) -> PreflightReport:
    """Check executable, model files, disk headroom, and duplicate candidates."""

    selected = tuple(MODEL_PROFILES.values() if profiles is None else profiles)
    errors: list[str] = []
    warnings: list[str] = []
    required = int(minimum_free_gb * 1024**3)
    nearest_existing = data_path
    while not nearest_existing.exists() and nearest_existing != nearest_existing.parent:
        nearest_existing = nearest_existing.parent
    free = shutil.disk_usage(nearest_existing).free
    if free < required:
        errors.append(
            f"Only {free / 1024**3:.2f} GiB free; {minimum_free_gb:.2f} GiB required."
        )
    if not server_path.is_file() or not os.access(server_path, os.X_OK):
        errors.append(f"llama-server is missing or not executable: {server_path}")

    models: dict[str, dict[str, Any]] = {}
    seen_paths: set[Path] = set()
    for profile in selected:
        if profile.model_path in seen_paths:
            continue
        seen_paths.add(profile.model_path)
        exists = profile.model_path.is_file()
        size = profile.model_path.stat().st_size if exists else 0
        models[profile.alias] = {
            "path": str(profile.model_path),
            "exists": exists,
            "size_bytes": size,
            "roles": sorted(
                p.role for p in selected if p.model_path == profile.model_path
            ),
        }
        if not exists:
            errors.append(f"Model is missing: {profile.model_path}")

    version = ""
    if server_path.is_file() and os.access(server_path, os.X_OK):
        try:
            result = subprocess.run(
                [str(server_path), "--version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            version = (result.stdout or result.stderr).strip()
            if result.returncode:
                warnings.append(f"llama-server --version exited {result.returncode}")
        except (OSError, subprocess.TimeoutExpired) as exc:
            warnings.append(f"Could not read llama-server version: {exc}")

    duplicate_checks = tuple(
        check.to_dict()
        for check in verify_redundant_copies(full_hash=full_duplicate_hash)
    )
    return PreflightReport(
        ok=not errors,
        server_path=str(server_path),
        llama_version=version,
        free_bytes=free,
        required_free_bytes=required,
        models=models,
        duplicate_checks=duplicate_checks,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


class TraceStore:
    """Append-only JSONL store with last-success lookup for resumable runs."""

    def __init__(self, run_dir: Path):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.calls_path = self.run_dir / "calls.jsonl"
        self.candidates_path = self.run_dir / "candidates.jsonl"
        self.plans_path = self.run_dir / "plans.jsonl"
        self.actor_traces_path = self.run_dir / "actor_traces.jsonl"
        self.candidate_dir = self.run_dir / "candidates"
        self.candidate_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _append(path: Path, record: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = canonical_json(dict(record)) + "\n"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def read(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        records: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc
                if not isinstance(value, dict):
                    raise ValueError(f"Expected JSON object at {path}:{line_number}")
                records.append(value)
        return records

    @staticmethod
    def _latest_completed(
        path: Path, identity_key: str, identity: str
    ) -> dict[str, Any] | None:
        found: dict[str, Any] | None = None
        for record in TraceStore.read(path):
            if (
                record.get(identity_key) == identity
                and record.get("status") == "completed"
            ):
                found = record
        return found

    def completed_call(self, call_id: str) -> dict[str, Any] | None:
        return self._latest_completed(self.calls_path, "call_id", call_id)

    def completed_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        latest = self.latest_candidate_record(candidate_id)
        if latest is None or latest.get("status") != "completed":
            return None
        return latest

    def latest_candidate_record(self, candidate_id: str) -> dict[str, Any] | None:
        """Return the latest append-only record, including partial checkpoints."""

        latest: dict[str, Any] | None = None
        for record in self.read(self.candidates_path):
            if record.get("candidate_id") == candidate_id:
                latest = record
        return latest

    def append_call(self, record: Mapping[str, Any]) -> None:
        self._append(self.calls_path, record)

    def append_plan(self, record: Mapping[str, Any]) -> None:
        self._append(self.plans_path, record)

    def append_actor_trace(self, record: Mapping[str, Any]) -> None:
        self._append(self.actor_traces_path, record)

    def append_candidate(self, record: Mapping[str, Any]) -> None:
        self._append(self.candidates_path, record)
        if record.get("status") == "completed" and isinstance(record.get("text"), str):
            target = self.candidate_dir / f"{record['candidate_id']}.md"
            temporary = target.with_suffix(".md.tmp")
            temporary.write_text(record["text"], encoding="utf-8")
            os.replace(temporary, target)


class LlamaServer:
    """Own one local llama-server process and its log file."""

    def __init__(
        self,
        profile: ModelProfile,
        *,
        port: int | None = None,
        host: str = "127.0.0.1",
        server_path: Path = LLAMA_SERVER,
        log_path: Path | None = None,
    ):
        self.profile = profile
        self.host = host
        self.port = port or choose_open_port(host)
        self.server_path = Path(server_path)
        self.log_path = Path(log_path) if log_path else None
        self.process: subprocess.Popen[bytes] | None = None
        self._log_handle: Any = None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def command(self) -> list[str]:
        return build_server_command(
            self.profile,
            port=self.port,
            host=self.host,
            server_path=self.server_path,
        )

    def start(self) -> "LlamaServer":
        if self.process and self.process.poll() is None:
            return self
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_handle = self.log_path.open("ab")
            stdout = self._log_handle
        else:
            stdout = subprocess.DEVNULL
        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        return self

    def wait_ready(self, timeout: float = 300.0, poll_interval: float = 0.5) -> None:
        from .model_client import LlamaClient, ModelClientError

        deadline = time.monotonic() + timeout
        client = LlamaClient(self.base_url, model=self.profile.alias, timeout=5)
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            if self.process and self.process.poll() is not None:
                raise RuntimeError(
                    f"llama-server exited before becoming ready: {self.process.returncode}"
                )
            try:
                if client.health():
                    return
            except (ModelClientError, OSError) as exc:
                last_error = exc
            time.sleep(poll_interval)
        raise TimeoutError(
            f"llama-server did not become ready in {timeout:.0f}s"
            + (f": {last_error}" if last_error else "")
        )

    def stop(self, timeout: float = 20.0) -> None:
        process = self.process
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if self._log_handle:
            self._log_handle.close()
            self._log_handle = None

    def __enter__(self) -> "LlamaServer":
        return self.start()

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.stop()
