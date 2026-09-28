@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
  echo Python 3 is required. Install it, then run this file again.
  pause
  exit /b 1
)
py -3 -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo.
echo Gateway dependencies are ready.
echo Run ENABLE-FIREWALL-HP.cmd as Administrator once, then RUN-GATEWAY-HP.cmd.
pause
exit /b 0
:failed
echo Setup failed. Check the message above.
pause
exit /b 1
