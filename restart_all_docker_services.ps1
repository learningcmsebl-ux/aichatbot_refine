# PowerShell script to restart ALL Docker services (Backend, Frontend, Dashboard)
# Run this script to rebuild and restart all services

Write-Host "="*70 -ForegroundColor Cyan
Write-Host "Restarting ALL Docker Services" -ForegroundColor Cyan
Write-Host "="*70 -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
$dockerRunning = docker ps 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Step 1: Stop all services
Write-Host "Step 1: Stopping all services..." -ForegroundColor Yellow
Set-Location "E:\Chatbot_refine\bank_chatbot"
docker-compose down
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] All services stopped" -ForegroundColor Green
} else {
    Write-Host "[WARNING] Some services may not have been running" -ForegroundColor Yellow
}

Write-Host ""

# Step 2: Rebuild all services
Write-Host "Step 2: Rebuilding all services..." -ForegroundColor Yellow
Write-Host "  This may take several minutes..." -ForegroundColor Gray
docker-compose build --no-cache
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] All services rebuilt" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Failed to rebuild services" -ForegroundColor Red
    Write-Host "  Check logs above for errors" -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# Step 3: Start all services
Write-Host "Step 3: Starting all services..." -ForegroundColor Yellow
docker-compose up -d
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] All services started" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Failed to start services" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Step 4: Wait for services to be ready
Write-Host "Step 4: Waiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

# Step 5: Check service status
Write-Host ""
Write-Host "Step 5: Checking service status..." -ForegroundColor Yellow
docker-compose ps

Write-Host ""

# Step 6: Test endpoints
Write-Host "Step 6: Testing service endpoints..." -ForegroundColor Yellow

# Test Backend
$maxRetries = 10
$retryCount = 0
$backendReady = $false
while ($retryCount -lt $maxRetries -and -not $backendReady) {
    Start-Sleep -Seconds 3
    $retryCount++
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8001/api/health" -Method Get -TimeoutSec 5 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            $backendReady = $true
            Write-Host "  [OK] Backend (port 8001) is ready" -ForegroundColor Green
        }
    } catch {
        Write-Host "    Backend attempt $($retryCount) of $($maxRetries): Waiting..." -ForegroundColor Gray
    }
}

if (-not $backendReady) {
    Write-Host "  [WARNING] Backend may still be starting" -ForegroundColor Yellow
}

# Test Frontend
$retryCount = 0
$frontendReady = $false
while ($retryCount -lt $maxRetries -and -not $frontendReady) {
    Start-Sleep -Seconds 3
    $retryCount++
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:3000" -Method Get -TimeoutSec 5 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            $frontendReady = $true
            Write-Host "  [OK] Frontend (port 3000) is ready" -ForegroundColor Green
        }
    } catch {
        Write-Host "    Frontend attempt $($retryCount) of $($maxRetries): Waiting..." -ForegroundColor Gray
    }
}

if (-not $frontendReady) {
    Write-Host "  [WARNING] Frontend may still be starting" -ForegroundColor Yellow
}

# Test Dashboard
$retryCount = 0
$dashboardReady = $false
while ($retryCount -lt $maxRetries -and -not $dashboardReady) {
    Start-Sleep -Seconds 3
    $retryCount++
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:3001" -Method Get -TimeoutSec 5 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            $dashboardReady = $true
            Write-Host "  [OK] Dashboard (port 3001) is ready" -ForegroundColor Green
        }
    } catch {
        Write-Host "    Dashboard attempt $($retryCount) of $($maxRetries): Waiting..." -ForegroundColor Gray
    }
}

if (-not $dashboardReady) {
    Write-Host "  [WARNING] Dashboard may still be starting" -ForegroundColor Yellow
}

# Summary
Write-Host ""
Write-Host "="*70 -ForegroundColor Cyan
Write-Host "Restart Complete!" -ForegroundColor Cyan
Write-Host "="*70 -ForegroundColor Cyan
Write-Host ""
Write-Host "Service URLs:" -ForegroundColor Cyan
Write-Host "  Backend:  http://localhost:8001" -ForegroundColor White
Write-Host "  Frontend: http://localhost:3000" -ForegroundColor White
Write-Host "  Dashboard: http://localhost:3001" -ForegroundColor White
Write-Host ""
Write-Host "To view logs:" -ForegroundColor Cyan
Write-Host "  All services: docker-compose logs -f" -ForegroundColor White
Write-Host "  Backend:     docker-compose logs -f chatbot" -ForegroundColor White
Write-Host "  Frontend:    docker-compose logs -f frontend" -ForegroundColor White
Write-Host "  Dashboard:   docker-compose logs -f dashboard" -ForegroundColor White
Write-Host ""

