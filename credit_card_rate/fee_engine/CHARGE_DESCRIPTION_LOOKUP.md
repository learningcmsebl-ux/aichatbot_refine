# Charge Description-Based Lookup

## Summary

The retail asset charge lookup system now uses **`charge_description`** text matching for intelligent filtering, while keeping the `charge_context` column unchanged. This provides flexible lookups based on actual description content rather than relying on a separate context field.

## Key Changes

### 1. API Request Model
**Changed Parameter:** `charge_context` → `description_keywords`

```python
# Before:
class RetailAssetChargeRequest(BaseModel):
    charge_context: Optional[Literal["GENERAL", "ON_LIMIT", ...]] = None

# After:
class RetailAssetChargeRequest(BaseModel):
    description_keywords: Optional[List[str]] = None  # List of keywords to match in description
```

### 2. Lookup Logic
**No longer filters by `charge_context` column**, instead filters by `charge_description` text:

```python
# If description_keywords provided, filter by charge_description content
if request.description_keywords:
    filtered_charges = []
    for charge in charges:
        desc_lower = (charge.charge_description or "").lower()
        # Match if ANY keyword is found in description
        if any(keyword.lower() in desc_lower for keyword in request.description_keywords):
            filtered_charges.append(charge)
    
    if filtered_charges:
        charges = filtered_charges
```

### 3. Fee Engine Client
Automatically extracts description keywords from user query:

```python
# Extract keywords from query
if "enhancement" in query or "enhance" in query:
    description_keywords = ["enhancement", "enhance", "limit enhancement"]
elif "reduction" in query or "reduce" in query:
    description_keywords = ["reduction", "reduce", "limit reduction"]
elif "on limit" in query or "limit" in query:
    description_keywords = ["on limit", "limit"]
```

## How It Works

### User Query Flow

1. **User asks:** "What is the fast cash processing fee on limit?"

2. **Fee Engine Client extracts:**
   - `charge_type` = "PROCESSING_FEE"
   - `loan_product` = "FAST_CASH_OD" (if detected)
   - `description_keywords` = ["on limit", "limit"]

3. **Fee Engine Service:**
   - Queries database: `charge_type = "PROCESSING_FEE"` (and optionally `loan_product`)
   - Gets all matching charges
   - Filters by `charge_description` containing "on limit" or "limit"
   - Returns matching charge(s)

4. **Result:** Finds charge with description like "Processing Fee On Limit"

### Keyword Matching Examples

| User Query | Extracted Keywords | Matches Descriptions Containing |
|------------|-------------------|--------------------------------|
| "processing fee on limit" | ["on limit", "limit"] | "Processing Fee On Limit" |
| "limit enhancement fee" | ["enhancement", "enhance", "limit enhancement"] | "Limit Enhancement Processing Fee" |
| "limit reduction processing fee" | ["reduction", "reduce", "limit reduction"] | "Limit Reduction Processing Fee" |
| "processing fee" | [] | All processing fees (no filtering) |

## Database Schema

### `charge_context` Column
- **Remains unchanged** - still String(50) with whatever values exist
- **NOT used for lookups** - only for display/storage/documentation
- Can contain any text value (no enum constraint needed)

### `charge_description` Column
- **Used for all lookups** - the single source of truth
- Should contain clear, descriptive text about the charge
- Examples:
  - "Processing Fee On Limit"
  - "Limit Enhancement Processing Fee"
  - "Limit Reduction Processing Fee"
  - "General Processing Fee"

## Benefits

✅ **Simple & Direct**: Lookups match against actual charge descriptions
✅ **No Schema Changes**: `charge_context` column stays as-is
✅ **Flexible**: Works with any description text
✅ **Intuitive**: What you search for is what's in the description
✅ **Maintainable**: Single source of truth (`charge_description`)

## Migration

**No database migration needed!** This is a code-only change.

### To Deploy:

1. **Restart Fee Engine Service:**
   ```powershell
   docker-compose restart fee-engine
   ```

2. **Restart Chatbot Backend:**
   ```powershell
   docker-compose restart bank-chatbot-backend
   ```

3. **Test Queries:**
   - "What is the fast cash processing fee on limit?"
   - "What is the limit enhancement fee?"
   - "What is the processing fee for Fast Cash?"

## Admin Panel

The admin panel's `charge_context` field can still be used for:
- Documentation/notes
- Display purposes
- Internal categorization

But it **does NOT affect** how charges are looked up or matched.

## Fallback Behavior

1. **If keywords provided but no matches:** Retry without keywords (returns all charges for that charge_type)
2. **If charge_type not found:** Try PROCESSING_FEE as fallback (for enhancement/reduction fees)

This ensures users always get results even if keywords don't match perfectly.

## Example API Calls

### With Description Keywords:
```json
{
  "as_of_date": "2025-01-04",
  "charge_type": "PROCESSING_FEE",
  "loan_product": "FAST_CASH_OD",
  "description_keywords": ["on limit", "limit"]
}
```

### Without Keywords (all processing fees):
```json
{
  "as_of_date": "2025-01-04",
  "charge_type": "PROCESSING_FEE",
  "loan_product": "FAST_CASH_OD"
}
```

## Notes

- **`charge_context`** field: For display/documentation only
- **`charge_description`** field: For all lookup logic
- Keyword matching is **case-insensitive**
- Matching uses **substring search** (partial matches work)
- If **multiple matches** found: Returns all for disambiguation
