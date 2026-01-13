# Fee Engine Microservice

Bank-grade, deterministic fee calculation microservice using a single master table design.

**Effective from: 01st January, 2026**

## Overview

The Fee Engine is a microservice that calculates applicable fees for any card-related event using a single master fee table (`card_fee_master`). It supports:

- Credit / Debit / Prepaid cards
- VISA / Mastercard / Diners / UnionPay / FX / TakaPay
- Fixed, percentage, mixed, count-based fees
- "Whichever higher" logic
- Free entitlements (e.g., supplementary cards, lounge visits)
- Note-based rules (returns structured dependency, no guessing)

## Architecture

### Single Master Table Design

All fee rules are stored in one table: `card_fee_master`

**Key Features:**
- Single source of truth
- No complex joins required
- Fast lookups with proper indexing
- Easy to maintain and audit

### Database Schema

See `schema.sql` for the complete database schema.

**Key Columns:**
- `fee_id`: Primary key (UUID)
- `effective_from` / `effective_to`: Date range for fee validity
- `charge_type`: Logical fee group (e.g., `CASH_WITHDRAWAL_EBL_ATM`)
- `card_category`: CREDIT / DEBIT / PREPAID / ANY
- `card_network`: VISA / MASTERCARD / etc. / ANY
- `card_product`: Classic / Gold / Platinum / etc. / ANY
- `fee_value`: Main fee value
- `fee_unit`: BDT / USD / PERCENT / COUNT / TEXT
- `fee_basis`: PER_TXN / PER_YEAR / PER_MONTH / PER_VISIT / ON_OUTSTANDING
- `condition_type`: NONE / WHICHEVER_HIGHER / FREE_UPTO_N / NOTE_BASED
- `priority`: Higher priority wins when multiple rules match

## Setup

### 1. Database Setup

```bash
# Create database and run schema
psql -U postgres -d postgres -f fee_engine/schema.sql
```

### 2. Install Dependencies

```bash
cd credit_card_rate
pip install -r requirements.txt
```

### 3. Migrate Data

```bash
# Import data from card_charges.json
python fee_engine/migrate_data.py
```

### 4. Run Service

```bash
# Set environment variables
export FEE_ENGINE_DB_URL="postgresql://user:password@localhost:5432/dbname"
export FEE_ENGINE_PORT=8003

# Run service
python fee_engine/fee_engine_service.py
```

Or using uvicorn:

```bash
uvicorn fee_engine.fee_engine_service:app --host 0.0.0.0 --port 8003
```

## API Endpoints

### POST /fees/calculate

Calculate applicable fee for a card-related event.

**Request:**
```json
{
  "as_of_date": "2026-02-15",
  "charge_type": "CASH_WITHDRAWAL_EBL_ATM",
  "card_category": "CREDIT",
  "card_network": "VISA",
  "card_product": "Platinum",
  "amount": 20000,
  "currency": "BDT",
  "usage_index": 3
}
```

**Success Response:**
```json
{
  "status": "CALCULATED",
  "fee_amount": 345,
  "fee_currency": "BDT",
  "fee_basis": "PER_TXN",
  "rule_id": "b8f3-9c21",
  "remarks": "Whichever higher applied"
}
```

**Note-based Response:**
```json
{
  "status": "REQUIRES_NOTE_RESOLUTION",
  "note_reference": "Note 12",
  "message": "Fee depends on external note definition"
}
```

### GET /fees/rules

List fee rules with optional filters.

**Query Parameters:**
- `charge_type`: Filter by charge type
- `card_category`: Filter by card category
- `card_network`: Filter by card network
- `limit`: Maximum number of results (default: 100, max: 1000)

### GET /health

Health check endpoint.

## Fee Calculation Logic

### 1. Rule Selection

Matches rows where:
- `effective_from ≤ as_of_date < effective_to` (or `effective_to` is NULL)
- `charge_type` matches
- Card attributes match or are `ANY`
- `status = ACTIVE`
- Highest `priority` wins

### 2. "Whichever Higher" Logic

If:
- `condition_type = WHICHEVER_HIGHER`
- `fee_unit = PERCENT`
- `min_fee_value` is set

Then:
```
percent_fee = amount × fee_value / 100
fixed_fee = min_fee_value
final_fee = max(percent_fee, fixed_fee)
```

Used for ATM withdrawals, EasyCredit, etc.

### 3. Free Entitlement Logic

If:
- `condition_type = FREE_UPTO_N`
- `free_entitlement_count = N`

Then:
- If `usage_index ≤ N` → fee = 0
- Else → apply next matching rule

Used for:
- Supplementary cards (1st card free)
- Lounge visits (2 free visits per year)

### 4. Mixed Currency Logic

If both BDT and USD rows exist:
- Select row matching `request.currency`
- If none → return `FX_RATE_REQUIRED`

### 5. Note-based Logic

If:
- `condition_type = NOTE_BASED`

Then:
```json
{
  "status": "REQUIRES_NOTE_RESOLUTION",
  "note_reference": "Note 12"
}
```

The engine never guesses. This matches the schedule's "According to Note X" entries.

## Charge Type Catalog

Standardized charge types (from schedule):

- `ISSUANCE_ANNUAL_PRIMARY`
- `SUPPLEMENTARY_ANNUAL`
- `SUPPLEMENTARY_FREE_ENTITLEMENT`
- `CARD_REPLACEMENT`
- `PIN_REPLACEMENT`
- `LATE_PAYMENT`
- `CASH_WITHDRAWAL_EBL_ATM`
- `CASH_WITHDRAWAL_OTHER_ATM`
- `ATM_RECEIPT_EBL`
- `GLOBAL_LOUNGE_ACCESS_FEE`
- `GLOBAL_LOUNGE_FREE_VISITS_ANNUAL`
- `SKYLOUNGE_FREE_VISITS_INTL_ANNUAL`
- `SKYLOUNGE_FREE_VISITS_DOM_ANNUAL`
- `OVERLIMIT`
- `DUPLICATE_ESTATEMENT`
- `SALES_VOUCHER_RETRIEVAL`
- `CERTIFICATE_FEE`
- `RISK_ASSURANCE_FEE`
- `CARD_CHEQUBOOK`
- `CARD_CHEQUE_PROCESSING`
- `CUSTOMER_VERIFICATION_CIB`
- `TRANSACTION_ALERT_ANNUAL`
- `INTEREST_RATE`

## Integration with Chatbot

The chatbot should call this service for card fee calculations:

```python
# Example integration
async def get_card_fee(charge_type, card_category, card_network, card_product, amount=None):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8003/fees/calculate",
            json={
                "as_of_date": "2026-02-15",
                "charge_type": charge_type,
                "card_category": card_category,
                "card_network": card_network,
                "card_product": card_product,
                "amount": amount,
                "currency": "BDT"
            }
        )
        return response.json()
```

## Environment Variables

- `FEE_ENGINE_DB_URL`: PostgreSQL connection string
- `FEE_ENGINE_PORT`: Service port (default: 8003)
- `POSTGRES_USER`: PostgreSQL user (fallback)
- `POSTGRES_PASSWORD`: PostgreSQL password (fallback)
- `POSTGRES_HOST`: PostgreSQL host (fallback)
- `POSTGRES_PORT`: PostgreSQL port (fallback)
- `POSTGRES_DB`: PostgreSQL database (fallback)

## Testing

```bash
# Test fee calculation
curl -X POST http://localhost:8003/fees/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "as_of_date": "2026-02-15",
    "charge_type": "ISSUANCE_ANNUAL_PRIMARY",
    "card_category": "CREDIT",
    "card_network": "VISA",
    "card_product": "Platinum",
    "currency": "BDT"
  }'
```

## Notes

- The service is deterministic - same inputs always produce same outputs
- No guessing - note-based rules return structured responses
- Bank-grade - designed for production use
- Single source of truth - all fees in one table
- Easy to maintain - simple schema, clear logic
