@echo off
setlocal
title Gerar pacote NEXUS ANON
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build-installer-package.ps1"

echo.
pause
