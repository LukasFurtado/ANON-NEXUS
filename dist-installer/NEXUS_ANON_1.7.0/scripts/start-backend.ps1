$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\..\backend"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python nao foi encontrado no PATH." -ForegroundColor Red
    Write-Host "Instale Python 3.11+ pelo site python.org e marque a opcao 'Add python.exe to PATH'."
    exit 1
}

if (-not (Test-Path ".venv")) {
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install --upgrade pip
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}

.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
