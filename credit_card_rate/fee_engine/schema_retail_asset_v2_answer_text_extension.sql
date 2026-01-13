-- Schema Extension (Retail Assets v2): Anti-hallucination columns
-- Run this AFTER schema_retail_asset_v2.sql has been applied.
--
-- Goal:
-- - Store authoritative fee text + structured fee facts for deterministic answers
-- - Enable a single verbatim answer field (`answer_text`) to prevent LLM inference

BEGIN;

-- 1) New columns
ALTER TABLE retail_asset_charge_master_v2
  ADD COLUMN IF NOT EXISTS fee_text TEXT,
  ADD COLUMN IF NOT EXISTS fee_rate_value NUMERIC(15,4),
  ADD COLUMN IF NOT EXISTS fee_rate_unit VARCHAR(20),
  ADD COLUMN IF NOT EXISTS fee_amount_value NUMERIC(15,4),
  ADD COLUMN IF NOT EXISTS fee_amount_currency VARCHAR(20),
  ADD COLUMN IF NOT EXISTS fee_period VARCHAR(20),
  ADD COLUMN IF NOT EXISTS fee_applies_to VARCHAR(30),
  ADD COLUMN IF NOT EXISTS answer_text TEXT,
  ADD COLUMN IF NOT EXISTS answer_source VARCHAR(20) NOT NULL DEFAULT 'SCHEDULE',
  ADD COLUMN IF NOT EXISTS parse_status VARCHAR(20) NOT NULL DEFAULT 'UNPARSED',
  ADD COLUMN IF NOT EXISTS parsed_from VARCHAR(20),
  ADD COLUMN IF NOT EXISTS parsed_at TIMESTAMP;

-- 2) Constraints (drop+add for idempotency)
ALTER TABLE retail_asset_charge_master_v2
  DROP CONSTRAINT IF EXISTS chk_retail_v2_has_fee_payload;
ALTER TABLE retail_asset_charge_master_v2
  ADD CONSTRAINT chk_retail_v2_has_fee_payload
  CHECK (
    -- Allow existing numeric/tiered structures OR the new text/answer fields
    fee_value IS NOT NULL
    OR tier_1_rate_value IS NOT NULL
    OR tier_2_rate_value IS NOT NULL
    OR original_charge_text IS NOT NULL
    OR fee_text IS NOT NULL
    OR answer_text IS NOT NULL
    OR fee_rate_value IS NOT NULL
    OR fee_amount_value IS NOT NULL
  );

ALTER TABLE retail_asset_charge_master_v2
  DROP CONSTRAINT IF EXISTS chk_retail_v2_rate_unit_when_rate_set;
ALTER TABLE retail_asset_charge_master_v2
  ADD CONSTRAINT chk_retail_v2_rate_unit_when_rate_set
  CHECK (fee_rate_value IS NULL OR fee_rate_unit IS NOT NULL);

ALTER TABLE retail_asset_charge_master_v2
  DROP CONSTRAINT IF EXISTS chk_retail_v2_amount_currency_when_amount_set;
ALTER TABLE retail_asset_charge_master_v2
  ADD CONSTRAINT chk_retail_v2_amount_currency_when_amount_set
  CHECK (fee_amount_value IS NULL OR fee_amount_currency IS NOT NULL);

-- 3) Indexes (for deterministic lookup and auditing)
CREATE INDEX IF NOT EXISTS ix_retail_v2_lookup_no_ctx
ON retail_asset_charge_master_v2 (loan_product, charge_type, status, effective_from DESC, priority DESC);

CREATE INDEX IF NOT EXISTS ix_retail_v2_parse_status
ON retail_asset_charge_master_v2 (parse_status);

COMMIT;

