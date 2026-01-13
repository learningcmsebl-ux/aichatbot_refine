# Union Pay Debit Card Issuance Fee - Issue and Fix

## Issue
When querying "What is the issuance fee for a Union pay Debit card?", the system was returning:
> "I'm sorry, but the specific issuance fee for a Union Pay Debit card is not available in the provided official Card Charges and Fees Schedule."

## Root Cause
The fee engine client was extracting the wrong network value:
- **Client extracted**: `"UNIONPAY"`
- **Database has**: `"UnionPay International"`

This mismatch prevented the fee engine from finding the matching record.

## Fix Applied

### 1. Updated Network Mapping
**File**: `bank_chatbot/app/services/fee_engine_client.py`

**Before:**
```python
elif "unionpay" in query_lower or "union pay" in query_lower:
    card_network = "UNIONPAY"
```

**After:**
```python
elif "unionpay" in query_lower or "union pay" in query_lower:
    card_network = "UnionPay International"  # Match DB format
```

### 2. Added Product Keyword for UnionPay Classic
Added "unionpay classic" and "union pay classic" to the product keywords mapping:
```python
"unionpay classic": "UnionPay Classic",  # UnionPay Classic (check before "classic")
"union pay classic": "UnionPay Classic",  # UnionPay Classic variant
```

### 3. Added Product Variation Handling
Added special handling for UnionPay Classic in the product variations:
```python
# Add variations for UnionPay Classic
elif card_info["card_network"] == "UnionPay International" and card_info["card_product"] == "Classic":
    product_variations.extend([
        "UnionPay Classic",  # Database format
        "Classic"  # Also try just Classic
    ])
```

## Answer
**The Union Pay Debit card issuance fee is BDT 575 per year.**

This data exists in the database:
- Charge Type: `ISSUANCE_ANNUAL_PRIMARY`
- Card Category: `DEBIT`
- Card Network: `UnionPay International`
- Card Product: `UnionPay Classic`
- Fee Amount: `575.0000 BDT`
- Fee Basis: `PER_YEAR`

## Next Steps
1. **Restart the chatbot service** to apply the fix:
   ```bash
   # If running in Docker
   docker-compose restart bank-chatbot
   
   # If running directly
   # Stop and restart the chatbot service
   ```

2. **Test the query again**:
   - Query: "What is the issuance fee for a Union pay Debit card ?"
   - Expected response: "The primary card annual fee is BDT 575 (per year)."

## Verification
Test scripts have been created:
- `test_unionpay_debit_fee.py` - Direct API test
- `test_unionpay_debit_client.py` - Client simulation test

Both tests confirm the fix is working correctly.

