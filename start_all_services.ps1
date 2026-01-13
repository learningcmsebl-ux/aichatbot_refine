# PowerShell script to start Backend, Frontend, and Dashboard
# For Windows Server

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "EBL Chatbot - Start All Services" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$basePath = "E:\Chatbot_refine"
$backendPath = "$basePath\bank_chatbot"
$frontendPath = "$basePath\bank_chatbot_frontend\vite-project"
$dashboardPath = "$basePath\chatbot_dashboard"

$backendPort = 8001
$frontendPort = 3000
$dashboardPort = 3001

# Function to check if port is in use
function Test-Port {
    param([int]$Port)
    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $connection
}

# Function to wait for service to be ready
function Wait-ForService {
    param(
        [string]$Url,
        [int]$MaxWaitSeconds = 30,
        [string]$ServiceName
    )
    $waited = 0
    Write-Host "  Waiting for $ServiceName to be ready..." -ForegroundColor Yellow
    while ($waited -lt $MaxWaitSeconds) {
        try {
            $response = Invoke-WebRequest -Uri $Url -Method Get -TimeoutSec 2 -ErrorAction Stop
            Write-Host "  $ServiceName is ready!" -ForegroundColor Green
            return $true
        } catch {
            Start-Sleep -Seconds 2
            $waited += 2
            Write-Host "    ... ($waited/$MaxWaitSeconds seconds)" -ForegroundColor Gray
        }
    }
    Write-Host "  Warning: $ServiceName may not be ready yet" -ForegroundColor Yellow
    return $false
}

# Step 1: Check if ports are available
Write-Host "Step 1: Checking port availability..." -ForegroundColor Yellow

$portsInUse = @()
if (Test-Port -Port $backendPort) {
    Write-Host "  Port $backendPort (Backend) is already in use" -ForegroundColor Red
    $portsInUse += $backendPort
} else {
    Write-Host "  Port $backendPort (Backend) is available" -ForegroundColor Green
}

if (Test-Port -Port $frontendPort) {
    Write-Host "  Port $frontendPort (Frontend) is already in use" -ForegroundColor Red
    $portsInUse += $frontendPort
} else {
    Write-Host "  Port $frontendPort (Frontend) is available" -ForegroundColor Green
}

if (Test-Port -Port $dashboardPort) {
    Write-Host "  Port $dashboardPort (Dashboard) is already in use" -ForegroundColor Red
    $portsInUse += $dashboardPort
} else {
    Write-Host "  Port $dashboardPort (Dashboard) is available" -ForegroundColor Green
}

if ($portsInUse.Count -gt 0) {
    Write-Host ""
    Write-Host "Warning: Some ports are already in use!" -ForegroundColor Red
    Write-Host "You may need to stop existing services first." -ForegroundColor Yellow
    Write-Host ""
    $continue = Read-Host "Continue anyway? (y/n)"
    if ($continue -ne "y" -and $continue -ne "Y") {
        Write-Host "Aborted." -ForegroundColor Yellow
        exit 1
    }
}
Write-Host ""

# Step 2: Start Backend
Write-Host "Step 2: Starting Backend API (Port $backendPort)..." -ForegroundColor Yellow
if (Test-Path "$backendPath\run.py") {
    Write-Host "  Starting backend in new window..." -ForegroundColor Gray
    $backendWindow = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$backendPath'; Write-Host 'Starting Backend API...' -ForegroundColor Cyan; python run.py" -PassThru
    Write-Host "  Backend window started (PID: $($backendWindow.Id))" -ForegroundColor Green
    Start-Sleep -Seconds 3
} else {
    Write-Host "  Error: Backend script not found at $backendPath\run.py" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Step 3: Start Frontend
Write-Host "Step 3: Starting Frontend (Port $frontendPort)..." -ForegroundColor Yellow
if (Test-Path "$frontendPath\package.json") {
    Write-Host "  Starting frontend in new window..." -ForegroundColor Gray
    $frontendWindow = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$frontendPath'; Write-Host 'Starting Frontend...' -ForegroundColor Cyan; npm run dev" -PassThru
    Write-Host "  Frontend window started (PID: $($frontendWindow.Id))" -ForegroundColor Green
    Start-Sleep -Seconds 2
} else {
    Write-Host "  Error: Frontend package.json not found at $frontendPath\package.json" -ForegroundColor Red
    Write-Host "  Skipping frontend..." -ForegroundColor Yellow
}
Write-Host ""

# Step 4: Start Dashboard
Write-Host "Step 4: Starting Dashboard (Port $dashboardPort)..." -ForegroundColor Yellow
if (Test-Path "$dashboardPath\package.json") {
    Write-Host "  Starting dashboard in new window..." -ForegroundColor Gray
    $dashboardWindow = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$dashboardPath'; Write-Host 'Starting Dashboard...' -ForegroundColor Cyan; npm run dev" -PassThru
    Write-Host "  Dashboard window started (PID: $($dashboardWindow.Id))" -ForegroundColor Green
    Start-Sleep -Seconds 2
} else {
    Write-Host "  Error: Dashboard package.json not found at $dashboardPath\package.json" -ForegroundColor Red
    Write-Host "  Skipping dashboard..." -ForegroundColor Yellow
}
Write-Host ""

# Step 5: Wait for services and verify
Write-Host "Step 5: Verifying services..." -ForegroundColor Yellow
Write-Host ""

# Wait a bit for services to start
Start-Sleep -Seconds 5

# Check backend
if (Test-Port -Port $backendPort) {
    Write-Host "  Backend API: Running on port $backendPort" -ForegroundColor Green
    Wait-ForService -Url "http://localhost:$backendPort/api/health" -ServiceName "Backend API" | Out-Null
} else {
    Write-Host "  Backend API: Not detected on port $backendPort" -ForegroundColor Yellow
}

# Check frontend
if (Test-Port -Port $frontendPort) {
    Write-Host "  Frontend: Running on port $frontendPort" -ForegroundColor Green
} else {
    Write-Host "  Frontend: Not detected on port $frontendPort (may still be starting)" -ForegroundColor Yellow
}

# Check dashboard
if (Test-Port -Port $dashboardPort) {
    Write-Host "  Dashboard: Running on port $dashboardPort" -ForegroundColor Green
} else {
    Write-Host "  Dashboard: Not detected on port $dashboardPort (may still be starting)" -ForegroundColor Yellow
}

Write-Host ""

# Step 6: Summary
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Services Started!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Backend API:" -ForegroundColor White
Write-Host "  URL: http://localhost:$backendPort" -ForegroundColor Gray
Write-Host "  Health: http://localhost:$backendPort/api/health" -ForegroundColor Gray
Write-Host ""
Write-Host "Frontend (Chat Interface):" -ForegroundColor White
Write-Host "  URL: http://localhost:$frontendPort" -ForegroundColor Gray
Write-Host ""
Write-Host "Dashboard (Analytics):" -ForegroundColor White
Write-Host "  URL: http://localhost:$dashboardPort" -ForegroundColor Gray
Write-Host ""
Write-Host "Note: Each service is running in a separate PowerShell window." -ForegroundColor Yellow
Write-Host "You can close this window, but keep the service windows open." -ForegroundColor Yellow
Write-Host ""

# Optional: Open browsers
$openBrowsers = Read-Host "Open services in browser? (y/n)"
if ($openBrowsers -eq "y" -or $openBrowsers -eq "Y") {
    Start-Sleep -Seconds 3
    Write-Host "Opening browsers..." -ForegroundColor Yellow
    
    if (Test-Port -Port $frontendPort) {
        Start-Process "http://localhost:$frontendPort"
    }
    
    Start-Sleep -Seconds 1
    
    if (Test-Port -Port $dashboardPort) {
        Start-Process "http://localhost:$dashboardPort"
    }
    
    Write-Host "Browsers opened!" -ForegroundColor Green
}

Write-Host ""
Write-Host "All services are starting. Check the individual windows for startup logs." -ForegroundColor Cyan
Write-Host ""




