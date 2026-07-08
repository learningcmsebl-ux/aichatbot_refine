# Fee Engine — Data Quality Audit

**Date:** 2026-06-22
**Database:** `chatbot_db` (PostgreSQL 15.8)
**Tables audited:** `card_fee_master`, `retail_asset_charge_master_v2`, `skybanking_fee_master`
**Backup taken:** `bank_chatbot/backups/fee_tables_20260622_141915.sql` (pg_dump, all four fee tables incl. `card_fee_notes`)

---

## 1. Dataset size

| Table | Rows |
|-------|------|
| `card_fee_master` | 509 |
| `retail_asset_charge_master_v2` | 84 |
| `skybanking_fee_master` | 15 |
| **Total** | **608** |

The full dataset is tiny — quality, not volume, is the issue.

---

## 2. Severity summary

| # | Issue | Table | Count | Severity | Impact |
|---|-------|-------|-------|----------|--------|
| 1 | Non-canonical `charge_type` (free text / spaces) | card | 5 | High | Breaks exact-match lookups |
| 2 | `card_network` contains non-network text | card | 4 distinct bogus values | High | Network filter unreliable |
| 3 | `card_product` holds charge descriptions | card | ~4 rows | High | Product match degrades |
| 4 | `product_line` not segregating data | card | 509 (all `CREDIT_CARDS`) | High | Wrong product line for non-card rows |
| 5 | `TEXT` unit with numeric `fee_value` | card | 14 | Medium | Risk of wrong numeric answers |
| 6 | Suspect numeric values (rates as BDT, etc.) | card | ~3 confirmed | High | Confidently-wrong answers |
| 7 | `card_product` double-space | card | 28 | Medium | Match + display |
| 8 | `charge_type` leading/trailing space | card | 1 | Medium | Exact match fails |
| 9 | `answer_text` NULL/empty | card | 1 | Low | Fallback formatting |
| 10 | `answer_text` NULL/empty | skybanking | 6 / 15 | High | Weak/robotic answers |
| 11 | `answer_text` NULL/empty | retail | 33 / 84 | High | Weak/robotic answers |
| 12 | `parse_status = UNPARSED` | retail | 84 / 84 | High | No structured fee fields |
| 13 | Inconsistent naming convention across tables | all | — | Medium | Cross-table logic complexity |
| 14 | Potential duplicate rows (need review) | card | up to 16 groups | Medium | Ambiguous matches |

---

## 3. Detailed findings

### 3.1 `charge_type` is the primary lookup key but is not normalized
Most values are clean `UPPER_SNAKE_CASE` (e.g. `OVERLIMIT`, `PIN_REPLACEMENT`, `LATE_PAYMENT`). The following 5 rows break the convention:

| `charge_type` | `card_product` | `card_network` | Issue |
|---------------|----------------|----------------|-------|
| `All Card Related Payment` | `All Card Related Payment` | `All Card Related Payment` | Free text in 3 columns |
| `All_Card_Related_Payment` | `ANY` | `payment rate` | Duplicate concept, different format |
| `Government Fees for Skybanking` | `A Challan Fees for Skybanking` | `A Challan Fee` | Belongs in skybanking table |
| ` Partial payment fee` | `Mortgage Loan Payment Protection` | `Mortgage Loan Payment Protection` | Leading space, lowercase; belongs in retail |
| `Priority_banking` | `Endorsement Fee for Priority and General customers` | `Foreign Currency (FCY)  Endorsement` | Belongs in priority/skybanking |

`All Card Related Payment` vs `All_Card_Related_Payment` are **effective duplicates**.

### 3.2 `card_network` column polluted
Distinct values include 4 that are **not networks**:
`A Challan Fee`, `All Card Related Payment`, `Foreign Currency (FCY)  Endorsement`, `Mortgage Loan Payment Protection`, `payment rate`.
Valid networks present: `VISA`, `MASTERCARD`, `UNIONPAY`, `DINERS`, `TAKAPAY`.
The fee engine filters on `card_network` (`fee_engine_service.py:255` `_apply_card_network_filter`), so polluted rows can't be filtered correctly.

### 3.3 `card_product` holds charge descriptions
Examples placed in the product column instead of a product:
`Endorsement Fee for Priority and General customers`, `A Challan Fees for Skybanking`, `Mortgage Loan Payment Protection`, `All Card Related Payment`.

### 3.4 `product_line` not segregating
All 509 card rows are `product_line = CREDIT_CARDS`, including the Priority Banking, Skybanking and Mortgage rows above. These should live in their correct product-line tables, not in `card_fee_master`.

### 3.5 Suspect numeric values
- `INTEREST_RATE` / Women Platinum → `0.2500 BDT` → *"BDT 0.25 per year"* — an interest rate stored as a BDT amount (almost certainly wrong).
- `RISK_ASSURANCE_FEE` → `0.0035`, unit `TEXT` → a 0.35% rate mis-encoded as text/number.
- `All_Card_Related_Payment` → `123.8888 BDT` — placeholder while the real answer is a USD payment-rate note.
- 14 rows have `fee_unit = 'TEXT'` but a non-zero numeric `fee_value`.

### 3.6 Whitespace hygiene
- `card_product` containing a double space: **28 rows** (e.g. `Women  Platinum` → should be `Women Platinum`).
- `card_network` double space: 1 (`Foreign Currency (FCY)  Endorsement`).
- `charge_type` with leading/trailing space: 1 (` Partial payment fee`).

### 3.7 `answer_text` completeness (drives "human" responses)
| Table | NULL/empty `answer_text` | Total |
|-------|--------------------------|-------|
| card | 1 | 509 |
| skybanking | 6 | 15 |
| retail | 33 | 84 |

Skybanking NULLs include: `VISA Credit Card Bill Payment`, several `Certificate Fee` rows (NOC, Balance, Loan Outstanding, DPS), `NPSB Fund Transfer`.

### 3.8 Retail asset charges unparsed
All **84** retail rows are `parse_status = UNPARSED` — none have structured fee fields populated, and 33 also lack `answer_text`. This is the weakest product line for accuracy. (`loan_product_name` is fully populated — good.)

### 3.9 Naming convention differs across tables
- `card_fee_master.charge_type` → `UPPER_SNAKE_CASE`
- `retail_asset_charge_master_v2.charge_type` → `UPPER_SNAKE_CASE` (clean: `PROCESSING_FEE`, `EARLY_SETTLEMENT_FEE`, …)
- `skybanking_fee_master.charge_type` → `Title Case With Spaces` (`Add Money Fee`, `Certificate Fee`, `Fund Transfer`)

Mixed conventions force the matching layer to handle multiple formats.

### 3.10 Potential duplicates (need review, not blind dedupe)
Up to 16 groups share the same `(charge_type, card_product, card_network)`. **Many are legitimate** — e.g. `OVERLIMIT / Women Platinum / VISA` has 2 rows because one is BDT and one is USD. Others (3-row groups on `ANY`) may differ by currency, effective date, or condition. Each group should be reviewed against `fee_unit`/`effective_from`/`condition_type` before any merge.

---

## 4. Why this hurts the two goals

- **Accuracy:** the deterministic cascade (`fee_engine_service.py:505+`) tries exact match on `charge_type` + `card_network` + `card_product` first. Polluted keys force fall-through to fuzzy `ILIKE`, which is where wrong-row matches happen. Suspect numerics produce confidently-wrong figures.
- **Natural conversation:** the bot returns `answer_text` verbatim. With 40 of 608 rows missing `answer_text` (and skybanking/retail worst affected), those queries get terse, fragment-style, or fallback-formatted replies instead of full human sentences.

---

## 5. Recommended cleanup (staged, safe)

1. **Controlled vocabularies + mapping table** for `charge_type`, `card_network`, `card_product` (canonical value per existing value).
2. **Relocate misplaced rows** (Priority/Skybanking/Mortgage/"All Card Related Payment") into `skybanking_fee_master` / retail tables; fix their `product_line`.
3. **Trim whitespace**, collapse double spaces (`Women  Platinum` → `Women Platinum`).
4. **Numeric audit** of `INTEREST_RATE`, `RISK_ASSURANCE_FEE`, and all 14 `TEXT`-unit numeric rows against `answer_text`.
5. **Backfill `answer_text`** (1 card + 6 skybanking + 33 retail) and **run the retail parser** so `parse_status = PARSED`.
6. **Standardize `answer_text` tone** — full sentences, consistent currency formatting.
7. **Post-cleanup constraints + indexes**: enum/`CHECK` on controlled columns + index on `(status, product_line, charge_type, card_product, card_network)`.

All changes should be delivered as idempotent SQL migrations in `bank_chatbot/migrations/`, run against a copy first, with a before/after distinct-value diff for review. Future edits should route through the admin panel (`admin_panel/admin_api.py`) with write-time validation.

---

## 6. Backup details

```
File: bank_chatbot/backups/fee_tables_20260622_141915.sql
Tool: pg_dump (PostgreSQL 15.8)
Tables: card_fee_master, card_fee_notes, retail_asset_charge_master_v2, skybanking_fee_master
```

Restore (if ever needed):
```powershell
docker exec -i chatbot_postgres psql -U chatbot_user -d chatbot_db < bank_chatbot/backups/fee_tables_20260622_141915.sql
```
