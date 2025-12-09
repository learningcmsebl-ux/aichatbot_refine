# Bank Chatbot - Quick Setup Guide

## Prerequisites

1. **Python 3.9+** installed
2. **PostgreSQL** running (or use Docker)
3. **Redis** running (or use Docker)
4. **LightRAG** service running (Docker container or standalone)

## Quick Start

### 1. Install Dependencies

```bash
cd bank_chatbot
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the example environment file:

```bash
cp env.example .env
```

Edit `.env` with your configuration:

```env
# Required
OPENAI_API_KEY=your_openai_api_key_here
POSTGRES_PASSWORD=your_postgres_password

# Optional (defaults shown)
POSTGRES_HOST=localhost
POSTGRES_DB=bank_chatbot
REDIS_HOST=localhost
LIGHTRAG_URL=http://localhost:9262/query
```

### 3. Start Services (if using Docker)

```bash
# Start PostgreSQL
docker run -d \
  --name postgres-bank-chatbot \
  -e POSTGRES_PASSWORD=your_password \
  -e POSTGRES_DB=bank_chatbot \
  -p 5432:5432 \
  postgres:15

# Start Redis
docker run -d \
  --name redis-bank-chatbot \
  -p 6379:6379 \
  redis:7-alpine
```

### 4. Run the Application

```bash
# Option 1: Using the run script
python run.py

# Option 2: Using uvicorn directly
uvicorn app:app --reload --host 0.0.0.0 --port 8001
```

### 5. Test the API

```bash
# Health check
curl http://localhost:8001/api/health

# Chat test
curl -X POST "http://localhost:8001/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Hello, what banking services do you offer?",
    "stream": false
  }'
```

## Verify Setup

### Check PostgreSQL Connection

```bash
psql -h localhost -U postgres -d bank_chatbot -c "SELECT 1;"
```

### Check Redis Connection

```bash
redis-cli ping
# Should return: PONG
```

### Check LightRAG Connection

```bash
curl http://localhost:9262/health
```

## Troubleshooting

### Database Connection Error

- Verify PostgreSQL is running: `docker ps` or `pg_isready`
- Check credentials in `.env`
- Ensure database exists: `CREATE DATABASE bank_chatbot;`

### Redis Connection Error

- Verify Redis is running: `redis-cli ping`
- Check Redis host/port in `.env`

### LightRAG Connection Error

- Verify LightRAG container is running: `docker ps`
- Check LightRAG URL and API key in `.env`
- Test LightRAG health endpoint

### Import Errors

- Ensure you're in the `bank_chatbot` directory
- Verify all dependencies are installed: `pip list`
- Check Python path: `python -c "import sys; print(sys.path)"`

## Next Steps

1. Review the [README.md](README.md) for detailed documentation
2. Test the API endpoints using the examples
3. Configure your LightRAG knowledge base
4. Customize the system message in `app/services/chat_orchestrator.py`

## Production Deployment

For production:

1. Set `DEBUG=False` in `.env`
2. Configure specific `CORS_ORIGINS` (not `*`)
3. Use environment variables for all secrets
4. Set up proper logging and monitoring
5. Use a process manager like systemd or supervisor
6. Enable HTTPS with a reverse proxy (nginx)

