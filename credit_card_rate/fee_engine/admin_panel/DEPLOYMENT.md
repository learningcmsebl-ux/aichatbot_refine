# Admin Panel Deployment Guide

## Quick Start

### 1. Build and Start the Admin Panel

```bash
cd E:\Chatbot_refine\credit_card_rate
docker-compose up -d --build fee-engine-admin
```

### 2. Access the Admin Panel

Open your browser and navigate to:
- **URL**: http://localhost:8009
- **Username**: `admin` (default)
- **Password**: `admin123` (default)

### 3. Change Default Credentials (Recommended)

Edit `docker-compose.yml` or set environment variables:

```yaml
environment:
  ADMIN_USERNAME: your_username
  ADMIN_PASSWORD: your_secure_password
```

Then restart:
```bash
docker-compose up -d --build fee-engine-admin
```

## Verify Deployment

### Check Container Status

```bash
docker-compose ps fee-engine-admin
```

### View Logs

```bash
docker-compose logs -f fee-engine-admin
```

### Test Health Endpoint

```bash
curl http://localhost:8009/api/health
```

Expected response:
```json
{"status":"healthy","service":"fee-engine-admin"}
```

## Troubleshooting

### Container Won't Start

1. Check logs: `docker-compose logs fee-engine-admin`
2. Verify database connection settings
3. Ensure PostgreSQL is running
4. Check port 8009 is not already in use

### Cannot Access Web Interface

1. Verify container is running: `docker ps | grep fee-engine-admin`
2. Check port mapping: `docker port fee-engine-admin`
3. Try accessing http://localhost:8009/api/health
4. Check firewall settings

### Database Connection Issues

1. Verify PostgreSQL is accessible from container
2. Check environment variables match your database setup
3. For Windows/Mac, ensure `host.docker.internal` works
4. For Linux, use actual host IP or container network

### Static Files Not Loading

1. Check container logs for static file mount messages
2. Verify static directory exists in container:
   ```bash
   docker exec fee-engine-admin ls -la /app/admin_panel/static
   ```
3. Rebuild container: `docker-compose up -d --build fee-engine-admin`

## Production Deployment

### Security Checklist

- [ ] Change default admin username and password
- [ ] Use strong, unique password
- [ ] Deploy behind HTTPS (use reverse proxy like nginx)
- [ ] Restrict network access to port 8009
- [ ] Enable firewall rules
- [ ] Use environment variables for secrets (not hardcoded)
- [ ] Regularly update dependencies
- [ ] Monitor access logs

### Recommended Setup

1. **Reverse Proxy (nginx)**:
   ```nginx
   server {
       listen 443 ssl;
       server_name admin.yourdomain.com;
       
       ssl_certificate /path/to/cert.pem;
       ssl_certificate_key /path/to/key.pem;
       
       location / {
           proxy_pass http://localhost:8009;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

2. **Environment Variables**:
   Create a `.env` file:
   ```bash
   ADMIN_USERNAME=secure_admin
   ADMIN_PASSWORD=very_secure_password_here
   POSTGRES_HOST=your_db_host
   POSTGRES_DB=your_database
   POSTGRES_USER=your_user
   POSTGRES_PASSWORD=your_password
   ```

   Then use in docker-compose:
   ```yaml
   env_file:
     - .env
   ```

## Maintenance

### Update Admin Panel

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose up -d --build fee-engine-admin
```

### Backup Considerations

The admin panel reads from the same database as the fee engine. Ensure your database backup strategy covers the `card_fee_master` table.

### Monitoring

Monitor the following:
- Container health status
- API response times
- Database connection pool
- Error logs
- Failed login attempts

## Support

For issues or questions:
1. Check logs: `docker-compose logs fee-engine-admin`
2. Review README.md for detailed documentation
3. Verify database connectivity
4. Check environment variables









