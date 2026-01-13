# Skybanking Certificate Fees Integration Guide

## Overview
This guide explains how to integrate Skybanking certificate fees from the Excel file into the fee dashboard admin panel.

## Files Created/Modified

### 1. Database Schema
- **File**: `credit_card_rate/fee_engine/skybanking_schema.sql`
- **Purpose**: Creates the `skybanking_fee_master` table to store Skybanking fees

### 2. Import Script
- **File**: `credit_card_rate/fee_engine/import_skybanking_fees.py`
- **Purpose**: Normalizes and imports Excel data into the database

### 3. Admin API Updates
- **File**: `credit_card_rate/fee_engine/admin_panel/admin_api.py`
- **Changes**: 
  - Added `SkybankingFeeMaster` model
  - Added API endpoints for CRUD operations

### 4. Admin Panel UI Updates
- **File**: `credit_card_rate/fee_engine/admin_panel/static/index.html`
- **Changes**: Add new tab for Skybanking fees

- **File**: `credit_card_rate/fee_engine/admin_panel/static/script.js`
- **Changes**: Add JavaScript functions for Skybanking tab

## Setup Steps

### Step 1: Create Database Table
```bash
cd credit_card_rate/fee_engine
psql -U chatbot_user -d chatbot_db -f skybanking_schema.sql
```

### Step 2: Import Data from Excel
```bash
cd credit_card_rate/fee_engine
python import_skybanking_fees.py
```

### Step 3: Add API Endpoints
The API endpoints need to be added to `admin_api.py`. See the next section.

### Step 4: Update Admin Panel UI
Add the new tab and JavaScript functions (see implementation details below).

## Data Structure

The Excel file contains:
- **15 rows** of fee data
- **Columns**: FEE ID, EFFECTIVE FROM, EFFECTIVE TO, CHARGE TYPE, NETWORK, PRODUCT, PRODUCT NAME, FEE AMOUNT, FEE UNIT, FEE BASIS, STATUS, CONDITIONAL, CONDITION DESCRIPTION

### Normalized Structure:
- `charge_type`: Type of charge (e.g., "Certificate Fee", "Fund Transfer")
- `product`: Always "Skybanking"
- `product_name`: Service name (e.g., "Account Certificate", "Binimoy Fund Transfer")
- `fee_amount`: Can be NULL for "Variable" or "Free"
- `fee_unit`: "BDT" or "PERCENTAGE"
- `fee_basis`: "PER_YEAR", "PER_REQUEST", or "PER_TRANSACTION"
- `is_conditional`: Boolean indicating if fee has conditions
- `condition_description`: Text describing conditions

## Next Steps

1. ✅ Database schema created
2. ✅ Import script created
3. ⏳ Add API endpoints to admin_api.py
4. ⏳ Add tab to HTML
5. ⏳ Add JavaScript functions
6. ⏳ Test the integration

## API Endpoints to Add

```python
# Get all Skybanking fees
@app.get("/api/skybanking-fees", dependencies=[Depends(verify_admin)])

# Get single Skybanking fee
@app.get("/api/skybanking-fees/{fee_id}", dependencies=[Depends(verify_admin)])

# Create Skybanking fee
@app.post("/api/skybanking-fees", dependencies=[Depends(verify_admin)])

# Update Skybanking fee
@app.put("/api/skybanking-fees/{fee_id}", dependencies=[Depends(verify_admin)])

# Delete Skybanking fee
@app.delete("/api/skybanking-fees/{fee_id}", dependencies=[Depends(verify_admin)])

# Get filters for Skybanking fees
@app.get("/api/skybanking-filters", dependencies=[Depends(verify_admin)])
```








