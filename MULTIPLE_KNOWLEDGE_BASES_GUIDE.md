# Multiple Knowledge Bases Setup Guide

## Overview

This guide shows you how to create and manage separate knowledge bases in LightRAG to avoid confusion between different document types.

## Recommended Knowledge Base Structure

1. **`ebl_financial_reports`** - Bank financial reports, annual reports, quarterly reports
2. **`ebl_user_documents`** - User-uploaded documents, custom documents
3. **`ebl_website`** - Website content (existing)
4. **`ebl_pdf`** - General PDF documents (existing)
5. **`default`** - Default knowledge base for general queries

## Step 1: Create Knowledge Bases in LightRAG

Knowledge bases are created automatically when you upload documents to them. You don't need to create them explicitly.

### Upload Financial Reports

```python
from connect_lightrag import LightRAGClient

client = LightRAGClient(
    base_url="http://localhost:9262",
    api_key="MyCustomLightRagKey456"
)

# Upload financial report documents
# Method 1: Insert text directly
client.insert_text(
    text="Financial report content here...",
    file_source="annual_report_2024.pdf"
)

# Method 2: Upload multiple documents
reports = [
    "Annual Report 2024 content...",
    "Quarterly Report Q1 2024 content...",
    "Financial Statement 2024 content..."
]

client.insert_texts(
    texts=reports,
    file_sources=["annual_report_2024.pdf", "q1_2024.pdf", "financial_statement_2024.pdf"]
)
```

**Note**: When inserting, you need to specify the `knowledge_base` parameter in the query, but for insertion, LightRAG uses the knowledge base from the request context or creates a new one.

### Upload User Documents

```python
# Upload user-defined documents
user_docs = [
    "User document 1 content...",
    "User document 2 content...",
    "Custom document content..."
]

client.insert_texts(
    texts=user_docs,
    file_sources=["user_doc_1.pdf", "user_doc_2.pdf", "custom_doc.pdf"]
)
```

## Step 2: Query Specific Knowledge Bases

### Method 1: Specify in Query

```python
# Query financial reports knowledge base
result = client.query(
    query="What was the bank's revenue in 2024?",
    knowledge_base="ebl_financial_reports"
)

# Query user documents knowledge base
result = client.query(
    query="What does the custom document say?",
    knowledge_base="ebl_user_documents"
)
```

### Method 2: Use in Chatbot API

```json
{
  "query": "What was the bank's profit last year?",
  "knowledge_base": "ebl_financial_reports"
}
```

## Step 3: Smart Routing in Chatbot

The chatbot can automatically route queries to the right knowledge base based on keywords:

- **Financial queries** → `ebl_financial_reports`
- **User document queries** → `ebl_user_documents`
- **General banking queries** → `ebl_website` or `default`

## Step 4: Upload Scripts

I'll create helper scripts to make uploading easier.

## Benefits

✅ **No Confusion**: Financial reports won't mix with user documents
✅ **Faster Queries**: Smaller knowledge bases = faster searches
✅ **Better Accuracy**: Relevant documents only
✅ **Easy Management**: Update one knowledge base without affecting others
✅ **Cost Efficient**: Only index what you need

## Next Steps

1. Create upload scripts for each knowledge base type
2. Update chatbot to route queries intelligently
3. Add knowledge base management utilities

