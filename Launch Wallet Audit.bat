@echo off
cd /d "%~dp0"
py -3 wallet_audit.py 2> launch-error.txt
if errorlevel 1 python wallet_audit.py 2> launch-error.txt
if errorlevel 1 (
  echo.
  echo The app could not start. Check launch-error.txt in this folder.
  pause
)
