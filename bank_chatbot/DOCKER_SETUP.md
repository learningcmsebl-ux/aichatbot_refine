# Docker Setup for Bank Chatbot

This guide explains how to run the Bank Chatbot service in Docker.

## Prerequisites

- Docker Desktop installed and running
- Docker Compose v3.8+
- Environment variables configured

## Quick Start

### 1. Create Environment File

Copy `env.example` to `.env` and configure your settings:

```bash
cp env.example .env
```

Edit `.env` with your actual values:
- `OPENAI_API_KEY` - Your OpenAI API key (required)
- `POSTGRES_PASSWORD` - PostgreSQL password
- `LIGHTRAG_URL` - LightRAG service URL (if running outside Docker)
- `CARD_RATES_URL` - Card rates microservice URL (if running outside Docker)

### 2. Build and Start Services

```bash
# Build and start all services (PostgreSQL, Redis, Chatbot)
docker-compose up -d

# View logs
docker-compose logs -f chatbot

# Check status
docker-compose ps
```

### 3. Verify Services

```bash
# Check chatbot health
curl http://localhost:8001/api/health

# Test chat endpoint
curl -X POST http://localhost:8001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Hello", "stream": false}'
```

## Services

The docker-compose.yml includes:

1. **PostgreSQL** (port 5432)
   - Database: `bank_chatbot`
   - User: `postgres`
   - Password: From `POSTGRES_PASSWORD` env var

2. **Redis** (port 6379)
   - Used for caching LightRAG queries
   - No password by default

3. **Chatbot API** (port 8001)
   - Main FastAPI application
   - Depends on PostgreSQL and Redis
   - Health check enabled

## Networking

### Internal Services (Docker Network)

Services within Docker can communicate using service names:
- PostgreSQL: `postgres:5432`
- Redis: `redis:6379`

### External Services

For services running outside Docker (e.g., LightRAG, Card Rates):
- Use `host.docker.internal` to access host machine
- Example: `http://host.docker.internal:9262/query`

## Environment Variables

### Required
- `OPENAI_API_KEY` - OpenAI API key

### Optional (with defaults)
- `POSTGRES_PASSWORD` - Default: `changeme`
- `LIGHTRAG_URL` - Default: `http://host.docker.internal:9262/query`
- `CARD_RATES_URL` - Default: `http://host.docker.internal:8002`
- `OPENAI_MODEL` - Default: `gpt-4`
- `CORS_ORIGINS` - Default: `*`

## Common Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v

# View logs
docker-compose logs -f chatbot

# Restart chatbot service only
docker-compose restart chatbot

# Rebuild chatbot service after code changes
docker-compose up -d --build chatbot

# Execute command in chatbot container
docker-compose exec chatbot python -c "print('Hello')"

# View container status
docker-compose ps

# Check resource usage
docker stats bank-chatbot-api
```

## Troubleshooting

### Port Already in Use

If port 8001 is already in use:

```bash
# Option 1: Stop existing service
# Find and kill process using port 8001

# Option 2: Change port in docker-compose.yml
ports:
  - "8002:8001"  # Map host port 8002 to container port 8001
```

### Cannot Connect to PostgreSQL/Redis

Check if services are healthy:

```bash
docker-compose ps
```

Wait for services to be healthy before starting chatbot:

```bash
docker-compose up -d postgres redis
# Wait for health checks to pass
docker-compose up -d chatbot
```

### LightRAG Connection Issues

If LightRAG is running on the host machine:

1. Ensure LightRAG is accessible from Docker
2. Use `host.docker.internal` in `LIGHTRAG_URL`
3. On Linux, you may need to add `extra_hosts` to docker-compose.yml:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

### View Logs

```bash
# All services
docker-compose logs

# Specific service
docker-compose logs chatbot

# Follow logs
docker-compose logs -f chatbot

# Last 100 lines
docker-compose logs --tail=100 chatbot
```

## Development vs Production

### Development

```bash
# Use volume mounts for live code updates
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

### Production

1. Set `DEBUG=False` in `.env`
2. Configure proper `CORS_ORIGINS`
3. Use environment secrets management
4. Enable HTTPS with reverse proxy (nginx/traefik)
5. Set up monitoring and logging

## Updating Code

After making code changes:

```bash
# Rebuild and restart
docker-compose up -d --build chatbot

# Or restart if no dependency changes
docker-compose restart chatbot
```

## Data Persistence

- PostgreSQL data: Stored in `postgres_data` volume
- Redis data: Stored in `redis_data` volume

To backup:

```bash
# Backup PostgreSQL
docker-compose exec postgres pg_dump -U postgres bank_chatbot > backup.sql

# Backup Redis
docker-compose exec redis redis-cli SAVE
docker cp bank-chatbot-redis:/data/dump.rdb ./redis-backup.rdb
```

## Health Checks

All services have health checks:

```bash
# Check health status
docker-compose ps

# Manual health check
curl http://localhost:8001/api/health
```

## Stopping Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes all data)
docker-compose down -v
```

