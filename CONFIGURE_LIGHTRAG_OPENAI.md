# Configure LightRAG to Use OpenAI

## Overview

This guide shows you how to reconfigure LightRAG to use OpenAI instead of Ollama for document processing.

## Why Switch to OpenAI?

- ✅ **No local service needed** - No need to install/run Ollama
- ✅ **Simpler setup** - Just need OpenAI API key
- ✅ **Reliable** - OpenAI API is stable and well-maintained
- ✅ **Same functionality** - LightRAG works the same way

## Prerequisites

1. **OpenAI API Key**
   - Get one from: https://platform.openai.com/api-keys
   - Make sure you have credits/usage available

2. **Docker** (already installed)

## Quick Setup (Automated)

### Option 1: Use PowerShell Script

```powershell
# Run the reconfiguration script
.\reconfigure_lightrag_openai.ps1
```

The script will:
- Ask for your OpenAI API key
- Stop the current LightRAG container
- Create a new container with OpenAI configuration
- Verify it's running

### Option 2: Manual Configuration

#### Step 1: Stop Current Container

```powershell
docker stop LightRAG_New
docker rm LightRAG_New
```

#### Step 2: Create New Container with OpenAI

```powershell
docker run -d `
  --name LightRAG_New `
  -p 9262:9621 `
  -e LIGHTRAG_API_KEY=MyCustomLightRagKey456 `
  -e EMBEDDING_MODEL=text-embedding-3-small `
  -e EMBEDDING_FUNC_MAX_ASYNC=6 `
  -e EMBEDDING_BATCH_NUM=64 `
  -e LLM_BINDING=openai `
  -e LLM_MODEL=gpt-4o-mini `
  -e OPENAI_API_KEY=your_openai_api_key_here `
  -e EMBEDDING_BINDING=openai `
  -e EMBEDDING_MODEL=text-embedding-3-small `
  -e WORKING_DIR=/app/data/rag_storage `
  -e INPUT_DIR=/app/data/inputs `
  ghcr.io/hkuds/lightrag:v1.4.9
```

**Important:** Replace `your_openai_api_key_here` with your actual OpenAI API key.

#### Step 3: Verify Configuration

```powershell
# Check container is running
docker ps --filter "name=LightRAG_New"

# Test health
python -c "from connect_lightrag import LightRAGClient; client = LightRAGClient(); print(client.health_check())"
```

## Configuration Details

### Environment Variables

| Variable | Value | Description |
|----------|-------|-------------|
| `LLM_BINDING` | `openai` | Use OpenAI for LLM |
| `LLM_MODEL` | `gpt-4o-mini` | OpenAI model to use |
| `OPENAI_API_KEY` | `your_key` | Your OpenAI API key |
| `EMBEDDING_BINDING` | `openai` | Use OpenAI for embeddings |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model |
| `LIGHTRAG_API_KEY` | `MyCustomLightRagKey456` | LightRAG API key (unchanged) |

### Models Used

- **LLM**: `gpt-4o-mini` (cost-effective, fast)
- **Embeddings**: `text-embedding-3-small` (efficient, low cost)

## After Configuration

### 1. Wait for Container to Start

Give it 10-15 seconds to fully initialize.

### 2. Verify Health

```python
from connect_lightrag import LightRAGClient

client = LightRAGClient()
health = client.health_check()
print(health)
```

Should show:
- `llm_binding`: `openai` (not `ollama`)
- `status`: `ok`

### 3. Re-upload Documents

Now you can upload documents and they should process successfully:

```bash
# Upload management committee info
python upload_to_knowledge_base.py scraped_text/EBL_Management_Committee.txt --knowledge-base ebl_website

# Upload annual report
python upload_to_knowledge_base.py scraped_text/EBL-ANNUAL-REPORT-2024.txt --knowledge-base ebl_financial_reports
```

### 4. Trigger Scan

In LightRAG web UI:
- Click "Scan" button
- Documents should process successfully (no more Ollama errors)

## Troubleshooting

### Issue: Container won't start

**Check logs:**
```powershell
docker logs LightRAG_New
```

**Common causes:**
- Invalid OpenAI API key
- Port 9262 already in use
- Docker issues

### Issue: Still showing Ollama errors

**Verify configuration:**
```powershell
docker inspect LightRAG_New --format '{{range .Config.Env}}{{println .}}{{end}}' | Select-String "LLM_BINDING"
```

Should show: `LLM_BINDING=openai`

### Issue: OpenAI API errors

**Check:**
- API key is correct
- You have credits/usage available
- API key has proper permissions

## Cost Considerations

Using OpenAI will incur API costs:
- **Embeddings**: ~$0.02 per 1M tokens (very cheap)
- **LLM (gpt-4o-mini)**: ~$0.15 per 1M input tokens, $0.60 per 1M output tokens

For document processing:
- A 2MB document ≈ ~500K tokens
- Embedding cost: ~$0.01
- Processing cost: ~$0.10-0.50 depending on document complexity

**Total per document**: Usually under $1, often much less.

## Summary

✅ **Stop current container**
✅ **Create new container with OpenAI config**
✅ **Verify it's working**
✅ **Re-upload documents**
✅ **Documents should process successfully**

Your LightRAG will now use OpenAI instead of Ollama, and documents should process without connection errors!

