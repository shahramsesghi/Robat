@echo off
REM Double-click launcher. Runs the PowerShell launcher from this folder.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0START_ANALYZER.ps1"
echo.
pause
