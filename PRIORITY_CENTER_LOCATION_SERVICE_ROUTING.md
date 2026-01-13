# Priority Center Queries - Location Service Routing

## Overview

All priority center location and address-related queries are now **exclusively routed to the location service**, not LightRAG. This ensures accurate, real-time data from the normalized location database.

## Changes Made

### 1. Enhanced Location Query Detection

Updated `_is_location_query()` method in `chat_orchestrator.py` to detect all priority center queries, including:

- **Count queries**: "how many priority center does ebl have"
- **Number queries**: "number of priority centers"
- **Location queries**: "where are priority centers", "location of priority centers"
- **Address queries**: "address of priority center"
- **General queries**: "priority center information", "tell me about priority center"

### 2. Added Priority Center Count Detection Patterns

Added regex patterns to catch count/number queries:
- `\bhow\s+many\s+priority\s+(center|centre)`
- `\bnumber\s+of\s+priority\s+(center|centre)`
- `\bcount\s+of\s+priority\s+(center|centre)`
- `\bpriority\s+(center|centre).*\b(how many|number|count|total|does.*have|has)`

### 3. Expanded Priority Center Keywords

Added additional keyword variations:
- `priority centers` (plural)
- `priority centres` (British spelling)
- `priority banking centers`
- `priority banking centres`

## Routing Flow

```
User Query: "how many priority center does ebl have"
    ↓
_is_location_query() detects "priority center" + "how many"
    ↓
Query routed to Location Service (line 2134-2136)
    ↓
Location Service returns: 4 Priority Centers
    ↓
Response generated from location service data only
    ↓
NO LightRAG query is made
```

## Current Priority Center Data

According to the location service database:
- **Total Priority Centers**: 4
- **Locations**:
  1. Dhaka - 1 Priority Center
  2. Chittagong - 1 Priority Center
  3. North and South - 1 Priority Center
  4. Sylhet and Narayangonj - 1 Priority Center

## Test Results

All tested priority center queries are correctly detected as location queries:
- ✅ "how many priority center does ebl have"
- ✅ "how many priority centers does ebl have"
- ✅ "number of priority centers"
- ✅ "count of priority centers"
- ✅ "priority centers in dhaka"
- ✅ "where are priority centers"
- ✅ "location of priority centers"
- ✅ "address of priority center"
- ✅ "tell me about priority center"
- ✅ "priority center information"
- ✅ "priority center locations"

## Verification

Run the test script to verify routing:
```bash
python test_priority_center_routing.py
```

## Important Notes

1. **No LightRAG for Priority Centers**: All priority center location/address queries go to location service only
2. **Real-time Data**: Location service provides up-to-date data from normalized PostgreSQL database
3. **Early Routing**: Location queries are checked BEFORE any LightRAG routing (line 2134-2136)
4. **Exclusive Context**: When location query is detected, ONLY location service context is used - no LightRAG, no knowledge base

## Files Modified

1. `bank_chatbot/app/services/chat_orchestrator.py`
   - Enhanced `_is_location_query()` method
   - Added priority center count detection patterns
   - Expanded priority center keywords

## Related Files

- `location_service/location_service.py` - Location service API
- `bank_chatbot/app/services/location_client.py` - Location service client
- `get_priority_centers_count.py` - Script to query location service for priority center count
- `test_priority_center_routing.py` - Test script to verify routing








