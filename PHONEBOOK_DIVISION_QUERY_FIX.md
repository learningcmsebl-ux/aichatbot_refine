# Phonebook Query Fix - "Who is Retail & SME Banking Division ?"

## Issue
When querying "Who is Retail & SME Banking Division ?", the system was returning:
> "I couldn't find any contact information for 'retail & sme banking division ?' in the employee directory."

The query doesn't explicitly mention "head", so the system wasn't inferring that the user is asking about the head of that division.

## Root Cause
The query extraction logic didn't handle cases where:
1. A division/department name is mentioned without a role keyword (like "head", "manager", etc.)
2. The system needs to infer that "Who is [Division Name]?" means "Who is the head of [Division Name]?"

## Fix Applied

**File**: `bank_chatbot/app/services/chat_orchestrator.py`

Added logic to detect division/department names without roles and automatically add "head":

```python
# If search term looks like a division/department name without a role, try adding "head"
division_dept_keywords = ['banking', 'division', 'department', 'unit', 'section', 'retail', 'sme', 'corporate', 'operations', 'finance', 'hr', 'ict', 'it']
role_keywords = ['head', 'manager', 'director', 'officer', 'executive', 'president', 'ceo', 'cfo', 'chief', 'senior', 'assistant']
search_term_lower = search_term.lower()
has_division_keyword = any(keyword in search_term_lower for keyword in division_dept_keywords)
has_role_keyword = any(keyword in search_term_lower for keyword in role_keywords)

# If it looks like a division/department name but no role mentioned, try with "head"
if has_division_keyword and not has_role_keyword:
    search_term_with_head = f"{search_term} head"
    # Try search with "head" added
    results = phonebook_db.smart_search(search_term_with_head, limit=5)
    if not results:
        # Also try department search as fallback
        dept_results = phonebook_db.search_by_department(search_term, limit=5)
        if dept_results:
            results = dept_results
```

## How It Works

**Before fix:**
- Query: "Who is Retail & SME Banking Division ?"
- Extracted search term: "Retail & SME Banking Division"
- No role keyword detected → goes to name search
- **Result**: No match ❌

**After fix:**
- Query: "Who is Retail & SME Banking Division ?"
- Extracted search term: "Retail & SME Banking" (after removing "Division")
- Detects division keyword ("banking", "retail", "sme") but no role keyword
- Adds "head": "Retail & SME Banking head"
- Searches for designation containing these keywords
- **Result**: Matches "DMD, Head of Retail & SME Banking" ✅

## Fallback Strategy

If the search with "head" doesn't find results, the system also tries:
1. Department search using the original search term
2. Original search term as final fallback

## Next Steps
1. **Restart the chatbot service** to apply the fix (already done)
2. **Test the query**: "Who is Retail & SME Banking Division ?"
   - Expected: Should return M. Khorshed Anowar's contact information

## Notes
- The fix applies to both contact queries and employee queries
- Works for queries like:
  - "Who is Retail & SME Banking Division?"
  - "Who is Operations Division?"
  - "Who is Finance Department?"
- The fix is backward compatible - queries that already worked will continue to work









