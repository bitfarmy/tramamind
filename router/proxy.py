"""Proxy OpenAI-compatible. Stesso tetto della chat, senza un secondo modello.

Gli ultimi messaggi restano gli oggetti originali. Il codice recente non viene
riscritto. Dei turni vecchi restano un estratto e, se ci stanno, fino a due
blocchi di codice parola per parola. Nessun modello viene chiamato per
riassumere: il client di coding ha già il suo modello caricato.
"""
from __future__ import annotations

import json
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from router.packet import (
    MESSAGE_OVERHEAD,
    code_fences,
    compact_message,
    estimate_tokens,
    fit_summary,
    message_excerpts,
    plain_prose,
    split_history,
)

DEFAULT_UPSTREAM = "http://127.0.0.1:11434/v1"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8788
DEFAULT_BUDGET = 2500
DEFAULT_VERBATIM = 6
UPSTREAM_TIMEOUT = 300
MAX_BODY = 32_000_000

NOTE_PREFIX = (
    "Earlier turns were compacted to fit a token budget. "
    "Recent turns are verbatim. "
    "Code blocks in this note are verbatim excerpts.\n\n"
)

DEMO_FENCE = "```python\ndef add(a, b):\n    return a + b\n```"
DEMO_MARKER = "UNIQUE_OLD_PROSE_MARKER"
DEMO_LAST = "What does add return?"


def message_text(message: dict) -> str:
    content = message.get("content")
    parts: list[str] = []
    if isinstance(content, str):
        parts.append(content)
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and "text" in part:
                parts.append(str(part.get("text") or ""))
            elif isinstance(part, dict) and part.get("type") == "image_url":
                parts.append("[image]")
    elif content is not None:
        parts.append(str(content))
    calls = message.get("tool_calls")
    if calls:
        parts.append(json.dumps(calls, ensure_ascii=False))
    return "\n".join(part for part in parts if part)


def _tokens(messages: list[dict]) -> int:
    total = 0
    for message in messages:
        total += estimate_tokens(message_text(message)) + MESSAGE_OVERHEAD
    return total


def _split_instructions(messages: list[dict]) -> tuple[list[dict], list[dict]]:
    index = 0
    while index < len(messages) and messages[index].get("role") in ("system", "developer"):
        index += 1
    return messages[:index], messages[index:]


def _extractive(messages: list[dict]) -> str:
    lines = []
    for message in messages:
        role = message.get("role") or "message"
        who = {"user": "User", "assistant": "Assistant", "tool": "Tool"}.get(role, role)
        name = message.get("name")
        label = f"{who} ({name})" if name else who
        lines.append(f"{label}: {compact_message(message_text(message), 400)}")
    text = "\n".join(lines)
    if len(text) > 1600:
        text = text[:1600].rstrip() + "…"
    return text


def compact_messages(
    messages: list[dict],
    budget: int = DEFAULT_BUDGET,
    verbatim: int = DEFAULT_VERBATIM,
) -> dict:
    if not isinstance(messages, list) or any(not isinstance(item, dict) for item in messages):
        raise ValueError("messages must be a list of objects")
    budget = max(int(budget), 1)
    verbatim = max(int(verbatim), 1)
    raw_tokens = _tokens(messages)
    instructions, history = _split_instructions(messages)
    if not history:
        return {
            "messages": messages,
            "raw_tokens": raw_tokens,
            "sent_tokens": raw_tokens,
            "summarized": False,
        }
    system_text = "\n\n".join(message_text(item) for item in instructions)
    text_history = [
        {"role": item.get("role") or "user", "content": message_text(item)} for item in history
    ]
    head, tail = split_history(text_history, budget, verbatim, system_text)
    if not head:
        return {
            "messages": messages,
            "raw_tokens": raw_tokens,
            "sent_tokens": raw_tokens,
            "summarized": False,
        }
    tail_n = len(tail)
    original_head = history[:-tail_n] if tail_n else history
    original_tail = history[-tail_n:] if tail_n else []
    prose = plain_prose(_extractive(original_head))
    fences = code_fences(text_history[: len(original_head)], "")
    fitted = fit_summary(system_text, prose, fences, text_history[-tail_n:], budget)
    outbound = list(instructions)
    if fitted:
        outbound.append({"role": "system", "content": NOTE_PREFIX + fitted})
    outbound.extend(original_tail)
    return {
        "messages": outbound,
        "raw_tokens": raw_tokens,
        "sent_tokens": _tokens(outbound),
        "summarized": True,
    }


def savings_line(
    raw_tokens: int,
    sent_tokens: int,
    summarized: bool,
    api_tokens: int | None = None,
) -> str:
    if summarized and raw_tokens > sent_tokens:
        saved = round(100 * (raw_tokens - sent_tokens) / raw_tokens)
        line = f"storia intera ~{raw_tokens} · inviati ~{sent_tokens} · −{saved}%"
    else:
        line = f"storia nel tetto · ~{sent_tokens}"
    if isinstance(api_tokens, int):
        line += f" · api {api_tokens}"
    return line


def prompt_tokens_of(payload: bytes) -> int | None:
    try:
        body = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(body, dict):
        return None
    usage = body.get("usage")
    if not isinstance(usage, dict):
        return None
    value = usage.get("prompt_tokens")
    return value if isinstance(value, int) else None


def prompt_tokens_of_sse_line(line: bytes) -> int | None:
    stripped = line.strip()
    if not stripped.startswith(b"data:"):
        return None
    data = stripped[5:].strip()
    if not data or data == b"[DONE]":
        return None
    return prompt_tokens_of(data)


def demo_messages() -> list[dict]:
    """Chat finta, stabile. Il blocco di codice è vecchio: non sta negli ultimi turni."""
    messages: list[dict] = [
        {"role": "system", "content": "You are a coding assistant. Quote code exactly."}
    ]
    for index in range(10):
        messages.append({
            "role": "user",
            "content": (
                f"Turn {index}. "
                + ("We discussed the cache layout and the retry policy. " * 40)
                + DEMO_MARKER
            ),
        })
        reply = "Noted. " + ("The cache key stays the prompt hash. " * 30)
        if index == 1:
            reply += "\n" + DEMO_FENCE
        messages.append({"role": "assistant", "content": reply})
    for index in range(3):
        messages.append({
            "role": "user",
            "content": f"Later {index}. " + ("Continue from the current function only. " * 20),
        })
        messages.append({"role": "assistant", "content": "Continuing. " + ("No extra files. " * 12)})
    messages.append({"role": "user", "content": DEMO_LAST})
    return messages


def render_demo(budget: int = DEFAULT_BUDGET, verbatim: int = DEFAULT_VERBATIM) -> str:
    messages = demo_messages()
    report = compact_messages(messages, budget, verbatim)
    blob = "\n".join(message_text(item) for item in report["messages"])
    code_ok = "def add(a, b):" in blob and "return a + b" in blob
    last_ok = report["messages"][-1] is messages[-1]
    raw = report["raw_tokens"]
    sent = report["sent_tokens"]
    saved = round(100 * (raw - sent) / raw) if raw > sent else 0
    code_line = (
        "code kept verbatim: def add(a, b)"
        if code_ok
        else "code missing from packet"
    )
    last_line = (
        f"last user message kept: {DEMO_LAST}"
        if last_ok
        else "last user message rewritten"
    )
    return (
        f"full history ~{raw} · packet ~{sent} · −{saved}%\n"
        f"{code_line}\n"
        f"{last_line}"
    )


def _preview(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("```")]
    if not lines:
        lines = [text.strip()]
    chosen = lines[-1] if text.startswith("Traceback") else lines[0]
    return chosen[:80]


def _kind(text: str) -> str:
    if text.startswith("```"):
        return "codice"
    if text.startswith("diff --git ") or text.startswith("--- "):
        return "diff"
    if text.startswith("Traceback"):
        return "traceback"
    return "tool"


def describe_kept(messages: list[dict], report: dict) -> list[tuple[str, str]]:
    blob = "\n".join(message_text(item) for item in report["messages"])
    outbound = report["messages"]
    rows: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for message in messages:
        if message.get("role") in ("system", "developer"):
            continue
        whole = message in outbound
        for piece in message_excerpts(message):
            if not whole and piece not in blob:
                continue
            row = (_kind(piece), _preview(piece))
            if row not in seen and row[1]:
                seen.add(row)
                rows.append(row)
    return rows


def render_pack(
    messages: list[dict],
    budget: int = DEFAULT_BUDGET,
    verbatim: int = DEFAULT_VERBATIM,
) -> tuple[str, dict]:
    report = compact_messages(messages, budget, verbatim)
    parts = [savings_line(report["raw_tokens"], report["sent_tokens"], report["summarized"])]
    kept = describe_kept(messages, report)
    if kept:
        parts.append("blocchi conservati:")
        for kind, preview in kept:
            parts.append(f"  {kind}: {preview}")
    users = [item for item in messages if item.get("role") == "user"]
    if users:
        last = users[-1]
        first = message_text(last).strip().splitlines()
        preview = (first[0] if first else "")[:80]
        if last in report["messages"]:
            parts.append(f"ultimo messaggio utente: {preview}")
        else:
            parts.append("ultimo messaggio utente riscritto")
    return "\n".join(parts), report


def load_transcript(path: str) -> list[dict]:
    file = Path(path)
    if file.stat().st_size > MAX_BODY:
        raise ValueError("file troppo grande")
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"json non valido: {exc.msg}") from exc
    if isinstance(data, dict) and isinstance(data.get("messages"), list):
        messages = data["messages"]
    elif isinstance(data, list):
        messages = data
    else:
        raise ValueError("atteso un array di messaggi, oppure un oggetto con la chiave messages")
    if any(not isinstance(item, dict) for item in messages):
        raise ValueError("ogni messaggio deve essere un oggetto")
    return messages


def run_pack(path: str, budget: int, verbatim: int, out: str | None = None) -> str:
    messages = load_transcript(path)
    text, report = render_pack(messages, budget, verbatim)
    if out:
        Path(out).write_text(
            json.dumps(report["messages"], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return text


def upstream_url(upstream: str, path: str) -> str:
    base = upstream.rstrip("/")
    path_only, _, query = path.partition("?")
    if not path_only.startswith("/"):
        path_only = "/" + path_only
    if base.endswith("/v1") and (path_only == "/v1" or path_only.startswith("/v1/")):
        path_only = path_only[3:] or "/"
    url = base + path_only
    if query:
        url += "?" + query
    return url


def _saved_pct(raw_tokens: int, sent_tokens: int) -> int:
    if raw_tokens <= sent_tokens:
        return 0
    return round(100 * (raw_tokens - sent_tokens) / raw_tokens)


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    upstream = DEFAULT_UPSTREAM
    budget = DEFAULT_BUDGET
    verbatim = DEFAULT_VERBATIM

    def log_message(self, fmt: str, *args) -> None:
        return

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/", "/health"):
            body = {
                "ok": True,
                "service": "tramamind-proxy",
                "upstream": self.upstream,
                "budget_tokens": self.budget,
                "verbatim_turns": self.verbatim,
            }
            self._send_json(200, body)
            return
        self._forward("GET", None)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            self._send_json(413, {"error": {"message": "body too large", "type": "invalid_request_error"}})
            return
        raw = self.rfile.read(length) if length else b""
        path = self.path.split("?", 1)[0]
        if path not in ("/v1/chat/completions", "/chat/completions"):
            self._forward("POST", raw)
            return
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send_json(400, {"error": {"message": "invalid json", "type": "invalid_request_error"}})
            return
        if not isinstance(body, dict):
            self._send_json(400, {"error": {"message": "json object required", "type": "invalid_request_error"}})
            return
        messages = body.get("messages")
        if not messages:
            self._forward("POST", raw)
            return
        try:
            report = compact_messages(messages, self.budget, self.verbatim)
        except ValueError as exc:
            self._send_json(400, {"error": {"message": str(exc), "type": "invalid_request_error"}})
            return
        body["messages"] = report["messages"]
        if body.get("stream") and "stream_options" not in body:
            body["stream_options"] = {"include_usage": True}
        self._forward(
            "POST",
            json.dumps(body).encode("utf-8"),
            report=report,
            stream=bool(body.get("stream")),
            model=body.get("model"),
        )

    def _note(self, report: dict, api_tokens: int | None, stream: bool, model) -> None:
        print(
            savings_line(report["raw_tokens"], report["sent_tokens"], report["summarized"], api_tokens),
            file=sys.stderr,
        )
        from router.stats import append_log

        append_log({
            "ts": time.time(),
            "kind": "proxy",
            "model": model if isinstance(model, str) else "",
            "packet_tokens_est": report["sent_tokens"],
            "raw_tokens_est": report["raw_tokens"],
            "prompt_tokens": api_tokens,
            "summarized": report["summarized"],
            "stream": stream,
        })

    def _forward(
        self,
        method: str,
        raw: bytes | None,
        report: dict | None = None,
        stream: bool = False,
        model=None,
    ) -> None:
        headers = {"Accept": self.headers.get("Accept") or "application/json"}
        auth = self.headers.get("Authorization")
        if auth:
            headers["Authorization"] = auth
        data = raw
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            upstream_url(self.upstream, self.path),
            data=data,
            headers=headers,
            method=method,
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            response = opener.open(request, timeout=UPSTREAM_TIMEOUT)
        except urllib.error.HTTPError as exc:
            response = exc
        except urllib.error.URLError as exc:
            if report is not None:
                self._note(report, None, stream, model)
            self._send_json(502, {
                "error": {
                    "message": f"upstream unreachable: {exc.reason}",
                    "type": "upstream_error",
                }
            })
            return
        with response:
            status = getattr(response, "status", None) or response.getcode()
            content_type = response.headers.get("Content-Type", "application/json")
            if stream and status < 400:
                api = self._relay_stream(response, status, content_type, report)
                if report is not None:
                    self._note(report, api, True, model)
                return
            payload = response.read()
            api = prompt_tokens_of(payload) if report is not None else None
            if report is not None:
                self._api_tokens = api
                self._note(report, api, False, model)
            self._send_bytes(status, content_type, payload, report)

    def _savings_headers(self, report: dict | None) -> None:
        if not report:
            return
        self.send_header("X-Tramamind-Raw-Tokens", str(report["raw_tokens"]))
        self.send_header("X-Tramamind-Sent-Tokens", str(report["sent_tokens"]))
        self.send_header("X-Tramamind-Saved-Pct", str(_saved_pct(report["raw_tokens"], report["sent_tokens"])))
        api = getattr(self, "_api_tokens", None)
        if isinstance(api, int):
            self.send_header("X-Tramamind-Api-Prompt-Tokens", str(api))

    def _send_json(self, status: int, payload: dict) -> None:
        self._send_bytes(status, "application/json; charset=utf-8", json.dumps(payload).encode("utf-8"), None)

    def _send_bytes(self, status: int, content_type: str, payload: bytes, report: dict | None) -> None:
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        self.send_header("Cache-Control", "no-store")
        self._savings_headers(report)
        self.end_headers()
        self.wfile.write(payload)

    def _relay_stream(self, response, status: int, content_type: str, report: dict | None) -> int | None:
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Transfer-Encoding", "chunked")
        self.send_header("Connection", "close")
        self.send_header("Cache-Control", "no-store")
        self._savings_headers(report)
        self.end_headers()
        pending = b""
        api = None
        while True:
            chunk = response.read(4096)
            if not chunk:
                break
            self.wfile.write(f"{len(chunk):X}\r\n".encode("ascii") + chunk + b"\r\n")
            self.wfile.flush()
            pending += chunk
            while b"\n" in pending:
                line, pending = pending.split(b"\n", 1)
                found = prompt_tokens_of_sse_line(line)
                if found is not None:
                    api = found
            if len(pending) > 65536:
                pending = pending[-65536:]
        found = prompt_tokens_of_sse_line(pending)
        if found is not None:
            api = found
        self.wfile.write(b"0\r\n\r\n")
        return api


def make_proxy(
    upstream: str = DEFAULT_UPSTREAM,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    budget: int = DEFAULT_BUDGET,
    verbatim: int = DEFAULT_VERBATIM,
) -> ThreadingHTTPServer:
    class Bound(ProxyHandler):
        pass

    Bound.upstream = upstream
    Bound.budget = budget
    Bound.verbatim = verbatim
    return ThreadingHTTPServer((host, port), Bound)


def parse_proxy_settings(body: dict) -> tuple[int, int, str]:
    try:
        budget = int(body.get("budget"))
        verbatim = int(body.get("verbatim"))
    except (TypeError, ValueError):
        raise ValueError("tetto e turni interi sono numeri") from None
    if budget < 1 or budget > 200_000:
        raise ValueError("tetto fra 1 e 200000")
    if verbatim < 1 or verbatim > 50:
        raise ValueError("turni interi fra 1 e 50")
    upstream = body.get("upstream") or "ollama"
    if upstream not in ("ollama", "omniroute"):
        raise ValueError("upstream sconosciuto")
    return budget, verbatim, upstream


def resolve_upstream(name: str, profile=None) -> str:
    if name == "omniroute":
        if profile is not None:
            return profile.omniroute_base
        return "http://127.0.0.1:20128/v1"
    if profile is not None:
        return profile.ollama_base
    return DEFAULT_UPSTREAM


def proxy_target(explicit: str | None, profile) -> str:
    if explicit:
        return explicit
    if profile is None:
        return DEFAULT_UPSTREAM
    return resolve_upstream(profile.proxy_upstream, profile)


def last_savings_line() -> str:
    from router.stats import read_log

    rows = [row for row in read_log() if row.get("kind") == "proxy"]
    if not rows:
        return ""
    row = rows[-1]
    api = row.get("prompt_tokens")
    return savings_line(
        int(row.get("raw_tokens_est") or 0),
        int(row.get("packet_tokens_est") or 0),
        bool(row.get("summarized")),
        api if isinstance(api, int) else None,
    )


_background_lock = threading.Lock()
_background_server: ThreadingHTTPServer | None = None
_background_thread: threading.Thread | None = None


def background_status() -> dict:
    with _background_lock:
        alive = (
            _background_thread is not None
            and _background_thread.is_alive()
            and _background_server is not None
        )
        port = _background_server.server_address[1] if alive else None
    return {"running": alive, "port": port}


def start_background(
    upstream: str,
    budget: int,
    verbatim: int,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> dict:
    global _background_server, _background_thread
    with _background_lock:
        if (
            _background_thread is not None
            and _background_thread.is_alive()
            and _background_server is not None
        ):
            return {"running": True, "port": _background_server.server_address[1]}
        server = make_proxy(upstream, host, port, budget, verbatim)
        thread = threading.Thread(target=server.serve_forever, name="tramamind-proxy", daemon=True)
        try:
            thread.start()
        except Exception:
            server.server_close()
            raise
        _background_server = server
        _background_thread = thread
        bound = server.server_address[1]
    return {"running": True, "port": bound}


def stop_background() -> dict:
    global _background_server, _background_thread
    with _background_lock:
        server, thread = _background_server, _background_thread
        _background_server = None
        _background_thread = None
    if server is not None:
        server.shutdown()
        server.server_close()
    if thread is not None:
        thread.join(timeout=3)
    return {"running": False, "port": None}


def serve(
    upstream: str = DEFAULT_UPSTREAM,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    budget: int = DEFAULT_BUDGET,
    verbatim: int = DEFAULT_VERBATIM,
) -> None:
    server = make_proxy(upstream, host, port, budget, verbatim)
    actual = server.server_address[1]
    print(f"TramaMind proxy · http://{host}:{actual}/v1")
    print(f"a monte {upstream}")
    print(f"tetto {budget} · turni interi {verbatim}")
    print("Solo questa macchina, salvo un --host diverso. Ctrl-C chiude.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
