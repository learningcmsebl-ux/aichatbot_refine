# Docker Rebuild Guide for Phonebook Changes

## Quick Answer: YES, Rebuild Required

Since the Dockerfile copies code into the image (`COPY . .`), you need to rebuild the container to get the new code changes.

## Rebuild Steps

### 1. Stop the Current Container

```bash
cd bank_chatbot
docker-compose down
```

### 2. Rebuild the Container

```bash
# Rebuild with no cache to ensure all changes are included
docker-compose build --no-cache chatbot

# Or rebuild all services
docker-compose build --no-cache
```

### 3. Start the Services

```bash
docker-compose up -d
```

### 4. Verify the Changes

```bash
# Check if phonebook endpoints are available
curl http://localhost:8001/api/phonebook/health

# Check logs
docker-compose logs -f chatbot
```

## Alternative: Development Mode with Volume Mounts

If you want to avoid rebuilding for every code change during development, you can add volume mounts to `docker-compose.yml`:

```yaml
chatbot:
  build:
    context: .
    dockerfile: Dockerfile
  container_name: bank-chatbot-api
  ports:
    - "8001:8001"
  volumes:
    # Mount code directory for live development
    - ./app:/app/app
    - ./main.py:/app/main.py
    - ./import_phonebook_from_mysql.py:/app/import_phonebook_from_mysql.py
  # ... rest of config
```

**Note**: This is for development only. For production, use the rebuild approach.

## Import Data from MySQL

**Important**: The import script should be run from your **host machine** (not inside the container) because it needs to connect to MySQL at `192.168.3.57`.

### Option 1: Run on Host (Recommended)

```bash
# From project root
python import_phonebook_from_mysql.py
```

### Option 2: Run Inside Container (if MySQL is accessible from container)

```bash
# Copy import script into container
docker cp import_phonebook_from_mysql.py bank-chatbot-api:/app/

# Execute inside container
docker exec -it bank-chatbot-api python import_phonebook_from_mysql.py
```

## Complete Workflow

```bash
# 1. Rebuild container
cd bank_chatbot
docker-compose build --no-cache chatbot

# 2. Start services
docker-compose up -d

# 3. Wait for services to be healthy
docker-compose ps

# 4. Import phonebook data (from host)
cd ..
python import_phonebook_from_mysql.py

# 5. Verify phonebook API
curl http://localhost:8001/api/phonebook/health
curl http://localhost:8001/api/phonebook/stats
```

## What Changed?

The following files were added/modified:

1. **New Files**:
   - `import_phonebook_from_mysql.py` - MySQL import script
   - `bank_chatbot/app/api/phonebook_routes.py` - Phonebook API endpoints
   - `PHONEBOOK_MICROSERVICE_README.md` - Documentation

2. **Modified Files**:
   - `bank_chatbot/main.py` - Added phonebook router
   - `bank_chatbot/requirements.txt` - Added `pymysql>=1.1.0`
   - `requirements.txt` - Added `pymysql>=1.1.0`

## Troubleshooting

### Container won't start after rebuild

```bash
# Check logs
docker-compose logs chatbot

# Common issues:
# - Missing dependencies: Check requirements.txt
# - Import errors: Verify all new files are copied
# - Database connection: Check POSTGRES_HOST in docker-compose.yml
```

### Phonebook endpoints not found

```bash
# Verify router is included in main.py
docker exec -it bank-chatbot-api cat main.py | grep phonebook_router

# Check if routes are registered
curl http://localhost:8001/docs
# Look for /api/phonebook endpoints in Swagger UI
```

### Import script can't connect to MySQL

- Verify MySQL is accessible from host: `telnet 192.168.3.57 3306`
- Check firewall rules
- Verify credentials in `import_phonebook_from_mysql.py`

## Production Deployment

For production, always rebuild:

```bash
# Build production image
docker-compose -f docker-compose.yml build --no-cache chatbot

# Tag and push to registry (if using)
docker tag bank-chatbot-api:latest your-registry/bank-chatbot-api:latest
docker push your-registry/bank-chatbot-api:latest

# Deploy
docker-compose up -d
```

