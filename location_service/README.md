# Location/Address Microservice

Unified API service for querying branches, ATMs, CRMs, RTDMs, priority centers, and head office information with normalized PostgreSQL database.

## Features

- Single unified endpoint `/locations` for all location types
- Normalized database schema (regions, cities, addresses)
- Integrated with admin panel (port 8009) with separate tabs
- Full-text search and filtering capabilities
- Head office identification

## Database Schema

The service uses a normalized schema with the following tables:

- **regions** - Region master data
- **cities** - City master data (linked to regions)
- **addresses** - Normalized address data (linked to cities)
- **branches** - Branch locations (linked to addresses)
- **machines** - ATM/CRM/RTDM locations (linked to addresses)
- **priority_centers** - Priority center cities (linked to cities)

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Database Setup

The service uses the same PostgreSQL database as other services. Ensure PostgreSQL is running and configured.

Environment variables:
- `LOCATION_SERVICE_DB_URL` - Full PostgreSQL connection string (optional)
- `POSTGRES_DB_URL` - Alternative connection string
- Or individual variables: `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`

### 3. Create Database Schema

```bash
# Option 1: Using SQL file
psql -U postgres -d chatbot_db -f schema.sql

# Option 2: Using Python (creates tables automatically on first run)
python -c "from location_service.models import Base; from location_service.location_service import engine; Base.metadata.create_all(bind=engine)"
```

### 4. Import Data

```bash
python import_data.py
```

This will:
- Read Excel files from `../xls/location_service/`
- Normalize data (extract cities, regions, addresses)
- Import branches, machines, and priority centers
- Identify head office from branch data

### 5. Run Service

```bash
# Direct run
python run_service.py

# Or using uvicorn
uvicorn location_service.location_service:app --host 0.0.0.0 --port 8004
```

## API Endpoints

### GET /health
Health check endpoint.

### GET /locations
Single unified endpoint for querying all location types.

**Query Parameters:**
- `type` (optional): `branch`, `atm`, `crm`, `rtdm`, `priority_center`, `head_office`
- `city` (optional): Filter by city name
- `region` (optional): Filter by region name
- `search` (optional): Full-text search across names and addresses
- `limit` (optional): Results limit (default: 100, max: 1000)
- `offset` (optional): Pagination offset

**Response:**
```json
{
  "total": 111,
  "locations": [
    {
      "id": "uuid",
      "type": "branch",
      "name": "AGRABAD BRANCH",
      "code": "1",
      "address": {
        "street": "33 Agrabad C/A",
        "city": "Chittagong",
        "region": "Chittagong",
        "zip_code": null
      },
      "status": "A"
    }
  ]
}
```

## Admin Panel Integration

The location service is integrated into the admin panel (port 8009) with three new tabs:

1. **Branches** - View and filter all branch locations
2. **ATM/CRM/RTDM** - View and filter machine locations
3. **Priority Centers** - View priority center cities

Each tab includes:
- Filtering by city and region
- Full-text search
- Pagination
- Real-time data loading

## Data Files

The service expects Excel files in `xls/location_service/`:

- `Branch-Info.xlsx` - Branch information
- `ATM_CRM_RTDM_locations.xlsx` - Machine locations
- `Priority_Centers_Fully_Normalized.xlsx` - Priority center cities

## Normalization Benefits

1. **Eliminate redundancy** - Cities and regions stored once
2. **Data consistency** - Single source of truth for city/region names
3. **Easy updates** - Update city name in one place
4. **Efficient queries** - Join-based queries instead of string matching
5. **Scalability** - Easy to add new location types

## Troubleshooting

### Location service not available in admin panel

- Ensure `location_service` directory exists at the project root
- Check that models can be imported: `python -c "from location_service.models import Branch"`
- Verify database connection and schema exists

### Import errors

- Check Excel file paths are correct
- Verify PostgreSQL is running
- Check database permissions
- Review import logs for specific errors

### Data not showing

- Run import script: `python import_data.py`
- Verify data in database: `SELECT COUNT(*) FROM branches;`
- Check API endpoint: `curl http://localhost:8004/locations?type=branch`

## Environment Variables

```bash
# Database connection
LOCATION_SERVICE_DB_URL=postgresql://user:password@localhost:5432/dbname
# Or use individual variables:
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=chatbot_db
POSTGRES_USER=chatbot_user
POSTGRES_PASSWORD=chatbot_password_123

# Service configuration
LOCATION_SERVICE_PORT=8004
LOCATION_SERVICE_HOST=0.0.0.0
LOCATION_SERVICE_RELOAD=false
```

