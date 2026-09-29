#!/usr/bin/env bash
# TramaMind — avvio gateway OpenClaw (L5b)
# Da includere in scripts/start-all.sh DOPO OmniRoute.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPENCLAW_DIR="${SCRIPT_DIR}/../integrations/openclaw"

# OmniRoute deve essere raggiungibile prima di avviare il gateway
echo "[tramamind] attesa OmniRoute su :20128..."
until curl -sf http://localhost:20128/v1/models >/dev/null 2>&1; do
  sleep 2
done
echo "[tramamind] OmniRoute OK — avvio OpenClaw"

cd "${OPENCLAW_DIR}"
[[ -f .env ]] || { echo "ERRORE: manca .env (cp .env.example .env)"; exit 1; }

docker compose up -d
echo "[tramamind] OpenClaw avviato. Log: docker logs tramamind-openclaw --follow"
