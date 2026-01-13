# Routing Rules - Visual Flow

## Complete Routing Decision Tree

```
┌─────────────────────────────────────────────────────────────┐
│                    QUERY RECEIVED                            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │  STEP 1: Check for Special Queries   │
        │  (These ALWAYS go to LightRAG)        │
        └───────────────────────────────────────┘
                            │
        ┌───────────────────┴───────────────────┐
        │                                       │
        ▼                                       ▼
┌───────────────────────┐          ┌──────────────────────────┐
│ Is it a SPECIAL       │  YES    │ Skip phonebook           │
│ query?                │────────▶│ Go directly to LightRAG  │
│                        │         │                           │
│ - Banking Product?    │         │ Knowledge Base Selection:│
│ - Compliance?         │         │ - Financial → ebl_financial_reports│
│ - Management?         │         │ - Management → ebl_website │
│ - Financial Report?   │         │ - Milestone → ebl_milestones│
│ - Milestone?          │         │ - User Doc → ebl_user_documents│
│ - User Document?      │         │ - Others → ebl_website    │
└───────────────────────┘         └──────────────────────────┘
        │
        │ NO
        ▼
┌───────────────────────┐
│ STEP 2: Check for     │
│ Contact/Phonebook      │
│ Queries                │
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│ Is it a CONTACT query?│
│                        │
│ - Contact info?       │
│ - Phonebook?          │
│ - Employee?           │
└───────────────────────┘
        │
        ├─── YES ───▶ Check Phonebook FIRST
        │             │
        │             ├─── Found results ──▶ Return results (NO LightRAG)
        │             │
        │             ├─── No results ────▶ Return error (NO LightRAG)
        │             │
        │             └─── Error ─────────▶ Return error (NO LightRAG)
        │
        │ NO
        ▼
┌───────────────────────┐
│ STEP 3: Check for     │
│ Small Talk            │
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│ Is it SMALL TALK?     │
│                        │
│ - Hello, Hi, Thanks   │
└───────────────────────┘
        │
        ├─── YES ───▶ Direct OpenAI (NO LightRAG, NO Phonebook)
        │
        │ NO
        ▼
┌───────────────────────┐
│ STEP 4: Default       │
│ Route to LightRAG     │
└───────────────────────┘
        │
        ▼
    Use LightRAG
    (ebl_website)
```

## Detailed Routing Logic (Code Flow)

### Step 1: Special Query Detection (Lines 914-930)

```python
# Check for special queries FIRST
is_banking_product_query = self._is_banking_product_query(query)
is_compliance_query = self._is_compliance_query(query)
is_management_query = self._is_management_query(query)
is_financial_query = self._is_financial_report_query(query)
is_milestone_query = self._is_milestone_query(query)
is_user_doc_query = self._is_user_document_query(query)

# If ANY special query detected → Skip phonebook, go to LightRAG
if is_banking_product_query or is_compliance_query or is_management_query or \
   is_financial_query or is_milestone_query or is_user_doc_query:
    should_check_phonebook = False
    # Route to LightRAG with appropriate knowledge base
```

**Result:** Query goes directly to LightRAG, phonebook is completely skipped.

### Step 2: Contact/Phonebook Detection (Lines 931-944)

```python
# Only if NOT a special query, check for contact queries
is_small_talk = self._is_small_talk(query)
is_contact_query = self._is_contact_info_query(query)
is_phonebook_query = self._is_phonebook_query(query)
is_employee_query = self._is_employee_query(query)

# If it's a contact/phonebook/employee query → Check phonebook FIRST
should_check_phonebook = (
    (is_phonebook_query or is_contact_query or is_employee_query) 
    and not is_small_talk 
    and PHONEBOOK_DB_AVAILABLE
)
```

**Result:** If contact query → Check phonebook, NEVER use LightRAG (even if phonebook fails).

### Step 3: Phonebook Processing (Lines 949-1086)

```python
if should_check_phonebook:
    # Search phonebook
    results = phonebook_db.smart_search(search_term, limit=5)
    
    if results:
        # Return phonebook results
        return  # DO NOT query LightRAG
    else:
        # Return error message
        return  # DO NOT query LightRAG (even if no results)
```

**Result:** Phonebook queries NEVER go to LightRAG, even if:
- Phonebook search returns no results
- Phonebook has an error
- User asks for more details

### Step 4: LightRAG Routing (Lines 1088-1097)

```python
# Only reached if NOT a special query AND NOT a contact query
if not is_small_talk:
    # Determine knowledge base
    knowledge_base = self._get_knowledge_base(query)
    
    # Get context from LightRAG
    context = await self._get_lightrag_context(query, knowledge_base)
```

**Knowledge Base Selection Priority:**
1. Financial Report → `ebl_financial_reports`
2. Management → `ebl_website`
3. Milestone → `ebl_milestones`
4. User Document → `ebl_user_documents`
5. Default → `ebl_website`

## Key Rules Summary

### ✅ ALWAYS Route to LightRAG (Skip Phonebook)
1. **Banking Product Queries** - credit cards, loans, accounts, services
2. **Compliance Queries** - AML, KYC, policies, regulations
3. **Management Queries** - CEO, board, executives
4. **Financial Report Queries** - annual reports, financial statements
5. **Milestone Queries** - EBL history, achievements
6. **User Document Queries** - document uploads

### ✅ ALWAYS Route to Phonebook (Never LightRAG)
1. **Contact Info Queries** - phone, email, address
2. **Phonebook Queries** - directory searches
3. **Employee Queries** - employee lookups

**Important:** Even if phonebook returns NO RESULTS, LightRAG is NOT used.

### ✅ Direct OpenAI (No LightRAG, No Phonebook)
1. **Small Talk** - greetings, thanks, goodbye

### ✅ Default Route
- If query doesn't match any category above → Route to LightRAG (`ebl_website`)

## Example Queries and Routing

| Query | Route | Knowledge Base | Reason |
|-------|-------|----------------|--------|
| "tell me about rfcd account" | LightRAG | ebl_website | Banking product (contains "account") |
| "what is AML policy?" | LightRAG | ebl_website | Compliance query |
| "who is the CEO?" | LightRAG | ebl_website | Management query |
| "show me annual report" | LightRAG | ebl_financial_reports | Financial report query |
| "tell me about EBL milestones" | LightRAG | ebl_milestones | Milestone query |
| "show my documents" | LightRAG | ebl_user_documents | User document query |
| "phone number of John" | Phonebook | None | Contact query |
| "employee directory" | Phonebook | None | Phonebook query |
| "hello" | Direct OpenAI | None | Small talk |
| "what is banking?" | LightRAG | ebl_website | Default route |

## Code Location

**File:** `bank_chatbot/app/services/chat_orchestrator.py`

**Main Routing Function:** `process_chat()` (line ~820)

**Key Sections:**
- Special query detection: Lines 914-930
- Contact query detection: Lines 931-944
- Phonebook processing: Lines 949-1086
- LightRAG routing: Lines 1088-1097
- Knowledge base selection: Lines 581-607






