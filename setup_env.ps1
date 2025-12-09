# Setup Environment Variables for PostgreSQL
# Run this script to set up your .env file

$envContent = @"
# PostgreSQL Configuration (Docker)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=chatbot_db
POSTGRES_USER=chatbot_user
POSTGRES_PASSWORD=chatbot_password_123

# Connection string (alternative)
POSTGRES_DB_URL=postgresql://chatbot_user:chatbot_password_123@localhost:5432/chatbot_db

# Optional: Separate databases for different components
PHONEBOOK_DB_URL=postgresql://chatbot_user:chatbot_password_123@localhost:5432/chatbot_db
ANALYTICS_DB_URL=postgresql://chatbot_user:chatbot_password_123@localhost:5432/chatbot_db

# LightRAG Configuration
LIGHTRAG_URL=http://localhost:9262/query
LIGHTRAG_API_KEY=MyCustomLightRagKey456
LIGHTRAG_KNOWLEDGE_BASE=ebl_website

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_CACHE_TTL=3600

# OpenAI Configuration (add your key)
# OPENAI_API_KEY=your_openai_api_key_here
"@

$envContent | Out-File -FilePath ".env" -Encoding UTF8 -NoNewline
Write-Host "✓ Created .env file with PostgreSQL credentials" -ForegroundColor Green
Write-Host ""
Write-Host "Next: Run 'python test_postgres_connection.py' to test the connection" -ForegroundColor Cyan

