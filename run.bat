@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run these commands once in this folder:
    echo   python -m venv .venv
    echo   .venv\Scripts\python -m pip install -r requirements.txt
    pause
    exit /b 2
)
".venv\Scripts\python.exe" -m compiler_studio
if errorlevel 1 pause
