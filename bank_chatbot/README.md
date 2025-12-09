# Bank Chatbot - FastAPI Orchestrator

A production-ready AI chatbot system for banking services built with FastAPI, PostgreSQL, Redis, and LightRAG.

## Architecture

```
┌─────────────────────────────────────────┐
│      FastAPI Chat Orchestrator          │
│         (app.py)                        │
└──────────────┬──────────────────────────┘
               │
    ┌──────────┼──────────┐
    │          │          │
    ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐
│Postgres│ │ Redis  │ │LightRAG│
│Memory  │ │ Cache  │ │  RAG   │
└────────┘ └────────┘ └────────┘
```

## Features

- ✅ **FastAPI Orchestrator**: Modern async web framework
- ✅ **PostgreSQL**: Persistent conversation memory
- ✅ **Redis**: High-performance caching for LightRAG queries
- ✅ **LightRAG Integration**: RAG system for knowledge retrieval
- ✅ **OpenAI GPT-4**: Advanced language model for responses
- ✅ **Streaming Responses**: Real-time response streaming
- ✅ **Session Management**: Conversation history per session
- ✅ **Intelligent Routing**: Small talk detection and context-aware responses
- ✅ **Error Handling**: Graceful degradation and error recovery

## Project Structure

```
bank_chatbot/
├── app/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py          # API endpoints
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py           # Configuration management
│   ├── database/
│   │   ├── __init__.py
│   │   ├── postgres.py         # PostgreSQL models and connection
│   │   └── redis_client.py     # Redis client and caching
│   ├── services/
│   │   ├── __init__.py
│   │   ├── chat_orchestrator.py # Main orchestration logic
│   │   └── lightrag_client.py   # LightRAG API client
│   └── main.py                  # Application entry point (alternative)
├── app.py                       # Main application entry point
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment variables template
└── README.md                    # This file
```

## Setup

### 1. Prerequisites

- Python 3.9+
- PostgreSQL 12+
- Redis 6+
- LightRAG service running (Docker container or standalone)

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# OpenAI
OPENAI_API_KEY=your_key_here

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_DB=bank_chatbot
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# LightRAG
LIGHTRAG_URL=http://localhost:9262/query
LIGHTRAG_API_KEY=MyCustomLightRagKey456
```

### 4. Initialize Database

The application will automatically create the required tables on first run. Alternatively, you can use Alembic for migrations:

```bash
# Create migration
alembic revision --autogenerate -m "Initial migration"

# Apply migration
alembic upgrade head
```

### 5. Run the Application

```bash
# Development
uvicorn app:app --reload --host 0.0.0.0 --port 8001

# Production
uvicorn app:app --host 0.0.0.0 --port 8001 --workers 4
```

## API Endpoints

### Health Check

```bash
GET /api/health
GET /api/health/detailed
```

### Chat

```bash
# Chat with streaming (default)
POST /api/chat
{
  "query": "What are your loan products?",
  "session_id": "optional-session-id",
  "knowledge_base": "optional-kb-name",
  "stream": true
}

# Chat without streaming
POST /api/chat
{
  "query": "What are your loan products?",
  "stream": false
}

# Streaming endpoint
POST /api/chat/stream
{
  "query": "What are your loan products?"
}
```

### Conversation History

```bash
# Get history
GET /api/chat/history/{session_id}?limit=50

# Clear history
DELETE /api/chat/history/{session_id}
```

## Usage Examples

### Python Client

```python
import httpx
import asyncio

async def chat_example():
    async with httpx.AsyncClient() as client:
        # Streaming chat
        async with client.stream(
            "POST",
            "http://localhost:8001/api/chat",
            json={
                "query": "What are your savings account options?",
                "stream": True
            }
        ) as response:
            async for chunk in response.aiter_text():
                print(chunk, end="", flush=True)

asyncio.run(chat_example())
```

### cURL

```bash
# Non-streaming
curl -X POST "http://localhost:8001/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are your loan products?",
    "stream": false
  }'

# Streaming
curl -X POST "http://localhost:8001/api/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are your loan products?"
  }'
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `OPENAI_MODEL` | OpenAI model name | `gpt-4` |
| `POSTGRES_HOST` | PostgreSQL host | `localhost` |
| `POSTGRES_DB` | Database name | `bank_chatbot` |
| `REDIS_HOST` | Redis host | `localhost` |
| `LIGHTRAG_URL` | LightRAG API URL | `http://localhost:9262/query` |
| `REDIS_CACHE_TTL` | Cache TTL in seconds | `3600` |

## Architecture Details

### Chat Orchestrator Flow

1. **Request Reception**: User query received via API
2. **Session Management**: Session ID generated/retrieved
3. **Query Classification**: Detect small talk vs banking queries
4. **LightRAG Query** (if needed):
   - Check Redis cache first
   - Query LightRAG API if cache miss
   - Cache result for future use
5. **Conversation History**: Retrieve from PostgreSQL
6. **OpenAI Processing**: Generate response with context
7. **Response Streaming**: Stream response to user
8. **Memory Storage**: Save conversation to PostgreSQL

### Caching Strategy

- **Redis Cache**: LightRAG queries cached with 1-hour TTL
- **Cache Key**: `lightrag:{kb_name}:query:{query_hash}`
- **Benefits**: 20-50x faster for repeated queries

### Database Schema

```sql
CREATE TABLE chat_messages (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_session_created ON chat_messages(session_id, created_at);
```

## Development

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest
```

### Code Structure

- **Modular Design**: Separated concerns (API, services, database)
- **Async/Await**: Full async support for performance
- **Error Handling**: Comprehensive error handling and logging
- **Type Hints**: Full type annotations for better IDE support

## Production Deployment

### Docker (Recommended)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
```

### Environment Setup

1. Set `DEBUG=False`
2. Configure `CORS_ORIGINS` with specific domains
3. Use environment variables for secrets
4. Enable HTTPS
5. Set up monitoring and logging

## Troubleshooting

### PostgreSQL Connection Issues

```bash
# Test connection
psql -h localhost -U postgres -d bank_chatbot
```

### Redis Connection Issues

```bash
# Test connection
redis-cli ping
```

### LightRAG Connection Issues

```bash
# Test LightRAG health
curl http://localhost:9262/health
```

## License

MIT License

## Support

For issues and questions, please open an issue on the repository.

