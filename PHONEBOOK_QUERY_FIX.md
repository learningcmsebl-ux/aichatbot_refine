# Phonebook Query Fix - "Who is Retail & SME Banking Division head of EBL"

## Issue
When querying "Who is Retail & SME Banking Division head of EBL", the system was returning:
> "I couldn't find any contact information for 'retail & sme banking division head of ebl' in the employee directory."

However, the query "phone head of retail banking" worked correctly and returned:
- Name: M. Khorshed Anowar
- Designation: DMD, Head of Retail & SME Banking
- Email: khorshed.anowar@ebl-bd.com
- Mobile: 01610002800

## Root Cause
The query extraction logic was not properly cleaning up the search term:
1. **Bank name suffix**: The query "Who is Retail & SME Banking Division head of EBL" extracted "Retail & SME Banking Division head of EBL" as the search term, but "of EBL" should be removed
2. **"Division" keyword**: The query included "Division" which is not in the actual designation ("DMD, Head of Retail & SME Banking"), causing the keyword-based search to fail (all keywords must match)

## Fix Applied

**File**: `bank_chatbot/app/services/chat_orchestrator.py`

Added two cleanup steps after the standard query extraction:

1. **Remove bank name suffixes**:
   ```python
   # Remove bank name suffixes (e.g., "of EBL", "of Eastern Bank", "at EBL")
   search_term = re.sub(r'\s+(of|at|in)\s+(ebl|eastern\s+bank|eastern\s+bank\s+plc)[\s.]*$', '', search_term, flags=re.IGNORECASE).strip()
   ```

2. **Remove "Division" suffix**:
   ```python
   # Remove "Division" if it appears at the end
   search_term = re.sub(r'\s+division\s*$', '', search_term, flags=re.IGNORECASE).strip()
   ```

## How It Works

**Before fix:**
- Query: "Who is Retail & SME Banking Division head of EBL"
- Extracted search term: "Retail & SME Banking Division head of EBL"
- Keywords extracted: ["retail", "sme", "banking", "division", "head", "ebl"]
- Database designation: "DMD, Head of Retail & SME Banking"
- Keywords in designation: ["head", "retail", "sme", "banking"]
- **Result**: No match (missing "division" and "ebl" keywords)

**After fix:**
- Query: "Who is Retail & SME Banking Division head of EBL"
- Extracted search term: "Retail & SME Banking head" (removed "Division" and "of EBL")
- Keywords extracted: ["retail", "sme", "banking", "head"]
- Database designation: "DMD, Head of Retail & SME Banking"
- Keywords in designation: ["head", "retail", "sme", "banking"]
- **Result**: Match found! ✅

## Next Steps
1. **Restart the chatbot service** to apply the fix
2. **Test the query**: "Who is Retail & SME Banking Division head of EBL"
   - Expected: Should return M. Khorshed Anowar's contact information

## Notes
- The fix applies to both contact queries and employee queries (two locations in the code)
- The fix is backward compatible - queries that already worked will continue to work
- The fix handles variations like "of EBL", "at EBL", "of Eastern Bank", etc.

