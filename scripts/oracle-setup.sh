#!/usr/bin/env bash
# TramaMind — provisioning VM Oracle Cloud Always Free (Ubuntu 24.04 ARM64)
# Uso: curl -fsSL https://raw.githubusercontent.com/bitfarmy/tramamind/main/scripts/oracle-setup.sh | bash
set -euo pipefail

echo "[tramamind] provisioning nodo always-on (Oracle A1.Flex, 2 OCPU / 12 GB)"

# ── Pacchetti base ────────────────────────────────────────────
sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get install -y curl git jq ufw ca-certificates

# ── Docker ────────────────────────────────────────────────────
if ! command -v docker >/dev/null 2>&1; then
  echo "[tramamind] installazione Docker..."
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi

# ── Ollama (supporta ARM64) ───────────────────────────────────
if ! command -v ollama >/dev/null 2>&1; then
  echo "[tramamind] installazione Ollama..."
  curl -fsSL https://ollama.com/install.sh | sh
fi

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
echo "  2. Stack:      cd ~/tramamind && ./scripts/install.sh --pull-models"
echo "  3. Chiavi:     compila .env con le API gratuite"
echo "  4. Avvio:      ./scripts/start-all.sh && ./scripts/start-openclaw.sh"
echo "  (rieloggati per usare docker senza sudo)"
