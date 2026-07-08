# Scheduled wrapper for EBL Home forms metadata sync.
# Invoked by Windows Task Scheduler (see schedule_forms_sync.ps1).

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

$logsDir = Join-Path $scriptDir "logs"
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $logsDir "forms_sync_$timestamp.log"
$statusFile = Join-Path $logsDir "forms_sync_status.json"

function Write-Log {
    param([string]$Message)
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Message"
    Add-Content -Path $logFile -Value $line
    Write-Host $line
}

try {
    $python = (Get-Command python -ErrorAction Stop).Source
    Write-Log "Starting EBL Home forms sync"
    Write-Log "Python: $python"
    Write-Log "Working directory: $scriptDir"

    $prevErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $python sync_forms_from_eblhome.py 2>&1 | ForEach-Object { Write-Log $_.ToString() }
    $formsExit = $LASTEXITCODE
    & $python sync_apps_from_eblhome.py 2>&1 | ForEach-Object { Write-Log $_.ToString() }
    $appsExit = $LASTEXITCODE
    & $python sync_leadership_from_eblhome.py 2>&1 | ForEach-Object { Write-Log $_.ToString() }
    $leadershipExit = $LASTEXITCODE
    & $python sync_soc_from_eblhome.py 2>&1 | ForEach-Object { Write-Log $_.ToString() }
    $socExit = $LASTEXITCODE
    & $python sync_proposals_from_eblhome.py 2>&1 | ForEach-Object { Write-Log $_.ToString() }
    $proposalsExit = $LASTEXITCODE
    & $python sync_circulars_from_eblhome.py 2>&1 | ForEach-Object { Write-Log $_.ToString() }
    $circularsExit = $LASTEXITCODE
    $exitCode = [Math]::Max([Math]::Max([Math]::Max($formsExit, $appsExit), $leadershipExit), [Math]::Max([Math]::Max($socExit, $proposalsExit), $circularsExit))
    $ErrorActionPreference = $prevErrorAction

    $status = @{
        last_run_at = (Get-Date).ToUniversalTime().ToString("o")
        last_run_local = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
        exit_code = $exitCode
        success = ($exitCode -eq 0)
        log_file = $logFile
    }

    if ($exitCode -ne 0) {
        Write-Log "Forms sync failed with exit code $exitCode"
    } else {
        Write-Log "Forms sync completed successfully"
    }

    $status | ConvertTo-Json -Depth 4 | Set-Content -Path $statusFile -Encoding UTF8
    exit $exitCode
} catch {
    Write-Log "Forms sync wrapper error: $_"
    @{
        last_run_at = (Get-Date).ToUniversalTime().ToString("o")
        last_run_local = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
        exit_code = 1
        success = $false
        error = $_.ToString()
        log_file = $logFile
    } | ConvertTo-Json -Depth 4 | Set-Content -Path $statusFile -Encoding UTF8
    exit 1
}
