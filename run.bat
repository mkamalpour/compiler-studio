@echo off
setlocal
cd /d "%~dp0"
python -c "import compiler_studio.gui; from compiler_studio.engine import compile_profile; from compiler_studio.profiles import ricepy_profile; compile_profile(ricepy_profile())" >nul 2>nul
if errorlevel 1 (
 echo Activate your existing Python or Conda environment with the project dependencies. See README.md.
 exit /b 1
)
if "%~1"=="--check" (
 echo Existing environment imports and desktop dependencies are ready.
 exit /b 0
)
python -m compiler_studio
