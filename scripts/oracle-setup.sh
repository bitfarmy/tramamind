#!/usr/bin/env bash
# TramaMind — provisioning VM Oracle Cloud Always Free (Ubuntu 24.04 ARM64)
# Uso: curl -fsSL https://raw.githubusercontent.com/bitfarmy/tramamind/main/scripts/oracle-setup.sh | bash
#
# Allocazione RAM target (12 GB):
#   sistema+Docker ~2GB · modello primario ~4GB · OmniRoute(L2 incluso) ~1.5GB · buffer ~4.5GB
#
# I distillati sono modelli PUBBLICI su HuggingFace (autori: Jackrong, 11-47):
# niente da caricare, la VM li scarica direttamente.
set -euo pipefail

echo "[tramamind] provisioning nodo always-on (Oracle A1.Flex, 2 OCPU / 12 GB)"

# ── Pacchetti base ────────────────────────────────────────────
sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get install -y curl git jq ufw ca-certificates python3-pip python3-venv

# ── Docker ────────────────────────────────────────────────────
if ! command -v docker >/dev/null 2>&1; then
  echo "[tramamind] installazione Docker..."
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi

# ── Download modelli (repo HF pubblici, verificati 2026-09-29) ─
# Primario: GPT-5-Distill-Qwen3-4B (Jackrong) — Qwen3-4B distillato su GPT-5
# Fast:     Gemini3.5-Code-Reasoner-2B (11-47) — task veloci e heartbeat
#
# NOTA RUNTIME: su 2 OCPU ARM la via realistica e' GGUF via llama.cpp/Ollama
# (Q4_K_M ~2.5 GB per il 4B). vLLM CPU con safetensors bf16 (~8 GB per il 4B)
# sfora il budget di 12 GB: tenerlo solo come esperimento.
pip3 install --user -q "huggingface_hub[cli]"
HF_BIN="$HOME/.local/bin/huggingface-cli"; [[ -x "$HF_BIN" ]] || HF_BIN="huggingface-cli"

echo "[tramamind] download GGUF del primario (Q4_K_M)..."
"$HF_BIN" download Jackrong/GPT-5-Distill-Qwen3-4B-Instruct-GGUF \
  --include "*Q4_K_M*"

echo "[tramamind] download fast lane 2B..."
"$HF_BIN" download 11-47/Gemini3.5-Code.Reasoner-2b || \
  echo "[tramamind] ATTENZIONE: repo 11-47/Gemini3.5-Code.Reasoner-2b non raggiungibile;"
  echo "[tramamind] alternative: Jackrong/Qwen3.5-2B-Claude-4.6-Opus-Reasoning-Distilled-GGUF"

# ── Runtime: Ollama (default su ARM) ──────────────────────────
if ! command -v ollama >/dev/null 2>&1; then
  echo "[tramamind] installazione Ollama..."
  curl -fsSL https://ollama.com/install.sh | sh
fi
# I GGUF scaricati si importano con:
#   ollama create gpt-5-distill-qwen3-4b -f <Modelfile che punta al .gguf>
# vedi docs/oracle-free-tier.md per il Modelfile di esempio.

# ── Firewall: solo SSH in ingresso ────────────────────────────
# OmniRoute (20128), Ollama (11434) e OpenClaw (18789) NON vanno esposti:
# l'accesso remoto avviene via Tailscale (vedi docs/oracle-free-tier.md)
sudo ufw allow OpenSSH
sudo ufw --force enable

# ── Repo ──────────────────────────────────────────────────────
if [[ ! -d "$HOME/tramamind" ]]; then
  git clone https://github.com/bitfarmy/tramamind.git "$HOME/tramamind"
else
  git -C "$HOME/tramamind" pull --ff-only
fi

# ── Swap di sicurezza (12 GB RAM: margine per i picchi) ───────
if [[ ! -f /swapfile ]]; then
  sudo fallocate -l 4G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

echo ""
echo "[tramamind] provisioning completato."
echo "Prossimi passi:"
echo "  1. Tailscale:  curl -fsSL https://tailscale.com/install.sh | sh && sudo tailscale up"
echo "  2. Chiavi:     compila ~/tramamind/.env con le API gratuite"
echo "  3. Modelli:    importa i GGUF in Ollama (vedi docs/oracle-free-tier.md)"
echo "  4. Avvio:      cd ~/tramamind && ./scripts/start-all.sh"
echo "  (rieloggati per usare docker senza sudo)"
