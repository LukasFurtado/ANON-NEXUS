@echo off
setlocal
title Abrir NEXUS ANON
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-nexus-anon.ps1"
