"""`tramamind keys` — le chiavi stanno nel keyring, in age o in .env locale."""
from __future__ import annotations

import getpass

from router import keystore
from router.providers import resolve_provider


def _load_providers() -> list[str]:
    from router.providers import provider_ids
    return provider_ids()


def _pick_backend(cli_choice: str | None) -> str:
    if cli_choice:
        return cli_choice
    best = keystore.detect_best_backend()
    labels = {
        "keyring": "Keyring di sistema (consigliato su desktop)",
        "age": "File cifrato age (consigliato su server/headless)",
        "plain": ".env plain (solo sviluppo)",
    }
    print("\nSalvataggio:")
    options = list(labels)
    for i, b in enumerate(options, 1):
        marker = " <- rilevato" if b == best else ""
        print(f"  [{i}] {labels[b]}{marker}")
    raw = input(f"Scelta [{options.index(best) + 1}]: ").strip()
    if not raw:
        return best
    try:
        return options[int(raw) - 1]
    except (ValueError, IndexError):
        print("Scelta non valida, uso il rilevamento automatico.")
        return best


def _ask_key(provider: str) -> str | None:
    key = getpass.getpass(f"{provider}: ").strip()
    if not key:
        print(f"  {provider}: saltato")
        return None
    return key


def cmd_add(provider: str | None, backend: str | None) -> int:
    providers = _load_providers()
    if not provider:
        print("Provider disponibili:")
        for i, p in enumerate(providers, 1):
            print(f"  [{i}] {p}")
        raw = input("Scelta: ").strip()
        try:
            provider = providers[int(raw) - 1]
        except (ValueError, IndexError):
            print("Scelta non valida.")
            return 1
    known = resolve_provider(provider)
    if known is None and provider not in providers:
        print(f"nota: '{provider}' non è nel catalogo — procedo comunque")
    elif known is not None:
        provider = known.id

    key = _ask_key(provider)
    if not key:
        return 1
    chosen = _pick_backend(backend)
    keystore.store_key(provider, key, chosen)
    print(f"OK: {provider} salvata ({chosen})")
    return 0


def cmd_setup(backend: str | None) -> int:
    providers = _load_providers()
    print("\nTramaMind - setup API key")
    print("Incolla le chiavi (invio per saltare):\n")
    collected = {}
    for p in providers:
        key = _ask_key(p)
        if key:
            collected[p] = key
    if not collected:
        print("\nNessuna chiave inserita.")
        return 1
    chosen = _pick_backend(backend)
    for p, k in collected.items():
        keystore.store_key(p, k, chosen)
    print(f"\nOK: {len(collected)} chiavi salvate ({chosen})")
    print("Per spingerle in OmniRoute, se lo usi: `tramamind sync`")
    return 0


def cmd_list() -> int:
    providers = _load_providers()
    print(f"\n{'Provider':<14}{'Stato':<12}{'Storage':<10}Chiave")
    print("-" * 48)
    missing = 0
    for p in providers:
        key, storage = keystore.get_key(p)
        if key:
            print(f"{p:<14}{'presente':<12}{storage or '?':<10}{keystore.mask(key)}")
        else:
            print(f"{p:<14}{'mancante':<12}{'-':<10}")
            missing += 1
    if missing:
        print(f"\n{missing} provider senza chiave: `tramamind keys add <provider>`")
    return 0


def cmd_remove(provider: str) -> int:
    removed = keystore.delete_key(provider)
    if removed:
        print(f"OK: {provider} rimossa da: {', '.join(removed)}")
    else:
        print(f"{provider}: nessuna chiave trovata")
    return 0


def run(args) -> int:
    if args.keys_command == "add":
        return cmd_add(args.provider, args.backend)
    if args.keys_command == "setup":
        return cmd_setup(args.backend)
    if args.keys_command == "list":
        return cmd_list()
    if args.keys_command == "remove":
        return cmd_remove(args.provider)
    return 1
