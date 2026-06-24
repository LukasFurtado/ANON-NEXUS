$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\.."
$manifestPath = Join-Path $root "backend\resources\integrity_manifest.json"

$protectedFiles = @(
    "backend\app\api\routes.py",
    "backend\app\core\config.py",
    "backend\app\main.py",
    "backend\app\models\schemas.py",
    "backend\app\pipeline\anonymizer.py",
    "backend\app\pipeline\exporter.py",
    "backend\app\pipeline\ocr.py",
    "backend\app\pipeline\parser.py",
    "backend\app\pipeline\profile_strategy.py",
    "backend\app\pipeline\regex_rules.py",
    "backend\app\pipeline\runner.py",
    "backend\app\pipeline\validator.py",
    "backend\app\services\data_protection.py",
    "backend\app\services\communication_bus.py",
    "backend\app\services\database.py",
    "backend\app\services\error_logger.py",
    "backend\app\services\integrity_guard.py",
    "backend\app\services\knowledge_base.py",
    "backend\app\services\ollama.py",
    "backend\resources\knowledge\anon_operational_knowledge.json",
    "backend\app\version.py",
    "backend\requirements.txt",
    "frontend\src\App.tsx",
    "frontend\src\styles\app.css",
    "frontend\package.json",
    "scripts\start-backend.ps1",
    "scripts\start-frontend.ps1",
    "scripts\start-nexus-anon.ps1"
)

$files = foreach ($relative in $protectedFiles) {
    $absolute = Join-Path $root $relative
    if (-not (Test-Path -LiteralPath $absolute)) {
        throw "Arquivo protegido ausente: $relative"
    }
    [ordered]@{
        path = $relative.Replace("\", "/")
        sha256 = (Get-FileHash -LiteralPath $absolute -Algorithm SHA256).Hash.ToUpperInvariant()
    }
}

$payload = [ordered]@{
    schema = "ANON-INTEGRITY-MANIFEST-v1"
    generated_at = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssK")
    purpose = "Protecao de dados institucional"
    files = $files
}

New-Item -ItemType Directory -Force -Path (Split-Path $manifestPath -Parent) | Out-Null
$json = $payload | ConvertTo-Json -Depth 6
[System.IO.File]::WriteAllText($manifestPath, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
Write-Host "Manifesto de integridade gerado:" -ForegroundColor Green
Write-Host $manifestPath
