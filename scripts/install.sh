#!/usr/bin/env bash
# Installa il CLI in .venv. Non avvia OpenHands e non installa OmniRoute.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -e .

echo "CLI pronto: $ROOT/.venv/bin/tramamind"
echo "  tramamind setup"
echo "  tramamind pull"
echo "  tramamind chat"
echo "Ollama, se manca: https://ollama.com"

if [[ "${1:-}" == "--pull" ]]; then
  exec "$ROOT/.venv/bin/tramamind" setup --non-interactive --pull
fi
