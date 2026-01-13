# Card Rates Microservice

Microservice providing deterministic card fees, rates, and charges from the official card charges schedule.

## Overview

This microservice provides accurate, up-to-date card fee and rate information from the structured card charges schedule. It is designed to be called by the chatbot orchestrator for card-related queries, ensuring users receive precise fee/rate information.

## Architecture

- **Parser**: `parse_card_charges.py` - Converts text schedule to structured JSON
- **Service**: `card_rates_service.py` - FastAPI microservice with search endpoints
- **Data**: `card_charges.json` - Structured card charges data

## Setup

1. **Parse the schedule file** (whenever the source file is updated):
   ```bash
   cd credit_card_rate
   python parse_card_charges.py
   ```

2. **Start the service**:
   ```bash
   python card_rates_service.py
   ```
   
   Or using uvicorn directly:
   ```bash
   uvicorn card_rates_service:app --host 0.0.0.0 --port 8002 --reload
   ```

## API Endpoints

### Health Check
```
GET /health
```

### Search Card Rates
```
GET /rates/search?q={query}&limit={limit}
```
Search for card charges using natural language query.

**Examples:**
- `/rates/search?q=annual fee for visa platinum`
- `/rates/search?q=replacement fee credit card`
- `/rates/search?q=lounge access infinite card`
- `/rates/search?q=interest rate visa classic`

### Get by Charge Type
```
GET /rates/by-charge-type/{charge_type}?limit={limit}
```
Get all cards for a specific charge type.

### Get by Card
```
GET /rates/by-card?card_name={card_name}&limit={limit}
```
Get all charges for a specific card.

### Metadata
```
GET /metadata
```
Get metadata about available charge types and card categories.

## Integration with Chatbot

The service is automatically integrated with the chatbot orchestrator:

1. **Query Detection**: The orchestrator detects card-related queries using `_is_card_rates_query()`
2. **Service Call**: Calls the microservice before querying LightRAG
3. **Context Combination**: Combines deterministic card rates data with general RAG context

### Configuration

Add to `bank_chatbot/.env`:
```
CARD_RATES_URL=http://localhost:8002
```

## Data Structure

Each record contains:
- `card_full_name`: Full name of the card
- `category`: Card category (Credit Card, Debit Card, Prepaid Card)
- `network`: Card network (VISA, Mastercard, etc.)
- `product`: Card product (Classic, Gold, Platinum, etc.)
- `charge_type`: Type of charge/fee
- `amount_raw`: Fee/rate amount (may include special values like "Unlimited", "According to Note X")

## Charge Types Supported

- Annual/Issuance/Renewal Fees
- Supplementary Card Fees
- Replacement Fees
- PIN Replacement Fees
- Interest Rates
- Late Payment Fees
- Overlimit Fees
- Cash Advance/Withdrawal Fees
- Lounge Access (International/Domestic/Global)
- Transaction Alert Fees
- Duplicate Statement Fees
- Certificate Fees
- Chequebook Fees
- And many more...

## Notes

- The service uses in-memory data for fast lookups
- Data is loaded on startup from `card_charges.json`
- Run the parser script whenever the source text file is updated
- The service handles special values like "Unlimited", "According to Note X", percentages, and multiple currencies

