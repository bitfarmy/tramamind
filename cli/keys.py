"""
`tramamind keys` — gestione interattiva delle API key.

I provider vengono letti da router/providers.yaml (campo env_key):
niente elenchi hardcoded, il catalogo è unico e versionato.
"""
from __future__ import annotations

import getpass
import sys
from pathlib import Path

from router import keystore

# Prefissi noti per validazione leggera (warn, non blocco)
KNOWN_PREFIXES = {
    "google": "AIza",
    "groq": "gsk_",
    "nvidia": "nvapi-",
    "cerebras": "csk-",
    "openrouter": "sk-or-",
    "kimi": "sk-",
}


def _load_providers() -> list[str]:
    """Provider con env_key dal catalogo versionato."""
    catalog = Path(__file__).resolve().parent.parent / "router" / "providers.yaml"
    try:
        import yaml
        data = yaml.safe_load(catalog.read_text())
        names = [
            name for name, cfg in data.get("providers", {}).items()
            if cfg.get("env_key") and str(cfg["env_key"]).endswith("_API_KEY")
        ]
        if names:
            return names
    except Exception:
        pass
    return ["google", "groq", "nvidia", "cerebras", "openrouter", "kimi"]


def _validate(provider: str, key: str) -> bool:
    prefix = KNOWN_PREFIXES.get(provider)
    if prefix and not key.startswith(prefix):
        print(f"  ⚠️  la chiave non inizia con '{prefix}' — verifica che sia quella giusta")
        return False
    return True


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
        marker = " ← rilevato" if b == best else ""
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
    _validate(provider, key)
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
    if provider not in providers:
        print(f"⚠️  '{provider}' non è nel catalogo providers.yaml — procedo comunque")

    key = _ask_key(provider)
    if not key:
        return 1
    chosen = _pick_backend(backend)
    keystore.store_key(provider, key, chosen)
    print(f"✓ {provider} salvata ({chosen})")
    return 0


def cmd_setup(backend: str | None) -> int:
    providers = _load_providers()
    print("\n🔐 TramaMind — setup API key")
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
    print(f"\n✓ {len(collected)} chiavi salvate ({chosen})")
    print("Nota: le stesse chiavi vanno inserite in OmniRoute → Dashboard → Providers")
    return 0


def cmd_list() -> int:
    providers = _load_providers()
    print(f"\n{'Provider':<14}{'Stato':<12}{'Storage':<10}Chiave")
    print("─" * 48)
    missing = 0
    for p in providers:
        key, storage = keystore.get_key(p)
        if key:
            print(f"{p:<14}{'✓ presente':<12}{storage or '?':<10}{keystore.mask(key)}")
        else:
            print(f"{p:<14}{'✗ mancante':<12}{'—':<10}")
            missing += 1
    if missing:
        print(f"\n{missing} provider senza chiave: `tramamind keys add <provider>`")
    return 0


def cmd_remove(provider: str) -> int:
    removed = keystore.delete_key(provider)
    if removed:
        print(f"✓ {provider} rimossa da: {', '.join(removed)}")
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
