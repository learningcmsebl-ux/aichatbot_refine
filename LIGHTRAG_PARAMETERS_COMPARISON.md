# LightRAG Parameters Comparison

## Parameters from Other LightRAG Instance (LightRAG_30092025)

Based on the UI screenshot:

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Query Mode** | `Hybrid` | Combines keyword + semantic search |
| **Response Format** | `Multiple Paragraphs` | Structured response format |
| **KG Top K** | `8` | Top 8 entities from knowledge graph |
| **Chunk Top K** | `5` | Top 5 document chunks |
| **Max Entity Tokens** | `2500` | Maximum tokens for entities |
| **Max Relation Tokens** | `3500` | Maximum tokens for relations |
| **Max Total Tokens** | `12000` | Overall maximum tokens |
| **Enable Rerank** | ✅ `true` | Reranking enabled |
| **Only Need Context** | ❌ `false` | Returns full response, not just context |
| **Only Need Prompt** | ✅ `true` | Prompt-only mode enabled |
| **Stream Response** | ✅ `true` | Streaming enabled |

## Current Chatbot Parameters (LightRAG_New)

From `bank_chatbot/app/services/chat_orchestrator.py`:

| Parameter | Current Value | Should Be |
|-----------|---------------|-----------|
| **mode** | `"mix"` | `"hybrid"` or keep `"mix"` |
| **top_k** | `5` | `8` (KG Top K) |
| **chunk_top_k** | `10` | `5` (Chunk Top K) |
| **only_need_context** | `True` | `False` (to get full response) |
| **max_entity_tokens** | Not set | `2500` |
| **max_relation_tokens** | Not set | `3500` |
| **max_total_tokens** | Not set | `12000` |
| **enable_rerank** | Not set | `true` |
| **only_need_prompt** | Not set | `true` |
| **stream** | Not set | `true` |

## Key Differences

1. **KG Top K**: Chatbot uses `5`, other instance uses `8` (more entities)
2. **Chunk Top K**: Chatbot uses `10`, other instance uses `5` (fewer chunks)
3. **Only Need Context**: Chatbot uses `True`, other instance uses `False` (full response)
4. **Missing Parameters**: Chatbot doesn't set token limits, rerank, or prompt-only mode

## Recommendation

Update the chatbot to match the other instance's parameters for consistency and potentially better results.

