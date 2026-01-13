-- Skybanking Fee Master Table
-- For fees and charges related to EBL Skybanking mobile banking app
-- Effective from 27th November 2025

CREATE TABLE IF NOT EXISTS skybanking_fee_master (
    fee_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    effective_from DATE NOT NULL,
    effective_to DATE,
    charge_type VARCHAR(100) NOT NULL,
    network VARCHAR(50),  -- VISA, etc. (nullable)
    product VARCHAR(50) NOT NULL,  -- Skybanking
    product_name VARCHAR(200) NOT NULL,  -- Service name (e.g., "Account Certificate", "Fund Transfer")
    fee_amount DECIMAL(15, 4),  -- Can be NULL for "Variable" or "Free"
    fee_unit VARCHAR(20) NOT NULL,  -- BDT, PERCENTAGE
    fee_basis VARCHAR(50) NOT NULL,  -- YEARLY, PER_REQUEST, PER_TRANSACTION
    is_conditional BOOLEAN NOT NULL DEFAULT FALSE,
    condition_description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    remarks TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_skybanking_effective_dates ON skybanking_fee_master(effective_from, effective_to);
CREATE INDEX IF NOT EXISTS idx_skybanking_charge_type ON skybanking_fee_master(charge_type);
CREATE INDEX IF NOT EXISTS idx_skybanking_product ON skybanking_fee_master(product);
CREATE INDEX IF NOT EXISTS idx_skybanking_status ON skybanking_fee_master(status);

-- Trigger to update updated_at
CREATE OR REPLACE FUNCTION update_skybanking_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_skybanking_fee_master_updated_at
    BEFORE UPDATE ON skybanking_fee_master
    FOR EACH ROW
    EXECUTE FUNCTION update_skybanking_updated_at();








