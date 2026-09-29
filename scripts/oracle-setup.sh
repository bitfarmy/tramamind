#!/usr/bin/env bash
# TramaMind — provisioning VM Oracle Cloud Always Free (Ubuntu 24.04 ARM64)
# Uso: curl -fsSL https://raw.githubusercontent.com/bitfarmy/tramamind/main/scripts/oracle-setup.sh | bash
#
# Allocazione RAM target (12 GB):
#   sistema+Docker ~2GB · vLLM(Qwen3-4B) ~4GB · Entropy Gate ~1GB · OmniRoute ~0.5GB · buffer ~4.5GB
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

# ── vLLM (CPU backend) + modelli approvati per 12 GB ──────────
# Primario: GPT-5-Distill-Qwen3-4B (~3 GB) · Fast: Gemini3.5-Code-Reasoner-2B (~1.5 GB)
# ESCLUSI: Qwen3.5-9B (troppo rischioso su 12 GB), Gemopus/Qwopus (solo PC locale)
if ! python3 -c "import vllm" 2>/dev/null; then
  echo "[tramamind] installazione vLLM (CPU backend, ARM64)..."
  pip3 install --user vllm || {
    echo "[tramamind] ATTENZIONE: build vLLM ARM64 fallita."
    echo "[tramamind] Fallback: installa Ollama (curl -fsSL https://ollama.com/install.sh | sh)"
    echo "[tramamind] e servi gli stessi pesi via Ollama. Vedi docs/oracle-free-tier.md"
  }
fi

# Scarica i pesi (richiede huggingface-cli login se i repo sono gated)
if command -v huggingface-cli >/dev/null 2>&1 || pip3 install --user -q huggingface_hub; then
  echo "[tramamind] download modelli (4B primario + 2B fast)..."
  # TODO: sostituire con i repo HF effettivi dei distillati
  # huggingface-cli download <org>/GPT-5-Distill-Qwen3-4B
  # huggingface-cli download <org>/Gemini3.5-Code-Reasoner-2B
  echo "[tramamind] (configura i repo HF dei distillati in questo script)"
fi

# ── Firewall: solo SSH in ingresso ────────────────────────────
# OmniRoute (20128), vLLM, Entropy Gate (9090) e OpenClaw (18789) NON vanno
# esposti: l'accesso remoto avviene via Tailscale (vedi docs/oracle-free-tier.md)
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
echo "  3. Avvio:      cd ~/tramamind && ./scripts/start-all.sh && ./scripts/start-openclaw.sh"
echo "  (rieloggati per usare docker senza sudo)"
