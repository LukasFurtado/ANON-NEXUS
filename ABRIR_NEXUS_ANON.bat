@echo off
setlocal
title Abrir ANON
cd /d "%~dp0"

if exist "%~dp0backend\.venv\Scripts\python.exe" (
    "%~dp0backend\.venv\Scripts\python.exe" "%~dp0anon_launcher.py"
    exit /b %errorlevel%
)

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 "%~dp0anon_launcher.py"
    exit /b %errorlevel%
)

where python >nul 2>nul
if %errorlevel%==0 (
    python "%~dp0anon_launcher.py"
    exit /b %errorlevel%
)

echo Python nao foi encontrado. Instale o Python 3.11+ ou execute primeiro o instalador local do ANON.
pause
