"""TramaMind — profilo, chat con tetto, escalation singola."""
from __future__ import annotations

import argparse
import sys

from cli import keys as keys_cmd
from cli.repl import describe_profile, open_session, run_once, run_repl
from router.engine import Engine
from router.keystore import BACKENDS
from router.presets import PRESETS, suggest_preset
from router.profile import fresh_profile, load_profile, require_profile, save_profile
from router.runtime import (
    apply_preset,
    checks,
    down,
    probe,
    pull_models,
    sync_keys,
    up,
    worst_level,
)
from router.stats import render_summary, summarize
from router.store import ensure_card, read_card, write_card


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tramamind",
        description="Assistente personale: modello locale, contesto corto, cloud solo se serve.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    setup = sub.add_parser("setup", help="Scrivi il profilo e, se vuoi, le chiavi")
    setup.add_argument("--preset", choices=sorted(PRESETS))
    setup.add_argument("--non-interactive", action="store_true")
    setup.add_argument("--pull", action="store_true", help="Scarica i modelli del preset")
    setup.add_argument("--force", action="store_true")

    sub.add_parser("up", help="Avvia Ollama e, se ci sono chiavi, OmniRoute")
    sub.add_parser("down", help="Ferma solo i processi avviati da tramamind up")
    doctor = sub.add_parser("doctor", help="Dice cosa manca, senza fingere")
    doctor.add_argument("--probe", action="store_true", help="Una completion minima sul modello locale")

    chat = sub.add_parser("chat", help="Chat persistente")
    chat.add_argument("message", nargs="*")
    chat.add_argument("--code", action="store_true")
    chat.add_argument("--think", action="store_true")
    chat.add_argument("--fast", action="store_true")
    chat.add_argument("--new", action="store_true")
    chat.add_argument("--debug", action="store_true")

    keys = sub.add_parser("keys", help="Chiavi nel keyring, in age o in .env locale")
    keys_sub = keys.add_subparsers(dest="keys_command", required=True)
    add = keys_sub.add_parser("add")
    add.add_argument("provider", nargs="?")
    add.add_argument("--backend", choices=BACKENDS)
    setup_keys = keys_sub.add_parser("setup")
    setup_keys.add_argument("--backend", choices=BACKENDS)
    keys_sub.add_parser("list")
    remove = keys_sub.add_parser("remove")
    remove.add_argument("provider")

    sub.add_parser("sync", help="Spinge le chiavi in OmniRoute, se è installato")
    ui = sub.add_parser("ui", help="Pagina locale su 127.0.0.1:8787")
    ui.add_argument("--port", type=int, default=8787)
    sub.add_parser("pull", help="ollama pull dei modelli del profilo")
    sub.add_parser("stats", help="Conti dei pacchetti, senza il testo")
    card = sub.add_parser("card", help="Scheda stabile che entra in ogni chat")
    card.add_argument("text", nargs="*")
    card.add_argument("--edit", action="store_true")

    proxy = sub.add_parser("proxy", help="Proxy OpenAI-compatible su 127.0.0.1:8788")
    proxy.add_argument("--upstream", default=None, help="Base OpenAI. Se manca, Ollama o OmniRoute dal profilo")
    proxy.add_argument("--host", default="127.0.0.1")
    proxy.add_argument("--port", type=int, default=8788)
    proxy.add_argument("--budget", type=int, default=None, help="Tetto in token stimati")
    proxy.add_argument("--verbatim", type=int, default=None, help="Ultimi messaggi tenuti interi")

    sub.add_parser("demo", help="Conta i token su una chat finta, senza modello")

    pack = sub.add_parser("pack", help="Conta il pacchetto di una trascrizione JSON, senza modello")
    pack.add_argument("path", help="Array di messaggi, oppure un oggetto con la chiave messages")
    pack.add_argument("--budget", type=int, default=None, help="Tetto in token stimati")
    pack.add_argument("--verbatim", type=int, default=None, help="Ultimi messaggi tenuti interi")
    pack.add_argument("--out", help="Scrive i messaggi del pacchetto in questo file")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "keys":
        return keys_cmd.run(args)
    if args.command == "setup":
        return cmd_setup(args)
    if args.command == "up":
        return _print_lines(up(require_profile()))
    if args.command == "down":
        return _print_lines(down())
    if args.command == "doctor":
        return cmd_doctor(args.probe)
    if args.command == "chat":
        return cmd_chat(args)
    if args.command == "sync":
        return _print_sync(sync_keys())
    if args.command == "ui":
        from cli.ui_server import serve
        serve(args.port)
        return 0
    if args.command == "pull":
        return pull_models(require_profile())
    if args.command == "stats":
        print(render_summary(summarize()))
        return 0
    if args.command == "card":
        return cmd_card(args)
    if args.command == "proxy":
        from router.proxy import proxy_target, serve
        budget, verbatim = _proxy_limits(args.budget, args.verbatim)
        serve(proxy_target(args.upstream, _profile_if_present()), args.host, args.port, budget, verbatim)
        return 0
    if args.command == "demo":
        from router.proxy import DEFAULT_BUDGET, DEFAULT_VERBATIM, render_demo
        print(render_demo(DEFAULT_BUDGET, DEFAULT_VERBATIM))
        return 0
    if args.command == "pack":
        return cmd_pack(args)
    return 1


def cmd_setup(args) -> int:
    preset = args.preset
    interactive = not args.non_interactive and sys.stdin.isatty()
    if preset is None and interactive:
        suggested = suggest_preset()
        print("Preset:")
        for key, item in PRESETS.items():
            mark = " ← consigliato" if key == suggested else ""
            print(f"  {key:6} {item.label}{mark}")
        raw = input(f"Scelta [{suggested}]: ").strip()
        preset = raw or suggested
    preset = preset or suggest_preset()
    if preset not in PRESETS:
        print(f"preset sconosciuto: {preset}")
        return 1
    existed = load_profile() is not None
    if existed and not args.force:
        print(f"profilo già presente ({describe_profile(load_profile())}). Usa --force per rifare i modelli.")
    elif existed:
        print(describe_profile(apply_preset(preset)))
    else:
        profile = fresh_profile(preset)
        save_profile(profile)
        print(describe_profile(profile))
    ensure_card()
    if interactive:
        print("Chiavi cloud, invio per saltarle. Servono solo per l'escalation.")
        keys_cmd.cmd_setup(None)
    if args.pull:
        return pull_models(require_profile())
    print("Poi: tramamind pull && tramamind chat")
    print("Oppure: tramamind ui")
    return 0


def cmd_doctor(do_probe: bool) -> int:
    items = checks()
    for item in items:
        mark = {"ok": "✓", "warn": "!", "fail": "✗"}[item.level]
        print(f"  {mark} {item.name}: {item.detail}")
    if do_probe:
        profile = load_profile()
        if profile is None:
            print("  ✗ probe: profilo assente")
            return 1
        try:
            text = probe(profile)
            print(f"  ✓ probe: {text!r}")
        except Exception as exc:
            print(f"  ✗ probe: {exc}")
            return 1
    return 1 if worst_level(items) == "fail" else 0


def cmd_chat(args) -> int:
    profile = require_profile()
    lanes = [name for name, on in (("code", args.code), ("think", args.think), ("fast", args.fast)) if on]
    if len(lanes) > 1:
        print("scegli una sola corsia", file=sys.stderr)
        return 2
    lane = lanes[0] if lanes else None
    session = open_session(args.new)
    engine = Engine(profile)
    if args.message:
        return run_once(engine, session, " ".join(args.message), lane, args.debug)
    print(describe_profile(profile))
    return run_repl(engine, session, lane)


def cmd_card(args) -> int:
    ensure_card()
    if args.edit:
        import os
        import subprocess
        subprocess.call([os.environ.get("EDITOR", "vi"), str(__import__("router.paths", fromlist=["card_path"]).card_path())])
        return 0
    if args.text:
        write_card(" ".join(args.text) + "\n")
        print("scheda aggiornata")
        return 0
    text = read_card().strip()
    print(text or "(scheda vuota)")
    return 0


def cmd_pack(args) -> int:
    from router.proxy import run_pack
    budget, verbatim = _proxy_limits(args.budget, args.verbatim)
    try:
        print(run_pack(args.path, budget, verbatim, args.out))
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def _proxy_limits(budget: int | None, verbatim: int | None) -> tuple[int, int]:
    profile = _profile_if_present()
    if budget is None:
        budget = profile.budget_tokens if profile is not None else 2500
    if verbatim is None:
        verbatim = profile.verbatim_turns if profile is not None else 6
    return budget, verbatim


def _profile_if_present():
    """Non crea ~/.config/tramamind solo perché qualcuno lancia demo o proxy."""
    import os
    from pathlib import Path

    override = os.environ.get("TRAMAMIND_CONFIG_DIR")
    root = Path(override) if override else Path.home() / ".config" / "tramamind"
    if not (root / "profile.yaml").exists():
        return None
    return load_profile()


def _print_lines(lines: list[str]) -> int:
    for line in lines:
        print(line)
    failed = any("non ha risposto" in line or "assente" in line for line in lines)
    return 1 if failed else 0


def _print_sync(rows: list[dict]) -> int:
    failed = False
    for row in rows:
        mark = "✓" if row["ok"] else "!"
        print(f"  {mark} {row['provider']}: {row['detail']}")
        failed = failed or not row["ok"]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
