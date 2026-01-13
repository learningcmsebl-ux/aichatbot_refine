# Fee Engine Directory Structure

## Overview

The Fee Engine is a microservice that calculates fees for multiple product lines using a master table design. This document outlines the directory structure and file organization.

## Directory Tree

```
fee_engine/
├── Core Service Files
│   ├── fee_engine_service.py          # Main FastAPI service with ORM models and API endpoints
│   ├── run_service.py                 # Service entry point/runner script
│   └── __init__.py                    # Package initialization
│
├── Database Schema Files
│   ├── schema.sql                     # Main card_fee_master table schema
│   ├── schema_extension.sql           # Schema extensions (enums, functions)
│   ├── schema_retail_asset_v2.sql     # Retail asset v2 table schema
│   ├── retail_asset_schema.sql        # Legacy retail asset v1 schema
│   ├── schema_charge_context_migration.sql  # Migration script for charge_context
│   ├── skybanking_schema.sql          # Skybanking fee table schema
│   └── lockdown_v1_and_add_constraints.sql  # V1 lockdown and v2 constraints
│
├── Data Migration Scripts
│   ├── migrate_data.py                # Legacy migration from JSON
│   ├── migrate_from_csv.py            # CSV import migration
│   ├── migrate_retail_asset_to_v2.py  # V1 to V2 retail asset migration
│   ├── import_credit_cards.py         # Credit card fee import
│   ├── import_retail_assets.py        # Retail asset fee import (v1)
│   ├── import_retail_asset_charges.py # Retail asset charge import helper
│   ├── import_skybanking.py           # Skybanking fee import
│   ├── import_skybanking_fees.py      # Skybanking fee import (alternative)
│   ├── import_priority_banking.py     # Priority banking fee import
│   └── import_all_product_lines.py    # Batch import all product lines
│
├── Database Setup Scripts
│   ├── deploy_fee_engine.py           # Full deployment script (schema + data)
│   ├── create_retail_asset_schema.py  # Create retail asset v1 schema
│   ├── create_retail_schema_complete.py  # Create complete retail schema
│   ├── create_v2_schema.py            # Create retail asset v2 schema
│   ├── create_table_only.py           # Create tables only (no data)
│   ├── setup_retail_schema.py         # Setup retail schema helper
│   ├── add_enum_values.py             # Add enum values to existing enums
│   ├── fix_column_sizes.py            # Fix column size issues
│   ├── fix_column_sizes.sql           # SQL for column size fixes
│   └── update_network_column.py       # Update network column values
│
├── Verification & Testing Scripts
│   ├── verify_v2_migration.py         # Verify v2 migration integrity
│   ├── smoke_test_v2.py               # Production smoke tests for v2
│   ├── test_fast_cash_queries.py      # Fast cash query tests
│   ├── check_fast_cash_reduction.py   # Check fast cash reduction fees
│   └── audit_fast_cash_charges.py     # Audit fast cash charges
│
├── Utility Scripts
│   ├── export_fees_to_csv.py          # Export fees to CSV
│   ├── apply_guardrails.py            # Apply database constraints/guardrails
│   └── card_fee_master_export.csv     # Exported CSV data
│
├── Admin Panel (admin_panel/)
│   ├── admin_api.py                   # Admin API endpoints (CRUD operations)
│   ├── Dockerfile                     # Admin panel Docker configuration
│   ├── requirements.txt               # Admin panel dependencies
│   ├── static/                        # Admin UI frontend
│   │   ├── index.html                 # Main admin dashboard HTML
│   │   ├── script.js                  # Admin panel JavaScript
│   │   └── styles.css                 # Admin panel styles
│   ├── add_firewall_rule.bat          # Windows firewall rule script
│   ├── add_firewall_rule.ps1          # PowerShell firewall rule script
│   └── __init__.py                    # Package initialization
│
└── Documentation
    ├── README.md                      # Main README (overview, setup, API)
    ├── FEE_ENGINE_ARCHITECTURE_AND_API.md  # Comprehensive architecture doc
    ├── SETUP.md                       # Setup guide
    ├── INTEGRATION.md                 # Integration guide
    ├── DEPLOYMENT_CHECKLIST.md        # Deployment checklist
    ├── DOCKER_DEPLOYMENT.md           # Docker deployment guide
    ├── DOCKER_STATUS.md               # Docker status documentation
    ├── QUICK_START_IMPORT.md          # Quick start import guide
    ├── RETAIL_ASSET_CHARGES_README.md # Retail asset charges documentation
    ├── RETAIL_ASSET_IMPORT_SUMMARY.md # Retail asset import summary
    ├── RETAIL_ASSET_CHARGE_TYPE_INVARIANT.md  # Data model invariants
    ├── admin_panel/
    │   ├── README.md                  # Admin panel README
    │   ├── ADMIN_PANEL_SUMMARY.md     # Admin panel summary
    │   ├── IMPLEMENTATION_SUMMARY.md  # Implementation details
    │   ├── DEPLOYMENT.md              # Admin panel deployment guide
    │   ├── FIREWALL_SETUP.md          # Firewall setup guide
    │   └── RETAIL_ASSET_CHARGES_FEATURE.md  # Retail asset feature docs
    └── STRUCTURE.md                   # This file
```

## Core Components

### 1. Main Service (`fee_engine_service.py`)

The heart of the fee engine microservice:

- **ORM Models**: SQLAlchemy models for all product line tables
  - `CardFeeMaster` (card_fee_master)
  - `RetailAssetChargeMaster` (retail_asset_charge_master_v2)
  - `SkybankingFeeMaster` (skybanking_fee_master)

- **API Endpoints**:
  - `POST /fees/calculate` - Calculate fee for card events
  - `POST /fees/query` - Query fees (with disambiguation support)
  - `GET /fees/rules` - List fee rules
  - `GET /health` - Health check

- **Core Logic**:
  - Rule matching algorithm
  - Fee calculation (whichever higher, free entitlements, tiered fees)
  - Disambiguation logic (product/context selection)
  - Date range filtering

### 2. Database Schema Files

- **schema.sql**: Main schema for `card_fee_master` table
- **schema_retail_asset_v2.sql**: Retail asset v2 schema (includes `charge_context`)
- **schema_extension.sql**: Enum types, functions, extensions
- **skybanking_schema.sql**: Skybanking fee table schema

### 3. Data Migration Scripts

Scripts organized by product line:

- **Card Fees**: `import_credit_cards.py`, `migrate_data.py`, `migrate_from_csv.py`
- **Retail Assets**: `import_retail_assets.py`, `migrate_retail_asset_to_v2.py`
- **Skybanking**: `import_skybanking.py`, `import_skybanking_fees.py`
- **Priority Banking**: `import_priority_banking.py`
- **Batch**: `import_all_product_lines.py`

### 4. Admin Panel

Located in `admin_panel/` directory:

- **Backend**: `admin_api.py` (FastAPI CRUD endpoints)
- **Frontend**: `static/` (HTML, CSS, JavaScript)
- **Features**:
  - Create, Read, Update, Delete operations
  - Filtering and search
  - CSV export
  - Bulk operations
  - Audit trails

### 5. Testing & Verification Scripts

- **Migration Verification**: `verify_v2_migration.py`
- **Smoke Tests**: `smoke_test_v2.py`
- **Product-Specific Tests**: `test_fast_cash_queries.py`, `audit_fast_cash_charges.py`

## Database Tables

### Product Line Tables

1. **card_fee_master**
   - Credit/Debit/Prepaid card fees
   - Filtered by: `charge_type`, `card_category`, `card_network`, `card_product`
   - Effective date ranges

2. **retail_asset_charge_master_v2** (current)
   - Loan and retail asset charges
   - Filtered by: `loan_product`, `charge_type`, `charge_context`, effective dates
   - Supports tiered fees, employee/category fees

3. **retail_asset_charge_master** (v1, deprecated/locked)
   - Legacy table (no longer writable)

4. **skybanking_fee_master**
   - Skybanking service fees
   - Filtered by: `service_type`, `charge_type`, effective dates

## API Structure

### Fee Calculation Flow

```
Request → fee_engine_service.py
         ↓
    Detect product line
         ↓
    Select appropriate table
         ↓
    Apply filters (charge_type, context, dates)
         ↓
    Match rules (priority-based)
         ↓
    Calculate fee (apply conditions)
         ↓
    Return response
```

### Disambiguation Flow

```
Query Request → Multiple matches found
              ↓
         Store options in Redis
              ↓
         Return NEEDS_DISAMBIGUATION
              ↓
         User selects option
              ↓
         Retrieve stored options
              ↓
         Query with selected parameters
              ↓
         Return fee result
```

## Environment Variables

- `FEE_ENGINE_DB_URL`: Database connection URL (primary)
- `POSTGRES_DB_URL`: Alternative database URL
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`: Individual DB settings
- `FEE_ENGINE_PORT`: Service port (default: 8003)

## Deployment Structure

### Docker Services

1. **fee-engine**: Main fee engine service (port 8003)
2. **fee-engine-admin**: Admin panel service (port 8004)

### File Organization Principles

1. **Separation of Concerns**:
   - Schema files separate from application code
   - Migration scripts separate from setup scripts
   - Testing scripts separate from production code

2. **Product Line Organization**:
   - Each product line has dedicated import scripts
   - Shared utilities for common operations

3. **Version Management**:
   - v1 and v2 schemas clearly separated
   - Migration scripts documented

4. **Documentation**:
   - Comprehensive markdown files
   - Architecture and API documentation
   - Setup and deployment guides

## Key Files Reference

| File | Purpose |
|------|---------|
| `fee_engine_service.py` | Main service (API + ORM) |
| `schema.sql` | Card fee master table schema |
| `schema_retail_asset_v2.sql` | Retail asset v2 table schema |
| `migrate_retail_asset_to_v2.py` | V1 to V2 migration |
| `verify_v2_migration.py` | Migration verification queries |
| `admin_panel/admin_api.py` | Admin CRUD API |
| `FEE_ENGINE_ARCHITECTURE_AND_API.md` | Complete architecture documentation |

## Adding New Features

### Adding a New Product Line

1. Create schema file: `schema_<product>_fee_master.sql`
2. Create ORM model in `fee_engine_service.py`
3. Create import script: `import_<product>.py`
4. Add API endpoint in `fee_engine_service.py`
5. Update documentation

### Adding a New Fee Type

1. Add to appropriate schema (if new fields needed)
2. Update ORM model
3. Update import scripts
4. Update API validation
5. Update documentation

## Maintenance Notes

- **Schema Changes**: Always version schema files
- **Migrations**: Test on staging before production
- **Data Integrity**: Use verification scripts after migrations
- **Constraints**: Use `apply_guardrails.py` for production constraints
- **Lockdown**: Lock down deprecated tables using `lockdown_v1_and_add_constraints.sql`
