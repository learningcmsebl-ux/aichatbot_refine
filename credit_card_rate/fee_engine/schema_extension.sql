-- Schema Extension: Add product_line column to support multiple product lines
-- Run this after the initial schema.sql has been applied

-- Add product_line column
ALTER TABLE card_fee_master 
ADD COLUMN IF NOT EXISTS product_line VARCHAR(50) DEFAULT 'CREDIT_CARDS';

-- Update existing records to have product_line (if any exist)
UPDATE card_fee_master 
SET product_line = 'CREDIT_CARDS' 
WHERE product_line IS NULL;

-- Make product_line NOT NULL after setting defaults
ALTER TABLE card_fee_master 
ALTER COLUMN product_line SET NOT NULL;

-- Add index for product_line lookups
CREATE INDEX IF NOT EXISTS idx_fee_product_line ON card_fee_master(product_line);

-- Update composite index to include product_line
DROP INDEX IF EXISTS idx_fee_lookup;
CREATE INDEX idx_fee_lookup ON card_fee_master(charge_type, product_line, card_category, card_network, card_product, status, effective_from, effective_to);

-- Add comment
COMMENT ON COLUMN card_fee_master.product_line IS 'Product line: CREDIT_CARDS, SKYBANKING, PRIORITY_BANKING, RETAIL_ASSETS';











