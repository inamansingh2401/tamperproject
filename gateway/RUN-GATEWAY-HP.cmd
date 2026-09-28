@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run SETUP-HP.cmd first.
  pause
  exit /b 1
)
echo Keep this window open. Local health: http://127.0.0.1:8765/status
".venv\Scripts\python.exe" gateway.py
echo Gateway stopped. Check the message above.
pause
