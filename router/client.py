"""Client OpenAI-compatible, stdlib. Locale su Ollama, cloud su Groq o OmniRoute."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass


class ChatError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


@dataclass
class Completion:
    text: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    provider: str


def chat_url(base: str) -> str:
    base = base.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def origin(base: str) -> str:
    parts = urllib.parse.urlsplit(base)
    return f"{parts.scheme}://{parts.netloc}"


class HttpChatClient:
    def __init__(self, base_url: str, provider: str, api_key: str | None = None):
        self.base_url = base_url
        self.provider = provider
        self.api_key = api_key or ""

    def complete(
        self,
        model: str,
        messages: list[dict],
        timeout: int,
        *,
        max_tokens: int | None = None,
        on_delta=None,
    ) -> Completion:
        payload: dict = {"model": model, "messages": messages, "stream": on_delta is not None}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if on_delta is not None:
            payload["stream_options"] = {"include_usage": True}
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            chat_url(self.base_url),
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            response = urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise ChatError(f"{self.provider} ha risposto {exc.code}: {detail}", exc.code) from exc
        except urllib.error.URLError as exc:
            raise ChatError(f"{self.provider} irraggiungibile: {exc.reason}") from exc

        with response:
            provider = response.headers.get("x-omniroute-provider") or self.provider
            if on_delta is None:
                body = json.loads(response.read().decode("utf-8"))
                return _from_body(body, model, provider)
            return _read_stream(response, model, provider, on_delta)


def _from_body(body: dict, model: str, provider: str) -> Completion:
    choices = body.get("choices") or []
    text = ""
    if choices:
        message = choices[0].get("message") or {}
        text = message.get("content") or ""
    usage = body.get("usage") or {}
    return Completion(
        text=text,
        model=body.get("model") or model,
        prompt_tokens=_int_or_none(usage.get("prompt_tokens")),
        completion_tokens=_int_or_none(usage.get("completion_tokens")),
        provider=provider,
    )


def _read_stream(response, model: str, provider: str, on_delta) -> Completion:
    parts: list[str] = []
    prompt_tokens = None
    completion_tokens = None
    seen_model = model
    for raw in response:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        seen_model = chunk.get("model") or seen_model
        usage = chunk.get("usage") or {}
        if usage.get("prompt_tokens") is not None:
            prompt_tokens = _int_or_none(usage.get("prompt_tokens"))
        if usage.get("completion_tokens") is not None:
            completion_tokens = _int_or_none(usage.get("completion_tokens"))
        choices = chunk.get("choices") or []
        if not choices:
            continue
        delta = (choices[0].get("delta") or {}).get("content") or ""
        if not delta:
            delta = (choices[0].get("message") or {}).get("content") or ""
        if delta:
            parts.append(delta)
            on_delta(delta)
    return Completion(
        text="".join(parts),
        model=seen_model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        provider=provider,
    )


def _int_or_none(value) -> int | None:
    if isinstance(value, int):
        return value
    return None


def http_ok(url: str, timeout: float = 2.0) -> bool:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 500
    except urllib.error.HTTPError as exc:
        return exc.code < 500
    except Exception:
        return False
