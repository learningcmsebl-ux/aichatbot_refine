# PowerShell script to deploy Bank Chatbot to Docker
# This script builds and starts the chatbot service on port 8001

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Bank Chatbot Docker Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
Write-Host "Step 1: Checking Docker..." -ForegroundColor Yellow
try {
    $dockerVersion = docker --version
    Write-Host "  Docker is running: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Docker is not running or not installed!" -ForegroundColor Red
    Write-Host "  Please start Docker Desktop and try again." -ForegroundColor Yellow
    exit 1
}

# Check if .env file exists
Write-Host ""
Write-Host "Step 2: Checking environment file..." -ForegroundColor Yellow
if (Test-Path ".env") {
    Write-Host "  .env file found" -ForegroundColor Green
} else {
    Write-Host "  WARNING: .env file not found!" -ForegroundColor Yellow
    Write-Host "  Creating .env from env.example..." -ForegroundColor Yellow
    if (Test-Path "env.example") {
        Copy-Item "env.example" ".env"
        Write-Host "  .env file created. Please edit it with your settings!" -ForegroundColor Yellow
        Write-Host "  IMPORTANT: Set OPENAI_API_KEY in .env file before continuing!" -ForegroundColor Red
        $continue = Read-Host "  Continue anyway? (y/n)"
        if ($continue -ne "y") {
            exit 1
        }
    } else {
        Write-Host "  ERROR: env.example not found!" -ForegroundColor Red
        exit 1
    }
}

# Stop existing containers if running
Write-Host ""
Write-Host "Step 3: Stopping existing containers..." -ForegroundColor Yellow
docker-compose down 2>&1 | Out-Null
Write-Host "  Existing containers stopped" -ForegroundColor Green

# Build and start services
Write-Host ""
Write-Host "Step 4: Building and starting services..." -ForegroundColor Yellow
Write-Host "  This may take a few minutes on first run..." -ForegroundColor Gray

docker-compose up -d --build

if ($LASTEXITCODE -eq 0) {
    Write-Host "  Services started successfully!" -ForegroundColor Green
} else {
    Write-Host "  ERROR: Failed to start services!" -ForegroundColor Red
    Write-Host "  Check logs with: docker-compose logs" -ForegroundColor Yellow
    exit 1
}

# Wait for services to be ready
Write-Host ""
Write-Host "Step 5: Waiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Check service status
Write-Host ""
Write-Host "Step 6: Checking service status..." -ForegroundColor Yellow
docker-compose ps

# Test health endpoint
Write-Host ""
Write-Host "Step 7: Testing chatbot health endpoint..." -ForegroundColor Yellow
$maxRetries = 10
$retryCount = 0
$healthCheckPassed = $false

while ($retryCount -lt $maxRetries -and -not $healthCheckPassed) {
    Start-Sleep -Seconds 3
    $retryCount++
    
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8001/api/health" -Method Get -TimeoutSec 5 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            $healthCheckPassed = $true
            Write-Host "  Health check passed! Service is running." -ForegroundColor Green
            Write-Host "  Response: $($response.Content)" -ForegroundColor Gray
        }
    } catch {
        Write-Host "    Attempt $retryCount/$maxRetries: Waiting for service..." -ForegroundColor Gray
    }
}

if (-not $healthCheckPassed) {
    Write-Host "  WARNING: Health check failed after $maxRetries attempts" -ForegroundColor Yellow
    Write-Host "  Service may still be starting. Check logs with:" -ForegroundColor Yellow
    Write-Host "    docker-compose logs chatbot" -ForegroundColor Gray
}

# Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deployment Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Services:" -ForegroundColor White
Write-Host "  Chatbot API: http://localhost:8001" -ForegroundColor Gray
Write-Host "  Health Check: http://localhost:8001/api/health" -ForegroundColor Gray
Write-Host "  PostgreSQL: localhost:5432" -ForegroundColor Gray
Write-Host "  Redis: localhost:6379" -ForegroundColor Gray
Write-Host ""
Write-Host "Useful Commands:" -ForegroundColor White
Write-Host "  View logs: docker-compose logs -f chatbot" -ForegroundColor Gray
Write-Host "  Stop services: docker-compose down" -ForegroundColor Gray
Write-Host "  Restart chatbot: docker-compose restart chatbot" -ForegroundColor Gray
Write-Host "  View status: docker-compose ps" -ForegroundColor Gray
Write-Host ""

