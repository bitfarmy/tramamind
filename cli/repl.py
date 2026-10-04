"""Chat persistente. Stampa i token man mano e, sotto, il conto del pacchetto."""
from __future__ import annotations

import sys

from router.client import ChatError
from router.engine import Engine, format_turn
from router.profile import Profile
from router.store import blank_session, latest_session, list_sessions, resolve_session, save_session

try:
    import readline
except ImportError:
    readline = None


def _dim(text: str) -> str:
    if sys.stdout.isatty():
        return f"\033[2m{text}\033[0m"
    return text


def run_repl(engine: Engine, session: dict, lane: str | None) -> int:
    print(_dim(
        f"sessione {session['id']}"
        + (f" · {session['title']}" if session.get("title") else " · nuova")
        + " · /new /sessions /resume /clear /model /use /exit"
    ))
    while True:
        try:
            line = input("› ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        command = line.strip()
        if not command:
            continue
        if command in ("/exit", "/quit"):
            return 0
        if command == "/new":
            session = blank_session()
            lane = None
            print(_dim(f"nuova sessione {session['id']}"))
            continue
        if command == "/clear":
            session["messages"] = []
            session["summary"] = ""
            session["summary_through"] = 0
            save_session(session)
            print(_dim("contesto azzerato"))
            continue
        if command == "/sessions":
            for item in list_sessions()[:20]:
                print(f"  {item['id']}  {item['title']}")
            continue
        if command.startswith("/resume "):
            found = resolve_session(command.split(maxsplit=1)[1].strip())
            if found is None:
                print("sessione non trovata")
                continue
            session = found
            print(_dim(f"ripresa {session['id']} · {session.get('title') or ''}"))
            continue
        if command.startswith("/model "):
            engine.profile.models.general = command.split(maxsplit=1)[1].strip()
            lane = "general"
            print(_dim(f"modello generale → {engine.profile.models.general}"))
            continue
        if command.startswith("/use "):
            picked = command.split(maxsplit=1)[1].strip()
            if picked not in ("general", "code", "think", "fast"):
                print("usa general, code, think o fast")
                continue
            lane = picked
            print(_dim(f"corsia {lane}"))
            continue
        try:
            _speak(engine, session, command, lane, debug=False)
        except ChatError as exc:
            print(f"errore: {exc}")
        except KeyboardInterrupt:
            print(_dim("\ninterrotto, turno non salvato"))


def run_once(engine: Engine, session: dict, text: str, lane: str | None, debug: bool) -> int:
    try:
        _speak(engine, session, text, lane, debug)
    except ChatError as exc:
        print(f"errore: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(_dim("\ninterrotto, turno non salvato"))
        return 130
    return 0


def open_session(new: bool) -> dict:
    if new:
        return blank_session()
    return latest_session() or blank_session()


def _speak(engine: Engine, session: dict, text: str, lane: str | None, debug: bool) -> None:
    def on_delta(chunk: str) -> None:
        print(chunk, end="", flush=True)

    def on_notice(notice: str) -> None:
        print("\n" + _dim(f"— {notice} —"))

    def on_debug(messages, built) -> None:
        print(_dim(
            f"[debug] inviati ~{built['sent_tokens']} · storia ~{built['raw_tokens']} · "
            f"riassunto {'sì' if built['summarized'] else 'no'}"
        ), file=sys.stderr)

    result = engine.turn(
        session,
        text,
        lane=lane,
        on_delta=on_delta,
        on_notice=on_notice,
        debug=on_debug if debug else None,
    )
    print()
    print(_dim(format_turn(result)))
    if result.note and result.note not in format_turn(result):
        print(_dim(result.note))


def describe_profile(profile: Profile) -> str:
    models = profile.models
    return (
        f"preset {profile.preset} · {models.general} / codice {models.code} / "
        f"ragionamento {models.think} · tetto {profile.budget_tokens}"
    )
