# PowerShell script to restart the chatbot server on Windows Server
# This script kills all processes using port 8001 and starts a fresh server

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Chatbot Server Restart Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Find all processes using port 8001
Write-Host "Step 1: Finding processes using port 8001..." -ForegroundColor Yellow
$connections = Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue

if ($connections) {
    Write-Host "Found $($connections.Count) process(es) using port 8001" -ForegroundColor Yellow
    foreach ($conn in $connections) {
        $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "  - PID: $($proc.Id), Name: $($proc.ProcessName), Path: $($proc.Path)" -ForegroundColor Gray
        }
    }
    Write-Host ""
    
    # Step 2: Kill all processes
    Write-Host "Step 2: Stopping all processes on port 8001..." -ForegroundColor Yellow
    foreach ($conn in $connections) {
        try {
            $proc = Get-Process -Id $conn.OwningProcess -ErrorAction Stop
            Write-Host "  Killing PID $($proc.Id)..." -ForegroundColor Gray
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction Stop
            Write-Host "    Stopped" -ForegroundColor Green
        } catch {
            Write-Host "    Error: $_" -ForegroundColor Red
        }
    }
    Write-Host ""
    
    # Wait for processes to fully stop
    Write-Host "Waiting 3 seconds for processes to fully stop..." -ForegroundColor Yellow
    Start-Sleep -Seconds 3
} else {
    Write-Host "No processes found using port 8001" -ForegroundColor Green
    Write-Host ""
}

# Step 3: Verify port is free
Write-Host "Step 3: Verifying port 8001 is free..." -ForegroundColor Yellow
$remaining = Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue
if ($remaining) {
    Write-Host "  Warning: Port 8001 is still in use!" -ForegroundColor Red
    Write-Host "  Remaining processes:" -ForegroundColor Red
    foreach ($conn in $remaining) {
        $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "    - PID: $($proc.Id), Name: $($proc.ProcessName)" -ForegroundColor Red
        }
    }
    Write-Host ""
    Write-Host "You may need to manually kill these processes or restart the server." -ForegroundColor Yellow
    exit 1
} else {
    Write-Host "  Port 8001 is free" -ForegroundColor Green
    Write-Host ""
}

# Step 4: Start the server
Write-Host "Step 4: Starting chatbot server..." -ForegroundColor Yellow
$serverPath = "E:\Chatbot_refine\bank_chatbot"
$runScript = "run.py"

if (Test-Path "$serverPath\$runScript") {
    Write-Host "  Server path: $serverPath" -ForegroundColor Gray
    Write-Host "  Script: $runScript" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Starting server in background..." -ForegroundColor Yellow
    Write-Host "  (Server will run in a new window)" -ForegroundColor Gray
    Write-Host ""
    
    # Change to server directory and start
    Push-Location $serverPath
    Start-Process python -ArgumentList $runScript -WindowStyle Normal
    Pop-Location
    
    Write-Host "  Server start command executed" -ForegroundColor Green
    Write-Host ""
    Write-Host "Please check the server window to confirm it started successfully." -ForegroundColor Cyan
    Write-Host "The server should be available at: http://localhost:8001" -ForegroundColor Cyan
} else {
    Write-Host "  Error: Server script not found at $serverPath\$runScript" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Restart complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
