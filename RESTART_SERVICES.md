# Restart Docker Services to Apply Women Platinum Fix

## Problem
The chatbot is still returning LightRAG responses instead of using the fee engine for Women Platinum queries.

## Solution
Both Docker containers need to be restarted to apply the code changes:

### 1. Restart Fee Engine Service (Docker)

**Windows PowerShell:**
```powershell
cd E:\Chatbot_refine\credit_card_rate

# Rebuild and restart the fee-engine container
docker-compose up -d --build fee-engine

# Or if you just want to restart without rebuild:
docker-compose restart fee-engine

# Check logs to verify it's working:
docker-compose logs -f fee-engine
```

**Alternative (using container name):**
```powershell
# Restart the container
docker restart fee-engine-service

# View logs
docker logs -f fee-engine-service
```

### 2. Restart Chatbot Service (Docker)

**Windows PowerShell:**
```powershell
cd E:\Chatbot_refine\bank_chatbot

# Rebuild and restart the chatbot container
docker-compose up -d --build chatbot

# Or if you just want to restart without rebuild:
docker-compose restart chatbot

# Check logs to verify it's working:
docker-compose logs -f chatbot
```

**Alternative (using container name):**
```powershell
# Restart the container
docker restart bank-chatbot-api

# View logs
docker logs -f bank-chatbot-api
```

### 3. Restart Both Services at Once

**If both are in the same docker-compose file:**
```powershell
cd E:\Chatbot_refine\bank_chatbot  # or wherever your main compose file is
docker-compose restart chatbot fee-engine
```

**Or rebuild both:**
```powershell
docker-compose up -d --build chatbot fee-engine
```

## What Was Fixed

1. ✅ Added "issuance charge" to charge type mapping
2. ✅ Added "women platinum" to product keywords
3. ✅ Fixed product variations to prioritize "Women  Platinum"
4. ✅ Fixed fee engine matching to prioritize exact matches over partial matches
5. ✅ Added fee_value ordering to select the correct record when multiple exact matches exist

## Expected Result After Restart

Query: "Issuance charge for a Women Platinum credit Card?"

**Should return:**
"The primary card annual fee is BDT 3,450 (per year)."

**NOT:**
"The EBL VISA Women Platinum Debit EMV Card..." (LightRAG response)

## Verification

After restarting, test with:
```bash
python verify_services.py
```

This will verify both services are returning the correct fee (BDT 3,450).

