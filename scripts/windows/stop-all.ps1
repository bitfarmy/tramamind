# -------------------------------------------------------------
# TramaMind - Arresto dello stack (Windows, PowerShell)
# Uso: .\scripts\windows\stop-all.ps1
#
# Ferma solo i processi avviati da start-all.ps1 (PID in data\).
# I servizi gia' attivi prima (es. Ollama tray di Windows) non
# vengono toccati.
# -------------------------------------------------------------
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Root

Write-Host "[*] TramaMind - Arresto stack"
Write-Host "============================"

function Ferma($nome, $pidfile) {
  if (Test-Path $pidfile) {
    $processId = Get-Content $pidfile
    $proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($proc) {
      Stop-Process -Id $processId -Force
      Write-Host "-> $nome fermato (PID $processId)"
    } else {
      Write-Host "-> $nome non era in esecuzione"
    }
    Remove-Item $pidfile
  } else {
    Write-Host "-> $nome : nessun PID registrato (non avviato da start-all.ps1?)"
  }
}

Ferma 'OmniRoute' 'data\omniroute.pid'
Ferma 'Ollama' 'data\ollama.pid'

# OpenHands gira in Docker: lo ferma via container, non via PID
$running = docker ps --format '{{.Names}}' 2>$null
if ($running -match '^tramamind-openhands$') {
  docker stop tramamind-openhands | Out-Null
  Write-Host "-> OpenHands fermato (container)"
}

Write-Host ""
Write-Host "[OK] Fatto."
