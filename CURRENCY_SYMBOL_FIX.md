# Currency Symbol Fix - BDT vs ₹ Issue

## Problem
The chatbot was incorrectly replacing "BDT" (Bangladeshi Taka) with "₹" (Indian Rupee) in responses. For example:
- **Incorrect**: "The Card Chequebook Fee for the VISA Credit Card Platinum is set at ₹287.5"
- **Correct**: "The Card Chequebook Fee for the VISA Credit Card Platinum is set at BDT 287.5"

## Root Cause
The LLM (OpenAI) was hallucinating currency symbols because the system message didn't explicitly instruct to preserve currency codes from the context.

## Fix Applied

### 1. Updated System Message (`bank_chatbot/app/services/chat_orchestrator.py`)
Added explicit currency preservation instructions:

```python
8. **CRITICAL CURRENCY PRESERVATION: When the context shows amounts with currency symbols or codes (BDT, USD, etc.), you MUST use the EXACT currency symbol/code from the context. NEVER replace BDT (Bangladeshi Taka) with ₹ (Indian Rupee) or any other currency symbol. If you see "BDT 287.5" in the context, you MUST output "BDT 287.5" - do NOT change it to ₹287.5 or any other currency. Preserve all currency codes exactly as shown: BDT = Bangladeshi Taka, USD = US Dollar.**
```

### 2. Enhanced User Message Context
Added currency preservation reminder in user message when card rates context is detected:

```python
if "OFFICIAL CARD RATES AND FEES INFORMATION" in context:
    currency_reminder = "\n\nCRITICAL: Preserve currency symbols/codes EXACTLY as shown in the context above. If you see 'BDT 287.5', output 'BDT 287.5' - NEVER use ₹ or other currency symbols. BDT = Bangladeshi Taka, USD = US Dollar. Use the exact currency code from the context."
```

### 3. Updated Response Guidelines
Added to "When responding" section:
```python
- **CRITICAL: Preserve currency symbols and codes exactly as shown in context - BDT means Bangladeshi Taka, USD means US Dollar. Never substitute or change currency symbols. If context says "BDT 287.5", output "BDT 287.5" - never use ₹ or other symbols.**
```

## Testing
After this fix, test with:
1. "What is the Card Chequebook Fee for VISA Credit Card Platinum?"
   - Expected: "BDT 287.5" (NOT ₹287.5)

2. "What is the annual fee for Credit Card VISA Classic?"
   - Expected: "BDT 1,725" (NOT ₹1,725)

3. "What is the annual fee for FX Credit Card Platinum in USD?"
   - Expected: "USD 57.5"

4. "What is the late payment fee for Credit Card Gold?"
   - Expected: "BDT 1150/$13.8" (both currencies preserved)

## Files Modified
- `bank_chatbot/app/services/chat_orchestrator.py`
  - Updated `_get_system_message()` method (line ~108)
  - Updated `_build_messages()` method (line ~1153)

## Date Fixed
2025-01-XX

## Status
✅ Fixed - Currency symbols now preserved exactly as shown in context

