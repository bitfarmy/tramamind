# TramaMind - installazione CLI su Windows (tutto automatico)
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\install-cli.ps1
# Fa tre cose: pip install -e . - aggiunge Scripts al PATH - verifica

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host "[tramamind] installazione pacchetto..." -ForegroundColor Cyan
pip install -e . --quiet
if ($LASTEXITCODE -ne 0) { Write-Host "ERRORE: pip install fallito" -ForegroundColor Red; exit 1 }

# Trova la cartella Scripts di Python
$ScriptsDir = python -c "import sysconfig; print(sysconfig.get_path('scripts'))"
Write-Host "[tramamind] cartella Scripts: $ScriptsDir"

# Aggiungi al PATH utente se manca
$UserPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if ($UserPath -notlike "*$ScriptsDir*") {
    [Environment]::SetEnvironmentVariable('Path', "$UserPath;$ScriptsDir", 'User')
    Write-Host "[tramamind] aggiunto al PATH utente (permanente)" -ForegroundColor Yellow
} else {
    Write-Host "[tramamind] PATH gia a posto"
}

# Rendi il PATH effettivo in QUESTA sessione (niente riavvio necessario)
$env:Path = "$env:Path;$ScriptsDir"

# Verifica
Write-Host "[tramamind] verifica..." -ForegroundColor Cyan
$exe = Join-Path $ScriptsDir "tramamind.exe"
if (Test-Path $exe) {
    & tramamind keys list
    Write-Host ""
    Write-Host "[tramamind] OK - da ora puoi usare: tramamind keys setup" -ForegroundColor Green
    Write-Host "(nelle NUOVE finestre di PowerShell funzionera senza altri passaggi)"
} else {
    Write-Host "ERRORE: tramamind.exe non trovato in $ScriptsDir" -ForegroundColor Red
    exit 1
}
