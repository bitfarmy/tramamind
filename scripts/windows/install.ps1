# ─────────────────────────────────────────────────────────────
# TramaMind — installazione (Windows, PowerShell)
# Uso: .\scripts\windows\install.ps1 [-PullModels] [-WithOpenHands]
#
# 1. Verifica le dipendenze (Node, Python, Ollama, Docker, OmniRoute)
# 2. Crea .env da .env.example (se assente)
# 3. Crea data\ e workspace\
# 4. -PullModels: scarica una selezione di modelli locali
# 5. -WithOpenHands: scarica le immagini Docker di OpenHands
# ─────────────────────────────────────────────────────────────
param(
  [switch]$PullModels,
  [switch]$WithOpenHands
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Root

Write-Host "🧵 TramaMind — Installazione (Windows)"
Write-Host "======================================="

# ── 1. Dipendenze ────────────────────────────────────────────
$manca = $false
function Verifica($cmd, $hint) {
  if (Get-Command $cmd -ErrorAction SilentlyContinue) {
    Write-Host "  ✓ $cmd"
  } else {
    Write-Host "  ✗ $cmd — $hint"
    $script:manca = $true
  }
}

Verifica node    "installa Node.js >= 22.22.2 o 24.x da https://nodejs.org"
Verifica python  "installa Python 3.10+ da https://python.org (spunta 'Add to PATH')"
Verifica ollama  "installa Ollama per Windows da https://ollama.com/download/windows"
Verifica docker  "installa Docker Desktop da https://docker.com/products/docker-desktop"

if (Get-Command omniroute -ErrorAction SilentlyContinue) {
  Write-Host "  ✓ omniroute"
} else {
  Write-Host "  ! omniroute mancante — provo: npm install -g omniroute"
  npm install -g omniroute
  if ($LASTEXITCODE -ne 0) { Write-Host "  ✗ installazione OmniRoute fallita"; $manca = $true }
}

if ($manca) { Write-Host "`n⚠️  Risolvi le dipendenze mancanti e rilancia."; exit 1 }

# ── 2. Config ────────────────────────────────────────────────
if (-not (Test-Path .env)) {
  Copy-Item .env.example .env
  Write-Host "→ Creato .env da .env.example — compilalo con le tue chiavi"
} else {
  Write-Host "→ .env già presente (non toccato)"
}

# ── 3. Directory dati ────────────────────────────────────────
New-Item -ItemType Directory -Force data, workspace | Out-Null
Write-Host "→ data\ e workspace\ pronte"

# ── 4. Modelli locali (opzionale) ────────────────────────────
if ($PullModels) {
  Write-Host "→ Download modelli locali consigliati (vedi docs\local-models.md)..."
  foreach ($m in 'qwen3:8b', 'qwen2.5-coder:7b', 'deepseek-r1:8b', 'gemma3:4b') {
    ollama pull $m
    if ($LASTEXITCODE -eq 0) { Write-Host "  ✓ $m" }
  }
}

# ── 5. OpenHands (opzionale) ─────────────────────────────────
if ($WithOpenHands) {
  Write-Host "→ Pull immagini OpenHands..."
  docker pull docker.all-hands.dev/all-hands-ai/openhands:latest
  docker pull docker.all-hands.dev/all-hands-ai/runtime:latest
  $oh = Join-Path $env:USERPROFILE '.openhands'
  New-Item -ItemType Directory -Force $oh | Out-Null
  $cfg = Join-Path $oh 'config.toml'
  if (-not (Test-Path $cfg)) { Copy-Item openhands\config.toml $cfg }
  Write-Host "  ✓ OpenHands pronto (config in $cfg)"
}

Write-Host "`n✅ Installazione completata."
Write-Host "   1. Compila .env e inserisci le chiavi anche in OmniRoute"
Write-Host "      (http://localhost:20128 → Providers)"
Write-Host "   2. .\scripts\windows\start-all.ps1   (-NoOpenHands per saltare l'agente)"
Write-Host "   3. .\scripts\windows\doctor.ps1      per la diagnostica"
