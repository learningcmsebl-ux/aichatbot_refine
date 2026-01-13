# LightRAG Error Troubleshooting

## Issue: Empty Error Message

When querying LightRAG, you see:
```
LightRAG query error: 
LightRAG query failed: 
```

But no actual error details.

## Root Causes

### 1. Knowledge Base Empty
The knowledge base `ebl_financial_reports` exists but has no documents.

**Solution:**
```bash
# Upload financial reports
python download_and_upload_financial_reports.py --years 2024 2023 2022
```

### 2. LightRAG URL Configuration
The `LIGHTRAG_URL` might include `/query` suffix, causing issues.

**Check:**
```env
# Should be:
LIGHTRAG_URL=http://localhost:9262

# NOT:
LIGHTRAG_URL=http://localhost:9262/query
```

### 3. Knowledge Base Not Indexed
Documents uploaded but not indexed yet.

**Solution:**
- Check LightRAG logs: `docker logs LightRAG_New`
- Trigger indexing if needed (check LightRAG API docs)

### 4. API Endpoint Mismatch
LightRAG API endpoint might be different.

**Test:**
```bash
python test_lightrag_knowledge_base.py
```

## Improved Error Handling

I've updated the error handling to show more details:

**Before:**
```
LightRAG query error: 
```

**After:**
```
LightRAG HTTP error 404: Knowledge base not found
Request URL: http://localhost:9262/query
Request data: {'query': '...', 'knowledge_base': 'ebl_financial_reports', ...}
```

## Debugging Steps

### Step 1: Check Knowledge Base Status
```bash
python test_lightrag_knowledge_base.py
```

### Step 2: Check LightRAG Logs
```bash
docker logs LightRAG_New --tail 50
```

### Step 3: Test Direct Query
```python
from connect_lightrag import LightRAGClient

client = LightRAGClient()
result = client.query(
    query="What was the bank's revenue in 2024?",
    knowledge_base="ebl_financial_reports"
)
```

### Step 4: Check Configuration
```bash
# In bank_chatbot/.env
LIGHTRAG_URL=http://localhost:9262  # Should NOT include /query
LIGHTRAG_API_KEY=MyCustomLightRagKey456
LIGHTRAG_KNOWLEDGE_BASE=ebl_website  # Default
```

## Common Solutions

### Solution 1: Upload Documents
If knowledge base is empty:
```bash
python download_and_upload_financial_reports.py
```

### Solution 2: Fix URL Configuration
If URL is wrong:
```env
# bank_chatbot/.env
LIGHTRAG_URL=http://localhost:9262
```

### Solution 3: Use Default Knowledge Base
If `ebl_financial_reports` doesn't work, try default:
```python
# Temporarily route to default
knowledge_base = "default"  # or "ebl_website"
```

## Next Steps

1. ✅ Check error logs (now shows more details)
2. ✅ Verify knowledge base has documents
3. ✅ Test with test script
4. ✅ Upload financial reports if needed

## Summary

The routing is working correctly - it detected the financial query and routed to `ebl_financial_reports`. The issue is likely:
- Knowledge base is empty (no documents uploaded)
- Or LightRAG API configuration issue

After restarting the chatbot, you'll see more detailed error messages that will help identify the exact issue.

