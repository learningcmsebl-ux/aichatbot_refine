# Register or remove the daily EBL Home forms sync scheduled task.
#
# Usage:
#   .\schedule_forms_sync.ps1                 # create/update daily task (2:00 AM)
#   .\schedule_forms_sync.ps1 -Time "03:30"   # custom local time
#   .\schedule_forms_sync.ps1 -Remove         # remove scheduled task
#   .\schedule_forms_sync.ps1 -RunNow          # run sync immediately

param(
    [string]$Time = "02:00",
    [switch]$Remove,
    [switch]$RunNow
)

$TaskName = "EBL Chatbot Forms Sync"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$wrapperScript = Join-Path $scriptDir "run_forms_sync_scheduled.ps1"

if (-not (Test-Path $wrapperScript)) {
    Write-Host "ERROR: Missing wrapper script: $wrapperScript" -ForegroundColor Red
    exit 1
}

if ($Remove) {
    schtasks /Delete /TN $TaskName /F 2>$null
    Write-Host "Removed scheduled task: $TaskName" -ForegroundColor Green
    exit 0
}

if ($RunNow) {
    Write-Host "Running forms sync now..." -ForegroundColor Cyan
    & powershell -NoProfile -ExecutionPolicy Bypass -File $wrapperScript
    exit $LASTEXITCODE
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "ERROR: python not found in PATH" -ForegroundColor Red
    exit 1
}

$action = "powershell -NoProfile -ExecutionPolicy Bypass -File `"$wrapperScript`""
$createArgs = @(
    "/Create",
    "/TN", $TaskName,
    "/TR", $action,
    "/SC", "DAILY",
    "/ST", $Time,
    "/RL", "HIGHEST",
    "/F"
)

Write-Host "Creating scheduled task: $TaskName" -ForegroundColor Cyan
Write-Host "  Schedule : Daily at $Time (local time)" -ForegroundColor White
Write-Host "  Script   : $wrapperScript" -ForegroundColor White

schtasks @createArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to create scheduled task. Run PowerShell as Administrator." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Scheduled task created successfully." -ForegroundColor Green
Write-Host "Commands:" -ForegroundColor Cyan
Write-Host "  Run now     : .\schedule_forms_sync.ps1 -RunNow" -ForegroundColor White
Write-Host "  View status : Get-Content .\logs\forms_sync_status.json" -ForegroundColor White
Write-Host "  View task   : schtasks /Query /TN `"$TaskName`" /V /FO LIST" -ForegroundColor White
Write-Host "  Remove task : .\schedule_forms_sync.ps1 -Remove" -ForegroundColor White
