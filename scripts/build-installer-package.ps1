$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\.."
$version = "2.0.0"
$packageRoot = Join-Path $root "dist-installer"
$stage = Join-Path $packageRoot "NEXUS_ANON_$version"
$zipPath = Join-Path $packageRoot "NEXUS_ANON_instalador_local_v$version.zip"

& (Join-Path $root "scripts\create-integrity-manifest.ps1")

if (Test-Path $stage) {
    Remove-Item -LiteralPath $stage -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $stage | Out-Null

$excludeDirs = @(
    ".git",
    "NEXUS-ANON",
    "data",
    "backend\.venv",
    "backend\data",
    "frontend\node_modules",
    "dist-installer",
    "logs",
    "tmp_review",
    "tmp_review_latest"
)

$excludeNames = @(
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache"
)

function Test-Excluded($path) {
    $relative = Get-RelativePath $root $path
    foreach ($dir in $excludeDirs) {
        if ($relative -eq $dir -or $relative.StartsWith("$dir\")) {
            return $true
        }
    }
    foreach ($name in $excludeNames) {
        if ((Split-Path $path -Leaf) -eq $name) {
            return $true
        }
    }
    return $false
}

function Test-ExcludedInStage($path) {
    $relative = Get-RelativePath $stage $path
    foreach ($dir in ($excludeDirs | Where-Object { $_ -ne "dist-installer" })) {
        if ($relative -eq $dir -or $relative.StartsWith("$dir\")) {
            return $true
        }
    }
    foreach ($name in $excludeNames) {
        if ((Split-Path $path -Leaf) -eq $name) {
            return $true
        }
    }
    return $false
}

function Get-RelativePath($basePath, $targetPath) {
    $baseFull = [IO.Path]::GetFullPath([string]$basePath).TrimEnd('\') + '\'
    $targetFull = [IO.Path]::GetFullPath([string]$targetPath)
    if ($targetFull.StartsWith($baseFull, [StringComparison]::OrdinalIgnoreCase)) {
        return $targetFull.Substring($baseFull.Length)
    }
    return $targetFull
}

Get-ChildItem -LiteralPath $root -Force | ForEach-Object {
    if (-not (Test-Excluded $_.FullName)) {
        Copy-Item -LiteralPath $_.FullName -Destination $stage -Recurse -Force
    }
}

Get-ChildItem -LiteralPath $stage -Recurse -Force | Where-Object { Test-ExcludedInStage $_.FullName } | Sort-Object FullName -Descending | ForEach-Object {
    Remove-Item -LiteralPath $_.FullName -Recurse -Force
}

if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zipPath -Force
Remove-Item -LiteralPath $stage -Recurse -Force

Write-Host "Pacote gerado:" -ForegroundColor Green
Write-Host $zipPath
Write-Host ""
Write-Host "Observacao: o pacote nao inclui qwen3:32b, .venv nem node_modules. O instalador prepara esses itens na maquina de destino."
