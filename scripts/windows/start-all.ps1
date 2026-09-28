# -------------------------------------------------------------
# TramaMind - Avvio dello stack (Windows, PowerShell)
# Uso: .\scripts\windows\start-all.ps1 [-NoOpenHands]
#
# Avvia Ollama (L1) e OmniRoute (L4) in background, PID in data\.
# OpenHands (L-APP) e' opzionale e gira in Docker.
# I servizi gia' attivi prima NON vengono riavviati ne' registrati:
# stop-all.ps1 ferma solo cio' che e' stato avviato da qui.
# -------------------------------------------------------------
param([switch]$NoOpenHands)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Root
New-Item -ItemType Directory -Force data | Out-Null

# Carica .env
if (Test-Path .env) {
  Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([A-Z_]+)\s*=\s*(.*)$' -and $_ -notmatch '^\s*#') {
      [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2].Trim(), 'Process')
    }
  }
}

function Test-Url($url) {
  try { Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3 | Out-Null; return $true }
  catch { return $false }
}

function Wait-Url($url, $nome, $tentativi = 30) {
  for ($i = 0; $i -lt $tentativi; $i++) {
    if (Test-Url $url) { return $true }
    Start-Sleep -Seconds 2
  }
  Write-Host "  [X] $nome non risponde su $url"
  return $false
}

Write-Host "[*] TramaMind - Avvio stack"
Write-Host "============================"

# -- L1: Ollama -------------------------------------------------
if (Test-Url 'http://localhost:11434/api/version') {
  Write-Host "-> Ollama gia' attivo (non lo tocco)"
} else {
  Write-Host "-> Avvio Ollama..."
  $p = Start-Process ollama -ArgumentList 'serve' -WindowStyle Hidden `
       -RedirectStandardOutput data\ollama.log -RedirectStandardError data\ollama.err -PassThru
  $p.Id | Out-File data\ollama.pid
  Wait-Url 'http://localhost:11434/api/version' 'Ollama' 15 | Out-Null
}

# -- L4: OmniRoute ----------------------------------------------
# Heap V8 maggiorato: gli agenti di coding con contesti lunghi
# saturano il default da 1 GB (FATAL ERROR oltre ~12 GiB).
if (Test-Url 'http://localhost:20128') {
  Write-Host "-> OmniRoute gia' attivo (non lo tocco)"
} else {
  Write-Host "-> Avvio OmniRoute :20128..."
  if (-not $env:OMNIROUTE_MEMORY_MB) { $env:OMNIROUTE_MEMORY_MB = '8192' }
  $p = Start-Process 'omniroute.cmd' -WindowStyle Hidden `
       -RedirectStandardOutput data\omniroute.log -RedirectStandardError data\omniroute.err -PassThru
  $p.Id | Out-File data\omniroute.pid
  Wait-Url 'http://localhost:20128' 'OmniRoute' 30 | Out-Null
}

# -- L-APP: OpenHands (Docker, opzionale) ------------------------
if (-not $NoOpenHands) {
  if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "-> OpenHands saltato: docker non trovato"
  } elseif (docker ps --format '{{.Names}}' | Select-String -Pattern '^tramamind-openhands$' -Quiet) {
    Write-Host "-> OpenHands gia' attivo (container tramamind-openhands)"
  } else {
    Write-Host "-> Avvio OpenHands :3000 (Docker)..."
    $ws = if ($env:WORKSPACE_BASE) { $env:WORKSPACE_BASE } else { Join-Path $Root 'workspace' }
    New-Item -ItemType Directory -Force $ws | Out-Null
    $model = if ($env:OPENHANDS_MODEL) { $env:OPENHANDS_MODEL } else { 'openai/auto' }
    $key   = if ($env:OMNIROUTE_API_KEY) { $env:OMNIROUTE_API_KEY } else { 'omniroute' }
    docker run -d --rm `
      --name tramamind-openhands `
      -e SANDBOX_RUNTIME_CONTAINER_IMAGE=docker.all-hands.dev/all-hands-ai/runtime:latest `
      -e LLM_MODEL=$model `
      -e LLM_BASE_URL=http://host.docker.internal:20128/v1 `
      -e LLM_API_KEY=$key `
      -e LLM_NUM_RETRIES=2 `
      -e LLM_TIMEOUT=300 `
      -v /var/run/docker.sock:/var/run/docker.sock `
      -v "$env:USERPROFILE\.openhands:/.openhands" `
      -v "${ws}:/opt/workspace_base" `
      -p 3000:3000 `
      --add-host host.docker.internal:host-gateway `
      docker.all-hands.dev/all-hands-ai/openhands:latest | Out-File data\openhands.log
  }
}

Write-Host ""
Write-Host "[OK] Stack attivo:"
Write-Host "   Ollama    -> http://localhost:11434"
Write-Host "   OmniRoute -> http://localhost:20128  (dashboard + /v1)"
if (-not $NoOpenHands) { Write-Host "   OpenHands -> http://localhost:3000" }
Write-Host ""
Write-Host "   Chat CLI: .\scripts\windows\chat.ps1"
Write-Host "   Stop:     .\scripts\windows\stop-all.ps1"
