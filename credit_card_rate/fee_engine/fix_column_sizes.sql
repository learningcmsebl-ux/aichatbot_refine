-- Fix column size issues for data truncation
-- Run this before re-importing data

-- Increase charge_type from VARCHAR(100) to VARCHAR(255)
ALTER TABLE card_fee_master 
ALTER COLUMN charge_type TYPE VARCHAR(255);

-- Increase card_product from VARCHAR(50) to VARCHAR(100) 
-- (Some values like "Skybanking" and long product names need more space)
ALTER TABLE card_fee_master 
ALTER COLUMN card_product TYPE VARCHAR(100);

-- Add comment
COMMENT ON COLUMN card_fee_master.charge_type IS 'Logical fee group - increased to VARCHAR(255) to accommodate long charge type names';
COMMENT ON COLUMN card_fee_master.card_product IS 'Product tier - increased to VARCHAR(100) to accommodate product names like Skybanking';










