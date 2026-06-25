$ErrorActionPreference = "Stop"

Write-Host "ANON - verificacao do modelo qwen3:32b" -ForegroundColor Cyan
Write-Host "O modelo derivado NEXUS-anon:latest nao e mais criado pelo fluxo padrao."
Write-Host "A especializacao do ANON fica nos prompts, perfis, regras, validador e corretor JSON internos."

$ollama = Get-Command "ollama" -ErrorAction SilentlyContinue
if (-not $ollama) {
    Write-Host "Ollama nao encontrado. Instale o Ollama e execute: ollama pull qwen3:32b" -ForegroundColor Red
    exit 1
}

$models = (& ollama list) -join "`n"
if ($models -match "qwen3:32b") {
    Write-Host "qwen3:32b detectado. Modelo padrao pronto para o ANON." -ForegroundColor Green
    exit 0
}

Write-Host "qwen3:32b nao foi encontrado." -ForegroundColor Yellow
Write-Host "Execute: ollama pull qwen3:32b"
exit 1
