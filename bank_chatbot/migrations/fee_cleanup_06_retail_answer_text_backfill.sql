-- Fee data cleanup (stage 6): retail answer_text backfill + light parsing
-- Adapted from credit_card_rate/fee_engine/schema_retail_asset_v2_answer_text_backfill.sql
-- Idempotent: does not overwrite existing answer_text.

BEGIN;

-- 6a) Populate fee_text from original_charge_text / remarks
UPDATE retail_asset_charge_master_v2
SET
    fee_text = COALESCE(
        NULLIF(btrim(fee_text), ''),
        NULLIF(btrim(original_charge_text), ''),
        NULLIF(btrim(remarks), '')
    ),
    parsed_from = CASE
        WHEN fee_text IS NOT NULL AND btrim(fee_text) <> '' THEN COALESCE(parsed_from, 'fee_text')
        WHEN original_charge_text IS NOT NULL AND btrim(original_charge_text) <> '' THEN COALESCE(parsed_from, 'original_charge_text')
        WHEN remarks IS NOT NULL AND btrim(remarks) <> '' THEN COALESCE(parsed_from, 'remarks')
        ELSE parsed_from
    END,
    parsed_at = COALESCE(parsed_at, NOW())
WHERE (fee_text IS NULL OR btrim(fee_text) = '')
  AND (
      (original_charge_text IS NOT NULL AND btrim(original_charge_text) <> '')
      OR (remarks IS NOT NULL AND btrim(remarks) <> '')
  );

-- 6b) Parse percentage from fee_text when structured fee_value is missing
WITH pct AS (
    SELECT
        charge_id,
        (regexp_match(fee_text, '([0-9]+(?:\.[0-9]+)?)\s*%'))[1] AS pct_str
    FROM retail_asset_charge_master_v2
    WHERE fee_text IS NOT NULL
      AND fee_rate_value IS NULL
      AND (fee_value IS NULL OR fee_unit IS NULL)
)
UPDATE retail_asset_charge_master_v2 t
SET
    fee_rate_value = NULLIF(p.pct_str, '')::NUMERIC(15, 4),
    fee_rate_unit  = COALESCE(t.fee_rate_unit, 'PERCENT'),
    parsed_at      = NOW()
FROM pct p
WHERE t.charge_id = p.charge_id
  AND p.pct_str IS NOT NULL;

-- 6c) Backfill answer_text (prefer manual, then fee_text, then original_charge_text, then structured fields)
UPDATE retail_asset_charge_master_v2
SET
    answer_text = COALESCE(
        NULLIF(btrim(answer_text), ''),
        CASE
            WHEN fee_text IS NOT NULL AND btrim(fee_text) <> '' THEN
                charge_title || ' is ' || btrim(fee_text) || '.'
            WHEN original_charge_text IS NOT NULL AND btrim(original_charge_text) <> '' THEN
                charge_title || ' is ' || btrim(original_charge_text) || '.'
            WHEN fee_value IS NOT NULL AND fee_unit = 'PERCENT' THEN
                charge_title || ' is ' || fee_value::TEXT || '%.'
            WHEN fee_value IS NOT NULL THEN
                charge_title || ' is ' || fee_value::TEXT || ' ' || fee_unit::TEXT || '.'
            WHEN fee_rate_value IS NOT NULL THEN
                charge_title || ' is ' || fee_rate_value::TEXT ||
                CASE WHEN fee_rate_unit = 'PERCENT' THEN '%' ELSE ' ' || COALESCE(fee_rate_unit, '') END || '.'
            ELSE NULL
        END
    ),
    parsed_at = NOW()
WHERE answer_text IS NULL OR btrim(answer_text) = '';

-- 6d) Mark rows that now have answer_text as PARSED (unless already MANUAL)
UPDATE retail_asset_charge_master_v2
SET
    parse_status = 'PARSED',
    parsed_at    = COALESCE(parsed_at, NOW())
WHERE parse_status = 'UNPARSED'
  AND answer_text IS NOT NULL
  AND btrim(answer_text) <> '';

COMMIT;
