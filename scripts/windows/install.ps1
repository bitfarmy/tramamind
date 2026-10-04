$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $root
python -m venv .venv
.\.venv\Scripts\pip install -e .
Write-Host "Poi: .\.venv\Scripts\tramamind setup"
