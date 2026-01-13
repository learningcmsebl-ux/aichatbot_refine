# PowerShell script to restart Docker backend with updated code
# This rebuilds the Docker image to include code changes

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Restarting Docker Backend with Updates" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
Write-Host "Step 1: Checking Docker..." -ForegroundColor Yellow
try {
    docker ps | Out-Null
    Write-Host "  Docker is running" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Docker Desktop is not running!" -ForegroundColor Red
    Write-Host "  Please start Docker Desktop first, then run this script again." -ForegroundColor Yellow
    exit 1
}

# Change to bank_chatbot directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$chatbotDir = Join-Path $scriptPath "bank_chatbot"

if (-not (Test-Path $chatbotDir)) {
    Write-Host "  ERROR: bank_chatbot directory not found!" -ForegroundColor Red
    exit 1
}

Push-Location $chatbotDir

try {
    Write-Host ""
    Write-Host "Step 2: Stopping existing containers..." -ForegroundColor Yellow
    docker-compose stop chatbot 2>&1 | Out-Null
    Write-Host "  Containers stopped" -ForegroundColor Green

    Write-Host ""
    Write-Host "Step 3: Rebuilding chatbot container with updated code..." -ForegroundColor Yellow
    Write-Host "  This will rebuild the Docker image with your latest code changes" -ForegroundColor Gray
    docker-compose build --no-cache chatbot
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: Failed to build container!" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "  Build completed successfully!" -ForegroundColor Green

    Write-Host ""
    Write-Host "Step 4: Starting chatbot container..." -ForegroundColor Yellow
    docker-compose up -d chatbot
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: Failed to start container!" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "  Container started!" -ForegroundColor Green

    Write-Host ""
    Write-Host "Step 5: Waiting for service to be ready..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5

    # Check health
    $maxRetries = 10
    $retryCount = 0
    $healthCheckPassed = $false

    while ($retryCount -lt $maxRetries -and -not $healthCheckPassed) {
        Start-Sleep -Seconds 2
        $retryCount++
        
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8001/api/health" -Method Get -TimeoutSec 5 -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                $healthCheckPassed = $true
                Write-Host "  Health check passed! Service is running." -ForegroundColor Green
            }
        } catch {
            Write-Host "    Attempt $retryCount/$maxRetries: Waiting..." -ForegroundColor Gray
        }
    }

    if (-not $healthCheckPassed) {
        Write-Host "  WARNING: Health check failed after $maxRetries attempts" -ForegroundColor Yellow
        Write-Host "  Check logs with: docker-compose logs chatbot" -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Docker Backend Restarted!" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Container Status:" -ForegroundColor White
    docker-compose ps chatbot
    Write-Host ""
    Write-Host "View logs: docker-compose logs -f chatbot" -ForegroundColor Gray
    Write-Host ""

} finally {
    Pop-Location
}

