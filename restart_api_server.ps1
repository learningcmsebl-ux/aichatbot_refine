# PowerShell script to restart the API server reliably
# Handles multiple processes, port cleanup, and proper startup

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Restart API Server" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$backendPort = 8001
$backendPath = "E:\Chatbot_refine\bank_chatbot"

# Step 1: Find and kill ALL Python processes related to the chatbot
Write-Host "Step 1: Stopping existing API server processes..." -ForegroundColor Yellow

# Method 1: Kill processes listening on port 8001
$listeningProcs = Get-NetTCPConnection -LocalPort $backendPort -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique

foreach ($processId in $listeningProcs) {
    try {
        $proc = Get-Process -Id $processId -ErrorAction Stop
        Write-Host "  Stopping process $processId ($($proc.ProcessName))..." -ForegroundColor Gray
        Stop-Process -Id $processId -Force -ErrorAction Stop
        Write-Host "    Stopped" -ForegroundColor Green
    } catch {
        Write-Host "    Process $processId already terminated" -ForegroundColor Gray
    }
}

# Method 2: Kill Python processes running from the chatbot directory
$pythonProcs = Get-Process python* -ErrorAction SilentlyContinue | Where-Object {
    try {
        $procPath = $_.Path
        $workingDir = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
        if ($workingDir -and $workingDir.Contains($backendPath)) {
            return $true
        }
    } catch {
        return $false
    }
    return $false
}

foreach ($proc in $pythonProcs) {
    try {
        Write-Host "  Stopping Python process $($proc.Id)..." -ForegroundColor Gray
        Stop-Process -Id $proc.Id -Force -ErrorAction Stop
        Write-Host "    Stopped" -ForegroundColor Green
    } catch {
        Write-Host "    Process $($proc.Id) already terminated" -ForegroundColor Gray
    }
}

# Wait for processes to fully terminate
Start-Sleep -Seconds 2

# Step 2: Verify port is free (ignore TIME_WAIT states - they're harmless)
Write-Host ""
Write-Host "Step 2: Verifying port availability..." -ForegroundColor Yellow

$stillListening = Get-NetTCPConnection -LocalPort $backendPort -State Listen -ErrorAction SilentlyContinue
if ($stillListening) {
    Write-Host "  Warning: Port $backendPort still has LISTENING connections" -ForegroundColor Red
    Write-Host "  Attempting to kill remaining processes..." -ForegroundColor Yellow
    
    $stillListening | ForEach-Object {
        try {
            Stop-Process -Id $_.OwningProcess -Force -ErrorAction Stop
        } catch {
            # Ignore errors
        }
    }
    Start-Sleep -Seconds 2
} else {
    Write-Host "  Port $backendPort is available (TIME_WAIT states are normal and harmless)" -ForegroundColor Green
}

# Step 3: Test if port can be bound (actual availability test)
Write-Host ""
Write-Host "Step 3: Testing port binding..." -ForegroundColor Yellow

try {
    $testSocket = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Any, $backendPort)
    $testSocket.Start()
    $testSocket.Stop()
    Write-Host "  Port $backendPort is available for binding" -ForegroundColor Green
} catch {
    Write-Host "  Port $backendPort may still be in use, but will attempt to start anyway" -ForegroundColor Yellow
    Write-Host "    (Note: SO_REUSEADDR will be used, which should work)" -ForegroundColor Gray
}

# Step 4: Start the server
Write-Host ""
Write-Host "Step 4: Starting API server..." -ForegroundColor Yellow

if (-not (Test-Path "$backendPath\run.py")) {
    Write-Host "  Error: run.py not found at $backendPath" -ForegroundColor Red
    exit 1
}

Write-Host "  Starting server in background..." -ForegroundColor Gray

# Start the server in a new PowerShell window so it's visible and manageable
$serverCommand = "cd '$backendPath'; Write-Host '========================================' -ForegroundColor Cyan; Write-Host 'API Server Starting...' -ForegroundColor Cyan; Write-Host '========================================' -ForegroundColor Cyan; Write-Host ''; python run.py"
$serverProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", $serverCommand -PassThru

Write-Host "  Server process started (PID: $($serverProcess.Id))" -ForegroundColor Green
Write-Host "  Server window opened - check it for startup logs" -ForegroundColor Gray

# Step 5: Wait and verify server is running
Write-Host ""
Write-Host "Step 5: Waiting for server to be ready..." -ForegroundColor Yellow

$maxWait = 15
$waited = 0
$serverReady = $false

while ($waited -lt $maxWait -and -not $serverReady) {
    Start-Sleep -Seconds 2
    $waited += 2
    
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$backendPort/api/health" -Method Get -TimeoutSec 2 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            $serverReady = $true
            Write-Host "  Server is ready and responding!" -ForegroundColor Green
            Write-Host "    Health check: $($response.Content)" -ForegroundColor Gray
        }
    } catch {
        Write-Host "    ... waiting ($waited/$maxWait seconds)" -ForegroundColor Gray
    }
}

if (-not $serverReady) {
    Write-Host "  Server may still be starting. Check the server window for details." -ForegroundColor Yellow
}

# Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Restart Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "API Server:" -ForegroundColor White
Write-Host "  URL: http://localhost:$backendPort" -ForegroundColor Gray
Write-Host "  Health: http://localhost:$backendPort/api/health" -ForegroundColor Gray
Write-Host ""
Write-Host "Note: The server is running in a separate PowerShell window." -ForegroundColor Yellow
Write-Host "Keep that window open while the server is running." -ForegroundColor Yellow
Write-Host ""
