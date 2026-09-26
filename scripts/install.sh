#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# TramaMind — installazione
# Verifica dipendenze, crea .env e la cartella data/.
#
# Uso:
#   ./scripts/install.sh                 # setup base
#   ./scripts/install.sh --pull-models   # scarica anche i modelli locali
# ─────────────────────────────────────────────────────────────
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PULL_MODELS=false
[[ "${1:-}" == "--pull-models" ]] && PULL_MODELS=true

if [[ -t 1 ]]; then
  C_BOLD=$'\033[1m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'; C_RESET=$'\033[0m'
else
  C_BOLD=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_RESET=""
fi

info() { printf '%s%s%s\n' "$C_BOLD" "$1" "$C_RESET"; }
ok()   { printf '  %s✓%s %s\n' "$C_GREEN" "$C_RESET" "$1"; }
warn() { printf '  %s!%s %s\n' "$C_YELLOW" "$C_RESET" "$1"; }
die()  { printf '  %s✗ %s%s\n' "$C_RED" "$1" "$C_RESET" >&2; exit 1; }

# ── 1. Dipendenze ────────────────────────────────────────────
info "1 · Verifica dipendenze"

missing=0
for cmd in curl git python3 node ollama; do
  if command -v "$cmd" >/dev/null 2>&1; then
    ok "$cmd"
  else
    warn "$cmd mancante"
    missing=$((missing+1))
  fi
done

if [[ "$missing" -gt 0 ]]; then
  cat >&2 <<'EOF'

Installa i mancanti:
  · Node 20+     → https://nodejs.org  (o: nvm install 20)
  · Python 3.10+ → https://python.org
  · Ollama       → curl -fsSL https://ollama.com/install.sh | sh
EOF
  die "Dipendenze mancanti: $missing"
fi

if command -v omniroute >/dev/null 2>&1; then
  ok "omniroute"
else
  die "omniroute mancante — installalo con: npm install -g omniroute"
fi

if ! command -v jq >/dev/null 2>&1; then
  warn "jq mancante — serve a benchmarks/benchmark.sh: sudo apt install jq"
fi

# ── 2. Configurazione ────────────────────────────────────────
info "2 · Configurazione"

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
  ok "creato .env da .env.example"
else
  ok ".env già presente (non toccato)"
fi

mkdir -p "$ROOT_DIR/data"
ok "cartella data/ pronta (log, PID, risultati benchmark)"

chmod +x "$ROOT_DIR"/scripts/*.sh "$ROOT_DIR"/benchmarks/*.sh 2>/dev/null || true
ok "permessi di esecuzione sugli script"

# ── 3. Modelli locali (opzionale) ────────────────────────────
# Selezione equilibrata per 16 GB RAM. Catalogo completo e
# alternative per hardware diverso: docs/local-models.md
MODELS=(
  "qwen2.5-coder:7b"   # codice, ~5 GB VRAM
  "qwen3:8b"           # generale + ragionamento, ~6 GB
  "gemma3:4b"          # generale leggero, ~3 GB
  "deepseek-r1:8b"     # ragionamento, ~6 GB
)

if $PULL_MODELS; then
  info "3 · Download modelli su Ollama"
  for m in "${MODELS[@]}"; do
    printf '  → ollama pull %s\n' "$m"
    ollama pull "$m" || warn "pull fallito per $m"
  done
else
  info "3 · Modelli locali: saltato (usa --pull-models per scaricarli)"
fi

# ── Fine ─────────────────────────────────────────────────────
info "Installazione completata."
cat <<EOF

Prossimi passi:
  1. Modifica .env con le tue chiavi API
  2. ./scripts/start-all.sh    → avvia Ollama + OmniRoute
  3. Dashboard http://localhost:20128 → Providers: connetti le chiavi
  4. ./scripts/doctor.sh       → verifica lo stack
  5. ./scripts/chat.sh         → prima chat
EOF
