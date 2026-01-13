# Chat Orchestration Logic - Complete Overview

## Architecture Overview

The `ChatOrchestrator` is the central component that coordinates all services and determines how queries are processed. It implements a **multi-tier routing system** that intelligently routes queries to the appropriate service based on query type.

---

## Main Processing Flow

### Entry Points
1. **`process_chat()`** - Async streaming response (for real-time chat)
2. **`process_chat_sync()`** - Synchronous response (for API calls)

Both methods follow the same routing logic but differ in response delivery.

---

## Query Routing Decision Tree

```
User Query
    │
    ├─→ Is Small Talk? 
    │   └─→ YES → Direct LLM response (no context needed)
    │
    ├─→ Is Phonebook/Employee Query?
    │   └─→ YES → Route to Phonebook Database
    │       └─→ Extract search term (handles "find X", "phone number of X", etc.)
    │       └─→ Search PostgreSQL phonebook
    │       └─→ Return contact info or "not found" message
    │       └─→ **DO NOT** query LightRAG
    │
    ├─→ Is Card Rates/Fees Query?
    │   └─→ YES → Try Fee Engine Microservice FIRST
    │       ├─→ If microservice returns data → Use ONLY that data (skip LightRAG)
    │       └─→ If microservice returns NO data → **FALLBACK to LightRAG**
    │
    ├─→ Is Compliance/Policy Query?
    │   └─→ YES → Check for required entities (policy name, account type, etc.)
    │       ├─→ If missing → Ask clarification question (skip LightRAG)
    │       └─→ If complete → Route to LightRAG
    │
    └─→ Default: Route to LightRAG
        └─→ Determine knowledge base (ebl_website, ebl_products, ebl_policies, etc.)
        └─→ Apply filters (e.g., filter financial docs for org overview queries)
        └─→ Retrieve context
        └─→ Generate response
```

---

## Service Integration

### 1. **Fee Engine Microservice** (Card Rates & Fees)

**Purpose**: Provides deterministic, authoritative fee calculations for credit/debit cards.

**Detection**: Query contains:
- Card product names (VISA, Mastercard, Platinum, Classic, etc.)
- Fee/rate keywords (annual fee, ATM withdrawal fee, transaction alert fee, etc.)

**Flow**:
1. Query detected as card rates query
2. Call `_get_card_rates_context()` → Calls fee engine microservice
3. **If microservice returns data**:
   - Use ONLY microservice data
   - Skip LightRAG completely
   - Add source: "Card Charges and Fees Schedule"
4. **If microservice returns NO data**:
   - **FALLBACK**: Query LightRAG for information
   - This ensures queries like "EasyCredit Early Settlement process" still get answered

**Special Handling**:
- **Supplementary Card Fees**: Always includes both tiers (first 2 cards free, 3rd+ at BDT 2,300)
- **ATM Withdrawal Fees**: Enforced format "2.5% or BDT 345" (never "BDT 300" or "2%")
- **Transaction Alert Fees**: Returns exact amount (e.g., "BDT 460")

---

### 2. **LightRAG** (Knowledge Base)

**Purpose**: Retrieves contextual information from knowledge bases for banking products, policies, and general queries.

**Knowledge Base Selection** (`_get_knowledge_base()`):
- **Organizational Overview** → `ebl_website` (with financial doc filtering)
- **Banking Products** → `ebl_products` (fallback: `ebl_website`)
- **Compliance/Policy** → `ebl_policies` (fallback: `ebl_website`)
- **Financial/Investor** → `ebl_financial_reports`
- **Milestones** → `ebl_website`
- **User Documents** → `ebl_user_docs`
- **Default** → `ebl_website`

**Filtering**:
- **Organizational Overview Queries**: Filters out investor/financial content, keeps only customer-facing information
- **Financial Report Queries**: Includes all financial documents

**Fallback Mechanism**:
- If card rates microservice returns no data → LightRAG is queried
- Ensures comprehensive coverage

---

### 3. **Phonebook Database** (PostgreSQL)

**Purpose**: Employee contact information lookup.

**Detection**: Query contains:
- Employee search patterns: "find X", "search X", "who is X", "contact X", "phone number of X"
- Employee ID patterns: alphanumeric IDs (e.g., "cr_app5_test", "rajib.bhowmik")
- Contact keywords: "phone", "email", "contact", "employee", "staff"

**Search Term Extraction**:
- Removes prefixes: "find", "search", "lookup", "who is", "contact", "info about", "get"
- Handles "phone number of X" → extracts "X"
- Handles "email of X" → extracts "X"
- Handles "contact info for X" → extracts "X"

**Search Strategies** (`smart_search()`):
1. **Exact name match**
2. **Employee ID search** (case-insensitive)
3. **Email search** (handles email-like formats like "rajib.bhowmik" → searches email field)
4. **Mobile number search**
5. **Designation search**
6. **Full-text search** (name, department, designation)

**Routing Rule**: 
- **Phonebook queries NEVER query LightRAG** - they are completely isolated
- If employee not found → Return helpful message (don't use LightRAG)

---

## Query Type Detection Methods

### `_is_small_talk(query)`
Detects greetings, casual conversation, date/time queries.
- Returns: Direct LLM response (no context)

### `_is_phonebook_query(query)`
Detects employee/contact lookup queries.
- Patterns: "find X", "search X", "who is X", "contact X", employee IDs

### `_is_employee_query(query)`
Detects employee-specific queries.
- Patterns: "find [employee_id]", "search [employee_id]", "who is [employee_id]"

### `_is_contact_info_query(query)`
Detects contact information requests.
- Patterns: "phone number", "email", "contact info", "telephone"

### `_is_card_rates_query(query)`
Detects card fee/rate queries.
- Requires: Card product name (VISA, Mastercard, Platinum, etc.) + fee/rate keyword
- Examples: "VISA Platinum annual fee", "ATM withdrawal fee", "transaction alert fee"

### `_is_banking_product_query(query)`
Detects banking product/service queries.
- Keywords: account, loan, card, online banking, branch, service, etc.
- Routes to: LightRAG (ebl_products or ebl_website)

### `_is_compliance_query(query)`
Detects compliance/policy queries.
- Keywords: AML, KYC, compliance, policy, regulatory, etc.
- Routes to: LightRAG (ebl_policies or ebl_website)
- **Entity Validation**: Checks for required entities (policy name, account type, customer type)

### `_is_organizational_overview_query(query)`
Detects high-level "about EBL" queries.
- Patterns: "tell me about EBL", "what is EBL", "about Eastern Bank"
- Routes to: LightRAG (ebl_website) with **financial doc filtering**
- **Filtering**: Excludes investor/financial content, keeps customer-facing info

### `_is_financial_report_query(query)`
Detects financial/investor queries.
- Keywords: financial report, annual report, quarterly results, etc.
- Routes to: LightRAG (ebl_financial_reports)

### `_is_management_query(query)`
Detects management/executive queries.
- Keywords: management, MD, CEO, CFO, management committee, etc.
- Routes to: LightRAG

### `_is_milestone_query(query)`
Detects milestone/history queries.
- Keywords: milestone, history, achievement, timeline, etc.
- Routes to: LightRAG (ebl_website)

---

## Response Generation

### Message Building (`_build_messages()`)

1. **System Message**: Contains:
   - Role definition (Eastern Bank PLC knowledge assistant)
   - Critical rules (currency preservation, bank name, conciseness)
   - Partial information handling instructions
   - Fee data priority rules
   - Supplementary card fee reminders
   - ATM withdrawal fee enforcement

2. **Context Assembly**:
   - Card rates context (from microservice) OR LightRAG context
   - Combined if both available (for non-card-rates queries)

3. **Conversation History**:
   - Retrieves last N messages from PostgreSQL
   - Includes in context for follow-up questions

4. **Special Reminders** (added to system message):
   - **Supplementary Card Reminder**: If query mentions supplementary cards
   - **Partial Info Reminder**: If query asks for specific details about a product/service
   - **ATM Withdrawal Reminder**: If query mentions ATM withdrawal fees

### LLM Call

- **Model**: `gpt-4` (configurable via `OPENAI_MODEL`)
- **Temperature**: `0.7` (configurable)
- **Max Tokens**: `1500` (reduced from 2000 to avoid context length errors)
- **Streaming**: Yes (for `process_chat()`)

### Response Post-Processing

1. **Markdown Cleaning**: Removes markdown formatting artifacts
2. **Currency Symbol Fix**: Ensures BDT is used (not ₹)
3. **Bank Name Fix**: Replaces "Eastern Bank Limited" with "Eastern Bank PLC."
4. **Source Attribution**: Appends sources as `__SOURCES__{json}__SOURCES__` marker

---

## Source Attribution

**Sources are collected from**:
1. Fee Engine → "Card Charges and Fees Schedule (Effective from 01st January, 2026)"
2. LightRAG → Document names from retrieved chunks
3. Phonebook → "Phone Book Database"
4. Knowledge Base Name → Fallback if no specific sources found

**Format**: 
```json
__SOURCES__{"type": "sources", "sources": ["Source 1", "Source 2"]}__SOURCES__
```

**Frontend Parsing**: Frontend extracts and displays sources separately from response text.

---

## Memory Management

### PostgreSQL Chat Memory

- **Storage**: Conversation history stored in PostgreSQL
- **Retrieval**: Last N messages retrieved for context (configurable via `MAX_CONVERSATION_HISTORY`)
- **Session Management**: Each session has unique `session_id` (UUID)

### Redis Cache (Optional)

- **Purpose**: Cache frequently accessed data
- **Usage**: Not heavily used in current implementation

---

## Lead Generation (Currently Disabled)

**Status**: Disabled via `ENABLE_LEAD_GENERATION=False` in `.env`

**Flow** (when enabled):
1. Detect lead intent ("apply for credit card", "want loan")
2. Start question flow (name, phone, email, etc.)
3. Collect answers
4. Save to database via `LeadManager`
5. Return confirmation message

**Code**: Preserved but gated by `settings.ENABLE_LEAD_GENERATION` flag.

---

## Error Handling

### Phonebook Errors
- If phonebook query fails → Return error message (don't use LightRAG)
- Ensures phonebook queries stay isolated

### Fee Engine Errors
- If microservice fails → Fallback to LightRAG
- Ensures card queries still get answered

### LightRAG Errors
- If LightRAG fails → Response indicates missing information
- System message instructs LLM to handle gracefully

### OpenAI API Errors
- **Rate Limit**: Returns "technical difficulties" message
- **Context Length Exceeded**: Reduced `max_tokens` to 1500, shortened reminders
- **Other Errors**: Logged, returns generic error message

---

## Key Design Principles

1. **Deterministic Data Priority**: Fee engine data takes absolute priority over LightRAG for card rates
2. **Service Isolation**: Phonebook queries never query LightRAG
3. **Graceful Fallback**: If microservice fails, fallback to LightRAG
4. **Context Preservation**: Conversation history maintained for follow-up questions
5. **Source Attribution**: All responses include source information
6. **Partial Information Handling**: LLM instructed to provide available info first, then note what's missing
7. **Currency/Bank Name Preservation**: Strict rules to prevent currency symbol and bank name errors

---

## Configuration

### Environment Variables

- `ENABLE_LEAD_GENERATION`: Enable/disable lead generation (default: `False`)
- `OPENAI_MODEL`: LLM model (default: `gpt-4`)
- `OPENAI_MAX_TOKENS`: Max response tokens (default: `1500`)
- `OPENAI_TEMPERATURE`: LLM temperature (default: `0.7`)
- `MAX_CONVERSATION_HISTORY`: Number of history messages to retrieve (default: `10`)

---

## Logging

**Log Levels**:
- `[ROUTING]`: Query routing decisions
- `[CARD_RATES]`: Card rates microservice calls
- `[PHONEBOOK]`: Phonebook queries
- `[SOURCES]`: Source attribution
- `[ERROR]`: Errors

**Example Log Output**:
```
[ROUTING] ===== Processing Query (STREAMING): 'VISA Platinum annual fee' =====
[CARD_RATES] Detected card rates query: 'VISA Platinum annual fee' - trying card rates microservice first
[CARD_RATES] Card rates context added (length: 450 chars)
[CARD_RATES] Using ONLY card rates microservice data, skipping LightRAG
[SOURCES] Sending 1 sources: ['Card Charges and Fees Schedule (Effective from 01st January, 2026)']
```

---

## Future Enhancements

1. **KB Existence Check**: Verify knowledge base exists before routing
2. **Caching**: Cache frequent queries in Redis
3. **Analytics**: Enhanced query analytics and routing metrics
4. **Multi-language Support**: Route to language-specific knowledge bases
5. **Confidence Scoring**: Score query matches and route based on confidence











