# Knowledge Base Smart Routing

## Overview

Your chatbot now automatically routes queries to the appropriate knowledge base based on query content. This prevents confusion between different document types.

## Knowledge Base Structure

### 1. `ebl_financial_reports`
**Purpose**: Bank financial reports, annual reports, quarterly reports

**Detected by keywords:**
- financial report, annual report, quarterly report
- revenue, profit, loss, income statement, balance sheet
- cash flow, earnings, dividend
- financial year, fiscal year
- audit, financial performance, financial results

**Example queries:**
- "What was the bank's revenue in 2024?"
- "Show me the annual report"
- "What are the quarterly results?"
- "Financial performance last year"

### 2. `ebl_user_documents`
**Purpose**: User-uploaded documents, custom documents

**Detected by keywords:**
- user document, uploaded document, custom document
- my document, document i uploaded, my file
- uploaded file, custom file, user file

**Example queries:**
- "What does my uploaded document say?"
- "Tell me about the document I provided"
- "What's in my custom file?"

### 3. `ebl_website` (Default)
**Purpose**: General banking queries, website content, products, services

**Used for:**
- Product information
- Service details
- General banking questions
- Website content queries

**Example queries:**
- "What are the loan products?"
- "Tell me about savings accounts"
- "What services does the bank offer?"

### 4. `ebl_employees` (If exists)
**Purpose**: Employee information (though phonebook is preferred)

**Used for:**
- Employee queries (though phonebook is checked first)

## How Routing Works

```
User Query
    ↓
Is it a contact query?
    ├─ YES → Check PostgreSQL Phonebook (never LightRAG)
    └─ NO → Continue to LightRAG routing
        ↓
Check query keywords:
    ├─ Financial keywords? → ebl_financial_reports
    ├─ User document keywords? → ebl_user_documents
    ├─ Employee keywords? → ebl_employees
    └─ Default → ebl_website (or configured default)
```

## Manual Override

You can still manually specify a knowledge base in the API request:

```json
{
  "query": "What are the loan products?",
  "knowledge_base": "ebl_financial_reports"  // Override automatic routing
}
```

## Benefits

✅ **No Confusion**: Financial reports won't mix with user documents
✅ **Automatic Routing**: Chatbot intelligently selects the right knowledge base
✅ **Faster Queries**: Smaller, focused knowledge bases = faster searches
✅ **Better Accuracy**: Only relevant documents are searched
✅ **Flexible**: Can still override manually if needed

## Setting Up Knowledge Bases

### 1. Upload Financial Reports

```bash
# Upload financial reports directory
python upload_to_knowledge_base.py financial_reports/ --knowledge-base ebl_financial_reports

# Or upload single file
python upload_to_knowledge_base.py annual_report_2024.pdf --knowledge-base ebl_financial_reports
```

### 2. Upload User Documents

```bash
# Upload user documents directory
python upload_to_knowledge_base.py user_documents/ --knowledge-base ebl_user_documents

# Or upload single file
python upload_to_knowledge_base.py custom_doc.pdf --knowledge-base ebl_user_documents
```

## Testing Routing

Test the routing with these queries:

1. **Financial Report Query:**
   ```
   "What was the bank's revenue in 2024?"
   ```
   Expected: Routes to `ebl_financial_reports`

2. **User Document Query:**
   ```
   "What does my uploaded document say?"
   ```
   Expected: Routes to `ebl_user_documents`

3. **General Banking Query:**
   ```
   "What are the loan products?"
   ```
   Expected: Routes to `ebl_website` (default)

## Logs

You'll see routing decisions in the logs:

```
[ROUTING] Query detected as financial report → using 'ebl_financial_reports'
[ROUTING] Query detected as user document → using 'ebl_user_documents'
[ROUTING] Query using default knowledge base: 'ebl_website'
```

## Configuration

Default knowledge base can be set in `.env`:

```env
LIGHTRAG_KNOWLEDGE_BASE=ebl_website
```

This is used when:
- Query doesn't match any specific keywords
- No manual override is provided

## Summary

✅ **Automatic routing** based on query content
✅ **Separate knowledge bases** for different document types
✅ **No confusion** between financial reports and user documents
✅ **Manual override** still available
✅ **Smart detection** using keyword matching

Your chatbot now intelligently routes queries to the right knowledge base!

