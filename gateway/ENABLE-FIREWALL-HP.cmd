@echo off
netsh advfirewall firewall show rule name="SafeTrack HP Gateway 8765" >nul 2>&1
if not errorlevel 1 (
  echo Firewall rule already exists.
  pause
  exit /b 0
)
netsh advfirewall firewall add rule name="SafeTrack HP Gateway 8765" dir=in action=allow protocol=TCP localport=8765 profile=private
if errorlevel 1 (
  echo Run this file as Administrator. Check that the hotspot network is Private.
  pause
  exit /b 1
)
echo Firewall rule added for TCP port 8765 on Private networks.
pause
