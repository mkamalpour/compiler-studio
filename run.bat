@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo First-run setup: preparing a local Python environment...
    py -3.11 -c "import sys" >nul 2>&1
    if not errorlevel 1 (
        py -3.11 -m venv .venv
    ) else (
        python -c "import sys; sys.exit(0 if sys.version_info[:2] == (3,11) else 1)" >nul 2>&1
        if errorlevel 1 goto missing_python
        python -m venv .venv
    )
    if not exist ".venv\Scripts\python.exe" goto setup_failed
)
".venv\Scripts\python.exe" -c "import lark; assert lark.__version__ == '1.3.1'" >nul 2>&1
if errorlevel 1 (
    echo Installing the required Python library. Internet access is needed for this first setup.
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto setup_failed
)
if "%~1"=="--check" goto verify_setup
".venv\Scripts\python.exe" -m compiler_studio
if errorlevel 1 goto launch_failed
exit /b 0

:verify_setup
".venv\Scripts\python.exe" -c "import compiler_studio, lark, tkinter; print('Setup is ready. Double-click run.bat to open Compiler Studio.')"
exit /b %errorlevel%

:missing_python
echo Python 3.11 is needed for first-run setup. Install it from python.org, enable PATH, then open run.bat again.
pause
exit /b 2

:setup_failed
echo Setup could not finish. Check your Python installation and internet connection, then try run.bat again.
pause
exit /b 2

:launch_failed
echo Compiler Studio could not open. Review the error above; the README includes manual setup steps.
pause
exit /b 2
