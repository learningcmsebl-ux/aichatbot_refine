# Query Test: "phone number of zahid"

## Expected Behavior

When you query **"phone number of zahid"** in your chatbot, here's what should happen:

### 1. Query Detection ✅
```
Query: "phone number of zahid"
    ↓
Detected as: contact query ✅
    - Contains: "phone", "number" → is_phonebook_query = True
    - Contains: "phone", "number" → is_contact_query = True
    - Result: should_check_phonebook = True
```

### 2. Phonebook Search ✅
```
Extract search term: "zahid" (removed "phone", "number", "of")
    ↓
Query PostgreSQL phonebook: smart_search("zahid", limit=5)
    ↓
Search strategies:
    1. Exact name match
    2. Partial name match
    3. Email match
    4. Employee ID match
    5. Full-text search (GIN index)
```

### 3. Expected Results

The phonebook should find employees with "zahid" in their name, such as:
- **Md. Safiqul Islam Zahid** (EVP & Head, Financial Operations & Control)
- Any other employees with "zahid" in their name

### 4. Response Format

**If 1 result found:**
```
Name: [Full Name]
Designation: [Designation]
Email: [Email]
Mobile: [Mobile]
IP Phone: [IP Phone]

(Source: Phone Book Database)
```

**If multiple results found:**
```
1. [Name 1]
   Designation: [Designation]
   Email: [Email]
   Mobile: [Mobile]

2. [Name 2]
   ...

We found X matching contact(s) in total. Showing only the top 5 results.

Please provide more details to narrow down the search.

(Source: Phone Book Database)
```

**If no results found:**
```
I couldn't find any contact information for 'zahid' in the employee directory. 
Please try:
- Providing the full name
- Using the employee ID
- Specifying the department or designation

(Source: Phone Book Database)
```

## Expected Logs

When the chatbot processes this query, you should see:

```
[DEBUG] Phonebook priority: phonebook=True, contact=True, employee=False, small_talk=False, available=True, will_check=True
[OK] Found X results in phonebook for: zahid
```

**You should NOT see:**
```
[INFO] Querying LightRAG for: phone number of zahid...
```

## Verification Checklist

✅ **Query detected as contact query**
✅ **Phonebook checked FIRST** (before LightRAG)
✅ **PostgreSQL phonebook searched** for "zahid"
✅ **Results returned immediately** (no LightRAG query)
✅ **Logs show phonebook check**, not LightRAG query

## If It's Not Working

1. **Check PostgreSQL connection:**
   - Ensure PostgreSQL is running
   - Verify `.env` has correct credentials
   - Test connection: `python test_postgres_connection.py`

2. **Check phonebook availability:**
   - Verify `PHONEBOOK_DB_AVAILABLE = True` in logs
   - Check if `phonebook_postgres.py` is in `bank_chatbot/app/services/`

3. **Check logs:**
   - Look for `[DEBUG] Phonebook priority:` message
   - Verify `will_check=True`
   - Check for any error messages

## Database Connection

Make sure your `.env` file (in `bank_chatbot/` directory) has:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=chatbot_db
POSTGRES_USER=chatbot_user
POSTGRES_PASSWORD=chatbot_password_123
```

Or the phonebook will use environment variables from the root `.env` file.

## Summary

✅ Query: "phone number of zahid"
✅ Should check: PostgreSQL phonebook FIRST
✅ Should NOT query: LightRAG
✅ Should return: Contact information for employees named "zahid"
✅ Response time: 2-5ms (much faster than LightRAG)

Your chatbot is configured to handle this query correctly!

