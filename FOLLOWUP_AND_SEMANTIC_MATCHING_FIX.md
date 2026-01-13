# Follow-up Questions & Semantic Matching Fix

## Problems Identified

### 1. Follow-up Question Recognition
**Issue**: Chatbot doesn't recognize follow-up questions in a conversation.

**Example**:
- User: "Tell me about Super HPA Account"
- User (follow-up): "After how many days interest is credited?"
- **Problem**: Chatbot doesn't connect the follow-up to the previous question about Super HPA Account

### 2. Semantic Matching Issue
**Issue**: Chatbot gets confused when wordings don't match exactly between user query and knowledge base.

**Example**:
- Query: "After how many days interest is **credited** for EBL Super HPA Account"
- Knowledge base: "interest is **paid** semi-annually"
- **Problem**: Chatbot doesn't recognize that "credited" and "paid" mean the same thing
- **Result**: Says "I don't have information" even though the answer exists

## Root Causes

1. **Follow-up Questions**: 
   - System message didn't explicitly instruct LLM to use conversation history for context
   - No mechanism to detect follow-up questions and link them to previous topics

2. **Semantic Matching**:
   - System message didn't instruct LLM to recognize semantic equivalents
   - LLM treated "credited" and "paid" as different concepts
   - No synonym awareness in query processing

## Fixes Applied

### 1. Enhanced System Message

Added explicit instructions for:
- **Follow-up Question Handling**: Instructions to check conversation history and link follow-up questions to previous topics
- **Semantic Equivalence Recognition**: Instructions to recognize that different words can mean the same thing:
  - "credited" = "paid" = "deposited" = "added"
  - "fee" = "charge" = "cost"
  - "rate" = "interest rate" = "percentage"
  - "frequency" = "schedule" = "how often" = "when"

### 2. Enhanced User Message Context

Added dynamic reminders in user message when:
- **Semantic terms detected**: If query contains terms like "credited", "paid", "fee", "charge", etc., add reminder about semantic equivalence
- **Follow-up question detected**: If conversation history exists and query looks like a follow-up (contains "after", "how many", "what is", etc.), add context from previous conversation

### 3. Query Improvement Function

Enhanced `_improve_query_for_lightrag()` to:
- Log when synonym terms are detected for monitoring
- Note that LightRAG's semantic search should handle synonyms automatically

## Expected Behavior After Fix

### Follow-up Question Example

**Before**:
```
User: "Tell me about Super HPA Account"
Bot: [Provides information about Super HPA Account]

User: "After how many days interest is credited?"
Bot: "I'm sorry, but I don't have the specific information..."
```

**After**:
```
User: "Tell me about Super HPA Account"
Bot: [Provides information about Super HPA Account]

User: "After how many days interest is credited?"
Bot: [Recognizes this is about Super HPA Account from previous conversation]
Bot: "Interest for the EBL Super HPA Account is paid (credited) semi-annually, 
      which means every six months..."
```

### Semantic Matching Example

**Before**:
```
Query: "After how many days interest is credited for EBL Super HPA Account"
Knowledge Base: "interest is paid semi-annually"
Result: "I don't have information"
```

**After**:
```
Query: "After how many days interest is credited for EBL Super HPA Account"
Knowledge Base: "interest is paid semi-annually"
Result: "Interest is paid (credited) semi-annually, which means every six months..."
[Recognizes "credited" = "paid"]
```

## Files Modified

- `bank_chatbot/app/services/chat_orchestrator.py`
  - Updated `_get_system_message()` method - Added follow-up and semantic matching instructions
  - Updated `_build_messages()` method - Added dynamic reminders for semantic matching and follow-up questions
  - Updated `_improve_query_for_lightrag()` method - Added synonym detection logging

## Testing

Test with these scenarios:

1. **Follow-up Question Test**:
   - Ask: "Tell me about Super HPA Account"
   - Then ask: "After how many days interest is credited?"
   - Expected: Bot should recognize this is about Super HPA Account

2. **Semantic Matching Test**:
   - Ask: "After how many days interest is credited for EBL Super HPA Account"
   - Expected: Bot should find information even if knowledge base uses "paid" instead of "credited"

3. **Combined Test**:
   - Ask: "What is Super HPA Account?"
   - Then ask: "How often is interest paid?"
   - Expected: Bot should connect follow-up AND recognize "paid" = "credited"

## Status

✅ Fixed - Both follow-up question recognition and semantic matching issues addressed

