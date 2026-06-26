$ErrorActionPreference = "Stop"

Write-Host "ANON - preparo dos modelos IA Nexus" -ForegroundColor Cyan
Write-Host "Modelos derivados exigidos: nexus.op:latest e nexus-chat:latest"

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$opModelfile = Join-Path $root "resources\ollama\Modelfile.nexus.op"
$chatModelfile = Join-Path $root "resources\ollama\Modelfile.nexus-chat"

$ollama = Get-Command "ollama" -ErrorAction SilentlyContinue
if (-not $ollama) {
    Write-Host "Ollama nao encontrado. Instale o Ollama em https://ollama.com/ e execute novamente." -ForegroundColor Red
    exit 1
}

$models = (& ollama list) -join "`n"
if ($models -notmatch "qwen3:32b") {
    Write-Host "Modelo base qwen3:32b nao encontrado." -ForegroundColor Yellow
    Write-Host "Execute: ollama pull qwen3:32b"
    exit 1
}

if (-not (Test-Path $opModelfile)) {
    Write-Host "Modelfile operacional nao encontrado: $opModelfile" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $chatModelfile)) {
    Write-Host "Modelfile do chat nao encontrado: $chatModelfile" -ForegroundColor Red
    exit 1
}

Write-Host "Criando nexus.op:latest..." -ForegroundColor Cyan
ollama create nexus.op:latest -f $opModelfile

Write-Host "Criando nexus-chat:latest..." -ForegroundColor Cyan
ollama create nexus-chat:latest -f $chatModelfile

Write-Host "IA Nexus preparada com sucesso." -ForegroundColor Green
