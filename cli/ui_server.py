"""Pagina locale. Una vista sul CLI, in ascolto solo su 127.0.0.1."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files

from router.client import ChatError
from router.engine import Engine, format_turn
from router.presets import PRESETS
from router.profile import load_profile, save_profile
from router.proxy import (
    DEFAULT_BUDGET,
    DEFAULT_UPSTREAM,
    DEFAULT_VERBATIM,
    background_status,
    last_savings_line,
    parse_proxy_settings,
    resolve_upstream,
    start_background,
    stop_background,
)
from router.runtime import apply_preset, checks, key_status
from router.store import blank_session, latest_session, list_sessions, load_session, read_card, write_card

PROXY_PORT = 8788


def make_server(host: str = "127.0.0.1", port: int = 8787) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        return

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._html()
        elif path == "/api/status":
            self._json(status_payload())
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            self._json({"error": "serve application/json"}, 415)
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json({"error": "json non valido"}, 400)
            return
        try:
            if path == "/api/profile":
                profile = apply_preset(str(body.get("preset") or ""))
                self._json({"ok": True, "preset": profile.preset, "status": status_payload()})
            elif path == "/api/keys":
                from router.runtime import save_provider_key, sync_keys
                name, backend = save_provider_key(str(body.get("provider") or ""), str(body.get("key") or ""))
                synced = []
                if name != "omniroute":
                    synced = [row for row in sync_keys() if row["provider"] in (name, "*")]
                self._json({"ok": True, "provider": name, "backend": backend, "sync": synced})
            elif path == "/api/card":
                write_card(str(body.get("text") or ""))
                self._json({"ok": True})
            elif path == "/api/chat":
                self._json(chat_payload(body))
            elif path == "/api/proxy":
                self._json(proxy_action(body))
            else:
                self.send_error(404)
        except (ValueError, FileNotFoundError, ChatError) as exc:
            self._json({"error": str(exc)}, 400)

    def _html(self) -> None:
        page = files("cli").joinpath("assets/index.html").read_text(encoding="utf-8")
        data = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def status_payload() -> dict:
    profile = load_profile()
    return {
        "profile": None if profile is None else {
            "preset": profile.preset,
            "models": profile.models.model_dump(),
            "budget_tokens": profile.budget_tokens,
            "escalation": profile.escalation.model_dump(),
        },
        "presets": {key: value.label for key, value in PRESETS.items()},
        "checks": [check.__dict__ for check in checks(profile)],
        "keys": key_status(),
        "card": read_card(),
        "sessions": list_sessions()[:30],
        "proxy": proxy_status(),
    }


def proxy_status() -> dict:
    profile = load_profile()
    state = background_status()
    ollama = profile.ollama_base if profile is not None else DEFAULT_UPSTREAM
    omni = profile.omniroute_base if profile is not None else "http://127.0.0.1:20128/v1"
    port = state["port"] if state["running"] else PROXY_PORT
    return {
        "budget_tokens": profile.budget_tokens if profile is not None else DEFAULT_BUDGET,
        "verbatim_turns": profile.verbatim_turns if profile is not None else DEFAULT_VERBATIM,
        "upstream": profile.proxy_upstream if profile is not None else "ollama",
        "upstreams": [
            {"id": "ollama", "label": "Ollama", "url": ollama},
            {"id": "omniroute", "label": "OmniRoute", "url": omni},
        ],
        "running": state["running"],
        "url": f"http://127.0.0.1:{port}/v1",
        "last_line": last_savings_line(),
    }


def proxy_action(body: dict) -> dict:
    action = body.get("action")
    if action == "stop":
        stop_background()
        return {"ok": True, "proxy": proxy_status()}
    if action not in ("save", "start"):
        raise ValueError("azione sconosciuta")
    budget, verbatim, upstream = parse_proxy_settings(body)
    profile = load_profile()
    if action == "save" and profile is None:
        raise FileNotFoundError("Scegli prima un preset.")
    if profile is not None:
        profile.budget_tokens = budget
        profile.verbatim_turns = verbatim
        profile.proxy_upstream = upstream
        save_profile(profile)
        profile = load_profile()
    if action == "save":
        return {"ok": True, "proxy": proxy_status()}
    try:
        start_background(
            resolve_upstream(upstream, profile),
            budget,
            verbatim,
            port=PROXY_PORT,
        )
    except OSError as exc:
        raise ValueError(f"porta {PROXY_PORT} non disponibile") from exc
    return {"ok": True, "proxy": proxy_status()}


def chat_payload(body: dict) -> dict:
    profile = load_profile()
    if profile is None:
        raise FileNotFoundError("Scegli prima un preset.")
    message = str(body.get("message") or "").strip()
    if not message:
        raise ValueError("messaggio vuoto")
    session_id = body.get("session")
    if session_id:
        session = load_session(str(session_id))
        if session is None:
            raise ValueError("sessione non trovata")
    else:
        session = latest_session() or blank_session()
    lane = body.get("lane") or None
    if lane not in (None, "general", "code", "think", "fast"):
        raise ValueError("corsia sconosciuta")
    result = Engine(profile).turn(session, message, lane=lane)
    return {
        "session": result.session_id,
        "text": result.text,
        "local_text": result.local_text,
        "stats": format_turn(result),
        "escalated": result.escalated,
    }


def serve(port: int = 8787) -> None:
    server = make_server(port=port)
    print(f"TramaMind · http://127.0.0.1:{port}")
    print("Solo questa macchina. Ctrl-C chiude.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        stop_background()
        server.server_close()
