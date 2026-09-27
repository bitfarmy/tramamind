#!/bin/bash
# ─────────────────────────────────────────────────────────────
# TramaMind — Avvio dello stack
# Uso: ./scripts/start-all.sh [--no-openhands]
#
# Avvia Ollama (L1) e OmniRoute (L4) in background, PID in data/.
# OpenHands (L-APP) è opzionale e gira in Docker.
# I servizi già attivi prima NON vengono riavviati né registrati:
# stop-all.sh ferma solo ciò che è stato avviato da qui.
# ─────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
mkdir -p data

WITH_OPENHANDS=1
[[ "${1:-}" == "--no-openhands" ]] && WITH_OPENHANDS=0

[[ -f .env ]] && { set -a; source .env; set +a; }

echo "🧵 TramaMind — Avvio stack"
echo "============================"

# ── L1: Ollama ───────────────────────────────────────────────
if curl -sf http://localhost:11434/api/version >/dev/null 2>&1; then
  echo "→ Ollama già attivo (non lo tocco)"
else
  echo "→ Avvio Ollama..."
  nohup ollama serve > data/ollama.log 2>&1 &
  echo $! > data/ollama.pid
  for _ in $(seq 1 15); do
    curl -sf http://localhost:11434/api/version >/dev/null 2>&1 && break
    sleep 1
  done
fi

# ── L4: OmniRoute ────────────────────────────────────────────
# Heap V8 maggiorato: gli agenti di coding con contesti lunghi
# saturano il default da 1 GB (FATAL ERROR oltre ~12 GiB).
if curl -sf http://localhost:20128 >/dev/null 2>&1; then
  echo "→ OmniRoute già attivo (non lo tocco)"
else
  echo "→ Avvio OmniRoute :20128..."
  OMNIROUTE_MEMORY_MB="${OMNIROUTE_MEMORY_MB:-8192}" \
    nohup omniroute > data/omniroute.log 2>&1 &
  echo $! > data/omniroute.pid
  for _ in $(seq 1 30); do
    curl -sf http://localhost:20128 >/dev/null 2>&1 && break
    sleep 1
  done
fi

# ── L-APP: OpenHands (Docker, opzionale) ─────────────────────
if [[ "$WITH_OPENHANDS" == "1" ]]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "→ OpenHands saltato: docker non trovato"
  elif docker ps --format '{{.Names}}' | grep -q '^tramamind-openhands$'; then
    echo "→ OpenHands già attivo (container tramamind-openhands)"
  else
    echo "→ Avvio OpenHands :3000 (Docker)..."
    mkdir -p "${WORKSPACE_BASE:-$ROOT/workspace}"
    docker run -d --rm \
      --name tramamind-openhands \
      -e SANDBOX_RUNTIME_CONTAINER_IMAGE=docker.all-hands.dev/all-hands-ai/runtime:latest \
      -e LLM_MODEL="${OPENHANDS_MODEL:-openai/auto}" \
      -e LLM_BASE_URL="http://host.docker.internal:20128/v1" \
      -e LLM_API_KEY="${OMNIROUTE_API_KEY:-omniroute}" \
      -e LLM_NUM_RETRIES=2 \
      -e LLM_TIMEOUT=300 \
      -v /var/run/docker.sock:/var/run/docker.sock \
      -v ~/.openhands:/.openhands \
      -v "${WORKSPACE_BASE:-$ROOT/workspace}:/opt/workspace_base" \
      -p 3000:3000 \
      --add-host host.docker.internal:host-gateway \
      docker.all-hands.dev/all-hands-ai/openhands:latest \
      > data/openhands.log 2>&1
  fi
fi

echo ""
echo "✅ Stack attivo:"
echo "   Ollama    → http://localhost:11434"
echo "   OmniRoute → http://localhost:20128  (dashboard + /v1)"
[[ "$WITH_OPENHANDS" == "1" ]] && echo "   OpenHands → http://localhost:3000"
echo ""
echo "   Chat CLI: ./scripts/chat.sh"
echo "   Stop:     ./scripts/stop-all.sh"
