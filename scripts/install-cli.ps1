# TramaMind - installazione CLI su Windows (tutto automatico)
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\install-cli.ps1
# Fa tre cose: pip install -e . - aggiunge Scripts al PATH - verifica

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host "[tramamind] installazione pacchetto..." -ForegroundColor Cyan
pip install -e . --quiet --no-warn-script-location
if ($LASTEXITCODE -ne 0) { Write-Host "ERRORE: pip install fallito" -ForegroundColor Red; exit 1 }

# pip puo installare in Scripts di sistema OPPURE in quella utente
# (AppData\Roaming): controlla entrambe e usa quella che contiene l'exe
$Candidates = python -c "import sysconfig; print(sysconfig.get_path('scripts')); print(sysconfig.get_path('scripts', 'nt_user'))"
$ScriptsDir = $null
foreach ($dir in $Candidates) {
    if ($dir -and (Test-Path (Join-Path $dir "tramamind.exe"))) {
        $ScriptsDir = $dir
        break
    }
}
if (-not $ScriptsDir) {
    Write-Host "ERRORE: tramamind.exe non trovato in nessuna cartella Scripts:" -ForegroundColor Red
    $Candidates | ForEach-Object { Write-Host "  - $_" }
    exit 1
}
Write-Host "[tramamind] trovato tramamind.exe in: $ScriptsDir"

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
& tramamind keys list
if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[tramamind] OK - da ora puoi usare: tramamind keys setup" -ForegroundColor Green
    Write-Host "(nelle NUOVE finestre di PowerShell funzionera senza altri passaggi)"
} else {
    Write-Host "ERRORE: la verifica non e' andata a buon fine" -ForegroundColor Red
    exit 1
}
