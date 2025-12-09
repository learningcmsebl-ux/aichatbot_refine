# LightRAG_New Container Connection

This project provides a connection client for the LightRAG_New Docker container.

## Container Information

- **Container Name**: LightRAG_New
- **Image**: ghcr.io/hkuds/lightrag:v1.4.9
- **Port**: 9262 (host) -> 9621 (container)
- **API Key**: MyCustomLightRagKey456
- **Status**: Running

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Python Client

```python
from connect_lightrag import LightRAGClient

# Initialize client
client = LightRAGClient(
    base_url="http://localhost:9262",
    api_key="MyCustomLightRagKey456"
)

# Check health
health = client.health_check()
print(health)

# Insert text documents
client.insert_text("This is a sample document about machine learning.")
client.insert_texts([
    "Document 1 content here...",
    "Document 2 content here..."
])

# Query the service
result = client.query("What is machine learning?")
print(result["response"])
print("References:", result["references"])

# Get detailed query data (entities, relationships, chunks)
detailed_result = client.query_data("What is machine learning?")
print(detailed_result)

# Get list of documents
documents = client.get_documents(page=1, page_size=10)
print(f"Total documents: {documents['pagination']['total_count']}")
```

### Run Test Connection

```bash
python connect_lightrag.py
```

## Available Methods

The `LightRAGClient` provides the following methods:

- `health_check()` - Check API server health and configuration
- `query(query, **kwargs)` - Query the RAG system (returns response and references)
- `query_data(query, **kwargs)` - Get detailed query results with entities, relationships, and chunks
- `insert_text(text, file_source=None)` - Insert a single text document
- `insert_texts(texts, file_sources=None)` - Insert multiple text documents
- `get_documents(page=1, page_size=50, status=None)` - Get paginated list of documents

## API Endpoints

The LightRAG API server provides:
- `GET /health` - Health check endpoint
- `POST /query` - Query endpoint (returns response and references)
- `POST /query/data` - Detailed query endpoint (returns entities, relationships, chunks)
- `POST /insert/text` - Insert single text document
- `POST /insert/texts` - Insert multiple text documents
- `GET /documents` - Get paginated document list

## Container Management

### View Container Logs
```bash
docker logs LightRAG_New
```

### Execute into Container
```bash
docker exec -it LightRAG_New /bin/bash
```

### Restart Container
```bash
docker restart LightRAG_New
```

