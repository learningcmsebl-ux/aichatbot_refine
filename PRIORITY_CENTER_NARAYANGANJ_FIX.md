# Priority Center Information for Narayanganj City - Fix Guide

## Problem

The chatbot is responding with:
> "I'm sorry, but the context provided does not contain specific information about the number of Priority Centers in Narayanganj City. Please contact Eastern Bank PLC. directly for the most accurate and up-to-date information."

This is because the LightRAG knowledge base doesn't have Priority Center data for Narayanganj City.

## Solution

I've updated the system to support adding Priority Center information for multiple cities, including Narayanganj.

### Files Updated/Created

1. **`add_priority_centers_to_lightrag.py`** (Updated)
   - Now supports multiple cities (Narayanganj, Sylhet, Dhaka, Chittagong)
   - Can add data for a specific city or all cities
   - Includes template structure for Priority Center data

2. **`find_priority_centers_data.py`** (New)
   - Helper script to find Priority Center data from phonebook
   - Provides guidance on where to find data
   - Shows how to add data to the system

## Steps to Fix

### Step 1: Gather Priority Center Data for Narayanganj

You need to find:
- **Count**: How many Priority Centers are in Narayanganj City?
- **Details** (for each center):
  - Name
  - Address
  - Phone number
  - Email (if available)

**Data Sources to Check:**
- EBL website branch locator
- Annual reports (may have Priority Center counts by city)
- Internal branch database
- Customer service department
- Phonebook (run `python find_priority_centers_data.py --city Narayanganj`)

### Step 2: Update the Script with Actual Data

Edit `add_priority_centers_to_lightrag.py` and update the `PRIORITY_CENTERS_DATA` dictionary:

```python
PRIORITY_CENTERS_DATA = {
    "Narayanganj": {
        "count": 1,  # Update with actual count
        "centers": [
            {
                "name": "Priority Center Name",
                "address": "Full address in Narayanganj",
                "phone": "Phone number",
                "email": "Email if available"
            }
        ],
        "notes": "Priority Centers in Narayanganj City provide premium banking services to Priority Banking customers."
    },
    # ... other cities
}
```

### Step 3: Add Data to LightRAG

Run the script to add Priority Center data for Narayanganj:

```bash
python add_priority_centers_to_lightrag.py --city Narayanganj
```

Or add all cities at once:

```bash
python add_priority_centers_to_lightrag.py
```

### Step 4: Verify

After adding the data, wait a few moments for LightRAG to process it, then test:

```
"How many Priority centers are there in Narayanganj City?"
```

You can also check if the data was added:

```bash
python check_priority_centers_in_lightrag.py
```

## Current Status

- ✅ Script updated to support Narayanganj
- ✅ Query routing already handles Narayanganj (in `chat_orchestrator.py` line 1664)
- ⚠️ **Missing**: Actual Priority Center data for Narayanganj City

## Quick Test

To test if the system is ready (once data is added):

```bash
# Check if data exists
python check_priority_centers_in_lightrag.py

# Test query
python test_priority_center_query.py
```

## Notes

- The chatbot routes Priority Center queries to LightRAG (not phonebook)
- The query enhancement logic in `chat_orchestrator.py` already handles Narayanganj queries
- Once data is added to LightRAG, the chatbot will be able to answer Priority Center questions for Narayanganj









