# Management Query Routing Fix ✅

## Problem

The query **"who are the mancom members of ebl?"** was being incorrectly classified as a contact query and checked in the phonebook instead of routing to LightRAG.

### Why It Happened

The `_is_contact_info_query()` method had keywords like:
- `'who is'`, `'who are'` (line 145)
- `'members'` (could match "members")

This caused management queries to be misclassified as contact queries.

## Solution

Updated the routing logic to **check for management/financial/user document queries FIRST**, before checking for contact queries.

### Code Changes

In both `process_chat()` and `process_chat_sync()` methods:

```python
# CRITICAL: Check for management/financial/user document queries FIRST
# These should go to LightRAG, NOT phonebook
is_management_query = self._is_management_query(query)
is_financial_query = self._is_financial_report_query(query)
is_user_doc_query = self._is_user_document_query(query)

# If it's a management/financial/user document query, skip phonebook and go to LightRAG
if is_management_query or is_financial_query or is_user_doc_query:
    logger.info(f"[ROUTING] Query detected as special (management/financial/user doc) - skipping phonebook, using LightRAG")
    should_check_phonebook = False
    # ... set flags to False
else:
    # Only check phonebook if NOT a special query
    # ... existing phonebook check logic
```

## Expected Behavior Now

### Query Flow

```
User: "who are the mancom members of ebl?"
    ↓
_is_management_query() → True ✅
    ↓
Skip phonebook check ✅
    ↓
Route to LightRAG with knowledge_base="ebl_website" ✅
    ↓
Returns: Complete list of 25 MANCOM members ✅
```

### Log Output

You should now see:
```
[ROUTING] Query detected as special (management/financial/user doc) - skipping phonebook, using LightRAG
[ROUTING] Query detected as management → using 'ebl_website'
Querying LightRAG for: who are the mancom members of ebl?...
```

Instead of:
```
[DEBUG] Phonebook priority: phonebook=True, contact=True, will_check=True
[INFO] No results in phonebook for 'who are mancom members ebl?' (contact query - NOT using LightRAG)
```

## Test

After restarting the chatbot, try:
- ✅ "who are the mancom members of ebl?"
- ✅ "who is the managing director?"
- ✅ "show me the management committee"
- ✅ "what was the bank's revenue in 2024?" (financial query)
- ✅ "phone number of tanvir" (contact query - should still check phonebook)

## Summary

✅ **Management queries now skip phonebook**
✅ **Routes directly to LightRAG**
✅ **Contact queries still check phonebook first**
✅ **Financial queries skip phonebook**
✅ **User document queries skip phonebook**

The fix ensures proper routing priority:
1. **Special queries** (management/financial/user docs) → LightRAG
2. **Contact queries** → Phonebook first
3. **Other queries** → LightRAG (default)

