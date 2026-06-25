@echo off
setlocal
cd /d "%~dp0"

if exist "%~dp0backend\.venv\Scripts\pythonw.exe" (
    start "" "%~dp0backend\.venv\Scripts\pythonw.exe" "%~dp0anon_launcher.py"
    exit /b 0
)

if exist "%~dp0backend\.venv\Scripts\python.exe" (
    start "" "%~dp0backend\.venv\Scripts\python.exe" "%~dp0anon_launcher.py"
    exit /b 0
)

where pyw >nul 2>nul
if %errorlevel%==0 (
    start "" pyw -3 "%~dp0anon_launcher.py"
    exit /b 0
)

where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%~dp0anon_launcher.py"
    exit /b 0
)

where py >nul 2>nul
if %errorlevel%==0 (
    start "" py -3 "%~dp0anon_launcher.py"
    exit /b 0
)

where python >nul 2>nul
if %errorlevel%==0 (
    start "" python "%~dp0anon_launcher.py"
    exit /b 0
)

echo Python nao foi encontrado. Instale o Python 3.11+ ou execute primeiro o instalador local do ANON.
pause
