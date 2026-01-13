# EBL Chatbot Microservices Architecture

## Overview

The EBL Chatbot system is built using a microservices architecture with multiple independent services that communicate via REST APIs. Each service handles a specific domain of functionality.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CLIENT LAYER                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐              │
│  │   Frontend   │      │   Dashboard  │      │  Admin Panel │              │
│  │  Port 3000   │      │  Port 3001   │      │  Port 8009   │              │
│  │  (React)     │      │  (React)     │      │  (FastAPI)    │              │
│  └──────┬───────┘      └──────┬───────┘      └──────┬───────┘              │
│         │                      │                      │                       │
└─────────┼──────────────────────┼──────────────────────┼───────────────────────┘
          │                      │                      │
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        API GATEWAY / ORCHESTRATION LAYER                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│                    ┌──────────────────────────┐                            │
│                    │   Bank Chatbot API       │                            │
│                    │   Port 8001              │                            │
│                    │   (FastAPI + OpenAI)     │                            │
│                    │   Chat Orchestrator      │                            │
│                    └───────────┬───────────────┘                            │
│                                │                                             │
└────────────────────────────────┼─────────────────────────────────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
                    ▼            ▼            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MICROSERVICES LAYER                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │
│  │  Fee Engine      │  │ Location Service │  │  LightRAG        │         │
│  │  Port 8003       │  │  Port 8004       │  │  Port 9262       │         │
│  │  (FastAPI)      │  │  (FastAPI)       │  │  (Docker)        │         │
│  │                  │  │                  │  │                  │         │
│  │  Card Fees       │  │  Branches        │  │  Knowledge Base  │         │
│  │  Calculations    │  │  ATMs/CRMs/RTDMs │  │  RAG Queries     │         │
│  │  Retail Assets   │  │  Priority Centers│  │                  │         │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘         │
│           │                      │                      │                     │
└───────────┼──────────────────────┼──────────────────────┼─────────────────────┘
            │                      │                      │
            ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA LAYER                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                      │
│  │  PostgreSQL  │  │    Redis     │  │  PostgreSQL   │                      │
│  │  Port 5432   │  │  Port 6379   │  │  Port 5432   │                      │
│  │              │  │              │  │              │                      │
│  │  chatbot_db  │  │  Cache       │  │  chatbot_db  │                      │
│  │  (Chatbot)   │  │  (LightRAG)  │  │  (Fee/Loc)   │                      │
│  └──────────────┘  └──────────────┘  └──────────────┘                      │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Microservices Details

### 1. Bank Chatbot API (Main Orchestrator)
- **Port**: `8001`
- **Technology**: FastAPI, Python, OpenAI GPT-4
- **Purpose**: Main API gateway and chat orchestrator
- **Responsibilities**:
  - Routes queries to appropriate microservices
  - Manages conversation state and history
  - Integrates with OpenAI for natural language responses
  - Coordinates between all microservices
- **Endpoints**:
  - `POST /api/chat` - Chat endpoint (streaming and sync)
  - `GET /api/health` - Health check
  - `GET /api/health/detailed` - Detailed health status
- **Dependencies**:
  - PostgreSQL (chat history, leads)
  - Redis (caching)
  - Fee Engine Service (port 8003)
  - Location Service (port 8004)
  - LightRAG (port 9262)
  - OpenAI API

### 2. Fee Engine Service
- **Port**: `8003`
- **Technology**: FastAPI, Python, SQLAlchemy
- **Purpose**: Deterministic fee calculations for cards and retail assets
- **Responsibilities**:
  - Calculate card fees (credit/debit/prepaid)
  - Calculate retail asset charges (loans, overdrafts)
  - Handle fee rules and schedules
  - Provide authoritative fee data
- **Endpoints**:
  - `POST /fees/calculate` - Calculate fee for a transaction
  - `GET /fees/rules` - Get fee rules
  - `GET /health` - Health check
- **Database**: PostgreSQL (`chatbot_db`)
- **Tables**: `fee_rules`, `card_charges`, `retail_asset_charges`
- **Docker**: `fee-engine-service` (from `credit_card_rate/docker-compose.yml`)

### 3. Location Service
- **Port**: `8004`
- **Technology**: FastAPI, Python, SQLAlchemy
- **Purpose**: Unified API for all location-related queries
- **Responsibilities**:
  - Query branches
  - Query ATMs, CRMs, RTDMs
  - Query priority centers
  - Query head office information
  - Provide normalized location data
- **Endpoints**:
  - `GET /locations` - Query all location types
    - Query params: `type`, `city`, `region`, `search`, `limit`, `offset`
    - Types: `branch`, `atm`, `crm`, `rtdm`, `priority_center`, `head_office`
  - `GET /health` - Health check
- **Database**: PostgreSQL (`chatbot_db`)
- **Tables**: `regions`, `cities`, `addresses`, `branches`, `machines`, `priority_centers`
- **Data**: Normalized location data from Excel files

### 4. Fee Engine Admin Panel
- **Port**: `8009`
- **Technology**: FastAPI, Python, HTML/JavaScript
- **Purpose**: Administrative interface for managing fee rules and locations
- **Responsibilities**:
  - Manage card fee rules
  - Manage retail asset charges
  - Manage location data (branches, machines, priority centers)
  - View and edit fee schedules
- **Endpoints**:
  - `GET /` - Admin panel UI
  - `GET /api/card-fees` - Get card fees
  - `POST /api/card-fees` - Create/update card fee
  - `GET /api/locations` - Get locations (integrated from location service)
  - `GET /api/health` - Health check
- **Authentication**: HTTP Basic Auth
- **Docker**: `fee-engine-admin-panel` (from `credit_card_rate/docker-compose.yml`)

### 5. LightRAG Service
- **Port**: `9262`
- **Technology**: Docker container, Python
- **Purpose**: Retrieval-Augmented Generation for knowledge base queries
- **Responsibilities**:
  - Query knowledge bases
  - Retrieve relevant context from documents
  - Support multiple knowledge bases:
    - `ebl_website` - General website content
    - `ebl_products` - Banking products
    - `ebl_policies` - Compliance and policies
    - `ebl_financial_reports` - Financial reports
    - `ebl_user_docs` - User documents
- **Endpoints**:
  - `POST /query` - Query knowledge base
- **Docker**: External container (`LightRAG_New`)

### 6. Frontend (Chat Interface)
- **Port**: `3000`
- **Technology**: React, Vite, TypeScript
- **Purpose**: Main chatbot user interface
- **Responsibilities**:
  - Chat interface for users
  - Real-time streaming responses
  - Conversation history
- **API**: Connects to Bank Chatbot API (port 8001)
- **Docker**: `bank-chatbot-frontend`

### 7. Dashboard (Analytics)
- **Port**: `3001`
- **Technology**: React, Vite, TypeScript
- **Purpose**: Analytics and monitoring dashboard
- **Responsibilities**:
  - View conversation analytics
  - Monitor service health
  - View usage statistics
- **API**: Connects to Bank Chatbot API (port 8001)
- **Docker**: `bank-chatbot-dashboard`

## Data Flow

### Query Routing Logic

```
User Query
    │
    ├─→ Is Fee Schedule Query?
    │   └─→ YES → Fee Engine Service (Port 8003)
    │
    ├─→ Is Location Query?
    │   └─→ YES → Location Service (Port 8004)
    │
    ├─→ Is Phonebook/Employee Query?
    │   └─→ YES → PostgreSQL Phonebook Database
    │
    ├─→ Is Small Talk?
    │   └─→ YES → Direct OpenAI Response
    │
    └─→ Default → LightRAG Service (Port 9262)
        └─→ Knowledge Base Selection:
            ├─→ Organizational Overview → ebl_website
            ├─→ Banking Products → ebl_products
            ├─→ Compliance/Policy → ebl_policies
            ├─→ Financial Reports → ebl_financial_reports
            └─→ Default → ebl_website
```

## Service Communication

### Internal Communication (HTTP REST APIs)

1. **Chatbot API → Fee Engine**
   - URL: `http://localhost:8003/fees/calculate`
   - Method: POST
   - Purpose: Calculate card fees and retail asset charges

2. **Chatbot API → Location Service**
   - URL: `http://localhost:8004/locations`
   - Method: GET
   - Purpose: Query branches, ATMs, CRMs, RTDMs, priority centers

3. **Chatbot API → LightRAG**
   - URL: `http://localhost:9262/query`
   - Method: POST
   - Purpose: Query knowledge bases for context

4. **Admin Panel → Location Service**
   - URL: `http://localhost:8004/locations` (via integrated models)
   - Method: GET
   - Purpose: Display location data in admin interface

### Database Connections

1. **Chatbot API Database**
   - Database: `bank_chatbot`
   - Tables: `conversations`, `messages`, `leads`, `phonebook`
   - Purpose: Chat history, lead management, employee directory

2. **Fee Engine Database**
   - Database: `chatbot_db`
   - Tables: `fee_rules`, `card_charges`, `retail_asset_charges`
   - Purpose: Fee calculation rules and schedules

3. **Location Service Database**
   - Database: `chatbot_db`
   - Tables: `regions`, `cities`, `addresses`, `branches`, `machines`, `priority_centers`
   - Purpose: Normalized location data

## Environment Variables

### Chatbot API (.env)
```env
# OpenAI
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4
OPENAI_TEMPERATURE=0.7

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=bank_chatbot
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# LightRAG
LIGHTRAG_URL=http://localhost:9262/query
LIGHTRAG_API_KEY=MyCustomLightRagKey456

# Microservices
FEE_ENGINE_URL=http://localhost:8003
LOCATION_SERVICE_URL=http://localhost:8004
```

### Fee Engine Service
```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=chatbot_db
POSTGRES_USER=chatbot_user
POSTGRES_PASSWORD=chatbot_password_123
FEE_ENGINE_PORT=8003
```

### Location Service
```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=chatbot_db
POSTGRES_USER=chatbot_user
POSTGRES_PASSWORD=chatbot_password_123
LOCATION_SERVICE_PORT=8004
```

## Docker Services

### Fee Engine Stack (`credit_card_rate/docker-compose.yml`)
- `fee-engine-service` (Port 8003)
- `fee-engine-admin-panel` (Port 8009)

### Chatbot Stack (`bank_chatbot/docker-compose.yml`)
- `bank-chatbot-api` (Port 8001)
- `postgres` (Port 5432)
- `redis` (Port 6379)

### Frontend Services
- `bank-chatbot-frontend` (Port 3000)
- `bank-chatbot-dashboard` (Port 3001)

## Port Summary

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| Bank Chatbot API | 8001 | HTTP | Main API gateway |
| Fee Engine | 8003 | HTTP | Fee calculations |
| Location Service | 8004 | HTTP | Location queries |
| Admin Panel | 8009 | HTTP | Admin interface |
| Frontend | 3000 | HTTP | Chat UI |
| Dashboard | 3001 | HTTP | Analytics UI |
| LightRAG | 9262 | HTTP | Knowledge base |
| PostgreSQL | 5432 | TCP | Database |
| Redis | 6379 | TCP | Cache |

## Service Dependencies

```
Bank Chatbot API
├── PostgreSQL (chatbot_db)
├── Redis
├── Fee Engine Service
├── Location Service
├── LightRAG Service
└── OpenAI API

Fee Engine Service
└── PostgreSQL (chatbot_db)

Location Service
└── PostgreSQL (chatbot_db)

Admin Panel
├── PostgreSQL (chatbot_db)
└── Location Service (integrated models)

Frontend
└── Bank Chatbot API

Dashboard
└── Bank Chatbot API
```

## Deployment

### Development
- Services run directly on host machine
- Use `start_all_services.ps1` to start all services
- Each service can be started independently

### Production (Docker)
- Services containerized using Docker
- Use `docker-compose.yml` files for orchestration
- Services communicate via Docker network or `host.docker.internal`

## Key Features

1. **Microservices Architecture**: Each service is independent and can be scaled/deployed separately
2. **Intelligent Routing**: Chat orchestrator routes queries to appropriate services
3. **Normalized Data**: Location service uses normalized database schema
4. **Deterministic Calculations**: Fee engine provides authoritative fee calculations
5. **Knowledge Base Integration**: LightRAG provides context from multiple knowledge bases
6. **Admin Interface**: Centralized admin panel for managing fees and locations

## API Contracts

### Fee Engine API
```json
POST /fees/calculate
{
  "as_of_date": "2026-01-01",
  "charge_type": "ISSUANCE_ANNUAL_PRIMARY",
  "card_category": "CREDIT",
  "card_network": "VISA",
  "card_product": "Platinum",
  "product_line": "CREDIT_CARDS",
  "currency": "BDT"
}
```

### Location Service API
```json
GET /locations?type=branch&city=Dhaka&limit=10
Response: {
  "total": 25,
  "locations": [
    {
      "id": "uuid",
      "type": "branch",
      "name": "Branch Name",
      "address": {
        "street": "Street Address",
        "city": "Dhaka",
        "region": "Dhaka",
        "zip_code": "1000"
      }
    }
  ]
}
```

## Monitoring & Health Checks

All services provide health check endpoints:
- `GET /health` - Basic health check
- `GET /api/health` - Detailed health status (Chatbot API)
- Health checks used by Docker for container orchestration

## Security

- Admin Panel uses HTTP Basic Authentication
- Services communicate over HTTP (HTTPS recommended for production)
- Database credentials stored in environment variables
- API keys stored securely in `.env` files

