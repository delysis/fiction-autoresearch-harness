"""Cross-process admission for the shared llama.cpp fiction endpoint."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import time
import uuid
from typing import Any

from .core import atomic_write_text


DEFAULT_STATE = Path("/private/tmp/fiction-shared-base31-admission.v1.json")


@dataclass(frozen=True, slots=True)
class EndpointLease:
    lease_id: str
    owner: str
    pid: int
    prompt_hash: str
    prompt_tokens: int
    completion_tokens: int
    admitted_tokens: int
    admitted_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class _LeaseContext:
    def __init__(self, admission: "SharedEndpointAdmission", lease: EndpointLease):
        self.admission = admission
        self.lease = lease

    def __enter__(self) -> EndpointLease:
        return self.lease

    def __exit__(self, *_: object) -> None:
        self.admission.release(self.lease.lease_id)


class SharedEndpointAdmission:
    """Admit requests by slot count and aggregate declared context budget.

    llama.cpp owns scheduling inside the endpoint. This small cross-process
    layer prevents independent experiment controllers from collectively
    declaring more live context than the unified KV pool can hold.
    """

    def __init__(
        self,
        state_path: Path = DEFAULT_STATE,
        *,
        parallel_slots: int = 4,
        slot_context_tokens: int = 32_768,
        reserved_slot_tokens: int = 2_048,
        context_budget_tokens: int = 122_880,
        poll_seconds: float = 0.25,
    ):
        if (
            parallel_slots < 1
            or slot_context_tokens < 1
            or reserved_slot_tokens < 0
            or reserved_slot_tokens >= slot_context_tokens
            or context_budget_tokens < 1
            or poll_seconds <= 0
        ):
            raise ValueError("invalid shared-endpoint admission geometry")
        self.state_path = state_path
        self.lock_path = state_path.with_suffix(state_path.suffix + ".lock")
        self.parallel_slots = parallel_slots
        self.slot_context_tokens = slot_context_tokens
        self.reserved_slot_tokens = reserved_slot_tokens
        self.context_budget_tokens = context_budget_tokens
        self.poll_seconds = poll_seconds

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def _read(self) -> list[dict[str, Any]]:
        if not self.state_path.is_file():
            return []
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        leases = value.get("leases", []) if isinstance(value, dict) else []
        return [item for item in leases if isinstance(item, dict)]

    def _write(self, leases: list[dict[str, Any]]) -> None:
        payload = {
            "schema_version": "shared-endpoint-admission.v1",
            "parallel_slots": self.parallel_slots,
            "slot_context_tokens": self.slot_context_tokens,
            "reserved_slot_tokens": self.reserved_slot_tokens,
            "context_budget_tokens": self.context_budget_tokens,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "leases": leases,
        }
        atomic_write_text(
            self.state_path,
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        )

    def acquire(
        self,
        *,
        owner: str,
        prompt_hash: str,
        prompt_tokens: int,
        completion_tokens: int,
        timeout_seconds: float = 7_200,
    ) -> _LeaseContext:
        requested = prompt_tokens + completion_tokens
        if not owner.strip() or not prompt_hash.strip():
            raise ValueError("owner and prompt_hash are required")
        if prompt_tokens < 1 or completion_tokens < 1:
            raise ValueError("declared token counts must be positive")
        safe_slot_tokens = self.slot_context_tokens - self.reserved_slot_tokens
        if requested > safe_slot_tokens:
            raise ValueError(
                f"request declares {requested} tokens but per-slot safe limit is "
                f"{safe_slot_tokens}"
            )
        if requested > self.context_budget_tokens:
            raise ValueError(
                f"request declares {requested} tokens but endpoint budget is "
                f"{self.context_budget_tokens}"
            )
        deadline = time.monotonic() + timeout_seconds
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            with self.lock_path.open("a+", encoding="utf-8") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                active = [
                    item
                    for item in self._read()
                    if self._pid_alive(int(item.get("pid", -1)))
                ]
                used = sum(int(item.get("admitted_tokens", 0)) for item in active)
                if (
                    len(active) < self.parallel_slots
                    and used + requested <= self.context_budget_tokens
                ):
                    lease = EndpointLease(
                        lease_id=uuid.uuid4().hex,
                        owner=owner.strip(),
                        pid=os.getpid(),
                        prompt_hash=prompt_hash.strip(),
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        admitted_tokens=requested,
                        admitted_at=datetime.now(timezone.utc).isoformat(),
                    )
                    active.append(lease.to_dict())
                    self._write(active)
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
                    return _LeaseContext(self, lease)
                self._write(active)
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            if time.monotonic() >= deadline:
                raise TimeoutError("timed out waiting for shared endpoint admission")
            time.sleep(self.poll_seconds)

    def release(self, lease_id: str) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            active = [
                item
                for item in self._read()
                if item.get("lease_id") != lease_id
                and self._pid_alive(int(item.get("pid", -1)))
            ]
            self._write(active)
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
