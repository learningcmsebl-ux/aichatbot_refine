# Docker Services Missing - Frontend and Dashboard

## Problem

When you run `docker-compose build chatbot` or `docker-compose up -d chatbot`, it only builds/starts the **chatbot** service. The **frontend** and **dashboard** services are defined in `docker-compose.yml` but are not automatically started.

## Why This Happens

1. **Selective Service Building**: When you specify a service name like `docker-compose build chatbot`, Docker Compose only builds that service
2. **Dependencies**: Frontend and dashboard depend on chatbot, but they won't start unless explicitly started
3. **Restart Scripts**: The restart scripts only target specific services (chatbot, fee-engine)

## Solution: Start All Services

### Option 1: Start All Services (Recommended)

```bash
cd bank_chatbot

# Build and start ALL services (redis, chatbot, frontend, dashboard)
docker-compose up -d --build
```

### Option 2: Start Specific Services

```bash
cd bank_chatbot

# Start frontend and dashboard (chatbot must be running first)
docker-compose up -d frontend dashboard

# Or build and start them
docker-compose up -d --build frontend dashboard
```

### Option 3: Check What's Running

```bash
# See all services defined
docker-compose config --services

# See what's actually running
docker-compose ps

# See all containers (including stopped)
docker-compose ps -a
```

## Complete Rebuild Workflow

After making code changes, rebuild and start ALL services:

```bash
cd bank_chatbot

# 1. Stop all services
docker-compose down

# 2. Rebuild all services (or specific ones)
docker-compose build --no-cache chatbot frontend dashboard

# 3. Start all services
docker-compose up -d

# 4. Check status
docker-compose ps

# 5. View logs
docker-compose logs -f
```

## Verify Services Are Running

```bash
# Check all containers
docker ps

# Should show:
# - bank-chatbot-redis (port 6379)
# - bank-chatbot-api (port 8001) - Backend
# - bank-chatbot-frontend (port 3000) - Frontend
# - bank-chatbot-dashboard (port 3001) - Dashboard

# Test endpoints
curl http://localhost:8001/api/health          # Backend
curl http://localhost:3000                       # Frontend
curl http://localhost:3001                       # Dashboard
```

## Common Issues

### Issue 1: Frontend/Dashboard Build Fails

**Error**: `ERROR: failed to solve: failed to compute cache key`

**Cause**: Build context paths (`../bank_chatbot_frontend`, `../chatbot_dashboard`) may not exist or be incorrect

**Solution**:
```bash
# Verify directories exist
ls ../bank_chatbot_frontend
ls ../chatbot_dashboard

# If they don't exist, check the actual paths
# Update docker-compose.yml if paths are wrong
```

### Issue 2: Services Start But Immediately Exit

**Check logs**:
```bash
docker-compose logs frontend
docker-compose logs dashboard
```

**Common causes**:
- Missing dependencies
- Build errors
- Port conflicts
- Health check failures

### Issue 3: Only Chatbot Starts

**Cause**: You ran `docker-compose up -d chatbot` instead of `docker-compose up -d`

**Solution**: Start all services:
```bash
docker-compose up -d
```

## Updated Restart Script

If you want to restart all services, use:

```bash
cd bank_chatbot
docker-compose down
docker-compose up -d --build
```

Or create a script that restarts all services (see `restart_all_docker_services.ps1` below).

