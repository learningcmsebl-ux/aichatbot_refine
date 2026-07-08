# Fee Engine — Optimization Audit (Round 2)

**Date:** 2026-06-22  
**Database:** `chatbot_db` (PostgreSQL 15.8)  
**Context:** Post `fee_cleanup_*` migrations + service restart

---

## 1. Executive summary

| Area | Verdict |
|------|---------|
| **Lookup performance** | Already excellent — card fee queries ~0.2 ms, retail ~0.7 ms |
| **Data hygiene (stage 1 cleanup)** | Clean — 0 bad networks, 0 missing answers, retail 100% PARSED |
| **Remaining accuracy risk** | 8 exact duplicate rows, ~6 suspect low-fee CCTV rows (21 BDT), 14 INTEREST_RATE rows in review queue |
| **In-memory cache** | Optional — helps **consistency & alias resolution**, not raw speed at 608 rows |
| **Index tuning** | One redundant new index; `ANALYZE` recommended after bulk updates |

---

## 2. Performance findings

### 2.1 Query plans (post-cleanup)

**Card lookup** (`PIN_REPLACEMENT`, Platinum, VISA):
- Uses `idx_fee_lookup` (Bitmap Index Scan)
- **Execution time: 0.19 ms**

**Retail lookup** (`HOME_LOAN`, `PARTIAL_PAYMENT_FEE`):
- Uses `no_overlap_active_rules` exclusion index
- **Execution time: 0.67 ms**

### 2.2 Dataset size

| Table | Active rows | Total size |
|-------|-------------|------------|
| `card_fee_master` | 503 | 808 kB |
| `retail_asset_charge_master_v2` | 84 | 320 kB |
| `skybanking_fee_master` | 15 | small |
| **Fee total** | **602** | **< 1 MB** |

At this scale, PostgreSQL is not the bottleneck. Fee engine has **no in-memory cache** today; every request hits the DB, which is still sub-millisecond.

### 2.2 In-memory cache recommendation

| Approach | When to use |
|----------|-------------|
| **Startup preload** (recommended) | Load all `ACTIVE` fee rows into a dict keyed by `(product_line, charge_type, network, product, category)` at fee-engine boot; TTL refresh every 5–15 min or on admin save |
| **Redis cache** | Only if fee engine scales to multiple replicas and you need shared invalidation |
| **Skip cache** | Acceptable at current load — DB is already fast |

**Primary benefit of preload:** deterministic rule selection without duplicate-row ambiguity, plus applying `fee_field_aliases` in one place before match — not latency.

---

## 3. Data quality — post-cleanup status

### 3.1 Clean (no action needed)

| Check | Count |
|-------|-------|
| Active card rows with bad `card_network` | 0 |
| Active card rows with lowercase `charge_type` | 0 |
| Active card rows with double-space `card_product` | 0 |
| Missing `answer_text` (card / skybanking / retail) | 0 |
| Retail `parse_status = UNPARSED` | 0 |
| `RISK_ASSURANCE_FEE` TEXT-unit mis-encoding | 0 (fixed → 0.35% PERCENT) |

### 3.2 Open business review (`fee_data_review_queue`)

| Issue | Rows | Notes |
|-------|------|-------|
| `INTEREST_RATE_UNIT_SUSPECT` | 14 | Still `0.25 BDT` / *"BDT 0.25 per year"* — confirm correct APR with product team |

---

## 4. New findings — accuracy (priority)

### 4.1 Exact duplicate rows (8 groups → 8 rows to deactivate)

Identical active rows (same keys, value, dates, priority). Fee engine may return either arbitrarily.

| charge_type | card_product | network | category | fee_value | duplicate count |
|-------------|--------------|---------|----------|-----------|-----------------|
| `TRANSACTION_ALERT_ANNUAL` | ANY | VISA | DEBIT | 0 TEXT | 2 |
| `TRANSACTION_ALERT_ANNUAL` | ANY | MASTERCARD | DEBIT | 0 TEXT | 2 |
| `SKYLOUNGE_FREE_VISITS_DOM_ANNUAL` | ANY | MASTERCARD | DEBIT | 0 TEXT | 2 |
| `SKYLOUNGE_FREE_VISITS_INTL_ANNUAL` | ANY | MASTERCARD | DEBIT | 0 TEXT | 2 |
| `ATM_RECEIPT_EBL` | ANY | VISA | DEBIT | 3.45 BDT | 2 |
| `ATM_CCTV_FOOTAGE_INSIDE_DHAKA` | ANY | VISA | DEBIT | 2300 BDT | 2 |
| `ATM_CCTV_FOOTAGE_OUTSIDE_DHAKA` | ANY | VISA | DEBIT | 3450 BDT | 2 |
| `CERTIFICATE_FEE` | ANY | VISA | DEBIT | 57.5 BDT | 2 |

**Action:** Stage 9 migration — deactivate the younger duplicate in each pair (keep lowest `fee_id` or earliest `created_at`).

### 4.2 Suspect CCTV fees — VISA CREDIT at 21 BDT

Most networks/categories use **2300 BDT** (inside) / **3450 BDT** (outside). VISA **CREDIT** rows are **21 BDT** — likely import/decimal error:

| charge_type | category | network | fee_value | Expected pattern |
|-------------|----------|---------|-----------|------------------|
| `ATM_CCTV_FOOTAGE_INSIDE_DHAKA` | CREDIT | VISA | **21** | 2300 (matches DINERS/UNIONPAY CREDIT) |
| `ATM_CCTV_FOOTAGE_OUTSIDE_DHAKA` | CREDIT | VISA | **21** | 3450 (matches DINERS/UNIONPAY CREDIT) |

DEBIT MASTERCARD also has conflicting **21 vs 2300/3450** pairs — the 21 BDT row is likely wrong; exact duplicate 2300 rows should be deduped.

**Action:** Add to `fee_data_review_queue` with code `CCTV_VISA_CREDIT_SUSPECT`; confirm against official SOC before updating.

### 4.3 Legitimate multi-value groups (do not merge)

**32 groups** share the same product key but differ by `fee_value` / `fee_unit`. Most are **valid multi-currency** rows, e.g.:

- `LATE_PAYMENT` / Platinum / VISA → **1380 BDT** and **17.25 USD**
- `OVERLIMIT` → BDT and USD variants

These should stay; fee engine should disambiguate by `currency` request param.

### 4.4 Low-quality `answer_text` (cosmetic)

| Pattern | Count | Impact |
|---------|-------|--------|
| `BDT 0.00 per year` | 14 | SKYLOUNGE rows — technically correct but not conversational |
| `2.36% or BDT 0.00` | 13 | WHICHEVER_HIGHER rules — acceptable but could be full sentences |

---

## 5. Index & database maintenance

### 5.1 Index usage (fee tables)

| Index | Scans | Verdict |
|-------|-------|---------|
| `idx_fee_lookup` | 148+ | **Primary workhorse** — keep |
| `idx_fee_product_line` | 14+ | Used — keep |
| `idx_card_fee_active_lookup` | **0** | **Redundant** with `idx_fee_lookup` — safe to drop after monitoring |
| `idx_retail_v2_answer_missing` | 1 | QA-only — keep or drop after cleanup verified |
| `idx_skybanking_active_lookup` | 0 | Low traffic — keep (15 rows, negligible cost) |

### 5.2 `chat_messages` redundant indexes

| Index | Notes |
|-------|-------|
| `ix_chat_messages_id` | Duplicates PK |
| `ix_chat_messages_session_id` | Overlaps `idx_session_created` |

Consider dropping when table grows; low impact at 128 rows today.

### 5.3 Statistics

Run after any bulk migration:

```sql
ANALYZE card_fee_master;
ANALYZE retail_asset_charge_master_v2;
ANALYZE skybanking_fee_master;
```

`pg_stat` showed `n_live_tup = 0` for `card_fee_master` until autoanalyze ran — planner stats were stale briefly after cleanup.

---

## 6. Retail structured fields (lower priority)

| Metric | Value |
|--------|-------|
| Rows with `answer_text` | 84 / 84 |
| Rows with `parse_status = PARSED` | 84 / 84 |
| Rows with null `fee_value` AND null `fee_rate_value` | 43 |

The 43 text-only rows still answer correctly via `answer_text` / `original_charge_text`. Optional stage 10: run deeper parser from `schema_retail_asset_v2_answer_text_backfill.sql` to populate tier/min/max fields for admin UI.

---

## 7. Recommended next steps (prioritized)

| Priority | Action | Effort |
|----------|--------|--------|
| **P1** | Migration `fee_cleanup_09_dedupe_exact_duplicates.sql` — deactivate 8 redundant rows | Low |
| **P1** | Queue CCTV VISA CREDIT 21 BDT rows for business review | Low |
| **P1** | Product team resolves 14 `INTEREST_RATE` rows | Business |
| **P2** | Fee engine startup preload cache (~600 rows) + invalidation on admin write | Medium |
| **P2** | `ANALYZE` fee tables; drop `idx_card_fee_active_lookup` if still unused | Low |
| **P3** | Improve SKYLOUNGE `answer_text` to link https://ebl.com.bd/skylounge | Low |
| **P3** | Drop redundant `chat_messages` indexes when table > 10k rows | Low |

---

## 8. Verification commands

```powershell
# Quick health dashboard
docker exec chatbot_postgres psql -U chatbot_user -d chatbot_db -c "
SELECT 'exact_dup_groups' m, count(*) FROM (
  SELECT 1 FROM card_fee_master WHERE status='ACTIVE'
  GROUP BY charge_type,card_product,card_network,card_category,product_line,
           fee_value,fee_unit,fee_basis,effective_from,effective_to
  HAVING count(*)>1
) x
UNION ALL SELECT 'review_queue', count(*) FROM fee_data_review_queue WHERE status='OPEN'
UNION ALL SELECT 'missing_answers', count(*) FROM card_fee_master WHERE status='ACTIVE' AND (answer_text IS NULL OR btrim(answer_text)='');
"

# Query timing
docker exec chatbot_postgres psql -U chatbot_user -d chatbot_db -c "
EXPLAIN (ANALYZE, TIMING) SELECT * FROM card_fee_master
WHERE status='ACTIVE' AND charge_type='PIN_REPLACEMENT' AND product_line='CREDIT_CARDS'
  AND card_network IN ('VISA','ANY') AND effective_from <= CURRENT_DATE LIMIT 10;
"
```
