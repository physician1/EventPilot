$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path '.venv/Scripts/python.exe')) {
    throw 'First follow the Python environment setup in README.md.'
}
if (-not (Test-Path 'frontend/dist/index.html')) {
    throw 'First run npm ci and npm run build in the frontend directory.'
}
Write-Host 'EventPilot: http://127.0.0.1:8000 (Ctrl+C to stop)'
& ./.venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
