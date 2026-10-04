import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cli.main import main
from router.profile import fresh_profile
from router.proxy import (
    DEMO_FENCE,
    DEMO_LAST,
    DEMO_MARKER,
    compact_messages,
    demo_messages,
    make_proxy,
    prompt_tokens_of,
    prompt_tokens_of_sse_line,
    proxy_target,
    render_demo,
    savings_line,
    upstream_url,
)
from router.stats import read_log


def test_proxy_target_follows_the_profile_until_the_flag_wins():
    profile = fresh_profile("cpu16")
    profile.proxy_upstream = "omniroute"
    assert proxy_target(None, profile) == profile.omniroute_base
    assert proxy_target("http://127.0.0.1:9/v1", profile) == "http://127.0.0.1:9/v1"
    assert proxy_target(None, None) == "http://127.0.0.1:11434/v1"


def test_upstream_url_joins_v1_once():
    assert upstream_url("http://127.0.0.1:11434/v1", "/v1/chat/completions") == (
        "http://127.0.0.1:11434/v1/chat/completions"
    )
    assert upstream_url("http://127.0.0.1:11434", "/v1/models") == "http://127.0.0.1:11434/v1/models"
    assert upstream_url("http://127.0.0.1:20128/v1/", "/chat/completions?x=1") == (
        "http://127.0.0.1:20128/v1/chat/completions?x=1"
    )


def test_long_history_keeps_the_fence_and_drops_old_prose():
    messages = demo_messages()
    last = messages[-1]
    report = compact_messages(messages, budget=2500, verbatim=6)
    blob = "\n".join(
        item.get("content") if isinstance(item.get("content"), str) else ""
        for item in report["messages"]
    )
    assert report["summarized"] is True
    assert report["sent_tokens"] < report["raw_tokens"]
    assert report["messages"][-1] is last
    assert DEMO_FENCE in blob
    assert DEMO_MARKER not in blob
    assert DEMO_LAST in report["messages"][-1]["content"]


def test_a_short_chat_is_forwarded_unchanged():
    messages = [
        {"role": "system", "content": "be exact"},
        {"role": "user", "content": "hi"},
    ]
    report = compact_messages(messages, budget=2500, verbatim=6)
    assert report["summarized"] is False
    assert report["messages"] is messages
    assert report["sent_tokens"] == report["raw_tokens"]


def _old_then_latest(content: str) -> list[dict]:
    return [
        {"role": "user", "content": ("prosa vecchia " * 80) + "DROP_OLD_PROSE\n" + content},
        {"role": "assistant", "content": "ok"},
        {"role": "user", "content": "ultima domanda"},
    ]


def _blob(report: dict) -> str:
    return "\n".join(
        item.get("content") if isinstance(item.get("content"), str) else ""
        for item in report["messages"]
    )


def test_an_old_diff_and_traceback_stay_verbatim():
    diff = (
        "diff --git a/app.py b/app.py\n"
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -1 +1 @@\n"
        "+KEEP_THIS_LINE = 1\n"
    )
    trace = (
        "Traceback (most recent call last):\n"
        "  File \"app.py\", line 3, in <module>\n"
        "    main()\n"
        "ValueError: KEEP_THIS_ERROR\n"
    )
    report = compact_messages(_old_then_latest(diff + "\n" + trace), budget=2500, verbatim=1)
    blob = _blob(report)
    assert "KEEP_THIS_LINE = 1" in blob
    assert "KEEP_THIS_ERROR" in blob
    assert "DROP_OLD_PROSE" not in blob
    assert report["messages"][-1]["content"] == "ultima domanda"


def test_an_old_tool_result_keeps_its_middle_and_drops_its_tail():
    body = ("a" * 450) + "TOOL_KEEP_MARKER" + ("b" * 1200) + "TOOL_DROP_MARKER"
    messages = [
        {"role": "user", "content": "prima " * 200},
        {"role": "tool", "name": "read_file", "content": body},
        {"role": "user", "content": "e adesso?"},
    ]
    report = compact_messages(messages, budget=2500, verbatim=1)
    blob = _blob(report)
    assert "TOOL_KEEP_MARKER" in blob
    assert "TOOL_DROP_MARKER" not in blob
    assert report["messages"][-1] is messages[-1]


def test_one_huge_diff_message_is_not_trimmed():
    diff = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n" + "".join(
        f"+line_{i} = {i}\n" for i in range(400)
    )
    messages = [
        {"role": "system", "content": "be exact"},
        {"role": "user", "content": diff},
    ]
    report = compact_messages(messages, budget=200, verbatim=6)
    assert report["summarized"] is False
    assert report["messages"][1]["content"] == diff


def test_one_huge_code_message_is_not_trimmed():
    code = "```python\n" + ("x = 1\n" * 4000) + "```"
    messages = [
        {"role": "system", "content": "be exact"},
        {"role": "user", "content": code},
    ]
    report = compact_messages(messages, budget=200, verbatim=6)
    assert report["summarized"] is False
    assert report["messages"][1]["content"] == code


def test_recent_tool_call_and_image_part_stay_the_same_objects():
    old = {"role": "user", "content": "old prose " * 500}
    tool = {
        "role": "assistant",
        "content": None,
        "tool_calls": [{"id": "1", "type": "function", "function": {"name": "read", "arguments": "{}"}}],
    }
    image = {
        "role": "user",
        "content": [
            {"type": "text", "text": "look"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
        ],
    }
    messages = [old, {"role": "assistant", "content": "ok " * 400}, tool, image]
    report = compact_messages(messages, budget=2000, verbatim=2)
    assert report["messages"][-1] is image
    assert report["messages"][-2] is tool
    assert old not in report["messages"]


def test_demo_command_prints_the_kept_code(capsys, tmp_path, monkeypatch):
    config = tmp_path / "no-config"
    monkeypatch.setenv("TRAMAMIND_CONFIG_DIR", str(config))
    assert main(["demo"]) == 0
    out = capsys.readouterr().out
    assert "full history ~10273 · packet ~1211 · −88%" in out
    assert "def add(a, b)" in out
    assert DEMO_LAST in out
    assert "code kept verbatim" in out
    assert read_log() == []
    assert not config.exists()


def test_savings_line_places_the_api_count_beside_the_estimate():
    assert savings_line(100, 40, True, 38) == "storia intera ~100 · inviati ~40 · −60% · api 38"
    assert prompt_tokens_of(b'{"usage": {"prompt_tokens": 432}}') == 432
    assert prompt_tokens_of(b'{"choices": []}') is None
    assert prompt_tokens_of_sse_line(b'data: {"usage": {"prompt_tokens": 90}}') == 90
    assert prompt_tokens_of_sse_line(b"data: [DONE]") is None


def test_pack_reports_the_kept_diff_and_writes_the_packet(tmp_path, monkeypatch, capsys):
    config = tmp_path / "absent"
    monkeypatch.setenv("TRAMAMIND_CONFIG_DIR", str(config))
    diff = (
        "diff --git a/app.py b/app.py\n"
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -1 +1 @@\n"
        "+KEEP_THIS_LINE = 1\n"
    )
    messages = _old_then_latest(diff)
    source = tmp_path / "session.json"
    source.write_text(json.dumps({"messages": messages}), encoding="utf-8")
    out = tmp_path / "packet.json"
    assert main(["pack", str(source), "--budget", "2500", "--verbatim", "1", "--out", str(out)]) == 0
    text = capsys.readouterr().out
    assert "diff: diff --git a/app.py" in text
    assert "DROP_OLD_PROSE" not in text
    assert "ultimo messaggio utente: ultima domanda" in text
    packet = out.read_text(encoding="utf-8")
    assert "KEEP_THIS_LINE" in packet
    assert "DROP_OLD_PROSE" not in packet
    assert not config.exists()
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    assert main(["pack", str(bad)]) == 1


def test_render_demo_matches_the_command():
    text = render_demo()
    assert text.startswith("full history ~")
    assert "packet ~" in text


class _Upstream(BaseHTTPRequestHandler):
    seen: dict = {}

    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        self._json({"object": "list", "data": [{"id": "qwen2.5-coder:7b"}]})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length).decode())
        _Upstream.seen = {
            "path": self.path,
            "body": body,
            "auth": self.headers.get("Authorization"),
        }
        if body.get("stream"):
            payload = b'data: {"choices":[{"delta":{"content":"pong"}}]}\n\ndata: [DONE]\n\n'
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self._json({
            "model": body.get("model"),
            "choices": [{"message": {"content": "pong"}}],
            "usage": {"prompt_tokens": 432, "completion_tokens": 1},
        })

    def _json(self, payload: dict):
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _start_proxy(upstream: str):
    server = make_proxy(upstream=upstream, port=0, budget=2500, verbatim=6)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _post(port: int, path: str, body: dict, auth: str | None = None):
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if auth:
        headers["Authorization"] = auth
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        headers=headers,
        method="POST",
    )
    try:
        response = urllib.request.urlopen(request, timeout=5)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        return response.status, dict(response.headers), response.read()


def test_proxy_compacts_forwards_and_does_not_log_the_text():
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _Upstream)
    upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    upstream_thread.start()
    origin = f"http://127.0.0.1:{upstream.server_address[1]}/v1"
    proxy = _start_proxy(origin)
    port = proxy.server_address[1]
    try:
        _Upstream.seen = {}
        messages = demo_messages()
        status, headers, raw = _post(
            port,
            "/v1/chat/completions",
            {"model": "qwen2.5-coder:7b", "messages": messages},
            auth="Bearer secret-token",
        )
        assert status == 200
        assert json.loads(raw)["choices"][0]["message"]["content"] == "pong"
        assert int(headers["X-Tramamind-Raw-Tokens"]) > int(headers["X-Tramamind-Sent-Tokens"])
        assert headers["X-Tramamind-Api-Prompt-Tokens"] == "432"
        forwarded = _Upstream.seen["body"]["messages"]
        blob = "\n".join(
            item.get("content") if isinstance(item.get("content"), str) else ""
            for item in forwarded
        )
        assert DEMO_FENCE in blob
        assert DEMO_MARKER not in blob
        assert forwarded[-1]["content"] == DEMO_LAST
        assert _Upstream.seen["auth"] == "Bearer secret-token"
        assert _Upstream.seen["path"] == "/v1/chat/completions"
        log = "\n".join(json.dumps(row) for row in read_log())
        assert DEMO_MARKER not in log
        assert "secret-token" not in log
        assert "def add" not in log
        models = urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=5)
        with models:
            assert json.loads(models.read())["data"][0]["id"] == "qwen2.5-coder:7b"
    finally:
        proxy.shutdown()
        proxy.server_close()
        upstream.shutdown()
        upstream.server_close()


def test_proxy_streams_the_upstream_body():
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _Upstream)
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()
    proxy = _start_proxy(f"http://127.0.0.1:{upstream.server_address[1]}/v1")
    try:
        status, _headers, raw = _post(
            proxy.server_address[1],
            "/v1/chat/completions",
            {"model": "m", "messages": [{"role": "user", "content": "hi"}], "stream": True},
        )
        assert status == 200
        assert b"pong" in raw
        assert b"[DONE]" in raw
    finally:
        proxy.shutdown()
        proxy.server_close()
        upstream.shutdown()
        upstream.server_close()


def test_proxy_reports_a_down_upstream_without_the_prompt():
    proxy = _start_proxy("http://127.0.0.1:1/v1")
    try:
        status, _headers, raw = _post(
            proxy.server_address[1],
            "/v1/chat/completions",
            {"model": "m", "messages": [{"role": "user", "content": DEMO_MARKER}]},
        )
        assert status == 502
        text = raw.decode()
        assert "upstream unreachable" in text
        assert DEMO_MARKER not in text
    finally:
        proxy.shutdown()
        proxy.server_close()
