# Fix Embedding Dimension Mismatch Error

## Error

```
all the input array dimensions except for the concatenation axis must match exactly,
but along dimension 1, the array at index 0 has size 1024 and the array at index 1 has size 1536
```

## Root Cause

This error occurs when LightRAG tries to combine embeddings from different models:
- **1024 dimensions**: Likely from `text-embedding-3-small` (1536 dims) or another model
- **1536 dimensions**: From `text-embedding-3-small` (standard)

The mismatch happens because:
1. **Cached embeddings** from previous configuration (Ollama) might have different dimensions
2. **Mixed embedding models** in the same knowledge base
3. **Inconsistent configuration** between different processing steps

## Solution

### Option 1: Clear Storage and Re-upload (Recommended)

Clear the LightRAG storage to remove old embeddings:

```powershell
# Stop container
docker stop LightRAG_New

# Access container and clear storage
docker exec LightRAG_New sh -c "rm -rf /app/data/rag_storage/*"

# Or backup first, then clear
docker exec LightRAG_New sh -c "cd /app/data && mv rag_storage rag_storage.backup && mkdir -p rag_storage"

# Restart container
docker start LightRAG_New
```

**Warning**: This will delete all indexed documents. You'll need to re-upload everything.

### Option 2: Use Consistent Embedding Model

Ensure all documents use the same embedding model. The current configuration should be:
- `EMBEDDING_MODEL=text-embedding-3-small` (1536 dimensions)
- `EMBEDDING_BINDING=openai`

### Option 3: Delete Failed Document and Re-upload

1. **Delete the failed document** in LightRAG web UI
2. **Clear any cached data** for that knowledge base
3. **Re-upload** the document

## Quick Fix Steps

### Step 1: Delete Failed Document

In LightRAG web UI:
- Select the failed document
- Click "Clear" or delete it

### Step 2: Clear Knowledge Base Storage

```powershell
# Stop container
docker stop LightRAG_New

# Clear storage (backup first if needed)
docker exec LightRAG_New sh -c "cd /app/data && rm -rf rag_storage/* && mkdir -p rag_storage"

# Restart
docker start LightRAG_New
```

### Step 3: Wait and Re-upload

1. Wait 30 seconds for LightRAG to restart
2. Re-upload documents:
   ```bash
   python upload_to_knowledge_base.py scraped_text/EBL_Management_Committee.txt --knowledge-base ebl_website
   ```
3. Trigger scan
4. Should process successfully now

## Why This Happened

When you switched from Ollama to OpenAI:
- **Old embeddings** (from Ollama) had different dimensions
- **New embeddings** (from OpenAI) have 1536 dimensions
- LightRAG tried to combine them → dimension mismatch

## Prevention

To avoid this in the future:
- **Clear storage** when switching embedding models
- **Use consistent embedding model** across all documents
- **Don't mix** different embedding configurations

## Summary

✅ **Good news**: LightRAG is now using OpenAI (no Ollama errors!)
❌ **Issue**: Embedding dimension mismatch from old cached data
✅ **Solution**: Clear storage and re-upload documents

After clearing storage and re-uploading, documents should process successfully!

