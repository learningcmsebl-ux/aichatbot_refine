# Fee Engine Setup Guide

## Quick Start

### 1. Database Setup

```bash
# Connect to PostgreSQL
psql -U postgres -d postgres

# Run schema
\i fee_engine/schema.sql

# Or from command line:
psql -U postgres -d postgres -f fee_engine/schema.sql
```

### 2. Install Dependencies

```bash
cd credit_card_rate
pip install -r requirements.txt
```

### 3. Migrate Data from CSV

The CSV file (`credit_card_rates.csv`) is already in the correct format. Import it:

```bash
# Set database URL
export FEE_ENGINE_DB_URL="postgresql://user:password@localhost:5432/dbname"
# Or use POSTGRES_* environment variables

# Run migration
python fee_engine/migrate_from_csv.py
```

### 4. Run Service

```bash
# Set environment variables
export FEE_ENGINE_DB_URL="postgresql://user:password@localhost:5432/dbname"
export FEE_ENGINE_PORT=8003

# Run service
python fee_engine/run_service.py
```

Or using uvicorn directly:

```bash
uvicorn fee_engine.fee_engine_service:app --host 0.0.0.0 --port 8003
```

### 5. Verify Service

```bash
# Health check
curl http://localhost:8003/health

# Test fee calculation
curl -X POST http://localhost:8003/fees/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "as_of_date": "2026-02-15",
    "charge_type": "ISSUANCE_ANNUAL_PRIMARY",
    "card_category": "DEBIT",
    "card_network": "MASTERCARD",
    "card_product": "World RFCD",
    "currency": "USD"
  }'
```

## CSV Format

The CSV file (`credit_card_rates.csv`) should have the following columns:

- `fee_id`: Unique identifier (optional, auto-generated if missing)
- `effective_from`: Date in format `M/D/YYYY` or `YYYY-MM-DD`
- `effective_to`: Date or empty (NULL = no expiry)
- `charge_type`: Standardized charge type (e.g., `ISSUANCE_ANNUAL_PRIMARY`)
- `card_category`: `CREDIT`, `DEBIT`, `PREPAID`, or `ANY`
- `card_network`: `VISA`, `MASTERCARD`, `DINERS`, `UNIONPAY`, `FX`, `TAKAPAY`, or `ANY`
- `card_product`: Product name (e.g., `Classic`, `Platinum`, `World RFCD`) or `ANY`
- `full_card_name`: Display name (optional)
- `fee_value`: Fee amount (decimal)
- `fee_unit`: `BDT`, `USD`, `PERCENT`, `COUNT`, or `TEXT`
- `fee_basis`: `PER_TXN`, `PER_YEAR`, `PER_MONTH`, `PER_VISIT`, or `ON_OUTSTANDING`
- `min_fee_value`: Minimum fee for "whichever higher" (optional)
- `min_fee_unit`: Unit for minimum fee (optional)
- `free_entitlement_count`: Number of free items (optional)
- `condition_type`: `NONE`, `WHICHEVER_HIGHER`, `FREE_UPTO_N`, or `NOTE_BASED`
- `note_reference`: Note number if `condition_type` is `NOTE_BASED` (optional)
- `priority`: Priority (higher wins, default: 100)
- `status`: `ACTIVE` or `INACTIVE`
- `remarks`: Additional notes (optional)

## Integration with Chatbot

The chatbot has been updated to use the fee-engine service. See `INTEGRATION.md` for details.

## Troubleshooting

### Service not starting

- Check database connection: `FEE_ENGINE_DB_URL` or `POSTGRES_*` environment variables
- Verify PostgreSQL is running
- Check if schema has been created

### No results from fee calculation

- Verify data has been migrated: `SELECT COUNT(*) FROM card_fee_master;`
- Check charge type matches exactly (case-sensitive)
- Verify card attributes match (category, network, product)
- Check effective dates are correct

### CSV import errors

- Verify CSV file exists: `credit_card_rates.csv`
- Check CSV format matches expected columns
- Review error messages for specific row issues
