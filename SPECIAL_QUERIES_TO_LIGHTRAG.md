# Special Queries That Route to LightRAG

These 6 query types are checked **FIRST** and **ALWAYS** route to LightRAG, **skipping phonebook entirely**.

## 1. Banking Product Queries (`_is_banking_product_query`)

**Keywords:**
- **Credit/Debit Cards:** `credit card`, `debit card`, `card limit`, `card conversion`, `card upgrade`, `card feature`, `card benefit`, `card reward`, `card fee`, `card charge`, `card application`, `card activation`, `card statement`, `card transaction`
- **Loans:** `loan`, `personal loan`, `home loan`, `car loan`, `business loan`, `loan interest`, `loan rate`, `loan term`, `loan eligibility`, `loan application`, `loan approval`, `loan repayment`, `loan emi`, `loan processing`
- **Accounts:** `savings account`, `current account`, `fixed deposit`, `fd`, `rd`, `recurring deposit`, `account opening`, `account balance`, `account statement`, `account fee`, `account interest`, `account rate`, `account minimum balance`
- **Banking Services:** `online banking`, `mobile banking`, `internet banking`, `atm`, `cash withdrawal`, `fund transfer`, `remittance`, `foreign exchange`, `forex`, `currency exchange`, `locker`, `safe deposit`, `cheque`, `draft`, `demand draft`
- **Products & Services:** `banking product`, `financial product`, `service`, `banking service`, `product feature`, `product benefit`, `product eligibility`, `product requirement`, `interest rate`, `exchange rate`, `service charge`, `fee structure`, `conversion`, `upgrade`, `downgrade`, `limit`, `limit increase`, `limit decrease`

**Examples:**
- "Tell me about credit card limit conversion"
- "What are the interest rates for personal loans?"
- "How do I open a savings account?"
- "What is the fee structure for online banking?"

**Knowledge Base:** `ebl_website` (default)

---

## 2. Compliance Queries (`_is_compliance_query`)

**Keywords:**
- **AML:** `aml`, `anti money laundering`, `anti-money laundering`, `money laundering`, `aml policy`, `aml compliance`, `aml regulation`, `aml requirements`, `aml customer`, `aml customers`, `aml sensitive`, `aml risk`
- **Compliance:** `compliance`, `regulatory`, `regulation`, `regulations`, `regulatory compliance`, `compliance policy`, `compliance requirement`, `compliance requirements`, `regulatory policy`, `regulatory requirement`, `regulatory requirements`
- **Policy:** `policy`, `policies`, `procedure`, `procedures`, `guideline`, `guidelines`, `bank policy`, `banking policy`, `bank policies`, `banking policies`, `internal policy`, `internal policies`, `operational policy`
- **KYC:** `kyc`, `know your customer`, `kyc policy`, `kyc compliance`, `kyc requirement`, `kyc requirements`, `customer due diligence`, `cdd`
- **Risk & Fraud:** `risk management`, `fraud prevention`, `fraud detection`, `suspicious activity`, `suspicious transaction`, `transaction monitoring`, `sanctions`, `sanctions screening`, `ofac`, `pep`, `politically exposed person`
- **Sensitive Customers:** `sensitive customer`, `sensitive customers`, `high risk customer`, `high risk customers`, `risk customer`, `risk customers`
- **Regulatory Bodies:** `bangladesh bank`, `central bank`, `bb guideline`, `bb guidelines`, `regulatory authority`, `regulatory authorities`

**Examples:**
- "What is AML policy?"
- "Who are the most sensitive customers?"
- "What are the compliance requirements?"
- "What is the KYC policy?"

**Knowledge Base:** `ebl_website` (default)

---

## 3. Management Queries (`_is_management_query`)

**Keywords:**
- `management`, `management committee`, `mancom`, `managing director`, `md and ceo`, `deputy managing director`, `chief financial officer`, `cfo`, `chief technology officer`, `cto`, `chief risk officer`, `cro`, `head of`, `unit head`, `executive committee`, `management team`, `who is the managing director`, `who is the cfo`, `who is the cto`, `management structure`, `organizational structure`, `management hierarchy`, `ebl management`, `ebl executives`, `bank management`, `leadership team`

**Examples:**
- "Who is the CEO of EBL?"
- "Tell me about the management team"
- "Who is the CFO?"
- "What is the management structure?"

**Knowledge Base:** `ebl_website`

---

## 4. Financial Report Queries (`_is_financial_report_query`)

**Keywords:**
- `financial report`, `annual report`, `quarterly report`, `financial statement`, `revenue`, `profit`, `loss`, `income statement`, `balance sheet`, `cash flow`, `earnings`, `dividend`, `financial year`, `fiscal year`, `audit`, `auditor`, `financial performance`, `financial results`, `quarterly results`, `annual results`, `financial data`, `financial metrics`

**Examples:**
- "Show me the annual financial report"
- "What was the profit in 2023?"
- "Show me the quarterly report"
- "What is the balance sheet?"

**Knowledge Base:** `ebl_financial_reports`

---

## 5. Milestone Queries (`_is_milestone_query`)

**Keywords:**
- `milestone`, `milestones`, `history`, `historical`, `achievement`, `achievements`, `timeline`, `journey`, `evolution`, `development`, `growth`, `progress`, `founded`, `establishment`, `established`, `inception`, `origin`, `beginnings`, `ebl milestone`, `ebl milestones`, `ebl history`, `bank milestone`, `bank milestones`, `what are the milestones`, `ebl achievements`, `bank achievements`, `company history`, `bank history`, `corporate history`, `about ebl`, `ebl background`, `ebl information`

**Special Pattern:**
- `"about ebl"` or `"tell me about ebl"` → Treated as milestone query (unless it contains contact keywords like `phone`, `contact`, `email`, `address`, `number`, `mobile`, `call`)

**Examples:**
- "Tell me about EBL milestones"
- "What is the history of EBL?"
- "About EBL" (without contact keywords)
- "What are the achievements of EBL?"

**Knowledge Base:** `ebl_milestones`

---

## 6. User Document Queries (`_is_user_document_query`)

**Keywords:**
- `user document`, `uploaded document`, `custom document`, `my document`, `document i uploaded`, `document i provided`, `my file`, `uploaded file`, `custom file`, `user file`, `personal document`, `my upload`

**Examples:**
- "Upload my document"
- "Show me my documents"
- "What did I upload?"

**Knowledge Base:** `ebl_user_documents`

---

## Routing Logic in Code

**Location:** `bank_chatbot/app/services/chat_orchestrator.py` (line ~911-928)

```python
# CRITICAL: Check for banking product/compliance/management/financial/milestone/user document queries FIRST
# These should go to LightRAG, NOT phonebook
is_banking_product_query = self._is_banking_product_query(query)
is_compliance_query = self._is_compliance_query(query)
is_management_query = self._is_management_query(query)
is_financial_query = self._is_financial_report_query(query)
is_milestone_query = self._is_milestone_query(query)
is_user_doc_query = self._is_user_document_query(query)

# If it's a banking product/compliance/management/financial/milestone/user document query, 
# skip phonebook and go to LightRAG
if is_banking_product_query or is_compliance_query or is_management_query or \
   is_financial_query or is_milestone_query or is_user_doc_query:
    logger.info(f"[ROUTING] Query detected as special (banking product/compliance/management/financial/milestone/user doc) - skipping phonebook, using LightRAG")
    should_check_phonebook = False
    is_phonebook_query = False
    is_contact_query = False
    is_employee_query = False
    is_small_talk = False
```

## Key Points

1. **Priority:** These 6 query types are checked **BEFORE** phonebook queries
2. **No Phonebook:** If any of these match, phonebook is **completely skipped**
3. **Always LightRAG:** These queries **always** go to LightRAG, never to phonebook
4. **Knowledge Base Selection:** Each query type routes to the appropriate knowledge base automatically






