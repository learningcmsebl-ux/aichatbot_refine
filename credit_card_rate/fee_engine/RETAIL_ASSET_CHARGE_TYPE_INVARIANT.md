# Retail Asset Charge Type Data Model Invariant

## Documented: 2025-12-30

## Invariant Rule

**For all retail asset loan products, enhancement/reduction processing fees are modeled as:**
- `charge_type = PROCESSING_FEE`
- `charge_context = ON_ENHANCED_AMOUNT` (for limit enhancement processing fees)
- `charge_context = ON_REDUCED_AMOUNT` (for limit reduction processing fees)
- `charge_context = GENERAL` (for standard processing fees)
- `charge_context = ON_LIMIT` (for processing fees on limit/loan amount)

**NOT as separate charge_types:**
- ❌ `LIMIT_ENHANCEMENT_FEE` (does not exist in database)
- ❌ `LIMIT_REDUCTION_FEE` (does not exist in database)

## Database Audit Results

**Audit Date:** 2025-12-30

**Fast Cash (FAST_CASH_OD) Charge Distribution:**
```
Charge Type                    Charge Context            Count
PROCESSING_FEE                 GENERAL                   1
PROCESSING_FEE                 ON_ENHANCED_AMOUNT        1
PROCESSING_FEE                 ON_REDUCED_AMOUNT         1
LIMIT_CANCELLATION_FEE         GENERAL                   1
RENEWAL_FEE                    GENERAL                   1
```

**All Loan Products:**
- ✅ No `LIMIT_ENHANCEMENT_FEE` charge_type found in any loan product
- ✅ No `LIMIT_REDUCTION_FEE` charge_type found in any loan product
- ✅ All enhancement/reduction processing fees use `PROCESSING_FEE` with `charge_context`

## Implementation Rules

1. **Query Mapping:**
   - "limit enhancement processing fee" → `PROCESSING_FEE` + `ON_ENHANCED_AMOUNT`
   - "limit reduction processing fee" → `PROCESSING_FEE` + `ON_REDUCED_AMOUNT`
   - "processing fee" → `PROCESSING_FEE` + `GENERAL` (or context from query)

2. **DB-Driven Fallback:**
   - If query maps to `LIMIT_ENHANCEMENT_FEE`/`LIMIT_REDUCTION_FEE` but returns `NO_RULE_FOUND`
   - AND query contains "processing fee"
   - AND `charge_context` is `ON_ENHANCED_AMOUNT`/`ON_REDUCED_AMOUNT`
   - THEN retry with `PROCESSING_FEE` + same `charge_context`

3. **Data Entry Guideline:**
   - When adding new enhancement/reduction processing fees:
     - Use `charge_type = PROCESSING_FEE`
     - Set `charge_context = ON_ENHANCED_AMOUNT` or `ON_REDUCED_AMOUNT`
     - Do NOT create `LIMIT_ENHANCEMENT_FEE` or `LIMIT_REDUCTION_FEE` charge_types

## Enforcement

- Database constraint: Partial unique index on `(loan_product, charge_type, charge_context, effective_from)` ensures no duplicates
- Code validation: Fee engine service validates charge_type against enum
- Migration script: `migrate_retail_asset_to_v2.py` enforces this pattern during data migration

