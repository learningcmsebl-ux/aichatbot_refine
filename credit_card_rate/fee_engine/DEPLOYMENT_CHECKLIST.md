# Fee Engine Deployment Checklist

## Issue: Chatbot returning incorrect fee (USD 50 instead of USD 11.5)

The chatbot is currently returning "USD 50" for "Mastercard World RFCD Debit annual fee" but the correct fee from the CSV is **USD 11.5**.

## Root Cause Analysis

1. **CSV Data**: ✅ The CSV file (`credit_card_rates.csv`) has the correct entry:
   - Line 8: `26,1/1/2026,,ISSUANCE_ANNUAL_PRIMARY,DEBIT,MASTERCARD,World RFCD,Debit Card Global/Master Card World RFCD,11.5,USD,PER_YEAR`

2. **Chatbot Integration**: ✅ The chatbot code has been updated to use fee-engine service

3. **Likely Issues**:
   - Fee-engine service is not running (port 8003)
   - Data has not been imported from CSV to database
   - Fee-engine service is running but chatbot can't connect to it
   - Fallback to old card_rates_service is being used (which may have incorrect data)

## Deployment Steps

### Step 1: Setup Database Schema

```bash
# Connect to PostgreSQL
psql -U postgres -d postgres

# Run schema
\i credit_card_rate/fee_engine/schema.sql

# Or from command line:
psql -U postgres -d postgres -f credit_card_rate/fee_engine/schema.sql
```

### Step 2: Import Data from CSV

```bash
cd credit_card_rate

# Set database URL
export FEE_ENGINE_DB_URL="postgresql://postgres:password@localhost:5432/postgres"
# Or use POSTGRES_* environment variables

# Run migration
python fee_engine/migrate_from_csv.py
```

**Expected Output:**
```
Found 35 records to migrate
Imported 26 records...
Imported 26 records...

Migration complete!
Imported: 26 records
Skipped: 0 records
```

### Step 3: Verify Data Import

```bash
# Connect to PostgreSQL
psql -U postgres -d postgres

# Check if data exists
SELECT COUNT(*) FROM card_fee_master;
-- Should return 26 or more

# Check for World RFCD Debit card
SELECT * FROM card_fee_master 
WHERE card_category = 'DEBIT' 
  AND card_network = 'MASTERCARD' 
  AND card_product LIKE '%RFCD%';
-- Should return at least 1 row with fee_value = 11.5 and fee_unit = 'USD'
```

### Step 4: Start Fee-Engine Service

```bash
cd credit_card_rate

# Set environment variables
export FEE_ENGINE_DB_URL="postgresql://postgres:password@localhost:5432/postgres"
export FEE_ENGINE_PORT=8003

# Run service
python fee_engine/run_service.py
```

**Expected Output:**
```
Starting Fee Engine Service on 0.0.0.0:8003
Database: postgresql://...
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8003
```

### Step 5: Test Fee-Engine Service

```bash
# Health check
curl http://localhost:8003/health

# Test fee calculation for World RFCD Debit
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

**Expected Response:**
```json
{
  "status": "CALCULATED",
  "fee_amount": 11.5,
  "fee_currency": "USD",
  "fee_basis": "PER_YEAR",
  "rule_id": "...",
  "remarks": null
}
```

### Step 6: Update Chatbot Configuration

Add to `bank_chatbot/.env`:

```bash
FEE_ENGINE_URL=http://localhost:8003
```

Or if fee-engine is on a different host:

```bash
FEE_ENGINE_URL=http://host.docker.internal:8003
```

### Step 7: Rebuild Chatbot

```bash
cd bank_chatbot
docker-compose up -d --build chatbot
```

### Step 8: Test Chatbot Query

Query: "Mastercard World RFCD Debit annual fee"

**Expected Response:**
- Should call fee-engine service
- Should return: "The annual fee is USD 11.5 (per year)."

## Troubleshooting

### Issue: Fee-engine service not starting

**Check:**
- Database connection string is correct
- PostgreSQL is running
- Schema has been created
- Port 8003 is not already in use

**Solution:**
```bash
# Check if port is in use
netstat -an | findstr :8003

# Check PostgreSQL connection
psql -U postgres -d postgres -c "SELECT 1;"
```

### Issue: Data not imported

**Check:**
- CSV file exists: `credit_card_rate/credit_card_rates.csv`
- CSV file has correct format
- Database connection works
- Migration script runs without errors

**Solution:**
```bash
# Re-run migration
python credit_card_rate/fee_engine/migrate_from_csv.py

# Check imported data
psql -U postgres -d postgres -c "SELECT COUNT(*) FROM card_fee_master;"
```

### Issue: Chatbot still using old service

**Check:**
- Fee-engine service is running on port 8003
- `FEE_ENGINE_URL` is set in chatbot config
- Chatbot logs show fee-engine calls

**Solution:**
```bash
# Check chatbot logs
docker logs bank-chatbot-api | grep FEE_ENGINE

# Should see:
# [FEE_ENGINE] Calling http://localhost:8003/fees/calculate with: ...
# [FEE_ENGINE] Fee calculation result: ...
```

### Issue: Fee-engine returns "NO_RULE_FOUND"

**Check:**
- Card product name matches exactly (case-sensitive)
- Charge type matches exactly
- Card attributes match

**Solution:**
```bash
# Check what's in database
psql -U postgres -d postgres -c "
SELECT charge_type, card_category, card_network, card_product, fee_value, fee_unit 
FROM card_fee_master 
WHERE card_category = 'DEBIT' AND card_network = 'MASTERCARD';
"

# Try different product variations:
# - "World RFCD"
# - "Global/Mastercard World RFCD"
# - "Global/Master Card World RFCD"
```

## Verification

After deployment, verify:

1. ✅ Fee-engine service is running on port 8003
2. ✅ Data imported (26+ records in `card_fee_master` table)
3. ✅ World RFCD Debit entry exists with fee_value = 11.5, fee_unit = USD
4. ✅ Fee-engine API returns correct fee for test query
5. ✅ Chatbot configuration has `FEE_ENGINE_URL` set
6. ✅ Chatbot logs show fee-engine calls (not fallback to old service)
7. ✅ Query "Mastercard World RFCD Debit annual fee" returns USD 11.5

## Current Status

- ✅ CSV file has correct entry (USD 11.5)
- ✅ Chatbot code updated to use fee-engine
- ⚠️ Fee-engine service needs to be deployed and running
- ⚠️ Data needs to be imported from CSV to database
- ⚠️ Chatbot needs to be configured with `FEE_ENGINE_URL`
