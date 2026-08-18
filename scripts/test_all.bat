@echo off
setlocal
REM ==========================================
REM  CareerPilot AI - Test Suite (Windows)
REM  Robust version: finds a working Python 3,
REM  repairs pip if needed, runs tests + smoke.
REM ==========================================

REM --- find a working Python 3 interpreter ---
set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>&1 && set "PY=python"
if not defined PY python3 -c "import sys" >nul 2>&1 && set "PY=python3"
if not defined PY goto :no_python

echo [0/5] Using Python: %PY%
%PY% --version

cd /d "%~dp0..\backend" || goto :bad_dir

if not exist .venv (
    echo [1/5] Creating virtual environment...
    %PY% -m venv .venv 2>nul
    if not exist ".venv\Scripts\python.exe" (
        echo       venv module missing - trying the virtualenv package instead...
        %PY% -m pip install --upgrade pip virtualenv >nul 2>&1
        %PY% -m virtualenv .venv || goto :fail
    )
    if not exist ".venv\Scripts\python.exe" goto :fail
    echo       Checking pip...
    .venv\Scripts\python.exe -m pip --version >nul 2>&1 || (
        echo       Repairing pip...
        .venv\Scripts\python.exe -m ensurepip --upgrade || goto :fail
    )
    .venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>&1
    echo       Installing dependencies...
    .venv\Scripts\python.exe -m pip install -r requirements.txt || goto :fail
) else (
    echo [1/5] Virtual environment already present.
)

echo.
echo [2/5] Running unit tests (pytest)...
.venv\Scripts\python.exe -m pytest -q
if errorlevel 1 goto :fail

echo.
echo [3/5] Starting API server for the smoke test...
set "SERVER_PID="
for /f %%i in ('powershell -NoProfile -Command "$p = Start-Process -FilePath '.venv\Scripts\python.exe' -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory '%CD%' -RedirectStandardOutput 'server_smoke.log' -RedirectStandardError 'server_smoke_err.log' -PassThru; $p.Id"') do set SERVER_PID=%%i
if not defined SERVER_PID (
    echo       Could not start the server. Check server_smoke_err.log
    goto :fail
)
echo       Server started (PID %SERVER_PID%). Waiting for it to become healthy...
for /l %%i in (1,1,20) do (
    curl -s -o nul http://127.0.0.1:8000/health && goto :server_up
    timeout /t 1 /nobreak >nul
)
echo       Server did not become healthy - check server_smoke_err.log
goto :stop_server
:server_up

echo.
echo [4/5] Running end-to-end smoke test...
.venv\Scripts\python.exe ..\scripts\smoke_test.py
set SMOKE_EXIT=%errorlevel%

:stop_server
echo.
echo [5/5] Stopping server...
if defined SERVER_PID taskkill /f /pid %SERVER_PID% >nul 2>&1
timeout /t 2 /nobreak >nul

if defined SMOKE_EXIT (
    if %SMOKE_EXIT%==0 (
        echo.
        echo  All tests passed! CareerPilot is ready.
        pause
        exit /b 0
    )
)
echo.
echo  Some tests FAILED - see the output above.
pause
exit /b 1

:no_python
echo.
echo  Python 3 was NOT found on this PC.
echo.
echo  Install it from https://www.python.org/downloads/
echo  IMPORTANT: tick "Add python.exe to PATH" during installation.
echo  After installing: close this window, open a NEW one, and run test_all.bat again.
echo.
pause
exit /b 1

:bad_dir
echo.
echo  Could not find the "backend" folder next to this script.
echo  Make sure test_all.bat is inside the "scripts" folder of the careerpilot folder.
echo.
pause
exit /b 1

:fail
echo.
echo  A step FAILED. See the messages above.
echo  Tip: if it was about pip, run this once, then re-run this script:
echo      .venv\Scripts\python.exe -m ensurepip --upgrade
echo.
pause
exit /b 1
