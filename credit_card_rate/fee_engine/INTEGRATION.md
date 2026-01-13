# Fee Engine Integration Guide

## Chatbot Integration

The chatbot has been updated to use the new fee-engine service for card fee calculations.

### Configuration

Add to your `.env` file:

```bash
FEE_ENGINE_URL=http://localhost:8003
```

### How It Works

1. **Query Detection**: The chatbot detects card rates queries using `_is_card_rates_query()`
2. **Fee Engine Call**: For card rates queries, it calls the fee-engine service via `FeeEngineClient`
3. **Query Mapping**: Natural language queries are mapped to standardized charge types:
   - "annual fee" → `ISSUANCE_ANNUAL_PRIMARY`
   - "cash withdrawal" → `CASH_WITHDRAWAL_EBL_ATM`
   - "lounge access" → `GLOBAL_LOUNGE_ACCESS_FEE`
   - etc.
4. **Card Info Extraction**: Card category, network, and product are extracted from the query
5. **Fee Calculation**: Fee engine calculates the fee using deterministic rules
6. **Response Formatting**: Results are formatted for LLM context

### Example Flow

**User Query**: "Mastercard World RFCD Debit annual fee"

1. Detected as card rates query
2. Mapped to charge type: `ISSUANCE_ANNUAL_PRIMARY`
3. Extracted card info:
   - Category: `DEBIT`
   - Network: `MASTERCARD`
   - Product: `World RFCD`
4. Fee engine calculates: `$11.5 USD`
5. Formatted response sent to LLM

### Fallback

If the fee-engine service is unavailable, the chatbot falls back to the old `card_rates_service` (port 8002).

### Testing

Test the integration:

```bash
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

### Charge Type Mapping

The `FeeEngineClient._map_query_to_charge_type()` method maps natural language to charge types:

- Annual/Yearly/Renewal fees → `ISSUANCE_ANNUAL_PRIMARY`
- Cash withdrawal/ATM → `CASH_WITHDRAWAL_EBL_ATM`
- Lounge access → `GLOBAL_LOUNGE_ACCESS_FEE`
- Interest rate → `INTEREST_RATE`
- Late payment → `LATE_PAYMENT`
- etc.

See `fee_engine_client.py` for the complete mapping.
