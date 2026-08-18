@echo off
setlocal
REM ==========================================
REM  CareerPilot - Python diagnostic tool
REM  Shows which Python is available and
REM  repairs pip if it is broken.
REM ==========================================
echo ==========================================
echo  Python diagnostic
echo ==========================================
echo.

set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>&1 && set "PY=python"
if not defined PY python3 -c "import sys" >nul 2>&1 && set "PY=python3"

if not defined PY (
    echo  No Python 3 was found at all.
    echo.
    echo  Install it from https://www.python.org/downloads/
    echo  IMPORTANT: tick "Add python.exe to PATH" during install.
    echo  Then close this window, open a NEW one, and run:
    echo      py -3 --version
    pause
    exit /b 1
)

echo  Found Python: %PY%
%PY% --version
echo  Python location:
%PY% -c "import sys; print(sys.executable)"
echo.

echo  Checking the venv module (needed to create virtual environments)...
%PY% -c "import venv" >nul 2>&1
if errorlevel 1 (
    echo  [WARNING] The venv module is MISSING - this Python install is incomplete.
    echo  Best fix: run the Python installer again and choose "Repair",
    echo  or install a fresh Python 3.12 from https://www.python.org/downloads/
    echo.
) else (
    echo  venv module: OK
)

echo  Checking pip...
%PY% -m pip --version >nul 2>&1
if errorlevel 1 (
    echo  pip is broken or missing. Trying to repair it...
    %PY% -m ensurepip --upgrade
    %PY% -m pip install --upgrade pip
    echo.
    echo  Re-checking pip...
    %PY% -m pip --version
) else (
    %PY% -m pip --version
)

echo.
echo  If the last line shows a pip version, Python is ready.
echo  Now open a NEW terminal and run:  scripts\test_all.bat
echo.
echo  If you still see "Python was not found", install Python from
echo  python.org and disable the Store aliases:
echo  Settings ^> Apps ^> Advanced app settings ^> App execution aliases
echo  ^> turn off "python.exe" and "python3.exe".
echo.
pause
endlocal
