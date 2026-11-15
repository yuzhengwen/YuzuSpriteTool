@echo off
rem ---------------------------------------------------------------------------
rem  Build Yuzu Sprite Tool into a standalone exe:  dist\YuzuSpriteTool.exe
rem
rem    build.bat            test, then build
rem    build.bat run        test, build, then launch the exe
rem    build.bat fast       skip the smoke test
rem    build.bat fast run   skip the test and launch afterwards
rem
rem  Everything installs into the local .venv; nothing is installed globally.
rem ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"
set "SKIPTEST="
set "LAUNCH="
for %%A in (%*) do (
    if /i "%%A"=="fast" set "SKIPTEST=1"
    if /i "%%A"=="run" set "LAUNCH=1"
)

if not exist "%PY%" (
    echo [1/4] Creating local virtual environment...
    python -m venv .venv || goto :fail
) else (
    echo [1/4] Using existing .venv
)

echo [2/4] Installing / updating dependencies in .venv...
"%PY%" -m pip install --disable-pip-version-check -q -r requirements-dev.txt || goto :fail
if not exist "assets\icon.ico" "%PY%" tools\make_icon.py || goto :fail

if defined SKIPTEST (
    echo [3/4] Smoke test skipped
) else (
    echo [3/4] Running smoke test...
    set "QT_QPA_PLATFORM=offscreen"
    "%PY%" tests\smoke_test.py || goto :testfail
    set "QT_QPA_PLATFORM="
)

echo [4/4] Building exe with PyInstaller...
taskkill /im YuzuSpriteTool.exe /f >nul 2>&1
"%PY%" -m PyInstaller --noconfirm --clean --log-level WARN YuzuSpriteTool.spec || goto :fail

echo.
echo Build complete: %CD%\dist\YuzuSpriteTool.exe
if defined LAUNCH start "" "dist\YuzuSpriteTool.exe"
endlocal
exit /b 0

:testfail
echo.
echo Smoke test FAILED - exe not built. Run this to see the error:
echo     set QT_QPA_PLATFORM=offscreen ^&^& %PY% tests\smoke_test.py
endlocal
exit /b 1

:fail
echo.
echo Build FAILED.
endlocal
exit /b 1
