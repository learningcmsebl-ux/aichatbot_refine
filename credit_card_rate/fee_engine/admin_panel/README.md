# Fee Engine Admin Panel

A web-based admin interface for managing card fees and rates in the Fee Engine system.

## Features

- **View Fee Rules**: Browse all fee rules with filtering and pagination
- **Edit Fee Rules**: Update existing fee rules
- **Create Fee Rules**: Add new fee rules
- **Delete Fee Rules**: Soft delete (mark as INACTIVE) fee rules
- **Advanced Filtering**: Filter by charge type, card category, network, product, and more
- **Admin Authentication**: Secure login with username/password

## Access

- **URL**: http://localhost:8009
- **Default Username**: `admin`
- **Default Password**: `admin123`

> **Note**: Change the default credentials using environment variables before deploying to production!

## Environment Variables

The admin panel can be configured using the following environment variables:

```bash
# Admin Credentials
ADMIN_USERNAME=admin          # Admin username
ADMIN_PASSWORD=admin123       # Admin password

# Service Configuration
ADMIN_PANEL_PORT=8009          # Port to run the admin panel on
ADMIN_PANEL_HOST=0.0.0.0      # Host to bind to

# Database Configuration (same as fee engine)
POSTGRES_HOST=host.docker.internal
POSTGRES_PORT=5432
POSTGRES_DB=chatbot_db
POSTGRES_USER=chatbot_user
POSTGRES_PASSWORD=chatbot_password_123
```

## Docker Deployment

### Using Docker Compose

The admin panel is included in the main `docker-compose.yml` file:

```bash
# Build and start the admin panel
docker-compose up -d --build fee-engine-admin

# View logs
docker-compose logs -f fee-engine-admin

# Stop the admin panel
docker-compose stop fee-engine-admin
```

### Standalone Docker

```bash
# Build the image
docker build -t fee-engine-admin -f fee_engine/admin_panel/Dockerfile .

# Run the container
docker run -d \
  --name fee-engine-admin \
  -p 8009:8009 \
  -e ADMIN_USERNAME=admin \
  -e ADMIN_PASSWORD=your_secure_password \
  -e POSTGRES_HOST=host.docker.internal \
  -e POSTGRES_DB=chatbot_db \
  -e POSTGRES_USER=chatbot_user \
  -e POSTGRES_PASSWORD=chatbot_password_123 \
  fee-engine-admin
```

## Local Development

### Prerequisites

- Python 3.11+
- PostgreSQL database (same as fee engine)
- All dependencies from `requirements.txt`

### Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=admin123
export POSTGRES_HOST=localhost
export POSTGRES_DB=chatbot_db
export POSTGRES_USER=chatbot_user
export POSTGRES_PASSWORD=chatbot_password_123

# Run the service
python admin_panel/admin_api.py
```

Or using uvicorn directly:

```bash
uvicorn admin_panel.admin_api:app --host 0.0.0.0 --port 8009 --reload
```

## API Endpoints

All API endpoints require HTTP Basic Authentication.

### Health Check
- `GET /api/health` - Health check (no auth required)

### Fee Rules
- `GET /api/rules` - List fee rules (with filters and pagination)
- `GET /api/rules/{fee_id}` - Get a specific fee rule
- `POST /api/rules` - Create a new fee rule
- `PUT /api/rules/{fee_id}` - Update a fee rule
- `DELETE /api/rules/{fee_id}` - Delete (deactivate) a fee rule

### Filters
- `GET /api/filters` - Get available filter options

## Security Notes

1. **Change Default Credentials**: Always change the default admin username and password in production
2. **Use HTTPS**: In production, deploy behind a reverse proxy with HTTPS
3. **Network Security**: Restrict access to the admin panel port (8009) to authorized networks only
4. **Password Storage**: Currently uses simple SHA256 hashing. For production, consider using bcrypt or similar

## Troubleshooting

### Cannot connect to database
- Verify PostgreSQL is running and accessible
- Check `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` environment variables
- For Docker, ensure `host.docker.internal` works (Windows/Mac) or use the actual host IP (Linux)

### Login not working
- Check that `ADMIN_USERNAME` and `ADMIN_PASSWORD` are set correctly
- Clear browser localStorage and try again
- Check browser console for errors

### Static files not loading
- Ensure the `static` directory is properly mounted/copied
- Check file permissions
- Verify the FastAPI static files mount is working

## Architecture

- **Backend**: FastAPI with SQLAlchemy ORM
- **Frontend**: Vanilla JavaScript (no framework dependencies)
- **Database**: PostgreSQL (shared with fee engine)
- **Authentication**: HTTP Basic Auth

## License

Same as the main Fee Engine project.

