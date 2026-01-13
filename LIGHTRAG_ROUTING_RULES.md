# LightRAG Routing Rules

This document explains when queries are routed to LightRAG vs Phonebook in the EBL DIA 2.0 chatbot.

## Routing Decision Flow

```
Query Received
    │
    ├─→ Is it Small Talk? → NO LightRAG (handled by OpenAI directly)
    │
    ├─→ Is it Banking Product Query? → YES → LightRAG (skip phonebook)
    │
    ├─→ Is it Compliance Query? → YES → LightRAG (skip phonebook)
    │
    ├─→ Is it Management Query? → YES → LightRAG (skip phonebook)
    │
    ├─→ Is it Financial Report Query? → YES → LightRAG (skip phonebook)
    │
    ├─→ Is it Milestone Query? → YES → LightRAG (skip phonebook)
    │
    ├─→ Is it User Document Query? → YES → LightRAG (skip phonebook)
    │
    └─→ Is it Contact/Phonebook/Employee Query? → YES → Phonebook FIRST (NO LightRAG)
        │
        └─→ If no results in phonebook → Return error (still NO LightRAG)
```

## Priority Rules

### 1. ALWAYS Use LightRAG (Skip Phonebook)

These query types **ALWAYS** go to LightRAG and **NEVER** check phonebook:

#### A. Banking Product Queries (`_is_banking_product_query`)
**Keywords:**
- Credit/Debit Cards: `credit card`, `debit card`, `card limit`, `card conversion`, `card upgrade`, `card feature`, `card benefit`, `card reward`, `card fee`, `card charge`, `card application`, `card activation`, `card statement`, `card transaction`
- Loans: `loan`, `personal loan`, `home loan`, `car loan`, `business loan`, `loan interest`, `loan rate`, `loan term`, `loan eligibility`, `loan application`, `loan approval`, `loan repayment`, `loan emi`, `loan processing`
- Accounts: `savings account`, `current account`, `fixed deposit`, `fd`, `rd`, `recurring deposit`, `account opening`, `account balance`, `account statement`, `account fee`, `account interest`, `account rate`, `account minimum balance`
- Banking Services: `online banking`, `mobile banking`, `internet banking`, `atm`, `cash withdrawal`, `fund transfer`, `remittance`, `foreign exchange`, `forex`, `currency exchange`, `locker`, `safe deposit`, `cheque`, `draft`, `demand draft`
- Products & Services: `banking product`, `financial product`, `service`, `banking service`, `product feature`, `product benefit`, `product eligibility`, `product requirement`, `interest rate`, `exchange rate`, `service charge`, `fee structure`, `conversion`, `upgrade`, `downgrade`, `limit`, `limit increase`, `limit decrease`

**Example Queries:**
- "Tell me about credit card limit conversion"
- "What are the interest rates for personal loans?"
- "How do I open a savings account?"

#### B. Compliance Queries (`_is_compliance_query`)
**Keywords:**
- AML: `aml`, `anti money laundering`, `anti-money laundering`, `money laundering`, `aml policy`, `aml compliance`, `aml regulation`, `aml requirements`, `aml customer`, `aml customers`, `aml sensitive`, `aml risk`
- Compliance: `compliance`, `regulatory`, `regulation`, `regulations`, `regulatory compliance`, `compliance policy`, `compliance requirement`, `compliance requirements`, `regulatory policy`, `regulatory requirement`, `regulatory requirements`
- Policy: `policy`, `policies`, `procedure`, `procedures`, `guideline`, `guidelines`, `bank policy`, `banking policy`, `bank policies`, `banking policies`, `internal policy`, `internal policies`, `operational policy`
- KYC: `kyc`, `know your customer`, `kyc policy`, `kyc compliance`, `kyc requirement`, `kyc requirements`, `customer due diligence`, `cdd`
- Risk & Fraud: `risk management`, `fraud prevention`, `fraud detection`, `suspicious activity`, `suspicious transaction`, `transaction monitoring`, `sanctions`, `sanctions screening`, `ofac`, `pep`, `politically exposed person`
- Sensitive Customers: `sensitive customer`, `sensitive customers`, `high risk customer`, `high risk customers`, `risk customer`, `risk customers`
- Regulatory Bodies: `bangladesh bank`, `central bank`, `bb guideline`, `bb guidelines`, `regulatory authority`, `regulatory authorities`

**Example Queries:**
- "What is AML policy?"
- "Who are the most sensitive customers?"
- "What are the compliance requirements?"

#### C. Management Queries (`_is_management_query`)
**Keywords:**
- `management`, `board`, `director`, `ceo`, `executive`, `leadership`, `management team`, `board of directors`, `executive team`, `senior management`, `top management`

**Example Queries:**
- "Who is the CEO of EBL?"
- "Tell me about the management team"

#### D. Financial Report Queries (`_is_financial_report_query`)
**Keywords:**
- `financial report`, `annual report`, `quarterly report`, `financial statement`, `balance sheet`, `income statement`, `profit`, `loss`, `revenue`, `earnings`, `financial performance`, `financial data`, `financial year`, `fy`, `audit report`, `audited report`

**Example Queries:**
- "Show me the annual financial report"
- "What was the profit in 2023?"

#### E. Milestone Queries (`_is_milestone_query`)
**Keywords:**
- `milestone`, `milestones`, `history`, `historical`, `achievement`, `achievements`, `timeline`, `journey`, `evolution`, `development`, `growth`, `progress`, `founded`, `establishment`, `established`, `inception`, `origin`, `beginnings`, `ebl milestone`, `ebl milestones`, `ebl history`, `bank milestone`, `bank milestones`, `what are the milestones`, `ebl achievements`, `bank achievements`, `company history`, `bank history`, `corporate history`, `about ebl`, `ebl background`, `ebl information`

**Special Pattern:**
- `"about ebl"` or `"tell me about ebl"` → Treated as milestone query (unless it contains contact keywords)

**Example Queries:**
- "Tell me about EBL milestones"
- "What is the history of EBL?"
- "About EBL" (without contact keywords)

#### F. User Document Queries (`_is_user_document_query`)
**Keywords:**
- `user document`, `user documents`, `my document`, `my documents`, `document upload`, `upload document`, `personal document`, `customer document`

**Example Queries:**
- "Upload my document"
- "Show me my documents"

### 2. ALWAYS Use Phonebook (NO LightRAG)

These query types **ALWAYS** check phonebook **FIRST** and **NEVER** use LightRAG:

#### A. Contact Info Queries (`_is_contact_info_query`)
**Keywords:**
- `phone`, `contact`, `email`, `address`, `number`, `mobile`, `telephone`, `call`, `reach`, `get in touch`, `contact information`, `contact details`, `phone number`, `email address`, `mobile number`, `office address`

**Example Queries:**
- "What is the phone number of John?"
- "Contact information for HR department"

#### B. Phonebook Queries (`_is_phonebook_query`)
**Keywords:**
- `phonebook`, `phone book`, `directory`, `employee directory`, `staff directory`, `contact list`, `employee list`, `staff list`

**Example Queries:**
- "Search in phonebook for John"
- "Show me the employee directory"

#### C. Employee Queries (`_is_employee_query`)
**Keywords:**
- `employee`, `employees`, `staff`, `staff member`, `colleague`, `colleagues`, `team member`, `team members`, `worker`, `workers`

**Example Queries:**
- "Who is the employee in IT department?"
- "Find employees named John"

**Important:** Even if phonebook search returns NO RESULTS, the system will **NOT** use LightRAG. It will return an error message asking for more details.

### 3. Small Talk (NO LightRAG, NO Phonebook)

**Keywords:**
- `hello`, `hi`, `hey`, `good morning`, `good afternoon`, `good evening`, `how are you`, `how do you do`, `nice to meet you`, `thanks`, `thank you`, `bye`, `goodbye`, `see you`, `have a nice day`

**Example Queries:**
- "Hello"
- "How are you?"
- "Thank you"

These are handled directly by OpenAI without any context from LightRAG or phonebook.

## Knowledge Base Selection

When a query goes to LightRAG, the system automatically selects the appropriate knowledge base:

1. **Financial Reports** → `ebl_financial_reports`
2. **Management** → `ebl_management`
3. **Milestones** → `ebl_milestones`
4. **User Documents** → `ebl_user_documents`
5. **Default** → `ebl_website` (for banking products, compliance, and general queries)

## Code Location

The routing logic is in:
- **File:** `bank_chatbot/app/services/chat_orchestrator.py`
- **Main routing function:** `process_chat()` (line ~820)
- **Detection functions:**
  - `_is_banking_product_query()` (line ~377)
  - `_is_compliance_query()` (line ~337)
  - `_is_management_query()` (line ~292)
  - `_is_financial_report_query()` (line ~266)
  - `_is_milestone_query()` (line ~308)
  - `_is_user_document_query()` (line ~280)
  - `_is_contact_info_query()` (line ~166)
  - `_is_phonebook_query()` (line ~213)
  - `_is_employee_query()` (line ~250)
  - `_is_small_talk()` (line ~117)

## Debugging

To see routing decisions in logs, look for:
- `[ROUTING] Query detected as special ... - skipping phonebook, using LightRAG`
- `[DEBUG] Phonebook priority: phonebook=..., contact=..., employee=..., will_check=...`
- `[OK] Found X results in phonebook for: ...`
- `[INFO] No results in phonebook for '...' (contact query - NOT using LightRAG)`






