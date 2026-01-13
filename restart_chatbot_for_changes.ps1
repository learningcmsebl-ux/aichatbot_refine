# Restart chatbot container to apply code changes
# The code is volume-mounted, so changes are already in the container
# We just need to restart to load the new code

Write-Host "Restarting bank-chatbot-api container to apply code changes..." -ForegroundColor Cyan

# Navigate to bank_chatbot directory
Set-Location -Path "bank_chatbot"

# Restart the chatbot container
docker-compose restart chatbot

Write-Host ""
Write-Host "Container restarted!" -ForegroundColor Green
Write-Host ""
Write-Host "Checking container status..." -ForegroundColor Cyan
docker-compose ps chatbot

Write-Host ""
Write-Host "Viewing logs (Ctrl+C to exit)..." -ForegroundColor Cyan
docker-compose logs -f chatbot








