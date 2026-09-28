# ─────────────────────────────────────────────────────────────
# TramaMind — doctor: diagnostica dello stack (Windows, PowerShell)
# Uso: .\scripts\windows\doctor.ps1
# Exit code 1 se c'è almeno un errore.
# ─────────────────────────────────────────────────────────────
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Root

$script:fail = 0
function Ok($m)   { Write-Host "  ✓ $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  ! $m" -ForegroundColor Yellow }
function Bad($m)  { Write-Host "  ✗ $m" -ForegroundColor Red; $script:fail++ }
function Sezione($m) { Write-Host "`n$m" -ForegroundColor White }

# Carica .env
if (Test-Path .env) {
  Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([A-Z_]+)\s*=\s*(.*)$' -and $_ -notmatch '^\s*#') {
      [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2].Trim(), 'Process')
    }
  }
}

Sezione "Dipendenze"
foreach ($c in 'node', 'python', 'ollama', 'docker', 'omniroute') {
  if (Get-Command $c -ErrorAction SilentlyContinue) { Ok $c } else { Bad "$c mancante" }
}
if (Get-Command node -ErrorAction SilentlyContinue) {
  $v = (node --version).TrimStart('v') -split '\.'
  $ok = ([int]$v[0] -ge 24 -and [int]$v[0] -lt 27) -or `
        ([int]$v[0] -eq 22 -and ([version]($v -join '.') -ge [version]'22.22.2'))
  if ($ok) { Ok "Node $(node --version) compatibile con OmniRoute" }
  else { Bad "Node $(node --version): OmniRoute richiede >= 22.22.2 oppure 24–26" }
}

Sezione "Servizi"
try { Invoke-WebRequest 'http://localhost:11434/api/version' -UseBasicParsing -TimeoutSec 3 | Out-Null; Ok 'Ollama :11434' }
catch { Bad 'Ollama :11434 non risponde (avvia con start-all.ps1)' }
try { Invoke-WebRequest 'http://localhost:20128' -UseBasicParsing -TimeoutSec 3 | Out-Null; Ok 'OmniRoute :20128' }
catch { Bad 'OmniRoute :20128 non risponde (avvia con start-all.ps1)' }
$oh = docker ps --format '{{.Names}}' 2>$null
if ($oh -match '^tramamind-openhands$') { Ok 'OpenHands (container attivo, :3000)' }
else { Warn 'OpenHands non attivo (opzionale: start-all.ps1 senza -NoOpenHands)' }

Sezione "Configurazione"
if (Test-Path .env) { Ok '.env presente' } else { Bad '.env mancante (copia da .env.example)' }
if ($env:OMNIROUTE_API_KEY) { Ok 'OMNIROUTE_API_KEY impostata' }
else { Warn 'OMNIROUTE_API_KEY vuota (Dashboard → Endpoints)' }
$chiavi = 0
foreach ($k in 'GOOGLE_API_KEY','GROQ_API_KEY','NVIDIA_API_KEY','CEREBRAS_API_KEY','OPENROUTER_API_KEY','KIMI_API_KEY') {
  if ([Environment]::GetEnvironmentVariable($k, 'Process')) { $chiavi++ }
}
if ($chiavi -gt 0) { Ok "$chiavi chiavi provider in .env" } else { Warn 'nessuna chiave cloud in .env (solo locale)' }

Sezione "Modelli locali"
try {
  $modelli = (Invoke-RestMethod 'http://localhost:11434/api/tags' -TimeoutSec 3).models
  if ($modelli.Count -gt 0) { Ok "$($modelli.Count) modelli: $($modelli.name -join ', ')" }
  else { Warn 'nessun modello scaricato (install.ps1 -PullModels)' }
} catch { Warn 'impossibile leggere i modelli (Ollama giù?)' }

Write-Host ""
if ($script:fail -gt 0) { Write-Host "✗ $($script:fail) errori" -ForegroundColor Red; exit 1 }
Write-Host "✅ Tutto in ordine" -ForegroundColor Green
