# Updated Routing Rules

## New Simplified Routing Logic

**ONLY these queries go to Phonebook:**
1. **Phone number queries** - phone, telephone, mobile, call, etc.
2. **Email queries** - email address, email id, etc.
3. **Employee information queries** - employee id, employee phone, employee email, etc.
4. **Phonebook/directory queries** - phonebook, directory, employee directory, etc.

**EVERYTHING ELSE goes to LightRAG:**
- Banking products, accounts, services
- Compliance, policies, AML, KYC
- Management, executives, CEO
- Financial reports
- Milestones, history
- User documents
- General questions
- Address/location queries (now go to LightRAG)
- Contact information queries (now go to LightRAG, unless specifically phone/email)
- Everything else!

## Changes Made

### Before (Old Rules):
- Many queries went to phonebook (address, location, contact, etc.)
- Broad keyword matching caught too many queries
- Queries like "what is the address" went to phonebook

### After (New Rules):
- **ONLY** phone/email/employee queries → Phonebook
- **EVERYTHING ELSE** → LightRAG
- Much more restrictive phonebook detection
- Removed broad keywords like "address", "location", "contact", "where", etc.

## Examples

| Query | Route | Reason |
|-------|-------|--------|
| "phone number of John" | Phonebook | Contains "phone number" |
| "email of John" | Phonebook | Contains "email" |
| "employee id 12345" | Phonebook | Contains "employee id" |
| "what is address of branch" | LightRAG | "address" removed from phonebook keywords |
| "contact information" | LightRAG | "contact" removed from phonebook keywords |
| "where is office" | LightRAG | "where" removed from phonebook keywords |
| "tell me about account" | LightRAG | Account query |
| "what is policy" | LightRAG | Policy query |
| "who is the CEO" | LightRAG | Management query (not employee lookup) |

## Code Changes

**File:** `bank_chatbot/app/services/chat_orchestrator.py`

### 1. `_is_contact_info_query()` (Line ~166)
- **Before:** 40+ keywords including "address", "location", "contact", "where", etc.
- **After:** Only phone and email keywords (15 keywords)

### 2. `_is_phonebook_query()` (Line ~191)
- **Before:** 30+ keywords including "contact", "address", "department", etc.
- **After:** Only explicit phonebook/directory keywords (8 keywords)

### 3. `_is_employee_query()` (Line ~205)
- **Before:** 20+ keywords including general "employee", "staff", "designation", etc.
- **After:** Only employee search/lookup keywords (15 keywords)
- Now requires "employee" + contact/search term (phone, email, id, search, find, etc.)

## Result

**Maximum queries now route to LightRAG**, with phonebook only used for:
- Explicit phone number lookups
- Explicit email lookups
- Explicit employee information searches
- Explicit phonebook/directory queries






