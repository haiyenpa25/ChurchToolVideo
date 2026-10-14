@echo off
chcp 65001 > nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run_local.py %*
    goto finished
)
py -3.12 --version >nul 2>&1
if not errorlevel 1 (
    py -3.12 run_local.py %*
    goto finished
)
py -3.11 --version >nul 2>&1
if not errorlevel 1 (
    py -3.11 run_local.py %*
    goto finished
)
python run_local.py %*
:finished
set CHURCH_EXIT_CODE=%errorlevel%
if not "%CHURCH_EXIT_CODE%"=="0" pause
exit /b %CHURCH_EXIT_CODE%
