-- Migration: Add charge_context ENUM and column to retail_asset_charge_master
-- This provides a second-level discriminator to handle data collisions
-- where multiple records have the same loan_product + charge_type

-- Create charge_context ENUM
CREATE TYPE charge_context_enum AS ENUM (
    'ON_LIMIT',
    'ON_ENHANCED_AMOUNT',
    'ON_REDUCED_AMOUNT',
    'ON_LOAN_AMOUNT',
    'TIERED',
    'GENERAL'
);

-- Add charge_context column (nullable initially to allow gradual migration)
ALTER TABLE retail_asset_charge_master 
ADD COLUMN charge_context charge_context_enum;

-- Create index for charge_context lookups
CREATE INDEX idx_retail_charge_context ON retail_asset_charge_master(charge_context);

-- Update existing records: extract charge_context from charge_description
-- This uses the same logic as extract_charge_context() function
UPDATE retail_asset_charge_master
SET charge_context = CASE
    WHEN LOWER(charge_description) LIKE '%limit enhancement%' 
         OR LOWER(charge_description) LIKE '%enhancement%' 
         OR LOWER(charge_description) LIKE '%enhance limit%'
         OR LOWER(charge_description) LIKE '%limit increase%' THEN 'ON_ENHANCED_AMOUNT'::charge_context_enum
    WHEN LOWER(charge_description) LIKE '%limit reduction%' 
         OR LOWER(charge_description) LIKE '%reduction%' 
         OR LOWER(charge_description) LIKE '%reduce limit%' THEN 'ON_REDUCED_AMOUNT'::charge_context_enum
    WHEN LOWER(charge_description) LIKE '%limit%' 
         OR LOWER(charge_description) LIKE '%on limit%' THEN 'ON_LIMIT'::charge_context_enum
    WHEN LOWER(charge_description) LIKE '%loan amount%' 
         OR LOWER(charge_description) LIKE '%on loan amount%' 
         OR LOWER(charge_description) LIKE '%of loan%' THEN 'ON_LOAN_AMOUNT'::charge_context_enum
    WHEN LOWER(charge_description) LIKE '%tier%' 
         OR LOWER(charge_description) LIKE '%tiered%' 
         OR LOWER(charge_description) LIKE '%up to%' 
         OR LOWER(charge_description) LIKE '%above%' THEN 'TIERED'::charge_context_enum
    ELSE 'GENERAL'::charge_context_enum
END
WHERE charge_context IS NULL;

-- Add uniqueness constraint: (loan_product, charge_type, charge_context, effective_from)
-- This ensures deterministic selection and prevents true collisions
CREATE UNIQUE INDEX idx_retail_charge_unique_lookup 
ON retail_asset_charge_master(loan_product, charge_type, charge_context, effective_from)
WHERE status = 'ACTIVE';

-- Optional: After verifying all records have charge_context, make it NOT NULL
-- Uncomment the following line after data migration is complete:
-- ALTER TABLE retail_asset_charge_master ALTER COLUMN charge_context SET NOT NULL;

-- Comments for documentation
COMMENT ON COLUMN retail_asset_charge_master.charge_context IS 'Second-level discriminator for charges with same loan_product + charge_type. Values: ON_LIMIT, ON_ENHANCED_AMOUNT, ON_REDUCED_AMOUNT, ON_LOAN_AMOUNT, TIERED, GENERAL';
COMMENT ON INDEX idx_retail_charge_unique_lookup IS 'Unique constraint ensuring deterministic charge selection: (loan_product, charge_type, charge_context, effective_from)';

