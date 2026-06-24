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

$ollamaReady = Test-Http "http://127.0.0.1:11434/api/tags"
if (-not $ollamaReady) {
    $ollamaCommand = Get-Command "ollama" -ErrorAction SilentlyContinue
    if ($ollamaCommand) {
        Start-Process -FilePath $ollamaCommand.Source -ArgumentList "serve" -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs "ollama.out.log") -RedirectStandardError (Join-Path $logs "ollama.err.log")
        Write-Host "Ollama iniciado em segundo plano."
        for ($i = 0; $i -lt 20; $i++) {
            if (Test-Http "http://127.0.0.1:11434/api/tags") {
                $ollamaReady = $true
                break
            }
            Start-Sleep -Seconds 1
        }
    } else {
        Write-Host "Ollama nao encontrado no PATH. Instale ou abra o Ollama antes de anonimizar." -ForegroundColor Yellow
    }
}

if (-not $ollamaReady) {
    Write-Host "Atencao: a interface pode abrir, mas a anonimizacao sera bloqueada ate o Ollama responder." -ForegroundColor Yellow
}

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
