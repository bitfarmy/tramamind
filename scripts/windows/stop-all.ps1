$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $root
if (Test-Path .\.venv\Scripts\tramamind.exe) { & .\.venv\Scripts\tramamind.exe down @args }
elseif (Get-Command tramamind -ErrorAction SilentlyContinue) { tramamind down @args }
else { python -m cli down @args }
