$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\.."
$logs = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null

function Test-Http($url) {
    try {
        Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2 | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Start-Helper($name, $script, $outLogFile, $errLogFile) {
    $argumentList = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$script`""
    )
    Start-Process -FilePath "powershell.exe" -ArgumentList $argumentList -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput $outLogFile -RedirectStandardError $errLogFile
    Write-Host "$name iniciado em segundo plano."
}

Write-Host "Abrindo NEXUS ANON..."

$backendReady = Test-Http "http://127.0.0.1:8000/health"
if (-not $backendReady) {
    Start-Helper "Backend local" (Join-Path $root "scripts\start-backend.ps1") (Join-Path $logs "backend.out.log") (Join-Path $logs "backend.err.log")
}

$frontendReady = Test-Http "http://localhost:5173/"
if (-not $frontendReady) {
    Start-Helper "Interface local" (Join-Path $root "scripts\start-frontend.ps1") (Join-Path $logs "frontend.out.log") (Join-Path $logs "frontend.err.log")
}

for ($i = 0; $i -lt 45; $i++) {
    if ((Test-Http "http://127.0.0.1:8000/health") -and (Test-Http "http://localhost:5173/")) {
        Start-Process "http://localhost:5173/"
        Write-Host "NEXUS ANON aberto no navegador."
        exit 0
    }
    Start-Sleep -Seconds 1
}

Write-Host "Nao foi possivel confirmar a abertura automatica em 45 segundos." -ForegroundColor Yellow
Write-Host "Abra manualmente: http://localhost:5173/"
Write-Host "Logs: $logs"
pause
