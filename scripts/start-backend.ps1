$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\..\backend"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python nao foi encontrado no PATH." -ForegroundColor Red
    Write-Host "Instale Python 3.11+ pelo site python.org e marque a opcao 'Add python.exe to PATH'."
    exit 1
}

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if (-not (Get-Command uvicorn -ErrorAction SilentlyContinue)) {
    Write-Host "Uvicorn nao foi instalado. A instalacao do requirements.txt falhou antes de concluir." -ForegroundColor Red
    Write-Host "Rode: python -m pip install -r requirements.txt"
    exit 1
}

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
