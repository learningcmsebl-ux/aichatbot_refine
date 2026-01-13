-- Data backfill (Retail Assets v2): Populate fee_text + structured fields + answer_text
-- Run this AFTER schema_retail_asset_v2_answer_text_extension.sql has been applied.
--
-- This script is intentionally conservative:
-- - It never deletes or overwrites existing numeric fee structures.
-- - It prefers existing `answer_text` (manual overrides) when present.
-- - It backfills `fee_text` primarily from `original_charge_text`, then `remarks`.
-- - It parses common patterns (percent, BDT/Tk amounts, period hints, applies-to hints).

BEGIN;

-- 1) Backfill fee_text from existing human-readable sources
UPDATE retail_asset_charge_master_v2
SET
  fee_text = COALESCE(
    NULLIF(TRIM(fee_text), ''),
    NULLIF(TRIM(original_charge_text), ''),
    NULLIF(TRIM(remarks), '')
  ),
  parsed_from = CASE
    WHEN fee_text IS NOT NULL AND TRIM(fee_text) <> '' THEN COALESCE(parsed_from, 'fee_text')
    WHEN original_charge_text IS NOT NULL AND TRIM(original_charge_text) <> '' THEN COALESCE(parsed_from, 'original_charge_text')
    WHEN remarks IS NOT NULL AND TRIM(remarks) <> '' THEN COALESCE(parsed_from, 'remarks')
    ELSE parsed_from
  END,
  parsed_at = COALESCE(parsed_at, now())
WHERE
  (fee_text IS NULL OR TRIM(fee_text) = '')
  AND (
    (original_charge_text IS NOT NULL AND TRIM(original_charge_text) <> '')
    OR (remarks IS NOT NULL AND TRIM(remarks) <> '')
  );

-- 2) Parse percentage from fee_text (e.g., "1.50%")
WITH pct AS (
  SELECT
    charge_id,
    (regexp_match(fee_text, '([0-9]+(?:\\.[0-9]+)?)\\s*%'))[1] AS pct_str
  FROM retail_asset_charge_master_v2
  WHERE fee_text IS NOT NULL AND fee_rate_value IS NULL
)
UPDATE retail_asset_charge_master_v2 t
SET
  fee_rate_value = NULLIF(p.pct_str, '')::NUMERIC(15,4),
  fee_rate_unit = COALESCE(t.fee_rate_unit, 'PERCENT'),
  parsed_at = now()
FROM pct p
WHERE t.charge_id = p.charge_id AND p.pct_str IS NOT NULL;

-- 3) Parse BDT/Tk amount from fee_text (e.g., "BDT 1,150" / "Tk. 402.5")
WITH amt AS (
  SELECT
    charge_id,
    (regexp_match(fee_text, '(?:BDT|Tk\\.?)[\\s]*([0-9]+(?:,[0-9]{3})*(?:\\.[0-9]+)?)'))[1] AS amt_str
  FROM retail_asset_charge_master_v2
  WHERE fee_text IS NOT NULL AND fee_amount_value IS NULL
)
UPDATE retail_asset_charge_master_v2 t
SET
  fee_amount_value = REPLACE(a.amt_str, ',', '')::NUMERIC(15,4),
  fee_amount_currency = COALESCE(t.fee_amount_currency, 'BDT'),
  parsed_at = now()
FROM amt a
WHERE t.charge_id = a.charge_id AND a.amt_str IS NOT NULL;

-- 4) Infer fee_period from fee_text
UPDATE retail_asset_charge_master_v2
SET
  fee_period = COALESCE(
    fee_period,
    CASE
      WHEN fee_text ILIKE '%per month%' OR fee_text ILIKE '%monthly%' THEN 'PER_MONTH'
      WHEN fee_text ILIKE '%per day%' OR fee_text ILIKE '%daily%' THEN 'PER_DAY'
      WHEN fee_text ILIKE '%per year%' OR fee_text ILIKE '%per annum%' OR fee_text ILIKE '%yearly%' OR fee_text ILIKE '%p.a.%' THEN 'PER_YEAR'
      WHEN fee_text ILIKE '%per transaction%' OR fee_text ILIKE '%per txn%' OR fee_text ILIKE '%per tx%' THEN 'PER_TRANSACTION'
      WHEN fee_text ILIKE '%one time%' OR fee_text ILIKE '%one-time%' THEN 'ONE_TIME'
      ELSE fee_period
    END
  ),
  parsed_at = now()
WHERE fee_text IS NOT NULL AND fee_period IS NULL;

-- 5) Infer fee_applies_to from fee_text / description
UPDATE retail_asset_charge_master_v2
SET
  fee_applies_to = COALESCE(
    fee_applies_to,
    CASE
      WHEN fee_text ILIKE '%overdue%' OR charge_description ILIKE '%overdue%' THEN 'ON_OVERDUE_AMOUNT'
      WHEN fee_text ILIKE '%loan amount%' OR charge_description ILIKE '%loan amount%' THEN 'ON_LOAN_AMOUNT'
      WHEN fee_text ILIKE '%on limit%' OR fee_text ILIKE '%limit%' OR charge_description ILIKE '%limit%' THEN 'ON_LIMIT'
      ELSE fee_applies_to
    END
  ),
  parsed_at = now()
WHERE (fee_text IS NOT NULL OR charge_description IS NOT NULL) AND fee_applies_to IS NULL;

-- 6) Generate answer_text (authoritative verbatim output)
-- Priority:
-- 1) existing answer_text (manual)
-- 2) fee_text (preferred)
-- 3) original_charge_text (fallback)
-- 4) deterministic formatting from numeric/tier fields
UPDATE retail_asset_charge_master_v2
SET
  answer_text = COALESCE(
    NULLIF(TRIM(answer_text), ''),
    NULLIF(TRIM(fee_text), ''),
    NULLIF(TRIM(original_charge_text), ''),
    CASE
      WHEN tier_1_rate_value IS NOT NULL THEN
        CONCAT(
          'Tier 1: ',
          tier_1_rate_value::TEXT,
          CASE WHEN tier_1_rate_unit = 'PERCENT' THEN '%' ELSE CONCAT(' ', COALESCE(tier_1_rate_unit, '')) END,
          CASE
            WHEN tier_1_max_fee_value IS NOT NULL THEN CONCAT(' (max ', tier_1_max_fee_value::TEXT, ' ', COALESCE(tier_1_max_fee_currency, 'BDT'), ')')
            ELSE ''
          END,
          CASE
            WHEN tier_2_rate_value IS NOT NULL THEN CONCAT(
              '; Tier 2: ',
              tier_2_rate_value::TEXT,
              CASE WHEN tier_2_rate_unit = 'PERCENT' THEN '%' ELSE CONCAT(' ', COALESCE(tier_2_rate_unit, '')) END,
              CASE
                WHEN tier_2_max_fee_value IS NOT NULL THEN CONCAT(' (max ', tier_2_max_fee_value::TEXT, ' ', COALESCE(tier_2_max_fee_currency, 'BDT'), ')')
                ELSE ''
              END
            )
            ELSE ''
          END
        )
      WHEN fee_value IS NOT NULL THEN
        CONCAT(
          fee_value::TEXT,
          ' ',
          fee_unit,
          CASE
            WHEN min_fee_value IS NOT NULL OR max_fee_value IS NOT NULL THEN
              CONCAT(
                ' (',
                CASE WHEN min_fee_value IS NOT NULL THEN CONCAT('Min: ', min_fee_value::TEXT, ' ', COALESCE(min_fee_currency, 'BDT')) ELSE '' END,
                CASE WHEN min_fee_value IS NOT NULL AND max_fee_value IS NOT NULL THEN ', ' ELSE '' END,
                CASE WHEN max_fee_value IS NOT NULL THEN CONCAT('Max: ', max_fee_value::TEXT, ' ', COALESCE(max_fee_currency, 'BDT')) ELSE '' END,
                ')'
              )
            ELSE ''
          END
        )
      WHEN fee_rate_value IS NOT NULL THEN
        CONCAT(
          fee_rate_value::TEXT,
          CASE WHEN fee_rate_unit = 'PERCENT' THEN '%' ELSE CONCAT(' ', fee_rate_unit) END,
          CASE
            WHEN fee_applies_to IS NOT NULL THEN CONCAT(' on ', REPLACE(LOWER(fee_applies_to), '_', ' '))
            ELSE ''
          END
        )
      WHEN fee_amount_value IS NOT NULL THEN
        CONCAT(
          COALESCE(fee_amount_currency, 'BDT'),
          ' ',
          fee_amount_value::TEXT
        )
      ELSE NULL
    END
  ),
  parse_status = CASE
    WHEN NULLIF(TRIM(answer_text), '') IS NOT NULL THEN 'MANUAL'
    WHEN NULLIF(TRIM(fee_text), '') IS NOT NULL OR fee_rate_value IS NOT NULL OR fee_amount_value IS NOT NULL THEN 'PARSED'
    WHEN fee_value IS NOT NULL OR tier_1_rate_value IS NOT NULL THEN 'PARSED'
    ELSE 'UNPARSEABLE'
  END,
  parsed_at = now()
WHERE answer_text IS NULL OR TRIM(answer_text) = '';

COMMIT;

