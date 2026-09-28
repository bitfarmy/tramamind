# -------------------------------------------------------------
# TramaMind - chat CLI (Windows, PowerShell)
# Mostra contenuto e token dopo ogni risposta. Logga in
# data\requests.jsonl.
#
# Uso:
#   .\scripts\windows\chat.ps1                  # interattiva
#   .\scripts\windows\chat.ps1 "una domanda"    # singolo colpo
#   $env:TRAMAMIND_MODEL="qwen3:8b"; .\scripts\windows\chat.ps1
# -------------------------------------------------------------
param([string]$Prompt)
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

$Endpoint = if ($env:TRAMAMIND_ENDPOINT) { $env:TRAMAMIND_ENDPOINT } else { 'http://localhost:20128/v1/chat/completions' }
$Model    = if ($env:TRAMAMIND_MODEL)    { $env:TRAMAMIND_MODEL }    else { 'auto' }
$Key      = if ($env:OMNIROUTE_API_KEY)  { $env:OMNIROUTE_API_KEY }  else { 'omniroute' }
$System   = 'Sei TramaMind, assistente personale. Rispondi in italiano, in modo denso e concreto.'

function Invia($testo) {
  $body = @{
    model    = $Model
    messages = @(
      @{ role = 'system'; content = $System },
      @{ role = 'user';   content = $testo }
    )
  } | ConvertTo-Json -Depth 5

  $sw = [Diagnostics.Stopwatch]::StartNew()
  try {
    $res = Invoke-RestMethod -Uri $Endpoint -Method Post `
      -Headers @{ Authorization = "Bearer $Key" } `
      -ContentType 'application/json' -Body $body -TimeoutSec 120
  } catch {
    Write-Host "[X] Errore: $($_.Exception.Message)" -ForegroundColor Red
    return
  }
  $sw.Stop()

  $risposta = $res.choices[0].message.content
  $in  = $res.usage.prompt_tokens
  $out = $res.usage.completion_tokens
  $prov = if ($res.model) { $res.model } else { $Model }

  Write-Host $risposta
  Write-Host ("[i] model={0} - {1}ms - {2} token (in {3} / out {4})" -f `
    $prov, $sw.ElapsedMilliseconds, ($in + $out), $in, $out) -ForegroundColor DarkGray

  $log = @{
    ts = (Get-Date).ToString('o'); model = $prov
    ms = $sw.ElapsedMilliseconds; tokens_in = $in; tokens_out = $out
  } | ConvertTo-Json -Compress
  Add-Content data\requests.jsonl $log
}

if ($Prompt) {
  Invia $Prompt
} else {
  Write-Host "[*] TramaMind chat (modello: $Model) - 'exit' per uscire"
  while ($true) {
    $line = Read-Host "`ntu"
    if ($line -in 'exit', 'quit', '') { break }
    Invia $line
  }
}
