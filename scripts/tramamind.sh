#!/usr/bin/env bash
# Risolve il CLI: venv del repo, poi il PATH, poi il modulo.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -x "$ROOT/.venv/bin/tramamind" ]]; then
  exec "$ROOT/.venv/bin/tramamind" "$@"
fi
if command -v tramamind >/dev/null 2>&1; then
  exec tramamind "$@"
fi
cd "$ROOT"
exec python3 -m cli "$@"
