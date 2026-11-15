@echo off
rem Yuzu Sprite Tool launcher. Creates a local .venv on first run; installs nothing globally.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo First run: creating local virtual environment...
    python -m venv .venv || goto :error
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error
)
start "" ".venv\Scripts\pythonw.exe" main.py %*
goto :eof

:error
echo Setup failed.
pause
