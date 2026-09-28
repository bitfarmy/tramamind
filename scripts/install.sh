#!/bin/bash
# ─────────────────────────────────────────────────────────────
# TramaMind — installazione
# Uso: ./scripts/install.sh [--pull-models] [--with-openhands]
#
# 1. Verifica le dipendenze (Node, Python, Ollama, OmniRoute, jq)
# 2. Crea .env da .env.example (se assente)
# 3. Crea data/ (log, PID, benchmark)
# 4. --pull-models: scarica una selezione di modelli locali
# 5. --with-openhands: scarica le immagini Docker di OpenHands
# ─────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1

PULL_MODELS=0
WITH_OPENHANDS=0
for arg in "$@"; do
  case "$arg" in
    --pull-models)    PULL_MODELS=1 ;;
    --with-openhands) WITH_OPENHANDS=1 ;;
  esac
done

echo "🧵 TramaMind — Installazione"
echo "=============================="

# ── 1. Dipendenze ────────────────────────────────────────────
manca=0
verifica() {
  if command -v "$1" >/dev/null 2>&1; then
    echo "  ✓ $1 ($($1 $2 2>/dev/null | head -1))"
  else
    echo "  ✗ $1 — $3"
    manca=1
  fi
}

verifica node    "--version"    "installa Node.js (OmniRoute richiede >= 22.22.2 oppure 24–26)"
verifica python3 "--version"    "installa Python 3.10+"
verifica ollama  "--version"    "installa Ollama: https://ollama.com"
verifica jq      "--version"    "richiesto da benchmarks/benchmark.sh"

if command -v omniroute >/dev/null 2>&1; then
  echo "  ✓ omniroute"
else
  echo "  ! omniroute mancante — provo: npm install -g omniroute"
  npm install -g omniroute || { echo "  ✗ installazione OmniRoute fallita"; manca=1; }
fi

[[ "$manca" == "1" ]] && { echo ""; echo "⚠️  Risolvi le dipendenze mancanti e rilancia."; exit 1; }

# ── 2. Config ────────────────────────────────────────────────
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "→ Creato .env da .env.example — compilalo con le tue chiavi"
else
  echo "→ .env già presente (non toccato)"
fi

# ── 3. Directory dati ────────────────────────────────────────
mkdir -p data workspace
echo "→ data/ e workspace/ pronte"

# ── 4. Modelli locali (opzionale) ────────────────────────────
if [[ "$PULL_MODELS" == "1" ]]; then
  echo "→ Download modelli locali consigliati (vedi docs/local-models.md)..."
  for m in qwen3:8b qwen2.5-coder:7b deepseek-r1:8b gemma3:4b; do
    ollama pull "$m" && echo "  ✓ $m"
  done
fi

# ── 5. OpenHands (opzionale) ──────────────────────────────────
if [[ "$WITH_OPENHANDS" == "1" ]]; then
  command -v docker >/dev/null 2>&1 || { echo "✗ docker mancante (richiesto da OpenHands)"; exit 1; }
  echo "→ Pull immagini OpenHands..."
  docker pull docker.openhands.dev/openhands/openhands:1.8
  docker pull ghcr.io/openhands/agent-server:1.26.0-python
  mkdir -p ~/.openhands
  [[ -f ~/.openhands/config.toml ]] || cp openhands/config.toml ~/.openhands/config.toml
  echo "  ✓ OpenHands pronto (config in ~/.openhands/config.toml)"
fi

echo ""
echo "✅ Installazione completata."
echo "   1. Compila .env e inserisci le chiavi anche in OmniRoute"
echo "      (http://localhost:20128 → Providers)"
echo "   2. ./scripts/start-all.sh   (aggiungi --no-openhands per saltare l'agente)"
echo "   3. ./scripts/doctor.sh      per la diagnostica"
