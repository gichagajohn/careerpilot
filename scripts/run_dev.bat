@echo off
setlocal
REM ==========================================
REM  CareerPilot AI - start the API server
REM  Robust version: finds a working Python 3,
REM  repairs pip if needed, seeds DB if missing.
REM ==========================================

set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>&1 && set "PY=python"
if not defined PY python3 -c "import sys" >nul 2>&1 && set "PY=python3"
if not defined PY goto :no_python

cd /d "%~dp0..\backend" || goto :bad_dir

if not exist .venv (
    echo Creating virtual environment...
    %PY% -m venv .venv 2>nul
    if not exist ".venv\Scripts\python.exe" (
        echo venv module missing - trying the virtualenv package instead...
        %PY% -m pip install --upgrade pip virtualenv >nul 2>&1
        %PY% -m virtualenv .venv || goto :fail
    )
    if not exist ".venv\Scripts\python.exe" goto :fail
    .venv\Scripts\python.exe -m pip --version >nul 2>&1 || (
        echo Repairing pip...
        .venv\Scripts\python.exe -m ensurepip --upgrade || goto :fail
    )
    .venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>&1
    echo Installing dependencies...
    .venv\Scripts\python.exe -m pip install -r requirements.txt || goto :fail
    echo.
    echo Dependencies installed. Run this file again to start the server.
    pause
    exit /b 0
)

if not exist ..\data\careerpilot.db (
    echo Initializing database and seeding master profile...
    .venv\Scripts\python.exe ..\scripts\init_db.py
    .venv\Scripts\python.exe ..\scripts\seed.py --email johngichaga8@gmail.com --demo
)

echo.
echo Starting CareerPilot API...
echo   API docs:   http://localhost:8000/docs
echo   Login:      johngichaga8@gmail.com / ChangeMe123!
echo   Press Ctrl+C to stop.
echo.
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
exit /b %errorlevel%

:no_python
echo.
echo  Python 3 was NOT found on this PC.
echo  Install it from https://www.python.org/downloads/
echo  IMPORTANT: tick "Add python.exe to PATH" during installation.
echo.
pause
exit /b 1

:bad_dir
echo.
echo  Could not find the "backend" folder next to this script.
echo  Make sure run_dev.bat is inside the "scripts" folder of the careerpilot folder.
echo.
pause
exit /b 1

:fail
echo.
echo  Setup FAILED. See the messages above.
echo  Tip: if it was about pip, run this once, then re-run this script:
echo      .venv\Scripts\python.exe -m ensurepip --upgrade
echo.
pause
exit /b 1
