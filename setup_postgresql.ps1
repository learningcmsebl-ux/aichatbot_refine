# PostgreSQL Setup Script for Windows
# This script helps set up PostgreSQL for the chatbot application

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PostgreSQL Setup for Chatbot" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if PostgreSQL is already installed
$psqlPath = Get-Command psql -ErrorAction SilentlyContinue
if ($psqlPath) {
    Write-Host "✓ PostgreSQL is already installed!" -ForegroundColor Green
    Write-Host "  Location: $($psqlPath.Source)" -ForegroundColor Gray
    Write-Host ""
    
    # Check if service is running
    $pgService = Get-Service -Name postgresql* -ErrorAction SilentlyContinue
    if ($pgService) {
        Write-Host "  Service Status: $($pgService.Status)" -ForegroundColor Gray
    }
} else {
    Write-Host "PostgreSQL is not installed." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Installation Options:" -ForegroundColor Cyan
    Write-Host "1. Docker (Recommended - Easy setup)" -ForegroundColor White
    Write-Host "2. Native Windows Installation" -ForegroundColor White
    Write-Host ""
    
    $choice = Read-Host "Choose installation method (1 or 2)"
    
    if ($choice -eq "1") {
        Write-Host ""
        Write-Host "Setting up PostgreSQL with Docker..." -ForegroundColor Cyan
        
        # Check if Docker is running
        try {
            docker ps | Out-Null
            Write-Host "✓ Docker is running" -ForegroundColor Green
        } catch {
            Write-Host "✗ Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
            exit 1
        }
        
        # Create docker-compose file
        $dockerCompose = @"
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: chatbot_postgres
    environment:
      POSTGRES_USER: chatbot_user
      POSTGRES_PASSWORD: chatbot_password_123
      POSTGRES_DB: chatbot_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U chatbot_user -d chatbot_db"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
"@
        
        $dockerCompose | Out-File -FilePath "docker-compose.postgres.yml" -Encoding UTF8
        Write-Host "✓ Created docker-compose.postgres.yml" -ForegroundColor Green
        
        Write-Host ""
        Write-Host "Starting PostgreSQL container..." -ForegroundColor Cyan
        docker-compose -f docker-compose.postgres.yml up -d
        
        Write-Host ""
        Write-Host "Waiting for PostgreSQL to be ready..." -ForegroundColor Cyan
        Start-Sleep -Seconds 5
        
        # Test connection
        $maxRetries = 30
        $retryCount = 0
        $connected = $false
        
        while ($retryCount -lt $maxRetries -and -not $connected) {
            try {
                docker exec chatbot_postgres pg_isready -U chatbot_user -d chatbot_db | Out-Null
                $connected = $true
                Write-Host "✓ PostgreSQL is ready!" -ForegroundColor Green
            } catch {
                $retryCount++
                Write-Host "  Waiting... ($retryCount/$maxRetries)" -ForegroundColor Gray
                Start-Sleep -Seconds 2
            }
        }
        
        if (-not $connected) {
            Write-Host "✗ PostgreSQL failed to start. Check logs with: docker logs chatbot_postgres" -ForegroundColor Red
            exit 1
        }
        
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Green
        Write-Host "PostgreSQL Setup Complete!" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "Connection Details:" -ForegroundColor Cyan
        Write-Host "  Host: localhost" -ForegroundColor White
        Write-Host "  Port: 5432" -ForegroundColor White
        Write-Host "  Database: chatbot_db" -ForegroundColor White
        Write-Host "  User: chatbot_user" -ForegroundColor White
        Write-Host "  Password: chatbot_password_123" -ForegroundColor White
        Write-Host ""
        Write-Host "To stop: docker-compose -f docker-compose.postgres.yml down" -ForegroundColor Gray
        Write-Host "To start: docker-compose -f docker-compose.postgres.yml up -d" -ForegroundColor Gray
        Write-Host ""
        
    } elseif ($choice -eq "2") {
        Write-Host ""
        Write-Host "Native Windows Installation:" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "1. Download PostgreSQL from: https://www.postgresql.org/download/windows/" -ForegroundColor White
        Write-Host "2. Or use Chocolatey: choco install postgresql" -ForegroundColor White
        Write-Host "3. During installation, remember the password you set for the 'postgres' user" -ForegroundColor White
        Write-Host "4. After installation, run this script again to set up the database" -ForegroundColor White
        Write-Host ""
        Write-Host "Press any key to open download page..." -ForegroundColor Yellow
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        Start-Process "https://www.postgresql.org/download/windows/"
    }
}

# If PostgreSQL is available, set up the database
if ($psqlPath -or $choice -eq "1") {
    Write-Host ""
    Write-Host "Setting up database schema..." -ForegroundColor Cyan
    
    # Create setup SQL script
    $setupSQL = @"
-- Create database if it doesn't exist
SELECT 'CREATE DATABASE chatbot_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'chatbot_db')\gexec

-- Connect to the database
\c chatbot_db

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Note: Tables will be created automatically by SQLAlchemy
-- when you run the application for the first time
"@
    
    $setupSQL | Out-File -FilePath "setup_database.sql" -Encoding UTF8
    Write-Host "✓ Created setup_database.sql" -ForegroundColor Green
    
    Write-Host ""
    Write-Host "To set up the database schema, run:" -ForegroundColor Cyan
    if ($choice -eq "1") {
        Write-Host "  docker exec -i chatbot_postgres psql -U chatbot_user -d chatbot_db < setup_database.sql" -ForegroundColor White
    } else {
        Write-Host "  psql -U postgres -f setup_database.sql" -ForegroundColor White
    }
    Write-Host ""
    
    # Create .env template
    if ($choice -eq "1") {
        $envTemplate = @"
# PostgreSQL Configuration (Docker)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=chatbot_db
POSTGRES_USER=chatbot_user
POSTGRES_PASSWORD=chatbot_password_123

# Or use connection string
POSTGRES_DB_URL=postgresql://chatbot_user:chatbot_password_123@localhost:5432/chatbot_db

# Optional: Separate databases for different components
PHONEBOOK_DB_URL=postgresql://chatbot_user:chatbot_password_123@localhost:5432/chatbot_db
ANALYTICS_DB_URL=postgresql://chatbot_user:chatbot_password_123@localhost:5432/chatbot_db
"@
    } else {
        $envTemplate = @"
# PostgreSQL Configuration
# Update these values with your PostgreSQL installation details
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=chatbot_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_postgres_password_here

# Or use connection string
POSTGRES_DB_URL=postgresql://postgres:your_postgres_password_here@localhost:5432/chatbot_db

# Optional: Separate databases for different components
PHONEBOOK_DB_URL=postgresql://postgres:your_postgres_password_here@localhost:5432/chatbot_db
ANALYTICS_DB_URL=postgresql://postgres:your_postgres_password_here@localhost:5432/chatbot_db
"@
    }
    
    if (-not (Test-Path ".env")) {
        $envTemplate | Out-File -FilePath ".env.example" -Encoding UTF8
        Write-Host "✓ Created .env.example" -ForegroundColor Green
        Write-Host "  Copy this to .env and update with your credentials" -ForegroundColor Gray
    }
    
    Write-Host ""
    Write-Host "Next Steps:" -ForegroundColor Cyan
    Write-Host "1. Update .env file with PostgreSQL credentials" -ForegroundColor White
    Write-Host "2. Run: python -c 'from phonebook_postgres import PhoneBookDB; db = PhoneBookDB(); print(\"Phonebook tables created!\")'" -ForegroundColor White
    Write-Host "3. Run: python -c 'from conversation_analytics_postgres import _init_database; _init_database(); print(\"Analytics tables created!\")'" -ForegroundColor White
    Write-Host ""
}

Write-Host "Setup complete!" -ForegroundColor Green

