@echo off
setlocal
title Instalador NEXUS ANON
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install-nexus-anon.ps1"

echo.
echo Se a instalacao terminou sem erro, use ABRIR_NEXUS_ANON.bat para iniciar o sistema.
pause
