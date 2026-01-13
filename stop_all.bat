@echo off
REM Simple batch file to stop all services
REM Double-click this file to stop everything

powershell.exe -ExecutionPolicy Bypass -File "%~dp0stop_all_services.ps1"
pause




