# Retail Asset Charges Database

This module provides a normalized database schema and import script for retail asset/loan charges from the "Retail Asset Schedule of Charges.xlsx" file.

## Overview

The retail asset charges are stored in a separate normalized table `retail_asset_charge_master` that handles:
- Different loan products (Fast Cash, Fast Loan, Education Loan, Auto Loan, Home Loan, etc.)
- Various charge types (Processing Fee, Partial Payment Fee, Early Settlement Fee, etc.)
- Complex fee structures (tiered fees, percentage with min/max, fixed amounts)
- Employee pricing (usually free)
- Effective dates

## Schema

### Table: `retail_asset_charge_master`

**Key Columns:**
- `charge_id`: Primary key (UUID)
- `effective_from` / `effective_to`: Date range for charge validity
- `loan_product`: Normalized loan product enum (FAST_CASH_OD, FAST_LOAN_SECURED_EMI, etc.)
- `loan_product_name`: Original product name from Excel
- `charge_type`: Normalized charge type enum (PROCESSING_FEE, PARTIAL_PAYMENT_FEE, etc.)
- `charge_description`: Original charge description from Excel
- `fee_value`: Main fee value (percentage or fixed amount)
- `fee_unit`: BDT, USD, PERCENT, TEXT, or ACTUAL_COST
- `fee_basis`: PER_LOAN, PER_AMOUNT, PER_INSTALLMENT, etc.
- `tier_1_threshold`, `tier_1_fee_value`, `tier_1_max_fee`: First tier for tiered fees
- `tier_2_threshold`, `tier_2_fee_value`, `tier_2_max_fee`: Second tier for tiered fees
- `min_fee_value`, `max_fee_value`: Min/max constraints
- `condition_type`: NONE, WHICHEVER_HIGHER, TIERED, NOTE_BASED
- `condition_description`: Text describing conditions (e.g., "minimum 30% of outstanding must be paid")
- `employee_fee_value`, `employee_fee_description`: Employee pricing information
- `original_charge_text`: Original charge amount text from Excel for reference

## Setup

### 1. Create the Schema

```bash
# Connect to your PostgreSQL database
psql -U postgres -d chatbot_db

# Run the schema file
\i credit_card_rate/fee_engine/retail_asset_schema.sql
```

Or using Python:

```python
from sqlalchemy import create_engine, text
from fee_engine_service import get_database_url

engine = create_engine(get_database_url())
with open('retail_asset_schema.sql', 'r') as f:
    schema_sql = f.read()
    with engine.connect() as conn:
        for statement in schema_sql.split(';'):
            statement = statement.strip()
            if statement and not statement.startswith('--'):
                conn.execute(text(statement))
                conn.commit()
```

### 2. Import Data from Excel

Set environment variables for database connection:

```bash
# Windows PowerShell
$env:POSTGRES_HOST="localhost"
$env:POSTGRES_PORT="5432"
$env:POSTGRES_DB="chatbot_db"
$env:POSTGRES_USER="chatbot_user"
$env:POSTGRES_PASSWORD="chatbot_password_123"

# Or use FEE_ENGINE_DB_URL
$env:FEE_ENGINE_DB_URL="postgresql://chatbot_user:chatbot_password_123@localhost:5432/chatbot_db"
```

Then run the import script:

```bash
cd credit_card_rate/fee_engine
python import_retail_asset_charges.py
```

The script will:
1. Read the Excel file from `E:\Chatbot_refine\xls\Retail Asset Schedule of Charges.xlsx`
2. Parse complex charge amount strings
3. Normalize product names and charge types
4. Extract tiered fee structures, min/max values, and conditions
5. Insert normalized data into the database

## Data Normalization

### Product Name Mapping

| Excel Product Name | Normalized Enum |
|-------------------|-----------------|
| Fast Cash (Overdraft - OD) | FAST_CASH_OD |
| Fast Loan (Secured EMI Loan) | FAST_LOAN_SECURED_EMI |
| Edu Loan Secured / Edu Loan Unsecured | EDU_LOAN_SECURED |
| Other EMI Loans | OTHER_EMI_LOANS |
| Executive Loan / Assure / Women's Loan | EXECUTIVE_LOAN |
| Auto Loan / Two Wheeler Loan | AUTO_LOAN |
| Home Loan / Home Credit / Mortgage Loan | HOME_LOAN |
| Home Loan / Home Credit / Mortgage Loan Payment Protection | HOME_LOAN_PAYMENT_PROTECTION |
| Other Charges | OTHER_CHARGES |

### Charge Type Mapping

| Excel Description | Normalized Enum |
|-----------------|-----------------|
| Processing Fee | PROCESSING_FEE |
| Partial Payment Fee | PARTIAL_PAYMENT_FEE |
| Early Settlement Fee | EARLY_SETTLEMENT_FEE |
| Fast Cash Renewal Fee | RENEWAL_FEE |
| Penal Interest | PENAL_INTEREST |
| CIB Charge | CIB_CHARGE |
| CPV Charge | CPV_CHARGE |
| ... | ... |

### Fee Structure Parsing

The import script handles various fee formats:

1. **Tiered Fees**: 
   - "Up to Tk. 50 lakh – 0.575% or max Tk. 17,250; Above Tk. 50 lakh – 0.345% or max Tk. 23,000"
   - Parsed into `tier_1_*` and `tier_2_*` fields

2. **Percentage with Min/Max**:
   - "0.575% on reduced amount; Min Tk. 575, Max Tk. 5,750"
   - Parsed into `fee_value`, `min_fee_value`, `max_fee_value`

3. **Simple Percentage**:
   - "0.575% on loan amount"
   - Parsed into `fee_value` with `fee_unit = PERCENT`

4. **Fixed Amount**:
   - "Tk. 2,300"
   - Parsed into `fee_value` with `fee_unit = BDT`

5. **Special Cases**:
   - "Not applicable" → `fee_unit = TEXT`
   - "Actual expense basis" → `fee_unit = ACTUAL_COST`

## Querying the Data

### Example Queries

```sql
-- Get all processing fees for Fast Cash
SELECT 
    loan_product_name,
    charge_description,
    fee_value,
    fee_unit,
    original_charge_text
FROM retail_asset_charge_master
WHERE loan_product = 'FAST_CASH_OD'
  AND charge_type = 'PROCESSING_FEE'
  AND status = 'ACTIVE'
  AND effective_from <= CURRENT_DATE
  AND (effective_to IS NULL OR effective_to >= CURRENT_DATE);

-- Get tiered fees
SELECT 
    loan_product_name,
    charge_description,
    tier_1_threshold,
    tier_1_fee_value,
    tier_1_max_fee,
    tier_2_threshold,
    tier_2_fee_value,
    tier_2_max_fee
FROM retail_asset_charge_master
WHERE condition_type = 'TIERED'
  AND status = 'ACTIVE';

-- Get all charges for a specific product
SELECT 
    charge_type,
    charge_description,
    fee_value,
    fee_unit,
    min_fee_value,
    max_fee_value,
    condition_description,
    employee_fee_description
FROM retail_asset_charge_master
WHERE loan_product = 'HOME_LOAN'
  AND status = 'ACTIVE'
ORDER BY charge_type;
```

## Integration with Fee Engine

The retail asset charges table is separate from the card fee master table but follows a similar design pattern:
- Single master table design
- Effective date ranges
- Status-based filtering
- Priority-based rule selection
- Support for complex fee structures

This allows for consistent querying patterns across both card fees and retail asset charges.

## Maintenance

### Updating Charges

To update charges:
1. Update the Excel file
2. Re-run the import script (it will add new records)
3. Or manually update records in the database

### Deactivating Charges

Set `status = 'INACTIVE'` instead of deleting records:

```sql
UPDATE retail_asset_charge_master
SET status = 'INACTIVE', updated_at = CURRENT_TIMESTAMP
WHERE charge_id = '...';
```

## Notes

- The `original_charge_text` field preserves the exact text from Excel for reference
- Complex fee structures are normalized but original text is retained
- Employee fees are typically "Free" but stored for consistency
- Conditions (like "minimum 30% of outstanding") are extracted and stored in `condition_description`









