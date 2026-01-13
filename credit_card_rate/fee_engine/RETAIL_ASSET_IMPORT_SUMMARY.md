# Retail Asset Charges - Import Summary

## ✅ What Has Been Created

### 1. Database Schema (`retail_asset_schema.sql`)
- Normalized table: `retail_asset_charge_master`
- Supports:
  - Multiple loan products (Fast Cash, Fast Loan, Education Loan, Auto Loan, Home Loan, etc.)
  - Various charge types (Processing Fee, Partial Payment, Early Settlement, etc.)
  - Complex fee structures:
    - Tiered fees (e.g., "Up to 50 lakh: 0.575% or max 17,250; Above 50 lakh: 0.345% or max 23,000")
    - Percentage with min/max (e.g., "0.575%; Min 575, Max 5,750")
    - Fixed amounts (e.g., "Tk. 2,300")
    - Percentage-based (e.g., "0.575% on loan amount")
    - Special cases ("Not applicable", "Actual expense basis")
  - Employee pricing (usually "Free")
  - Effective dates
  - Conditions (e.g., "minimum 30% of outstanding must be paid", "after 6 months")

### 2. Import Script (`import_retail_asset_charges.py`)
- Reads Excel file: `E:\Chatbot_refine\xls\Retail Asset Schedule of Charges.xlsx`
- Parses complex charge amount strings
- Normalizes product names and charge types
- Extracts structured data from free-form text
- Inserts normalized data into database

### 3. Documentation
- `RETAIL_ASSET_CHARGES_README.md` - Complete documentation
- This summary file

## 📊 Data Structure

### Products Supported
- Fast Cash (Overdraft - OD)
- Fast Loan (Secured EMI Loan)
- Education Loan (Secured/Unsecured)
- Other EMI Loans
- Executive Loan / Assure / Women's Loan
- Auto Loan / Two Wheeler Loan
- Home Loan / Home Credit / Mortgage Loan
- Home Loan Payment Protection
- Other Charges

### Charge Types Supported
- Processing Fee
- Limit Enhancement Fee
- Limit Reduction Fee
- Limit Cancellation Fee
- Renewal Fee
- Partial Payment Fee
- Early Settlement Fee
- Security Lien Confirmation
- Quotation Change Fee
- Notarization Fee
- NOC Fee
- Penal Interest
- CIB Charge
- CPV Charge
- Vetting & Valuation Charge
- Security Replacement Fee
- Stamp Charge
- Loan Outstanding Certificate Fee
- Reschedule & Restructure Fee
- And more...

## 🚀 Next Steps

### 1. Create the Schema

```bash
# Option 1: Using psql
psql -U chatbot_user -d chatbot_db -f credit_card_rate/fee_engine/retail_asset_schema.sql

# Option 2: Using Python (with proper DB credentials)
cd credit_card_rate/fee_engine
python -c "
from sqlalchemy import create_engine, text
from fee_engine_service import get_database_url
engine = create_engine(get_database_url())
with open('retail_asset_schema.sql', 'r', encoding='utf-8') as f:
    schema_sql = f.read()
    with engine.connect() as conn:
        for statement in schema_sql.split(';'):
            statement = statement.strip()
            if statement and not statement.startswith('--'):
                try:
                    conn.execute(text(statement))
                    conn.commit()
                except Exception as e:
                    if 'already exists' not in str(e).lower():
                        print(f'Warning: {e}')
"
```

### 2. Set Database Credentials

Set environment variables:

```bash
# Windows PowerShell
$env:POSTGRES_HOST="localhost"
$env:POSTGRES_PORT="5432"
$env:POSTGRES_DB="chatbot_db"
$env:POSTGRES_USER="chatbot_user"
$env:POSTGRES_PASSWORD="chatbot_password_123"

# Or use direct URL
$env:FEE_ENGINE_DB_URL="postgresql://chatbot_user:chatbot_password_123@localhost:5432/chatbot_db"
```

### 3. Run the Import

```bash
cd credit_card_rate/fee_engine
python import_retail_asset_charges.py
```

Expected output:
```
Reading Excel file: E:\Chatbot_refine\xls\Retail Asset Schedule of Charges.xlsx
Found 38 rows to import

Inserting 38 records...
✓ Successfully imported 38 records

Import Summary:
--------------------------------------------------
  FAST_CASH_OD: X charges
  FAST_LOAN_SECURED_EMI: X charges
  ...
```

## 📋 Schema Features

### Normalized Design
- Single master table (similar to `card_fee_master`)
- Enum types for product and charge type consistency
- Supports complex fee structures with tiered pricing
- Preserves original text for reference

### Key Fields
- **Tiered Fees**: `tier_1_*` and `tier_2_*` fields for "Up to X amount" scenarios
- **Min/Max**: `min_fee_value`, `max_fee_value` for percentage-based fees with constraints
- **Conditions**: `condition_description` for special rules (e.g., "minimum 30% must be paid")
- **Employee Pricing**: Separate fields for employee fee information
- **Original Text**: `original_charge_text` preserves exact Excel text

## 🔍 Example Queries

```sql
-- Get all processing fees
SELECT loan_product_name, charge_description, fee_value, fee_unit, original_charge_text
FROM retail_asset_charge_master
WHERE charge_type = 'PROCESSING_FEE' AND status = 'ACTIVE';

-- Get tiered fees
SELECT loan_product_name, tier_1_threshold, tier_1_fee_value, tier_1_max_fee,
       tier_2_threshold, tier_2_fee_value, tier_2_max_fee
FROM retail_asset_charge_master
WHERE condition_type = 'TIERED' AND status = 'ACTIVE';

-- Get charges for a specific product
SELECT charge_type, charge_description, fee_value, fee_unit, 
       min_fee_value, max_fee_value, condition_description
FROM retail_asset_charge_master
WHERE loan_product = 'HOME_LOAN' AND status = 'ACTIVE';
```

## 📝 Notes

- The import script handles various fee formats automatically
- Original text is preserved in `original_charge_text` for reference
- Employee fees are typically "Free" but stored for consistency
- Complex conditions are extracted and stored in `condition_description`
- The schema follows the same design pattern as `card_fee_master` for consistency

## ✅ Status

- [x] Schema created
- [x] Import script created
- [x] Documentation created
- [ ] Schema deployed to database (requires DB credentials)
- [ ] Data imported (requires DB credentials and Excel file)

---

**Files Created:**
1. `retail_asset_schema.sql` - Database schema
2. `import_retail_asset_charges.py` - Import script
3. `RETAIL_ASSET_CHARGES_README.md` - Full documentation
4. `RETAIL_ASSET_IMPORT_SUMMARY.md` - This summary









