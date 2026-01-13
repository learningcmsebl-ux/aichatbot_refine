# Fee Engine Docker Deployment Status

## Current Status: ✅ DEPLOYED

The fee-engine microservice is now **hosted in Docker** and running successfully!

## Container Information

- **Container Name**: `fee-engine-service`
- **Port**: `8003` (mapped to host)
- **Status**: Running and healthy
- **Network**: `credit_card_rate_fee-engine-network`

## Quick Commands

### Start the Service
```bash
cd credit_card_rate
docker-compose up -d fee-engine
```

### Stop the Service
```bash
cd credit_card_rate
docker-compose down fee-engine
```

### View Logs
```bash
docker logs -f fee-engine-service
```

### Check Status
```bash
docker ps --filter "name=fee-engine"
```

### Test Health
```bash
curl http://localhost:8003/health
```

## Configuration

The service is configured via `docker-compose.yml`:

- **PostgreSQL Host**: `host.docker.internal` (to access PostgreSQL on host machine)
- **Database**: `chatbot_db`
- **User**: `chatbot_user`
- **Port**: `8003`

## Integration with Chatbot

The chatbot is configured to use the fee-engine service via:
- **URL**: `http://host.docker.internal:8003` (from chatbot container)
- **Environment Variable**: `FEE_ENGINE_URL` in chatbot's docker-compose.yml

## Notes

- The service connects to PostgreSQL running on the host machine using `host.docker.internal`
- If PostgreSQL is in a Docker container, update `POSTGRES_HOST` to the container name
- Ensure the database schema is created and data is imported before starting the service
