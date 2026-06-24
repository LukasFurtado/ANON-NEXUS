$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\.."

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Ollama nao foi encontrado no PATH." -ForegroundColor Red
    Write-Host "Instale o Ollama e abra um novo PowerShell."
    exit 1
}

$modelfile = Resolve-Path ".\backend\resources\ollama\AnonRIF2.modelfile"
ollama create NEXUS-anon -f $modelfile

Write-Host "Modelo local 'NEXUS-anon:latest' criado com sucesso a partir do Qwen3 32B." -ForegroundColor Green
