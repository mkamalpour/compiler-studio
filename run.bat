@echo off
setlocal
cd /d "%~dp0"
python -c "import compiler_studio" >nul 2>nul
if errorlevel 1 (
 echo Activate your existing Python or Conda environment with the project dependencies. See README.md.
 exit /b 1
)
if "%~1"=="--check" (
 python -c "import compiler_studio; print('Existing environment is ready.')"
 exit /b %errorlevel%
)
python -m compiler_studio
