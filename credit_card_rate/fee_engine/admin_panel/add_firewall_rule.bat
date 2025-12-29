@echo off
REM Batch file to add Windows Firewall rule for Admin Panel (Port 8009)
REM This file must be run as Administrator

echo Adding Windows Firewall rule for Fee Engine Admin Panel (Port 8009)...
echo.

netsh advfirewall firewall add rule name="Fee Engine Admin Panel (Port 8009)" dir=in action=allow protocol=TCP localport=8009

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] Firewall rule added successfully!
    echo.
    echo The admin panel is now accessible from remote computers on port 8009.
    echo.
    echo To verify the rule was added, run:
    echo   netsh advfirewall firewall show rule name="Fee Engine Admin Panel (Port 8009)"
    echo.
) else (
    echo.
    echo [ERROR] Failed to add firewall rule.
    echo.
    echo Make sure you are running this batch file as Administrator!
    echo Right-click the file and select "Run as administrator"
    echo.
)

pause

