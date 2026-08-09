"""Small OpenAI-compatible client for a local llama.cpp server."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import time
from typing import Any, Callable, Mapping, Sequence
from urllib import error, request


class ModelClientError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Completion:
    content: str
    model: str
    finish_reason: str
    usage: dict[str, Any]
    timings: dict[str, Any]
    cache: dict[str, Any]
    elapsed_seconds: float
    raw: dict[str, Any]
    reasoning_content: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LlamaClient:
    """Call llama-server's OpenAI-compatible chat completion endpoint."""

    def __init__(
        self,
        base_url: str,
        *,
        model: str,
        timeout: float = 1_200.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def _json_request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = request.Request(
            self.base_url + path, data=body, headers=headers, method=method
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ModelClientError(
                f"llama-server returned HTTP {exc.code}: {detail[:1000]}"
            ) from exc
        except error.URLError as exc:
            raise ModelClientError(f"Could not reach llama-server: {exc.reason}") from exc
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ModelClientError("llama-server returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise ModelClientError("llama-server returned a non-object JSON response")
        return value

    def health(self) -> bool:
        value = self._json_request("GET", "/health")
        return value.get("status") in {"ok", "ready"}

    def models(self) -> list[dict[str, Any]]:
        value = self._json_request("GET", "/v1/models")
        data = value.get("data", [])
        return [item for item in data if isinstance(item, dict)]

    def props(self) -> dict[str, Any]:
        """Return llama.cpp's actual loaded-model and sampler/build properties."""

        return self._json_request("GET", "/props")

    def slots(self) -> list[dict[str, Any]]:
        req = request.Request(
            self.base_url + "/slots",
            headers={"Accept": "application/json"},
            method="GET",
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                value = json.loads(response.read().decode("utf-8"))
        except (error.HTTPError, error.URLError, json.JSONDecodeError) as exc:
            raise ModelClientError(f"could not inspect llama-server slots: {exc}") from exc
        if not isinstance(value, list):
            raise ModelClientError("llama-server /slots returned a non-list")
        return [item for item in value if isinstance(item, dict)]

    def erase_idle_slots(self) -> list[dict[str, Any]]:
        """Erase reusable KV state before a reproducibility witness."""

        erased: list[dict[str, Any]] = []
        for slot in self.slots():
            if slot.get("is_processing"):
                raise ModelClientError(
                    "cannot establish a cold replay while another slot is active"
                )
            slot_id = int(slot["id"])
            req = request.Request(
                self.base_url + f"/slots/{slot_id}?action=erase",
                data=b"",
                headers={"Accept": "application/json"},
                method="POST",
            )
            try:
                with request.urlopen(req, timeout=self.timeout) as response:
                    value = json.loads(response.read().decode("utf-8"))
            except (error.HTTPError, error.URLError, json.JSONDecodeError) as exc:
                raise ModelClientError(
                    f"could not erase llama-server slot {slot_id}: {exc}"
                ) from exc
            if not isinstance(value, dict):
                raise ModelClientError("llama-server slot erase returned a non-object")
            erased.append(value)
        return erased

    def token_count(self, text: str) -> int:
        """Return the server tokenizer's exact token count for a prompt."""

        if not text:
            return 0
        value = self._json_request(
            "POST",
            "/tokenize",
            {"content": text, "add_special": False, "with_pieces": False},
        )
        tokens = value.get("tokens", [])
        if not isinstance(tokens, list):
            raise ModelClientError("Tokenize response contains no token list")
        return len(tokens)

    def complete(
        self,
        *,
        prompt: str | None = None,
        messages: Sequence[Mapping[str, str]] | None = None,
        seed: int,
        max_tokens: int,
        temperature: float = 0.9,
        top_p: float = 0.95,
        min_p: float = 0.03,
        response_format: Mapping[str, Any] | None = None,
        stop: Sequence[str] | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> Completion:
        if (prompt is None) == (messages is None):
            raise ValueError("Provide exactly one of prompt or messages")
        if prompt is not None:
            messages = [{"role": "user", "content": prompt}]
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": list(messages or []),
            "seed": seed,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "min_p": min_p,
            "stream": False,
            "cache_prompt": True,
        }
        if response_format:
            payload["response_format"] = dict(response_format)
        if stop:
            payload["stop"] = list(stop)
        if extra:
            payload.update(extra)

        started = time.monotonic()
        value = self._json_request("POST", "/v1/chat/completions", payload)
        elapsed = time.monotonic() - started
        choices = value.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ModelClientError("Completion response contains no choices")
        choice = choices[0]
        message = choice.get("message", {}) if isinstance(choice, dict) else {}
        content = message.get("content", "") if isinstance(message, dict) else ""
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        usage = value.get("usage", {})
        timings = value.get("timings", {})
        if not isinstance(usage, dict):
            usage = {}
        if not isinstance(timings, dict):
            timings = {}
        cache = {
            key: value
            for key, value in {
                "prompt_tokens": usage.get("prompt_tokens"),
                "cached_tokens": usage.get("prompt_tokens_details", {}).get(
                    "cached_tokens"
                )
                if isinstance(usage.get("prompt_tokens_details"), dict)
                else None,
                "cache_n": timings.get("cache_n"),
                "prompt_n": timings.get("prompt_n"),
            }.items()
            if value is not None
        }
        return Completion(
            content=content,
            reasoning_content=str(message.get("reasoning_content", ""))
            if isinstance(message, dict)
            else "",
            model=str(value.get("model", self.model)),
            finish_reason=str(choice.get("finish_reason", ""))
            if isinstance(choice, dict)
            else "",
            usage=usage,
            timings=timings,
            cache=cache,
            elapsed_seconds=elapsed,
            raw=value,
        )

    @staticmethod
    def _raw_completion(
        value: Mapping[str, Any],
        *,
        model: str,
        elapsed: float,
        content: str | None = None,
    ) -> Completion:
        text = value.get("content", "") if content is None else content
        if not isinstance(text, str):
            text = str(text)
        timings = value.get("timings", {})
        if not isinstance(timings, dict):
            timings = {}
        prompt_tokens = value.get("tokens_evaluated", timings.get("prompt_n"))
        completion_tokens = value.get(
            "tokens_predicted", timings.get("predicted_n")
        )
        usage = {
            key: item
            for key, item in {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }.items()
            if item is not None
        }
        cache = {
            key: item
            for key, item in {
                "cache_n": timings.get("cache_n"),
                "prompt_n": timings.get("prompt_n"),
            }.items()
            if item is not None
        }
        finish_reason = (
            "length"
            if value.get("stopped_limit")
            else "stop"
            if value.get("stop", True)
            else ""
        )
        return Completion(
            content=text,
            reasoning_content="",
            model=str(value.get("model", model)),
            finish_reason=finish_reason,
            usage=usage,
            timings=timings,
            cache=cache,
            elapsed_seconds=elapsed,
            raw=dict(value),
        )

    @staticmethod
    def _raw_payload(
        *,
        prompt: str,
        seed: int,
        max_tokens: int,
        temperature: float,
        top_p: float,
        min_p: float,
        xtc_probability: float,
        stream: bool,
        stop: Sequence[str] | None,
        extra: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        if not prompt:
            raise ValueError("raw completion prompt must not be empty")
        payload: dict[str, Any] = {
            "prompt": prompt,
            "seed": seed,
            "n_predict": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "min_p": min_p,
            "xtc_probability": xtc_probability,
            "stream": stream,
            "cache_prompt": True,
            "speculative": False,
        }
        if stop:
            payload["stop"] = list(stop)
        if extra:
            payload.update(extra)
        return payload

    def complete_raw(
        self,
        *,
        prompt: str,
        seed: int,
        max_tokens: int,
        temperature: float = 0.9,
        top_p: float = 0.95,
        min_p: float = 0.02,
        xtc_probability: float = 0.05,
        stop: Sequence[str] | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> Completion:
        """Call llama.cpp's native completion endpoint without a chat template."""

        payload = self._raw_payload(
            prompt=prompt,
            seed=seed,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            min_p=min_p,
            xtc_probability=xtc_probability,
            stream=False,
            stop=stop,
            extra=extra,
        )
        started = time.monotonic()
        value = self._json_request("POST", "/completion", payload)
        return self._raw_completion(
            value,
            model=self.model,
            elapsed=time.monotonic() - started,
        )

    def stream_raw(
        self,
        *,
        prompt: str,
        seed: int,
        max_tokens: int,
        on_delta: Callable[[str], None],
        temperature: float = 0.9,
        top_p: float = 0.95,
        min_p: float = 0.02,
        xtc_probability: float = 0.05,
        stop: Sequence[str] | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> Completion:
        """Stream a raw base-model completion and permit immediate cancellation.

        ``on_delta`` may raise (for example, on a forbidden source shingle).
        Exiting the response context closes the HTTP connection, which causes
        llama-server to cancel the active slot.
        """

        payload = self._raw_payload(
            prompt=prompt,
            seed=seed,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            min_p=min_p,
            xtc_probability=xtc_probability,
            stream=True,
            stop=stop,
            extra=extra,
        )
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            self.base_url + "/completion",
            data=body,
            headers={
                "Accept": "text/event-stream",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        started = time.monotonic()
        text_parts: list[str] = []
        final: dict[str, Any] = {}
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                while True:
                    raw_line = response.readline()
                    if not raw_line:
                        break
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line or line.startswith(":"):
                        continue
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    event = json.loads(data)
                    if not isinstance(event, dict):
                        continue
                    delta = event.get("content", "")
                    if isinstance(delta, str) and delta:
                        on_delta(delta)
                        text_parts.append(delta)
                    if event.get("stop"):
                        final = event
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ModelClientError(
                f"llama-server returned HTTP {exc.code}: {detail[:1000]}"
            ) from exc
        except error.URLError as exc:
            raise ModelClientError(
                f"Could not reach llama-server: {exc.reason}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise ModelClientError(
                "llama-server returned invalid streaming JSON"
            ) from exc
        elapsed = time.monotonic() - started
        final.setdefault("content", "".join(text_parts))
        timings = final.get("timings", {})
        predicted = final.get("tokens_predicted")
        if predicted is None and isinstance(timings, Mapping):
            predicted = timings.get("predicted_n")
        # Some streaming llama.cpp responses report only `stop: true` when
        # they exhaust n_predict. Recover the accurate completion reason from
        # the generated-token count so a clipped manuscript cannot masquerade
        # as a natural stop.
        if isinstance(predicted, (int, float)) and predicted >= max_tokens:
            final["stopped_limit"] = True
        return self._raw_completion(
            final,
            model=self.model,
            elapsed=elapsed,
            content="".join(text_parts),
        )
