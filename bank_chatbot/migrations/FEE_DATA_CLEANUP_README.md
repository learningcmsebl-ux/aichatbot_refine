# Fee Data Cleanup Migrations

Staged, idempotent SQL migrations to improve fee lookup accuracy and conversational answer quality.

**Prerequisite backup:** `bank_chatbot/backups/fee_tables_20260622_141915.sql`  
**Audit report:** `bank_chatbot/FEE_DATA_QUALITY_AUDIT.md`

## Run order

| # | File | What it does |
|---|------|--------------|
| 1 | `fee_cleanup_01_vocab_and_review_queue.sql` | Creates `fee_field_aliases` + `fee_data_review_queue`; flags INTEREST_RATE rows for business review |
| 2 | `fee_cleanup_02_whitespace_normalize.sql` | Trims / collapses whitespace on lookup keys |
| 3 | `fee_cleanup_03_relocate_misplaced_card_rows.sql` | Normalizes 5 bad card rows; deactivates duplicates/misplaced rows |
| 4 | `fee_cleanup_04_numeric_semantics.sql` | Fixes RISK_ASSURANCE_FEE 0.0035 TEXT → 0.35% PERCENT |
| 5 | `fee_cleanup_05_skybanking_answer_text.sql` | Backfills 6 missing skybanking `answer_text` rows |
| 6 | `fee_cleanup_06_retail_answer_text_backfill.sql` | Parses + backfills retail `answer_text`; sets `parse_status=PARSED` |
| 7 | `fee_cleanup_07_card_answer_text_gaps.sql` | Fills remaining card `answer_text` gap (SKYLOUNGE Platinum) |
| 8 | `fee_cleanup_08_indexes.sql` | Adds lookup indexes |
| 9 | `fee_cleanup_09_dedupe_and_cctv_review.sql` | Deactivates 8 exact duplicate rows; queues VISA CREDIT CCTV 21 BDT for review |

## Apply (PowerShell)

```powershell
cd e:\Chatbot_refine\bank_chatbot
$migrations = @(
  "migrations/fee_cleanup_01_vocab_and_review_queue.sql",
  "migrations/fee_cleanup_02_whitespace_normalize.sql",
  "migrations/fee_cleanup_03_relocate_misplaced_card_rows.sql",
  "migrations/fee_cleanup_04_numeric_semantics.sql",
  "migrations/fee_cleanup_05_skybanking_answer_text.sql",
  "migrations/fee_cleanup_06_retail_answer_text_backfill.sql",
  "migrations/fee_cleanup_07_card_answer_text_gaps.sql",
  "migrations/fee_cleanup_08_indexes.sql",
  "migrations/fee_cleanup_09_dedupe_and_cctv_review.sql"
)
foreach ($f in $migrations) {
  Write-Host "Running $f ..."
  Get-Content $f -Raw | docker exec -i chatbot_postgres psql -U chatbot_user -d chatbot_db
}
```

## Verify after run

```powershell
docker exec chatbot_postgres psql -U chatbot_user -d chatbot_db -c "
SELECT 'card bad charge_type' m, count(*) FROM card_fee_master WHERE status='ACTIVE' AND charge_type ~ '[a-z ]'
UNION ALL SELECT 'card bad network', count(*) FROM card_fee_master WHERE status='ACTIVE' AND card_network NOT IN ('VISA','MASTERCARD','DINERS','UNIONPAY','TAKAPAY','FX','ANY')
UNION ALL SELECT 'skybanking missing answer', count(*) FROM skybanking_fee_master WHERE answer_text IS NULL OR btrim(answer_text)=''
UNION ALL SELECT 'retail missing answer', count(*) FROM retail_asset_charge_master_v2 WHERE answer_text IS NULL OR btrim(answer_text)=''
UNION ALL SELECT 'retail UNPARSED', count(*) FROM retail_asset_charge_master_v2 WHERE parse_status='UNPARSED'
UNION ALL SELECT 'review queue open', count(*) FROM fee_data_review_queue WHERE status='OPEN';
"
```

## Not auto-fixed (needs business sign-off)

- **INTEREST_RATE** (14 rows): stored as `0.25 BDT` with answer *"BDT 0.25 per year"*. Queued in `fee_data_review_queue` — confirm correct rate with product team before changing unit/value.
- **Duplicate card groups** (multi-currency rows): reviewed manually; not merged.

## Rollback

Restore from backup (fee tables only):

```powershell
Get-Content backups/fee_tables_20260622_141915.sql -Raw | docker exec -i chatbot_postgres psql -U chatbot_user -d chatbot_db
```

Drop cleanup artifacts if needed:

```sql
DROP TABLE IF EXISTS fee_field_aliases;
DROP TABLE IF EXISTS fee_data_review_queue;
DROP FUNCTION IF EXISTS fee_normalize_ws(TEXT);
```
