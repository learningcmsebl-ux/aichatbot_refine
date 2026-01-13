# PowerShell script to restart Docker services for Women Platinum fix
# Run this script to apply all code changes

Write-Host "="*70 -ForegroundColor Cyan
Write-Host "Restarting Docker Services for Women Platinum Fix" -ForegroundColor Cyan
Write-Host "="*70 -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
$dockerRunning = docker ps 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Restart Fee Engine Service
Write-Host "Step 1: Restarting Fee Engine Service..." -ForegroundColor Yellow
Set-Location "E:\Chatbot_refine\credit_card_rate"
docker-compose up -d --build fee-engine
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Fee Engine service restarted" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Failed to restart Fee Engine service" -ForegroundColor Red
}

Write-Host ""

# Restart Chatbot Service
Write-Host "Step 2: Restarting Chatbot Service..." -ForegroundColor Yellow
Set-Location "E:\Chatbot_refine\bank_chatbot"
docker-compose up -d --build chatbot
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Chatbot service restarted" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Failed to restart Chatbot service" -ForegroundColor Red
}

Write-Host ""
Write-Host "="*70 -ForegroundColor Cyan
Write-Host "Restart Complete!" -ForegroundColor Cyan
Write-Host "="*70 -ForegroundColor Cyan
Write-Host ""
Write-Host "Checking container status..." -ForegroundColor Yellow
docker ps --filter "name=fee-engine" --filter "name=bank-chatbot" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
Write-Host ""
Write-Host "To view logs:" -ForegroundColor Cyan
Write-Host "  Fee Engine: docker logs -f fee-engine-service" -ForegroundColor White
Write-Host "  Chatbot:    docker logs -f bank-chatbot-api" -ForegroundColor White










