"""
TramaMind CLI — entrypoint `tramamind`.

Comandi attivi: keys (fase 2).
In roadmap: topology (fase 3, vedi docs/cloud-implementation.md).
"""
from __future__ import annotations

import argparse
import sys

from cli import keys as keys_cmd


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tramamind",
        description="TramaMind — IA personale multi-modello",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_keys = sub.add_parser("keys", help="Gestione API key (keyring/age/.env)")
    keys_sub = p_keys.add_subparsers(dest="keys_command", required=True)

    p_add = keys_sub.add_parser("add", help="Aggiungi/aggiorna una chiave")
    p_add.add_argument("provider", nargs="?", help="es. google, groq, kimi…")
    p_add.add_argument("--backend", choices=keystore_backends(),
                       help="Storage (default: rilevamento automatico)")

    p_setup = keys_sub.add_parser("setup", help="Wizard interattivo per tutti i provider")
    p_setup.add_argument("--backend", choices=keystore_backends())

    keys_sub.add_parser("list", help="Stato delle chiavi (mascherate)")

    p_rm = keys_sub.add_parser("remove", help="Rimuovi una chiave da tutti gli storage")
    p_rm.add_argument("provider")

    p_topo = sub.add_parser("topology", help="Setup hub/edge (fase 3)")
    p_topo.set_defaults(not_implemented=True)

    return parser


def keystore_backends() -> list[str]:
    from router.keystore import BACKENDS
    return list(BACKENDS)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if getattr(args, "not_implemented", False):
        print("`tramamind topology` è in roadmap (fase 3).")
        print("Vedi docs/cloud-implementation.md — sezione Roadmap.")
        return 1

    if args.command == "keys":
        return keys_cmd.run(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
