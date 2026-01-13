-- Lockdown v1 table and add guardrails for v2
-- Run this after migration is complete and verified

-- ============================================================================
-- 1) Lock down v1 table (prevent accidental updates)
-- ============================================================================
-- Revoke write permissions on old v1 table to prevent accidental modifications
-- Note: We keep SELECT for backward compatibility views/queries if needed

REVOKE INSERT, UPDATE, DELETE ON retail_asset_charge_master FROM PUBLIC;
-- If you have specific app roles, revoke from them too:
-- REVOKE INSERT, UPDATE, DELETE ON retail_asset_charge_master FROM your_app_role;

COMMENT ON TABLE retail_asset_charge_master IS 'DEPRECATED: Use retail_asset_charge_master_v2 instead. This table is read-only and will be removed in a future migration.';

-- ============================================================================
-- 2) Add exclusion constraint to prevent future data drift (hard guardrail)
-- ============================================================================
-- This ensures no overlapping effective date ranges for the same
-- (loan_product, charge_type, charge_context) combination when status='ACTIVE'

-- Enable btree_gist extension if not already enabled
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- Add exclusion constraint to prevent overlaps
-- This guarantees "deterministic forever" even if someone inserts new rows later
ALTER TABLE retail_asset_charge_master_v2
ADD CONSTRAINT no_overlap_active_rules
EXCLUDE USING gist (
  loan_product WITH =,
  charge_type WITH =,
  charge_context WITH =,
  daterange(effective_from, COALESCE(effective_to, 'infinity'::date), '[]') WITH &&
)
WHERE (status = 'ACTIVE');

COMMENT ON CONSTRAINT no_overlap_active_rules ON retail_asset_charge_master_v2 IS 
'Prevents overlapping effective date ranges for the same (loan_product, charge_type, charge_context) combination when status=ACTIVE. Ensures deterministic fee selection.';

