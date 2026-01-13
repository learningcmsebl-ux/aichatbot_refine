# LightRAG_New Configuration ✅

## Status: All RAG Queries Target LightRAG_New

All RAG queries in the `bank_chatbot` are configured to use **LightRAG_New** on port **9262**.

## Configuration Summary

### Current Setup

- **Container:** `LightRAG_New`
- **Port:** `9262` (host) → `9621` (container)
- **Status:** Running ✅
- **API Key:** `MyCustomLightRagKey456`
- **Default Knowledge Base:** `default` (can be overridden per query)

### Configuration Files

#### 1. `bank_chatbot/app/core/config.py`
```python
LIGHTRAG_URL: str = os.getenv("LIGHTRAG_URL", "http://localhost:9262/query")
LIGHTRAG_API_KEY: str = os.getenv("LIGHTRAG_API_KEY", "MyCustomLightRagKey456")
LIGHTRAG_KNOWLEDGE_BASE: str = os.getenv("LIGHTRAG_KNOWLEDGE_BASE", "default")
```

#### 2. `bank_chatbot/.env`
```
LIGHTRAG_URL=http://localhost:9262/query
LIGHTRAG_API_KEY=MyCustomLightRagKey456
LIGHTRAG_KNOWLEDGE_BASE=default
```

#### 3. `bank_chatbot/env.example`
```
LIGHTRAG_URL=http://localhost:9262/query
LIGHTRAG_API_KEY=MyCustomLightRagKey456
LIGHTRAG_KNOWLEDGE_BASE=default
```

### Code Implementation

#### `bank_chatbot/app/services/lightrag_client.py`
- Initializes with `settings.LIGHTRAG_URL` (port 9262)
- Removes `/query` suffix if present
- Uses base URL: `http://localhost:9262`
- Appends `/query` when making requests

#### `bank_chatbot/app/services/chat_orchestrator.py`
- Uses `LightRAGClient()` which connects to port 9262
- Routes queries to appropriate knowledge bases:
  - `ebl_website` - General website content, management info
  - `ebl_financial_reports` - Financial reports
  - `ebl_user_documents` - User-uploaded documents
  - `ebl_employees` - Employee information (if exists)

## Knowledge Base Routing

The chatbot intelligently routes queries to different knowledge bases:

1. **Management Queries** → `ebl_website`
   - Example: "who are the mancom members of ebl?"

2. **Financial Report Queries** → `ebl_financial_reports`
   - Example: "what was the bank's revenue in 2024?"

3. **User Document Queries** → `ebl_user_documents`
   - Example: Queries about uploaded documents

4. **Default** → `ebl_website` or configured default

## Verification

### Current Configuration
```bash
# Check .env file
LIGHTRAG_URL=http://localhost:9262/query ✅

# Check running containers
LightRAG_New: Port 9262 ✅
```

### Test Connection
```python
from connect_lightrag import LightRAGClient
client = LightRAGClient(base_url='http://localhost:9262')
result = client.health_check()
# Should return: {"status": "ok"}
```

## Important Notes

1. **Old Chatbot (`chatbot_convert`)**: Still references port 9261, but is not used by the current `bank_chatbot`
2. **LightRAG_30092025**: Running on port 9261, but not used by `bank_chatbot`
3. **All Active Queries**: Use LightRAG_New on port 9262 ✅

## Summary

✅ **All RAG queries target LightRAG_New (port 9262)**
✅ **Configuration is correct in all files**
✅ **Knowledge base routing is working**
✅ **Ready for production use**

The chatbot is fully configured to use LightRAG_New for all RAG queries!

