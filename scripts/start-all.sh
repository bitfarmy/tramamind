#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# TramaMind — avvio stack
# Avvia (se non già attivi): Ollama → OmniRoute.
# Scrive i PID in data/ così stop-all.sh ferma solo ciò che
# ha avviato questo script.
#
# Uso: ./scripts/start-all.sh
# ─────────────────────────────────────────────────────────────
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
DATA_DIR="$ROOT_DIR/data"
mkdir -p "$DATA_DIR"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
TRAMAMIND_ENDPOINT="${TRAMAMIND_ENDPOINT:-http://localhost:20128/v1/chat/completions}"
OMNIROUTE_BASE="${TRAMAMIND_ENDPOINT%/v1/chat/completions}"

if [[ -t 1 ]]; then
  C_BOLD=$'\033[1m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'; C_RESET=$'\033[0m'
else
  C_BOLD=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_RESET=""
fi

ok()   { printf '  %s✓%s %s\n' "$C_GREEN" "$C_RESET" "$1"; }
warn() { printf '  %s!%s %s\n' "$C_YELLOW" "$C_RESET" "$1"; }
bad()  { printf '  %s✗%s %s\n' "$C_RED" "$C_RESET" "$1"; }
up()   { curl -sS --max-time 3 -o /dev/null "$1" 2>/dev/null; }

printf '%sTramaMind — avvio stack%s\n' "$C_BOLD" "$C_RESET"

# ── 1. Ollama (L1) ───────────────────────────────────────────
if up "$OLLAMA_BASE_URL/api/tags"; then
  ok "Ollama già attivo ($OLLAMA_BASE_URL) — non lo tocco"
elif command -v ollama >/dev/null 2>&1; then
  nohup ollama serve >"$DATA_DIR/ollama.log" 2>&1 &
  echo $! > "$DATA_DIR/ollama.pid"
  sleep 2
  if up "$OLLAMA_BASE_URL/api/tags"; then
    ok "Ollama avviato ($OLLAMA_BASE_URL, PID $(cat "$DATA_DIR/ollama.pid"))"
  else
    bad "Ollama non risponde dopo l'avvio — vedi data/ollama.log"
  fi
else
  bad "ollama non installato — vedi docs/setup.md"
fi

# ── 2. OmniRoute (L4) ────────────────────────────────────────
if up "$OMNIROUTE_BASE/v1/models"; then
  ok "OmniRoute già attivo ($OMNIROUTE_BASE) — non lo tocco"
elif command -v omniroute >/dev/null 2>&1; then
  nohup omniroute >"$DATA_DIR/omniroute.log" 2>&1 &
  echo $! > "$DATA_DIR/omniroute.pid"
  sleep 4
  if up "$OMNIROUTE_BASE/v1/models"; then
    ok "OmniRoute avviato ($OMNIROUTE_BASE, PID $(cat "$DATA_DIR/omniroute.pid"))"
  else
    bad "OmniRoute non risponde dopo l'avvio — vedi data/omniroute.log"
  fi
else
  bad "omniroute non installato — npm install -g omniroute"
fi

# ── Riepilogo ────────────────────────────────────────────────
printf '\n%sStato finale%s\n' "$C_BOLD" "$C_RESET"
up "$OLLAMA_BASE_URL/api/tags"  && ok "L1 Ollama     $OLLAMA_BASE_URL"  || bad "L1 Ollama giù"
up "$OMNIROUTE_BASE/v1/models"  && ok "L4 OmniRoute  $OMNIROUTE_BASE"   || bad "L4 OmniRoute giù"

printf '\nDashboard: %s%s%s\n' "$C_BOLD" "$OMNIROUTE_BASE" "$C_RESET"
printf 'Pronto? → %s./scripts/chat.sh%s\n' "$C_BOLD" "$C_RESET"
