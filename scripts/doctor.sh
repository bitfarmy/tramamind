#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# TramaMind — doctor: diagnostica completa dello stack
# Controlla dipendenze, hardware, servizi, configurazione e
# modelli locali. Exit code 1 se c'è almeno un errore.
#
# Uso: ./scripts/doctor.sh
# ─────────────────────────────────────────────────────────────
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"

if [[ -t 1 ]]; then
  C_DIM=$'\033[2m'; C_BOLD=$'\033[1m'
  C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'; C_RESET=$'\033[0m'
else
  C_DIM=""; C_BOLD=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_RESET=""
fi

N_OK=0; N_WARN=0; N_FAIL=0
ok()   { printf '  %s✓%s %s\n' "$C_GREEN" "$C_RESET" "$1"; N_OK=$((N_OK+1)); }
warn() { printf '  %s!%s %s\n' "$C_YELLOW" "$C_RESET" "$1"; N_WARN=$((N_WARN+1)); }
fail() { printf '  %s✗%s %s\n' "$C_RED" "$C_RESET" "$1"; N_FAIL=$((N_FAIL+1)); }
section() { printf '\n%s%s%s\n' "$C_BOLD" "$1" "$C_RESET"; }

# Config (se presente) — serve ai check su endpoint e chiavi
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi
TRAMAMIND_ENDPOINT="${TRAMAMIND_ENDPOINT:-http://localhost:20128/v1/chat/completions}"
OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
OMNIROUTE_BASE="${TRAMAMIND_ENDPOINT%/v1/chat/completions}"

printf '%s%sTramaMind doctor%s — diagnostica dello stack' "$C_BOLD" "$C_DIM" "$C_RESET"

# ── 1. Dipendenze ────────────────────────────────────────────
section "1 · Dipendenze"

for cmd in curl git python3 node ollama; do
  if command -v "$cmd" >/dev/null 2>&1; then
    ok "$cmd installato ($($cmd --version 2>/dev/null | head -n1))"
  else
    fail "$cmd mancante — vedi docs/setup.md"
  fi
done

if command -v jq >/dev/null 2>&1; then
  ok "jq installato (benchmark)"
else
  warn "jq mancante — serve a benchmarks/benchmark.sh: sudo apt install jq"
fi

if command -v omniroute >/dev/null 2>&1; then
  ok "omniroute installato"
else
  fail "omniroute mancante — npm install -g omniroute"
fi

if command -v node >/dev/null 2>&1; then
  node_major="$(node --version | sed 's/^v//' | cut -d. -f1)"
  if [[ "$node_major" -ge 20 ]]; then
    ok "Node >= 20 (v$node_major)"
  else
    fail "Node $node_major < 20 — aggiorna Node.js"
  fi
fi

if command -v python3 >/dev/null 2>&1; then
  if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
    ok "Python >= 3.10"
  else
    fail "Python < 3.10 — aggiorna Python"
  fi
fi

# ── 2. Hardware ──────────────────────────────────────────────
section "2 · Hardware"

if [[ -r /proc/meminfo ]]; then
  ram_gb="$(awk '/MemTotal/ {printf "%d", $2/1024/1024}' /proc/meminfo)"
  if [[ "$ram_gb" -ge 16 ]]; then
    ok "RAM: ${ram_gb} GB (>= 16)"
  elif [[ "$ram_gb" -ge 8 ]]; then
    warn "RAM: ${ram_gb} GB — sotto i 16 GB consigliati, solo modelli piccoli"
  else
    fail "RAM: ${ram_gb} GB — insufficiente"
  fi
else
  warn "Impossibile leggere /proc/meminfo"
fi

disk_gb="$(df --output=avail -BG "$ROOT_DIR" 2>/dev/null | tail -n1 | tr -dc '0-9')"
if [[ -n "$disk_gb" ]]; then
  if [[ "$disk_gb" -ge 50 ]]; then
    ok "Disco: ${disk_gb} GB liberi (>= 50)"
  else
    warn "Disco: ${disk_gb} GB liberi — sotto i 50 GB consigliati"
  fi
fi

# ── 3. Servizi ───────────────────────────────────────────────
section "3 · Servizi"

http_code() { curl -sS --max-time 3 -o /dev/null -w '%{http_code}' "$1" 2>/dev/null || echo "000"; }

code="$(http_code "$OLLAMA_BASE_URL/api/tags")"
if [[ "$code" == "200" ]]; then
  ok "Ollama risponde su $OLLAMA_BASE_URL (L1/L3C)"
else
  fail "Ollama non risponde su $OLLAMA_BASE_URL — avvia con: ollama serve"
fi

code="$(http_code "$OMNIROUTE_BASE/v1/models")"
if [[ "$code" == "000" ]]; then
  fail "OmniRoute non risponde su $OMNIROUTE_BASE — ./scripts/start-all.sh"
else
  ok "OmniRoute risponde su $OMNIROUTE_BASE (HTTP $code)"
fi

# ── 4. Configurazione ────────────────────────────────────────
section "4 · Configurazione"

if [[ -f "$ENV_FILE" ]]; then
  ok ".env presente"
  n_keys=0
  for k in KIMI_API_KEY GOOGLE_API_KEY GROQ_API_KEY NVIDIA_API_KEY CEREBRAS_API_KEY OPENROUTER_API_KEY; do
    v="${!k:-}"
    [[ -n "$v" ]] && n_keys=$((n_keys+1))
  done
  if [[ "$n_keys" -gt 0 ]]; then
    ok "Chiavi API in .env: $n_keys/6 (valori mai mostrati)"
  else
    warn "Nessuna chiave API in .env — funzioneranno solo i modelli locali"
  fi
  printf '  %s…%s ricorda: le chiavi vanno anche nella dashboard OmniRoute (Providers)\n' "$C_DIM" "$C_RESET"
else
  fail ".env mancante — cp .env.example .env"
fi

# ── 5. Modelli locali ────────────────────────────────────────
section "5 · Modelli locali (L3C)"

if [[ "$(http_code "$OLLAMA_BASE_URL/api/tags")" == "200" ]]; then
  models="$(ollama list 2>/dev/null || true)"
  found=0
  for kw in qwen gemma deepseek llama; do
    if printf '%s' "$models" | grep -qi "$kw"; then
      found=$((found+1))
    fi
  done
  n_models="$(printf '%s\n' "$models" | tail -n +2 | grep -c . || true)"
  if [[ "$found" -gt 0 ]]; then
    ok "Modelli installati: $n_models (famiglie presenti: $found/4)"
    printf '%s\n' "$models" | tail -n +2 | grep . | while read -r line; do
      printf '  %s·%s %s\n' "$C_DIM" "$C_RESET" "$line"
    done
  else
    warn "Nessun modello del catalogo trovato — ./scripts/install.sh --pull-models"
  fi
else
  warn "Ollama non raggiungibile — salto il controllo modelli"
fi

# ── Riepilogo ────────────────────────────────────────────────
section "Riepilogo"
printf '  %s%d ok%s · %s%d avvisi%s · %s%d errori%s\n\n' \
  "$C_GREEN" "$N_OK" "$C_RESET" "$C_YELLOW" "$N_WARN" "$C_RESET" "$C_RED" "$N_FAIL" "$C_RESET"

[[ "$N_FAIL" -eq 0 ]]
