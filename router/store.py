"""Sessioni su disco e scheda dell'utente."""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from router.paths import card_path, session_dir

CARD_TEMPLATE = """# Fatti stabili, una riga per fatto. Le righe che iniziano con # non vengono inviate.
# Esempio:
# Mi chiamo Ada. Rispondimi in italiano, senza preamboli.
"""


def new_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]


def session_path(session_id: str) -> Path:
    return session_dir() / f"{session_id}.json"


def blank_session() -> dict:
    return {
        "id": new_id(),
        "title": "",
        "created": time.time(),
        "updated": time.time(),
        "messages": [],
        "summary": "",
        "summary_through": 0,
    }


def save_session(session: dict) -> None:
    session["updated"] = time.time()
    path = session_path(session["id"])
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_session(session_id: str) -> dict | None:
    path = session_path(session_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_sessions() -> list[dict]:
    found = []
    for path in session_dir().glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        found.append({
            "id": data.get("id") or path.stem,
            "title": data.get("title") or "(senza titolo)",
            "updated": data.get("updated") or 0,
        })
    found.sort(key=lambda item: item["updated"], reverse=True)
    return found


def latest_session() -> dict | None:
    sessions = list_sessions()
    if not sessions:
        return None
    return load_session(sessions[0]["id"])


def resolve_session(prefix: str) -> dict | None:
    exact = load_session(prefix)
    if exact:
        return exact
    matches = [item for item in list_sessions() if item["id"].startswith(prefix)]
    if len(matches) == 1:
        return load_session(matches[0]["id"])
    return None


def read_card() -> str:
    path = card_path()
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_card(text: str) -> None:
    card_path().write_text(text, encoding="utf-8")


def ensure_card() -> None:
    path = card_path()
    if not path.exists():
        path.write_text(CARD_TEMPLATE, encoding="utf-8")
