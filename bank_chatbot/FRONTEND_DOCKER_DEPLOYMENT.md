# Frontend Docker Deployment Guide

Both frontend services have been successfully containerized and deployed to Docker.

## Services Deployed

### 1. Bank Chatbot Frontend (Port 3000)
- **URL**: `http://localhost:3000`
- **Container**: `bank-chatbot-frontend`
- **Technology**: React + Vite + Nginx
- **Purpose**: Main chatbot user interface

### 2. Chatbot Dashboard (Port 3001)
- **URL**: `http://localhost:3001`
- **Container**: `bank-chatbot-dashboard`
- **Technology**: React + Vite + Nginx
- **Purpose**: Analytics and monitoring dashboard

### 3. Chatbot API (Port 8001)
- **URL**: `http://localhost:8001`
- **Container**: `bank-chatbot-api`
- **Technology**: FastAPI + Python
- **Purpose**: Backend API service

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│   Frontend      │     │   Dashboard     │
│   Port 3000     │     │   Port 3001     │
└────────┬────────┘     └────────┬────────┘
         │                        │
         │  /api proxy            │  /api proxy
         │                        │
         └────────────┬───────────┘
                      │
                      ▼
              ┌───────────────┐
              │  Chatbot API  │
              │   Port 8001   │
              └───────────────┘
                      │
         ┌────────────┼────────────┐
         │            │            │
         ▼            ▼            ▼
    PostgreSQL    Redis      LightRAG
    (external)   (Docker)   (external)
```

## Files Created

### Frontend (bank_chatbot_frontend/)
- `Dockerfile` - Multi-stage build (Node.js builder + Nginx production)
- `nginx.conf` - Nginx configuration with API proxy
- `.dockerignore` - Excludes unnecessary files

### Dashboard (chatbot_dashboard/)
- `Dockerfile` - Multi-stage build (Node.js builder + Nginx production)
- `nginx.conf` - Nginx configuration with API proxy
- `.dockerignore` - Excludes unnecessary files

## Configuration

### Nginx Proxy Settings

Both frontends use Nginx to proxy `/api` requests to the chatbot service:

```nginx
location /api {
    proxy_pass http://chatbot:8001;  # Uses Docker service name
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection 'upgrade';
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 300s;
    proxy_connect_timeout 75s;
}
```

### Docker Networking

All services are on the same Docker network (`chatbot-network`), allowing them to communicate using service names:
- Frontend → `http://chatbot:8001`
- Dashboard → `http://chatbot:8001`

## Deployment Commands

### Start All Services
```bash
cd bank_chatbot
docker-compose up -d
```

### Start Only Frontends
```bash
docker-compose up -d frontend dashboard
```

### Rebuild After Code Changes
```bash
docker-compose up -d --build frontend dashboard
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f frontend
docker-compose logs -f dashboard
```

### Check Status
```bash
docker-compose ps
```

### Stop Services
```bash
docker-compose down
```

## Access URLs

- **Frontend**: http://localhost:3000
- **Dashboard**: http://localhost:3001
- **API Health**: http://localhost:8001/api/health

## Troubleshooting

### Frontend Can't Connect to API

If you see 502 errors in nginx logs:
1. Check chatbot service is running: `docker-compose ps`
2. Verify they're on same network: `docker network inspect bank_chatbot_chatbot-network`
3. Test API directly: `curl http://localhost:8001/api/health`

### Port Conflicts

If ports 3000 or 3001 are in use:
1. Change ports in `docker-compose.yml`:
   ```yaml
   ports:
     - "3002:3000"  # Use different host port
   ```

### Build Errors

If TypeScript errors occur:
- Check `tsconfig.json` has `"types": ["vite/client"]`
- Ensure unused imports are removed or `noUnusedLocals: false`

## Production Considerations

1. **Environment Variables**: Set `VITE_API_URL` if API is on different domain
2. **HTTPS**: Add SSL certificates and configure nginx for HTTPS
3. **CORS**: Update `CORS_ORIGINS` in chatbot service to include frontend domains
4. **Resource Limits**: Add memory/CPU limits in docker-compose.yml
5. **Monitoring**: Set up health checks and monitoring

## Status

✅ Frontend (3000): Deployed and running
✅ Dashboard (3001): Deployed and running
✅ API (8001): Deployed and running

All services are containerized and ready for production use!
