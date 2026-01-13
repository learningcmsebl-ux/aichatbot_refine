@echo off
REM Simple batch file to start all services
REM Double-click this file to start everything

powershell.exe -ExecutionPolicy Bypass -File "%~dp0start_all_services.ps1"
pause




