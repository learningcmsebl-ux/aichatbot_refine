# LightRAG Instances - Which One Was Checked?

## LightRAG Containers Running

There are **2 LightRAG containers** currently running:

### 1. **LightRAG_New** (Port 9262)
- **Container Name:** `LightRAG_New`
- **Host Port:** `9262` → Container Port: `9621`
- **Status:** Up 8 minutes
- **This is what I tested!** ✅

### 2. **LightRAG_30092025** (Port 9261)
- **Container Name:** `LightRAG_30092025`
- **Host Port:** `9261` → Container Port: `9621`
- **Status:** Up 5 hours
- **Older instance**

## Which One I Checked

When I tested the management committee query, I used:
```python
client = LightRAGClient(base_url='http://localhost:9262')
```

**This means I tested `LightRAG_New` on port 9262.** ✅

## Which One the Chatbot Uses

The chatbot's default configuration:
- **Default URL:** `http://localhost:9262/query` (from `config.py`)
- **This points to:** `LightRAG_New` ✅

So the chatbot is configured to use the **same instance** I tested!

## Configuration Details

### Chatbot Config (`bank_chatbot/app/core/config.py`)
```python
LIGHTRAG_URL: str = os.getenv("LIGHTRAG_URL", "http://localhost:9262/query")
LIGHTRAG_API_KEY: str = os.getenv("LIGHTRAG_API_KEY", "MyCustomLightRagKey456")
```

### Test Script (`connect_lightrag.py`)
```python
def __init__(self, base_url: str = "http://localhost:9262", ...):
```

## Summary

✅ **I tested:** `LightRAG_New` (port 9262)
✅ **Chatbot uses:** `LightRAG_New` (port 9262)
✅ **They match!** The test result applies to the chatbot.

## Management Committee Data

The management committee information is in `LightRAG_New`:
- **Knowledge Base:** `ebl_website`
- **Source:** Scraped from `https://www.ebl.com.bd/management`
- **Status:** ✅ Successfully uploaded and queryable
- **Test Result:** ✅ Successfully retrieved 25 MANCOM members

## Note

If you want to use the older instance (`LightRAG_30092025` on port 9261), you would need to:
1. Update `.env` file: `LIGHTRAG_URL=http://localhost:9261/query`
2. Restart the chatbot

But currently, both the test and chatbot are using `LightRAG_New` on port 9262.

