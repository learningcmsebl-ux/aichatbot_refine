-- Retail Asset Charges v2 Schema
-- Adds charge_context field for deterministic selection
-- Creates v2 table and backward-compatible VIEW

-- 1) ENUM Types (create once, skip if exists)
DO $$ BEGIN
  CREATE TYPE loan_product_enum AS ENUM (
    'FAST_CASH_OD','FAST_LOAN_SECURED_EMI','EDU_LOAN_SECURED','EDU_LOAN_UNSECURED',
    'OTHER_EMI_LOANS','EXECUTIVE_LOAN','ASSURE_LOAN','WOMENS_LOAN','AUTO_LOAN',
    'TWO_WHEELER_LOAN','HOME_LOAN','HOME_CREDIT','MORTGAGE_LOAN','HOME_LOAN_PAYMENT_PROTECTION',
    'OTHER_CHARGES','ANY'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE retail_charge_type_enum AS ENUM (
    'PROCESSING_FEE','LIMIT_ENHANCEMENT_FEE','LIMIT_REDUCTION_FEE','LIMIT_CANCELLATION_FEE',
    'RENEWAL_FEE','PARTIAL_PAYMENT_FEE','EARLY_SETTLEMENT_FEE','SECURITY_LIEN_CONFIRMATION',
    'QUOTATION_CHANGE_FEE','NOTARIZATION_FEE','NOC_FEE','PENAL_INTEREST','CIB_CHARGE','CPV_CHARGE',
    'VETTING_VALUATION_CHARGE','SECURITY_REPLACEMENT_FEE','STAMP_CHARGE',
    'LOAN_OUTSTANDING_CERTIFICATE_FEE','RESCHEDULE_RESTRUCTURE_FEE','RESCHEDULE_RESTRUCTURE_EXIT_FEE',
    'OTHER'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE fee_unit_enum AS ENUM ('BDT','USD','PERCENT','TEXT','ACTUAL_COST','COUNT');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE fee_basis_enum AS ENUM ('PER_LOAN','PER_AMOUNT','PER_INSTALLMENT','PER_INSTANCE','ON_OUTSTANDING','ON_OVERDUE','PER_QUOTATION_CHANGE');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE condition_type_enum AS ENUM ('NONE','WHICHEVER_HIGHER','TIERED','NOTE_BASED');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE status_enum AS ENUM ('ACTIVE','INACTIVE');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE charge_context_enum AS ENUM ('GENERAL','ON_LIMIT','ON_ENHANCED_AMOUNT','ON_REDUCED_AMOUNT');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- 2) New v2 master table
CREATE TABLE IF NOT EXISTS retail_asset_charge_master_v2 (
  charge_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  effective_from DATE NOT NULL,
  effective_to   DATE,

  loan_product      loan_product_enum NOT NULL,
  loan_product_name VARCHAR(200),

  charge_type    retail_charge_type_enum NOT NULL,
  charge_context charge_context_enum NOT NULL DEFAULT 'GENERAL',

  charge_title       VARCHAR(200) NOT NULL,     -- short label for UI
  charge_description VARCHAR(500),              -- longer text for schedule / audit

  -- Main fee definition (for NONE / WHICHEVER_HIGHER / NOTE_BASED)
  fee_value NUMERIC(15,4),
  fee_unit  fee_unit_enum,
  fee_basis fee_basis_enum,

  -- Money caps (always money/currency)
  min_fee_value NUMERIC(15,4),
  min_fee_currency fee_unit_enum DEFAULT 'BDT', -- only BDT/USD allowed by validation
  max_fee_value NUMERIC(15,4),
  max_fee_currency fee_unit_enum DEFAULT 'BDT',

  -- Tiered fee block (for condition_type=TIERED)
  tier_1_threshold_amount NUMERIC(15,4),
  tier_1_threshold_currency fee_unit_enum DEFAULT 'BDT',

  tier_1_rate_value NUMERIC(15,4),
  tier_1_rate_unit  fee_unit_enum,             -- should be PERCENT (or TEXT)
  tier_1_max_fee_value NUMERIC(15,4),
  tier_1_max_fee_currency fee_unit_enum DEFAULT 'BDT',

  tier_2_threshold_amount NUMERIC(15,4),
  tier_2_threshold_currency fee_unit_enum DEFAULT 'BDT',
  tier_2_rate_value NUMERIC(15,4),
  tier_2_rate_unit  fee_unit_enum,             -- should be PERCENT (or TEXT)
  tier_2_max_fee_value NUMERIC(15,4),
  tier_2_max_fee_currency fee_unit_enum DEFAULT 'BDT',

  condition_type condition_type_enum NOT NULL DEFAULT 'NONE',
  condition_description TEXT,
  note_reference VARCHAR(50),
  remarks TEXT,

  -- Employee pricing (kept from v1)
  employee_fee_value NUMERIC(15,4),
  employee_fee_unit fee_unit_enum,
  employee_fee_description VARCHAR(200),

  -- Category-based pricing (kept from v1)
  category_a_fee_value NUMERIC(15,4),
  category_a_fee_unit fee_unit_enum,
  category_b_fee_value NUMERIC(15,4),
  category_b_fee_unit fee_unit_enum,
  category_c_fee_value NUMERIC(15,4),
  category_c_fee_unit fee_unit_enum,

  -- Additional information
  original_charge_text TEXT,

  priority INTEGER NOT NULL DEFAULT 100,
  status   status_enum NOT NULL DEFAULT 'ACTIVE',

  created_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
  updated_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),

  -- Audit fields
  created_by VARCHAR(50),
  updated_by VARCHAR(50),
  approved_by VARCHAR(50),
  approved_at TIMESTAMP
);

-- 3) Deterministic uniqueness (prevents future ambiguity)
-- one "meaning" per version start date
CREATE UNIQUE INDEX IF NOT EXISTS uq_retail_v2_rule
ON retail_asset_charge_master_v2 (loan_product, charge_type, charge_context, effective_from)
WHERE status = 'ACTIVE';

-- 4) Fast lookups
CREATE INDEX IF NOT EXISTS ix_retail_v2_lookup
ON retail_asset_charge_master_v2 (loan_product, charge_type, charge_context, status, effective_from, effective_to);

CREATE INDEX IF NOT EXISTS ix_retail_v2_effective_dates
ON retail_asset_charge_master_v2 (effective_from, effective_to);

CREATE INDEX IF NOT EXISTS ix_retail_v2_status
ON retail_asset_charge_master_v2 (status);

CREATE INDEX IF NOT EXISTS ix_retail_v2_priority
ON retail_asset_charge_master_v2 (priority DESC);

-- 5) Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_retail_asset_charge_v2_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = (now() AT TIME ZONE 'utc');
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 6) Trigger to auto-update updated_at
DROP TRIGGER IF EXISTS update_retail_asset_charge_master_v2_updated_at ON retail_asset_charge_master_v2;
CREATE TRIGGER update_retail_asset_charge_master_v2_updated_at
    BEFORE UPDATE ON retail_asset_charge_master_v2
    FOR EACH ROW
    EXECUTE FUNCTION update_retail_asset_charge_v2_updated_at();

-- 7) Comments for documentation
COMMENT ON TABLE retail_asset_charge_master_v2 IS 'Master table for all retail asset/loan charges v2 - with charge_context for deterministic selection';
COMMENT ON COLUMN retail_asset_charge_master_v2.charge_id IS 'Primary key UUID';
COMMENT ON COLUMN retail_asset_charge_master_v2.loan_product IS 'Normalized loan product type';
COMMENT ON COLUMN retail_asset_charge_master_v2.loan_product_name IS 'Original product name from source document';
COMMENT ON COLUMN retail_asset_charge_master_v2.charge_type IS 'Type of charge (processing fee, partial payment, etc.)';
COMMENT ON COLUMN retail_asset_charge_master_v2.charge_context IS 'Second-level discriminator: GENERAL, ON_LIMIT, ON_ENHANCED_AMOUNT, ON_REDUCED_AMOUNT';
COMMENT ON COLUMN retail_asset_charge_master_v2.charge_title IS 'Short label for UI display';
COMMENT ON COLUMN retail_asset_charge_master_v2.charge_description IS 'Longer description for schedule / audit';
COMMENT ON INDEX uq_retail_v2_rule IS 'Unique constraint ensuring deterministic charge selection: (loan_product, charge_type, charge_context, effective_from)';

-- 8) Backward Compatible VIEW (maps v2 back to v1 structure)
-- This allows existing code using raw SQL queries on 'retail_asset_charge_master' to continue working
-- Note: SQLAlchemy ORM uses the v2 table directly (via __tablename__), so it bypasses this VIEW
CREATE OR REPLACE VIEW retail_asset_charge_master AS
SELECT
  charge_id,
  effective_from,
  effective_to,
  loan_product::VARCHAR(50) AS loan_product,
  loan_product_name,
  charge_type::VARCHAR(50) AS charge_type,
  COALESCE(charge_title, charge_description) AS charge_description,  -- Use charge_title if available, fallback to description
  fee_value,
  fee_unit::VARCHAR(20) AS fee_unit,
  fee_basis::VARCHAR(20) AS fee_basis,
  -- Tier fields: map v2 names back to v1 names
  tier_1_threshold_amount AS tier_1_threshold,
  tier_1_rate_value AS tier_1_fee_value,
  tier_1_rate_unit AS tier_1_fee_unit,
  tier_1_max_fee_value AS tier_1_max_fee,
  tier_2_threshold_amount AS tier_2_threshold,
  tier_2_rate_value AS tier_2_fee_value,
  tier_2_rate_unit AS tier_2_fee_unit,
  tier_2_max_fee_value AS tier_2_max_fee,
  min_fee_value,
  COALESCE(min_fee_currency::VARCHAR(20), 'BDT') AS min_fee_unit,  -- Default to BDT if NULL
  max_fee_value,
  COALESCE(max_fee_currency::VARCHAR(20), 'BDT') AS max_fee_unit,  -- Default to BDT if NULL
  condition_type::VARCHAR(20) AS condition_type,
  condition_description,
  employee_fee_value,
  employee_fee_unit::VARCHAR(20) AS employee_fee_unit,
  employee_fee_description,
  category_a_fee_value,
  category_a_fee_unit::VARCHAR(20) AS category_a_fee_unit,
  category_b_fee_value,
  category_b_fee_unit::VARCHAR(20) AS category_b_fee_unit,
  category_c_fee_value,
  category_c_fee_unit::VARCHAR(20) AS category_c_fee_unit,
  original_charge_text,
  note_reference,
  priority,
  status::VARCHAR(20) AS status,
  remarks,
  created_at,
  updated_at
FROM retail_asset_charge_master_v2;

COMMENT ON VIEW retail_asset_charge_master IS 'Backward-compatible view mapping v2 table structure to v1 structure. For legacy raw SQL queries only - SQLAlchemy ORM queries v2 table directly.';

