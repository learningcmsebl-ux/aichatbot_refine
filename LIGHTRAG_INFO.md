# LightRAG Setup Information

## What is LightRAG?

**LightRAG** is a lightweight Retrieval-Augmented Generation (RAG) system that combines:
- **Knowledge Graph (KG)**: Extracts entities and relationships from documents
- **Document Chunks (DC)**: Stores original text chunks for retrieval
- **Hybrid Search**: Uses both KG and document chunks for better context retrieval

It's designed to be simple, fast, and efficient for RAG applications.

## Your Current Setup

### Containers Running

You have **2 LightRAG containers** running:

1. **LightRAG_New** (Primary)
   - **Port**: `9262` (host) → `9621` (container)
   - **Status**: ✅ Running
   - **Image**: `ghcr.io/hkuds/lightrag:v1.4.9`
   - **API Key**: `MyCustomLightRagKey456`

2. **LightRAG_30092025** (Secondary/Old)
   - **Port**: `9261` (host) → `9621` (container)
   - **Status**: ✅ Running
   - **Image**: `ghcr.io/hkuds/lightrag:v1.4.9`
   - **API Key**: `MyCustomLightRagKey456`

### Version Information

- **Version**: `v1.4.9`
- **Source**: GitHub Container Registry (`ghcr.io/hkuds/lightrag`)
- **Repository**: https://github.com/HKUDS/LightRAG
- **Paper**: "[EMNLP2025] LightRAG: Simple and Fast Retrieval-Augmented Generation"

### Configuration

**Environment Variables:**
- `LIGHTRAG_API_KEY`: `MyCustomLightRagKey456`
- `EMBEDDING_MODEL`: `text-embedding-3-small`
- `EMBEDDING_FUNC_MAX_ASYNC`: `6`
- `EMBEDDING_BATCH_NUM`: `64`
- `WORKING_DIR`: `/app/data/rag_storage`
- `INPUT_DIR`: `/app/data/inputs`

**LLM Configuration** (from health check):
- `llm_binding`: `ollama`
- `llm_binding_host`: `http://localhost:11434`
- `llm_model`: `mistral-nemo:latest`
- `embedding_binding`: `ollama`
- `embedding_binding_host`: `http://localhost:11434`
- `embedding_model`: `text-embedding-3-small`

**Storage Configuration:**
- `kv_storage`: `JsonKVStorage`
- `doc_status_storage`: `JsonDocStatusStorage`
- `graph_storage`: `NetworkXStorage`
- `vector_storage`: `NanoVectorDBStorage`

## Knowledge Bases

Your setup supports **multiple knowledge bases**:

1. **`ebl_website`** - Website scraped content (30+ documents)
2. **`ebl_pdf`** - PDF documents (Annual Report 2024)
3. **`default`** - Default knowledge base

### Knowledge Base Usage

**In your application:**
```python
# Default knowledge base
LIGHTRAG_KNOWLEDGE_BASE=ebl_website

# Or specify per request
{
  "chatInput": "query",
  "knowledgeBase": "ebl_website"
}
```

## API Endpoints

### Health Check
```
GET http://localhost:9262/health
```

### Query
```
POST http://localhost:9262/query
Headers:
  X-API-Key: MyCustomLightRagKey456
  Content-Type: application/json
Body:
{
  "query": "your question",
  "mode": "mix",  // Gets both KG and document chunks
  "top_k": 5,
  "chunk_top_k": 10,
  "include_references": true,
  "only_need_context": true
}
```

### Query with Detailed Data
```
POST http://localhost:9262/query/data
```
Returns entities, relationships, chunks, and references.

### Insert Text
```
POST http://localhost:9262/insert/text
Body:
{
  "text": "document content",
  "file_source": "optional source name"
}
```

## How LightRAG Works

### 1. Document Processing
- Documents are uploaded to LightRAG
- LightRAG extracts:
  - **Entities**: Key concepts, people, places, products
  - **Relationships**: Connections between entities
  - **Chunks**: Original text segments

### 2. Query Processing
When you query LightRAG:
1. **Entity Retrieval**: Finds relevant entities from knowledge graph
2. **Relationship Retrieval**: Gets relationships between entities
3. **Chunk Retrieval**: Retrieves original document chunks
4. **Context Assembly**: Combines all into structured context

### 3. Response Format
LightRAG returns:
```
Entities Data From Knowledge Graph(KG):
- Entity 1: description
- Entity 2: description

Relationships Data From Knowledge Graph(KG):
- Entity1 → relationship → Entity2 (details)

Original Texts From Document Chunks(DC):
- Chunk 1: text from document
- Chunk 2: text from document
```

## Connection Client

I created a Python client (`connect_lightrag.py`) that provides:

```python
from connect_lightrag import LightRAGClient

client = LightRAGClient(
    base_url="http://localhost:9262",
    api_key="MyCustomLightRagKey456"
)

# Health check
health = client.health_check()

# Query
result = client.query("What is LightRAG?")

# Query with detailed data
detailed = client.query_data("What is LightRAG?")

# Insert text
client.insert_text("Document content here")

# Get documents
docs = client.get_documents(page=1, page_size=10)
```

## Performance Characteristics

- **Query Mode**: `mix` (KG + document chunks)
- **Entity Retrieval**: `top_k: 5`
- **Chunk Retrieval**: `chunk_top_k: 10`
- **Caching**: Redis (1 hour TTL)
- **Response Time**: ~2-4 seconds (uncached), ~50-100ms (cached)

## Integration with Your Chatbot

In your old chatbot (`chatbot_convert/main.py`):
- LightRAG is queried for banking/product questions
- Results are cached in Redis
- Context is formatted and sent to OpenAI
- Small talk queries skip LightRAG

## Key Features

1. **Hybrid Retrieval**: Combines knowledge graph and document chunks
2. **Multiple Knowledge Bases**: Separate storage for different document types
3. **Fast Queries**: Optimized for speed with caching
4. **Structured Output**: Returns entities, relationships, and chunks
5. **API-Based**: RESTful API for easy integration

## Documentation

- **GitHub**: https://github.com/HKUDS/LightRAG
- **Paper**: "LightRAG: Simple and Fast Retrieval-Augmented Generation" (EMNLP 2025)
- **Docker Image**: `ghcr.io/hkuds/lightrag:v1.4.9`

## Container Management

### View Status
```powershell
docker ps --filter "name=LightRAG"
```

### View Logs
```powershell
docker logs LightRAG_New
docker logs LightRAG_30092025
```

### Restart Container
```powershell
docker restart LightRAG_New
```

### Access Container Shell
```powershell
docker exec -it LightRAG_New /bin/bash
```

## Testing

Test the connection:
```powershell
python connect_lightrag.py
```

This will:
1. Check health status
2. Test query endpoint
3. Show configuration details

---

**Summary**: You're using LightRAG v1.4.9 in Docker containers, configured with Ollama for LLM/embeddings, supporting multiple knowledge bases, and optimized for fast retrieval with Redis caching.

