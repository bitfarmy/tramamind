$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $root
if (Test-Path .\.venv\Scripts\tramamind.exe) { & .\.venv\Scripts\tramamind.exe chat @args }
elseif (Get-Command tramamind -ErrorAction SilentlyContinue) { tramamind chat @args }
else { python -m cli chat @args }
