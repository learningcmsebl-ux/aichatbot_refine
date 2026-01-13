# Fee Engine Microservice - Architecture & API Contract

**Effective from: 01st January, 2026**  
**Document Version: 2.0 (Bank-Grade Production Ready)**  
**Last Review: 2025-12-30**

## Document Status

✅ **Production Ready**: This document has been reviewed from a bank-grade production, audit, and integration perspective.  
✅ **Implementation Ready**: Architecture is sound, API contracts are clear, and fee logic is correctly modeled.  
⚠️ **Enhancements Documented**: Recommended improvements for audit compliance, performance, and governance are documented with implementation notes.

### Key Improvements in This Version

- ✅ Explicit rule specificity precedence (ANY handling rules)
- ✅ Conflict resolution documentation (specificity score recommendation)
- ✅ Audit trail field recommendations (created_by, updated_by, approved_by)
- ✅ Request ID/Trace ID support for production debugging
- ✅ Rule metadata in API responses (rule_id, priority, effective dates)
- ✅ FX rate handling specification and retry mechanism recommendations
- ✅ Validation error structure definition
- ✅ Free entitlement chaining behavior documentation
- ✅ Tiered fee + min/max interaction precedence (critical for auditors)
- ✅ ON_OUTSTANDING + PERCENT calculation period clarification
- ✅ Cache strategy and SLA expectations documentation
- ✅ Admin panel governance model (maker-checker, versioning, rollback)
- ✅ Naming consistency clarifications (case-insensitive, NULL vs ANY)

---

## Overview

The Fee Engine is a deterministic fee calculation microservice using a single master table design. It supports multiple product lines: Credit Cards, Retail Assets, Skybanking, and Priority Banking.

---

## Architecture

### Design Pattern: Single Master Table

The system uses **multiple master tables** (one per product line):
1. `card_fee_master` - Credit/Debit/Prepaid card fees
2. `retail_asset_charge_master` - Loan and retail asset charges  
3. `skybanking_fee_master` - Skybanking service fees

**Key Benefits:**
- ✅ Single source of truth per product line
- ✅ Fast lookups with proper indexing
- ✅ No complex joins required
- ✅ Easy to maintain and audit
- ✅ Supports versioning via date ranges

### Database Schema Structure

#### Card Fee Master Table
```sql
CREATE TABLE card_fee_master (
    fee_id UUID PRIMARY KEY,
    effective_from DATE NOT NULL,
    effective_to DATE,
    charge_type VARCHAR(100) NOT NULL,
    card_category ENUM('CREDIT', 'DEBIT', 'PREPAID', 'ANY'),
    card_network ENUM('VISA', 'MASTERCARD', 'DINERS', 'UNIONPAY', 'FX', 'TAKAPAY', 'ANY'),
    card_product VARCHAR(50),
    full_card_name VARCHAR(200),
    fee_value DECIMAL(15, 4) NOT NULL,
    fee_unit ENUM('BDT', 'USD', 'PERCENT', 'COUNT', 'TEXT'),
    fee_basis ENUM('PER_TXN', 'PER_YEAR', 'PER_MONTH', 'PER_VISIT', 'ON_OUTSTANDING'),
    min_fee_value DECIMAL(15, 4),
    max_fee_value DECIMAL(15, 4),
    free_entitlement_count INTEGER,
    condition_type ENUM('NONE', 'WHICHEVER_HIGHER', 'FREE_UPTO_N', 'NOTE_BASED'),
    note_reference VARCHAR(20),
    priority INTEGER DEFAULT 100,
    status ENUM('ACTIVE', 'INACTIVE'),
    product_line VARCHAR(50) DEFAULT 'CREDIT_CARDS',
    remarks TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**Key Columns Explained:**
- `fee_id`: Primary key (UUID)
- `effective_from` / `effective_to`: Date range for fee validity
- `charge_type`: Logical fee group (e.g., `CASH_WITHDRAWAL_EBL_ATM`)
- `card_category`: CREDIT / DEBIT / PREPAID / **ANY** (explicit ENUM value)
- `card_network`: VISA / MASTERCARD / DINERS / UNIONPAY / FX / TAKAPAY / **ANY** (explicit ENUM value)
- `card_product`: Classic / Gold / Platinum / etc. / **ANY** (VARCHAR, where "ANY" or NULL = match all)
- `fee_value`: Main fee value
- `fee_unit`: BDT / USD / PERCENT / COUNT / TEXT
- `fee_basis`: PER_TXN / PER_YEAR / PER_MONTH / PER_VISIT / ON_OUTSTANDING
- `condition_type`: NONE / WHICHEVER_HIGHER / FREE_UPTO_N / NOTE_BASED
- `priority`: Higher priority wins when multiple rules match (see Conflict Resolution below)

**Important Notes:**
- **ANY values**: The ENUM types (`card_category_enum`, `card_network_enum`) explicitly include `'ANY'` as a valid value
- **card_product handling**: For `card_product` (VARCHAR field):
  - `"ANY"` string = matches all products
  - `NULL` or empty string = matches all products (treated same as "ANY")
  - Case-insensitive matching is used for product name comparisons
  - Special handling for "/" in product names (e.g., "Platinum/Titanium" matches both "Platinum" and "Titanium")

#### Retail Asset Charge Master Table
```sql
CREATE TABLE retail_asset_charge_master (
    charge_id UUID PRIMARY KEY,
    effective_from DATE NOT NULL,
    effective_to DATE,
    loan_product ENUM('FAST_CASH_OD', 'FAST_LOAN_SECURED_EMI', ...),
    loan_product_name VARCHAR(200),
    charge_type ENUM('PROCESSING_FEE', 'LIMIT_REDUCTION_FEE', ...),
    charge_description VARCHAR(500),
    fee_value DECIMAL(15, 4),
    fee_unit ENUM('BDT', 'USD', 'PERCENT', 'COUNT', 'TEXT', 'ACTUAL_COST'),
    fee_basis ENUM('PER_LOAN', 'PER_AMOUNT', 'PER_INSTALLMENT', ...),
    -- Tiered fee structure
    tier_1_threshold DECIMAL(15, 4),
    tier_1_fee_value DECIMAL(15, 4),
    tier_1_max_fee DECIMAL(15, 4),
    tier_2_threshold DECIMAL(15, 4),
    tier_2_fee_value DECIMAL(15, 4),
    tier_2_max_fee DECIMAL(15, 4),
    min_fee_value DECIMAL(15, 4),
    max_fee_value DECIMAL(15, 4),
    condition_type ENUM('NONE', 'WHICHEVER_HIGHER', 'TIERED', 'NOTE_BASED'),
    priority INTEGER DEFAULT 100,
    status ENUM('ACTIVE', 'INACTIVE'),
    ...
);
```

**Key Features:**
- Supports tiered fee structures (e.g., "Up to 50 lakh: 0.575%, Above 50 lakh: 0.345%")
- Stores original descriptions for reference
- Employee pricing support
- Category-based pricing (for Executive Loan, etc.)

### Audit Trail & Governance Fields (Recommended Addition)

**Current State:** The schema includes `created_at` and `updated_at` timestamps.

**Recommended Enhancement for Bank-Grade Auditing:**
For production deployments requiring full audit trail compliance, consider adding:

```sql
ALTER TABLE card_fee_master ADD COLUMN created_by VARCHAR(50);
ALTER TABLE card_fee_master ADD COLUMN updated_by VARCHAR(50);
ALTER TABLE card_fee_master ADD COLUMN approved_by VARCHAR(50);
ALTER TABLE card_fee_master ADD COLUMN approved_at TIMESTAMP;

-- Similar additions for retail_asset_charge_master and skybanking_fee_master
```

**Purpose:**
- `created_by`: User/system that created the rule
- `updated_by`: User/system that last modified the rule
- `approved_by`: User/system that approved the rule (maker-checker workflow)
- `approved_at`: Timestamp of approval (enables effective date validation)

**Implementation Note:** Even if admin panel controls these fields, the schema should reflect audit requirements for regulatory compliance and change traceability.

---

## API Contract

### Base URL
```
http://localhost:8003
```

### Request Headers

**Recommended Headers:**
- `Content-Type: application/json` (required)
- `X-Request-ID: <uuid>` (optional, recommended for production)
  - Client-generated UUID for request tracing
  - Echoed back in response headers for debugging and reconciliation
  - Format: Standard UUID v4 (e.g., `550e8400-e29b-41d4-a716-446655440000`)

**Response Headers:**
- `X-Request-ID`: Echoed back from request (if provided)

### Endpoints

#### 1. Health Check
```
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "fee-engine"
}
```

---

#### 2. Calculate Card Fee
```
POST /fees/calculate
```

**Request Body:**
```json
{
  "as_of_date": "2026-02-15",
  "charge_type": "CASH_WITHDRAWAL_EBL_ATM",
  "card_category": "CREDIT",
  "card_network": "VISA",
  "card_product": "Platinum",
  "amount": 20000,
  "currency": "BDT",
  "usage_index": 3,
  "outstanding_balance": null,
  "product_line": "CREDIT_CARDS"
}
```

**Request Fields:**
- `as_of_date` (required): Date for fee calculation (YYYY-MM-DD)
- `charge_type` (required): Charge type (e.g., "CASH_WITHDRAWAL_EBL_ATM")
- `card_category` (required): CREDIT / DEBIT / PREPAID
- `card_network` (required): VISA / MASTERCARD / DINERS / UNIONPAY / FX / TAKAPAY (case-insensitive matching)
- `card_product` (optional): Platinum / Classic / Gold / etc.
  - **NULL vs ANY**: If `card_product` is NULL or omitted, the system searches for rules where `card_product` is NULL, empty string, or "ANY" (all treated equivalently)
  - **Case-insensitive**: Product names are matched case-insensitively (e.g., "platinum" matches "Platinum")
  - **Partial matching**: Supports partial matches for compound names (e.g., "Platinum/Titanium" matches queries for "Platinum" or "Titanium")
- `amount` (optional): Transaction amount for percentage-based fees
- `currency` (optional): BDT or USD (default: BDT)
- `usage_index` (optional): For free entitlement logic (e.g., 1st, 2nd, 3rd card)
- `outstanding_balance` (optional): For ON_OUTSTANDING basis fees
- `product_line` (optional): CREDIT_CARDS / SKYBANKING / PRIORITY_BANKING / RETAIL_ASSETS

**Response - Success (CALCULATED):**
```json
{
  "status": "CALCULATED",
  "fee_amount": 345.00,
  "fee_currency": "BDT",
  "fee_basis": "PER_TXN",
  "charge_type": "CASH_WITHDRAWAL_EBL_ATM",
  "rule_id": "550e8400-e29b-41d4-a716-446655440000",
  "rule_priority": 90,
  "effective_from": "2025-11-27",
  "effective_to": null,
  "remarks": "Whichever higher applied"
}
```

**Response Fields:**
- `rule_id`: UUID of the fee rule used for calculation (essential for audit disputes)
- `rule_priority`: Priority value of the selected rule
- `effective_from`: Effective start date of the rule
- `effective_to`: Effective end date of the rule (null if no expiry)

**Response - Note-based (REQUIRES_NOTE_RESOLUTION):**
```json
{
  "status": "REQUIRES_NOTE_RESOLUTION",
  "note_reference": "Note 12",
  "message": "Fee depends on external note definition"
}
```

**Response - Not Found (NO_RULE_FOUND):**
```json
{
  "status": "NO_RULE_FOUND",
  "message": "No fee rule found for this card and charge type"
}
```

**Response - Currency Required (FX_RATE_REQUIRED):**
```json
{
  "status": "FX_RATE_REQUIRED",
  "message": "Fee rule exists but currency conversion required",
  "rule_id": "550e8400-e29b-41d4-a716-446655440000",
  "rule_priority": 90,
  "effective_from": "2025-11-27"
}
```

**FX Rate Handling:**

**Current Behavior:**
- If fee rule exists but currency conversion is required (e.g., fee in USD but request in BDT), returns `FX_RATE_REQUIRED` status.

**Recommended Enhancement:**
For production use, consider adding an endpoint that accepts FX rate:

**Option 1: Extended Request Field**
```json
{
  "as_of_date": "2026-02-15",
  "charge_type": "CASH_WITHDRAWAL_EBL_ATM",
  "card_category": "CREDIT",
  "card_network": "VISA",
  "card_product": "Platinum",
  "amount": 20000,
  "currency": "BDT",
  "fx_rate": 109.50,
  "fx_rate_date": "2026-02-15"
}
```

**Option 2: Separate Endpoint**
```
POST /fees/calculate-with-fx
```

**Note:** Current implementation requires external FX rate service integration. The response structure supports future enhancement.

**Response - Validation Error (400 Bad Request):**
```json
{
  "status": "INVALID_REQUEST",
  "message": "Validation error",
  "errors": [
    {
      "field": "card_network",
      "message": "Invalid value. Must be one of: VISA, MASTERCARD, DINERS, UNIONPAY, FX, TAKAPAY"
    },
    {
      "field": "as_of_date",
      "message": "Date cannot be in the future"
    }
  ]
}
```

---

#### 3. Query Retail Asset Charges
```
POST /retail-asset-charges/query
```

**Request Body:**
```json
{
  "as_of_date": "2026-02-15",
  "loan_product": "FAST_CASH_OD",
  "charge_type": "LIMIT_REDUCTION_FEE"
}
```

**Request Fields:**
- `as_of_date` (required): Date for charge lookup (YYYY-MM-DD)
- `loan_product` (optional): FAST_CASH_OD / FAST_LOAN_SECURED_EMI / etc.
- `charge_type` (optional): PROCESSING_FEE / LIMIT_REDUCTION_FEE / etc.

**Response - Success (FOUND):**
```json
{
  "status": "FOUND",
  "charges": [
    {
      "charge_id": "uuid-here",
      "loan_product": "FAST_CASH_OD",
      "loan_product_name": "Fast Cash (Overdraft - OD)",
      "charge_type": "LIMIT_REDUCTION_FEE",
      "charge_description": "Fast Cash Limit Reduction Processing Fee",
      "fee_value": 0.575,
      "fee_unit": "PERCENT",
      "fee_basis": "PER_AMOUNT",
      "min_fee_value": 575.0,
      "min_fee_unit": "BDT",
      "max_fee_value": 5750.0,
      "max_fee_unit": "BDT",
      "tier_1_threshold": null,
      "tier_1_fee_value": null,
      "tier_1_max_fee": null,
      "tier_2_threshold": null,
      "tier_2_fee_value": null,
      "tier_2_max_fee": null,
      "effective_from": "2025-11-27",
      "effective_to": null,
      "status": "ACTIVE",
      "priority": 100
    }
  ]
}
```

**Note:** All charge objects include metadata (`charge_id`, `priority`, `effective_from`, `effective_to`) for audit and dispute resolution.

**Response - Not Found:**
```json
{
  "status": "NO_RULE_FOUND",
  "charges": [],
  "message": "No retail asset charges found for the specified criteria"
}
```

---

#### 4. Query Skybanking Fees
```
POST /skybanking-fees/query
```

**Request Body:**
```json
{
  "as_of_date": "2026-02-15",
  "charge_type": "ACCOUNT_CERTIFICATE",
  "product": "Skybanking",
  "network": "VISA"
}
```

**Request Fields:**
- `as_of_date` (required): Date for fee lookup
- `charge_type` (optional): ACCOUNT_CERTIFICATE / FUND_TRANSFER / etc.
- `product` (optional): Skybanking
- `network` (optional): VISA / Mastercard

**Response Format:** Similar structure to retail asset charges

---

#### 5. List Card Fee Rules
```
GET /fees/rules?charge_type=CASH_WITHDRAWAL_EBL_ATM&card_category=CREDIT&limit=100
```

**Query Parameters:**
- `charge_type` (optional): Filter by charge type
- `card_category` (optional): Filter by card category (CREDIT / DEBIT / PREPAID)
- `card_network` (optional): Filter by card network
- `limit` (optional): Maximum number of results (default: 100, max: 1000)

**Response:**
```json
{
  "rules": [
    {
      "fee_id": "uuid",
      "charge_type": "CASH_WITHDRAWAL_EBL_ATM",
      "card_category": "CREDIT",
      "card_network": "VISA",
      "card_product": "Platinum",
      "fee_value": 2.5,
      "fee_unit": "PERCENT",
      "min_fee_value": 345,
      ...
    }
  ],
  "total": 1
}
```

---

#### 6. Unified Fee Query
```
POST /fees/query
```

**Request Body:**
```json
{
  "product_line": "RETAIL_ASSETS",
  "as_of_date": "2026-02-15",
  "charge_type": "LIMIT_REDUCTION_FEE",
  "loan_product": "FAST_CASH_OD"
}
```

**Request Fields:**
- `product_line` (required): CREDIT_CARDS / RETAIL_ASSETS / SKYBANKING
- `as_of_date` (required): Date for fee lookup
- Other fields depend on product_line (card fields for CREDIT_CARDS, loan_product for RETAIL_ASSETS, etc.)

Routes to the appropriate handler based on `product_line`.

---

## Fee Calculation Logic

### 1. Rule Selection Algorithm

Matches rules where:
- `effective_from ≤ as_of_date < effective_to` (or `effective_to` is NULL)
- `charge_type` matches exactly
- Card/loan attributes match or are `ANY`
- `status = 'ACTIVE'`

**Rule Matching with ANY Values - Specificity Precedence:**

When multiple rules match, the system follows this precedence order (most specific first):

1. **Exact Match** (specificity score = 6)
   - `card_category` = exact match (not ANY)
   - `card_network` = exact match (not ANY)
   - `card_product` = exact match (not NULL, not "ANY")
   - Example: VISA + Platinum + CREDIT (all specific)

2. **Network-Specific, Product-Any** (specificity score = 4)
   - `card_category` = exact match
   - `card_network` = exact match
   - `card_product` = ANY/NULL
   - Example: VISA + ANY product + CREDIT

3. **Product-Specific, Network-Any** (specificity score = 4)
   - `card_category` = exact match
   - `card_network` = ANY
   - `card_product` = exact match
   - Example: ANY network + Platinum + CREDIT

4. **Category-Specific, Others-Any** (specificity score = 2)
   - `card_category` = exact match
   - `card_network` = ANY
   - `card_product` = ANY/NULL
   - Example: ANY network + ANY product + CREDIT

5. **Fully Generic** (specificity score = 0)
   - `card_category` = ANY
   - `card_network` = ANY
   - `card_product` = ANY/NULL
   - Example: ANY + ANY + ANY

**Specificity Score Calculation:**
```
specificity_score = 
  (card_category != 'ANY' ? 2 : 0) +
  (card_network != 'ANY' ? 2 : 0) +
  (card_product IS NOT NULL AND card_product != 'ANY' AND card_product != '' ? 2 : 0)
```

**Conflict Resolution Logic (CRITICAL):**

**Current Implementation (Recommended for Fix):**
1. **Primary**: Rules with higher `priority` value are selected first
2. **Secondary (Current - Problematic)**: If priorities are equal, higher `fee_value` is selected ⚠️
   - **Issue**: Higher fee value ≠ correct business rule (e.g., annual fee vs discount fee)
   - **Risk**: Incorrect rule selection when priorities are equal

**Recommended Enhancement:**
Replace secondary tiebreaker with **specificity score**:

1. **Primary**: Higher `priority` value wins
2. **Secondary (Recommended)**: If priorities are equal, higher `specificity_score` wins (more specific rule)
3. **Tertiary (Optional)**: If priority and specificity are equal, select rule with most recent `effective_from` date
4. **Final (Avoid)**: Do NOT use `fee_value` as tiebreaker (not business-logical)

**Example:**
```
Rule A: priority=100, VISA+Platinum+CREDIT (specificity=6), fee_value=5000
Rule B: priority=100, VISA+ANY+CREDIT (specificity=4), fee_value=6000

Correct Selection: Rule A (higher specificity, even though lower fee)
Current (Problematic): Rule B (higher fee_value, but less specific)
```

**Note:** This ensures deterministic, predictable, and auditable fee calculation aligned with business logic.

### 2. "Whichever Higher" Logic

When `condition_type = 'WHICHEVER_HIGHER'`:
```
percent_fee = amount × fee_value / 100
fixed_fee = min_fee_value
final_fee = max(percent_fee, fixed_fee)
```

**Example:** ATM withdrawal fee
- Fee: 2.5% or BDT 345, whichever is higher
- If withdrawal = BDT 10,000 → 2.5% = BDT 250 → Final fee = BDT 345
- If withdrawal = BDT 20,000 → 2.5% = BDT 500 → Final fee = BDT 500

**Note on ON_OUTSTANDING + PERCENT Calculation Period:**

When `fee_basis = 'ON_OUTSTANDING'` and `fee_unit = 'PERCENT'`, the calculation period must be clarified:

**Current Specification:**
- The fee is calculated as: `outstanding_balance × fee_value / 100`
- However, the **calculation period** (daily/monthly/annual) is not explicitly defined in the schema

**Clarification Needed:**
- **For Card Fees**: `ON_OUTSTANDING` typically implies **monthly calculation** on the outstanding balance
- **For Retail Assets**: May vary by product (e.g., daily, monthly, annual)
- **Recommendation**: Document the calculation period per charge_type or loan_product in business rules, or add a `calculation_period` field to the schema

**Example:**
- Late Payment Fee: `fee_basis='ON_OUTSTANDING'`, `fee_unit='PERCENT'`, calculation_period='MONTHLY'
- Calculation: `fee = (outstanding_balance × fee_value / 100) / 12` (if annual rate) or `fee = outstanding_balance × fee_value / 100` (if monthly rate)

**Note:** Current implementation assumes the fee_value represents the rate for the period specified in `fee_basis`. For audit clarity, document the expected period explicitly.

### 3. Free Entitlement Logic

When `condition_type = 'FREE_UPTO_N'`:
- If `usage_index ≤ free_entitlement_count` → fee = 0 (rule matched, fee is zero)
- Else → apply next matching rule

**Free Entitlement Chaining Behavior (CRITICAL):**

When a `FREE_UPTO_N` rule matches but the usage index exceeds the free entitlement count, the system applies the **next matching rule** using the following logic:

1. **Same Charge Type**: The system searches for another rule with the **same `charge_type`**
2. **Re-evaluation**: Rule selection is re-evaluated (same matching criteria, priority, specificity logic applies)
3. **Priority Re-evaluation**: Rules are re-sorted by priority (and specificity if equal priority)
4. **ANY Fallback**: If no specific rule found, can fall back to ANY rules (following specificity precedence)
5. **Deterministic**: The chaining is deterministic - same inputs always produce same results

**Example:** Supplementary cards
- Rule 1: `FREE_UPTO_N`, `free_entitlement_count=2`, `usage_index ≤ 2` → fee = 0
- Rule 2: `NONE`, `usage_index > 2` → fee = BDT 2,300 per year

**Query**: `usage_index=3` (3rd card)
1. Rule 1 matches (same charge_type, same card attributes) but `usage_index (3) > free_entitlement_count (2)`
2. System applies Rule 2 (next matching rule with same charge_type)
3. Result: Fee = BDT 2,300

**Important Clarifications:**
- ✅ Chaining occurs **within the same charge_type** only
- ✅ Priority and specificity logic applies during chaining
- ✅ Can fall back to ANY rules if no specific rule exists
- ✅ Deterministic - no guessing or ambiguous behavior
- ❌ Does NOT cross charge_type boundaries
- ❌ Does NOT apply rules from different fee categories

### 4. Tiered Fee Logic (Retail Assets)

When tiered structure exists:
- Amount ≤ `tier_1_threshold` → Use `tier_1_fee_value` (with `tier_1_max_fee` cap)
- Amount > `tier_1_threshold` → Use `tier_2_fee_value` (with `tier_2_max_fee` cap)

**Tiered Fee + Min/Max Interaction - Precedence (CRITICAL for Auditors):**

When tiered fees have both tier-specific max fees AND global min/max fees, the precedence is:

```
Step 1: Calculate tier-based fee
  - If amount ≤ tier_1_threshold: fee = amount × tier_1_fee_value / 100
  - If amount > tier_1_threshold: fee = amount × tier_2_fee_value / 100

Step 2: Apply tier-specific max cap
  - If tier 1: fee = min(fee, tier_1_max_fee)
  - If tier 2: fee = min(fee, tier_2_max_fee)

Step 3: Apply global min fee cap
  - fee = max(fee, min_fee_value)

Step 4: Apply global max fee cap
  - fee = min(fee, max_fee_value)
```

**Example:** Fast Cash Processing Fee
- Tier 1: Up to 50 lakh: 0.575% (max BDT 17,250)
- Tier 2: Above 50 lakh: 0.345% (max BDT 23,000)
- Global min: BDT 500
- Global max: BDT 25,000

**Calculation for 60 lakh (tier 2):**
1. Tier calculation: 60,00,000 × 0.345% = BDT 20,700
2. Tier 2 max cap: min(20,700, 23,000) = BDT 20,700
3. Global min cap: max(20,700, 500) = BDT 20,700
4. Global max cap: min(20,700, 25,000) = BDT 20,700
5. **Final fee: BDT 20,700**

**Edge Case:** If tier_2_max_fee (23,000) < global_min_fee_value (500), the global min would override after step 2, but this is a data configuration error that should be caught during validation.

### 5. Note-Based Logic

When `condition_type = 'NOTE_BASED'`:
- Returns `REQUIRES_NOTE_RESOLUTION` status
- Provides `note_reference` for external resolution
- Never guesses - strictly deterministic
- Client must handle note resolution externally

**Example:** Some fees depend on "Note 12" definition which is external to the fee engine

---

## Product Lines Supported

1. **CREDIT_CARDS** - Credit/Debit/Prepaid card fees
   - Annual fees, supplementary cards, ATM withdrawals, lounge access, etc.

2. **RETAIL_ASSETS** - Loan processing fees, early settlement, etc.
   - Processing fees, limit enhancement/reduction, renewal, partial payment, early settlement

3. **SKYBANKING** - Digital banking service fees
   - Account certificates, fund transfers, transaction fees

4. **PRIORITY_BANKING** - Priority banking fees
   - Priority account fees, services

---

## Charge Types (Card Fees)

Standardized charge types:
- `ISSUANCE_ANNUAL_PRIMARY` - Primary card annual fee
- `SUPPLEMENTARY_ANNUAL` - Supplementary card annual fee (3rd+ cards)
- `SUPPLEMENTARY_FREE_ENTITLEMENT` - Free supplementary cards count
- `CARD_REPLACEMENT` - Card replacement fee
- `PIN_REPLACEMENT` - PIN replacement fee
- `LATE_PAYMENT` - Late payment fee
- `CASH_WITHDRAWAL_EBL_ATM` - Cash withdrawal at EBL ATM
- `CASH_WITHDRAWAL_OTHER_ATM` - Cash withdrawal at other bank ATM
- `ATM_RECEIPT_EBL` - ATM receipt fee
- `GLOBAL_LOUNGE_ACCESS_FEE` - Global lounge access fee
- `GLOBAL_LOUNGE_FREE_VISITS_ANNUAL` - Free lounge visits per year
- `SKYLOUNGE_FREE_VISITS_INTL_ANNUAL` - International SkyLounge free visits
- `SKYLOUNGE_FREE_VISITS_DOM_ANNUAL` - Domestic SkyLounge free visits
- `OVERLIMIT` - Overlimit fee
- `DUPLICATE_ESTATEMENT` - Duplicate e-statement fee
- `SALES_VOUCHER_RETRIEVAL` - Sales voucher retrieval fee
- `CERTIFICATE_FEE` - Certificate fee
- `RISK_ASSURANCE_FEE` - Risk assurance fee
- `CARD_CHEQUBOOK` - Card chequebook fee
- `CARD_CHEQUE_PROCESSING` - Card cheque processing fee
- `CUSTOMER_VERIFICATION_CIB` - CIB verification fee
- `TRANSACTION_ALERT_ANNUAL` - Transaction alert annual fee
- `INTEREST_RATE` - Interest rate information

---

## Charge Types (Retail Assets)

Standardized charge types:
- `PROCESSING_FEE` - Loan processing fee
- `LIMIT_ENHANCEMENT_FEE` - Limit enhancement processing fee
- `LIMIT_REDUCTION_FEE` - Limit reduction processing fee
- `LIMIT_CANCELLATION_FEE` - Limit cancellation/closing fee
- `RENEWAL_FEE` - Loan renewal fee
- `PARTIAL_PAYMENT_FEE` - Partial payment fee
- `EARLY_SETTLEMENT_FEE` - Early settlement fee
- `SECURITY_LIEN_CONFIRMATION` - Security lien confirmation & encashment
- `QUOTATION_CHANGE_FEE` - Quotation change fee (for car loans)
- `NOTARIZATION_FEE` - Notarization fee
- `NOC_FEE` - Loan repayment certificate (NOC) fee
- `PENAL_INTEREST` - Penal interest
- `CIB_CHARGE` - CIB charge
- `CPV_CHARGE` - CPV charge
- `VETTING_VALUATION_CHARGE` - Vetting & valuation charge
- `SECURITY_REPLACEMENT_FEE` - Security replacement fee
- `STAMP_CHARGE` - Stamp charge
- `LOAN_OUTSTANDING_CERTIFICATE_FEE` - Loan outstanding certificate fee
- `RESCHEDULE_RESTRUCTURE_FEE` - Reschedule & restructure fee
- `RESCHEDULE_RESTRUCTURE_EXIT_FEE` - Reschedule & restructure exit fee

---

## Loan Products (Retail Assets)

- `FAST_CASH_OD` - Fast Cash (Overdraft - OD)
- `FAST_LOAN_SECURED_EMI` - Fast Loan (Secured EMI Loan)
- `EDU_LOAN_SECURED` - Education Loan (Secured)
- `EDU_LOAN_UNSECURED` - Education Loan (Unsecured)
- `OTHER_EMI_LOANS` - Other EMI Loans
- `EXECUTIVE_LOAN` - Executive Loan
- `ASSURE_LOAN` - Assure Loan
- `WOMENS_LOAN` - Women's Loan
- `AUTO_LOAN` - Auto Loan
- `TWO_WHEELER_LOAN` - Two Wheeler Loan
- `HOME_LOAN` - Home Loan
- `HOME_CREDIT` - Home Credit
- `MORTGAGE_LOAN` - Mortgage Loan
- `HOME_LOAN_PAYMENT_PROTECTION` - Home Loan Payment Protection

---

## Integration Example

### Python Client Example
```python
import httpx
from datetime import date

async def calculate_card_fee(charge_type, card_category, card_network, card_product, amount=None):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8003/fees/calculate",
            json={
                "as_of_date": str(date.today()),
                "charge_type": charge_type,
                "card_category": card_category,
                "card_network": card_network,
                "card_product": card_product,
                "amount": amount,
                "currency": "BDT"
            },
            timeout=5.0
        )
        return response.json()

# Example usage
result = await calculate_card_fee(
    charge_type="CASH_WITHDRAWAL_EBL_ATM",
    card_category="CREDIT",
    card_network="VISA",
    card_product="Platinum",
    amount=20000
)

if result["status"] == "CALCULATED":
    print(f"Fee: {result['fee_currency']} {result['fee_amount']}")
```

### Retail Asset Charges Query Example
```python
async def query_retail_asset_charge(loan_product, charge_type):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8003/retail-asset-charges/query",
            json={
                "as_of_date": str(date.today()),
                "loan_product": loan_product,
                "charge_type": charge_type
            },
            timeout=5.0
        )
        return response.json()

# Example usage
result = await query_retail_asset_charge(
    loan_product="FAST_CASH_OD",
    charge_type="LIMIT_REDUCTION_FEE"
)

if result["status"] == "FOUND":
    charge = result["charges"][0]
    print(f"Fee: {charge['fee_value']} {charge['fee_unit']}")
    print(f"Min: {charge['min_fee_value']} {charge['min_fee_unit']}")
    print(f"Max: {charge['max_fee_value']} {charge['max_fee_unit']}")
```

---

## Environment Variables

### Required
- `FEE_ENGINE_DB_URL`: PostgreSQL connection string
  - Format: `postgresql://user:password@host:port/database`

### Optional (used if FEE_ENGINE_DB_URL not set)
- `POSTGRES_USER`: PostgreSQL user (default: postgres)
- `POSTGRES_PASSWORD`: PostgreSQL password
- `POSTGRES_HOST`: PostgreSQL host (default: localhost)
- `POSTGRES_PORT`: PostgreSQL port (default: 5432)
- `POSTGRES_DB`: PostgreSQL database name

### Service Configuration
- `FEE_ENGINE_PORT`: Service port (default: 8003)

---

## Setup Instructions

### 1. Database Setup
```bash
# Create database and run schema
psql -U postgres -d postgres -f fee_engine/schema.sql
psql -U postgres -d postgres -f fee_engine/retail_asset_schema.sql
psql -U postgres -d postgres -f fee_engine/skybanking_schema.sql
```

### 2. Install Dependencies
```bash
cd credit_card_rate
pip install -r requirements.txt
```

### 3. Import Data
```bash
# Import card fees
python fee_engine/import_credit_cards.py

# Import retail asset charges
python fee_engine/import_retail_asset_charges.py

# Import Skybanking fees
python fee_engine/import_skybanking_fees.py
```

### 4. Run Service
```bash
# Set environment variables
export FEE_ENGINE_DB_URL="postgresql://user:password@localhost:5432/dbname"
export FEE_ENGINE_PORT=8003

# Run service
uvicorn fee_engine.fee_engine_service:app --host 0.0.0.0 --port 8003
```

Or using Docker:
```bash
docker-compose up fee-engine
```

---

## Testing

### Test Card Fee Calculation
```bash
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

### Test Retail Asset Charges Query
```bash
curl -X POST http://localhost:8003/retail-asset-charges/query \
  -H "Content-Type: application/json" \
  -d '{
    "as_of_date": "2026-02-15",
    "loan_product": "FAST_CASH_OD",
    "charge_type": "LIMIT_REDUCTION_FEE"
  }'
```

### Test Health Check
```bash
curl http://localhost:8003/health
```

---

## Key Features

✅ **Deterministic** - Same inputs always produce same outputs  
✅ **No guessing** - Note-based rules return structured responses  
✅ **Bank-grade** - Designed for production use  
✅ **Single source of truth** - All fees in master tables  
✅ **Easy to maintain** - Simple schema, clear logic  
✅ **Versioning support** - Date-based effective periods  
✅ **Multi-currency** - BDT and USD support  
✅ **Complex logic** - Whichever higher, free entitlements, tiered fees  
✅ **Multi-product line** - Cards, Retail Assets, Skybanking, Priority Banking  
✅ **Extensible** - Easy to add new charge types and products

---

## Error Handling

### HTTP Status Codes
- `200 OK` - Request successful
- `400 Bad Request` - Invalid request parameters (see Validation Error Structure below)
- `500 Internal Server Error` - Server error

### Response Status Values
- `CALCULATED` - Fee calculated successfully
- `FOUND` - Charge/fee found (for query endpoints)
- `NO_RULE_FOUND` - No matching rule found
- `REQUIRES_NOTE_RESOLUTION` - Fee depends on external note
- `FX_RATE_REQUIRED` - Currency conversion required
- `INVALID_REQUEST` - Validation error (request parameters invalid)

### Validation Error Structure

When a request fails validation (HTTP 400), the response follows this structure:

```json
{
  "status": "INVALID_REQUEST",
  "message": "Validation error",
  "errors": [
    {
      "field": "card_network",
      "message": "Invalid value 'MASTERCARDX'. Must be one of: VISA, MASTERCARD, DINERS, UNIONPAY, FX, TAKAPAY"
    },
    {
      "field": "as_of_date",
      "message": "Date '2027-01-01' cannot be more than 1 year in the future"
    },
    {
      "field": "amount",
      "message": "Amount must be positive when provided"
    }
  ]
}
```

**Error Object Fields:**
- `field`: The request field that failed validation
- `message`: Human-readable error message explaining the validation failure

**Common Validation Rules:**
- Required fields must be present and non-null
- Enum values must match defined values (case-insensitive matching applied)
- Dates must be valid ISO 8601 format (YYYY-MM-DD)
- Dates cannot be too far in the future (business rule dependent)
- Numeric values (amount, usage_index) must be positive when provided
- Currency must be one of: BDT, USD

---

## Performance Considerations

- **Indexing**: All lookup columns are indexed for fast queries
- **Priority-based selection**: Efficient rule matching
- **Date range queries**: Optimized for effective date filtering
- **Connection pooling**: Database connections are pooled
- **Timeout**: 5 second default timeout for API calls

### Cache Strategy (Recommended for Production)

**Current State:** The service relies on database lookups only (no caching layer).

**Recommended Enhancement:**
For production deployments with high transaction volumes, implement a **read-through cache**:

**Cache Strategy:**
- **Cache Layer**: Redis or in-memory cache (e.g., Python `functools.lru_cache` with TTL)
- **Cache Key**: Hash of request attributes + `as_of_date`
  - Key components: `charge_type`, `card_category`, `card_network`, `card_product`, `as_of_date`, `usage_index`
  - Format: `fee:{hash(request_attributes)}:{as_of_date}`
- **Cache TTL**: 
  - Short TTL for fee rules (e.g., 5-15 minutes) to handle mid-day updates
  - Longer TTL for static lookups (e.g., 1 hour)
- **Cache Invalidation**: 
  - On rule updates (admin panel changes)
  - On effective date boundaries (midnight rollover)
- **Cache Miss**: Falls through to database query

**Example Implementation:**
```python
cache_key = f"fee:{hash(f'{charge_type}:{card_category}:{card_network}:{card_product}')}:{as_of_date}"
cached_result = redis.get(cache_key)
if cached_result:
    return cached_result
else:
    result = db_query(...)
    redis.set(cache_key, result, ex=300)  # 5 minute TTL
    return result
```

**SLA Expectations (Recommended Documentation):**

For infrastructure sizing and performance monitoring:

- **P95 Latency Target**: < 50ms (with cache), < 200ms (without cache)
- **P99 Latency Target**: < 100ms (with cache), < 500ms (without cache)
- **Expected TPS**: 
  - Contact Center: 100-500 TPS (typical)
  - Channel Integration: 1000-5000 TPS (peak)
  - Batch Processing: 10,000+ TPS (with bulk optimization)
- **Availability Target**: 99.9% uptime (typical bank SLA)
- **Concurrent Connections**: Support 100-1000 concurrent requests

---

## Admin Panel

The fee engine includes an admin panel for managing fees:
- Web-based interface at `/admin` (typically port 8009)
- CRUD operations for all fee types
- Bulk import/export capabilities
- Data validation and error checking

### Admin Panel Governance (Recommended for Production)

**Current State:** Admin panel provides CRUD operations with basic validation.

**Recommended Governance Model for Bank-Grade Operations:**

**1. Maker-Checker Workflow:**
- **Maker**: Creates/updates fee rules (status: `PENDING_APPROVAL`)
- **Checker**: Reviews and approves/rejects (status: `ACTIVE` / `REJECTED`)
- **Approval Required**: All changes require approval before taking effect
- **Approval History**: Track who approved what and when (links to `approved_by`, `approved_at` schema fields)

**2. Effective Date Enforcement:**
- **Validation**: Prevent creation of rules with `effective_from` in the past (unless authorized override)
- **Future-Dating**: Allow rules to be created with future `effective_from` dates (scheduled changes)
- **Overlap Detection**: Warn/block rules that overlap in date ranges for same charge_type + card attributes
- **Automatic Activation**: Background job activates rules when `effective_from` date is reached

**3. Rollback & Version History:**
- **Versioning**: Maintain historical versions of rules (soft delete or version table)
- **Rollback Capability**: Allow reverting to previous version if error detected
- **Change Log**: Audit trail of all changes (who, what, when, why)
- **Comparison View**: Diff view showing what changed between versions

**4. Data Validation Rules:**
- **Business Rules Validation**:
  - Ensure `min_fee_value ≤ max_fee_value`
  - Ensure `tier_1_threshold < tier_2_threshold` (if both present)
  - Ensure `tier_1_max_fee` and `tier_2_max_fee` are within global min/max bounds
  - Validate effective date ranges (no gaps, no overlaps for same rule attributes)
- **Completeness Checks**: Required fields must be populated
- **Consistency Checks**: Enum values must match schema definitions

**5. Access Control:**
- **Role-Based Access Control (RBAC)**:
  - Viewer: Read-only access
  - Maker: Create/update (pending approval)
  - Checker: Approve/reject changes
  - Admin: Full access + configuration changes
- **Audit Logging**: All actions logged (who, what, when, IP address)

**6. Bulk Operations:**
- **Import Validation**: Validate Excel/CSV imports before committing
- **Batch Approval**: Approve multiple rules at once
- **Bulk Deactivation**: Mass deactivation of rules (e.g., end-of-year cleanup)

**Implementation Note:** These governance features should be implemented based on organizational requirements. The schema supports audit fields (`created_by`, `updated_by`, `approved_by`, `approved_at`), and the admin panel can enforce these workflows.

---

## Notes

- The service is **deterministic** - same inputs always produce same outputs
- No guessing - note-based rules return structured responses
- Bank-grade - designed for production use
- Single source of truth - all fees in master tables
- Easy to maintain - simple schema, clear logic
- Effective dates support fee versioning and historical queries
- All timestamps are in UTC

---

## Support & Documentation

- Service Code: `credit_card_rate/fee_engine/fee_engine_service.py`
- Schema Files: `credit_card_rate/fee_engine/schema.sql`
- Import Scripts: `credit_card_rate/fee_engine/import_*.py`
- Admin Panel: `credit_card_rate/fee_engine/admin_panel/`

---

---

## Appendix: Naming & Consistency Rules

### Case-Insensitive Matching

**Card Network Matching:**
- API accepts case-insensitive values (e.g., "VISA", "visa", "Visa" all match)
- Database stores values in uppercase (ENUM type: `'VISA'`, `'MASTERCARD'`, etc.)
- Matching is performed case-insensitively using `UPPER()` function
- Exception: "Mastercard" vs "MASTERCARD" - both are normalized and matched

**Card Product Matching:**
- Product names are matched case-insensitively using `ILIKE` or `UPPER()` functions
- Example: "platinum" matches "Platinum", "PLATINUM", "Platinum"
- Special handling for "/" in names: "Platinum/Titanium" matches both "Platinum" and "Titanium"

**Charge Type Matching:**
- Charge types are matched exactly (case-sensitive)
- Example: `"CASH_WITHDRAWAL_EBL_ATM"` must match exactly (no case variation)

### NULL vs ANY Clarification

**card_product Field (VARCHAR):**
- `NULL` = matches all products (treated as "ANY")
- `""` (empty string) = matches all products (treated as "ANY")
- `"ANY"` (string) = matches all products
- All three are functionally equivalent in matching logic

**card_category / card_network Fields (ENUM):**
- `'ANY'` is an explicit ENUM value (not NULL)
- Database stores `'ANY'` as a string value in the ENUM
- NULL is not a valid value for these ENUM fields

**Recommendation:** For consistency, prefer using `"ANY"` string for `card_product` and `'ANY'` ENUM for category/network fields.

---

*Last Updated: 2025-12-30*
*Review Status: Bank-Grade Production Ready (with recommended enhancements noted)*

