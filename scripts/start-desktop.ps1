$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\..\frontend"

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "Node.js/npm nao foi encontrado no PATH." -ForegroundColor Red
    Write-Host "Instale Node.js 20+ pelo site nodejs.org e abra um novo PowerShell."
    exit 1
}

npm install
npm run tauri dev
