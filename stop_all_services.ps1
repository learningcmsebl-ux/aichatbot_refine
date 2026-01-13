# PowerShell script to stop Backend, Frontend, and Dashboard services
# For Windows Server

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "EBL Chatbot - Stop All Services" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$backendPort = 8001
$frontendPort = 3000
$dashboardPort = 3001

# Function to stop processes on a port
function Stop-PortProcesses {
    param([int]$Port, [string]$ServiceName)
    
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    
    if ($connections) {
        Write-Host "Stopping $ServiceName (Port $Port)..." -ForegroundColor Yellow
        foreach ($conn in $connections) {
            try {
                $proc = Get-Process -Id $conn.OwningProcess -ErrorAction Stop
                Write-Host "  Killing PID $($proc.Id) - $($proc.ProcessName)..." -ForegroundColor Gray
                Stop-Process -Id $conn.OwningProcess -Force -ErrorAction Stop
                Write-Host "    Stopped" -ForegroundColor Green
            } catch {
                Write-Host "    Error: $_" -ForegroundColor Red
            }
        }
    } else {
        Write-Host "$ServiceName (Port $Port): No processes found" -ForegroundColor Gray
    }
}

# Stop Backend
Stop-PortProcesses -Port $backendPort -ServiceName "Backend API"
Start-Sleep -Seconds 1

# Stop Frontend
Stop-PortProcesses -Port $frontendPort -ServiceName "Frontend"
Start-Sleep -Seconds 1

# Stop Dashboard
Stop-PortProcesses -Port $dashboardPort -ServiceName "Dashboard"
Start-Sleep -Seconds 1

Write-Host ""
Write-Host "Verifying ports are free..." -ForegroundColor Yellow

$allStopped = $true
if (Get-NetTCPConnection -LocalPort $backendPort -State Listen -ErrorAction SilentlyContinue) {
    Write-Host "  Warning: Port $backendPort is still in use" -ForegroundColor Red
    $allStopped = $false
} else {
    Write-Host "  Port $backendPort is free" -ForegroundColor Green
}

if (Get-NetTCPConnection -LocalPort $frontendPort -State Listen -ErrorAction SilentlyContinue) {
    Write-Host "  Warning: Port $frontendPort is still in use" -ForegroundColor Red
    $allStopped = $false
} else {
    Write-Host "  Port $frontendPort is free" -ForegroundColor Green
}

if (Get-NetTCPConnection -LocalPort $dashboardPort -State Listen -ErrorAction SilentlyContinue) {
    Write-Host "  Warning: Port $dashboardPort is still in use" -ForegroundColor Red
    $allStopped = $false
} else {
    Write-Host "  Port $dashboardPort is free" -ForegroundColor Green
}

Write-Host ""
if ($allStopped) {
    Write-Host "All services stopped successfully!" -ForegroundColor Green
} else {
    Write-Host "Some services may still be running. Check manually if needed." -ForegroundColor Yellow
}
Write-Host ""




