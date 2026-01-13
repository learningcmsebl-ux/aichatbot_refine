# Plan: Integrate 4 Product Lines into Fee Engine Microservice

## Overview
Integrate fees and charges from 4 different product lines into the fee engine microservice:
1. **Credit Cards** - `Card_Fees_From_TXT.xlsx`
2. **Skybanking** - `Fees and Charges against issuing Certificates through EBL Skybanking...xlsx`
3. **Priority Banking** - `Priority_SOC_Converted.xlsx`
4. **Retail Assets/Loans** - `Retail Asset Schedule of Charges.xlsx`

## Current State Analysis

### Database Schema
- Current `card_fee_master` table is designed for card-specific fees
- Fields: `card_category`, `card_network`, `card_product` are card-specific
- Fee engine matching logic uses these fields for query matching

### Excel File Structures

1. **Credit Cards** (`Card_Fees_From_TXT.xlsx`):
   - Columns: Charge Type, Card Category, Card Network, Card Product, Full Card Name, Charge Amount/Fee
   - Simple structure, maps directly to current schema

2. **Skybanking** (`Skybanking_Fees` sheet):
   - Columns: FEE ID, EFFECTIVE FROM, EFFECTIVE TO, CHARGE TYPE, PRODUCT, PRODUCT NAME, FEE AMOUNT, FEE UNIT, FEE BASIS, STATUS, CONDITIONAL, CONDITION DESCRIPTION
   - Well-structured, similar to current schema

3. **Priority Banking** (`Priority_SOC_Converted.xlsx`):
   - Columns: Service Category, Service Item, Details/Conditions, Fee
   - Unstructured format, needs parsing

4. **Retail Assets** (`Retail Asset Schedule of Charges.xlsx`):
   - Columns: Product/Loan Type, Description, Charge Amount (complex text), Fee for EBL Employees, Effective from
   - Complex fee descriptions with conditions

## Proposed Solution

### Option 1: Extend Schema (Recommended)
Add a `product_line` field to distinguish product types while maintaining backward compatibility.

### Option 2: Reuse Existing Fields
Use `card_product` field creatively for non-card products (e.g., "Skybanking", "Priority Banking", "Fast Cash OD").

**Recommendation**: Option 1 is cleaner and more maintainable.

## Implementation Steps

### Step 1: Schema Extension
- Add `product_line` VARCHAR(50) column to `card_fee_master` table
- Make `card_category`, `card_network` nullable or default to "ANY" for non-card products
- Update ENUM types if needed (e.g., add "SKYBANKING", "PRIORITY_BANKING", "RETAIL_ASSETS" to card_category_enum, or create new product_line_enum)
- Update indexes to include `product_line`

### Step 2: Data Cleanup
- Delete all existing data from `card_fee_master` table (as requested)
- OR mark existing data as INACTIVE (if historical data needed)
- **Decision needed**: Delete all or mark inactive?

### Step 3: Create Import Scripts
Create separate import scripts for each product line:

#### 3.1 Credit Cards Importer (`import_credit_cards.py`)
- Read `Card_Fees_From_TXT.xlsx`
- Map columns:
  - `Charge Type` → `charge_type`
  - `Card Category` → `card_category` (normalize: "Credit Card" → "CREDIT")
  - `Card Network` → `card_network` (normalize: "VISA" → "VISA")
  - `Card Product` → `card_product`
  - `Full Card Name` → `full_card_name`
  - `Charge Amount/Fee` → `fee_value` (parse "BDT 1,725" → 1725)
- Set `product_line = "CREDIT_CARDS"`
- Set `fee_unit = "BDT"`, `fee_basis = "PER_YEAR"` (for annual fees)
- Set `effective_from = "2026-01-01"` (or parse from file if available)

#### 3.2 Skybanking Importer (`import_skybanking.py`)
- Read `Skybanking_Fees` sheet
- Map columns:
  - `CHARGE TYPE` → `charge_type`
  - `PRODUCT` → `card_product` (e.g., "Skybanking")
  - `PRODUCT NAME` → `full_card_name`
  - `FEE AMOUNT` → `fee_value` (handle "Variable" → NULL or 0)
  - `FEE UNIT` → `fee_unit`
  - `FEE BASIS` → `fee_basis` (normalize: "YEARLY" → "PER_YEAR", "PER REQUEST" → "PER_TXN")
  - `EFFECTIVE FROM` → `effective_from` (parse "27/11/2025")
  - `CONDITIONAL` → `condition_type` (map "YES" → "NOTE_BASED" or parse condition)
  - `CONDITION DESCRIPTION` → `remarks`
- Set `product_line = "SKYBANKING"`
- Set `card_category = "ANY"`, `card_network = "ANY"`

#### 3.3 Priority Banking Importer (`import_priority_banking.py`)
- Read `Priority SOC` sheet
- Parse unstructured format:
  - Skip header rows (rows 0-1)
  - `Service Category` → use in `charge_type` or `remarks`
  - `Service Item` → `charge_type`
  - `Details or conditions` → `remarks`
  - `Fee` → `fee_value` (parse "Free" → 0, parse amounts)
- Set `product_line = "PRIORITY_BANKING"`
- Set `card_category = "ANY"`, `card_network = "ANY"`, `card_product = "Priority Banking"`
- Set `effective_from = "2025-07-01"` (from sheet title)

#### 3.4 Retail Assets Importer (`import_retail_assets.py`)
- Read `Retail Loan SOC` sheet
- Map columns:
  - `Product / Loan Type` → `card_product` (e.g., "Fast Cash OD")
  - `Description` → `charge_type` (normalize to standard format)
  - `Charge Amount (Including 15% VAT)` → Parse complex text:
    - "Up to Tk. 50 lakh → 0.575% or max Tk. 17,250" → Use `fee_value = 0.575`, `fee_unit = "PERCENT"`, `min_fee_value = 0`, `max_fee_value = 17250`, `condition_type = "WHICHEVER_HIGHER"`
    - "Free" → `fee_value = 0`
  - `Effective from` → `effective_from`
- Set `product_line = "RETAIL_ASSETS"`
- Set `card_category = "ANY"`, `card_network = "ANY"`
- Handle complex fee structures with `condition_type` and `min_fee_value`/`max_fee_value`

### Step 4: Update Fee Engine Service
- Modify `calculate_fee` endpoint to accept optional `product_line` parameter
- Update query matching logic to filter by `product_line` when provided
- Update `FeeCalculationRequest` model to include `product_line` field

### Step 5: Update Chatbot Integration
- Modify `FeeEngineClient` to detect product line from query
- Add product line detection logic (e.g., "skybanking", "priority banking", "loan", "retail asset")
- Map queries to appropriate product line and charge types

### Step 6: Create Master Import Script
- Create `import_all_product_lines.py` that:
  1. Cleans existing data (delete or mark inactive)
  2. Runs all 4 importers in sequence
  3. Provides summary report

## Files to Create/Modify

### New Files
1. `credit_card_rate/fee_engine/import_credit_cards.py`
2. `credit_card_rate/fee_engine/import_skybanking.py`
3. `credit_card_rate/fee_engine/import_priority_banking.py`
4. `credit_card_rate/fee_engine/import_retail_assets.py`
5. `credit_card_rate/fee_engine/import_all_product_lines.py`
6. `credit_card_rate/fee_engine/schema_extension.sql` (ALTER TABLE statements)

### Files to Modify
1. `credit_card_rate/fee_engine/schema.sql` - Add product_line column
2. `credit_card_rate/fee_engine/fee_engine_service.py` - Update models and query logic
3. `bank_chatbot/app/services/fee_engine_client.py` - Add product line detection

## Data Cleanup Strategy

**Question for user**: Should we:
- **A)** Delete ALL existing data from `card_fee_master` before import?
- **B)** Only delete data for specific charge_types/product lines?
- **C)** Mark old data as INACTIVE instead of deleting?

**Recommendation**: Option A (delete all) for clean slate, OR Option C (mark inactive) if historical data is needed.

## Testing Plan

1. Test each importer individually with sample data
2. Verify data integrity (no duplicates, correct mappings)
3. Test fee engine queries for each product line
4. Test chatbot integration with queries for each product line

## Notes

- Priority Banking and Retail Assets have complex fee structures that may need special handling
- Some fees have "Variable" amounts - these may need to be stored as TEXT unit or with special condition_type
- Retail Assets fees often have tiered structures (e.g., "Up to X → Y%, Above X → Z%") - may need multiple records or complex condition logic











