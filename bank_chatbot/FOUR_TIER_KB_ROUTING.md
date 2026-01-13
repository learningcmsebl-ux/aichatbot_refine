# 4-Tier Knowledge Base Routing Strategy

## Overview

The chatbot now implements a 4-tier knowledge base (KB) routing strategy to ensure queries are routed to the most appropriate knowledge base, preventing content leakage between different document types.

## The 4 Tiers

### 1. **Overview Tier** (`ebl_website`)
- **Purpose**: Customer-facing organizational overview
- **Queries**: "tell me about EBL", "what is EBL", "about Eastern Bank"
- **Content**: Establishment year, country, core banking services, customer-facing platforms
- **Excludes**: Annual reports, financial statements, investor content
- **Filtering**: Post-retrieval filtering to exclude financial documents

### 2. **Product Tier** (`ebl_products`)
- **Purpose**: Banking products and services information
- **Queries**: Account types, loan products, credit cards, banking services
- **Content**: Product features, rates, fees, eligibility, requirements
- **Examples**: 
  - "What is Super HPA Account?"
  - "Tell me about credit cards"
  - "What are the loan products?"

### 3. **Policy Tier** (`ebl_policies`)
- **Purpose**: Compliance, policies, and regulatory information
- **Queries**: AML, KYC, compliance policies, regulatory requirements
- **Content**: Policy documents, compliance procedures, regulatory guidelines
- **Examples**:
  - "What is the AML policy?"
  - "Tell me about KYC requirements"
  - "What are the compliance procedures?"

### 4. **Investor Tier** (`ebl_financial_reports`)
- **Purpose**: Financial reports, investor information, annual reports
- **Queries**: Financial statements, annual reports, investor content
- **Content**: Financial data, balance sheets, income statements, audit reports
- **Examples**:
  - "What are the financial results?"
  - "Show me the annual report"
  - "What is the profit for the year?"

## Routing Logic

The `_get_knowledge_base()` method routes queries in priority order:

```python
Priority 0: Organizational Overview → ebl_website (with filtering)
Priority 1: Banking Products → ebl_products
Priority 2: Compliance/Policy → ebl_policies
Priority 3: Financial/Investor → ebl_financial_reports
Priority 4: Management → ebl_website
Priority 5: Milestones → ebl_milestones
Priority 6: User Documents → ebl_user_documents
Priority 7: Employees → ebl_employees
Priority 8: Default → ebl_website
```

## Key Features

### 1. Organizational Overview Filtering
- **Query Enhancement**: Adds customer-facing keywords to bias retrieval
- **Post-Retrieval Filtering**: Hard exclusion of annual report/financial statement chunks
- **Response Filtering**: Excludes response text if it contains financial content
- **Reference Filtering**: Excludes references from financial documents

### 2. Product Query Routing
- Banking product queries automatically route to `ebl_products` KB
- Includes: accounts, loans, cards, services, branches, etc.

### 3. Policy Query Routing
- Compliance/policy queries automatically route to `ebl_policies` KB
- Includes: AML, KYC, regulatory, compliance keywords

### 4. Investor Query Routing
- Financial/investor queries route to `ebl_financial_reports` KB
- Keeps investor content separate from customer-facing content

## Bug Fixes Applied

### 1. Filtering Variable Initialization
**Issue**: `excluded_count` and `filter_financial_docs` were referenced but not properly initialized.

**Fix**: 
- Added `filter_financial_docs` parameter to `_format_lightrag_context()` function signature
- Initialized `excluded_count = 0` at function start
- All references now properly scoped

### 2. Milestone Query Greediness
**Issue**: `_is_milestone_query()` was too greedy, catching "tell me about ebl".

**Fix**:
- Added explicit check: if organizational overview query, return False
- Removed generic keywords like "about ebl", "ebl background"
- Only matches explicit milestone/history keywords

### 3. Knowledge Base Routing Order
**Issue**: Organizational overview queries were routed after financial reports.

**Fix**:
- Moved organizational overview check to Priority 0 (first)
- Ensures correct routing before any other checks

## Implementation Details

### Document-Type Filtering

The `_is_financial_document()` function detects financial documents by checking source names for patterns:

```python
financial_patterns = [
    'annual report', 'financial report', 'financial statement',
    'quarterly report', 'audit report', 'investor', 'shareholder',
    'balance sheet', 'income statement', 'cash flow',
    'financial year', 'fiscal year', 'financial data',
    'accounting', 'valuation', 'fair value', 'subsidiary',
    'board of directors', 'management report', 'directors report'
]
```

### Query Enhancement for Org Overview

For organizational overview queries, the query is enhanced with customer-facing keywords:

```python
customer_facing_keywords = "banking services accounts loans cards digital platforms EBLConnect customer"
improved_query = f"{query} {customer_facing_keywords}"
```

This biases LightRAG retrieval toward customer-facing content.

## Testing

Test the 4-tier routing with:

1. **Overview Query**: "tell me about ebl"
   - Expected: Routes to `ebl_website`, filters financial docs
   - Should NOT include: annual report content, financial statements

2. **Product Query**: "What is Super HPA Account?"
   - Expected: Routes to `ebl_products`
   - Should include: Account features, rates, benefits

3. **Policy Query**: "What is the AML policy?"
   - Expected: Routes to `ebl_policies`
   - Should include: Policy details, compliance requirements

4. **Investor Query**: "What are the financial results?"
   - Expected: Routes to `ebl_financial_reports`
   - Should include: Financial data, annual report content

## Files Modified

- `bank_chatbot/app/services/chat_orchestrator.py`
  - `_get_knowledge_base()`: Added 4-tier routing logic
  - `_format_lightrag_context()`: Fixed filtering bug, added parameter
  - `_is_milestone_query()`: Fixed greediness issue
  - `_is_financial_document()`: New helper function
  - `_improve_query_for_lightrag()`: Enhanced for org overview queries

## Status

✅ **4-Tier KB Routing**: Implemented
✅ **Filtering Bug**: Fixed
✅ **Milestone Greediness**: Fixed
✅ **Post-Retrieval Filtering**: Implemented

## Next Steps (Optional Enhancements)

1. **KB Existence Check**: Add logic to check if `ebl_products`/`ebl_policies` exist before routing
2. **Fallback Strategy**: If dedicated KB doesn't exist, fallback to `ebl_website` with appropriate filtering
3. **Monitoring**: Add metrics to track KB routing decisions
4. **Configuration**: Make KB names configurable via environment variables
