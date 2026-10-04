import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from cli.ui_server import make_server
from router.client import HttpChatClient
from router.profile import fresh_profile, load_profile, save_profile
from router.proxy import stop_background
from router.runtime import save_provider_key


def test_client_reads_a_normal_response_and_a_stream():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class H(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            return

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length).decode())
            if body.get("stream"):
                payload = (
                    'data: {"choices":[{"delta":{"content":"ciao"}}]}\n\n'
                    'data: {"choices":[],"usage":{"prompt_tokens":11,"completion_tokens":1}}\n\n'
                    "data: [DONE]\n\n"
                )
                data = payload.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            data = json.dumps({
                "model": "gemma3:4b",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 1},
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), H)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = HttpChatClient(f"http://127.0.0.1:{port}/v1", "ollama")
        plain = client.complete("gemma3:4b", [{"role": "user", "content": "x"}], 5)
        assert plain.text == "ok"
        assert plain.prompt_tokens == 5
        chunks = []
        streamed = client.complete(
            "gemma3:4b", [{"role": "user", "content": "x"}], 5, on_delta=chunks.append
        )
        assert chunks == ["ciao"]
        assert streamed.prompt_tokens == 11
    finally:
        server.shutdown()
        server.server_close()


def test_ui_status_profile_and_key_roundtrip():
    server = make_server(port=0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as response:
            page = response.read().decode()
        assert "TramaMind" in page
        assert "Tetto" in page
        assert "Avvia" in page
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status") as response:
            status = json.load(response)
        assert any(item["level"] == "fail" and item["name"] == "profilo" for item in status["checks"])

        def post(path, payload):
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}{path}",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request) as response:
                return json.load(response)

        created = post("/api/profile", {"preset": "cpu16"})
        assert created["status"]["profile"]["models"]["general"] == "gemma3:4b"
        saved = post("/api/keys", {"provider": "groq", "key": "gsk-test-9999"})
        assert saved["provider"] == "groq"
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status") as response:
            status = json.load(response)
        groq = next(row for row in status["keys"] if row["id"] == "groq")
        assert groq["present"] is True
        assert "gsk-test-9999" not in json.dumps(status)
        assert groq["masked"].endswith("9999")
    finally:
        server.shutdown()
        server.server_close()


def _post(port, path, payload):
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)


def test_the_page_saves_proxy_settings_starts_it_and_shows_the_line(monkeypatch):
    from cli import ui_server

    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            return

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            data = json.dumps({
                "choices": [{"message": {"content": "pong"}}],
                "usage": {"prompt_tokens": 432, "completion_tokens": 1},
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    upstream_thread.start()
    monkeypatch.setattr(ui_server, "PROXY_PORT", 0)
    server = make_server(port=0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, missing = _post(port, "/api/proxy", {
            "action": "save", "budget": 800, "verbatim": 3, "upstream": "ollama",
        })
        assert status == 400
        assert "preset" in missing["error"]

        status, created = _post(port, "/api/profile", {"preset": "cpu16"})
        assert status == 200
        status, saved = _post(port, "/api/proxy", {
            "action": "save", "budget": 800, "verbatim": 3, "upstream": "omniroute",
        })
        assert status == 200
        proxy = saved["proxy"]
        assert proxy["budget_tokens"] == 800
        assert proxy["verbatim_turns"] == 3
        assert proxy["upstream"] == "omniroute"
        assert proxy["upstreams"][0]["url"].endswith(":11434/v1")
        assert proxy["upstreams"][1]["url"].endswith(":20128/v1")
        assert proxy["running"] is False
        assert load_profile().budget_tokens == 800

        status, rejected = _post(port, "/api/proxy", {
            "action": "save", "budget": 800, "verbatim": 3, "upstream": "altro",
        })
        assert status == 400

        profile = load_profile()
        profile.ollama_base = f"http://127.0.0.1:{upstream.server_address[1]}/v1"
        save_profile(profile)
        status, started = _post(port, "/api/proxy", {
            "action": "start", "budget": 900, "verbatim": 4, "upstream": "ollama",
        })
        assert status == 200
        proxy = started["proxy"]
        assert proxy["running"] is True
        assert proxy["url"].startswith("http://127.0.0.1:")
        assert load_profile().budget_tokens == 900
        assert load_profile().proxy_upstream == "ollama"

        code, body = _post(
            int(proxy["url"].rsplit(":", 1)[1].split("/", 1)[0]),
            "/v1/chat/completions",
            {"model": "m", "messages": [{"role": "user", "content": "ciao"}]},
        )
        assert code == 200
        assert body["choices"][0]["message"]["content"] == "pong"
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status") as response:
            shown = json.load(response)["proxy"]["last_line"]
        assert "api 432" in shown
        assert "ciao" not in shown

        status, stopped = _post(port, "/api/proxy", {"action": "stop"})
        assert status == 200
        assert stopped["proxy"]["running"] is False
    finally:
        stop_background()
        server.shutdown()
        server.server_close()
        upstream.shutdown()
        upstream.server_close()


def test_save_provider_key_rejects_unknown():
    save_profile(fresh_profile("cpu16"))
    with pytest.raises(ValueError):
        save_provider_key("gemopus", "x")


def test_setup_command_writes_the_preset():
    from cli.main import main
    assert main(["setup", "--preset", "cpu16", "--non-interactive"]) == 0
    assert load_profile().models.summary == "gemma3:4b"
