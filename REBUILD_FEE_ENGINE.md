# Rebuild Fee Engine Service - Instructions

## Why Rebuild?
The fee engine service is running in Docker. When you make code changes, you need to **rebuild** the Docker image, not just restart it. A restart only reloads the existing image.

## Steps to Rebuild

### Option 1: Rebuild using Docker Compose (Recommended)

```powershell
# Navigate to the credit_card_rate directory
cd E:\Chatbot_refine\credit_card_rate

# Stop the service
docker-compose stop fee-engine

# Rebuild the image (this will pick up your code changes)
docker-compose build fee-engine

# Start the service with the new image
docker-compose up -d fee-engine

# Check logs to verify it started correctly
docker-compose logs -f fee-engine
```

### Option 2: Rebuild and Restart in One Command

```powershell
cd E:\Chatbot_refine\credit_card_rate

# Rebuild and restart in one command
docker-compose up -d --build fee-engine

# Check logs
docker-compose logs -f fee-engine
```

### Option 3: Using Docker Commands (if not using docker-compose)

```powershell
# Stop and remove the container
docker stop fee-engine-service
docker rm fee-engine-service

# Rebuild the image
cd E:\Chatbot_refine\credit_card_rate
docker build -t fee-engine -f fee_engine/Dockerfile .

# Run the container
docker run -d --name fee-engine-service -p 8003:8003 fee-engine
```

## Verify the Fix

After rebuilding, test the Visa Platinum annual fee:

```powershell
cd E:\Chatbot_refine
python test_visa_platinum_annual_fee.py
```

Expected output:
```
[SUCCESS] Fee calculation successful!
[SUCCESS] RESULT: Visa Platinum Card Annual Fee
   Amount: 5750.0 BDT
   Basis: PER_YEAR
```

## What Was Fixed

The SQL syntax error in `fee_engine_service.py` was fixed:
- Changed `func.position("/" in CardFeeMaster.card_product)` to `CardFeeMaster.card_product.like("%/%")`
- This fix was applied in 4 locations

The Visa Platinum Card annual fee is **BDT 5,750 per year**.

