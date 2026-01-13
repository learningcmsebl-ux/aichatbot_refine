# Fee Engine Docker Deployment Guide

## Overview

The fee-engine microservice can be deployed using Docker for easier management and consistency with other services.

## Prerequisites

- Docker and Docker Compose installed
- PostgreSQL database accessible (either on host or in another container)
- Database schema created (run `schema.sql` first)

## Quick Start

### 1. Build and Start the Service

```bash
cd credit_card_rate
docker-compose up -d --build fee-engine
```

### 2. Check Service Status

```bash
docker-compose ps
```

### 3. View Logs

```bash
docker-compose logs -f fee-engine
```

### 4. Test the Service

```bash
curl http://localhost:8003/health
```

## Configuration

### Environment Variables

The service can be configured using environment variables in `docker-compose.yml` or a `.env` file:

```env
# PostgreSQL Configuration
POSTGRES_HOST=host.docker.internal
POSTGRES_PORT=5432
POSTGRES_DB=chatbot_db
POSTGRES_USER=chatbot_user
POSTGRES_PASSWORD=chatbot_password_123

# Fee Engine Configuration
FEE_ENGINE_PORT=8003
FEE_ENGINE_HOST=0.0.0.0
```

### Database Connection

The service uses `host.docker.internal` by default to access PostgreSQL running on the host machine. If PostgreSQL is in another Docker container:

1. Use the container name as `POSTGRES_HOST`
2. Ensure both containers are on the same Docker network
3. Or use an external network

## Integration with Chatbot

Update the chatbot's `docker-compose.yml` to use the fee-engine service:

```yaml
services:
  chatbot:
    # ... existing config ...
    environment:
      # ... existing env vars ...
      FEE_ENGINE_URL: http://fee-engine-service:8003  # Use service name for Docker networking
    networks:
      - chatbot-network
      - fee-engine-network  # Connect to fee-engine network
    depends_on:
      - fee-engine

  fee-engine:
    # ... fee-engine config ...
    networks:
      - fee-engine-network
      - chatbot-network  # Connect to chatbot network
```

Or if fee-engine is on host:

```yaml
services:
  chatbot:
    environment:
      FEE_ENGINE_URL: http://host.docker.internal:8003
```

## Data Migration

Before starting the service, ensure data is imported:

```bash
# Option 1: Run migration from host (if Python is available)
cd credit_card_rate
python fee_engine/migrate_from_csv.py

# Option 2: Run migration inside container
docker-compose exec fee-engine python migrate_from_csv.py
```

## Troubleshooting

### Service won't start

1. Check logs: `docker-compose logs fee-engine`
2. Verify PostgreSQL is accessible from container
3. Check database schema is created
4. Verify data is imported

### Connection errors

1. Ensure PostgreSQL is running and accessible
2. Check `POSTGRES_HOST` is correct:
   - `host.docker.internal` for host PostgreSQL
   - Container name for Docker PostgreSQL
3. Verify network connectivity

### Health check fails

1. Check service is listening on port 8003
2. Verify database connection works
3. Check logs for errors

## Stopping the Service

```bash
docker-compose down
```

## Updating the Service

```bash
docker-compose up -d --build fee-engine
```

## Production Considerations

1. **Use environment files**: Store sensitive credentials in `.env` file (not committed to git)
2. **Network security**: Use Docker networks to isolate services
3. **Resource limits**: Add resource constraints in `docker-compose.yml`
4. **Logging**: Configure log rotation and aggregation
5. **Monitoring**: Add health checks and monitoring endpoints
6. **Backup**: Ensure database backups are configured

## Example Production docker-compose.yml

```yaml
version: '3.8'

services:
  fee-engine:
    build:
      context: .
      dockerfile: fee_engine/Dockerfile
    container_name: fee-engine-service
    ports:
      - "8003:8003"
    environment:
      POSTGRES_HOST: ${POSTGRES_HOST}
      POSTGRES_PORT: ${POSTGRES_PORT}
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      FEE_ENGINE_PORT: 8003
    networks:
      - backend-network
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
    healthcheck:
      test: ["CMD", "python", "-c", "import httpx; httpx.get('http://localhost:8003/health', timeout=5)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

networks:
  backend-network:
    driver: bridge
```
