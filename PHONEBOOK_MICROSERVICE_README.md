# Phonebook Microservice - Redesigned

## Overview

The phonebook microservice has been redesigned to import data from MySQL and provide a comprehensive REST API for employee contact information. The service uses PostgreSQL for fast, indexed searches with full-text search capabilities.

## Architecture

```
MySQL (ebl_home) → Import Script → PostgreSQL (phonebook) → REST API
```

### Components

1. **MySQL Import Script** (`import_phonebook_from_mysql.py`)
   - Connects to MySQL database
   - Executes query to extract employee data
   - Imports data into PostgreSQL phonebook

2. **PostgreSQL Phonebook Service** (`bank_chatbot/app/services/phonebook_postgres.py`)
   - Fast, indexed employee database
   - Full-text search with GIN indexes
   - Multiple search strategies

3. **REST API** (`bank_chatbot/app/api/phonebook_routes.py`)
   - RESTful endpoints for phonebook operations
   - Integrated into main FastAPI application

## Setup

### 1. Install Dependencies

```bash
pip install -r bank_chatbot/requirements.txt
```

### 2. Configure Environment Variables

Create or update `.env` file:

```env
# PostgreSQL Configuration (for phonebook)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=bank_chatbot
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# Or use connection string
PHONEBOOK_DB_URL=postgresql://postgres:password@localhost:5432/bank_chatbot
```

### 3. Import Data from MySQL

Run the import script:

```bash
python import_phonebook_from_mysql.py
```

This will:
- Connect to MySQL at `192.168.3.57:3306`
- Fetch employee data from `ebl_home` schema
- Import into PostgreSQL phonebook
- Clear existing data and replace with fresh import

## API Endpoints

### Health Check
```
GET /api/phonebook/health
```

### Search Employees
```
GET /api/phonebook/search?q={query}&limit={limit}
```

**Example:**
```bash
curl "http://localhost:8000/api/phonebook/search?q=tanvir&limit=10"
```

### Get Employee by ID
```
GET /api/phonebook/employee/{employee_id}
```

**Example:**
```bash
curl "http://localhost:8000/api/phonebook/employee/1234"
```

### Get Employee by Email
```
GET /api/phonebook/email/{email}
```

**Example:**
```bash
curl "http://localhost:8000/api/phonebook/email/tanvir.jubair@ebl.com.bd"
```

### Get Employee by Mobile
```
GET /api/phonebook/mobile/{mobile}
```

### Get Employees by Department
```
GET /api/phonebook/department/{department}?limit={limit}
```

**Example:**
```bash
curl "http://localhost:8000/api/phonebook/department/ICT?limit=50"
```

### Get Employees by Designation
```
GET /api/phonebook/designation/{designation}?limit={limit}
```

**Example:**
```bash
curl "http://localhost:8000/api/phonebook/designation/Manager?limit=20"
```

### Get Statistics
```
GET /api/phonebook/stats
```

Returns:
- Total employees
- Department distribution
- Division distribution
- Contact information completeness

## Response Models

### Employee Response
```json
{
  "id": 1,
  "employee_id": "1234",
  "full_name": "Tanvir Jubair Islam",
  "first_name": "Tanvir",
  "last_name": "Jubair Islam",
  "designation": "Senior Officer",
  "department": "ICT",
  "division": "Technology",
  "email": "tanvir.jubair@ebl.com.bd",
  "telephone": "",
  "pabx": "",
  "ip_phone": "7526",
  "mobile": "01712239119",
  "group_email": ""
}
```

### Search Response
```json
{
  "query": "tanvir",
  "results": [
    {
      "id": 1,
      "employee_id": "1234",
      "full_name": "Tanvir Jubair Islam",
      ...
    }
  ],
  "total": 1,
  "limit": 10
}
```

## Search Strategies

The phonebook service uses multiple search strategies:

1. **Exact Name Match** - Case-insensitive exact match
2. **Employee ID** - Numeric or alphanumeric ID search
3. **Email** - Email address search
4. **Mobile Number** - Phone number search (normalized)
5. **Designation** - Role/title search with keyword matching
6. **Full-Text Search** - PostgreSQL GIN index search
7. **Partial Name Match** - Fallback partial matching

## Integration with Chatbot

The phonebook is automatically integrated into the chatbot's query routing:

- Contact queries are routed to phonebook first
- Phonebook queries never use LightRAG
- Fast response times (< 10ms for indexed searches)

## Data Import

### Manual Import

```bash
python import_phonebook_from_mysql.py
```

### Scheduled Import (Recommended)

Set up a cron job or scheduled task to run the import script periodically:

```bash
# Daily import at 2 AM
0 2 * * * /usr/bin/python3 /path/to/import_phonebook_from_mysql.py
```

## Performance

- **Exact name search**: ~2ms
- **Full-text search**: ~3ms
- **Designation search**: ~5ms
- **Department search**: ~4ms

## Database Schema

### Employees Table

```sql
CREATE TABLE employees (
    id SERIAL PRIMARY KEY,
    employee_id VARCHAR,
    full_name VARCHAR NOT NULL,
    first_name VARCHAR,
    last_name VARCHAR,
    designation VARCHAR,
    department VARCHAR,
    division VARCHAR,
    email VARCHAR,
    telephone VARCHAR,
    pabx VARCHAR,
    ip_phone VARCHAR,
    mobile VARCHAR,
    group_email VARCHAR,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    search_vector TSVECTOR
);
```

### Indexes

- `idx_employee_id` - Employee ID lookup
- `idx_full_name` - Name search
- `idx_email` - Email lookup
- `idx_mobile` - Mobile lookup
- `idx_department` - Department filter
- `idx_designation` - Designation filter
- `idx_search_vector` (GIN) - Full-text search

## Troubleshooting

### Connection Issues

**Error**: `Failed to connect to MySQL`

**Solution**:
1. Verify MySQL server is running
2. Check network connectivity to `192.168.3.57:3306`
3. Verify credentials (username: `tanvir`, password: `tanvir`)
4. Check firewall rules

### PostgreSQL Issues

**Error**: `Failed to connect to PostgreSQL`

**Solution**:
1. Verify PostgreSQL is running
2. Check connection string in `.env`
3. Verify database exists
4. Check user permissions

### Import Errors

**Error**: `No employees fetched from MySQL`

**Solution**:
1. Verify MySQL query returns results
2. Check schema name (`ebl_home`)
3. Verify table names match (ebl_posts, ebl_postmeta, etc.)
4. Check WHERE clause filters

## Maintenance

### Update Data

Run the import script to update data:

```bash
python import_phonebook_from_mysql.py
```

This will clear existing data and import fresh data from MySQL.

### Backup

Before importing, consider backing up the PostgreSQL phonebook:

```bash
pg_dump -U postgres -d bank_chatbot -t employees > phonebook_backup.sql
```

### Restore

```bash
psql -U postgres -d bank_chatbot < phonebook_backup.sql
```

## Future Enhancements

- [ ] Incremental sync (update only changed records)
- [ ] LDAP integration for automatic sync
- [ ] Caching layer for frequently accessed records
- [ ] GraphQL API option
- [ ] WebSocket support for real-time updates
- [ ] Advanced analytics and reporting

## Support

For issues or questions:
1. Check logs in `bank_chatbot/logs/`
2. Review API documentation at `/docs` endpoint
3. Check database connection status at `/api/phonebook/health`

