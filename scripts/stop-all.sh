#!/bin/bash
# TramaMind — Arresto dello stack
# Uso: ./scripts/stop-all.sh
#
# Ferma solo i processi avviati da start-all.sh (tramite i PID in data/).
# I servizi già attivi prima (es. Ollama di sistema) non vengono toccati.

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "🧵 TramaMind — Arresto stack"
echo "============================"

ferma() {
  local nome="$1" pidfile="$2"
  if [ -f "$pidfile" ]; then
    local pid
    pid=$(cat "$pidfile")
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" && echo "→ $nome fermato (PID $pid)"
    else
      echo "→ $nome non era in esecuzione"
    fi
    rm -f "$pidfile"
  else
    echo "→ $nome: nessun PID registrato (non avviato da start-all.sh?)"
  fi
}

ferma "OmniRoute" data/omniroute.pid
ferma "Ollama" data/ollama.pid

echo ""
echo "✅ Fatto."
