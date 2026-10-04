$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $root
if (Test-Path .\.venv\Scripts\tramamind.exe) { & .\.venv\Scripts\tramamind.exe up @args }
elseif (Get-Command tramamind -ErrorAction SilentlyContinue) { tramamind up @args }
else { python -m cli up @args }
