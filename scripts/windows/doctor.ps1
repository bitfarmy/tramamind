$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $root
if (Test-Path .\.venv\Scripts\tramamind.exe) { & .\.venv\Scripts\tramamind.exe doctor @args }
elseif (Get-Command tramamind -ErrorAction SilentlyContinue) { tramamind doctor @args }
else { python -m cli doctor @args }
