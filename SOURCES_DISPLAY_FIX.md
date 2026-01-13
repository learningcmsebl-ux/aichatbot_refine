# Sources Display Fix

## Issue
The chatbot was showing sources as raw text (`__SOURCES__{json}__SOURCES__`) in the chat message instead of parsing and displaying them in the formatted sources section.

## Root Cause
The frontend parsing logic wasn't robust enough to handle the sources marker format consistently, especially when sources arrived in chunks during streaming.

## Fix Applied

### Enhanced Source Parsing (`bank_chatbot_frontend/vite-project/src/hooks/useChat.ts`)

**Changes:**
1. **Improved pattern matching** - Better handling of sources markers in streaming chunks
2. **Multiple cleanup passes** - Ensures sources markers are removed from display content
3. **Better error handling** - More robust JSON parsing with fallbacks
4. **Final cleanup** - Additional safety net to remove any remaining markers

**Key improvements:**
- Sources are now extracted from chunks as they arrive
- Sources markers are properly removed from displayed content
- Sources are set on the message object for display in the sources section
- Handles both single and double underscore formats (if needed)

## Expected Behavior After Fix

**Before:**
```
The annual fee is BDT 0 per year.
__SOURCES__{"type": "sources", "sources": ["Card Charges and Fees Schedule"]}__SOURCES__
```

**After:**
```
The annual fee is BDT 0 per year.

Sources:
• Card Charges and Fees Schedule (Effective from 01st January, 2026)
```

## Files Modified

- `bank_chatbot_frontend/vite-project/src/hooks/useChat.ts`
  - Enhanced source parsing logic (lines 62-91)
  - Improved cleanup of sources markers
  - Better handling of streaming chunks

## Deployment

The frontend Docker container has been rebuilt with the fix. The changes are now active.

## Testing

To verify the fix:
1. Open the chatbot at http://localhost:3000
2. Ask a question that should have sources (e.g., "VISA Platinum supplementary card fee")
3. Check that:
   - Sources appear in a formatted section below the message
   - No raw `__SOURCES__` markers appear in the message content
   - Sources are properly listed with bullet points

## Status

✅ **Fixed** - Frontend container rebuilt and restarted with enhanced source parsing

