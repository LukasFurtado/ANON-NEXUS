$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\.."
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"

function Write-Step($message) {
    Write-Host ""
    Write-Host "== $message ==" -ForegroundColor Cyan
}

function Write-Ok($message) {
    Write-Host "[OK] $message" -ForegroundColor Green
}

function Write-Warn($message) {
    Write-Host "[AVISO] $message" -ForegroundColor Yellow
}

function Assert-Command($name, $installMessage) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if (-not $cmd) {
        Write-Host "[PENDENTE] $name nao encontrado." -ForegroundColor Red
        Write-Host $installMessage
        return $false
    }
    Write-Ok "$name encontrado."
    return $true
}

Write-Host "NEXUS ANON - Instalador local" -ForegroundColor White
Write-Host "Este assistente prepara o ambiente local. O processamento dos documentos continua offline."

Write-Step "1. Conferindo requisitos"
$hasPython = Assert-Command "python" "Instale Python 3.11 ou 3.12 em https://www.python.org/downloads/ e marque Add python.exe to PATH."
$hasNode = Assert-Command "npm" "Instale Node.js LTS em https://nodejs.org/ e abra este instalador novamente."
$hasOllama = Assert-Command "ollama" "Instale Ollama em https://ollama.com/ para usar o modelo local qwen3:32b."

if ($hasPython) {
    $pyVersion = (& python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')").Trim()
    Write-Ok "Python $pyVersion detectado."
    if ($pyVersion -match '^3\.(1[3-9]|[2-9][0-9])\.') {
        Write-Warn "Python muito novo pode causar falhas em bibliotecas OCR. Para maior estabilidade, prefira Python 3.11 ou 3.12."
    }
}

if ($hasPython) {
    Write-Step "2. Preparando backend"
    Set-Location $backend
    if (-not (Test-Path ".venv")) {
        python -m venv .venv
        Write-Ok "Ambiente Python criado."
    } else {
        Write-Ok "Ambiente Python ja existe."
    }
    & ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
    & ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
    Write-Ok "Dependencias do backend instaladas."
}

if ($hasNode) {
    Write-Step "3. Preparando interface"
    Set-Location $frontend
    npm install
    Write-Ok "Dependencias da interface instaladas."
}

if ($hasOllama) {
    Write-Step "4. Conferindo modelo local"
    $models = (& ollama list) -join "`n"
    if ($models -notmatch 'qwen3:32b') {
        Write-Warn "O modelo qwen3:32b ainda nao foi encontrado no Ollama."
        Write-Host "Ele e grande e pode exigir internet, bastante espaco em disco e computador potente."
        $answer = Read-Host "Deseja baixar qwen3:32b agora pelo Ollama? Digite S para sim"
        if ($answer -match '^[sS]') {
            ollama pull qwen3:32b
            Write-Ok "qwen3:32b baixado."
        } else {
            Write-Warn "Download do qwen3:32b ignorado. O ANON precisara desse modelo para executar a IA local."
        }
    } else {
        Write-Ok "qwen3:32b ja esta instalado."
    }
    if (($models -match 'qwen3:32b') -or ($answer -match '^[sS]')) {
        $modelScript = Join-Path $root "scripts\create-anonrif2-model.ps1"
        if (Test-Path $modelScript) {
            & $modelScript
        }
    }
    Write-Ok "Padrao de IA local: nexus.op:latest para pipeline e nexus-chat:latest para orientacao."
}

Write-Step "5. Criando atalho de abertura"
$shortcutTarget = Join-Path $root "ABRIR_NEXUS_ANON.bat"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "NEXUS ANON.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $shortcutTarget
$shortcut.WorkingDirectory = $root
$shortcut.Description = "Abrir NEXUS ANON"
$shortcut.Save()
Write-Ok "Atalho criado na Area de Trabalho: NEXUS ANON"

Write-Step "Instalacao concluida"
Write-Host "Para abrir, use o atalho da Area de Trabalho ou o arquivo ABRIR_NEXUS_ANON.bat."
Write-Host "Endereco local da interface: http://localhost:5173/"
