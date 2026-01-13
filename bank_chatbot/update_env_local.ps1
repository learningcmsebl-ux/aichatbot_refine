# PowerShell script to update .env file with local PostgreSQL configuration
# This removes any Supabase references and configures for local Docker container

$envFile = ".env"
$envExample = "env.example"

Write-Host "Updating .env file for local PostgreSQL container..." -ForegroundColor Cyan

# Check if .env exists
if (Test-Path $envFile) {
    Write-Host "Found existing .env file" -ForegroundColor Yellow
    
    # Read current .env
    $content = Get-Content $envFile -Raw
    
    # Update PostgreSQL configuration
    $content = $content -replace 'POSTGRES_HOST=.*', 'POSTGRES_HOST=localhost'
    $content = $content -replace 'POSTGRES_PORT=.*', 'POSTGRES_PORT=5432'
    $content = $content -replace 'POSTGRES_DB=.*', 'POSTGRES_DB=chatbot_db'
    $content = $content -replace 'POSTGRES_USER=.*', 'POSTGRES_USER=chatbot_user'
    $content = $content -replace 'POSTGRES_PASSWORD=.*', 'POSTGRES_PASSWORD=chatbot_password_123'
    
    # Remove any Supabase-related lines
    $lines = $content -split "`n" | Where-Object { 
        $_ -notmatch 'supabase' -and 
        $_ -notmatch 'aws-0\.oavtrlusfysd' -and
        $_ -notmatch 'pooler\.supabase'
    }
    
    $content = $lines -join "`n"
    
    # Write updated content
    Set-Content -Path $envFile -Value $content -NoNewline
    Write-Host "✓ Updated .env file with local PostgreSQL configuration" -ForegroundColor Green
} else {
    Write-Host ".env file not found. Creating from env.example..." -ForegroundColor Yellow
    Copy-Item $envExample $envFile
    Write-Host "✓ Created .env file from env.example" -ForegroundColor Green
    Write-Host "Please update OPENAI_API_KEY in .env file" -ForegroundColor Yellow
}

Write-Host "`nCurrent PostgreSQL configuration:" -ForegroundColor Cyan
Get-Content $envFile | Select-String "POSTGRES" | ForEach-Object { Write-Host "  $_" }

Write-Host "`n✓ Configuration updated for local Docker container" -ForegroundColor Green
Write-Host "  Database: chatbot_db" -ForegroundColor Gray
Write-Host "  User: chatbot_user" -ForegroundColor Gray
Write-Host "  Host: localhost:5432" -ForegroundColor Gray

