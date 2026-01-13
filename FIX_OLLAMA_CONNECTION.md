# Fix Ollama Connection Issue

## Problem

LightRAG document processing is failing with error:
```
Failed to connect to ollama. Please check that ollama is downloaded, running and accessible.
```

## Root Cause

LightRAG is configured to use **Ollama** (local LLM service) for document processing, but Ollama is not running or not accessible at `http://localhost:11434`.

## Current LightRAG Configuration

From your setup:
- `llm_binding`: `ollama`
- `llm_binding_host`: `http://localhost:11434`
- `llm_model`: `mistral-nemo:latest`
- `embedding_binding`: `ollama`
- `embedding_binding_host`: `http://localhost:11434`
- `embedding_model`: `text-embedding-3-small`

## Solutions

### Solution 1: Start Ollama Service (Recommended if you want local processing)

#### Option A: Install and Run Ollama Locally

1. **Download Ollama:**
   - Visit: https://ollama.com/download
   - Download for Windows
   - Install it

2. **Start Ollama:**
   ```powershell
   # Ollama should start automatically after installation
   # Or start it manually:
   ollama serve
   ```

3. **Pull Required Model:**
   ```powershell
   ollama pull mistral-nemo:latest
   ```

4. **Verify Ollama is Running:**
   ```powershell
   # Test connection
   curl http://localhost:11434/api/tags
   ```

5. **Restart LightRAG Container:**
   ```powershell
   docker restart LightRAG_New
   ```

#### Option B: Run Ollama in Docker

```powershell
# Run Ollama in Docker
docker run -d -p 11434:11434 --name ollama ollama/ollama

# Pull model
docker exec ollama ollama pull mistral-nemo:latest
```

### Solution 2: Configure LightRAG to Use OpenAI (Alternative)

If you don't want to use Ollama, you can configure LightRAG to use OpenAI instead:

1. **Stop LightRAG Container:**
   ```powershell
   docker stop LightRAG_New
   ```

2. **Restart with OpenAI Configuration:**
   ```powershell
   docker run -d \
     --name LightRAG_New \
     -p 9262:9621 \
     -e LIGHTRAG_API_KEY=MyCustomLightRagKey456 \
     -e EMBEDDING_MODEL=text-embedding-3-small \
     -e LLM_BINDING=openai \
     -e LLM_MODEL=gpt-4o-mini \
     -e OPENAI_API_KEY=your_openai_api_key \
     -e EMBEDDING_BINDING=openai \
     -e EMBEDDING_MODEL=text-embedding-3-small \
     -e OPENAI_API_KEY=your_openai_api_key \
     ghcr.io/hkuds/lightrag:v1.4.9
   ```

   **Note:** Replace `your_openai_api_key` with your actual OpenAI API key.

### Solution 3: Check Current LightRAG Configuration

Check what LightRAG is currently configured to use:

```powershell
docker inspect LightRAG_New | Select-String -Pattern "LLM|OLLAMA|OPENAI" -Context 2
```

## Quick Fix Steps

### If You Want to Use Ollama:

1. **Install Ollama:**
   - Download from: https://ollama.com/download
   - Install and start it

2. **Pull Model:**
   ```powershell
   ollama pull mistral-nemo:latest
   ```

3. **Verify:**
   ```powershell
   curl http://localhost:11434/api/tags
   ```

4. **Re-upload Document:**
   - Delete the failed document in LightRAG web UI
   - Upload again: `python upload_to_knowledge_base.py scraped_text/EBL_Management_Committee.txt --knowledge-base ebl_website`
   - Trigger scan

### If You Want to Use OpenAI:

1. **Get OpenAI API Key** (if you don't have one)
2. **Restart LightRAG with OpenAI config** (see Solution 2 above)
3. **Re-upload document**

## Verification

After fixing, check LightRAG health:

```python
from connect_lightrag import LightRAGClient

client = LightRAGClient()
health = client.health_check()
print(health)
```

Should show:
- `llm_binding`: Connected
- `embedding_binding`: Connected

## Recommendation

**For your use case**, I recommend:
- **Use OpenAI** if you already have an API key (simpler, no local service needed)
- **Use Ollama** if you want local processing (no API costs, but requires running Ollama service)

## Summary

The document failed because LightRAG needs Ollama (or OpenAI) to process documents. You need to either:
1. ✅ Start Ollama service, OR
2. ✅ Configure LightRAG to use OpenAI

Once fixed, re-upload the document and it should process successfully.

