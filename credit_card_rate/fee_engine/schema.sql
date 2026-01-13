-- Fee Engine Database Schema
-- Single Master Table Design for Card Fee Calculation
-- Effective from 01st January, 2026

-- Create ENUM types
CREATE TYPE card_category_enum AS ENUM ('CREDIT', 'DEBIT', 'PREPAID', 'ANY');
CREATE TYPE card_network_enum AS ENUM ('VISA', 'MASTERCARD', 'DINERS', 'UNIONPAY', 'FX', 'TAKAPAY', 'ANY');
CREATE TYPE fee_unit_enum AS ENUM ('BDT', 'USD', 'PERCENT', 'COUNT', 'TEXT');
CREATE TYPE fee_basis_enum AS ENUM ('PER_TXN', 'PER_YEAR', 'PER_MONTH', 'PER_VISIT', 'ON_OUTSTANDING');
CREATE TYPE condition_type_enum AS ENUM ('NONE', 'WHICHEVER_HIGHER', 'FREE_UPTO_N', 'NOTE_BASED');
CREATE TYPE status_enum AS ENUM ('ACTIVE', 'INACTIVE');

-- Master fee table (single source of truth)
CREATE TABLE card_fee_master (
    fee_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    effective_from DATE NOT NULL,
    effective_to DATE,
    charge_type VARCHAR(100) NOT NULL,
    card_category card_category_enum NOT NULL,
    card_network card_network_enum NOT NULL,
    card_product VARCHAR(50) NOT NULL,
    full_card_name VARCHAR(200),
    fee_value DECIMAL(15, 4) NOT NULL,
    fee_unit fee_unit_enum NOT NULL,
    fee_basis fee_basis_enum NOT NULL,
    min_fee_value DECIMAL(15, 4),
    min_fee_unit fee_unit_enum,
    max_fee_value DECIMAL(15, 4),
    free_entitlement_count INTEGER,
    condition_type condition_type_enum NOT NULL DEFAULT 'NONE',
    note_reference VARCHAR(20),
    priority INTEGER NOT NULL DEFAULT 100,
    status status_enum NOT NULL DEFAULT 'ACTIVE',
    remarks TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_fee_effective_dates ON card_fee_master(effective_from, effective_to);
CREATE INDEX idx_fee_charge_type ON card_fee_master(charge_type);
CREATE INDEX idx_fee_card_attrs ON card_fee_master(card_category, card_network, card_product);
CREATE INDEX idx_fee_status ON card_fee_master(status);
CREATE INDEX idx_fee_priority ON card_fee_master(priority DESC);
CREATE INDEX idx_fee_lookup ON card_fee_master(charge_type, card_category, card_network, card_product, status, effective_from, effective_to);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to auto-update updated_at
CREATE TRIGGER update_card_fee_master_updated_at
    BEFORE UPDATE ON card_fee_master
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Comments for documentation
COMMENT ON TABLE card_fee_master IS 'Master table for all card fees - single source of truth';
COMMENT ON COLUMN card_fee_master.fee_id IS 'Primary key UUID';
COMMENT ON COLUMN card_fee_master.effective_from IS 'Fee effective start date';
COMMENT ON COLUMN card_fee_master.effective_to IS 'Fee expiry date (NULL = no expiry)';
COMMENT ON COLUMN card_fee_master.charge_type IS 'Logical fee group (e.g. CASH_WITHDRAWAL_EBL_ATM)';
COMMENT ON COLUMN card_fee_master.card_category IS 'Card type: CREDIT, DEBIT, PREPAID, or ANY';
COMMENT ON COLUMN card_fee_master.card_network IS 'Card network: VISA, MASTERCARD, etc., or ANY';
COMMENT ON COLUMN card_fee_master.card_product IS 'Product tier: Classic, Gold, Platinum, etc., or ANY';
COMMENT ON COLUMN card_fee_master.fee_value IS 'Main fee value';
COMMENT ON COLUMN card_fee_master.fee_unit IS 'Fee unit: BDT, USD, PERCENT, COUNT, or TEXT';
COMMENT ON COLUMN card_fee_master.fee_basis IS 'Fee basis: PER_TXN, PER_YEAR, PER_MONTH, PER_VISIT, ON_OUTSTANDING';
COMMENT ON COLUMN card_fee_master.min_fee_value IS 'Minimum fee for whichever higher logic';
COMMENT ON COLUMN card_fee_master.free_entitlement_count IS 'Number of free items (e.g., 1st card free, 2 visits free)';
COMMENT ON COLUMN card_fee_master.condition_type IS 'Condition: NONE, WHICHEVER_HIGHER, FREE_UPTO_N, NOTE_BASED';
COMMENT ON COLUMN card_fee_master.note_reference IS 'Note number if condition_type is NOTE_BASED';
COMMENT ON COLUMN card_fee_master.priority IS 'Higher priority wins when multiple rules match';
